# Async + data fetching

PythonNative is **async-first**. The whole framework (rendering,
effects, native modules, animations, timers) shares a single `asyncio`
event loop that runs on the platform's main thread, components
themselves can be `async def`, and [`Suspense`][pythonnative.Suspense]
turns "waiting for data" into a declarative UI state instead of
hand-rolled loading flags.

This guide walks through the moving parts and the patterns that come
out of them.

## The framework runtime: one loop, on the main thread

The framework loop lives on the platform's main thread, interleaved
with UIKit / the Android Looper as a guest: whenever async work is
scheduled, PythonNative asks the platform to pump the loop on the next
main-queue turn. There is no background runtime thread, so coroutines
can read component state and (through the commit) native views without
any cross-thread marshaling or locks.

The entry points you'll use directly:

| Helper                                                              | When to use                                                                 |
| ------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| [`pn.run_async(coro)`][pythonnative.run_async]                      | Schedule a coroutine from sync code (a tap handler, a hook setup function). |
| [`pn.run_blocking(coro)`][pythonnative.runtime.run_blocking]        | Drive a coroutine to completion from a plain script or a test.              |
| [`pn.runtime.get_loop()`][pythonnative.runtime.get_loop]            | Access the loop directly for interop with other asyncio libraries.          |
| [`pn.runtime.resolve_future`][pythonnative.runtime.resolve_future]  | Deliver a value to an `asyncio.Future` from any thread.                     |

You'll most often call `pn.run_async` from a sync button handler:

```python
import pythonnative as pn


@pn.component
def Toolbar():
    async def export():
        report = await build_report()
        await save_to_disk(report)

    return pn.Button("Export", on_press=lambda: pn.run_async(export()))
```

## Async components + Suspense

A component body may be an `async def`. The body awaits whatever it
needs and returns its element tree; while an await is pending, the
render **suspends** and the nearest
[`Suspense`][pythonnative.Suspense] boundary shows its fallback:

```python
@pn.component
async def Profile(user_id: str):
    user = await api.fetch_user(user_id)
    return pn.Column(
        pn.Text(user["name"]),
        pn.Text(user["bio"]),
    )


@pn.component
def ProfileScreen():
    return pn.Suspense(
        Profile(user_id="42"),
        fallback=pn.ActivityIndicator(),
    )
```

No `loading` flag, no conditional render, no effect that copies data
into state. Two timing rules, matching React:

- **Initial mount**: the fallback shows until the content is ready.
- **Updates**: a component that's already on screen and suspends again
  (its inputs changed) keeps its previous content visible and
  re-renders when the new data arrives; there's no fallback flash.

Boundaries nest: each `Suspense` covers exactly the subtree it wraps,
so one slow widget doesn't blank the whole screen. A boundary without
a `fallback` is transparent and lets the suspension propagate to the
next boundary up.

Awaits on already-resolved values complete inline during the render
pass, so a re-render of an async component whose data is cached costs
no event-loop round trips.

## Fetch-during-render: `use_resource`

`use_resource(fetcher, deps)` starts an async fetch **during render**
(not after commit, so there's no mount-then-fetch waterfall) and
caches the resulting [`Resource`][pythonnative.Resource] until `deps`
change:

```python
@pn.component
def UserCard(user_id: str):
    resource = pn.use_resource(lambda: api.get_user(user_id), [user_id])
    user = resource.read()  # suspends while pending
    return pn.Text(user["name"])
```

Consume a resource two ways, with identical semantics:

- `resource.read()` in a regular component: returns the value when
  ready, re-raises the fetcher's error (so an enclosing
  [`ErrorBoundary`][pythonnative.ErrorBoundary] catches failures),
  and suspends the render while pending.
- `await resource` inside an `async def` component.

Because results are cached per component instance, re-renders resolve
instantly; only genuinely new data (a `deps` change) refetches, and
the stale in-flight fetch is cancelled first.

For module-level preloading (start fetching before a screen mounts),
use [`pn.start_resource`][pythonnative.start_resource], the non-hook
constructor.

## Code splitting: `lazy`

[`pn.lazy(loader)`][pythonnative.lazy] defers loading a component
until its first render. The loader runs once; renders suspend until
it resolves:

```python
Chart = pn.lazy(lambda: __import__("app.chart", fromlist=["Chart"]).Chart)


@pn.component
def Dashboard():
    return pn.Suspense(
        Chart(points=[1, 2, 3]),
        fallback=pn.ActivityIndicator(),
    )
```

Synchronous loaders (a deferred `import`) resolve immediately and
never suspend; `async def` loaders can pull code or data from
anywhere.

## Async side effects: `use_effect` with `async def`

[`use_effect`][pythonnative.use_effect] accepts coroutine callbacks
directly. The coroutine runs as a task on the framework loop after
the commit, and the task is **cancelled automatically** whenever
`deps` change or the component unmounts:

```python
@pn.component
def WelcomeBanner():
    visible, set_visible = pn.use_state(True)

    async def auto_dismiss():
        await asyncio.sleep(3.0)
        set_visible(False)

    pn.use_effect(auto_dismiss, [])

    return pn.Text("Welcome!") if visible else pn.Spacer()
```

If the user navigates away within 3 seconds, the sleep is cancelled
and `set_visible` never fires on the unmounted component. An async
effect may also return a callable, which runs as its cleanup:

```python
async def subscribe():
    connection = await open_socket()
    return connection.close  # cleanup

pn.use_effect(subscribe, [])
```

## Keeping the UI responsive: `use_transition` and `use_deferred_value`

State updates are urgent by default: they render synchronously so
taps and typing feel immediate. When an update drives *expensive*
work (filtering a large list, re-rendering a chart), mark it as a
**transition** so urgent updates queued in the meantime render first:

```python
@pn.component
def Search():
    query, set_query = pn.use_state("")
    submitted, set_submitted = pn.use_state("")
    is_pending, start_transition = pn.use_transition()

    def on_change(text):
        set_query(text)  # urgent: the input updates immediately
        start_transition(lambda: set_submitted(text))  # deferred

    return pn.Column(
        pn.TextInput(value=query, on_change=on_change),
        pn.ActivityIndicator() if is_pending else Results(query=submitted),
    )
```

`is_pending` is `True` from the moment `start_transition` is called
until the deferred render commits, which is exactly when to show a
lightweight busy hint.

[`use_deferred_value`][pythonnative.use_deferred_value] is the
value-shaped variant: it returns a copy of its argument that lags
behind during bursts and catches up in a transition-priority render
when things go quiet. Pass the deferred copy to the expensive subtree
and the urgent part of the UI stays snappy.

## Loading data with state flags: `use_query`

When you'd rather manage loading state explicitly (or need `refetch`),
`use_query(fetcher, deps)` subscribes to an async fetcher and
re-renders when its result changes. The return value is a frozen
[`QueryResult`][pythonnative.hooks.QueryResult] with `data`,
`loading`, `error`, and a stable `refetch` callable:

```python
@pn.component
def UserCard(user_id: int):
    q = pn.use_query(lambda: api.get_user(user_id), [user_id])

    if q.loading and q.data is None:
        return pn.Text("Loading…")
    if q.error:
        return pn.Text(f"Error: {q.error}")
    return pn.Column(
        pn.Text(q.data["name"]),
        pn.Button("Refresh", on_press=q.refetch),
    )
```

Rule of thumb: reach for `use_resource` + `Suspense` when a loading
state is all you need (the boundary owns it), and `use_query` when
the component wants to keep stale data on screen with a refresh
affordance.

## Side-effecting actions: `use_mutation`

Use `use_mutation` for "do something then maybe refresh" patterns
(create, update, delete). It returns a `(state, mutate)` tuple where
`state` is a [`MutationState`][pythonnative.hooks.MutationState] (with
`loading`, `data`, `error`) and `mutate(*args, **kwargs)` triggers the
mutator:

```python
@pn.component
def NewPostForm():
    title, set_title = pn.use_state("")
    state, save = pn.use_mutation(api.create_post)

    async def submit():
        await save(title)              # await the result
        set_title("")
        await pn.Alert.show("Posted!")

    return pn.Column(
        pn.TextInput(value=title, on_change=set_title),
        pn.Button(
            "Save" if not state.loading else "Saving…",
            on_press=lambda: pn.run_async(submit()),
        ),
        pn.Text(str(state.error)) if state.error else pn.Spacer(),
    )
```

The handle returned by `mutate(...)` is a
[`MutationCall`][pythonnative.hooks.MutationCall], awaitable,
cancellable, and safe to ignore if you only care about the state
transitions.

## HTTP requests: `pn.fetch`

A small, dependency-free coroutine wrapper around `urllib`:

```python
resp = await pn.fetch(
    "https://api.example.com/posts",
    method="POST",
    body={"title": "Hello"},
    headers={"Authorization": f"Bearer {token}"},
)
resp.raise_for_status()
data = resp.json()
```

`resp.text()`, `resp.json()`, and `resp.content` cover the common
cases. For multipart uploads, HTTP/2, or streaming, integrate
`httpx` / `aiohttp` directly; `pn.fetch` deliberately stays small.

## Key/value persistence: `AsyncStorage`

[`pn.AsyncStorage`][pythonnative.storage.AsyncStorage] is the platform
key/value store (`NSUserDefaults` on iOS, `SharedPreferences` on
Android, a local JSON file in desktop tests). All operations are
coroutines:

```python
await pn.AsyncStorage.set("token", token)
token = await pn.AsyncStorage.get("token")

await pn.AsyncStorage.set_json("user", user.to_dict())
restored = await pn.AsyncStorage.get_json("user")
```

`set_json` / `get_json` add a JSON encode/decode step so you can
round-trip lists, dicts, and primitives.

## Persisted component state: `use_persisted_state`

If you just want `use_state` that survives app restarts, reach for
`use_persisted_state(key, initial)`. It looks like `use_state` but
loads the previous value on mount and writes every update back to
`AsyncStorage`:

```python
@pn.component
def ThemeToggle():
    theme, set_theme = pn.use_persisted_state("settings.theme", "light")
    return pn.Button(
        f"Theme: {theme}",
        on_press=lambda: set_theme("dark" if theme == "light" else "light"),
    )
```

The initial render returns the `initial` fallback; the async load
triggers a re-render with the stored value as soon as it lands.

## Awaitable alerts

[`pn.Alert.confirm`][pythonnative.alerts.Alert.confirm] and
[`pn.Alert.choose`][pythonnative.alerts.Alert.choose] are coroutines
that resolve to the user's choice:

```python
if await pn.Alert.confirm("Delete this item?"):
    await delete_item()

photo_source = await pn.Alert.choose(
    "Photo source",
    options=["Camera", "Gallery"],
    cancel_label="Cancel",
)
if photo_source == "Camera":
    path = await pn.Camera.take_photo()
```

For a fire-and-forget single-button notice, use the sync
[`pn.Alert.show`][pythonnative.alerts.Alert.show]:

```python
pn.Alert.show("Saved!")
```

## Testing async code

Because the loop is a guest on the calling thread, synchronous tests
drive it explicitly:

```python
from pythonnative.runtime import drain, run_blocking

def test_load():
    rec.mount(pn.Suspense(Profile(user_id="42"), fallback=pn.Text("…")))
    drain()            # pump the loop until it goes idle
    rec.flush_dirty()  # commit renders queued by async completions

def test_storage():
    assert run_blocking(pn.AsyncStorage.get("token")) is None
```

`async` tests can just `await` framework APIs directly;
[`get_loop`][pythonnative.runtime.get_loop] adopts the already-running
loop.

## How everything fits together

Putting the pieces side by side, here's the canonical "screen with
data + form + persistence + animations" shape:

```python
import pythonnative as pn


@pn.component
async def PostList(user_id: int, version: int):
    posts = await pn.use_resource(lambda: api.list_posts(user_id), [user_id, version])
    return pn.FlatList(
        posts,
        render_item=lambda p, _: pn.Text(p["body"]),
    )


@pn.component
def PostsScreen(user_id: int):
    draft, set_draft = pn.use_persisted_state(f"draft.{user_id}", "")
    state, create = pn.use_mutation(api.create_post)
    version, set_version = pn.use_state(0)

    opacity = pn.use_animated_value(0.0)
    pn.use_effect(
        lambda: pn.Animated.timing(opacity, to=1.0, duration=300),
        [],
    )

    async def submit():
        if not draft.strip():
            return
        await create({"author_id": user_id, "body": draft})
        set_draft("")
        set_version(version + 1)  # refetch the list resource

    return pn.Animated.View(
        pn.TextInput(value=draft, on_change=set_draft),
        pn.Button(
            "Post" if not state.loading else "Posting…",
            on_press=lambda: pn.run_async(submit()),
        ),
        pn.Suspense(
            PostList(user_id=user_id, version=version),
            fallback=pn.ActivityIndicator(),
        ),
        style={"opacity": opacity, "padding": 16, "spacing": 8},
    )
```

Each piece (fetch, animation, persistence, mutation) is its own
hook with its own lifecycle, and `asyncio` is the glue, running right
on the UI thread.
