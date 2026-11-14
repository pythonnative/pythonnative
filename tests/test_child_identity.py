"""Child identity: slots, holes, and groups (RFC 0010).

Each entry of a child list occupies a slot. ``None`` and ``False`` keep
their slot, a list is a group whose items are matched among themselves,
and a fragment is a node of its own. These tests pin the identity rule,
and check after each update that the native tree the ops produced
matches a fresh mount of the same element.
"""

from __future__ import annotations

import itertools
import random
from typing import Any, Callable, Iterator, List, Optional

import pytest

import pythonnative as pn
from pythonnative import diagnostics
from pythonnative.testing import render

_ids = itertools.count(1)


@pn.component
def Stateful(label: str) -> pn.Node:
    """Shows its label and an identity fixed at mount, so a remount is visible."""
    ident = pn.use_memo(lambda: next(_ids), [])
    return pn.Text(f"{label}#{ident}")


def native_tree(result: Any) -> List[Any]:
    """The fake native views in document order, by type and text."""

    def visit(view: Any) -> Iterator[Any]:
        yield (view.type_name, view.props.get("text"))
        for child in view.children:
            yield from visit(child)

    root = result.backend.views.get(result.reconciler.root_tag)
    return list(visit(root)) if root is not None else []


def identities(result: Any) -> dict[str, str]:
    """Label to mount identity for every ``Stateful`` on screen."""
    out = {}
    for text in result.text():
        if "#" in text:
            label, ident = text.split("#")
            out[label] = ident
    return out


def assert_matches_fresh_mount(result: Any, element: pn.Element) -> None:
    fresh = render(element)
    try:
        assert [kind for kind, _ in native_tree(result)] == [kind for kind, _ in native_tree(fresh)]
        strip = [text.split("#")[0] if text else text for _, text in native_tree(result)]
        fresh_strip = [text.split("#")[0] if text else text for _, text in native_tree(fresh)]
        assert strip == fresh_strip
    finally:
        fresh.unmount()


# ----------------------------------------------------------------------
# Holes
# ----------------------------------------------------------------------


@pytest.mark.parametrize("hole", [None, False, True])
def test_a_falsy_child_keeps_its_slot_so_siblings_keep_their_state(hole: Any) -> None:
    def tree(show: bool) -> pn.Element:
        return pn.Column(pn.Text("banner") if show else hole, Stateful("field"), Stateful("results"))

    result = render(tree(False))
    before = identities(result)
    for show in (True, False, True):
        result.rerender(tree(show))
        assert identities(result) == before
        assert_matches_fresh_mount(result, tree(show))
    assert result.text()[0] == "banner"


def test_a_conditional_component_beside_a_stateful_one() -> None:
    @pn.component
    def Screen(query: str) -> pn.Node:
        return pn.Column(pn.Button("Clear") if query else None, Stateful("search"), Stateful("footer"))

    result = render(Screen(""))
    before = identities(result)
    result.rerender(Screen("abc"))
    assert identities(result) == before
    assert result.text()[0] == "Clear"
    result.rerender(Screen(""))
    assert identities(result) == before


def test_a_hole_in_a_component_return_value_keeps_its_slot() -> None:
    @pn.component
    def Rows(first: bool) -> pn.Node:
        return [first and pn.Text("first"), Stateful("second")]

    result = render(pn.Column(Rows(False)))
    before = identities(result)
    result.rerender(pn.Column(Rows(True)))
    assert identities(result) == before
    assert result.text() == ["first", f"second#{before['second']}"]


# ----------------------------------------------------------------------
# Groups
# ----------------------------------------------------------------------


def test_a_growing_group_never_shifts_a_stateful_sibling_after_it() -> None:
    def tree(count: int) -> pn.Element:
        return pn.Column(
            pn.Text("header"),
            [pn.Text(f"row {i}", key=str(i)) for i in range(count)],
            Stateful("footer"),
        )

    result = render(tree(1))
    before = identities(result)
    for count in (3, 0, 5, 2):
        result.rerender(tree(count))
        assert identities(result) == before
        assert result.text()[1 : 1 + count] == [f"row {i}" for i in range(count)]
        assert_matches_fresh_mount(result, tree(count))


def test_unkeyed_group_items_match_by_index_within_the_group() -> None:
    def tree(labels: List[str]) -> pn.Element:
        return pn.Column([Stateful(label) for label in labels], Stateful("after"))

    with _release():
        result = render(tree(["a", "b"]))
        first = identities(result)
        result.rerender(tree(["a", "b", "c"]))
        after = identities(result)
    assert after["a"] == first["a"] and after["b"] == first["b"] and after["after"] == first["after"]


def test_keyed_items_move_within_their_group() -> None:
    def tree(order: List[str]) -> pn.Element:
        return pn.Column(Stateful("head"), [Stateful(label).with_key(label) for label in order])

    result = render(tree(["a", "b", "c"]))
    before = identities(result)
    result.rerender(tree(["c", "a", "b"]))
    assert identities(result) == before
    assert [text.split("#")[0] for text in result.text()] == ["head", "c", "a", "b"]
    assert_matches_fresh_mount(result, tree(["c", "a", "b"]))


def test_a_keyed_child_matches_its_old_node_in_any_slot() -> None:
    def tree(lead: bool) -> pn.Element:
        if lead:
            return pn.Column(Stateful("x").with_key("x"), pn.Text("tail"))
        return pn.Column(pn.Text("head"), pn.Text("middle"), Stateful("x").with_key("x"))

    result = render(tree(False))
    before = identities(result)
    result.rerender(tree(True))
    assert identities(result) == before
    assert_matches_fresh_mount(result, tree(True))


def test_nested_groups_and_generators() -> None:
    def tree(outer: int, inner: int) -> pn.Element:
        return pn.Column(
            [[pn.Text(f"{o}.{i}", key=f"{o}.{i}") for i in range(inner)] for o in range(outer)],
            (pn.Text(f"gen {n}", key=str(n)) for n in range(inner)),
            Stateful("last"),
        )

    result = render(tree(2, 2))
    before = identities(result)
    for outer, inner in ((3, 1), (1, 3), (0, 0), (2, 2)):
        result.rerender(tree(outer, inner))
        assert identities(result) == before
        assert_matches_fresh_mount(result, tree(outer, inner))


def test_spreading_still_fills_separate_slots() -> None:
    def tree(count: int) -> pn.Element:
        return pn.Column(*[pn.Text(f"row {i}") for i in range(count)], Stateful("footer"))

    with _release():
        result = render(tree(1))
        before = identities(result)
        result.rerender(tree(2))
        after = identities(result)
    assert after["footer"] != before["footer"], "a spread list shifts later slots, as in React"


# ----------------------------------------------------------------------
# Fragments and component return values
# ----------------------------------------------------------------------


def test_an_unkeyed_fragment_is_a_node_of_its_own() -> None:
    def tree(extra: bool) -> pn.Element:
        return pn.Column(
            pn.Fragment(pn.Text("a"), extra and pn.Text("extra"), Stateful("inside")),
            Stateful("outside"),
        )

    result = render(tree(False))
    before = identities(result)
    result.rerender(tree(True))
    assert identities(result) == before
    assert [text.split("#")[0] for text in result.text()] == ["a", "extra", "inside", "outside"]
    assert_matches_fresh_mount(result, tree(True))


def test_a_component_returning_a_list_or_none() -> None:
    @pn.component
    def Maybe(mode: str) -> pn.Node:
        if mode == "none":
            return None
        if mode == "one":
            return Stateful("one")
        return [Stateful("one"), pn.Text("two")]

    def tree(mode: str) -> pn.Element:
        return pn.Column(Maybe(mode), Stateful("sibling"))

    result = render(tree("list"))
    before = identities(result)
    result.rerender(tree("one"))
    assert identities(result) == before
    result.rerender(tree("none"))
    assert identities(result) == {"sibling": before["sibling"]}
    result.rerender(tree("list"))
    assert identities(result)["sibling"] == before["sibling"]
    assert_matches_fresh_mount(result, tree("list"))


def test_state_driven_updates_keep_native_order() -> None:
    setters: List[Callable[[Any], None]] = []

    @pn.component
    def Toggle() -> pn.Node:
        shown, set_shown = pn.use_state(False)
        setters[:] = [set_shown]
        return [shown and pn.Text("revealed"), pn.Text("always")]

    result = render(pn.Column(pn.Text("before"), Toggle(), pn.Text("after")))
    setters[0](True)
    result.settle()
    assert result.text() == ["before", "revealed", "always", "after"]
    setters[0](False)
    result.settle()
    assert result.text() == ["before", "always", "after"]


# ----------------------------------------------------------------------
# Equivalence with a fresh mount
# ----------------------------------------------------------------------


def _random_children(rng: random.Random, depth: int) -> List[Any]:
    entries: List[Any] = []
    for index in range(rng.randint(0, 4)):
        roll = rng.random()
        if roll < 0.15:
            entries.append(None)
        elif roll < 0.25:
            entries.append(False)
        elif roll < 0.4 and depth < 3:
            entries.append([pn.Text(f"k{key}", key=f"k{key}") for key in rng.sample(range(6), rng.randint(0, 4))])
        elif roll < 0.5 and depth < 3:
            entries.append(pn.Fragment(*_random_children(rng, depth + 1)))
        elif roll < 0.65 and depth < 3:
            entries.append(pn.Row(*_random_children(rng, depth + 1)))
        elif roll < 0.8:
            entries.append(Stateful(f"s{index}"))
        else:
            entries.append(pn.Text(f"t{rng.randint(0, 3)}"))
    return entries


@pytest.mark.parametrize("seed", range(40))
def test_random_updates_match_a_fresh_mount(seed: int) -> None:
    rng = random.Random(seed)
    with _release():
        result = render(pn.Column(*_random_children(rng, 0)))
        for _ in range(6):
            element = pn.Column(*_random_children(rng, 0))
            result.rerender(element)
            assert_matches_fresh_mount(result, element)
        result.unmount()


class _release:
    """Render in release mode (no development warnings) for the duration of a block."""

    def __enter__(self) -> None:
        self.previous: Optional[bool] = diagnostics.is_dev()
        diagnostics.set_dev_mode(False)

    def __exit__(self, *exc: Any) -> None:
        diagnostics.set_dev_mode(bool(self.previous))
