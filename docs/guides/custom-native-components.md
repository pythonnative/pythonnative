# Custom native components

PythonNative renders through native **component managers**: a Swift
`PNComponentManager` in `PythonNativeKit` and a Kotlin `ComponentManager`
in the `pythonnative` Gradle module own every `UIView` and
`android.view.View`. Python owns the element tree, reconciliation, and
layout, and ships each commit to native as one transaction (see
[The native bridge](../concepts/bridge.md)).

Adding your own component means writing one manager per platform,
registering both under an element name, and giving Python a typed
factory for it. Custom components then participate in reconciliation,
flex layout, gestures, animations, and Fast Refresh exactly like the
built-ins.

This guide builds a small `Badge` widget end to end and shows how to
ship it as an installable PyPI plugin.

## The pieces

| Piece | Where | Role |
|---|---|---|
| `Props` dataclass | Python | Declares the props your component accepts, with types and defaults. |
| `PNComponentManager` subclass | Swift (`ios/`) | Creates the `UIView`, applies props, measures, handles commands. |
| `ComponentManager` subclass | Kotlin (`android/`) | Same for `android.view.View`. |
| `PNPlugin` entry | Swift and Kotlin | Registers the managers (and any native modules) by name. |
| `pn_plugin.json` | Plugin root | Tells `pn build` which entry to call on each platform. |
| `register_component` + `element_factory` | Python | Declares the element name and exposes the typed factory. |
| `ViewHandler` (optional) | Python | Off-device stand-in so unit tests can render the component without a device. |

Layout stays in Python: managers never read `flex`, `margin`, or
`padding`. They receive absolute frames through `setFrame` and answer
`measure` for content-sized leaves.

## Project layout

```text
my_badge/
    pyproject.toml
    my_badge/
        __init__.py          # Props, register_component, Badge factory
        desktop.py           # optional ViewHandler for pn preview
        native/
            __init__.py      # empty; makes the directory importable
            pn_plugin.json
            ios/
                BadgeManager.swift
                MyBadgePlugin.swift
            android/
                com/example/badge/
                    BadgeManager.kt
                    MyBadgePlugin.kt
```

## 1. Typed props

`my_badge/__init__.py`:

```python
from dataclasses import dataclass
from typing import Optional

import pythonnative as pn
from pythonnative.sdk import Props, element_factory, register_component


@dataclass(frozen=True)
class BadgeProps(Props):
    """Visible state of a Badge.

    Every field defaults so callers pass only what they care about.
    ``style`` is the standard ``StyleProp`` accepted by every built-in.
    """

    text: str = ""
    color: str = "#FF3B30"
    text_color: str = "#FFFFFF"
    style: Optional[pn.StyleProp] = None


register_component(name="Badge", props=BadgeProps)
Badge = element_factory("Badge")
```

`Props` is a frozen dataclass, so the reconciler's equality diff stays
cheap. `register_component` declares the element name; the factory
validates kwargs against `BadgeProps`, resolves `style` through
[`resolve_style`][pythonnative.style.resolve_style], and returns a
regular [`Element`][pythonnative.Element].

Props cross the bridge as JSON. Stick to strings, numbers, booleans,
lists, and dicts; callables become events (see below) and anything else
is dropped with a warning.

## 2. The Swift manager

`native/ios/BadgeManager.swift`:

```swift
import PythonNativeKit
import UIKit

final class BadgeView: UIView {
    let label = UILabel()

    override init(frame: CGRect) {
        super.init(frame: frame)
        layer.cornerRadius = 12
        clipsToBounds = true
        label.textAlignment = .center
        label.font = .systemFont(ofSize: 13, weight: .semibold)
        addSubview(label)
    }

    required init?(coder: NSCoder) { fatalError() }

    override func layoutSubviews() {
        super.layoutSubviews()
        label.frame = bounds
    }
}

public final class BadgeManager: PNComponentManager {
    public override func makeView(props: [String: Any]) -> UIView {
        BadgeView(frame: .zero)
    }

    public override func apply(view: UIView, props: [String: Any], initial: Bool) {
        super.apply(view: view, props: props, initial: initial)  // background, border, opacity, ...
        guard let badge = view as? BadgeView else { return }
        if let text = PNProps.string(props["text"]) { badge.label.text = text }
        if let color = PNProps.string(props["color"]) { badge.backgroundColor = PNColor.parse(color) }
        if let textColor = PNProps.string(props["text_color"]) { badge.label.textColor = PNColor.parse(textColor) }
    }

    public override func measure(view: UIView, maxW: CGFloat, maxH: CGFloat) -> CGSize {
        guard let badge = view as? BadgeView else { return .zero }
        let fit = badge.label.sizeThatFits(CGSize(width: max(0, maxW - 24), height: maxH))
        return CGSize(width: fit.width + 24, height: fit.height + 8)
    }
}
```

`apply` receives the full props on create (`initial == true`) and only
the changed keys on update; a removed prop arrives as `NSNull`. Call
`mergedProps(view)` when you need the complete current set.

## 3. The Kotlin manager

`native/android/com/example/badge/BadgeManager.kt`:

```kotlin
package com.example.badge

import android.content.Context
import android.graphics.drawable.GradientDrawable
import android.view.Gravity
import android.view.View
import android.widget.TextView
import com.pythonnative.runtime.components.ComponentManager
import com.pythonnative.runtime.components.PNColor
import org.json.JSONObject

class BadgeManager : ComponentManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View =
        TextView(context).apply {
            gravity = Gravity.CENTER
            background = GradientDrawable().apply { cornerRadius = 12 * resources.displayMetrics.density }
        }

    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        super.applyProps(view, props, initial)
        val badge = view as TextView
        if (props.has("text")) badge.text = props.optString("text")
        if (props.has("color")) (badge.background as GradientDrawable).setColor(PNColor.parse(props.optString("color")))
        if (props.has("text_color")) badge.setTextColor(PNColor.parse(props.optString("text_color")))
    }

    override fun measure(view: View, maxWidth: Double, maxHeight: Double): FloatArray {
        val base = super.measure(view, maxWidth, maxHeight)
        return floatArrayOf(base[0] + 24f, base[1] + 8f)
    }
}
```

Geometry on Android is in **dp** on both sides of the bridge; the base
class converts to pixels in `setFrame` and back in `measure`.

## 4. Register both in a plugin entry

`native/ios/MyBadgePlugin.swift`:

```swift
import PythonNativeKit

public enum MyBadgePlugin: PNPlugin {
    public static func register(into registry: PNRegistry) {
        registry.registerComponent("Badge") { BadgeManager() }
    }
}
```

`native/android/com/example/badge/MyBadgePlugin.kt`:

```kotlin
package com.example.badge

import com.pythonnative.runtime.bridge.PNPlugin
import com.pythonnative.runtime.bridge.PNRegistry

object MyBadgePlugin : PNPlugin {
    override fun register(registry: PNRegistry) {
        registry.registerComponent("Badge") { BadgeManager() }
    }
}
```

`native/pn_plugin.json`:

```json
{
  "ios": {"entry": "MyBadgePlugin"},
  "android": {"entry": "com.example.badge.MyBadgePlugin"}
}
```

A plugin may declare only one platform; the component then renders as a
labelled placeholder on the other.

## 5. Tell `pn build` about the plugin

Point the `pythonnative.plugins` entry point at the directory holding
`pn_plugin.json`, and the `pythonnative.handlers` entry point at the
Python module that calls `register_component`:

```toml
[project.entry-points."pythonnative.plugins"]
my_badge = "my_badge.native"

[project.entry-points."pythonnative.handlers"]
my_badge = "my_badge"
```

`pn build` (and `pn run`) copies `ios/*.swift` into
`PythonNativeKit/Sources/PythonNativeKit/Plugins/my_badge/` and
`android/**/*.kt` into the `pythonnative` Gradle module, then regenerates
the registration file that calls `MyBadgePlugin.register` on each
platform. SwiftPM and Gradle compile whatever lands there; no Xcode or
Gradle project edits are involved.

For native code that lives inside an app rather than a package, list
the directory in `pythonnative.toml` instead of an entry point:

```toml
[plugins]
paths = ["native/badge"]
```

## 6. Use it

```python
import pythonnative as pn
from my_badge import Badge


@pn.component
def InboxRow():
    count, _ = pn.use_state(3)
    return pn.Row(
        pn.Text("Inbox"),
        Badge(text=str(count), color="#0A84FF"),
        style={"spacing": 8, "align_items": "center"},
    )
```

## Events

Callable props never cross the bridge. When a `Badge(on_press=...)`
element is created, Python strips the callback into the process-wide
[`EventRegistry`][pythonnative.events.EventRegistry] and sends the prop
`_pn_events: ["on_press"]` instead. The manager wires a listener once
and fires by tag:

```swift
// Swift: inside createView / didCreate
badge.addGestureRecognizer(UITapGestureRecognizer(target: self, action: #selector(tapped(_:))))

@objc private func tapped(_ recognizer: UITapGestureRecognizer) {
    guard let view = recognizer.view else { return }
    PNEvents.emitIfWired(view, "on_press")
}
```

```kotlin
// Kotlin
view.setOnClickListener { PNEvents.fire(it, "on_press") }
```

The payload is a positional argument list, so `PNEvents.emit(view,
"on_change", [newText])` calls `on_change(new_text)` in Python. A
re-render that only swaps the lambda costs zero native calls.

## Commands

Imperative actions (`focus`, `scroll_to_offset`, ...) arrive through
`command(view:name:args:)`. Return a JSON-encodable value or `nil`:

```swift
public override func command(view: UIView, name: String, args: [String: Any]) -> Any? {
    switch name {
    case "pulse": (view as? BadgeView)?.pulse(); return nil
    default: return super.command(view: view, name: name, args: args)
    }
}
```

Python reaches it through the tag the reconciler publishes on a `ref`:

```python
from pythonnative.native_views import get_registry

badge_ref = pn.use_ref(None)
...
get_registry().command(badge_ref._pn_tag, "pulse")
```

## Browser preview and tests

Neither the [browser preview](browser-preview.md) nor
`pythonnative.testing` loads Swift or Kotlin. In the preview, a
component with no browser implementation validates its props, takes
part in layout, and renders as a labeled placeholder box, so the
layout around it stays truthful while you work on everything else.

Off device (the `"test"` platform), register a Python
[`ViewHandler`][pythonnative.sdk.ViewHandler] so the component has a
stand-in; the `@native_component` decorator does this and declares the
element in one step:

```python
# my_badge/fallback.py
from pythonnative.sdk import ViewHandler, native_component

from . import BadgeProps


@native_component("Badge", props=BadgeProps)
class FallbackBadgeHandler(ViewHandler):
    def create(self, tag, props):
        return {"tag": tag, "text": props.get("text", "")}

    def update(self, view, changed):
        if "text" in changed:
            view["text"] = changed["text"] or ""

    def measure_intrinsic(self, view, max_w, max_h):
        return (8.0 * len(view["text"]) + 12.0, 20.0)
```

Unit tests use the recording backend from
[`pythonnative.testing`](../api/testing.md):

```python
from pythonnative.testing import render
from my_badge import Badge


def test_badge_renders_text() -> None:
    result = render(Badge(text="3"))
    badge = result.get_by_type("Badge")
    assert badge.props["text"] == "3"
```

Native managers get their own tests: `PythonNativeKit` ships an XCTest
target and the Gradle module a JUnit target, both driving managers with
decoded transactions. See [Testing](testing.md).

## Validation rules

| Call site | Result |
|---|---|
| `Badge(text="3")` | Validated against `BadgeProps`. Unknown fields raise `TypeError`. |
| `Badge(props=BadgeProps(text="3"))` | Used directly. `style` is still resolved if present. |
| `Badge(props=..., text="3")` | `TypeError`: pass either `props` *or* keyword arguments. |
| `Badge(unknown=...)` | `TypeError("Invalid props for 'Badge': ...")`. |

For `register_component` calls without a `props` class, kwargs flow
straight to the `Element` and aren't validated.

## Next steps

- Protocol details: [The native bridge](../concepts/bridge.md).
- SDK reference: [`pythonnative.sdk`](../api/sdk.md).
- Wrap a device API instead of a widget: [Native modules](native-modules.md).
