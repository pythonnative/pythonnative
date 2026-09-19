# Custom native components

PythonNative renders through native **component managers**: a Swift
`PNComponentManager` in `PythonNativeKit` and a Kotlin `ComponentManager`
in the `pythonnative` Gradle module own every `UIView` and
`android.view.View`. Python owns the element tree and reconciliation and
ships styles in each validated commit (see
[The native bridge](../concepts/bridge.md)).

Adding your own component means declaring its props once in Python,
generating the native contract from that declaration, and writing one
manager per platform against the generated types. Custom components
then participate in reconciliation, flex layout, gestures, animations,
and Fast Refresh exactly like the built-ins. There is no Python-side
view handler to write: headless tests render the component into the
same fake backend as every built-in, and the browser preview draws it
as a labeled placeholder.

This guide builds a small `Badge` widget end to end and shows how to
ship it as an installable PyPI plugin. The repository's
[`examples/inbox-extension`](https://github.com/pythonnative/pythonnative/tree/main/examples/inbox-extension)
is the complete reference: a native `InboxBadge` with a typed press
event, an `InboxTools` module with a cancellable async method, bundled
resources, and real SwiftPM and Maven dependencies.

## The pieces

| Piece | Where | Role |
|---|---|---|
| `Props` dataclass | Python | Declares the props your component accepts, with types, defaults, and `NativeField` metadata. |
| `define_component(name, props)` | Python | Registers the props schema and returns the typed element factory. |
| `schema.json` | Plugin root | The generated contract; `pn codegen` writes it from the Python declarations. |
| `PNTypedComponentManager<Props>` subclass | Swift (`ios/`) | Creates the `UIView`, applies checked props, measures, handles commands. |
| `TypedComponentManager<Props>` subclass | Kotlin (`android/`) | Same for `android.view.View`. |
| `PNPlugin` entry | Swift and Kotlin | Registers the managers (and any native modules) by name. |
| `pn_plugin.json` | Plugin root | Tells `pn build` which entry to call on each platform and which contract file to merge. |

The native runtime runs Yoga over the committed styles. Managers receive
absolute frames through `setFrame` and implement `measure` for content-sized
leaves. See [Generated native contracts](native-contracts.md) for the
schema vocabulary, typed adapters, and plugin contract registration.

## Project layout

```text
my_badge/
    pyproject.toml
    generate_contracts.py        # regenerates native/schema.json
    src/my_badge/
        __init__.py              # Props, define_component, Badge factory
        native/
            __init__.py          # empty; makes the directory importable
            pn_plugin.json
            schema.json          # generated
            ios/
                BadgeManager.swift
                MyBadgePlugin.swift
            android/
                com/example/badge/
                    BadgeManager.kt
                    MyBadgePlugin.kt
```

## 1. Typed props

`src/my_badge/__init__.py`:

```python
from dataclasses import dataclass
from typing import Annotated, Any, Callable

from pythonnative.sdk import Props, define_component
from pythonnative.sdk.schema import NativeField


@dataclass(frozen=True)
class BadgeProps(Props):
    """Visible state of a Badge.

    Every field defaults so callers pass only what they care about.
    ``style`` is added to the factory automatically.
    """

    text: Annotated[str, NativeField(invalidates_layout=True)] = ""
    color: str = "#FF3B30"
    text_color: str = "#FFFFFF"
    on_press: Callable[[], Any] | None = None


Badge = define_component("Badge", BadgeProps)
```

`Props` is a frozen dataclass, so the reconciler's equality diff stays
cheap. [`define_component`][pythonnative.sdk.define_component] registers
`BadgeProps` as the component's schema (the contract generator emits it,
the commit validator checks it) and returns the factory, which validates
keyword arguments against `BadgeProps`, resolves `style` through
[`resolve_style`][pythonnative.style.resolve_style], and returns a regular
[`Element`][pythonnative.Element]. `NativeField(invalidates_layout=True)`
tells the renderer that a `text` change needs a new measurement.

Props cross the bridge as JSON. Stick to strings, numbers, booleans,
lists, dicts, and the record types described in
[Generated native contracts](native-contracts.md); callables become
events (see below).

## 2. Generate the contract

`generate_contracts.py` filters the manifest to your own components and
writes `native/schema.json` (the Inbox extension's script is the model):

```python
import json
from pathlib import Path

import my_badge  # noqa: F401  (runs define_component)

from pythonnative.sdk.schema import manifest

spec = manifest()
spec["components"] = {"Badge": spec["components"]["Badge"]}
spec["modules"] = {}
root = Path(__file__).with_name("src") / "my_badge" / "native"
root.joinpath("schema.json").write_text(json.dumps(spec, indent=2) + "\n")
```

Run it after every change to `BadgeProps` and commit the result next to
the declarations. `pn codegen --module my_badge --output generated` also
emits the Swift `NativeProps` and Kotlin sources you can read while
writing the managers; the typed `BadgeProps` record they contain is what
the managers below receive.

## 3. The Swift manager

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

final class BadgeManager: PNTypedComponentManager<BadgeProps> {
    init() { super.init(BadgeProps.self) }

    override func makeView(props: [String: Any]) -> UIView {
        BadgeView(frame: .zero)
    }

    override func applyTyped(view: UIView, props: BadgeProps, initial: Bool) {
        PNViewStyler.applyCommon(view, props.values)   // background, border, opacity, ...
        guard let badge = view as? BadgeView else { return }
        if initial || props.has_text { badge.label.text = props.text ?? "" }
        if initial || props.has_color { badge.backgroundColor = PNColor.parse(props.color ?? "#FF3B30") }
        if initial || props.has_text_color { badge.label.textColor = PNColor.parse(props.text_color ?? "#FFFFFF") }
    }

    override func measure(view: UIView, maxW: CGFloat, maxH: CGFloat) -> CGSize {
        guard let badge = view as? BadgeView else { return .zero }
        let fit = badge.label.sizeThatFits(CGSize(width: max(0, maxW - 24), height: maxH))
        return CGSize(width: fit.width + 24, height: fit.height + 8)
    }
}
```

`applyTyped` receives the full props on create (`initial == true`) and
only the changed keys on update; `has_text` distinguishes a changed
property from one absent in a partial update, and fields are optional
so a reset arrives as `nil`. `props.values` holds the raw dictionary;
pass it to `PNViewStyler.applyCommon` so the shared view props
(background, border, opacity, transform, accessibility) apply.

## 4. The Kotlin manager

`native/android/com/example/badge/BadgeManager.kt`:

```kotlin
package com.example.badge

import android.content.Context
import android.graphics.drawable.GradientDrawable
import android.view.Gravity
import android.view.View
import android.widget.TextView
import com.pythonnative.generated.BadgeProps
import com.pythonnative.runtime.components.PNColor
import com.pythonnative.runtime.components.TypedComponentManager
import com.pythonnative.runtime.components.ViewStyler
import org.json.JSONObject

class BadgeManager : TypedComponentManager<BadgeProps>({ values, partial -> BadgeProps(values, partial) }) {
    override fun createView(context: Context, tag: Long, props: JSONObject): View =
        TextView(context).apply {
            gravity = Gravity.CENTER
            background = GradientDrawable().apply { cornerRadius = 12 * resources.displayMetrics.density }
        }

    override fun applyTyped(view: View, props: BadgeProps, initial: Boolean) {
        ViewStyler.apply(view, props.values)
        val badge = view as TextView
        if (initial || props.has_text) badge.text = props.text ?: ""
        if (initial || props.has_color) (badge.background as GradientDrawable).setColor(PNColor.parse(props.color ?: "#FF3B30"))
        if (initial || props.has_text_color) badge.setTextColor(PNColor.parse(props.text_color ?: "#FFFFFF"))
    }

    override fun measure(view: View, maxWidth: Double, maxHeight: Double): FloatArray {
        val base = super.measure(view, maxWidth, maxHeight)
        return floatArrayOf(base[0] + 24f, base[1] + 8f)
    }
}
```

Geometry on Android is in **dp** on both sides of the bridge; the base
class converts to pixels in `setFrame` and back in `measure`.

## 5. Register both in a plugin entry

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
  "name": "MyBadge",
  "contracts": "schema.json",
  "ios": {"entry": "MyBadgePlugin"},
  "android": {"entry": "com.example.badge.MyBadgePlugin"}
}
```

A plugin may declare only one platform; pass
`define_component(..., platforms=("ios",))` so
`Platform.supports("Badge")` answers truthfully, and gate its use with
`Platform.OS` or provide an application-level fallback elsewhere. Native
commits reject unregistered component types.

## 6. Tell `pn build` about the plugin

Point the `pythonnative.plugins` entry point at the directory holding
`pn_plugin.json`. If the app doesn't import your package itself, also
point the `pythonnative.handlers` entry point at the module that calls
`define_component`, so the schema is registered before the first commit
is validated:

```toml
[project.entry-points."pythonnative.plugins"]
my_badge = "my_badge.native"

[project.entry-points."pythonnative.handlers"]
my_badge = "my_badge"

[tool.setuptools.package-data]
"my_badge.native" = ["*.json", "ios/*.swift", "android/**/*.kt"]
```

`pn build` (and `pn run`) copies `ios/*.swift` into
`PythonNativeKit/Sources/PythonNativeKit/Plugins/my_badge/` and
`android/**/*.kt` into the `pythonnative` Gradle module, merges
`schema.json` into the compiled contract, then regenerates the
registration file that calls `MyBadgePlugin.register` on each platform.
SwiftPM and Gradle compile whatever lands there; no Xcode or Gradle
project edits are involved. Startup checks the contract fingerprint, so
rebuild the app after changing `BadgeProps` or the native sources.

For native code that lives inside an app rather than a package, list
the directory in `pythonnative.toml` instead of an entry point:

```toml
[plugins]
paths = ["native/badge"]
```

## 7. Use it

```python
import pythonnative as pn
from my_badge import Badge


@pn.component
def InboxRow():
    count, _ = pn.use_state(3)
    return pn.Row(
        pn.Text("Inbox"),
        Badge(text=str(count), color="#0A84FF", on_press=lambda: print("badge")),
        style={"spacing": 8, "align_items": "center"},
    )
```

## Events

Callable props never cross the bridge. When a `Badge(on_press=...)`
element is created, Python strips the callback into the process-wide
[`EventRegistry`][pythonnative.events.EventRegistry] and sends the prop
`_pn_events: ["on_press"]` instead. Declaring `on_press` in the props
dataclass generates a typed emitter, so the manager wires a listener
once and fires by tag with the declared payload:

```swift
// Swift: wire the recognizer in createView, after super so the view's state exists
override func createView(tag: Int64, props: [String: Any]) -> UIView {
    let view = super.createView(tag: tag, props: props)
    view.addGestureRecognizer(UITapGestureRecognizer(target: self, action: #selector(tapped(_:))))
    return view
}

@objc private func tapped(_ recognizer: UITapGestureRecognizer) {
    guard let view = recognizer.view else { return }
    PNComponentEvents.Badge.on_press(view)
}
```

For a `UIControl` subclass, `PNActionTarget.attach(control, events: .touchUpInside) { ... }`
does the same without a selector; the Inbox extension's badge button uses it.

```kotlin
// Kotlin: inside createView
view.setOnClickListener { PNComponentEvents.Badge.on_press(it) }
```

The payload is a positional argument list, so an emitter declared as
`Callable[[int], Any]` calls `on_press(count)` in Python. A re-render
that only swaps the lambda costs zero native calls.

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

Python reaches it through the [`ViewHandle`][pythonnative.ViewHandle]
the reconciler publishes on a `ref` after commit:

```python
@pn.component
def PulsingBadge():
    badge_ref = pn.use_ref()

    def pulse():
        if badge_ref.current is not None:
            badge_ref.current.command("pulse")

    return pn.Column(
        Badge(text="3", ref=badge_ref),
        pn.Button("Pulse", on_press=pulse),
    )
```

[`ViewHandle.command`][pythonnative.handles.ViewHandle.command] is the
generic entry point; the built-in handles (`TextInputHandle.focus()`,
`ScrollViewHandle.scroll_to()`) are thin typed wrappers over it. See
[Handles](../api/handles.md).

## Browser preview and tests

Neither the [browser preview](browser-preview.md) nor
`pythonnative.testing` loads Swift or Kotlin. In the preview, a
component with no browser implementation validates its props, takes
part in layout, and renders as a labeled placeholder box, so the
layout around it stays truthful while you work on everything else.

Off device, a defined component renders into the
[`FakeBackend`][pythonnative.testing.FakeBackend] like any built-in, so
unit tests need nothing beyond the definition:

```python
from pythonnative.testing import render
from my_badge import Badge


def test_badge_renders_text() -> None:
    result = render(Badge(text="3"))
    badge = result.get_by_type("Badge")
    assert badge.props["text"] == "3"


def test_badge_press() -> None:
    pressed = []
    result = render(Badge(text="3", on_press=lambda: pressed.append(True)))
    result.press(result.get_by_type("Badge"))
    assert pressed
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
| `define_component("Badge", NotADataclass)` | `TypeError`: `props` must be a `@dataclass` type. |

Defining the same name twice replaces the earlier schema, which is what
Fast Refresh relies on when you edit `BadgeProps`.

## Next steps

- Protocol details: [The native bridge](../concepts/bridge.md).
- Contract vocabulary and module adapters: [Generated native contracts](native-contracts.md).
- SDK reference: [`pythonnative.sdk`](../api/sdk.md).
- Wrap a device API instead of a widget: [Native modules](native-modules.md).
