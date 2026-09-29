# RFC 0002: Core parity and correctness

- Status: Implemented
- Author(s): Owen Carey, with Claude (Claude Code)
- Created: 2026-09-17
- Implemented in: this pull request
- Supersedes / Superseded by: list transport and Python sticky headers replaced by [RFC 0003](0003-incremental-rendering-and-lists.md); other decisions remain implemented

## Summary

PythonNative has every system React Native has: components and hooks, a
reconciler, native widgets, navigation, gestures, animation, device
modules, a dev loop, and a build pipeline. What it doesn't have yet is the
second layer inside each system that a real application reaches for on its
first screen, and several first-layer behaviors are wrong in ways an app
can't work around. This RFC is the release where a developer who knows
React Native can port a real app without hitting a wall.

It fixes the correctness bugs found in the runtime, navigation, and
animation layers; completes the React Native core component, prop, style,
and accessibility surface on iOS, Android, and the browser preview; adds
typed imperative handles; adds the device APIs that React Native core
ships (`Keyboard`, `Dimensions`, `PixelRatio`, `Device`, `Localization`,
`AccessibilityInfo`); brings navigation up to React Navigation's common
options with a theme, navigator-level screen options, groups, and a
navigation ref; tightens the Python typing so editors catch mistakes; and
finishes the testing library so all of it can be tested with pytest. It
removes the legacy Python view-handler layer, the dead `requests`
dependency, and every prop or convention that these changes replace.

## Motivation

A repository-wide audit (September 2026, v0.45.0) compared each subsystem
with React Native, React Navigation, Reanimated, Gesture Handler, and the
Expo SDK. The gaps fall into three groups.

### Things that are wrong

- An exception raised in a `use_effect` callback bypasses
  `ErrorBoundary` and escapes the render pass. If any operation was
  already flushed, the reconciler retires the whole native surface and
  the app shows a blank screen (`reconciler/core.py`, `_commit` and
  `_pass`). React routes effect errors to the nearest boundary.
- When a newly mounted descendant suspends during an update, `Suspense`
  destroys the boundary's committed content, so a sibling `TextInput`
  loses focus and text. React hides the siblings and keeps them mounted.
- `async def` components always show their fallback for one loop turn,
  even when every await is already resolved, and the async guide claims
  the opposite.
- Without a native host, two setter calls in one handler produce two full
  renders; the hooks guide documents this as intended.
- On iOS, a `before_remove` veto after a swipe-back leaves UIKit popped
  while Python still holds the route. `before_remove` also never fires for
  `navigate` to an existing route, `replace`, or `reset`. The canonical
  "unsaved changes" guard can't be built.
- On iOS, animating one transform channel replaces the whole
  `view.transform`, so the documented drag example binding `translate_x`
  and `translate_y` fights itself.
- `Animated.decay` uses a rate of `0.997` per millisecond with an
  exponential time constant of about one millisecond. Flings travel about
  three hundred times shorter than in React Native and than in the
  browser preview, which uses the correct model.
- Android `Camera.take_photo` returns the thumbnail from
  `ACTION_IMAGE_CAPTURE`, Android `Location.get_current` never prompts
  for permission, Android `SecureStore.set_item` swallows failure, and
  `use_keyboard_height` never updates on iOS.
- The `Pressable` factory has no `disabled` argument though all three
  renderers implement it. `ScrollView(content_container_style=...)` is
  accepted and consumed by nothing. Modal's `on_request_close` is read
  natively but can't be passed from Python. Android ignores light/dark
  color dictionaries that iOS and the browser accept.

### Things that are missing

- Imperative handles. The docs tell users to reach into a private
  `_pn_tag` attribute to focus a text input.
- Text truncation mode, selectable text, pressable spans; controlled
  selection, key events, keyboard appearance, and content-size events on
  `TextInput`; drag and momentum events, content insets, snapping, and
  keyboard dismissal behavior on `ScrollView`; load lifecycle and fade on
  `Image`; sticky section headers, inverted lists, separators, and an
  initial scroll index on lists.
- Accessibility beyond label, role, hint, and state: no value, actions,
  importance, announcements, or screen-reader and reduce-motion queries.
- Navigator-level screen options, screen groups, a navigation ref usable
  outside components, `pop_to`, theming and dark mode for Python-drawn
  navigation chrome, tab-bar styling, per-screen tab-bar hiding, and
  Android transitions other than a fade.
- `Keyboard`, `Dimensions`, `PixelRatio`, `Device`, `Localization`, and
  `AccessibilityInfo` modules.
- Testing queries by role, placeholder, and display value; `wait_for`;
  scoped queries; a controllable clock; and a shipped pytest plugin.

### Things that are un-Pythonic or untyped

- `pn.style(**properties: Any)` accepts typos silently at type-check
  time, though `Style` itself is a fully typed `TypedDict`.
- `use_effect(deps: list)` rejects tuples; `use_reducer` loses the
  action type; `use_ref(0).current` is `int | None`; `key=` at a
  component call site is a type error unless the function declares it.
- `Context.Provider(value, *children)` puts the value before the children
  while every other container is `Container(*children, **props)`.
- `on_layout` and `on_scroll` deliver untyped dicts while `Image` and
  `WebView` events are dataclasses.
- Easing is a free-form string that silently falls back to
  `ease_in_out` when misspelled.

## Reference behavior

React Native's core components define the vocabulary developers expect:
`Pressable` with `disabled`, `delayLongPress`, `android_ripple`, and a
pressed-state render function; `ScrollView` with `contentContainerStyle`,
`contentInset`, `scrollEventThrottle`, drag and momentum events,
`keyboardShouldPersistTaps`, `snapToInterval`; `Text` with
`numberOfLines`, `ellipsizeMode`, `selectable`, nested pressable spans;
`TextInput` with `selection`, `onKeyPress`, `selectTextOnFocus`,
`blurOnSubmit`, `keyboardAppearance`, `onContentSizeChange`, and
`focus()`/`blur()`/`clear()` on the ref; `FlatList` with `inverted`,
`ItemSeparatorComponent`, `initialScrollIndex`; `SectionList` with
`stickySectionHeadersEnabled`; `Modal` with `onRequestClose`. Its APIs
include `Keyboard`, `Dimensions`, `PixelRatio`, `AccessibilityInfo`,
`I18nManager`, and `Platform.constants`. React Navigation adds
`screenOptions` on navigators, `Group`, `createNavigationContainerRef`,
`popTo`, `beforeRemove` on every removal, themes, and tab-bar options.
Reanimated and RN Animated define `Easing` and the decay model
`v(t) = v0 * deceleration^t`.

PythonNative follows the same shape with a Python accent:

- Props are keyword arguments on typed factory functions, so the
  contract generator and the type checker see the same signature. Events
  deliver frozen dataclasses (`LayoutEvent`, `ScrollEvent`,
  `KeyPressEvent`), not dicts.
- Imperative handles are ordinary objects on `ref.current` with methods,
  not string commands. Methods that need a native answer are `async`.
- Options that React Native spells as dictionaries of camelCase keys are
  `TypedDict`s or frozen dataclasses (`ScreenOptions`, `TabBarStyle`,
  `NavigationTheme`, `Ripple`).
- Enumerations stay `Literal` strings at call sites, because that's how
  a Python developer reads `align_items="center"`, but the runtime
  rejects unknown values with a `ValueError` instead of guessing.
- Where React Native ships a feature only on one platform, PythonNative
  documents the platform note on the argument and ignores it elsewhere;
  it doesn't invent behavior.

## Design

### Runtime correctness

**Effect errors.** `Reconciler._commit` wraps each layout and passive
effect flush in a per-component error path that calls `_route_error` with
the owning component's vnode, exactly as render-time errors do. A
component with no boundary above it reports through `diagnostics` and
unmounts its root, the same as today's render errors. Post-commit Python
errors never mark the surface failed; `_pass` only retires the surface
when the backend itself rejected a commit.

**Suspense on update.** When a boundary that already has committed content
suspends because a new descendant suspended, the boundary keeps its
content vnodes mounted, applies `display: "none"` to the content's native
roots through an ordinary `UpdateOp`, and inserts the fallback. When the
pending resource settles, the fallback is removed and the `display`
override is lifted. Hook state, native views, focus, and scroll position
survive. The existing path where the suspending component is the dirty
component itself is unchanged.

**Async components.** The reconciler drives an `async def` body eagerly:
it steps the coroutine once synchronously, and only if the first `await`
is actually pending does it schedule a task and suspend. Bodies whose
awaits are already resolved render inline with no fallback flash, as
`docs/guides/async.md` already promises.

**Automatic batching.** `Reconciler.request_render` never renders inline.
It schedules one flush on the application loop with `call_soon`, so every
setter call within one callback, effect, or task step coalesces into one
render pass on every host, including headless tests. `batch_updates()`
stays as an explicit way to coalesce across awaits.

**One render-storm policy.** The three inconsistent guards (raise at 25,
warn and drop at 100, silent stop at 25) collapse into one: a flush that
schedules itself more than fifty times without settling raises
`RuntimeError("Too many re-renders")` from the component that keeps
dirtying itself, which then routes through the nearest `ErrorBoundary`
and the RedBox like any other render error.

**Dev warnings.** In dev mode the reconciler warns once per site for: a
dynamic list of unkeyed sibling elements; a state setter called after the
component unmounted; a setter called during the component's own render;
a setter receiving the identical `list`, `dict`, or `set` object it
already holds (in-place mutation never re-renders); and a dependency list
whose length changed between renders.

### Typing

```python
Deps = Sequence[object] | None
def use_effect(effect: Callable[[], Any], deps: Deps = None) -> None: ...
def use_reducer(reducer: Callable[[S, A], S], initial: S | Callable[[], S]) -> tuple[S, Callable[[A], None]]: ...
@overload
def use_ref() -> Ref[T | None]: ...
@overload
def use_ref(initial: T) -> Ref[T]: ...
def use_color_scheme() -> ColorScheme: ...        # Literal["light", "dark"]
def style(**props: Unpack[Style]) -> Style: ...
```

- `Component.keyed(key)` returns a typed callable with the component's
  own signature whose result carries `key`, so
  `[Row.keyed(item.id)(item) for item in items]` type-checks. The
  "declare `key` in your signature" guidance is removed.
- `Color = Union[str, DynamicColor]` where
  `DynamicColor = TypedDict("DynamicColor", {"light": str, "dark": str})`.
  Every renderer resolves the dictionary against the current color scheme.
- `Context.Provider(*children, value=...)`. `value` is keyword-only.
- New frozen dataclasses in `pythonnative.components.events`, exported
  from `pythonnative`: `LayoutEvent(x, y,
  width, height)`, `ScrollEvent(x, y, content_width, content_height,
  viewport_width, viewport_height)`, `SelectionEvent(start, end)`,
  `KeyPressEvent(key)`, `ContentSizeEvent(width, height)`. `on_layout`,
  `on_scroll`, `on_selection_change`, `on_key_press`, and
  `on_content_size_change` deliver them. `Animated.event(on_scroll,
  y=scroll_y)` keeps binding by field name.

### Components

Every argument below is a keyword argument on the factory, which makes it
part of the generated contract for iOS, Android, and the browser. Platform
notes are recorded in the argument's docstring.

**All views** gain `accessibility_value: str | AccessibilityValue`
(`AccessibilityValue` is a `TypedDict` with `min`, `max`, `now`, `text`),
`accessibility_actions: Sequence[AccessibilityAction]` (`TypedDict` with
`name` and optional `label`), `on_accessibility_action:
Callable[[str], Any]`, and `important_for_accessibility:
Literal["auto", "yes", "no", "no_hide_descendants"]`. Android maps
`accessibility_hint` by appending it to the content description, as React
Native does, instead of setting a tooltip. The browser implements
`accessibility_live_region` with `aria-live`.

**Pressable**

```python
pn.Pressable(
    lambda state: pn.Text("Pressed" if state.pressed else "Press me"),
    on_press=save,
    disabled=not valid,
    delay_long_press=400,
    android_ripple=pn.Ripple(color="#33000000", borderless=False),
    style=lambda state: pn.style(opacity=0.5 if state.pressed else 1),
)
```

`PressState` is a frozen dataclass with `pressed: bool`. A single callable
positional child receives it. `Ripple(color, borderless=False,
radius=None, foreground=False)` is a frozen dataclass; it's ignored on iOS
and the browser. `disabled=True` suppresses every press callback and sets
the accessibility disabled state. `TouchableOpacity` stays as a thin
wrapper over `Pressable`.

**ScrollView**

```python
pn.ScrollView(
    *rows,
    horizontal=False,
    content_container_style=pn.style(padding=16, gap=12),
    content_inset=pn.EdgeInsets(bottom=80),
    scroll_enabled=True,
    scroll_event_throttle=16,
    on_scroll=lambda e: ...,                 # ScrollEvent
    on_scroll_begin_drag=..., on_scroll_end_drag=..., on_momentum_scroll_end=...,
    keyboard_should_persist_taps="handled",  # "never" | "always" | "handled"
    keyboard_dismiss_mode="on_drag",
    snap_to_interval=300, snap_to_alignment="start",
    deceleration_rate="fast",                # or a float
    ref=scroll_ref,
)
```

`horizontal: bool` replaces `scroll_axis`, and a horizontal ScrollView
lays its content out in a row, as in React Native. `content_container_style`
is applied by wrapping the children in one inner `View` in Python, so the
padding, gap, and alignment keys work on every renderer without native
changes. `scroll_event_throttle` is milliseconds; native emits `on_scroll`
only when the app wired it.

**Text**

```python
pn.Text(
    "Read the ", pn.Text("terms", on_press=open_terms, style=pn.style(color="#06F")), ".",
    max_lines=2, ellipsize_mode="tail", selectable=True, allow_font_scaling=True,
)
```

`ellipsize_mode: Literal["head", "middle", "tail", "clip"]`,
`selectable: bool`, `allow_font_scaling: bool` (iOS Dynamic Type and
Android `sp` opt-out), and `on_press` on the label or on any nested span.
Spans carry a `pressable` flag on the wire; native reports
`on_span_press(index)` and Python routes it to the span's callback.

**TextInput**

```python
pn.TextInput(
    value=text, on_change=set_text,
    selection=(start, end), on_selection_change=lambda e: ...,   # SelectionEvent
    on_key_press=lambda e: ...,                                  # KeyPressEvent
    select_text_on_focus=True, blur_on_submit=None,               # None = not multiline
    keyboard_appearance="dark", on_content_size_change=lambda e: ...,
    keyboard_type="numbers_and_punctuation",
    ref=input_ref,
)
```

`KeyboardType` gains `"ascii"`, `"numbers_and_punctuation"`,
`"web_search"`, and `"visible_password"`. `on_key_press` reports the
typed character or `"Backspace"`/`"Enter"`; native platforms report only
what their input pipeline exposes, which the docstring states.

**Image** gains `on_load_start`, `on_load_end`, `fade_duration`
(milliseconds; iOS skips the fade under Reduce Motion), and
`headers: Mapping[str, str]` for network sources (ignored by the browser
preview, which can't attach headers to an image request).

**Modal** gains `on_request_close: Callable[[], Any]` (Android back
button, iOS sheet pull-down, a tap on an overlay's backdrop; when unset
the modal stays open) and `status_bar_translucent: bool` (Android).
`on_dismiss` fires once the modal has closed after `visible` became
`False`, on every renderer.

**StatusBar** gains `translucent: bool` (Android) and `animated: bool`
(iOS).

**Lists.** `FlatList` gains `inverted: bool`, `item_separator:
Callable[[], Element] | Element | None`, and `initial_scroll_index:
int | None`. `SectionList` gains `sticky_section_headers: bool`,
`inverted`, `item_separator`, and `on_viewable_items_changed`. All are
implemented in Python on top of the existing `VirtualList` contract:
`inverted` applies a `scale_y: -1` transform (`scale_x` for a horizontal
list) to the container and each row, separators are appended to each row except the last, the initial
index is scrolled to through the existing `scroll_to_index` command after
mount, and sticky headers render the current section's header in an
absolutely positioned overlay derived from the viewable-items event.

**Imperative handles.** When a `Ref` is passed to a built-in element, the
reconciler publishes a typed handle on `ref.current` chosen by element
type, and `None` after unmount:

| Element | `ref.current` |
| --- | --- |
| `TextInput` | `TextInputHandle`: `focus()`, `blur()`, `clear()`, `select_all()`, `set_selection(start, end=None)`, `async get_value() -> str` |
| `ScrollView` | `ScrollViewHandle`: `scroll_to(x=None, y=None, animated=True)`, `scroll_to_end(animated=True)`, `flash_scroll_indicators()`, `async get_scroll_offset() -> ScrollOffset` |
| `FlatList`, `SectionList` | `ListController` (unchanged) |
| `WebView` | `WebViewHandle`: `reload()`, `go_back()`, `go_forward()`, `stop_loading()`, `load_url(url)`, `inject_javascript(script)`, `async eval_js(script) -> str` (through the `WebViews` module), `async can_go_back() -> bool`, `async can_go_forward() -> bool`, `async get_url() -> str` |
| everything else | `ViewHandle`: `frame` property, `tag` |

Every handle exposes `frame: LayoutEvent | None` (the last committed
frame) and `tag: int`. The private `_pn_tag` and `_pn_frame` attributes
on `Ref` are removed.

### Style

- `border_style: Literal["solid", "dashed", "dotted"]` on all three
  renderers.
- `inset: Dimension` (all four edges), `inset_horizontal`, and
  `inset_vertical` shorthands, matching the padding vocabulary.
- Transform operations `rotate`, `rotate_x`, `rotate_y`, `rotate_z`,
  `scale`, `scale_x`, `scale_y`, `translate_x`, `translate_y`, `skew_x`,
  `skew_y`, and `perspective` are supported on every renderer (Android
  skew needs API 29). iOS switches from `CGAffineTransform` to
  `CATransform3D` to do so.
- Shadows follow React Native's platform split and say so: `shadow_*`
  keys are iOS and browser, `elevation` is Android. The `Style` reference
  and the styling guide document the split.
- Android resolves `DynamicColor` dictionaries.
- `pn.style()` is typed with `Unpack[Style]`, so `pn.style(colour="red")`
  is a type error. `StyleProp` drops `Dict[str, Any]`; a plain dict still
  works at runtime because `Style` is a `TypedDict`.

### Accessibility, keyboard, dimensions, device, localization

New modules, each declared as a protocol in `sdk/services.py`, generated
into Swift and Kotlin adapters, implemented on both platforms and in the
browser host where the browser can, with a Python fallback for headless
tests. Return values are frozen dataclasses. Readers of OS state are
synchronous; anything that shows UI or waits on the OS is `async`.

```python
pn.AccessibilityInfo.is_screen_reader_enabled() -> bool
pn.AccessibilityInfo.is_reduce_motion_enabled() -> bool
pn.AccessibilityInfo.announce(message: str) -> None
pn.AccessibilityInfo.set_accessibility_focus(ref: Ref) -> None
pn.AccessibilityInfo.add_listener(callback) -> unsubscribe     # AccessibilityEvent(screen_reader, reduce_motion)
pn.use_screen_reader_enabled() -> bool
pn.use_reduce_motion() -> bool

pn.Keyboard.dismiss() -> None
pn.Keyboard.is_visible() -> bool
pn.Keyboard.add_listener(callback) -> unsubscribe              # KeyboardEvent(height, visible, duration_ms)

pn.Dimensions.get(which: Literal["window", "screen"] = "window") -> WindowDimensions
pn.Dimensions.add_listener(callback) -> unsubscribe
pn.PixelRatio.get() -> float
pn.PixelRatio.get_font_scale() -> float
pn.PixelRatio.get_pixel_size_for_layout_size(size: float) -> int
pn.PixelRatio.round_to_nearest_pixel(size: float) -> float

pn.Device.info() -> DeviceInfo
pn.Localization.get_locales() -> list[Locale]
pn.Localization.get_timezone() -> str
pn.Localization.is_rtl() -> bool
pn.use_locales() -> list[Locale]
```

`WindowDimensions` gains `scale` and `font_scale`; the native viewport
payload carries `scale`, `font_scale`, `screen_width`, and
`screen_height`, and the `Keyboard` module emits `change` on both
platforms so `use_keyboard_height` works on iOS. `DeviceInfo` has
`platform`, `os_version`, `model`, `manufacturer`, `is_simulator`,
`is_tablet`, `app_name`, `app_version`, `build_number`, `bundle_id`,
`scale`, `font_scale`, and `locale`; the native `Device.info` returns
every key on both platforms and the Python-only keys in the fallback are
dropped. `Locale` has `language_tag`, `language_code`, `region_code`, and
`is_rtl`.

Battery and NetInfo declare their `change` events in their schemas so the
generated emitters and `decode_event` validation cover them.

### Navigation

```python
Stack = pn.create_stack_navigator()
nav_ref = pn.create_navigation_ref()

@pn.component
def App():
    return pn.NavigationContainer(
        Stack.Navigator(
            Stack.Screen("Home", HomeScreen),
            Stack.Group(
                Stack.Screen("Compose", ComposeScreen),
                Stack.Screen("Preview", PreviewScreen),
                screen_options={"presentation": "modal"},
            ),
            screen_options=lambda route: {"title": route.name.title()},
        ),
        ref=nav_ref,
        theme=pn.DARK_NAVIGATION_THEME if scheme == "dark" else pn.DEFAULT_NAVIGATION_THEME,
    )

def on_push_notification(payload):
    if nav_ref.is_ready():
        nav_ref.navigate("Thread", id=payload["thread"])
```

- `Navigator(*screens_or_groups, screen_options=None, initial_route=None,
  key=None)` on stack, tab, and drawer navigators. `screen_options` is a
  `ScreenOptions` or a callable `(route) -> ScreenOptions`. Resolution
  order is navigator, group, screen, then `set_options`.
- `Group(*screens, screen_options=None)` on every navigator.
- `create_navigation_ref() -> NavigationRef` with `current`,
  `is_ready()`, and the `Navigation` methods `navigate`, `go_back`,
  `push`, `pop`, `pop_to`, `pop_to_top`, `replace`, `reset`, and
  `get_state`, which raise `RuntimeError` when no container is mounted.
- `Navigation.pop_to(name, **params)`.
- `before_remove` fires for every route removal: `pop`, `pop_to`,
  `navigate` to an existing route, `replace`, and `reset`. A vetoed native
  back on iOS re-synchronizes UIKit with Python by issuing the existing
  `restore_stack` command whenever the Python state didn't change, and by
  answering `navigationBar(_:shouldPop:)` and
  `presentationControllerShouldDismiss` from a `guarded` wire prop that
  Python sets while the route has a `before_remove` listener, so a guarded
  screen doesn't animate out and back in.
- `NavigationTheme` is a frozen dataclass with `dark: bool` and a
  `NavigationColors(primary, background, card, text, border,
  notification)` record. `DEFAULT_NAVIGATION_THEME` and
  `DARK_NAVIGATION_THEME` are provided, `NavigationContainer(theme=)`
  accepts one, and `use_navigation_theme()` reads it. Python-drawn
  headers, drawer panels, and fallbacks use it, and it supplies the
  default header tint, header background, and tab bar colors sent to the
  native containers.
- `Tab.Navigator(tab_bar_style=TabBarStyle)` where `TabBarStyle` is a
  `TypedDict` with `background_color`, `active_tint_color`,
  `inactive_tint_color`, `translucent`, and `show_labels`, forwarded to
  the native `TabBar` props that already exist. `ScreenOptions` gains
  `tab_bar_visible: bool` and `freeze_on_blur: bool` (an unfocused tab's
  subtree isn't re-rendered until it regains focus).
- `ScreenOptions.presentation` becomes `Literal["card", "modal",
  "full_screen_modal", "form_sheet", "transparent_modal"]`, and
  `animation` (`default`, `none`, `fade`, `slide_from_right`,
  `slide_from_bottom`) is honored on iOS and Android. iOS maps
  presentations to `pageSheet`, `fullScreen`, `formSheet`, and
  `overFullScreen`; Android presents every modal style as a full-screen
  screen with a slide-from-bottom transition, which is what React
  Navigation's native stack does there.
- Android gains slide transitions for pushes and pops, a proper back
  arrow, an inset-aware toolbar, `header_large_title` rendered as an
  expanded toolbar with a larger title, and predictive back enabled in
  the manifest. `header_back_title` and `gesture_enabled` are documented
  as iOS-only.
- The `Screen`, `ScreenStack`, and `TabBar` native props gain the
  corresponding fields. The browser preview's host header and its native
  stacks read the same option names as the native hosts.

### Animation and gestures

- `Animated.decay` adopts React Native's model on every platform:
  velocity in points per millisecond decays as `v0 * deceleration^t`
  with `deceleration` defaulting to `0.998`, and the projected final
  value is `v0 / (1 - deceleration)`. The Python ticker and the Swift,
  Kotlin, and browser decay drivers evaluate the same closed form, and
  each has a test for it.
- The iOS animator keeps per-view animated transform channels and
  composes them with the static `transform` prop before assigning
  `layer.transform`, so binding `translate_x` and `translate_y`
  together works.
- `pn.Easing` is a namespace of serializable easing descriptors:
  `Easing.linear`, `Easing.ease`, `Easing.ease_in`, `Easing.ease_out`,
  `Easing.ease_in_out`, `Easing.quad`, `Easing.cubic`, `Easing.bounce`,
  and `Easing.bezier(x1, y1, x2, y2)`. `Animated.timing(easing=...)`
  accepts an `EasingSpec` or one of those names as a string; any other
  string raises `ValueError`. Bezier curves reach the native drivers as
  control points instead of being stringified.
- Binding an `AnimatedNode` to a style key that no renderer can animate
  natively (`width`, `margin`, and other layout keys) raises `ValueError`
  naming the animatable set: `opacity`, `background_color`, `color`,
  `translate_x`, `translate_y`, `scale`, `scale_x`, `scale_y`, `rotate`,
  `rotate_x`, `rotate_y`.
- `await Animated.timing(...)` (and `spring`, `decay`, `sequence`,
  `parallel`, `stagger`, `loop`) returns `AnimationResult(finished:
  bool)`, and `.start(callback)` passes the same value.
- Gestures gain `enabled: bool` on every descriptor; `Pan` gains
  `active_offset_x`, `active_offset_y`, `fail_offset_x`, `fail_offset_y`
  (each a number or `(min, max)` pair), `max_pointers`, and
  `min_velocity`; `GestureEvent` gains `absolute_x` and `absolute_y`;
  `direction` is typed `SwipeDirection | None`. iOS enforces
  `min_distance` and `min_pointers`, which it currently parses and
  ignores. Every renderer implements the same activation rules.

### Device module fixes

- Android `Camera.take_photo` writes to a `FileProvider` URI passed as
  `EXTRA_OUTPUT`; the library manifest declares the provider and its
  paths resource.
- Android `Location.get_current` requests when-in-use permission inline,
  like iOS.
- `SecureStore.set_item` and `delete_item` raise `NativeModuleError` when
  the native side reports failure.
- `Permissions.check` is documented as `async`;
  `Notifications.get_device_token` documents that it raises
  `NativeModuleError("unsupported")` on Android.

### Performance work included here

Three measured hot spots are small enough to fix alongside the API work
they touch:

- `VNode.__setattr__` and `Ref.__setattr__` consult a module-level
  `journal_active` flag with the import hoisted, and the journal skips
  layout caches, recording only what a failed pass must roll back. Measured: a 2,000-row mount spends 42 percent of its
  time in the journal hook today.
- `BridgeBackend.apply_mutations` builds the wire operations once,
  validates once, and serializes once, instead of encode, decode, patch,
  validate, and encode again.
- Native `VirtualList` emits `on_scroll` only when the app wired it,
  matching `ScrollView`.

### Testing library

```python
from pythonnative.testing import render, within, wait_for

def test_form(pn_clock):
    r = render(Form())
    r.change_text(r.get_by_placeholder_text("Email"), "a@b.c")
    r.press(r.get_by_role("button", name="Save"))
    pn_clock.advance(2.0)                     # timers fire, no real sleep
    assert wait_for(lambda: r.query_by_text("Saved"))
    card = within(r.get_by_test_id("summary"))
    assert card.get_by_display_value("a@b.c")
```

- Queries: `get_by_role(role, *, name=None)`,
  `get_by_placeholder_text`, `get_by_display_value`, each with
  `query_by_` and `get_all_by_` variants. `FakeView.text` no longer
  matches placeholders.
- `wait_for(predicate, timeout=1.0, interval=0.01)` and `find_by_*`
  (`get_by_*` wrapped in `wait_for`).
- `within(view)` returns a scoped query object.
- `press` raises `AssertionError` on a disabled pressable unless
  `force=True`.
- A `FakeClock` patches the framework loop's `time()`; `pn_clock.advance(
  seconds)` runs due timers and drains the loop without sleeping.
- `pythonnative.testing.pytest_plugin` is registered under the `pytest11`
  entry point and provides the autouse runtime-reset fixture and
  `pn_clock`. The repository's own `tests/conftest.py` shrinks to what
  the plugin doesn't cover.

### Tooling

- `pn codegen` regenerates the checked-in Swift and Kotlin contracts for
  every new prop, module, and event; `tests/test_codegen.py` guards
  drift.
- `pn preview` and `pn start` report which `[requirements].packages`
  are missing from the host environment with the exact `pip install`
  line, instead of failing on the first import.
- The e2e suite gains a demo and Maestro flow for every new public
  symbol; `scripts/check-e2e-coverage.py` gains exemptions only for pure
  types and typed records.

## Removals

- The Python view-handler layer: `native_views.NativeViewRegistry`,
  `ViewRecord`, `ViewHandler`, `native_views.get_registry` (replaced by
  `get_backend`), `sdk.register_component`, `sdk.native_component`, the
  tripwire logger,
  `BridgeBackend.register`/`handler_for`, and the `handle_internal_event`
  lookup. Production never runs Python handlers, and the test backend
  implements the registry protocol directly. `sdk.define_component(name,
  props)` returns a typed element factory for extension authors; `Props`
  and `element_factory` stay. The custom-native-components guide is
  rewritten around the generated contract path only.
- `ScrollView(scroll_axis=)` in favor of `horizontal: bool`.
- `Context.Provider(value, *children)` in favor of keyword-only `value`.
- Dict payloads for `on_layout`, `on_scroll`, and `on_selection_change`.
- `Ref._pn_tag` and `Ref._pn_frame`; the `get_registry().command(ref._pn_tag,
  ...)` recipe in the docs.
- Free-form easing strings that fall back silently.
- The Android `TextManager`'s undocumented string props
  (`ellipsize_mode`, `selectable`), now that they're real props on every
  renderer.
- The `requests` dependency: nothing imports it.
- `equality.equal`, `_value_changed`, `_diff_props`, and
  `shallow_equal_props` collapse into one module with one documented
  equality rule. `PYTHONNATIVE_DEBUG` and `Reconciler._log` fold into
  `diagnostics`. Dead browser methods (`Clipboard.has_string`,
  `Linking.get_initial_url`), the `ScreenHost` no-op lifecycle hooks
  (`on_layout`, `on_save_instance_state`, `on_restore_instance_state`,
  and the `getattr` event dispatch), the `log_pn` alias, and the stale
  "Protocol 2" and "keeps the door open" comments go.
- Documentation claims that contradict the code: nested stacks described
  as Python-drawn, predictive back described as supported, "each state
  setter call triggers a re-render", the `on_change_text` name in the
  testing guide, and the async guide's inline-completion claim (which
  becomes true).

No compatibility shims are kept. The project is pre-1.0 and every removed
path is replaced in the same change.

## Alternatives considered

- **Doing the commit-path performance redesign first** (typed validators,
  incremental Yoga styles, compact encoding, frame-paced flush, the iOS
  list layout fix, a native error overlay). Rejected for this RFC: it
  would be invisible in features while the API above is still missing
  pieces any app needs, and settling the public surface first means the
  performance work has a fixed contract to preserve. It's the next RFC.
- **Native sticky headers and inverted lists** via supplementary views
  and reversed layouts. Rejected: three native implementations for a
  behavior Python can express on the existing `VirtualList` contract in
  a few dozen lines; native versions can replace them later without a
  wire change.
- **Android modal presentation as a child stack in a `DialogFragment`.**
  Rejected: React Navigation's native stack also presents Android modals
  as full-screen screens with a bottom slide; matching it is simpler and
  what users expect.
- **A `BoundaryError` dataclass for `ErrorBoundary` fallbacks.** Deferred:
  the current `(error, reset)` callable works and changing it buys
  little.
- **Keeping Python `ViewHandler`s as a preview-only extension path.**
  Rejected: nothing ships through it, and two authoring stories confused
  the guide.
- **Faking time by monkeypatching `asyncio.sleep`.** Rejected in favor of
  patching the loop's `time()` so every timer, including the framework's
  own, advances consistently.

## Non-goals

- Commit-path performance beyond the three small fixes above: typed
  native validators, incremental Yoga style application, a compact op
  encoding, frame-paced flushing, opt-in frame echo, the iOS collection
  view invalidation fix, and a native error overlay (RFC 0003).
- The release pipeline: entitlements tables, splash and icon variants,
  R8, ABI splits, stdlib pruning, bundle trimming, version bumps, store
  upload credentials, config plugins, and over-the-air updates (RFC
  0004).
- Developer tooling: Fast Refresh precision, an on-device dev menu, an
  element inspector, LogBox, RedBox source excerpts, dev-server
  authentication (RFC 0005).
- Expo-SDK breadth: camera preview, image picker upgrades, `watch_position`,
  push handlers, sensors, contacts, calendar, audio and video, maps,
  in-app purchases.
- Layout animations, shared-element transitions, and worklet-style UI
  thread callbacks.
- A native drawer; the drawer navigator stays Python-drawn but themed.
- `PlatformColor` semantic colors, `box_shadow`, `filter`, and
  `mix_blend_mode`.
- Material top tabs.

## Testing and rollout

- Python: unit tests for every runtime fix (effect-error routing, hidden
  Suspense siblings, eager async first step, batching, the single
  render-storm policy, each dev warning), for every new factory argument
  and handle, for the list features, for the navigation additions and the
  `before_remove` matrix, for the decay closed form, `Easing`, the
  animatable-prop check, gesture activation rules, the new modules and
  their fallbacks, and the testing-library additions. `tests/test_codegen.py`
  confirms the generated contracts match.
- Swift: XCTest for transform composition, the decay driver, `Pressable`
  disabled and delay, `Text` truncation and span presses, `TextInput`
  selection and key events, `ScrollView` drag and momentum events,
  `Modal` request-close, `border_style`, 3D transforms, accessibility
  props, the `AccessibilityInfo`, `Keyboard`, `Device`, and
  `Localization` modules, screen presentation and animation mapping, and
  the back-veto restore path.
- Kotlin: JUnit and Robolectric for the same surface plus slide
  transitions, the back arrow, large-title toolbar, dynamic colors, the
  camera `EXTRA_OUTPUT` path, and location permission.
- Browser: `tests/browser/renderer.mjs` covers the new props and the
  Python gesture arbiter's new rules.
- E2E: a demo screen and Maestro flow per new public symbol, and updated
  flows where behavior changed (`Pressable`, `ScrollView`, `Text`,
  `TextInput`, `Modal`, navigation). `hello-world` and `inbox` are
  updated for the `Context.Provider` and `ScrollView` changes.
- Docs: guides and API pages for every new module and option;
  `mkdocs build --strict` passes; the removed claims are corrected.
- `./scripts/check.sh` and `scripts/check-e2e-coverage.py` pass.
- All 115 Maestro flows pass on an iPhone 15 Pro simulator (iOS 17.0)
  and on Android 12 (API 31) emulators, both a 1080 by 2400 phone and
  the 320 by 640 screen CI uses.

## Decisions recorded during implementation

Runtime and typing:

- Typed event records live in `pythonnative.components.events` (the
  former `media_events.py`), because `pythonnative.events` already holds
  the event registry.
- The undo journal records every mutable `VNode` field except layout
  caches, not only the five structural fields the RFC listed. The literal
  list left the tree stale after a failed pass because in-place element
  updates and Suspense hydration were not rolled back. The journal moved
  to `pythonnative.journal` to break the hooks and reconciler import
  cycle; the hot-path gate and hoisted import are as designed.
- `Component.__slots__` keeps its `__dict__` entry: `functools.update_wrapper`
  needs it for `__module__` and `__qualname__`, which Fast Refresh reads.
- `use_ref()` with no argument returns `Ref[Any]`; mypy rejects an
  unbound `T | None` there.
- Eager async stepping runs a body's first step synchronously, so a
  sibling render failure now cancels an already-started body.
- `native_views.get_backend()` raises when no backend is installed
  instead of returning a handler-less table.
- Host lifecycle: `save_state` and `restore_state` are acknowledged
  without calling into the host (restoration state is cached as Python
  publishes it), and the `on_layout` hook is gone; the `layout` event
  carries metrics.

Components and style:

- `ScrollView(content_container_style=)` wraps children in an inner
  `View` whose `flex_direction` follows `horizontal`, so horizontal
  content stacks correctly.
- Inverted horizontal lists mirror with `scale_x: -1`; vertical lists use
  `scale_y: -1`.
- `SectionList(item_separator=)` renders separators only between items
  within a section, never after a header or a section's last item.
- `Text(on_press=)` on the outer element is the whole-label event; only
  nested `Text(on_press=)` produces pressable spans, reported as
  `on_span_press(index)`.
- Sticky section headers derive from the first visible native row rather
  than the item-only viewable-items list, so the overlay hides exactly
  when the real header is at the top.
- `content_inset` is typed `EdgeInsets` so `all`, `horizontal`, and
  `vertical` work; the factory normalizes to the four edges.
- Default-valued enum props are omitted from the wire, matching the
  existing "drop noise" convention.

Device modules:

- `WindowDimensions` stays a `NamedTuple` and gains `scale` and
  `font_scale`, so code that indexed it by position still works.
- `SecureStore.delete_item` returns `None` and raises
  `NativeModuleError(code="delete_failed")` on failure; `set_item` raises
  with `code="write_failed"`. iOS treats deleting an absent key as success.
- `Dimensions.add_listener` delivers `DimensionsEvent(window, screen)`
  and fires only when a size or density changed.
- `Device.info()` keeps `app_dir` and `cache_dir` as extra keys because
  `FileSystem` reads them; `DeviceInfo` doesn't expose them.

Navigation:

- The native back veto uses a `guarded: bool` wire prop on `Screen`,
  sent when the route has at least one `before_remove` listener. UIKit
  refuses the pop synchronously for guarded screens and asks Python; the
  `restore_stack` fallback covers the unguarded race. Android accepts the
  prop and keeps its asynchronous back path.
- `NavigationRef.navigate` resolves only routes the root navigator knows;
  nested routes use `navigate("Tabs", screen="Profile")`.
- `freeze_on_blur` is a parent-driven memo: a state change inside the
  frozen screen still re-renders that component.
- `pop_to` on a route not in history replaces the active screen, as
  React Navigation does; on tab and drawer navigators it falls back to
  `navigate`.
- `NavigatorCore` commits state eagerly so `get_state()` is truthful
  right after an action; this is also what the veto check reads.
- Android presents every modal presentation as a full-screen screen with
  a slide-from-bottom transition; the header of a screen with
  `header_large_title` is an expanded toolbar with a larger title.
  Predictive back is enabled at the activity level; the system back
  preview appears once Python reports that the stack can't pop.

Animation and gestures:

- The decay spec keeps the existing `kind` key: `{"kind": "decay",
  "from", "velocity", "deceleration"}` with velocity in points per
  millisecond and `deceleration` defaulting to `0.998`. Rest is
  `|v| < 0.001` points per millisecond, after which every driver snaps to
  the projected final value.
- `Easing.ease` follows React Native exactly (the same curve as
  `ease_in`), not CSS `ease`. Beziers travel as a bare four-element
  array, which all three drivers already parsed.
- `Pan.min_distance` defaults to `None` (Gesture Handler semantics) and
  resolves to ten points only when no offset or velocity criterion is
  set. `Swipe` and `Fling` take `direction=None` instead of `"any"`.
- `sequence` stops with `finished=False` when a step is stopped.
- Skew transforms are supported on Android API 29 and later through the
  animation matrix, and ignored with a one-time log below that.

Native renderers:

- The iOS animator composes animated transform channels over the static
  `transform` prop into one `CATransform3D`; `rotate_x`, `rotate_y`, and
  `perspective` therefore work on iOS as well.
- iOS selectable text keeps `UILabel` (so measurement, spans, and Dynamic
  Type are unchanged) and offers Copy from the edit menu on long press
  instead of drag handles.
- Dashed and dotted borders use `[3w, 3w]` and `[w, w]` dash patterns;
  per-side borders stay solid.
- The `Host.keyboard` event is gone on both platforms; the `Keyboard`
  module's `change` event feeds `platform_metrics`, which is what
  `use_keyboard_height` and `KeyboardAvoidingView` read.
- `VirtualList.on_scroll` carries `first`, `last`, `extent`, and `range`
  beside the six `ScrollEvent` fields because list windowing reads them;
  the event is untyped in the contract. `ScrollView` scroll events are
  exactly the six fields.
- Modals never dismiss themselves natively. A pull-down or back press
  calls `on_request_close` when it's wired and otherwise leaves the modal
  presented, so `visible` stays owned by Python.
- `keyboard_should_persist_taps="handled"` skips taps that land on a
  control or a pressable; `"never"` dismisses on any content tap outside a
  text input.
- Pan translation is measured from the activation point, and `min_velocity`
  is sampled per move in window space because UIKit doesn't expose a
  velocity before recognition.
- Android `deceleration_rate` scales the fling velocity, since platform
  scrollers hide their friction constant. `"ascii"` maps to a plain text
  keyboard because Android has no ASCII-only hint.
- The browser preview maps `important_for_accessibility="no"` to
  `role="presentation"` so descendants stay reachable, truncates
  head and middle ellipsis modes in JavaScript for single-line text, and
  documents its no-ops (`allow_font_scaling`, `keyboard_appearance`,
  `android_ripple`, image `headers`, status bar props, `deceleration_rate`,
  `bounces`).
- An unknown easing name is refused by every native driver; Python
  validates first, so this is a contract guard, not a fallback.

Found by the simulator runs:

- Events a view emits while its own commit applies (an image starting to
  load as it's created) are stamped with the application, surface, and
  revision of that commit on all three renderers. Before this, they
  carried the previous revision and Python dropped them as older than the
  view, so `on_load_start` never arrived for a newly created image.
- Pressable spans are bounded by their glyphs on every renderer: a tap
  past the end of a line or between spans goes to the outer `Text`, as in
  React Native. Android's stock link handling fired the last span for
  taps past the line end, and a span tap also fired the label's own
  `on_press`; both are fixed.
- The browser preview's native stack draws a navigation bar from the
  top screen's options, hosts the `header_left` and `header_right` slots,
  and routes its back button through `on_native_back`, so the veto path
  matches iOS. A root-level stack hides the host's own bar. Before this,
  preview stacks showed no titles or back buttons at all.
- A horizontal ScrollView's content was laid out in a column on iOS,
  Android, and the browser, so it was squeezed to the viewport width and
  couldn't scroll; only the headless layout wrapped it in a row. The
  factory now gives horizontal ScrollViews `flex_direction: "row"`, which
  every renderer's layout reads.
- `WebViewHandle.eval_js()` never returned a value: WebKit and Android
  answer scripts asynchronously, and the view command discarded the
  result on every renderer. It's now an async `WebViews.eval_js(tag,
  script)` native module method that settles when the page answers, and
  the `eval_js` view command is gone. The browser preview also stored its
  iframe under a property that layout overwrote, which broke every
  preview WebView command after the first layout pass.
- Android never made a `Text` with `on_press` clickable: it waited for an
  `on_press` prop, but wired events travel only in the element's event
  list. The label now re-checks its press whenever that list changes.
- An iOS `Pan` with activation offsets never began: the recognizer waited
  for UIKit's own pan to announce its start, which UIKit does once at
  about ten points of travel, before a twenty-point offset is met. The
  activation rules now begin the pan themselves.
- `TextInputHandle.clear()` reports `on_change("")` on every renderer, so a
  controlled value follows. Android's text watcher already did; iOS and
  the browser cleared the field silently.
- iOS reports `"Enter"` from `on_key_press` when Return is pressed in a
  single-line field, matching multiline fields, Android, and the browser.
  UIKit's empty edit over an empty range, which it sends while committing
  text as a field ends editing, is no longer reported as a Backspace.
- A `Modal` opened a second time showed an empty sheet on iOS and
  Android, a bug older than this RFC: each presentation builds a new
  content view, the first one took the children, and closing left them
  there. Both runtimes now keep a modal's children for its whole life
  and move them into every presentation.
- One iOS sheet pull-down reported `on_request_close` twice, because
  UIKit asks `presentationControllerShouldDismiss` and then reports the
  refused attempt, and both answered. Only the refused attempt reports
  now, and a sheet locked with `dismiss_on_backdrop=False` reports
  nothing.
- Android now fires `on_dismiss` when `visible` becomes `False`, as iOS
  and the browser already did, and an overlay's backdrop tap no longer
  closes the modal natively when `on_request_close` isn't wired. A
  backdrop tap is one outside every child on all three renderers; iOS
  and preview overlays ignored backdrop taps before, and Android counted
  taps on plain text inside the modal.

Found by CI, whose Android emulator has a 320 by 640 screen:

- The Android `Keyboard` module never saw the keyboard. It read IME
  insets on the activity's content view, but under `adjustResize` the
  window applies the IME inset as padding above that view, which then
  reads a zero height. It now observes the decor view, which sees the
  insets first, and hands them on unchanged.
- A build with a native plugin renamed built-in generated types (such as
  `PNViewWidth`) and broke the hand-written Kotlin that names them.
  Codegen decides which View props are shared by comparing every
  component's schema, and an extension manifest arrives through JSON, so
  a built-in tuple never equaled the manifest's list. The comparison now
  uses the JSON form, and the example extension's manifest is
  regenerated and checked against the built-ins by a test.
- Several new demos didn't fit a short screen: controls sat under the
  keyboard or below the fold. Their flows scroll each target into view,
  and the Android shards were rebalanced to stay under the emulator's
  stable session length.

Testing library:

- `FakeClock` adds a virtual offset to real monotonic time rather than
  freezing time, because `runtime.drain` paces itself with real one
  millisecond sleeps; `advance()` steps timer by timer so re-arming
  timers fire the right number of times.
- `press` on a disabled target raises `AssertionError` unless
  `force=True`; `RenderResult.act` mirrors `HookResult.act`.
