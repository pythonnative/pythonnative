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
def Greeting(name: str = "World"):
    return pn.Text(f"Hello, {name}!", style={"font_size": 20})
```

Use it like any other component:

```python
@pn.component
def MyPage():
    return pn.Column(
        Greeting(name="Alice"),
        Greeting(name="Bob"),
        style={"spacing": 12},
    )
```

## Hooks

Hooks let function components manage state and side effects. They must be called at the top level of a `@pn.component` function (not inside loops or conditions).

### use_state

Local component state. Returns `(value, setter)`.

```python
@pn.component
def Counter(initial: int = 0):
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
def reducer(state, action):
    if action == "increment":
        return state + 1
    if action == "decrement":
        return state - 1
    if action == "reset":
        return 0
    return state

@pn.component
def Counter():
    count, dispatch = pn.use_reducer(reducer, 0)

    return pn.Column(
        pn.Text(f"Count: {count}"),
        pn.Row(
            pn.Button("-", on_press=lambda: dispatch("decrement")),
            pn.Button("+", on_press=lambda: dispatch("increment")),
            pn.Button("Reset", on_press=lambda: dispatch("reset")),
            style={"spacing": 8},
        ),
    )
```

The reducer receives the current state and an action, and returns the new state. Actions can be any value (strings, dicts, etc.). The component only re-renders when the reducer returns a different state.

### use_effect

Run side effects **after** the native view tree is committed. The effect function may return a cleanup callable.

```python
@pn.component
def Timer():
    seconds, set_seconds = pn.use_state(0)

    async def tick():
        import asyncio
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

Dependency control:

- `pn.use_effect(fn, None)`: run on every render.
- `pn.use_effect(fn, [])`: run on mount only.
- `pn.use_effect(fn, [a, b])`: run when `a` or `b` change.

### use_layout_effect

Like [`use_effect`][pythonnative.use_effect], but runs synchronously
inside the commit, after native mutations and the layout pass and
before passive effects. Use it to read a committed frame from a ref or
to issue an imperative command (like scrolling a list into position)
before the user sees the new frame:

```python
@pn.component
def Chat(messages):
    list_ref = pn.use_ref()

    def scroll_to_bottom():
        if list_ref.current is not None:
            list_ref.current.scroll_to_end(animated=False)

    pn.use_layout_effect(scroll_to_bottom, [len(messages)])
    return pn.FlatList(data=messages, render_item=Bubble, ref=list_ref)
```

Prefer `use_effect` for everything else; layout effects block the
commit, so heavy work here delays the frame.

### use_navigation

Access navigation from any screen. Returns the
[`Navigation`][pythonnative.Navigation] handle for the current route,
with `.navigate()`, `.push()`, `.go_back()`, `.set_options()`,
`.add_listener()`, and more.

```python
@pn.component
def HomeScreen():
    nav = pn.use_navigation()

    return pn.Column(
        pn.Text("Home", style={"font_size": 24}),
        pn.Button(
            "Go to Details",
            on_press=lambda: nav.navigate("Detail", id=42),
        ),
        style={"spacing": 12, "padding": 16},
    )

@pn.component
def DetailScreen():
    nav = pn.use_navigation()
    item_id = pn.use_route().params.get("id", 0)

    return pn.Column(
        pn.Text(f"Detail #{item_id}", style={"font_size": 20}),
        pn.Button("Back", on_press=nav.go_back),
        style={"spacing": 12, "padding": 16},
    )
```

See the [Navigation guide](../guides/navigation.md) for full details.

### use_route

Read the current [`Route`][pythonnative.navigation.Route]: its
`name`, `params`, and stable `key`:

```python
@pn.component
def DetailScreen():
    route = pn.use_route()
    item_id = route.params.get("id", 0)
    return pn.Text(f"Detail #{item_id}")
```

### use_focus_effect

Like [`use_effect`][pythonnative.use_effect] but only runs when the
screen is focused. Useful for refreshing data when navigating back to
a screen:

```python
@pn.component
def FeedScreen():
    items, set_items = pn.use_state([])
    pn.use_focus_effect(lambda: load_items(set_items), [])
    return pn.FlatList(data=items, render_item=lambda item, i: pn.Text(item))
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

Pass a ref to a built-in element via the `ref=` prop and the
reconciler populates `ref.current` with the underlying native view
after commit (and clears it on unmount). The layout pass also mirrors
the committed frame, so Python code can read measured geometry without
a native round-trip:

```python
box_ref = pn.use_ref()
pn.View(ref=box_ref, style={"height": 48})
# after commit: box_ref.current is the native view
```

### use_imperative_handle

Composite components that accept a `ref` prop can publish a curated
controller object on `ref.current` instead of a raw native view.
[`FlatList`][pythonnative.FlatList] does this out of the box: it
installs a [`ListController`][pythonnative.ListController] with
`scroll_to_offset`, `scroll_to_index`, and `scroll_to_end` methods.
Your own components use [`use_imperative_handle`][pythonnative.use_imperative_handle]:

```python
@pn.component
def VideoPlayer(source, ref=None):
    pn.use_imperative_handle(ref, lambda: PlayerController(...), [source])
    return pn.View(...)

@pn.component
def Screen():
    player = pn.use_ref()
    return pn.Column(
        VideoPlayer(source=url, ref=player),
        pn.Button("Play", on_press=lambda: player.current.play()),
    )
```

### use_back_handler

Intercept the system back action (the Android hardware back button and
predictive back gesture; Escape in the desktop preview). Return `True`
to consume the event, `False` to pass it along:

```python
@pn.component
def Editor():
    dirty, set_dirty = pn.use_state(False)
    pn.use_back_handler(lambda: dirty)  # block back while dirty
    ...
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
def Greeting():
    locale = pn.use_context(Locale)
    return pn.Text("Hello" if locale == "en" else "Hola")
```

For theming specifically, prefer [`use_theme`][pythonnative.use_theme],
which returns a typed [`Theme`][pythonnative.Theme] and falls back to
the built-in light or dark theme when no provider is mounted.

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
user_context = pn.create_context({"name": "Guest"})

@pn.component
def App():
    return user_context.Provider({"name": "Alice"}, UserProfile())

@pn.component
def UserProfile():
    user = pn.use_context(user_context)
    return pn.Text(f"Welcome, {user['name']}")
```

Context is **reactive**: when a `Provider`'s value changes, every
component that read the context re-renders, even when a memoized
ancestor in between would otherwise skip its subtree. This matches
React's context propagation, so `@pn.memo` walls never trap stale
theme or session values.

## Batching state updates

By default, each state setter call triggers a re-render. When you
need to update multiple pieces of state at once, use
[`batch_updates`][pythonnative.scheduler.batch_updates] to coalesce them into a
single render pass:

```python
@pn.component
def Form():
    name, set_name = pn.use_state("")
    email, set_email = pn.use_state("")

    def on_submit():
        with pn.batch_updates():
            set_name("Alice")
            set_email("alice@example.com")
        # single re-render here

    return pn.Column(
        pn.Text(f"{name} <{email}>"),
        pn.Button("Fill", on_press=on_submit),
    )
```

State updates triggered by effects during a render pass are
automatically batched; the framework drains any pending re-renders
after effect flushing completes, so you don't need `batch_updates()`
inside effects.

## Memoizing function components

Wrap a function component with [`@pn.memo`][pythonnative.memo] to skip
its body when neither its props nor its internal state have changed:

```python
@pn.memo
@pn.component
def ExpensiveRow(label: str, value: int):
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
def App():
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
def use_toggle(initial: bool = False):
    value, set_value = pn.use_state(initial)
    toggle = pn.use_callback(lambda: set_value(not value), [value])
    return value, toggle

def use_text_input(initial: str = ""):
    text, set_text = pn.use_state(initial)
    return text, set_text
```

Use them in any component:

```python
@pn.component
def Settings():
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

1. Only call hooks inside `@pn.component` functions.
2. Call hooks at the top level, not inside loops, conditions, or
   nested functions.
3. Hooks must be called in the same order on every render.

!!! tip "Why these rules?"
    Hooks are matched to per-component slots by call order. If a hook
    is conditional, the slot it lands in changes from render to render
    and the framework can't keep your state straight. Move the
    condition *inside* the hook, or compose the hook into a helper
    that the parent calls unconditionally.

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
