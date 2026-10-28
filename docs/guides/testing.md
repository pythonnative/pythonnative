# Testing

PythonNative is built so that the bulk of your application logic can
be tested without a device or simulator. The reconciler talks to
native widgets exclusively through the batched mutation protocol (see
[Native views](../concepts/native-views.md)); `pythonnative.testing`
swaps in a backend that commits to the host build of the same renderer
core the apps link, so tests validate, lay out, animate, and recognize
gestures with the code that ships. A render produces a tree of plain
Python objects that `pytest` can introspect, and Testing Library-style
queries help you do it.

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
under the `pytest11` entry point), so no `conftest.py` is needed. It
runs every test in development mode, resets the framework runtime
between tests, and provides the `pn_clock` fixture. Disable it with
`-p no:pythonnative`.

Development mode turns on the checks a debug build runs and a release
build skips: built-in prop and style validation, hook-order checks,
and checks of your components' props against their annotations. A
mismatch is a [`diagnostics`][pythonnative.diagnostics] warning, not an
exception, so assert on it when a test cares:

```python
import pythonnative as pn
from pythonnative import diagnostics
from pythonnative.testing import render


@pn.component
def Greeting(name: str) -> pn.Node:
    return pn.Text(f"Hello, {name}")


def test_untyped_caller_is_reported() -> None:
    render(Greeting(name=42))  # type: ignore[arg-type]
    assert any("Greeting() received name=42" in w for w in diagnostics.get_warnings())
```

The plugin clears recorded warnings between tests.

## Rendering a component

[`render`][pythonnative.testing.render] mounts an element and returns a
[`RenderResult`][pythonnative.testing.RenderResult]:

```python
import pythonnative as pn
from pythonnative.testing import render


@pn.component
def Counter() -> pn.Node:
    count, set_count = pn.use_state(0)
    return pn.Column(
        pn.Text(f"Count: {count}"),
        pn.Button("+", on_press=lambda: set_count(count + 1)),
    )


def test_counter_increments() -> None:
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
whole flow fits in one test. With the `App` from the
[Navigation guide](navigation.md#a-complete-example):

```python
def test_home_to_item_and_back() -> None:
    result = render(App())
    result.press(result.get_by_text("Open item 42"))
    assert result.get_by_text("Item 42 (details)")
    assert result.back() is True
    assert result.get_by_text("Open item 42")
```

To assert on navigation state, pass `on_state_change` to the container
and record what it reports. Route names default to the screen
components' names:

```python
def test_push_records_params() -> None:
    states: list[pn.NavigationState] = []

    @pn.component
    def Harness() -> pn.Node:
        return pn.NavigationContainer(Root, on_state_change=states.append)

    result = render(Harness())
    result.press(result.get_by_text("Open item 42"))
    route = states[-1].current
    assert (route.name, route.params) == ("ItemScreen", {"id": 42, "tab": "details"})
```

To test how the root navigator behaves under a native host, render
under a [`FakeHost`][pythonnative.testing.FakeHost]. Its `initial_state`
boots the navigator "mid-stack" from a saved state, the way a pushed
native screen re-entering Python does, and `set_focused` simulates the
platform covering or revealing the screen:

```python
from pythonnative.testing import FakeHost


def test_restores_saved_stack() -> None:
    saved = {
        "routes": [
            {"name": "HomeScreen", "params": {}, "key": "home"},
            {"name": "ItemScreen", "params": {"id": 7}, "key": "item"},
        ],
        "index": 1,
    }
    result = render(App(), host=FakeHost(initial_state=saved))
    assert result.get_by_text("Item 7 (details)")
```

The host also records the screen options it receives in `options`, with
the latest title in `title`.

## Testing layouts

Headless tests lay out in the renderer core, with the same Yoga rules,
detached roots, and flattening as a device. The fake platform measures
leaves with fixed sizes
([`DEFAULT_INTRINSIC`][pythonnative.testing.DEFAULT_INTRINSIC]: a `Text`
is 60 by 16, for example); pass `FakeBackend(intrinsic={...})` to change
them. It doesn't reproduce platform fonts or control metrics. Rendered
views carry the `frame` (`x, y, width, height`) the core computed for the
default 390x844 viewport (pass `viewport=(w, h)` to change it, or
`viewport=None` to skip layout):

```python
def test_row_distributes_flex_children():
    result = render(
        pn.Row(
            pn.View(test_id="a", style={"flex": 1, "height": 50}),
            pn.View(test_id="b", style={"flex": 2, "height": 50}),
            style={"width": 310, "gap": 10},
        )
    )
    a, b = result.get_by_test_id("a"), result.get_by_test_id("b")
    assert a.frame[2] == pytest.approx((310 - 10) / 3)
    assert b.frame[0] == pytest.approx(a.frame[2] + 10)
```

Frames on the logical views are relative to their logical parents, the
way `on_layout` reports them. To check what the platform would mount
instead, read the transport (see below).

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

## Testing what the platform mounts

[`FakeBackend`][pythonnative.testing.FakeBackend] commits through a
[`FakeTransport`][pythonnative.bridge.fake.FakeTransport], available as
`result.backend.native`. The transport plays the platform's UI thread:
it decodes each binary mount transaction the core queues and keeps the
mounted tree, so tests can assert on what a device would receive.

```python
def test_layout_wrappers_are_flattened() -> None:
    result = render(pn.Column(pn.Row(pn.Text("a"), pn.Text("b"), style={"padding": 10})))
    backend = result.backend
    assert backend.live_view_count() == 4     # Column, Row, and two Texts
    assert backend.mounted_view_count() == 3  # the Row only affects layout
    text = backend.native.find("Text")[0]
    assert text.parent.type_name == "Column"
    assert text.frame[:2] == (10.0, 10.0)   # offset by the flattened Row
```

| Attribute or method | What it holds |
| --- | --- |
| `native.views`, `find(type)`, `roots()` | Mounted [`FakeNativeView`][pythonnative.bridge.fake.FakeNativeView]s with merged props, mounted children, frames relative to the nearest mounted ancestor, and animated values |
| `native.transactions` | Every decoded [`MountTransaction`][pythonnative.bridge.core.MountTransaction] |
| `native.commands` | `(tag, name, args)` view commands in the order the UI thread ran them |
| `native.writes` (also `backend.animated`) | `(tag, prop, value)` animated prop writes from the core's animator |
| `native.calls` | `(module, method, args)` native module calls |
| `native.measured` | `(tag, component)` pairs the core asked the platform to measure |
| `backend.list_store(tag)` | A `VirtualList`'s dataset as the UI thread's data source sees it: revision, keys, and rows |
| `backend.request_list(tag, first)` | Simulates the native list viewport requesting rows from `first` |

The transport also plays the native side in the other direction:
`fire(tag, name, *args)` sends a view event through the core's stamping,
`pointer(tag, events)` feeds gestures (see
[Gestures](gestures.md#testing)), `report_container` and
`report_intrinsic` report native sizes and relayout, and
`emit_module_event`, `resolve_pending`, and `host_event` deliver module
and host messages. Animations advance on the framework loop's clock, so a
[`FakeClock`][pythonnative.testing.FakeClock] drives them. Every
`FakeTransport` owns its own core surface, so several can live in one
test. `tests/test_bridge.py` in the repository is the reference for this
style.

## Testing native code

The Swift and Kotlin halves have their own suites next to the code:

```bash
cd src/pythonnative/native/ios
xcodebuild test -project Tests/NativeTests.xcodeproj -scheme NativeTests -destination 'platform=iOS Simulator,name=iPhone 15 Pro'

cd src/pythonnative/templates/android_template
./gradlew :pythonnative:testDebugUnitTest
```

Both drive the mounting layer, component managers, and modules with
mount transactions and promise envelopes, so a wire-format change is
caught on every side. Add
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
- The wire formats the transport decodes: [The native bridge](../concepts/bridge.md).
- Browse the API: [Testing](../api/testing.md).
