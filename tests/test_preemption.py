"""Preemptible transitions (RFC 0010).

A render pass for transition updates checks for queued urgent input
before each component body. When input is waiting, the pass rolls back,
the input is handled and committed, and the transition renders again.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import pytest

import pythonnative as pn
from pythonnative import scheduler
from pythonnative.testing import fake_clock, render

_ctx: Dict[str, Any] = {}


@pytest.fixture(autouse=True)
def _reset() -> Any:
    _ctx.clear()
    _ctx["effects"] = []
    _ctx["cell_effects"] = []
    yield
    _ctx.clear()


@pn.component
def Cell(n: int, index: int) -> pn.Node:
    hook: Optional[Callable[[int, int], None]] = _ctx.get("on_cell")
    if hook is not None:
        hook(n, index)
    pn.use_effect(lambda: _ctx["cell_effects"].append((index, n)), [n])
    return pn.Text(f"cell {index} {n}")


@pn.component
def App() -> pn.Node:
    clicks, set_clicks = pn.use_state(0)
    shown, set_shown = pn.use_state(0)
    pending, start = pn.use_transition()
    pn.use_effect(lambda: _ctx["effects"].append(shown), [shown])
    _ctx["press"] = lambda: set_clicks(lambda count: count + 1)
    _ctx["show"] = lambda n: start(lambda: set_shown(n))
    _ctx["set_shown"] = set_shown
    return pn.Column(
        pn.Text(f"clicks {clicks} pending {pending}"),
        [Cell(shown, index).with_key(str(index)) for index in range(12)],
    )


def record_commits(result: Any) -> List[tuple[str, str]]:
    commits: List[tuple[str, str]] = []

    def committed() -> None:
        texts = result.text()
        commits.append((texts[0], texts[1]))

    result.reconciler.on_commit = committed
    return commits


def press_once_at(cell: int, *, shown: int) -> List[str]:
    """Queue one urgent press while the transition renders ``cell`` for ``shown``."""
    log: List[str] = []

    def on_cell(n: int, index: int) -> None:
        if n == shown and index == cell and not log:
            log.append("queued")
            scheduler.queue_urgent(_ctx["press"])

    _ctx["on_cell"] = on_cell
    return log


def test_urgent_input_preempts_a_rendering_transition() -> None:
    result = render(App())
    commits = record_commits(result)
    press_once_at(5, shown=1)

    _ctx["show"](1)
    result.settle()

    assert commits == [
        ("clicks 0 pending True", "cell 0 0"),
        ("clicks 1 pending True", "cell 0 0"),
        ("clicks 1 pending False", "cell 0 1"),
    ]
    assert result.reconciler.transitions.preemptions == 0
    assert not result.reconciler.transitions.pending


def test_a_preempted_pass_runs_no_effects_and_keeps_hook_state() -> None:
    result = render(App())
    press_once_at(5, shown=1)
    _ctx["cell_effects"].clear()

    _ctx["show"](1)
    result.settle()

    assert sorted(_ctx["cell_effects"]) == [(index, 1) for index in range(12)]
    assert _ctx["effects"] == [0, 1]


def test_urgent_updates_render_without_the_transition_updates() -> None:
    result = render(App())
    seen: List[str] = []

    def on_cell(n: int, index: int) -> None:
        if index == 0:
            seen.append(f"render {n}")
        if n == 1 and index == 3 and "pressed" not in seen:
            seen.append("pressed")
            scheduler.queue_urgent(lambda: _ctx["press"]())

    _ctx["on_cell"] = on_cell
    _ctx["show"](1)
    result.settle()

    # The urgent pass for is_pending, the abandoned transition, the urgent
    # pass for the press (still 0), then the retry.
    assert seen == ["render 0", "render 1", "pressed", "render 0", "render 1"]
    assert result.text()[:2] == ["clicks 1 pending False", "cell 0 1"]


def test_a_starved_transition_renders_without_yielding() -> None:
    result = render(App())
    attempts: List[int] = []

    def on_cell(n: int, index: int) -> None:
        if n == 1 and index == 2:
            attempts.append(result.reconciler.transitions.preemptions)
            scheduler.queue_urgent(lambda: None)

    _ctx["on_cell"] = on_cell
    _ctx["show"](1)
    result.settle()

    assert attempts == [0, 1, 2, 3]
    assert scheduler.MAX_PREEMPTIONS == 3
    assert result.text()[:2] == ["clicks 0 pending False", "cell 0 1"]
    assert result.reconciler.transitions.preemptions == 0


def test_a_transition_pending_past_the_deadline_renders_without_yielding() -> None:
    with fake_clock() as clock:
        result = render(App())
        commits = record_commits(result)
        press_once_at(5, shown=1)
        transitions = result.reconciler.transitions

        _ctx["show"](1)
        assert transitions.started is not None
        assert not transitions.must_finish(transitions.started + 0.1)
        assert transitions.must_finish(transitions.started + scheduler.STARVATION_SECONDS)
        transitions.started -= 1.0
        clock.run_until_idle()
        result.settle()

    assert commits[-2:] == [
        ("clicks 0 pending False", "cell 0 1"),
        ("clicks 1 pending False", "cell 0 1"),
    ]


def test_start_transition_outside_a_component() -> None:
    result = render(App())
    commits = record_commits(result)
    press_once_at(4, shown=7)

    pn.start_transition(lambda: _ctx["set_shown"](7))
    assert result.reconciler.transitions.pending
    assert result.text()[1] == "cell 0 0", "a transition doesn't render inline"
    result.settle()

    assert commits == [("clicks 1 pending False", "cell 0 0"), ("clicks 1 pending False", "cell 0 7")]


def test_a_deferred_value_restarts_for_the_newer_value() -> None:
    rendered: List[str] = []

    @pn.component
    def Row(query: str, index: int) -> pn.Node:
        rendered.append(f"{query}:{index}")
        if query == "a" and index == 2 and "typed" not in _ctx:
            _ctx["typed"] = True
            scheduler.queue_urgent(lambda: _ctx["type"]("ab"))
        return pn.Text(f"{query} {index}")

    @pn.component
    def Search() -> pn.Node:
        query, set_query = pn.use_state("")
        shown = pn.use_deferred_value(query)
        _ctx["type"] = set_query
        return pn.Column(pn.Text(f"query {query}"), [Row(shown, i).with_key(str(i)) for i in range(5)])

    result = render(Search())
    commits = record_commits(result)
    _ctx["type"]("a")
    result.settle()

    assert ("query ab", " 0") in commits, "the keystroke committed before the deferred rows"
    assert commits[-1] == ("query ab", "ab 0")
    assert "a:3" not in rendered, "the abandoned render stopped at the preemption"


def test_is_pending_stays_true_until_the_transition_commits() -> None:
    result = render(App())
    pending: List[str] = []

    def on_cell(n: int, index: int) -> None:
        if n == 1 and index == 0 and len(pending) < 2:
            pending.append(result.text()[0])
            scheduler.queue_urgent(_ctx["press"])

    _ctx["on_cell"] = on_cell
    _ctx["show"](1)
    result.settle()

    assert pending == ["clicks 0 pending True", "clicks 1 pending True"]
    assert result.text()[0] == "clicks 2 pending False"


def test_bridge_discrete_events_are_urgent_and_continuous_ones_are_not(monkeypatch: pytest.MonkeyPatch) -> None:
    from pythonnative import bridge

    queued: List[str] = []
    monkeypatch.setattr(scheduler, "queue_urgent", lambda callback, *args: queued.append(args[2]))

    class Loop:
        def is_running(self) -> bool:
            return True

        def call_soon_threadsafe(self, callback: Any, *args: Any) -> None:
            queued.append(f"plain {args[1] if len(args) > 1 else ''}")

    monkeypatch.setattr("pythonnative.runtime.get_loop", lambda: Loop())
    monkeypatch.setattr("pythonnative.runtime._on_loop_thread", lambda loop: False)
    bridge.native_callback("event", 1, "on_press", "[]")
    bridge.native_callback("event", 1, "on_scroll", "{}")
    bridge.native_callback("module", 0, "Fetch", "{}")
    bridge._continuous.clear()
    assert queued[0] == "on_press"
    assert queued[1] == "plain on_scroll"
    assert queued[2].startswith("plain")
