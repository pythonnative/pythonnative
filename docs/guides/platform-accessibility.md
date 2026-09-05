# Platform & Accessibility

## Platform

[`Platform`][pythonnative.Platform] is the canonical way to write
platform-aware code:

```python
import pythonnative as pn

font = pn.Platform.select(
    {"ios": "Helvetica", "android": "Roboto", "default": None}
)

if pn.Platform.is_ios:
    margin = 16
else:
    margin = 12
```

`Platform.select` looks up the current platform first, then `"native"`
(matches iOS *and* Android), then `"default"`, then the explicit
`default=` argument. `Platform.OS` is `"test"` when running off-device,
which is useful for skipping native-only code paths in tests.

## Window dimensions, safe area, keyboard

PythonNative ships three reactive hooks that subscribe to the
platform-published metrics in `pythonnative.platform_metrics`:

```python
@pn.component
def Responsive():
    dims = pn.use_window_dimensions()
    insets = pn.use_safe_area_insets()
    keyboard = pn.use_keyboard_height()

    return pn.Column(
        pn.Text(f"{dims.width:.0f} × {dims.height:.0f}"),
        pn.Text(f"Bottom inset: {insets.bottom:.0f}"),
        pn.Text(f"Keyboard: {keyboard:.0f}"),
        style={"padding": 16, "spacing": 8},
    )
```

The component re-renders whenever the underlying value actually
changes (no spurious renders on no-op updates). For most apps,
[`KeyboardAvoidingView`][pythonnative.KeyboardAvoidingView] handles
the keyboard case for you and you won't need
[`use_keyboard_height`][pythonnative.use_keyboard_height] directly.

## Status bar

Mount [`StatusBar`][pythonnative.StatusBar] anywhere in the tree (it
renders nothing visible) to control style and visibility:

```python
pn.StatusBar(bar_style="light", background_color="#000000")
```

`style` is `"light"` (light icons, dark background), `"dark"` (dark
icons, light background), or `"default"`.

## Alerts and pickers

[`Alert.show`][pythonnative.alerts.Alert.show] is the imperative way
to present a dialog.
[`Alert.confirm`][pythonnative.alerts.Alert.confirm] wraps the common
confirm/cancel case. The [`Picker`][pythonnative.Picker] component is
implemented on top of `Alert.show(style="action_sheet")`.

## Accessibility props

Every interactive component (`Text`, `Button`, `Pressable`,
`TextInput`, `Image`, container views) accepts the same set of
accessibility kwargs:

| Prop | Purpose |
|---|---|
| `accessibility_label` | Short spoken description for screen readers |
| `accessibility_hint` | Extra detail (iOS only) |
| `accessibility_role` | Semantic role (`"button"`, `"link"`, `"image"`, ...) |
| `accessible` | Override whether the element is exposed to assistive tech |
| `accessibility_state` | Dict of state flags announced with the element |
| `accessibility_live_region` | Announce content changes: `"polite"` or `"assertive"` |
| `test_id` | Stable identifier for UI test frameworks |

Components like [`Button`][pythonnative.Button] supply a sensible
default `accessibility_role` for you.

### State flags

`accessibility_state` mirrors React Native's prop of the same name.
Supported keys are `disabled`, `selected`, `checked`, `busy`, and
`expanded`; they map to `UIAccessibilityTraits` on iOS and to
`AccessibilityNodeInfo` state on Android:

```python
pn.Pressable(
    pn.Text("Inbox"),
    on_press=select_inbox,
    accessibility_role="button",
    accessibility_state={"selected": current_tab == "inbox"},
)
```

### Live regions

Set `accessibility_live_region="polite"` on a status line so screen
readers announce its text when it changes without moving focus (use
`"assertive"` only for content the user must hear immediately):

```python
pn.Text(f"{unread} unread messages", accessibility_live_region="polite")
```

### Test identifiers

`test_id` gives UI-test frameworks (Maestro, Appium, XCUITest,
Espresso) a stable handle that is independent of visible text. It
maps to `accessibilityIdentifier` on iOS and to the accessibility
node's `viewIdResourceName` (resource-id) on Android:

```python
pn.Button("Continue", on_press=next_step, test_id="onboarding-continue")
```
