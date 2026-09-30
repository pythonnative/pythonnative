"""Tests for authoring rules: keys, positional children, and dev-mode prop checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterator, List, Literal, Mapping, Optional, Sequence

import pytest

import pythonnative as pn
from pythonnative import diagnostics
from pythonnative.hooks import StateSetter
from pythonnative.testing import render

# ======================================================================
# Keys
# ======================================================================


@pn.component
def Row(label: str) -> pn.Node:
    return pn.Text(label)


def test_with_key_returns_a_keyed_copy() -> None:
    element = Row("a")
    keyed = element.with_key("k")
    assert keyed.key == "k"
    assert element.key is None
    assert keyed.props == element.props
    assert keyed.type is element.type


def test_with_key_stringifies_non_string_keys_and_none_clears() -> None:
    assert Row("a").with_key(3).key == "3"
    assert Row("a").with_key("x").with_key(None).key is None


def test_user_component_rejects_key_keyword() -> None:
    with pytest.raises(TypeError, match="with_key"):
        Row("a", key="x")  # type: ignore[call-arg]


def test_user_component_may_not_declare_a_key_parameter() -> None:
    def Keyed(key: str) -> pn.Node:
        return None

    with pytest.raises(TypeError, match="'key'"):
        pn.component(Keyed)


def test_builtin_factories_keep_key() -> None:
    assert pn.Text("x", key="a").key == "a"
    assert pn.Column(key="c").key == "c"
    assert pn.View(pn.Text("x"), key="v").key == "v"


def test_list_components_accept_key() -> None:
    flat = pn.FlatList(data=[1, 2], render_item=lambda item, index: pn.Text(str(item)), key="k")
    assert flat.key == "k"
    assert "key" not in flat.props

    sections = pn.SectionList(sections=[], key="s")
    assert sections.key == "s"
    assert "key" not in sections.props


def test_keyed_rows_keep_state_across_reorders() -> None:
    setters: List[StateSetter[List[str]]] = []

    @pn.component
    def Counter(label: str) -> pn.Node:
        count, set_count = pn.use_state(0)
        return pn.Button(f"{label}:{count}", on_press=lambda: set_count(count + 1))

    @pn.component
    def Rows() -> pn.Node:
        order, set_order = pn.use_state(["a", "b"])
        setters.append(set_order)
        return pn.Column(*(Counter(label).with_key(label) for label in order))

    result = render(Rows())
    result.press(result.get_by_text("b:0"))
    result.act(lambda: setters[-1](["b", "a"]))
    assert result.text() == ["b:1", "a:0"]


# ======================================================================
# Children
# ======================================================================


def test_containers_skip_none_and_booleans() -> None:
    flag = False
    result = render(
        pn.Column(
            pn.Text("first"),
            None,
            False,
            True,
            flag and pn.Text("hidden"),
            pn.Text("shown") if not flag else None,
        )
    )
    assert result.text() == ["first", "shown"]


def test_containers_flatten_nested_lists_and_generators() -> None:
    result = render(
        pn.Column(
            [pn.Text("a"), [pn.Text("b"), None]],
            (pn.Text(label).with_key(label) for label in ("c", "d")),
            pn.Text("e"),
        )
    )
    assert result.text() == ["a", "b", "c", "d", "e"]


def test_component_children_pass_through() -> None:
    @pn.component
    def Card(*children: pn.Node, title: str = "") -> pn.Node:
        return pn.Column(pn.Text(title), *children)

    result = render(Card(pn.Text("body"), None, [pn.Text("more")], title="Hello"))
    assert result.text() == ["Hello", "body", "more"]


def test_generator_children_survive_a_rerender() -> None:
    setters: List[StateSetter[int]] = []

    @pn.component
    def Card(*children: pn.Node) -> pn.Node:
        count, set_count = pn.use_state(0)
        setters.append(set_count)
        return pn.Column(pn.Text(f"count={count}"), *children)

    @pn.component
    def App() -> pn.Node:
        return Card(pn.Text(f"item{i}").with_key(str(i)) for i in range(3))

    result = render(App())
    assert result.text() == ["count=0", "item0", "item1", "item2"]

    result.act(lambda: setters[-1](1))
    assert result.text() == ["count=1", "item0", "item1", "item2"]


def test_component_may_return_a_list_or_none() -> None:
    @pn.component
    def Pair() -> pn.Node:
        return [pn.Text("x").with_key("x"), pn.Text("y").with_key("y")]

    @pn.component
    def Nothing() -> pn.Node:
        return None

    result = render(pn.Column(Pair(), Nothing()))
    assert result.text() == ["x", "y"]


# ======================================================================
# Dev-mode prop checks
# ======================================================================


class Mode:
    pass


@dataclass
class Item:
    id: int


@pn.component
def Card(title: str, count: int = 0) -> pn.Node:
    return pn.Text(f"{title}:{count}")


@pn.component
def Scaled(factor: float, label: Optional[str] = None) -> pn.Node:
    return None


@pn.component
def Sized(size: Literal["small", "large"] = "small") -> pn.Node:
    return None


@pn.component
def Extra(title: str, **rest: Any) -> pn.Node:
    return None


@pn.component
def Rich(
    items: Sequence[int],
    meta: Mapping[str, int],
    on_press: Callable[[], None],
    item: Item,
    mode: Mode,
    either: int | str,
) -> pn.Node:
    return None


@pytest.fixture
def warnings() -> Iterator[List[str]]:
    diagnostics.clear_warnings()
    yield diagnostics.get_warnings()
    diagnostics.clear_warnings()


def _prop_warnings() -> List[str]:
    return [w for w in diagnostics.get_warnings() if "doesn't match its annotation" in w]


def _untyped(value: Any) -> Any:
    """Hide a value's type from mypy, as an untyped caller would."""
    return value


@pytest.mark.usefixtures("warnings")
def test_mismatched_prop_warns_once() -> None:
    Card(title=_untyped(1))
    Card(title=_untyped(2))

    found = _prop_warnings()
    assert len(found) == 1
    assert "Card()" in found[0]
    assert "title=1" in found[0]
    assert "str" in found[0]


@pytest.mark.usefixtures("warnings")
def test_mismatch_on_another_parameter_warns_separately() -> None:
    Card(title=_untyped(1), count=_untyped("x"))
    assert len(_prop_warnings()) == 2


@pytest.mark.usefixtures("warnings")
def test_matching_props_do_not_warn() -> None:
    Card(title="ok", count=3)
    Card("positional")
    Scaled(factor=1)
    Scaled(factor=1.5, label=None)
    Scaled(factor=2, label="x")
    Sized(size="large")
    Extra(title="t", anything=object(), other=1)
    Rich(
        items=[1, 2],
        meta={"a": 1},
        on_press=lambda: None,
        item=Item(id=1),
        mode=Mode(),
        either="s",
    )
    assert _prop_warnings() == []


@pytest.mark.usefixtures("warnings")
def test_bool_is_not_an_int_and_float_rejects_str() -> None:
    Card(title="t", count=_untyped(True))
    Scaled(factor=_untyped("1.0"))
    assert len(_prop_warnings()) == 2


@pytest.mark.usefixtures("warnings")
def test_optional_and_literal_mismatches_warn() -> None:
    Scaled(factor=1, label=_untyped(3))
    Sized(size=_untyped("medium"))
    found = _prop_warnings()
    assert len(found) == 2
    assert any("size='medium'" in w for w in found)


@pytest.mark.usefixtures("warnings")
def test_structured_mismatches_warn() -> None:
    Rich(
        items=_untyped(5),
        meta=_untyped([1]),
        on_press=_untyped("not callable"),
        item=_untyped({"id": 1}),
        mode=_untyped(None),
        either=_untyped(1.5),
    )
    assert len(_prop_warnings()) == 6


@pytest.mark.usefixtures("warnings")
def test_kwargs_parameters_are_not_checked() -> None:
    Extra(title="t", title2=1, anything=None)
    assert _prop_warnings() == []


@pytest.mark.usefixtures("warnings")
def test_unevaluable_annotations_are_skipped() -> None:
    def Broken(value: int) -> pn.Node:
        return None

    Broken.__annotations__ = {"value": "NoSuchName", "return": "pn.Node"}
    component = pn.component(Broken)
    component(value=_untyped("anything"))
    assert _prop_warnings() == []


@pytest.mark.usefixtures("warnings")
def test_no_prop_checks_outside_dev_mode() -> None:
    diagnostics.set_dev_mode(False)
    try:
        Card(title=_untyped(1))
    finally:
        diagnostics.set_dev_mode(True)
    assert diagnostics.get_warnings() == []


@pytest.mark.usefixtures("warnings")
def test_prop_checks_use_each_components_own_annotations() -> None:
    # Components built from short-lived functions must never be checked
    # against another function's annotations.
    for index in range(50):
        if index % 2:

            def Probe(value: int) -> pn.Node:
                return None

            pn.component(Probe)(value=1)
        else:

            def Other(value: str) -> pn.Node:
                return None

            pn.component(Other)(value="x")
    assert _prop_warnings() == []


@pytest.mark.usefixtures("warnings")
def test_prop_mismatch_does_not_raise_and_still_renders() -> None:
    result = render(Card(title=_untyped(7)))
    assert result.text() == ["7:0"]
    assert len(_prop_warnings()) == 1
