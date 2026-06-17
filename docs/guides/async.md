# Async + data fetching

PythonNative is built on Python's `asyncio`. Animations, native
modules, alerts, the network client, and persistent storage are all
coroutines, and there are dedicated hooks
([`use_async_effect`][pythonnative.hooks.use_async_effect],
[`use_query`][pythonnative.hooks.use_query],
[`use_mutation`][pythonnative.hooks.use_mutation],
[`use_persisted_state`][pythonnative.storage.use_persisted_state])
that bridge those coroutines into the component lifecycle.

This guide walks through the moving parts and the patterns that come
out of them.

## The framework runtime

PythonNative starts a dedicated asyncio event loop on a daemon thread
named `"pn-asyncio"` the first time it's needed. Everything async in
the framework runs on this loop.

The two entry points you'll use directly are:

| Helper                                                                       | When to use                                                                 |
| ---------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| [`pn.run_async(coro)`][pythonnative.run_async]                               | Schedule a coroutine from sync code (a tap handler, a hook setup function). |
| [`pn.runtime.get_loop()`][pythonnative.runtime.get_loop]                     | Access the loop directly for interop with other asyncio libraries.          |
| [`pn.runtime.resolve_future`][pythonnative.runtime.resolve_future]           | Deliver a value to an `asyncio.Future` from any thread.                     |

You'll most often call `pn.run_async` from a sync button handler:

```python
import pythonnative as pn


@pn.component
def Toolbar():
    async def export():
        report = await build_report()
        await save_to_disk(report)

    return pn.Button("Export", on_click=lambda: pn.run_async(export()))
```

## Async side effects: `use_async_effect`

`use_async_effect(effect, deps)` is the async sibling of
[`use_effect`][pythonnative.use_effect]. `effect` is a zero-arg
``async`` callable; the framework schedules it on the runtime after
the native commit and cancels the in-flight coroutine whenever
``deps`` change or the component unmounts.

```python
@pn.component
def WelcomeBanner():
    visible, set_visible = pn.use_state(True)

    async def auto_dismiss():
        await asyncio.sleep(3.0)
        set_visible(False)

    pn.use_async_effect(auto_dismiss, [])

    return pn.Text("Welcome!") if visible else pn.Spacer()
```

If the user navigates away within 3 seconds, the sleep is cancelled
and `set_visible` never fires on the unmounted component.

## Loading data: `use_query`

`use_query(fetcher, deps)` subscribes to an async fetcher and re-renders
when its result changes. The return value is a frozen
[`QueryResult`][pythonnative.hooks.QueryResult] with `data`, `loading`,
`error`, and a stable `refetch` callable.

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
        pn.Button("Refresh", on_click=q.refetch),
    )
```

Cancellation falls through naturally: if the user navigates away mid-
fetch, the underlying coroutine is cancelled. If `user_id` changes,
the previous fetch is cancelled before the new one starts.

## Side-effecting actions: `use_mutation`

Use `use_mutation` for "do something then maybe refresh" patterns
(create, update, delete). It returns a `(state, mutate)` tuple where
`state` is a [`MutationState`][pythonnative.hooks.MutationState] (with
`loading`, `data`, `error`) and `mutate(*args, **kwargs)` triggers the
mutator.

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
            on_click=lambda: pn.run_async(submit()),
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
        on_click=lambda: set_theme("dark" if theme == "light" else "light"),
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

## How everything fits together

Putting the pieces side by side, here's the canonical "screen with
data + form + persistence + animations" shape:

```python
import pythonnative as pn


@pn.component
def PostsScreen(user_id: int):
    posts = pn.use_query(lambda: api.list_posts(user_id), [user_id])
    draft, set_draft = pn.use_persisted_state(f"draft.{user_id}", "")
    state, create = pn.use_mutation(api.create_post)

    opacity = pn.use_animated_value(0.0)
    pn.use_async_effect(
        lambda: pn.Animated.timing(opacity, to=1.0, duration=300),
        [],
    )

    async def submit():
        if not draft.strip():
            return
        await create({"author_id": user_id, "body": draft})
        set_draft("")
        posts.refetch()

    return pn.Animated.View(
        pn.TextInput(value=draft, on_change=set_draft),
        pn.Button(
            "Post" if not state.loading else "Posting…",
            on_click=lambda: pn.run_async(submit()),
        ),
        pn.FlatList(
            posts.data or [],
            render_item=lambda p, _: pn.Text(p["body"]),
        ),
        style={"opacity": opacity, "padding": 16, "spacing": 8},
    )
```

Each piece (fetch, animation, persistence, mutation) is its own
hook with its own lifecycle, and `asyncio` is the glue.
