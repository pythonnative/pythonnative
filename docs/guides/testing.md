# Testing

PythonNative is built so that the bulk of your application logic can
be tested without a device or simulator. The reconciler talks to
native widgets exclusively through the batched mutation protocol (see
[Native views](../concepts/native-views.md)); `pythonnative.testing`
swaps in an in-memory backend so a render produces a tree of plain
Python objects that `pytest` can introspect, and gives you Testing
Library-style queries to do it.

## What to test

- **Components**: render them, find things by text or `test_id`, fire
  events, assert on what's visible.
- **Hooks**: drive state transitions with
  [`render_hook`][pythonnative.testing.render_hook].
- **Navigation flows**: render the whole app and press through it.
- **Reducers and helpers**: pure functions; test them as you would any
  other Python code.

What *not* to test (or to test sparingly): the platform handler
implementations themselves. Those run only on the device and are
covered by the Maestro E2E suite (`tests/e2e/`).

## Rendering a component

[`render`][pythonnative.testing.render] mounts an element and returns a
[`RenderResult`][pythonnative.testing.RenderResult]:

```python
import pythonnative as pn
from pythonnative.testing import render


@pn.component
def Counter():
    count, set_count = pn.use_state(0)
    return pn.Column(
        pn.Text(f"Count: {count}"),
        pn.Button("+", on_press=lambda: set_count(count + 1)),
    )


def test_counter_increments():
    result = render(Counter())
    result.press(result.get_by_text("+"))
    assert result.get_by_text("Count: 1")
```

`press` (and the general `fire(target, "on_event", *args)`) dispatch
the event exactly as a native listener would, then settle: pending
re-renders, effects, and async work run before the call returns, so
the next line can assert on the new tree.

### Queries

Queries mirror Testing Library:

| Query | Returns |
|---|---|
| `get_by_text`, `get_by_test_id`, `get_by_label`, `get_by_type` | exactly one view, or raises `LookupError` with the tree dumped in the message |
| `query_by_*` | the view or `None` |
| `get_all_by_*` | every match |

Matchers are exact strings, compiled regexes, or predicates;
`get_by_text("Count", exact=False)` matches substrings. Views inside a
`display: "none"` subtree (inactive tabs, screens beneath the top of a
stack) are skipped unless you pass `hidden=True`, which is how you
assert that a hidden screen kept its state.

Each match is a [`FakeView`][pythonnative.testing.FakeView] with
`type_name`, `props`, `children`, `parent`, `frame`, and `text`.
`result.text()` lists the visible strings in order, and
`result.dump()` prints the tree when a test is confusing.

### Other helpers

- `change_text(input, "value")` fires `on_change_text`.
- `back()` simulates the system back action and returns whether a
  handler consumed it.
- `rerender(element)` reconciles new root props from outside the tree.
- `settle()` pumps the framework loop until async work is done.
- `unmount()` tears down and runs effect cleanups; `RenderResult` is
  also a context manager.

## Testing hooks in isolation

```python
from pythonnative.testing import render_hook


def use_toggle(initial=False):
    on, set_on = pn.use_state(initial)
    return on, lambda: set_on(not on)


def test_use_toggle():
    hook = render_hook(use_toggle, True)
    assert hook.current[0] is True
    hook.act(lambda: hook.current[1]())
    assert hook.current[0] is False
    assert hook.render_count == 2
```

`hook.rerender(*args, **kwargs)` re-renders with new arguments, which
is how you test hooks that react to prop changes.

## Testing navigation

Navigators render in Python when no host is present, so a whole flow
fits in one test:

```python
def test_home_to_detail_and_back():
    result = render(App())
    result.press(result.get_by_text("Open item 42"))
    assert result.get_by_text("Detail #42")
    assert result.back() is True
    assert result.get_by_text("Home")
```

To test what a root stack asks the *platform* to do, render under a
[`FakeHost`][pythonnative.testing.FakeHost]. It records `pushed`,
`popped`, `replaced`, `resets`, and `options`, exposes the latest
`title`, and lets you simulate focus changes with `set_focused`:

```python
from pythonnative.testing import FakeHost


def test_detail_pushes_native_screen():
    host = FakeHost()
    result = render(App(), host=host)
    result.press(result.get_by_text("Open item 42"))
    state, options = host.pushed[0]
    assert [r["name"] for r in state["routes"]] == ["Home", "Detail"]
    assert options["title"] == "Item 42"
```

Booting a screen "mid-stack" the way a pushed native screen does is
`FakeHost(initial_state=state.to_dict())`.

## Testing layouts

The flexbox engine in `pythonnative.layout` is pure Python. Rendered
views carry their computed `frame` (`x, y, width, height`) once
`render` runs the layout pass for the default 390x844 viewport (pass
`viewport=(w, h)` to change it, or `viewport=None` to skip layout):

```python
def test_row_distributes_flex_children():
    result = render(
        pn.Row(
            pn.View(test_id="a", style={"flex": 1, "height": 50}),
            pn.View(test_id="b", style={"flex": 2, "height": 50}),
            style={"width": 300, "spacing": 10},
        )
    )
    a, b = result.get_by_test_id("a"), result.get_by_test_id("b")
    assert a.frame[2] == pytest.approx((300 - 10) / 3)
    assert b.frame[0] == pytest.approx(a.frame[2] + 10)
```

For the engine alone, build `LayoutNode` trees and call
`calculate_layout` directly (see
[`pythonnative.layout`](../api/layout.md)).

## Testing native modules

Native modules call into platform SDKs directly, so unit-testing them
with the real implementation requires a device. For most app tests
it's enough to inject a fake at the boundary:

```python
class FakeFs:
    def __init__(self):
        self.store = {}

    def write_text(self, path, content):
        self.store[path] = content

    def read_text(self, path):
        return self.store[path]
```

Pass the fake into your component (via a context, a default argument,
or a module-level injection) and assert on `store`.

## Testing async code

`render` and every event helper settle the framework's `asyncio` loop
before returning, so `use_effect` coroutines, `use_resource`,
`use_query`, and transitions complete without extra plumbing. When you
trigger async work outside the helpers (a module-level task, a
mutation started from a fixture), call `result.settle()` or
[`settle()`][pythonnative.testing.settle], or use
[`pn.runtime.drain()`][pythonnative.runtime.drain] /
[`pn.run_blocking(coro)`][pythonnative.runtime.run_blocking] directly.
See [Testing async code](async.md#testing-async-code).

## Going lower level

`render` is a thin layer over
[`Reconciler`][pythonnative.reconciler.Reconciler] and
[`FakeBackend`][pythonnative.testing.FakeBackend]. Tests that need to
assert on the *mutations* themselves (how many `InsertOp`s a reorder
produced, which props an `UpdateOp` changed) can pass their own
backend and read `backend.ops`, or construct the reconciler directly:

```python
from pythonnative.reconciler import Reconciler
from pythonnative.testing import FakeBackend

backend = FakeBackend()
rec = Reconciler(backend)
rec.mount(pn.Text("hi"))
assert [type(op).__name__ for op in backend.ops] == ["CreateOp"]
```

## Running the suite

PythonNative uses `pytest` plus the standard CI matrix (Ruff, Black,
MyPy). Run them all locally before pushing:

```bash
./scripts/check.sh
```

The same commands run in CI on every push and pull request.

## Next steps

- Wrap subtrees with [Error boundaries](error-boundaries.md) so test
  failures don't crash unrelated assertions.
- See how the fake backend fits underneath: [Native views](../concepts/native-views.md).
- Browse the API: [Testing](../api/testing.md).
