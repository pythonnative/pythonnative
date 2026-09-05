"""Test utilities: render components without a device.

```python
import pythonnative as pn
from pythonnative.testing import render, render_hook

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

def test_use_state():
    hook = render_hook(lambda: pn.use_state("a"))
    hook.act(lambda: hook.current[1]("b"))
    assert hook.current[0] == "b"
```

- [`render`][pythonnative.testing.render] mounts an element into a
  [`FakeBackend`][pythonnative.testing.FakeBackend] and returns a
  [`RenderResult`][pythonnative.testing.RenderResult] with Testing
  Library-style queries (``get_by_text``, ``get_by_test_id``,
  ``get_by_label``, ``get_by_type``) and event helpers (``press``,
  ``fire``, ``change_text``, ``back``).
- [`render_hook`][pythonnative.testing.render_hook] runs a hook in a
  throwaway component.
- [`settle`][pythonnative.testing.settle] pumps the framework loop so
  async work (resources, queries, transitions) completes.
- [`FakeHost`][pythonnative.testing.FakeHost] stands in for a native
  screen host so root stack navigators can be tested.
"""

from .backend import DEFAULT_INTRINSIC, FakeBackend, FakeView
from .harness import FakeHost, HookResult, RenderResult, render, render_hook, settle

__all__ = [
    "DEFAULT_INTRINSIC",
    "FakeBackend",
    "FakeHost",
    "FakeView",
    "HookResult",
    "RenderResult",
    "render",
    "render_hook",
    "settle",
]
