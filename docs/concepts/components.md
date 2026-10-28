# Components

PythonNative uses a **declarative component model** inspired by
React. You describe *what* the UI should look like, and the framework
handles creating and updating native views.

## Element functions

UI is built with element-creating functions. Each returns a
lightweight [`Element`][pythonnative.Element] descriptor; no native
objects are created until the
[`Reconciler`][pythonnative.reconciler.Reconciler] mounts the tree.

```python
import pythonnative as pn

pn.Text("Hello", style={"font_size": 18, "color": "#333333"})
pn.Button("Tap me", on_press=lambda: print("tapped"))
pn.Column(
    pn.Text("First"),
    pn.Text("Second"),
    style={"gap": 8, "padding": 16},
)
```

### Available components

**Layout:**

- [`View(*children, style=...)`][pythonnative.View]: universal flex
  container (default `flex_direction: "column"`).
- [`Column(*children, style=...)`][pythonnative.Column]: vertical
  flex container (fixed `flex_direction: "column"`).
- [`Row(*children, style=...)`][pythonnative.Row]: horizontal flex
  container (fixed `flex_direction: "row"`).
- [`ScrollView(*children, horizontal, content_container_style, ...)`][pythonnative.ScrollView]:
  scrollable container with drag, momentum, snapping, and keyboard
  options.
- [`SafeAreaView(*children, style=...)`][pythonnative.SafeAreaView]:
  safe-area-aware container.
- [`Spacer(size, flex)`][pythonnative.Spacer]: empty space.

**Display:**

- [`Text(*parts, ellipsize_mode, selectable, on_press, style=...)`][pythonnative.Text]:
  text display, with nested pressable spans.
- [`Image(source, style=...)`][pythonnative.Image]: image display
  (supports URLs and resource names).
- [`WebView(url)`][pythonnative.WebView]: embedded web content.

**Input:**

- [`Button(title, on_press, style=...)`][pythonnative.Button]:
  tappable button.
- [`TextInput(value, placeholder, on_change, secure, style=...)`][pythonnative.TextInput]:
  text entry.
- [`Switch(value, on_change)`][pythonnative.Switch]: toggle switch.
- [`Slider(value, min_value, max_value, on_change)`][pythonnative.Slider]:
  continuous slider.
- [`Pressable(child, on_press, on_long_press, disabled, android_ripple)`][pythonnative.Pressable]:
  tap handler wrapper whose child and `style` may be functions of a
  [`PressState`][pythonnative.PressState].

**Feedback:**

- [`ProgressBar(value)`][pythonnative.ProgressBar]: determinate
  progress (0.0 to 1.0).
- [`ActivityIndicator(animating)`][pythonnative.ActivityIndicator]:
  indeterminate spinner.

**Overlay:**

- [`Modal(*children, visible, on_dismiss, on_request_close, title)`][pythonnative.Modal]:
  modal dialog.
- [`Portal(*children)`][pythonnative.Portal]: render children into a
  full-screen overlay above everything else (analogous to React DOM's
  `createPortal`). The children stay part of your component tree for
  state, context, and events; only their native views move. Use it for
  toasts, floating action buttons, and custom dropdowns.

**Error handling:**

- [`ErrorBoundary(*children, fallback, on_error)`][pythonnative.ErrorBoundary]:
  catches render errors in the subtree and displays `fallback`. The
  fallback may be an element, `fallback(error)`, or
  `fallback(error, reset)` where `reset` remounts the children.

**Composition:**

- [`Fragment(*children, key)`][pythonnative.Fragment]: group siblings
  into a parent's child list without an extra wrapping view (analogous
  to React's `<>…</>`). A keyed Fragment moves all of its children as
  one unit during keyed reconciliation.
- Components may also return a plain `list` of elements, or `None` to
  render nothing; `None` and `False` children are dropped, so
  `cond and pn.Text(...)` works for conditional rendering.

**Lists:**

- [`FlatList(data, render_item, key_extractor, item_height, inverted, item_separator, ...)`][pythonnative.FlatList]:
  virtualized scrollable data list. Rows are mounted lazily as they
  scroll into view; pass `item_height=` (or `get_item_height=`) for
  exact extents, or let rows be measured on screen.
- [`SectionList(sections, render_item, render_section_header, sticky_section_headers, ...)`][pythonnative.SectionList]:
  virtualized list with section headers.

**Platform UI:**

- [`StatusBar(bar_style, background_color, hidden, translucent, animated)`][pythonnative.StatusBar]:
  configure the device's status bar (light/dark icons, color, hidden).
- [`KeyboardAvoidingView(*children, behavior)`][pythonnative.KeyboardAvoidingView]:
  shift content up when the software keyboard appears.
- [`RefreshControl(refreshing, on_refresh)`][pythonnative.RefreshControl]:
  pull-to-refresh control for `ScrollView`, `FlatList`, and
  `SectionList` (passed via the `refresh_control=` prop).
- [`Picker(value, items, on_change, placeholder)`][pythonnative.Picker]:
  select / dropdown widget backed by an action sheet.

**Imperative APIs:**

- [`Alert.show(title, message)`][pythonnative.alerts.Alert.show]:
  fire-and-forget single-button notice.
- [`await Alert.confirm(title, message)`][pythonnative.alerts.Alert.confirm]:
  awaitable two-button yes/no (resolves to a ``bool``).
- [`await Alert.choose(title, options=[...])`][pythonnative.alerts.Alert.choose]:
  awaitable multi-button picker / action sheet (resolves to the
  selected label, or ``None``).

**Animations:**

- `Animated.View` / `Animated.Text` / `Animated.Image`: components
  whose `style` accepts [`AnimatedValue`][pythonnative.AnimatedValue]
  instances. Drive animations with `Animated.timing`,
  `Animated.spring`, or `Animated.decay`. See the
  [Animations guide](../guides/animations.md).

### Flex layout model

PythonNative uses a **flexbox-inspired layout model**. `View` is the
universal flex container; `Column` and `Row` are convenience wrappers
that fix the direction.

#### Flex container properties (inside `style`)

- `flex_direction`: `"column"` (default), `"row"`, `"column_reverse"`,
  `"row_reverse"`.
- `justify_content`: main-axis distribution: `"flex_start"`,
  `"center"`, `"flex_end"`, `"space_between"`, `"space_around"`,
  `"space_evenly"`.
- `align_items`: cross-axis alignment: `"stretch"`, `"flex_start"`,
  `"center"`, `"flex_end"`.
- `overflow`: `"visible"` (default), `"hidden"`.
- `gap`: space between children (dp / pt).
- `padding`: inner spacing.

#### Child layout properties

All components accept these in their `style` dict:

- `width`, `height`: fixed dimensions (dp / pt).
- `flex`: flex grow factor (shorthand).
- `flex_grow`, `flex_shrink`: individual flex properties.
- `margin`: outer margin (int, float, or dict like padding).
- `min_width`, `min_height`: minimum size constraints.
- `max_width`, `max_height`: maximum size constraints.
- `align_self`: override parent alignment for this child.

#### Example: centering content

```python
pn.View(
    pn.Text("Centered"),
    style={"flex": 1, "justify_content": "center", "align_items": "center"},
)
```

#### Example: horizontal row with spacing

```python
pn.Row(
    pn.Button("Cancel"),
    pn.Spacer(flex=1),
    pn.Button("OK"),
    style={"padding": 16, "align_items": "center"},
)
```

## Function components: the building block

All UI in PythonNative is built with `@pn.component` function
components. Each screen is a function component that returns an
element tree:

```python
@pn.component
def App() -> pn.Node:
    name, set_name = pn.use_state("World")
    return pn.Text(f"Hello, {name}!", style={"font_size": 24})
```

The entry point [`create_screen`][pythonnative.create_screen] is called
internally by native templates to bootstrap your root component. You
don't call it directly: name your top-level component `App` (so the
templates can find it by convention) and `app.entry_point` in
`pythonnative.toml` points at the module that defines it.

## State and re-rendering

Use [`use_state(initial)`][pythonnative.use_state] to create local
component state. Call the setter to update; the framework automatically
re-renders the component and applies only the differences to the
native views:

```python
@pn.component
def CounterPage() -> pn.Node:
    count, set_count = pn.use_state(0)

    return pn.Column(
        pn.Text(f"Count: {count}", style={"font_size": 24}),
        pn.Button("Increment", on_press=lambda: set_count(count + 1)),
        style={"gap": 12},
    )
```

## Composing components

Build complex UIs by composing smaller `@pn.component` functions.
Each instance has **independent state**:

```python
@pn.component
def Counter(label: str = "Count", initial: int = 0) -> pn.Node:
    count, set_count = pn.use_state(initial)

    return pn.Column(
        pn.Text(f"{label}: {count}", style={"font_size": 18}),
        pn.Row(
            pn.Button("-", on_press=lambda: set_count(count - 1)),
            pn.Button("+", on_press=lambda: set_count(count + 1)),
            style={"gap": 8},
        ),
        style={"gap": 4},
    )


@pn.component
def App() -> pn.Node:
    return pn.Column(
        Counter(label="Apples", initial=0),
        Counter(label="Oranges", initial=5),
        style={"gap": 16, "padding": 16},
    )
```

Changing one `Counter` doesn't affect the other; each has its own
hook state.

### Children

Children are positional, for your components exactly as for the
built-in containers. A component that accepts children declares
`*children: pn.Node`:

```python
@pn.component
def Card(*children: pn.Node, title: str) -> pn.Node:
    return pn.Column(
        pn.Text(title, style={"bold": True}),
        *children,
        style={"padding": 12, "border_radius": 8},
    )


Card(pn.Text("Body"), pn.Button("OK"), title="Hello")
```

[`pn.Node`][pythonnative.element.Node] is the type of anything that
can appear in a tree: an element, `None` or a `bool` for "nothing", or
a (possibly nested) iterable of nodes. That makes the usual
conditional idioms type-check:

```python
pn.Column(
    pn.Text(status) if status else None,
    is_admin and AdminBanner(),
    (Row(item=item).with_key(item.id) for item in items),
)
```

`None` and `False` are dropped during reconciliation, and nested
iterables are flattened. Strings aren't nodes: wrap text in
[`pn.Text`][pythonnative.Text]. Annotate every component's return type
as `pn.Node`, since a component may return an element, a list of
siblings, or `None` to render nothing.

### Typed props

`@pn.component` preserves the function's signature for type checkers
(it's a `ParamSpec`), so `Card(titel="x")` is a static error and editors
autocomplete props from the function definition.

In development builds (`pn start`, `pn run` without `--release`, and
every test run under the pytest plugin), each call is also checked
against the function's annotations at run time. A mismatch, such as
`Card(title=3)` from untyped code, produces one
[`diagnostics`][pythonnative.diagnostics] warning per component and
parameter instead of an exception. The checker understands `str`,
`int`, `float` (which accepts `int`), `bool`, `None`, `Optional`,
unions, `Literal`, `Sequence`, `Mapping`, `Callable`, dataclasses, and
plain classes, and skips annotations it can't evaluate. Release builds
skip the check entirely, along with the built-in components' prop and
style validation. Static checking remains the primary guard.

### Keys

A key identifies an element among its siblings so the reconciler can
match it across renders when a list is reordered, inserted into, or
filtered. Built-in factories take `key=` directly. User components
don't: `key` isn't a prop, and PEP 612 doesn't allow a typed keyword
next to a component's own signature. Key any element with
[`.with_key()`][pythonnative.element.Element.with_key] instead:

```python
@pn.component
def Row(item: Item) -> pn.Node:
    return pn.Text(item.title)


pn.Column(*(Row(item).with_key(item.id) for item in items))
pn.Column(*(pn.Text(item.title, key=str(item.id)) for item in items))
```

`with_key` accepts any value and converts non-strings with `str`.
Passing `key=` to a user component raises `TypeError` pointing to
`.with_key()`, a component may not declare a parameter named `key`, and
[`pn lint`](../guides/linting.md) reports `key=` on a component call
(rule `PN104`) before you run the app.

### Available hooks

- [`use_state(initial)`][pythonnative.use_state]: local component
  state; returns `(value, setter)`.
- [`use_reducer(reducer, initial_state)`][pythonnative.use_reducer]:
  reducer-based state; returns `(state, dispatch)`.
- [`use_effect(effect, deps)`][pythonnative.use_effect]: side effects,
  run after native commit (timers, API calls, subscriptions).
- [`use_layout_effect(effect, deps)`][pythonnative.use_layout_effect]:
  side effects run synchronously inside the commit, before passive
  effects; use to measure committed frames or issue view commands.
- [`use_memo(factory, deps)`][pythonnative.use_memo]: memoized
  computed values.
- [`use_callback(fn, deps)`][pythonnative.use_callback]: stable
  function references.
- [`use_ref(initial)`][pythonnative.use_ref]: mutable
  [`Ref`][pythonnative.Ref] that persists across renders. When passed
  via the `ref=` prop, the reconciler publishes a typed
  [handle](../api/handles.md) on `ref.current`.
- [`use_imperative_handle(ref, factory, deps)`][pythonnative.use_imperative_handle]:
  publish a controller object on `ref.current` from a composite
  component (how `FlatList` exposes its
  [`ListController`][pythonnative.ListController]).
- [`use_back_handler(handler)`][pythonnative.use_back_handler]:
  intercept the Android back action / browser Escape; return `True`
  to consume.
- [`use_animated_value(initial)`][pythonnative.use_animated_value]:
  stable [`AnimatedValue`][pythonnative.AnimatedValue] across renders;
  the canonical way to drive `Animated.View`.
- [`use_context(context)`][pythonnative.use_context]: read from a
  context provider.
- [`use_store(store, selector)`][pythonnative.use_store]: read an app
  [`Store`][pythonnative.Store], re-rendering only when the selected
  value changes.
- [`use_theme()`][pythonnative.use_theme] and
  [`use_styles(factory)`][pythonnative.use_styles]: read the active
  [`Theme`][pythonnative.Theme] and derive styles from it once per
  theme.
- [`use_navigation()`][pythonnative.use_navigation]: the
  [`Navigation`][pythonnative.Navigation] handle for navigate, push,
  go_back, set_options, and listeners.
- [`use_screen_options(**options)`][pythonnative.use_screen_options]:
  set the current screen's title and header from its render.
- [`use_route()`][pythonnative.use_route]: the current
  [`Route`][pythonnative.navigation.Route] (name, params, key). Screens
  receive their params as arguments, so few need it.
- [`use_focus_effect(effect, deps)`][pythonnative.use_focus_effect]:
  like `use_effect` but only runs when the screen is focused.
- [`use_window_dimensions()`][pythonnative.use_window_dimensions]:
  reactive viewport size.
- [`use_safe_area_insets()`][pythonnative.use_safe_area_insets]:
  reactive safe-area insets.
- [`use_keyboard_height()`][pythonnative.use_keyboard_height]:
  reactive software-keyboard height.
- [`use_color_scheme()`][pythonnative.use_color_scheme]: the effective
  [`ColorScheme`][pythonnative.hooks.ColorScheme], `"light"` or `"dark"`.
- [`use_screen_reader_enabled()`][pythonnative.use_screen_reader_enabled],
  [`use_reduce_motion()`][pythonnative.use_reduce_motion],
  [`use_locales()`][pythonnative.use_locales]: reactive device settings
  from the [native modules](../guides/native-modules.md).
- [`@memo`][pythonnative.memo]: decorator that skips a function
  component's re-render when its props are shallowly equal and its
  internal state is unchanged.

### Custom hooks

Extract reusable stateful logic into plain functions:

```python
from collections.abc import Callable


def use_toggle(initial: bool = False) -> tuple[bool, Callable[[], None]]:
    value, set_value = pn.use_state(initial)

    def toggle() -> None:
        set_value(lambda current: not current)

    return value, toggle
```

A custom hook is a function whose name starts with `use_`. It follows
the same rules as the built-in hooks, which `pn lint` checks; see
[Hooks](hooks.md#rules-of-hooks).

### Context and Provider

Share values across the tree without prop drilling:

```python
Accent = pn.create_context("#007AFF", name="Accent")


@pn.component
def App() -> pn.Node:
    return Accent.Provider(MyComponent(), value="#FF2D55")


@pn.component
def MyComponent() -> pn.Node:
    accent = pn.use_context(Accent)
    return pn.Button("Click", style={"color": accent})
```

For colors and other design tokens, use the built-in
[`Theme`][pythonnative.Theme] and
[`ThemeProvider`][pythonnative.ThemeProvider] rather than a context of
your own; see [Styling](../guides/styling.md#themes). For app state
that many components read, see [Managing state](../guides/state.md).

## Platform detection

The recommended way to write platform-aware code is via
[`Platform`][pythonnative.Platform]:

```python
import pythonnative as pn

title = pn.Platform.select({"ios": "iOS App", "android": "Android App"})

if pn.Platform.is_ios:
    margin = 16
```

`pn.Platform.OS` is `"ios"`, `"android"`, `"web"` (the `pn preview`
browser preview, see the [Browser preview guide](../guides/browser-preview.md)),
or `"test"` (off-device, e.g. in unit tests). The lower-level
`utils.IS_ANDROID` / `utils.IS_IOS` / `utils.IS_WEB` constants are
still available.

`Platform.select` matches on the exact key; a `"native"` key is shared
by iOS **and** Android (but not the browser preview), and a `"default"`
key catches anything unmatched:

```python
pad = pn.Platform.select({"native": 16, "web": 12, "default": 8})
```

## Next steps

- Learn the renderer underneath: [Architecture](architecture.md).
- Manage state and side effects: [Hooks](hooks.md) and
  [Managing state](../guides/state.md).
- See worked examples: [Examples](../examples.md).
- Browse the API: [Components](../api/components.md).
