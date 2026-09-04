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
    style={"spacing": 8, "padding": 16},
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
- [`ScrollView(child, style=...)`][pythonnative.ScrollView]:
  scrollable container.
- [`SafeAreaView(*children, style=...)`][pythonnative.SafeAreaView]:
  safe-area-aware container.
- [`Spacer(size, flex)`][pythonnative.Spacer]: empty space.

**Display:**

- [`Text(text, style=...)`][pythonnative.Text]: text display.
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
- [`Pressable(child, on_press, on_long_press)`][pythonnative.Pressable]:
  tap handler wrapper.

**Feedback:**

- [`ProgressBar(value)`][pythonnative.ProgressBar]: determinate
  progress (0.0 to 1.0).
- [`ActivityIndicator(animating)`][pythonnative.ActivityIndicator]:
  indeterminate spinner.

**Overlay:**

- [`Modal(*children, visible, on_dismiss, title)`][pythonnative.Modal]:
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

- [`FlatList(data, render_item, key_extractor, item_height, ...)`][pythonnative.FlatList]:
  virtualized scrollable data list. Rows are mounted lazily as they
  scroll into view; pass `item_height=` (or `get_item_height=`) for
  exact extents, or let rows be measured on screen.
- [`SectionList(sections, render_item, render_section_header, item_height, ...)`][pythonnative.SectionList]:
  virtualized list with section headers.

**Platform UI:**

- [`StatusBar(bar_style, background_color, hidden)`][pythonnative.StatusBar]:
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
- `spacing`: gap between children (dp / pt).
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
def App():
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
def CounterPage():
    count, set_count = pn.use_state(0)

    return pn.Column(
        pn.Text(f"Count: {count}", style={"font_size": 24}),
        pn.Button("Increment", on_press=lambda: set_count(count + 1)),
        style={"spacing": 12},
    )
```

## Composing components

Build complex UIs by composing smaller `@pn.component` functions.
Each instance has **independent state**:

```python
@pn.component
def Counter(label: str = "Count", initial: int = 0):
    count, set_count = pn.use_state(initial)

    return pn.Column(
        pn.Text(f"{label}: {count}", style={"font_size": 18}),
        pn.Row(
            pn.Button("-", on_press=lambda: set_count(count - 1)),
            pn.Button("+", on_press=lambda: set_count(count + 1)),
            style={"spacing": 8},
        ),
        style={"spacing": 4},
    )


@pn.component
def App():
    return pn.Column(
        Counter(label="Apples", initial=0),
        Counter(label="Oranges", initial=5),
        style={"spacing": 16, "padding": 16},
    )
```

Changing one `Counter` doesn't affect the other; each has its own
hook state.

### Children and keys

Children are positional, for your components exactly as for the
built-in containers. A component that accepts children declares
`*children`:

```python
@pn.component
def Card(*children: pn.Element, title: str):
    return pn.Column(
        pn.Text(title, style={"bold": True}),
        *children,
        style={"padding": 12, "border_radius": 8},
    )


Card(pn.Text("Body"), pn.Button("OK"), title="Hello")
```

`@pn.component` preserves the function's signature for type checkers,
so `Card(titel="x")` is a static error and editors autocomplete props.
Every component also accepts `key=` for keyed reconciliation; when a
strict type checker complains about it, declare `key: str | None =
None` in the signature or call `.with_key(...)` on the element.

Components that return a `list` of elements render them as siblings;
`None` and `False` are dropped, so `cond and pn.Text("...")` is a
fine way to render conditionally.

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
  via the `ref=` prop, the reconciler populates `ref.current` with the
  underlying native view.
- [`use_imperative_handle(ref, factory, deps)`][pythonnative.use_imperative_handle]:
  publish a controller object on `ref.current` from a composite
  component (how `FlatList` exposes its
  [`ListController`][pythonnative.ListController]).
- [`use_back_handler(handler)`][pythonnative.use_back_handler]:
  intercept the Android back button / desktop Escape; return `True`
  to consume.
- [`use_animated_value(initial)`][pythonnative.use_animated_value]:
  stable [`AnimatedValue`][pythonnative.AnimatedValue] across renders;
  the canonical way to drive `Animated.View`.
- [`use_context(context)`][pythonnative.use_context]: read from a
  context provider.
- [`use_navigation()`][pythonnative.use_navigation]: the
  [`Navigation`][pythonnative.Navigation] handle for navigate, push,
  go_back, set_options, and listeners.
- [`use_route()`][pythonnative.use_route]: the current
  [`Route`][pythonnative.navigation.Route] (name, params, key).
- [`use_focus_effect(effect, deps)`][pythonnative.use_focus_effect]:
  like `use_effect` but only runs when the screen is focused.
- [`use_window_dimensions()`][pythonnative.use_window_dimensions]:
  reactive viewport size.
- [`use_safe_area_insets()`][pythonnative.use_safe_area_insets]:
  reactive safe-area insets.
- [`use_keyboard_height()`][pythonnative.use_keyboard_height]:
  reactive software-keyboard height.
- [`@memo`][pythonnative.memo]: decorator that skips a function
  component's re-render when its props are shallowly equal and its
  internal state is unchanged.

### Custom hooks

Extract reusable stateful logic into plain functions:

```python
def use_toggle(initial: bool = False):
    value, set_value = pn.use_state(initial)
    def toggle():
        set_value(not value)
    return value, toggle
```

### Context and Provider

Share values across the tree without prop drilling:

```python
theme = pn.create_context({"primary": "#007AFF"})

@pn.component
def App():
    return theme.Provider({"primary": "#FF0000"}, MyComponent())

@pn.component
def MyComponent():
    t = pn.use_context(theme)
    return pn.Button("Click", style={"color": t["primary"]})
```

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
- Manage state and side effects: [Hooks](hooks.md).
- See worked examples: [Examples](../examples.md).
- Browse the API: [Components](../api/components.md).
