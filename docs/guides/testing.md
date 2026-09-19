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

What *not* to test (or to test sparingly): the Swift and Kotlin
component managers themselves. Those run only on the device and are
covered by their XCTest and JUnit suites and by the Maestro E2E suite
(`tests/e2e/`).

Installing `pythonnative` also installs a pytest plugin (registered
under the `pytest11` entry point) that resets the framework runtime
between tests and provides the `pn_clock` fixture, so no `conftest.py`
is needed. Disable it with `-p no:pythonnative`.

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
    result.press(result.get_by_role("button", name="+"))
    assert result.get_by_text("Count: 1")
```

`press` (and the general `fire(target, "on_event", *args)`) dispatch
the event exactly as a native listener would, then settle: pending
re-renders, effects, and async work run before the call returns, so
the next line can assert on the new tree. Like a real tap, `press`
refuses a disabled target (`disabled=True`,
`accessibility_state={"disabled": True}`, or a disabled `Pressable` or
`Button` ancestor) with an `AssertionError`; pass `force=True` to
dispatch anyway. `act(fn)` runs a plain callable (a state setter, an
imperative handle call) and settles the same way.

### Queries

Queries mirror Testing Library:

| Query | Returns |
|---|---|
| `get_by_text`, `get_by_test_id`, `get_by_label`, `get_by_type`, `get_by_role`, `get_by_placeholder_text`, `get_by_display_value` | exactly one view, or raises `LookupError` with the tree dumped in the message |
| `query_by_*` | the view or `None` |
| `get_all_by_*` | every match |
| `find_by_*` | `get_by_*` wrapped in [`wait_for`][pythonnative.testing.wait_for]: polls until the view appears |

Matchers are exact strings, compiled regexes, or predicates;
`get_by_text("Count", exact=False)` matches substrings. Views inside a
`display: "none"` subtree (inactive tabs, screens beneath the top of a
stack) are skipped unless you pass `hidden=True`, which is how you
assert that a hidden screen kept its state.

`get_by_role(role, name=...)` matches the `accessibility_role` prop, or
the type's implicit role when the prop is unset, optionally narrowed by
the accessible name (the `accessibility_label`, else the visible text
or title, else the text of descendants). The implicit roles come from
[`IMPLICIT_ROLES`][pythonnative.testing.IMPLICIT_ROLES]:

| Type | Implicit role |
|---|---|
| `Button`, `Pressable`, `Picker`, `DatePicker` | `"button"` |
| `Switch` | `"switch"` |
| `Checkbox` | `"checkbox"` |
| `TextInput` | `"textbox"` |
| `Image`, `ImageBackground` | `"image"` |
| `Slider` | `"adjustable"` |
| `ProgressBar` | `"progressbar"` |

`Text` has no implicit role; `pn.Text("Title", accessibility_role="header")`
matches `get_by_role("header")` through the prop.

Each match is a [`FakeView`][pythonnative.testing.FakeView] with
`type_name`, `props`, `children`, `parent`, `frame`, `text`, `value`,
and `placeholder`. `text` is the visible static text (`Text.text` or
`Button.title`); a `TextInput`'s contents are exposed as `value` and
`placeholder`, so `get_by_text` never matches a form field, while
`get_by_display_value` and `get_by_placeholder_text` do.
`result.text()` lists the visible strings in order, and
`result.dump()` prints the tree when a test is confusing.

Scope any query to one subtree with
[`within`][pythonnative.testing.within]:

```python
from pythonnative.testing import render, wait_for, within


def test_form(pn_clock):
    r = render(Form())
    r.change_text(r.get_by_placeholder_text("Email"), "a@b.c")
    r.press(r.get_by_role("button", name="Save"))
    pn_clock.advance(2.0)                     # timers fire, no real sleep
    assert wait_for(lambda: r.query_by_text("Saved"))
    card = within(r.get_by_test_id("summary"))
    assert card.get_by_display_value("a@b.c")
```

`wait_for(predicate, timeout=1.0, interval=0.01)` polls `predicate`
while draining the framework loop; a `LookupError` or `AssertionError`
raised by the predicate counts as "not yet", so both `get_by_*` and
`query_by_*` work inside it.

### Other helpers

- `change_text(input, "value")` fires `on_change` on a `TextInput`.
- `press(target, force=False)` fires `on_press`; `act(fn)` runs any
  callable and settles.
- `back()` simulates the system back action and returns whether a
  handler consumed it.
- `rerender(element)` reconciles new root props from outside the tree.
- `settle()` pumps the framework loop until async work is done.
- `unmount()` tears down and runs effect cleanups; `RenderResult` is
  also a context manager.

### Virtual time

Timers (`asyncio.sleep`, `call_later`, `asyncio.timeout`) on the
framework loop can run on virtual time. The `pn_clock` fixture from the
shipped pytest plugin installs a
[`FakeClock`][pythonnative.testing.FakeClock];
[`fake_clock`][pythonnative.testing.fake_clock] is the context-manager
form for code outside pytest:

```python
from pythonnative.testing import fake_clock, render


def test_toast_disappears():
    with fake_clock() as clock:
        result = render(Toast())          # hides itself after asyncio.sleep(3)
        assert result.query_by_text("Saved")
        clock.advance(3.0)                # timers fire, no real sleep
        assert result.query_by_text("Saved") is None
```

The clock patches the loop's `time()` rather than `asyncio.sleep`, so
the framework's own timers (transitions, animations, debounced hooks)
advance together with the app's. `advance()` steps timer by timer, so
a re-arming timer fires the right number of times.

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

Navigators draw their own header when no native host is present, so a
whole flow fits in one test:

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

Headless tests call Yoga through the `pythonnative.layout` host binding.
The fake backend supplies deterministic intrinsic measurements; it doesn't
reproduce platform fonts or control metrics. Rendered views carry their
computed `frame` (`x, y, width, height`) once
`render` runs the layout pass for the default 390x844 viewport (pass
`viewport=(w, h)` to change it, or `viewport=None` to skip layout):

```python
def test_row_distributes_flex_children():
    result = render(
        pn.Row(
            pn.View(test_id="a", style={"flex": 1, "height": 50}),
            pn.View(test_id="b", style={"flex": 2, "height": 50}),
            style={"width": 310, "spacing": 10},
        )
    )
    a, b = result.get_by_test_id("a"), result.get_by_test_id("b")
    assert a.frame[2] == pytest.approx((310 - 10) / 3)
    assert b.frame[0] == pytest.approx(a.frame[2] + 10)
```

For the engine alone, build `LayoutNode` trees and call
`calculate_layout` directly (see
[`pythonnative.layout`](../api/layout.md)).

## Testing native modules

Off device every native module facade resolves to a Python
implementation, so `pn.Clipboard`, `pn.SecureStore`, `pn.AsyncStorage`,
and friends work in `pytest` with in-memory state. To control what a
module answers, register your own implementation under the module's
name before the component under test runs:

```python
from pythonnative.native_modules.registry import emit, register_python_module


class FakeLocation:
    async def get_current(self, **options):
        return {"latitude": 59.91, "longitude": 10.75}


register_python_module("Location", FakeLocation())
```

Methods are matched by name and receive the keyword arguments the
facade passed. Module events (`AppState` changes, `NetInfo` updates,
your own module's notifications) can be pushed with
`emit("NetInfo", "change", {"type": "none", "is_connected": False})`;
listeners registered through the facades or the `use_*` hooks fire the
same way they would on device.

Use `unregister_python_module(name)` in a fixture teardown to restore
the built-in desktop implementation.

Facades don't swallow errors: a fake that raises
[`NativeModuleError`][pythonnative.native_modules.NativeModuleError]
surfaces through the facade to the component, which is the right way
to test your error handling. User cancellations and denials are
ordinary return values (`None` from `Camera.launch_camera`, `False`
from `Permissions.request`), so fake those by returning them.

## Testing the bridge

The reconciler's on-device backend serializes commits to JSON. To assert
on what native would receive (or to test a custom component's props at
the wire level), install a
[`FakeTransport`][pythonnative.bridge.fake.FakeTransport]: it decodes
transactions and keeps a native-style view tree, and lets tests inject
events, module results, and host lifecycle from the "native" side.
`tests/test_bridge.py` in the repository is the reference for this
style.

## Testing native code

The Swift and Kotlin halves have their own suites next to the code:

```bash
cd src/pythonnative/native/ios
xcodebuild test -project Tests/NativeTests.xcodeproj -scheme NativeTests -destination 'platform=iOS Simulator,name=iPhone 15 Pro'

cd src/pythonnative/templates/android_template
./gradlew :pythonnative:testDebugUnitTest
```

Both drive component managers and modules with decoded transactions and
promise envelopes, so a wire-format change is caught on every side. Add
cases there when you change a manager or module rather than relying on
the Maestro E2E suite alone.

The iOS `NativeTests` scheme runs the Swift tests inside a minimal UIKit
app. Use that scheme for native tests: composition, selection, and focus
need an application event loop and keyboard session, which the standalone
Swift package test runner doesn't provide. Add new Swift test files to
both the test directory and the Xcode project's `PythonNativeKitTests`
target.

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

### A minimal fake backend

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

Two optional suites need the network and are skipped by default:

- `uv run pytest tests/packages -m network` resolves every package in
  `tests/packages/matrix.toml` against the live PyPI, BeeWare, and
  Chaquopy indexes and asserts the outcome matches the manifest. The
  `packages` workflow runs it weekly. See
  [PyPI packages](pypi-packages.md#compatibility-matrix).
- The Maestro E2E suite under `tests/e2e/` drives the example apps on
  an emulator and a Simulator; see `tests/e2e/AGENTS.md`.

## Next steps

- Wrap subtrees with [Error boundaries](error-boundaries.md) so test
  failures don't crash unrelated assertions.
- See how the fake backend fits underneath: [Native views](../concepts/native-views.md).
- Browse the API: [Testing](../api/testing.md).
