# Testing

PythonNative is built so that the bulk of your application logic can
be tested without a device or simulator. The reconciler talks to
native widgets exclusively through the
[`NativeViewRegistry`][pythonnative.native_views.NativeViewRegistry];
swap that out for a mock and a render produces a tree of plain Python
dicts that `pytest` can introspect.

## What to test

- **Components**: assert that a component renders the expected
  element type with the expected props for a given input.
- **Hooks**: drive state transitions and verify outputs after each
  render.
- **Reducers**: pure functions; test them as you would any other
  Python function.
- **Native modules**: skip platform-only paths or mock them at the
  boundary.

What *not* to test (or to test sparingly): the platform handler
implementations themselves. Those run only on the device and benefit
much more from manual smoke tests.

## A minimal mock registry

```python
from pythonnative.native_views import NativeViewRegistry, set_registry


class _MockHandler:
    def create_view(self, props):
        return {"props": dict(props), "children": [], "frame": (0, 0, 0, 0)}

    def update_view(self, view, prev, next):
        view["props"] = dict(next)

    def add_child(self, parent, child, index):
        parent["children"].insert(index, child)

    def remove_child(self, parent, child):
        parent["children"].remove(child)

    def insert_child(self, parent, child, index):
        parent["children"].insert(index, child)

    def set_frame(self, view, x, y, width, height):
        view["frame"] = (x, y, width, height)

    def measure_intrinsic(self, view, max_w, max_h):
        return (0.0, 0.0)


def install_mock_registry():
    reg = NativeViewRegistry()
    for ty in (
        "Text", "Button", "Column", "Row", "ScrollView",
        "View", "TextInput", "Image", "Switch", "Spacer",
        "Pressable", "FlatList",
    ):
        reg.register(ty, _MockHandler())
    set_registry(reg)
```

Drop this into a `conftest.py` and call `install_mock_registry()` from
a session-scoped fixture, or as a fixture parameterized on the
component under test.

## Rendering a component in a test

`create_screen` boots an `_ScreenHost` which is the same shape used at
runtime. For tests we want a more direct path: invoke the reconciler
with a known root and read its output.

```python
import pythonnative as pn
from pythonnative.reconciler import Reconciler


def render(element):
    """Mount `element` once with the mock registry and return the root."""
    rec = Reconciler()
    rec.mount(element)
    return rec.root_view  # the mock dict for the root element
```

(For a longer-running test (effects, navigation), use `create_screen` so
you get the full lifecycle plumbing.)

## Asserting on rendered output

```python
def test_counter_increments():
    @pn.component
    def Counter():
        count, set_count = pn.use_state(0)
        return pn.Column(
            pn.Text(f"Count: {count}", key="t"),
            pn.Button("+", on_click=lambda: set_count(count + 1), key="b"),
        )

    install_mock_registry()
    root = render(Counter())

    label, button = root["children"]
    assert label["props"]["text"] == "Count: 0"

    button["props"]["on_click"]()
    # The reconciler re-renders synchronously; read the latest text.
    assert root["children"][0]["props"]["text"] == "Count: 1"
```

Notes:

- `key="t"` and `key="b"` aren't required for a two-child column, but
  using them in tests makes assertions more robust as the component
  evolves.
- Behavioural props (like `on_click`) are passed through unchanged, so
  tests can call them directly.

## Testing hooks in isolation

For complex hook compositions (a custom hook that wraps several
built-ins), wrap the hook in a tiny throwaway component and assert on
its rendered shape:

```python
def test_use_toggle():
    def use_toggle(initial=False):
        on, set_on = pn.use_state(initial)
        return on, lambda: set_on(not on)

    @pn.component
    def Probe():
        on, toggle = use_toggle()
        return pn.Text("on" if on else "off", on_click=toggle, key="t")

    root = render(Probe())
    assert root["props"]["text"] == "off"
    root["props"]["on_click"]()
    assert root["props"]["text"] == "on"
```

## Testing layouts

The flexbox engine in `pythonnative.layout` is pure Python and easy
to test in isolation. For a single tree:

```python
from pythonnative.layout import LayoutNode, calculate_layout


def test_row_distributes_flex_children():
    root = LayoutNode(
        style={"flex_direction": "row", "width": 300, "height": 50,
               "spacing": 10},
        children=[
            LayoutNode(style={"flex": 1, "height": 50}),
            LayoutNode(style={"flex": 2, "height": 50}),
        ],
    )
    calculate_layout(root, 400, 600)

    a, b = root.children
    assert a.x == 0 and a.width == (300 - 10) / 3
    assert b.x == a.width + 10 and b.width == 2 * (300 - 10) / 3
```

To test the layout pass for a real component (with the mock registry),
use [`Reconciler.compute_layout_for_test`][pythonnative.reconciler.Reconciler.compute_layout_for_test]
which returns the computed `LayoutNode` tree.

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

## Running the suite

PythonNative uses `pytest` plus the standard CI matrix (Ruff, Black,
MyPy). Run them all locally before pushing:

```bash
ruff check src/pythonnative
ruff format --check
black --check src/pythonnative
mypy src/pythonnative
pytest
```

The same commands run in CI on every push and pull request.

## Next steps

- Wrap subtrees with [Error boundaries](error-boundaries.md) so test
  failures don't crash unrelated assertions.
- See how mocks are wired underneath: [Native views](../concepts/native-views.md).
