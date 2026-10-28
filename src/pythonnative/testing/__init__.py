"""Test utilities: render components without a device.

```python
import pythonnative as pn
from pythonnative.testing import render, render_hook, wait_for, within

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

def test_use_state():
    hook = render_hook(lambda: pn.use_state("a"))
    hook.act(lambda: hook.current[1]("b"))
    assert hook.current[0] == "b"

def test_timer(pn_clock):
    result = render(Toast())            # hides itself after asyncio.sleep(3)
    pn_clock.advance(3.0)               # timers fire, no real sleep
    assert wait_for(lambda: result.query_by_text("Saved") is None)
```

- [`render`][pythonnative.testing.render] mounts an element into a
  [`FakeBackend`][pythonnative.testing.FakeBackend] and returns a
  [`RenderResult`][pythonnative.testing.RenderResult] with Testing
  Library-style queries (``get_by_text``, ``get_by_test_id``,
  ``get_by_label``, ``get_by_type``, ``get_by_role``,
  ``get_by_placeholder_text``, ``get_by_display_value``, each with
  ``query_by_``, ``get_all_by_``, and ``find_by_`` variants) and event
  helpers (``press``, ``fire``, ``change_text``, ``back``, ``act``).
- [`within`][pythonnative.testing.within] scopes the same queries to one
  view's subtree; [`wait_for`][pythonnative.testing.wait_for] polls a
  predicate while draining the framework loop.
- [`render_hook`][pythonnative.testing.render_hook] runs a hook in a
  throwaway component.
- [`settle`][pythonnative.testing.settle] pumps the framework loop so
  async work (resources, queries, transitions) completes.
- [`fake_clock`][pythonnative.testing.fake_clock] (and the ``pn_clock``
  pytest fixture) installs a [`FakeClock`][pythonnative.testing.FakeClock]
  so ``asyncio`` timers run on virtual time.
- [`FakeHost`][pythonnative.testing.FakeHost] stands in for a native
  screen host so root stack navigators can be tested.
- ``pythonnative.testing.pytest_plugin`` is registered with pytest
  automatically and resets the runtime between tests.
"""

from .backend import DEFAULT_INTRINSIC, IMPLICIT_ROLES, FakeBackend, FakeView
from .clock import FakeClock, current_fake_clock, fake_clock
from .harness import FakeHost, HookResult, RenderResult, render, render_hook, settle
from .queries import Matcher, Queries, Scope, wait_for, within

__all__ = [
    "DEFAULT_INTRINSIC",
    "IMPLICIT_ROLES",
    "FakeBackend",
    "FakeClock",
    "FakeHost",
    "FakeView",
    "HookResult",
    "Matcher",
    "Queries",
    "RenderResult",
    "Scope",
    "current_fake_clock",
    "fake_clock",
    "render",
    "render_hook",
    "settle",
    "wait_for",
    "within",
]
