# Function components and hooks

PythonNative uses React-like function components with hooks for
managing state, effects, navigation, memoization, and context.
Function components decorated with `@pn.component` are the only way
to build UI in PythonNative.

## Creating a function component

Decorate a Python function with `@pn.component`:

```python
import pythonnative as pn

@pn.component
def Greeting(name: str = "World") -> pn.Node:
    return pn.Text(f"Hello, {name}!", style={"font_size": 20})
```

Use it like any other component:

```python
@pn.component
def MyPage() -> pn.Node:
    return pn.Column(
        Greeting(name="Alice"),
        Greeting(name="Bob"),
        style={"gap": 12},
    )
```

## Hooks

Hooks let function components manage state and side effects. They must be called at the top level of a `@pn.component` function or a custom hook (not inside loops or conditions). [`pn lint`](../guides/linting.md) checks this for you; see [Rules of hooks](#rules-of-hooks).

### use_state

Local component state. Returns `(value, setter)`.

```python
@pn.component
def Counter(initial: int = 0) -> pn.Node:
    count, set_count = pn.use_state(initial)

    return pn.Column(
        pn.Text(f"Count: {count}"),
        pn.Button("+", on_press=lambda: set_count(count + 1)),
    )
```

The setter accepts a value or a function that receives the current value:

```python
set_count(10)                     # set directly
set_count(lambda prev: prev + 1) # functional update
```

If the initial value is expensive to compute, pass a callable:

```python
count, set_count = pn.use_state(lambda: compute_default())
```

### use_reducer

For complex state logic, [`use_reducer`][pythonnative.use_reducer]
lets you manage state transitions through a reducer function (similar
to React's `useReducer`):

```python
from typing import Literal

Action = Literal["increment", "decrement", "reset"]


def reducer(state: int, action: Action) -> int:
    if action == "increment":
        return state + 1
    if action == "decrement":
        return state - 1
    return 0


@pn.component
def Counter() -> pn.Node:
    count, dispatch = pn.use_reducer(reducer, 0)

    return pn.Column(
        pn.Text(f"Count: {count}"),
        pn.Row(
            pn.Button("-", on_press=lambda: dispatch("decrement")),
            pn.Button("+", on_press=lambda: dispatch("increment")),
            pn.Button("Reset", on_press=lambda: dispatch("reset")),
            style={"gap": 8},
        ),
    )
```

The reducer receives the current state and an action, and returns the new state. Actions can be any value (strings, tuples, dataclasses, and so on). The component only re-renders when the reducer returns a different state. The hook is generic over the state type and the action type, so with the annotated reducer above a type checker rejects `dispatch("typo")`.

### use_effect

Run side effects **after** the native view tree is committed. The effect function may return a cleanup callable.

```python
import asyncio


@pn.component
def Timer() -> pn.Node:
    seconds, set_seconds = pn.use_state(0)

    async def tick() -> None:
        await asyncio.sleep(1.0)
        set_seconds(seconds + 1)

    pn.use_effect(tick, [seconds])

    return pn.Text(f"Elapsed: {seconds}s")
```

Effects are **deferred**: they are queued during the render phase and
executed after the reconciler finishes committing native view
mutations. This means effect callbacks can safely measure layout or
interact with the committed native tree.

The effect callback may be an `async def` (as above); the coroutine
runs as a task on the framework loop and is **cancelled
automatically** when the effect re-runs or the component unmounts, so
the sleeping tick above never fires against an unmounted component.
See the [Async + data guide](../guides/async.md).

Dependency control (`deps` is any [`Deps`][pythonnative.Deps] sequence,
a list or a tuple):

- `pn.use_effect(fn, None)`: run on every render.
- `pn.use_effect(fn, [])` or `pn.use_effect(fn, ())`: run on mount only.
- `pn.use_effect(fn, [a, b])`: run when `a` or `b` change (compared by
  identity, then `==`; bound methods of the same object compare equal).

List every value from the component that the effect reads. `pn lint`
reports a missing dependency as `PN103`.

An exception raised inside an effect is routed to the nearest
[`ErrorBoundary`][pythonnative.ErrorBoundary], exactly like an
exception raised during render. In dev mode the reconciler also warns
once per site when a dependency list changes length between renders.

### use_layout_effect

Like [`use_effect`][pythonnative.use_effect], but runs synchronously
inside the commit, after native mutations and the layout pass and
before passive effects. Use it to read a committed frame from a ref or
to issue an imperative command (like scrolling a list into position)
before the user sees the new frame:

```python
@pn.component
def Chat(messages: list[str]) -> pn.Node:
    list_ref = pn.use_ref()

    def scroll_to_bottom() -> None:
        if list_ref.current is not None:
            list_ref.current.scroll_to_end(animated=False)

    pn.use_layout_effect(scroll_to_bottom, [len(messages)])
    return pn.FlatList(data=messages, render_item=lambda text, index: pn.Text(text), ref=list_ref)
```

Prefer `use_effect` for everything else; layout effects block the
commit, so heavy work here delays the frame.

### use_navigation

Access navigation from any screen. Returns the
[`Navigation`][pythonnative.Navigation] handle for the current route,
with `.navigate()`, `.push()`, `.go_back()`, `.set_options()`,
`.add_listener()`, and more. Destinations are screen components called
with their params, and a screen receives its params as ordinary
arguments:

```python
@pn.component
def HomeScreen() -> pn.Node:
    nav = pn.use_navigation()

    return pn.Column(
        pn.Text("Home", style={"font_size": 24}),
        pn.Button("Go to details", on_press=lambda: nav.push(DetailScreen(id=42))),
        style={"gap": 12, "padding": 16},
    )


@pn.component
def DetailScreen(id: int) -> pn.Node:
    nav = pn.use_navigation()
    pn.use_screen_options(title=f"Item {id}")

    return pn.Column(
        pn.Text(f"Detail #{id}", style={"font_size": 20}),
        pn.Button("Back", on_press=nav.go_back),
        style={"gap": 12, "padding": 16},
    )
```

[`use_screen_options`][pythonnative.use_screen_options] sets the
calling screen's title, header buttons, and other
[`ScreenOptions`][pythonnative.ScreenOptions] from its render. See the
[Navigation guide](../guides/navigation.md) for full details.

### use_route

Read the current [`Route`][pythonnative.navigation.Route]: its
`name`, raw `params` dict, and `key`, which is unique for each visit.
Screens get their params as arguments, so reach for `use_route` only
when you need the route's identity:

```python
@pn.component
def DetailScreen(id: int) -> pn.Node:
    route = pn.use_route()
    return pn.Text(f"Detail #{id} (visit {route.key})")
```

### use_focus_effect

Like [`use_effect`][pythonnative.use_effect] but only runs when the
screen is focused. Useful for refreshing data when navigating back to
a screen:

```python
@pn.component
def FeedScreen() -> pn.Node:
    items, set_items = pn.use_state(list[str]())
    pn.use_focus_effect(lambda: load_items(set_items), [])
    return pn.FlatList(data=items, render_item=lambda item, index: pn.Text(item))
```

### use_memo

Memoize an expensive computation:

```python
sorted_items = pn.use_memo(lambda: sorted(items, key=lambda x: x.name), [items])
```

### use_callback

Return a stable function reference (avoids unnecessary re-renders of children):

```python
handle_click = pn.use_callback(lambda: set_count(count + 1), [count])
```

### use_ref

Returns a [`Ref`][pythonnative.Ref], a mutable container that persists
across renders without triggering re-renders:

```python
render_count = pn.use_ref(0)
render_count.current += 1
```

`use_ref(0)` is a `Ref[int]`; `use_ref()` with no argument is a
`Ref[Any]` meant to be filled in later (by a handle, a timer, a task).

### Refs and handles

Pass a ref to a built-in element via the `ref=` prop and the reconciler
publishes a typed imperative **handle** on `ref.current` after commit,
chosen by element type, and clears it back to `None` on unmount:

| Element | `ref.current` |
|---|---|
| `TextInput` | [`TextInputHandle`][pythonnative.TextInputHandle]: `focus()`, `blur()`, `clear()`, `select_all()`, `set_selection(start, end=None)`, `await get_value()` |
| `ScrollView` | [`ScrollViewHandle`][pythonnative.ScrollViewHandle]: `scroll_to(x=None, y=None, animated=True)`, `scroll_to_end(animated=True)`, `flash_scroll_indicators()`, `await get_scroll_offset()` (a [`ScrollOffset`][pythonnative.ScrollOffset]) |
| `WebView` | [`WebViewHandle`][pythonnative.WebViewHandle]: `reload()`, `go_back()`, `go_forward()`, `stop_loading()`, `load_url(url)`, `inject_javascript(script)`, `await eval_js(script)`, `await can_go_back()`, `await can_go_forward()`, `await get_url()` |
| `FlatList`, `SectionList` | [`ListController`][pythonnative.ListController]: `scroll_to_index`, `scroll_to_offset`, `scroll_to_end` |
| everything else | [`ViewHandle`][pythonnative.ViewHandle] |

Every handle exposes `tag`, `type_name`, and `frame`, the last committed
[`LayoutEvent`][pythonnative.LayoutEvent] written by the layout pass, so
Python code can read measured geometry without a native round-trip.
Methods that act on the view are plain calls; methods that need an
answer from the native view are `async`:

```python
@pn.component
def Search() -> pn.Node:
    field = pn.use_ref()

    def focus_field() -> None:
        if field.current is not None:
            field.current.focus()

    pn.use_effect(focus_field, [])
    return pn.TextInput(placeholder="Search", ref=field)


@pn.component
def MeasuredBox() -> pn.Node:
    box = pn.use_ref()

    def report() -> None:
        if box.current is not None and box.current.frame is not None:
            print(box.current.frame.width, box.current.frame.height)

    pn.use_layout_effect(report)
    return pn.View(ref=box, style={"height": 48})
```

A custom native component's own commands go through
[`ViewHandle.command`][pythonnative.handles.ViewHandle.command]; see
the [Custom native components guide](../guides/custom-native-components.md#commands).
The full reference is on the [Handles](../api/handles.md) page.

### use_imperative_handle

Composite components that accept a `ref` prop can publish a curated
controller object on `ref.current` instead of a raw native view.
[`FlatList`][pythonnative.FlatList] does this out of the box: it
installs a [`ListController`][pythonnative.ListController] with
`scroll_to_offset`, `scroll_to_index`, and `scroll_to_end` methods.
Your own components use [`use_imperative_handle`][pythonnative.use_imperative_handle]:

```python
from typing import Any


@pn.component
def VideoPlayer(source: str, ref: pn.Ref[Any] | None = None) -> pn.Node:
    pn.use_imperative_handle(ref, lambda: PlayerController(source), [source])
    return pn.View(style={"aspect_ratio": 16 / 9})


@pn.component
def PlayerScreen(url: str) -> pn.Node:
    player = pn.use_ref()
    return pn.Column(
        VideoPlayer(source=url, ref=player),
        pn.Button("Play", on_press=lambda: player.current.play()),
    )
```

### use_back_handler

Intercept the system back action (the Android back button or back
gesture; Escape in the browser preview). Return `True` to consume the
event, `False` to pass it along:

```python
@pn.component
def Editor() -> pn.Node:
    dirty, set_dirty = pn.use_state(False)
    pn.use_back_handler(lambda: dirty)  # block back while dirty
    return pn.TextInput(on_change=lambda text: set_dirty(True))
```

iOS has no system back button, so the handler never fires there;
swipe-back is controlled by the navigation stack instead.

### use_animated_value

Create an [`AnimatedValue`][pythonnative.AnimatedValue] that's stable
across renders. Equivalent to wrapping `pn.Animated.Value(initial)` in
`use_memo(..., [])` but more discoverable:

```python
opacity = pn.use_animated_value(0.0)
pn.Animated.timing(opacity, to=1.0, duration=300).start()
```

### use_context

Read a value from the nearest `Provider` ancestor:

```python
Locale = pn.create_context("en")


@pn.component
def Greeting() -> pn.Node:
    locale = pn.use_context(Locale)
    return pn.Text("Hello" if locale == "en" else "Hola")
```

For theming specifically, prefer [`use_theme`][pythonnative.use_theme],
which returns a typed [`Theme`][pythonnative.Theme] and falls back to
the built-in light or dark theme when no provider is mounted, and
[`use_styles`][pythonnative.use_styles], which derives styles from the
theme once per theme. See [Styling](../guides/styling.md#themes).

### use_store

Read an app-wide [`Store`][pythonnative.Store], optionally through a
selector. The component re-renders only when the selected value
changes:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Cart:
    items: tuple[str, ...] = ()


cart = pn.Store(Cart())


@pn.component
def CartBadge() -> pn.Node:
    count = pn.use_store(cart, lambda state: len(state.items))
    return pn.Text(str(count))
```

See [Managing state](../guides/state.md) for when to use a store
instead of component state or context.

### Async hooks

Data fetching and priority scheduling have dedicated hooks, covered in
the [Async + data guide](../guides/async.md):

- [`use_resource`][pythonnative.use_resource]: start a fetch during
  render; reading a pending resource suspends until the nearest
  [`Suspense`][pythonnative.Suspense] boundary's fallback resolves.
- [`use_query`][pythonnative.use_query] /
  [`use_mutation`][pythonnative.use_mutation]: subscribe to an async
  fetcher / wrap an async mutator with loading and error state.
- [`use_transition`][pythonnative.use_transition] /
  [`use_deferred_value`][pythonnative.use_deferred_value]: mark
  expensive updates as low priority so urgent updates paint first.
- [`use_persisted_state`][pythonnative.use_persisted_state]:
  `use_state` backed by [`AsyncStorage`][pythonnative.AsyncStorage].

## Context and Provider

Share values through the component tree without passing props manually:

```python
UserName = pn.create_context("Guest", name="UserName")


@pn.component
def App() -> pn.Node:
    return UserName.Provider(UserProfile(), value="Alice")


@pn.component
def UserProfile() -> pn.Node:
    name = pn.use_context(UserName)
    return pn.Text(f"Welcome, {name}")
```

Like every other container, `Provider` takes its children positionally
and the value as the keyword-only `value=` argument.

Context is **reactive**: when a `Provider`'s value changes, every
component that read the context re-renders, even when a memoized
ancestor in between would otherwise skip its subtree. This matches
React's context propagation, so `@pn.memo` walls never trap stale
theme or session values. Each provider keeps a registry of the
components that read it, so a value change re-renders exactly those
consumers without walking the rest of the subtree.

## Batching state updates

State setters never render inline. Every setter call made during one
callback, effect, or task step is coalesced into a single render pass
scheduled on the application loop, on every host, including headless
tests:

```python
@pn.component
def Form() -> pn.Node:
    name, set_name = pn.use_state("")
    email, set_email = pn.use_state("")

    def on_submit() -> None:
        set_name("Alice")
        set_email("alice@example.com")
        # one re-render, after on_submit returns

    return pn.Column(
        pn.Text(f"{name} <{email}>"),
        pn.Button("Fill", on_press=on_submit),
    )
```

Automatic batching stops at an `await`: each step of a task is its own
batch. Use [`batch_updates`][pythonnative.scheduler.batch_updates] when
you want setters on both sides of an `await` to land in one pass:

```python
async def load() -> None:
    with pn.batch_updates():
        set_loading(True)
        data = await fetch_data()
        set_items(data)
        set_loading(False)
```

A component that keeps dirtying itself (an effect that sets state
unconditionally, or a setter called during its own render) is stopped
after fifty passes with `RuntimeError("Too many re-renders")`, raised
from that component and routed through the nearest
[`ErrorBoundary`][pythonnative.ErrorBoundary] (or the RedBox in dev
mode). In dev mode the reconciler also warns once per site for a
setter called after unmount, a setter called during render, and a
setter handed the identical `list`, `dict`, or `set` object it already
holds (in-place mutation never re-renders; replace the object).

[`use_color_scheme`][pythonnative.use_color_scheme] returns a
[`ColorScheme`][pythonnative.hooks.ColorScheme] (`"light"` or `"dark"`) and
re-renders when it changes.

## Memoizing function components

Wrap a function component with [`@pn.memo`][pythonnative.memo] to skip
its body when neither its props nor its internal state have changed:

```python
@pn.memo
@pn.component
def ExpensiveRow(label: str, value: int) -> pn.Node:
    return pn.Row(
        pn.Text(label, style={"flex": 1}),
        pn.Text(str(value)),
    )
```

When a `memo`'d component is reconciled, the reconciler compares the
new props against the previous props using shallow equality. If they
match and none of the component's `use_state` / `use_reducer` setters
have fired since the last render, the previously-rendered subtree is
reused and the component body is not re-executed. This is the
component-level equivalent of [`use_memo`][pythonnative.use_memo].

`memo` is typically used on pure, prop-driven leaves that re-render
frequently as part of a larger tree, e.g. rows inside a list whose
identity doesn't change between renders of the parent.

## Error boundaries

Wrap risky components in
[`ErrorBoundary`][pythonnative.ErrorBoundary] to catch render errors
and display a fallback UI. The fallback can receive the error and a
`reset` callable that remounts the original children, and `on_error`
hooks in error reporting:

```python
@pn.component
def App() -> pn.Node:
    return pn.ErrorBoundary(
        MyRiskyComponent(),
        fallback=lambda err, reset: pn.Column(
            pn.Text(f"Something went wrong: {err}"),
            pn.Button("Retry", on_press=reset),
        ),
        on_error=lambda err: log.exception(err),
    )
```

Without an error boundary, an exception during rendering propagates to
the screen host: in dev mode that shows the full-screen error overlay
(the RedBox); in production it crashes the screen. Error boundaries
catch errors during both initial mount and subsequent reconciliation.

## Custom hooks

Extract reusable stateful logic into plain functions:

```python
from collections.abc import Callable


def use_toggle(initial: bool = False) -> tuple[bool, Callable[[], None]]:
    value, set_value = pn.use_state(initial)
    toggle = pn.use_callback(lambda: set_value(lambda current: not current), [])
    return value, toggle


def use_text_input(initial: str = "") -> tuple[str, Callable[[str], None]]:
    text, set_text = pn.use_state(initial)
    return text, set_text
```

A custom hook's name starts with `use_`, which is how `pn lint`
recognizes it and allows hook calls inside it.

Use them in any component:

```python
@pn.component
def Settings() -> pn.Node:
    dark_mode, toggle_dark = use_toggle(False)

    return pn.Column(
        pn.Text("Settings", style={"font_size": 24, "bold": True}),
        pn.Row(
            pn.Text("Dark mode"),
            pn.Switch(value=dark_mode, on_change=lambda v: toggle_dark()),
        ),
    )
```

## Rules of hooks

1. Only call hooks inside `@pn.component` functions and custom hooks
   (functions named `use_...`).
2. Call hooks at the top level, not inside loops, conditions,
   comprehensions, `try` blocks, or nested functions, and not after an
   early `return`.
3. Hooks must be called in the same order on every render.

!!! tip "Why these rules?"
    Hooks are matched to per-component slots by call order. If a hook
    is conditional, the slot it lands in changes from render to render
    and the framework can't keep your state straight. Move the
    condition *inside* the hook, or compose the hook into a helper
    that the parent calls unconditionally.

Run `pn lint` to catch violations of these rules without running the
app. It reports a conditional or late hook (`PN101`), a hook outside a
component or custom hook (`PN102`), a missing effect, memo, or
callback dependency (`PN103`), and `key=` passed to a user component
(`PN104`). See the [Linting guide](../guides/linting.md).

In dev mode (`pn preview`, `pn run` with hot reload, or `PN_DEV=1`),
violating these rules raises a
[`HookOrderError`][pythonnative.HookOrderError] naming the component
and the offending hook position, instead of silently cross-wiring
state.

## Next steps

- See hooks in worked examples: [Counter](../examples/counter.md),
  [Forms](../examples/forms.md), [Lists](../examples/lists.md).
- Read about deferred effects in [Lifecycle](lifecycle.md).
- Browse the API: [Hooks](../api/hooks.md).
