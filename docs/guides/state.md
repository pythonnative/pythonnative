# Managing state

State in a PythonNative app lives in one of four places, depending on
who needs it and how long it has to last:

| Where | Who reads it | How long it lasts | Tool |
| --- | --- | --- | --- |
| A component | That component and the props it passes down | While the component is mounted | [`use_state`][pythonnative.use_state], [`use_reducer`][pythonnative.use_reducer] |
| A context | Any descendant of a provider | While the provider is mounted | [`create_context`][pythonnative.create_context], [`use_context`][pythonnative.use_context] |
| A store | Any component, and code outside the tree | For the life of the process | [`pn.Store`][pythonnative.Store], [`use_store`][pythonnative.use_store] |
| Device storage | Any of the above, after a restart | Across launches | [`use_persisted_state`][pythonnative.use_persisted_state], [`AsyncStorage`][pythonnative.AsyncStorage] |

Start with the first row and move down only when you need to. Most
state belongs to a single component.

## Component state

[`use_state`][pythonnative.use_state] gives a component a value and a
setter. Calling the setter schedules a re-render with the new value:

```python
import pythonnative as pn


@pn.component
def Counter(initial: int = 0) -> pn.Node:
    count, set_count = pn.use_state(initial)
    return pn.Row(
        pn.Button("-", on_press=lambda: set_count(lambda c: c - 1)),
        pn.Text(str(count)),
        pn.Button("+", on_press=lambda: set_count(lambda c: c + 1)),
        style={"gap": 12, "align_items": "center"},
    )
```

Pass a function to the setter (`set_count(lambda c: c + 1)`) when the
next value depends on the previous one; it always sees the latest
value, even when several updates are batched together.

When one action changes several related values, collect the
transitions in a reducer with [`use_reducer`][pythonnative.use_reducer].
The reducer is a plain function, so it's easy to test on its own:

```python
from dataclasses import dataclass, replace
from typing import Literal

import pythonnative as pn


@dataclass(frozen=True)
class Form:
    email: str = ""
    submitting: bool = False
    error: str | None = None


Action = tuple[Literal["email"], str] | tuple[Literal["submit"]] | tuple[Literal["fail"], str]


def reduce(state: Form, action: Action) -> Form:
    if action[0] == "email":
        return replace(state, email=action[1], error=None)
    if action[0] == "submit":
        return replace(state, submitting=True)
    return replace(state, submitting=False, error=action[1])


@pn.component
def SignUp() -> pn.Node:
    form, dispatch = pn.use_reducer(reduce, Form())
    return pn.Column(
        pn.TextInput(value=form.email, on_change=lambda text: dispatch(("email", text))),
        pn.Text(form.error or "", style={"color": "#FF3B30"}),
        pn.Button("Sign up", on_press=lambda: dispatch(("submit",)), disabled=form.submitting),
        style={"gap": 8, "padding": 16},
    )
```

Keep state values immutable (frozen dataclasses, tuples, and fresh
dicts) and replace them rather than mutating them. The framework
decides whether to re-render by comparing the old and new values, so a
mutated object looks unchanged.

To share component state with a few children, pass the value and its
setter down as props. That's usually enough.

## Sharing state with context

When many components at different depths need the same value (the
signed-in user, a feature flag, a repository object), passing it
through every layer gets noisy. A context delivers a value to a whole
subtree:

```python
from dataclasses import dataclass

import pythonnative as pn


@dataclass(frozen=True)
class User:
    name: str


UserContext = pn.create_context(User("guest"), name="User")


@pn.component
def Greeting() -> pn.Node:
    user = pn.use_context(UserContext)
    return pn.Text(f"Hello, {user.name}")


@pn.component
def App() -> pn.Node:
    user, set_user = pn.use_state(User("ada"))
    return UserContext.Provider(
        pn.Column(Greeting(), pn.Button("Sign out", on_press=lambda: set_user(User("guest")))),
        value=user,
    )
```

Components that call `use_context` re-render when the provider's value
changes, even if a memoized ancestor skipped. The provider tracks its
consumers directly, so a change costs work proportional to the number
of consumers, not the size of the subtree.

Context is best for values that change rarely or that the whole subtree
reads. Every consumer re-renders on every change, so a frequently
changing value with many readers that each need one field is better
served by a store.

## App state with `pn.Store`

A [`Store`][pythonnative.Store] holds one immutable value outside the
component tree and notifies subscribers when it's replaced. Components
read it with [`use_store`][pythonnative.use_store], optionally through
a selector, and re-render only when the selected value changes:

```python
from dataclasses import dataclass, replace

import pythonnative as pn


@dataclass(frozen=True)
class Todo:
    id: int
    title: str
    done: bool = False


@dataclass(frozen=True)
class TodoState:
    todos: tuple[Todo, ...] = ()
    filter: str = ""


todos = pn.Store(TodoState(), name="todos")


def add_todo(title: str) -> None:
    todos.update(
        lambda state: replace(state, todos=(*state.todos, Todo(id=len(state.todos) + 1, title=title)))
    )


def toggle(todo_id: int) -> None:
    todos.update(
        lambda state: replace(
            state,
            todos=tuple(replace(t, done=not t.done) if t.id == todo_id else t for t in state.todos),
        )
    )


@pn.component
def RemainingCount() -> pn.Node:
    remaining = pn.use_store(todos, lambda state: sum(not t.done for t in state.todos))
    return pn.Text(f"{remaining} left")


@pn.component
def TodoRow(todo: Todo) -> pn.Node:
    return pn.Checkbox(value=todo.done, label=todo.title, on_change=lambda _: toggle(todo.id))


@pn.component
def TodoList() -> pn.Node:
    items = pn.use_store(todos, lambda state: state.todos)
    return pn.Column(*(TodoRow(todo).with_key(todo.id) for todo in items))


@pn.component
def App() -> pn.Node:
    return pn.Column(
        RemainingCount(),
        TodoList(),
        pn.Button("Add", on_press=lambda: add_todo("New task")),
        style={"gap": 8, "padding": 16},
    )
```

- **Actions are plain functions.** `add_todo` and `toggle` call
  `store.update(...)` and can be imported anywhere: a button handler, a
  network callback, or a test.
- **Selectors keep re-renders targeted.** `RemainingCount` re-renders
  only when the count changes, not when a title is edited. The selector
  may be a fresh lambda on every render.
- **Writes apply immediately.** `store.get()` returns the new value as
  soon as `set` or `update` returns, on any thread. Subscribed
  components re-render on the application thread like any state update.
- **Unchanged values don't notify.** Setting a value equal to the
  current one does nothing, under the same equality rule the
  reconciler uses.

The `Store` API is small:

| Method | Does |
| --- | --- |
| `get()` | Returns the current value |
| `set(value)` | Replaces the value |
| `update(fn)` | Replaces the value with `fn(current)`, atomically with respect to other writers |
| `subscribe(listener)` | Calls `listener()` after each change; returns an unsubscribe function |
| `batch()` | A context manager that coalesces the writes inside it into one notification |

```python
with todos.batch():
    add_todo("Buy milk")
    add_todo("Walk the dog")
# subscribers hear about both additions once
```

Define stores at module level for app-wide state, or create one per
object you own (for example, one per open document) and hand it down
through a context. Because the value is replaced rather than mutated,
tests can drive a store without rendering anything:

```python
def test_toggle() -> None:
    todos.set(TodoState(todos=(Todo(id=1, title="a"),)))
    toggle(1)
    assert todos.get().todos[0].done
```

For an external source that isn't a `Store` (a native module's event
stream, a third-party client), use
[`use_subscription`][pythonnative.use_subscription], the primitive
`use_store` is built on. Bound methods compare equal when they belong
to the same object, so passing `client.subscribe` directly doesn't
resubscribe on every render.

## Persisting state across launches

[`use_persisted_state`][pythonnative.use_persisted_state] is
`use_state` backed by [`AsyncStorage`][pythonnative.AsyncStorage]:

```python
MODES = ["system", "light", "dark"]


@pn.component
def AppearancePicker() -> pn.Node:
    mode, set_mode = pn.use_persisted_state("settings.appearance", "system")
    return pn.SegmentedControl(
        segments=MODES,
        selected_index=MODES.index(mode),
        on_change=lambda index: set_mode(MODES[index]),
    )
```

- The first render returns `initial`. The stored value loads in the
  background and re-renders the component when it arrives.
- Each committed change is written from an effect after the commit, so
  a transition that replays updaters doesn't write twice.
- A value set before loading finishes wins: the stored value is
  discarded and the new one is persisted.
- Values must be JSON-serializable. Use a stable, namespaced key such
  as `"settings.theme"`.

To persist a store, load its value once at startup and write it back
from a subscriber:

```python
from dataclasses import asdict


async def load_todos() -> None:
    saved = await pn.AsyncStorage.get_json("todos")
    if saved is not None:
        todos.set(TodoState(todos=tuple(Todo(**t) for t in saved)))


def save_todos() -> None:
    pn.run_async(pn.AsyncStorage.set_json("todos", [asdict(t) for t in todos.get().todos]))


todos.subscribe(save_todos)


@pn.component
def PersistentApp() -> pn.Node:
    pn.use_effect(load_todos, [])
    return App()
```

`use_effect` accepts an `async def` callback and cancels it if the
component unmounts first.

For secrets such as tokens, use
[`SecureStore`][pythonnative.SecureStore] instead of `AsyncStorage`.

## Choosing a tool

- **Only one component uses it:** `use_state`, or `use_reducer` when
  the transitions are involved.
- **A parent and a few children use it:** keep it in the parent and
  pass it down as props.
- **A subtree uses it, and it changes rarely:** a context.
- **Many unrelated components use it, code outside the tree changes
  it, or components need different slices of it:** a `Store` with
  selectors.
- **It must survive a restart:** `use_persisted_state` for a component
  value; a `Store` with a saving subscriber for app state.
- **It comes from the server:** [`use_query`][pythonnative.use_query]
  or [`use_resource`][pythonnative.use_resource]; see
  [Async + data](async.md). Keep server data out of stores unless you
  need to edit it locally.
- **It describes where the user is:** the navigation state. Screens
  receive their params as arguments; see [Navigation](navigation.md).

## Next steps

- Learn how hooks keep their state: [Hooks](../concepts/hooks.md).
- Check the rules of hooks automatically with [`pn lint`](linting.md).
- Browse the API: [Store](../api/store.md), [Hooks](../api/hooks.md),
  and [Storage](../api/storage.md).
