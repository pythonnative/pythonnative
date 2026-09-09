"""Unit tests for Element descriptors."""

from pythonnative.element import Element


def test_element_creation() -> None:
    el = Element("Text", {"text": "hello"}, [])
    assert el.type == "Text"
    assert el.props == {"text": "hello"}
    assert el.children == ()
    assert el.key is None


def test_element_with_key() -> None:
    el = Element("Text", {}, [], key="abc")
    assert el.key == "abc"


def test_element_with_children() -> None:
    child1 = Element("Text", {"text": "a"}, [])
    child2 = Element("Text", {"text": "b"}, [])
    parent = Element("Column", {}, [child1, child2])
    assert len(parent.children) == 2
    assert parent.children[0].props["text"] == "a"
    assert parent.children[1].props["text"] == "b"


def test_element_equality() -> None:
    a = Element("Text", {"text": "hi"}, [])
    b = Element("Text", {"text": "hi"}, [])
    assert a == b


def test_element_inequality_type() -> None:
    a = Element("Text", {"text": "hi"}, [])
    b = Element("Button", {"text": "hi"}, [])
    assert a != b


def test_element_inequality_props() -> None:
    a = Element("Text", {"text": "hi"}, [])
    b = Element("Text", {"text": "bye"}, [])
    assert a != b


def test_element_inequality_children() -> None:
    child = Element("Text", {}, [])
    a = Element("Column", {}, [child])
    b = Element("Column", {}, [])
    assert a != b


def test_element_not_equal_to_other_types() -> None:
    el = Element("Text", {}, [])
    assert el != "not an element"
    assert el != 42


def test_element_repr() -> None:
    el = Element("Button", {"title": "ok"}, [])
    r = repr(el)
    assert "Button" in r
    assert "children=0" in r


def test_deeply_nested_equality() -> None:
    leaf = Element("Text", {"text": "x"}, [])
    mid = Element("Row", {}, [leaf])
    root_a = Element("Column", {}, [mid])
    root_b = Element("Column", {}, [Element("Row", {}, [Element("Text", {"text": "x"}, [])])])
    assert root_a == root_b
