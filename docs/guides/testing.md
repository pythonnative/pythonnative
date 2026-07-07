# Testing

PythonNative is built so that the bulk of your application logic can
be tested without a device or simulator. The reconciler talks to
native widgets exclusively through the batched mutation protocol
(see [Native views](../concepts/native-views.md)); swap the backend
for an in-memory fake and a render produces a tree of plain Python
objects that `pytest` can introspect.

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
implementations themselves. Those run only on the device and are
covered by the Maestro E2E suite (`tests/e2e/`).

## A minimal fake backend

A test backend implements the registry protocol: `apply_mutations`,
`resolve_view`, `measure_intrinsic`, and `command`. PythonNative's own
suite keeps a full-featured one in `tests/fake_backend.py`; copy it
into your project or use this trimmed version:

```python
from pythonnative.mutations import (
    CreateOp, UpdateOp, InsertOp, DestroyOp, SetFrameOp,
)


class FakeView:
    def __init__(self, tag, type_name, props):
        self.tag, self.type_name, self.props = tag, type_name, dict(props)
        self.children, self.frame = [], (0, 0, 0, 0)

    def find_all(self, type_name):
        out = [self] if self.type_name == type_name else []
        for child in self.children:
            out.extend(child.find_all(type_name))
        return out


class FakeBackend:
    def __init__(self):
        self.views = {}

    def apply_mutations(self, ops):
        for op in ops:
            if isinstance(op, CreateOp):
                self.views[op.tag] = FakeView(op.tag, op.type_name, op.props)
            elif isinstance(op, UpdateOp):
                self.views[op.tag].props.update(op.changed_props)
            elif isinstance(op, InsertOp):
                child = self.views[op.child_tag]
                self.views[op.parent_tag].children.insert(op.index, child)
            elif isinstance(op, DestroyOp):
                self.views.pop(op.tag, None)
            elif isinstance(op, SetFrameOp):
                self.views[op.tag].frame = op.frame

    def resolve_view(self, tag):
        return self.views.get(tag)

    def measure_intrinsic(self, tag, max_w, max_h):
        return (0.0, 0.0)

    def command(self, tag, name, args=None):
        return None

    def set_animated_property(self, tag, prop, value): ...
    def start_animation(self, tag, anim_id, prop, spec): return False
    def cancel_animation(self, tag, anim_id): return None
```

## Rendering a component in a test

Construct the reconciler with the fake backend directly:

```python
import pythonnative as pn
from pythonnative.reconciler import Reconciler


def render(element):
    """Mount `element` and return (root FakeView, reconciler)."""
    backend = FakeBackend()
    rec = Reconciler(backend)
    rec._screen_re_render = lambda: None  # no screen host in tests
    rec.mount(element)
    return backend.views[rec.root_tag()], rec
```

(For a longer-running test (effects, navigation), use `create_screen` so
you get the full lifecycle plumbing.)

## Asserting on rendered output

Event callbacks live in the event registry, not on the view; drive
them with [`dispatch_event`][pythonnative.events.dispatch_event]
exactly like a native listener would:

```python
from pythonnative.events import dispatch_event


def test_counter_increments():
    @pn.component
    def Counter():
        count, set_count = pn.use_state(0)
        return pn.Column(
            pn.Text(f"Count: {count}", key="t"),
            pn.Button("+", on_click=lambda: set_count(count + 1), key="b"),
        )

    root, rec = render(Counter())

    label, button = root.children
    assert label.props["text"] == "Count: 0"

    dispatch_event(button.tag, "on_click")
    rec.flush_dirty()  # state changes commit on the next flush
    assert root.children[0].props["text"] == "Count: 1"
```

Notes:

- `key="t"` and `key="b"` aren't required for a two-child column, but
  using them in tests makes assertions more robust as the component
  evolves.
- Callable props never appear in `props`; the view carries a
  `_pn_events` frozenset naming the wired events, and
  `dispatch_event(tag, name, *args)` invokes the current callback.

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

    root, rec = render(Probe())
    assert root.props["text"] == "off"
    dispatch_event(root.tag, "on_click")
    rec.flush_dirty()
    assert root.props["text"] == "on"
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
