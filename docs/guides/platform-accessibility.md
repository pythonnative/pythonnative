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

PythonNative ships reactive hooks that subscribe to the
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
changes (no spurious renders on no-op updates). `dims` is a
[`WindowDimensions`][pythonnative.WindowDimensions] with `width`,
`height`, `scale`, and `font_scale`. For most apps,
[`KeyboardAvoidingView`][pythonnative.KeyboardAvoidingView] handles
the keyboard case for you and you won't need
[`use_keyboard_height`][pythonnative.use_keyboard_height] directly.

Outside a component, the same values are available imperatively from
the [`Dimensions`][pythonnative.Dimensions],
[`PixelRatio`][pythonnative.PixelRatio], and
[`Keyboard`][pythonnative.Keyboard] modules (`Dimensions.get("screen")`,
`PixelRatio.round_to_nearest_pixel(0.5)`, `Keyboard.dismiss()`); see the
[Native modules guide](native-modules.md#keyboard-dimensions-and-pixel-ratio).

## Status bar

Mount [`StatusBar`][pythonnative.StatusBar] anywhere in the tree (it
renders nothing visible) to control style and visibility:

```python
pn.StatusBar(bar_style="light", background_color="#000000", translucent=True, animated=True)
```

`bar_style` is `"light"` (light icons, dark background), `"dark"` (dark
icons, light background), or `"default"`. `background_color` and
`translucent` (draw your content under the bar) apply on Android only;
iOS always draws underneath. `animated` animates `bar_style` and
`hidden` changes on iOS only.

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
| `accessibility_hint` | Extra detail. iOS reads it after the label; Android appends it to the content description, as React Native does |
| `accessibility_role` | Semantic role (`"button"`, `"link"`, `"image"`, ...) |
| `accessible` | Override whether the element is exposed to assistive tech |
| `accessibility_state` | Dict of state flags announced with the element |
| `accessibility_value` | The widget's current value: a string, or an [`AccessibilityValue`][pythonnative.AccessibilityValue] with `min` / `max` / `now` / `text` |
| `accessibility_actions` | Custom actions a screen reader may invoke, each an [`AccessibilityAction`][pythonnative.AccessibilityAction] |
| `on_accessibility_action` | Callback receiving the invoked action's `name` |
| `accessibility_live_region` | Announce content changes: `"none"`, `"polite"`, or `"assertive"` (`aria-live` in the browser) |
| `important_for_accessibility` | Whether assistive tech sees this view and its subtree: `"auto"`, `"yes"`, `"no"`, or `"no_hide_descendants"` |
| `test_id` | Stable identifier for UI test frameworks |

Components like [`Button`][pythonnative.Button] supply a sensible
default `accessibility_role` for you, and `Pressable(disabled=True)`
sets the disabled state unless you pass `accessibility_state`
explicitly.

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

### Values and actions

`accessibility_value` describes range-like widgets (`min`, `max`,
`now`) or gives a spoken value for anything else (`text`; a plain
string is shorthand for `{"text": ...}`). `accessibility_actions`
lists actions a screen reader can invoke without a visible control;
the standard names `"activate"`, `"increment"`, `"decrement"`,
`"longpress"`, `"magicTap"`, and `"escape"` map to the platform's
built-in actions, and any other name is announced with its `label`:

```python
pn.View(
    Slider(...),
    accessibility_role="adjustable",
    accessibility_value={"min": 0, "max": 100, "now": volume},
    accessibility_actions=[
        {"name": "increment"},
        {"name": "decrement"},
        {"name": "mute", "label": "Mute"},
    ],
    on_accessibility_action=lambda name: adjust(name),
)
```

`important_for_accessibility="no_hide_descendants"` hides decorative
subtrees from the accessibility tree.

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

## Accessibility settings: `AccessibilityInfo`

[`AccessibilityInfo`][pythonnative.AccessibilityInfo] mirrors React
Native's module of the same name over `UIAccessibility` on iOS and
`AccessibilityManager` on Android. The two readers answer from state
the OS already holds, so they are synchronous; `announce` and
`set_accessibility_focus` hand a request to the OS and return at once:

```python
pn.AccessibilityInfo.is_screen_reader_enabled()   # VoiceOver or TalkBack running
pn.AccessibilityInfo.is_reduce_motion_enabled()   # the system Reduce Motion setting
pn.AccessibilityInfo.announce("Message sent")     # a no-op when no screen reader runs
pn.AccessibilityInfo.set_accessibility_focus(heading_ref)
unsubscribe = pn.AccessibilityInfo.add_listener(lambda e: print(e.screen_reader, e.reduce_motion))
```

The listener receives an [`AccessibilityEvent`][pythonnative.AccessibilityEvent]
whenever either setting flips. Inside components, prefer the reactive
hooks [`use_screen_reader_enabled`][pythonnative.use_screen_reader_enabled]
and [`use_reduce_motion`][pythonnative.use_reduce_motion], which
re-render when the setting changes:

```python
@pn.component
def Toast(message: str):
    reduce_motion = pn.use_reduce_motion()
    pn.use_effect(lambda: pn.AccessibilityInfo.announce(message), [message])
    return pn.Text(
        message,
        style=pn.style(opacity=1 if reduce_motion else 0.9),
        accessibility_live_region="polite",
    )


@pn.component
def Chart(points):
    if pn.use_screen_reader_enabled():
        return DataTable(points=points)   # a readable alternative to the drawing
    return pn.Svg(...)
```

Text respects the user's text-size setting by default (iOS Dynamic
Type, Android `sp`); pass `allow_font_scaling=False` on a `Text` that
must keep its exact size, and read the multiplier with
[`PixelRatio.get_font_scale`][pythonnative.native_modules.dimensions.PixelRatio.get_font_scale].

## Localization

[`Localization`][pythonnative.Localization] reads the user's preferred
languages and time zone; the [`use_locales`][pythonnative.use_locales]
hook re-renders when they change. Each [`Locale`][pythonnative.Locale]
carries `language_tag`, `language_code`, `region_code`, and `is_rtl`:

```python
@pn.component
def Greeting():
    locale = pn.use_locales()[0]
    text = "Hola" if locale.language_code == "es" else "Hello"
    return pn.Text(text, style=pn.style(text_align="right" if locale.is_rtl else "left"))
```

`Localization.get_timezone()` returns the IANA name
(`"America/New_York"`) and `Localization.is_rtl()` answers for the
preferred locale. The layout engine's `direction: "rtl"` style flips
rows and resolves `margin_start` / `padding_end`; see
[Styling](styling.md).
