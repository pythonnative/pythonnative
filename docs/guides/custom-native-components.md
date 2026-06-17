# Custom native components

PythonNative ships a public extension SDK,
[`pythonnative.sdk`](../api/sdk.md), that lets you wrap a real
platform widget (a `UIView` subclass on iOS, a `View` subclass on
Android) and expose it to user code as a first-class element with
type-checked props. Custom components participate in reconciliation,
flex layout, and Fast Refresh exactly like the built-ins.

This guide walks through the four-file shape of a typical component
(typed props, iOS handler, Android handler, registration) and shows
how to ship one as an installable PyPI plugin.

## Why an SDK?

Before the SDK, custom widgets were a monkey-patching exercise:
construct a `ViewHandler` subclass, reach into the global
[`NativeViewRegistry`][pythonnative.native_views.NativeViewRegistry],
and define your own ad-hoc element factory by hand. There was no
contract for prop validation, no entry point for third-party
plugins, and `mypy` couldn't help you.

The SDK fixes that:

- A frozen [`Props`][pythonnative.sdk._components.Props] dataclass
  declares every prop your component accepts, with types, defaults,
  and IDE autocomplete.
- A [`@native_component`][pythonnative.sdk._components.native_component]
  decorator registers your handlers under a unique element name.
- An [`element_factory`][pythonnative.sdk._components.element_factory]
  turns that registration into a callable users invoke like any
  other built-in.
- Discovery via the `pythonnative.handlers` entry-point group (see
  [`ENTRY_POINT_GROUP`][pythonnative.sdk._components.ENTRY_POINT_GROUP])
  lets your component appear automatically when users `pip install`
  your package.

## A worked example: `Badge`

We'll build a small widget that draws a coloured pill with a centred
label, useful for unread counts, status chips, etc. The same
project layout works for anything from a chart view to a camera
preview.

### 1. Define typed props

Create `my_pkg/badge_props.py`:

```python
from dataclasses import dataclass
from typing import Optional

import pythonnative as pn
from pythonnative.sdk import Props


@dataclass(frozen=True)
class BadgeProps(Props):
    """Visible state of a Badge.

    All fields default so callers can pass only the props they care
    about. ``style`` is the standard ``StyleProp`` accepted by every
    built-in factory.
    """

    text: str = ""
    color: str = "#FF3B30"
    text_color: str = "#FFFFFF"
    style: Optional[pn.StyleProp] = None
```

`Props` is a frozen dataclass; instances are immutable so equality
diffing in the reconciler stays cheap.

### 2. Implement the iOS handler

`my_pkg/badge_ios.py` runs only when `IS_IOS` is true. It uses
[rubicon-objc](https://rubicon-objc.readthedocs.io/) to wrap a
`UIView` containing a `UILabel`:

```python
from typing import Any, Dict

from rubicon.objc import ObjCClass

from pythonnative.sdk import ViewHandler, native_component
from .badge_props import BadgeProps

UIView = ObjCClass("UIView")
UILabel = ObjCClass("UILabel")
UIColor = ObjCClass("UIColor")


def _hex_to_uicolor(hex_str: str) -> Any:
    s = hex_str.lstrip("#")
    if len(s) == 6:
        a = 1.0
        r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    else:  # 8-char AARRGGBB
        a = int(s[0:2], 16) / 255.0
        r, g, b = int(s[2:4], 16), int(s[4:6], 16), int(s[6:8], 16)
    return UIColor.colorWithRed_green_blue_alpha_(r / 255, g / 255, b / 255, a)


@native_component("Badge", props=BadgeProps, platforms=("ios",))
class IOSBadgeHandler(ViewHandler):
    def create(self, tag: int, props: Dict[str, Any]) -> Any:
        view = UIView.alloc().init()
        view.layer.cornerRadius = 12
        label = UILabel.alloc().init()
        label.textAlignment = 1  # NSTextAlignmentCenter
        view.addSubview_(label)
        view._pn_label = label
        self.update(view, props)
        return view

    def update(self, view: Any, changed: Dict[str, Any]) -> None:
        if "color" in changed:
            view.backgroundColor = _hex_to_uicolor(changed["color"])
        if "text" in changed:
            view._pn_label.text = changed["text"]
        if "text_color" in changed:
            view._pn_label.textColor = _hex_to_uicolor(changed["text_color"])

    def set_frame(self, view: Any, x: float, y: float, w: float, h: float) -> None:
        view.frame = ((x, y), (w, h))
        view._pn_label.frame = ((0, 0), (w, h))

    def measure_intrinsic(self, view: Any, max_w: float, max_h: float) -> tuple[float, float]:
        size = view._pn_label.sizeThatFits_((max_w - 24, max_h))
        return (float(size.width) + 24.0, float(size.height) + 8.0)
```

### 3. Implement the Android handler

`my_pkg/badge_android.py` runs only when `IS_ANDROID` is true. It
uses [Chaquopy](https://chaquo.com/chaquopy/) to wrap a `TextView`
inside a `FrameLayout`:

```python
from typing import Any, Dict

from java import jclass

from pythonnative.sdk import ViewHandler, native_component
from pythonnative.utils import get_android_context
from .badge_props import BadgeProps

FrameLayout = jclass("android.widget.FrameLayout")
TextView = jclass("android.widget.TextView")
GradientDrawable = jclass("android.graphics.drawable.GradientDrawable")
Color = jclass("android.graphics.Color")
Gravity = jclass("android.view.Gravity")


@native_component("Badge", props=BadgeProps, platforms=("android",))
class AndroidBadgeHandler(ViewHandler):
    def create(self, tag: int, props: Dict[str, Any]) -> Any:
        ctx = get_android_context()
        container = FrameLayout(ctx)
        bg = GradientDrawable()
        bg.setShape(GradientDrawable.RECTANGLE)
        bg.setCornerRadius(24.0)
        container.setBackground(bg)
        label = TextView(ctx)
        label.setGravity(Gravity.CENTER)
        container.addView(label)
        container._pn_label = label
        container._pn_bg = bg
        self.update(container, props)
        return container

    def update(self, view: Any, changed: Dict[str, Any]) -> None:
        if "color" in changed:
            view._pn_bg.setColor(Color.parseColor(changed["color"]))
        if "text" in changed:
            view._pn_label.setText(changed["text"])
        if "text_color" in changed:
            view._pn_label.setTextColor(Color.parseColor(changed["text_color"]))
```

The `set_frame` and `measure_intrinsic` shapes are identical to the
built-in handlers; see
[Native views](../concepts/native-views.md) for the full protocol.

The `tag` argument is the view's stable identity in the mutation
protocol. Handlers that fire events use it to dispatch back into
Python: wire the platform listener once in `create` and call
[`dispatch_event(tag, "on_change", value)`][pythonnative.events.dispatch_event];
the reconciler keeps the `(tag, name) -> callback` registry up to date
across re-renders without any further native calls.

### 4. Wire it into your project

`my_pkg/__init__.py` imports the right module based on the active
runtime and exposes a typed factory:

```python
from pythonnative.sdk import element_factory
from pythonnative.utils import IS_ANDROID, IS_IOS

if IS_ANDROID:
    from . import badge_android  # noqa: F401  # registers AndroidBadgeHandler
elif IS_IOS:
    from . import badge_ios  # noqa: F401  # registers IOSBadgeHandler

Badge = element_factory("Badge")
```

Users now write:

```python
import pythonnative as pn
from my_pkg import Badge

@pn.component
def NotificationsButton():
    count, _ = pn.use_state(3)
    return pn.Row(
        pn.Text("Inbox"),
        Badge(text=str(count), color="#0A84FF"),
        style={"spacing": 8, "align_items": "center"},
    )
```

`Badge(...)` validates kwargs against `BadgeProps`, resolves the
`style` argument through [`resolve_style`][pythonnative.style.resolve_style],
and returns a regular [`Element`][pythonnative.Element].

## Validation rules

The factory enforces a strict contract on its arguments:

| Call site | Result |
|---|---|
| `Badge(text="3")` | Validated against `BadgeProps`. Unknown fields raise `TypeError`. |
| `Badge(props=BadgeProps(text="3"))` | Used directly. `style` is still resolved if present. |
| `Badge(props=..., text="3")` | `TypeError`: pass either `props` *or* keyword arguments. |
| `Badge(some_unknown_key=...)` | `TypeError("Invalid props for 'Badge': …")`. |

For `register_component` callers without a `Props` class, kwargs
flow straight to the `Element` and are not validated. We strongly
recommend defining a `Props` dataclass for every public component.

## Distributing as a plugin

To ship `Badge` as a PyPI package and have it auto-register on
install, declare an entry point in your project's `pyproject.toml`:

```toml
[project.entry-points."pythonnative.handlers"]
badge = "my_pkg:register"
```

The function pointed at by the entry point runs once on first call
to [`get_registry()`][pythonnative.native_views.get_registry]. A
common pattern is to import the platform-specific module from inside
that function so the heavy `rubicon-objc`/Chaquopy code path only
runs on the target device:

```python
def register() -> None:
    from pythonnative.utils import IS_ANDROID, IS_IOS
    if IS_ANDROID:
        from . import badge_android  # noqa: F401
    elif IS_IOS:
        from . import badge_ios  # noqa: F401
```

Plugins are loaded once per process, even if `get_registry()` is
called many times. Errors raised from a misbehaving plugin are
caught and logged but do not break PythonNative's startup.

## Imperative registration

If you don't want to use the decorator (e.g., for handlers that are
constructed lazily), call
[`register_component`][pythonnative.sdk._components.register_component]:

```python
from pythonnative.sdk import register_component

register_component(
    name="Badge",
    props=BadgeProps,
    handlers={"ios": IOSBadgeHandler(), "android": AndroidBadgeHandler()},
)
```

You can call this at any time before the first `Badge(...)` call.
Multiple calls merge by platform, so different files can register
the iOS and Android handlers separately.

## Testing custom components

The SDK is platform-agnostic: it does not import Chaquopy or
rubicon-objc, so you can unit-test your factory and registration
logic from pytest on a developer laptop. A typical pattern is to
swap in a stub handler that records calls:

```python
import pytest
from pythonnative.sdk import register_component, element_factory, ViewHandler
from pythonnative.native_views import NativeViewRegistry, set_registry
from my_pkg.badge_props import BadgeProps


class _StubHandler(ViewHandler):
    def create(self, tag, props): return {"props": dict(props)}
    def update(self, view, changed): view["props"].update(changed)


def test_badge_validates_props() -> None:
    register_component(name="Badge", props=BadgeProps, handlers={"ios": _StubHandler()})
    Badge = element_factory("Badge")

    with pytest.raises(TypeError):
        Badge(unknown_field=42)

    el = Badge(text="3", color="#000000")
    assert el.props["text"] == "3"
```

See `tests/test_sdk.py` in the PythonNative repo for a fuller
end-to-end example that runs the reconciler against a recording
backend.

## Next steps

- API reference: [`pythonnative.sdk`](../api/sdk.md).
- Native view protocol: [Native views](../concepts/native-views.md).
- Forward styles cleanly: [Styling](styling.md).
- Wrap a device API instead of a widget: [Native modules](native-modules.md).
