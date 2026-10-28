"""Tests for the reconciler's identity bailout, the context consumer registry, and the transition queue."""

from __future__ import annotations

from collections import Counter
from typing import Callable, List

import pytest

import pythonnative as pn
from pythonnative.hooks import StateSetter
from pythonnative.scheduler import TransitionQueue
from pythonnative.testing import render

ValueContext = pn.create_context(0, name="Value")


class Probe:
    """Counts renders by label and keeps the latest state setter per label."""

    def __init__(self) -> None:
        self.renders: Counter[str] = Counter()
        self.setters: dict[str, StateSetter[int]] = {}

    def leaf(self) -> pn.Component[[str]]:
        probe = self

        @pn.component
        def Leaf(label: str) -> pn.Node:
            count, set_count = pn.use_state(0)
            probe.renders[label] += 1
            probe.setters[label] = set_count
            return pn.Text(f"{label}:{count}")

        return Leaf

    def consumer(self) -> pn.Component[[str]]:
        probe = self

        @pn.component
        def Consumer(label: str) -> pn.Node:
            value = pn.use_context(ValueContext)
            probe.renders[label] += 1
            return pn.Text(f"{label}={value}")

        return Consumer


# ======================================================================
# Identity bailout
# ======================================================================


def test_passed_through_children_skip_when_the_parent_rerenders() -> None:
    probe = Probe()
    Leaf = probe.leaf()

    @pn.component
    def Wrapper(*children: pn.Node) -> pn.Node:
        tick, set_tick = pn.use_state(0)
        probe.renders["wrapper"] += 1
        probe.setters["wrapper"] = set_tick
        return pn.Column(pn.Text(f"tick={tick}"), *children)

    @pn.component
    def App() -> pn.Node:
        probe.renders["app"] += 1
        return Wrapper(Leaf("a"), pn.View(Leaf("b")))

    result = render(App())
    assert probe.renders == {"app": 1, "wrapper": 1, "a": 1, "b": 1}

    for n in range(1, 4):
        result.act(lambda n=n: probe.setters["wrapper"](n))  # type: ignore[misc]

    assert result.text() == ["tick=3", "a:0", "b:0"]
    assert probe.renders == {"app": 1, "wrapper": 4, "a": 1, "b": 1}


def test_a_bailed_out_child_with_its_own_state_change_still_renders() -> None:
    probe = Probe()
    Leaf = probe.leaf()

    @pn.component
    def Wrapper(*children: pn.Node) -> pn.Node:
        tick, set_tick = pn.use_state(0)
        probe.setters["wrapper"] = set_tick
        return pn.Column(pn.Text(f"tick={tick}"), *children)

    result = render(Wrapper(Leaf("a"), Leaf("b")))

    result.act(lambda: probe.setters["a"](5))
    assert result.text() == ["tick=0", "a:5", "b:0"]
    assert probe.renders == {"a": 2, "b": 1}

    def both() -> None:
        probe.setters["wrapper"](1)
        probe.setters["b"](7)

    result.act(both)
    assert result.text() == ["tick=1", "a:5", "b:7"]
    assert probe.renders == {"a": 2, "b": 2}


def test_rerendering_the_root_with_new_elements_still_updates() -> None:
    probe = Probe()
    Leaf = probe.leaf()

    result = render(pn.Column(Leaf("a")))
    result.rerender(pn.Column(Leaf("a"), Leaf("b")))

    assert result.text() == ["a:0", "b:0"]
    assert probe.renders == {"a": 2, "b": 1}


def test_identical_native_element_is_reused() -> None:
    setters: List[StateSetter[int]] = []
    static = pn.View(pn.Text("static"), test_id="static")

    @pn.component
    def Screen() -> pn.Node:
        tick, set_tick = pn.use_state(0)
        setters.append(set_tick)
        return pn.Column(pn.Text(str(tick)), static)

    result = render(Screen())
    before = result.get_by_test_id("static")
    result.act(lambda: setters[-1](1))

    assert result.get_by_test_id("static") is before
    assert result.text() == ["1", "static"]


def test_context_change_reaches_consumers_below_a_bailed_out_subtree() -> None:
    probe = Probe()
    Leaf = probe.leaf()
    Consumer = probe.consumer()

    @pn.component
    def Wrapper(*children: pn.Node) -> pn.Node:
        value, set_value = pn.use_state(1)
        probe.setters["wrapper"] = set_value
        return ValueContext.Provider(pn.Column(*children), value=value)

    result = render(Wrapper(Leaf("a"), pn.View(Consumer("consumer"))))
    assert result.text() == ["a:0", "consumer=1"]

    result.act(lambda: probe.setters["wrapper"](2))

    assert result.text() == ["a:0", "consumer=2"]
    assert probe.renders == {"a": 1, "consumer": 2}


def test_memo_skips_equal_props_and_renders_changed_props() -> None:
    renders: List[str] = []
    setters: List[StateSetter[int]] = []

    @pn.memo
    @pn.component
    def Label(text: str) -> pn.Node:
        renders.append(text)
        return pn.Text(text)

    @pn.component
    def Screen() -> pn.Node:
        tick, set_tick = pn.use_state(0)
        setters.append(set_tick)
        return pn.Column(Label(text="fixed"), Label(text=f"tick {tick // 2}"))

    result = render(Screen())
    assert renders == ["fixed", "tick 0"]

    result.act(lambda: setters[-1](1))
    assert renders == ["fixed", "tick 0"]

    result.act(lambda: setters[-1](2))
    assert renders == ["fixed", "tick 0", "tick 1"]
    assert result.text() == ["fixed", "tick 1"]


def test_memo_custom_comparator() -> None:
    renders: List[int] = []
    setters: List[StateSetter[int]] = []

    @pn.memo(equal=lambda old, new: old["value"] // 10 == new["value"] // 10)
    @pn.component
    def Bucket(value: int) -> pn.Node:
        renders.append(value)
        return pn.Text(str(value))

    @pn.component
    def Screen() -> pn.Node:
        value, set_value = pn.use_state(1)
        setters.append(set_value)
        return Bucket(value=value)

    result = render(Screen())
    result.act(lambda: setters[-1](5))
    result.act(lambda: setters[-1](12))
    assert renders == [1, 12]


# ======================================================================
# Context consumer registry
# ======================================================================


def test_provider_change_rerenders_only_consumers() -> None:
    probe = Probe()
    Leaf = probe.leaf()
    Consumer = probe.consumer()
    setters: List[StateSetter[int]] = []

    @pn.memo
    @pn.component
    def Middle() -> pn.Node:
        probe.renders["middle"] += 1
        return pn.Column(Leaf("inside"), Consumer("deep"))

    @pn.memo
    @pn.component
    def Sibling() -> pn.Node:
        probe.renders["sibling"] += 1
        return pn.Text("sibling")

    @pn.component
    def Root() -> pn.Node:
        value, set_value = pn.use_state(1)
        setters.append(set_value)
        return ValueContext.Provider(Sibling(), Middle(), Consumer("top"), value=value)

    result = render(Root())
    assert result.text() == ["sibling", "inside:0", "deep=1", "top=1"]

    result.act(lambda: setters[-1](2))

    assert result.text() == ["sibling", "inside:0", "deep=2", "top=2"]
    assert probe.renders == {"sibling": 1, "middle": 1, "inside": 1, "deep": 2, "top": 2}


def test_provider_with_an_equal_value_does_not_rerender_consumers() -> None:
    probe = Probe()
    Consumer = probe.consumer()
    setters: List[StateSetter[int]] = []

    @pn.memo
    @pn.component
    def Boundary() -> pn.Node:
        return Consumer("c")

    @pn.component
    def Root() -> pn.Node:
        tick, set_tick = pn.use_state(0)
        setters.append(set_tick)
        return ValueContext.Provider(pn.Text(str(tick)), Boundary(), value=7)

    result = render(Root())
    result.act(lambda: setters[-1](1))
    assert result.text() == ["1", "c=7"]
    assert probe.renders == {"c": 1}


def test_nested_providers_shadow_the_outer_value() -> None:
    probe = Probe()
    Consumer = probe.consumer()
    outer_setters: List[StateSetter[int]] = []
    inner_setters: List[StateSetter[int]] = []

    @pn.memo
    @pn.component
    def Box(label: str) -> pn.Node:
        return Consumer(label)

    @pn.component
    def Root() -> pn.Node:
        outer, set_outer = pn.use_state(1)
        inner, set_inner = pn.use_state(100)
        outer_setters.append(set_outer)
        inner_setters.append(set_inner)
        return ValueContext.Provider(
            Box(label="outer"),
            ValueContext.Provider(Box(label="inner"), value=inner),
            value=outer,
        )

    result = render(Root())
    assert result.text() == ["outer=1", "inner=100"]

    result.act(lambda: outer_setters[-1](2))
    assert result.text() == ["outer=2", "inner=100"]
    assert probe.renders == {"outer": 2, "inner": 1}

    # The outer consumer is behind a memo boundary and reads the outer provider only.
    result.act(lambda: inner_setters[-1](200))
    assert result.text() == ["outer=2", "inner=200"]
    assert probe.renders == {"outer": 2, "inner": 2}


def test_consumer_without_a_provider_reads_the_default() -> None:
    probe = Probe()
    result = render(probe.consumer()("lonely"))
    assert result.text() == ["lonely=0"]


def test_unmounted_consumers_are_ignored() -> None:
    probe = Probe()
    Consumer = probe.consumer()
    value_setters: List[StateSetter[int]] = []
    show_setters: List[StateSetter[bool]] = []

    @pn.memo
    @pn.component
    def Other() -> pn.Node:
        return Consumer("kept")

    @pn.component
    def Root() -> pn.Node:
        value, set_value = pn.use_state(1)
        show, set_show = pn.use_state(True)
        value_setters.append(set_value)
        show_setters.append(set_show)
        return ValueContext.Provider(show and Consumer("gone"), Other(), value=value)

    result = render(Root())
    assert result.text() == ["gone=1", "kept=1"]

    result.act(lambda: show_setters[-1](False))
    assert result.text() == ["kept=1"]
    gone_renders = probe.renders["gone"]

    result.act(lambda: value_setters[-1](2))
    assert result.text() == ["kept=2"]
    assert probe.renders["gone"] == gone_renders

    result.act(lambda: show_setters[-1](True))
    assert result.text() == ["gone=2", "kept=2"]


def test_remounted_consumer_under_a_new_provider_follows_it() -> None:
    probe = Probe()
    Consumer = probe.consumer()
    setters: List[StateSetter[int]] = []

    @pn.component
    def Root() -> pn.Node:
        value, set_value = pn.use_state(1)
        setters.append(set_value)
        if value % 2:
            return ValueContext.Provider(Consumer("c"), value=value)
        return pn.View(ValueContext.Provider(Consumer("c"), value=value))

    result = render(Root())
    result.act(lambda: setters[-1](2))
    result.act(lambda: setters[-1](3))
    assert result.text() == ["c=3"]


# ======================================================================
# Transition queue
# ======================================================================


def test_transition_queue_runs_every_trigger_then_reraises_the_first_error() -> None:
    queue = TransitionQueue()
    ran: List[str] = []

    def make(label: str, error: Exception | None = None) -> Callable[[], None]:
        def trigger() -> None:
            ran.append(label)
            if error is not None:
                raise error

        return trigger

    first = ValueError("first")
    queue.defer(make("a"))
    queue.defer(make("b", first))
    queue.defer(make("c", RuntimeError("second")))
    queue.defer(make("d"))
    queue.on_complete(make("done"))

    with pytest.raises(ValueError) as raised:
        queue.flush()

    assert raised.value is first
    assert ran == ["a", "b", "c", "d", "done"]
    assert not queue.pending


def test_transition_queue_dedupes_the_same_trigger() -> None:
    queue = TransitionQueue()
    ran: List[str] = []

    def trigger() -> None:
        ran.append("t")

    queue.defer(trigger)
    queue.defer(trigger)
    queue.flush()
    assert ran == ["t"]


def test_failing_transition_does_not_drop_other_transitions() -> None:
    setters: List[StateSetter[int]] = []
    starts: List[Callable[[Callable[[], None]], None]] = []

    @pn.component
    def Screen() -> pn.Node:
        a, set_a = pn.use_state(0)
        b, set_b = pn.use_state(0)
        _pending, start = pn.use_transition()
        setters[:] = [set_a, set_b]
        starts.append(start)
        return pn.Text(f"{a},{b}")

    result = render(Screen())
    queue = result.reconciler.transitions

    def bad_trigger() -> None:
        raise RuntimeError("bad trigger")

    queue.defer(bad_trigger)
    starts[-1](lambda: setters[0](lambda n: n + 1))
    starts[-1](lambda: setters[1](lambda n: n + 2))

    with pytest.raises(RuntimeError, match="bad trigger"):
        queue.flush()
    result.settle()

    assert result.text() == ["1,2"]
