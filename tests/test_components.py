"""Unit tests for the built-in element-creating functions."""

from pythonnative.components import (
    ActivityIndicator,
    Button,
    Column,
    ErrorBoundary,
    FlatList,
    Fragment,
    Image,
    Modal,
    Pressable,
    ProgressBar,
    Row,
    SafeAreaView,
    ScrollView,
    Slider,
    Spacer,
    Switch,
    Text,
    TextInput,
    View,
    WebView,
)
from pythonnative.element import ERROR_BOUNDARY, FRAGMENT
from pythonnative.style import AccessibilityState
from pythonnative.testing import FakeBackend

# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------


def test_text_defaults() -> None:
    el = Text()
    assert el.type == "Text"
    assert el.props.get("text", "") == ""
    assert el.children == []


def test_text_single_string_has_no_spans() -> None:
    el = Text("plain")
    assert el.props["text"] == "plain"
    assert "spans" not in el.props


def test_text_rich_spans_flatten_and_concatenate() -> None:
    el = Text(
        "Hello, ",
        Text("world", style={"bold": True, "color": "#0A84FF"}),
        "!",
    )
    assert el.props["text"] == "Hello, world!"
    spans = el.props["spans"]
    assert spans == [
        {"text": "Hello, "},
        {"text": "world", "bold": True, "color": "#0A84FF"},
        {"text": "!"},
    ]
    assert el.children == []  # spans are props, not native children


def test_text_nested_spans_inherit_and_override() -> None:
    el = Text(
        Text(
            "outer ",
            Text("inner", style={"italic": True}),
            style={"color": "#FF0000", "italic": False},
        ),
    )
    spans = el.props["spans"]
    assert spans[0] == {"text": "outer ", "color": "#FF0000", "italic": False}
    assert spans[1] == {"text": "inner", "color": "#FF0000", "italic": True}


def test_text_multiple_plain_strings_become_spans() -> None:
    el = Text("a", "b")
    assert el.props["text"] == "ab"
    assert el.props["spans"] == [{"text": "a"}, {"text": "b"}]


def test_text_with_style() -> None:
    el = Text("Hello", style={"font_size": 18, "color": "#FF0000", "bold": True, "text_align": "center"})
    assert el.props["text"] == "Hello"
    assert el.props["font_size"] == 18
    assert el.props["color"] == "#FF0000"
    assert el.props["bold"] is True
    assert el.props["text_align"] == "center"


def test_text_no_style_no_extra_props() -> None:
    el = Text("Hi")
    assert "font_size" not in el.props
    assert "color" not in el.props


def test_text_layout_via_style() -> None:
    el = Text("Hi", style={"width": 100, "height": 50, "flex": 1, "margin": 8, "align_self": "center"})
    assert el.props["width"] == 100
    assert el.props["height"] == 50
    assert el.props["flex"] == 1
    assert el.props["margin"] == 8
    assert el.props["align_self"] == "center"


def test_text_style_list() -> None:
    base = {"font_size": 16, "color": "#000"}
    override = {"color": "#FFF", "bold": True}
    el = Text("combo", style=[base, override])
    assert el.props["font_size"] == 16
    assert el.props["color"] == "#FFF"
    assert el.props["bold"] is True


# ---------------------------------------------------------------------------
# Button
# ---------------------------------------------------------------------------


def test_button_defaults() -> None:
    el = Button()
    assert el.type == "Button"
    assert el.props["title"] == ""
    assert "on_press" not in el.props


def test_button_with_callback() -> None:
    cb = lambda: None  # noqa: E731
    el = Button("Tap", on_press=cb, style={"background_color": "#123456"})
    assert el.props["title"] == "Tap"
    assert el.props["on_press"] is cb
    assert el.props["background_color"] == "#123456"


def test_button_disabled() -> None:
    el = Button("Off", enabled=False)
    assert el.props["enabled"] is False


# ---------------------------------------------------------------------------
# Column / Row
# ---------------------------------------------------------------------------


def test_column_with_children() -> None:
    el = Column(Text("a"), Text("b"), style={"spacing": 10, "padding": 16, "align_items": "stretch"})
    assert el.type == "Column"
    assert len(el.children) == 2
    assert el.props["spacing"] == 10
    assert el.props["padding"] == 16
    assert el.props["align_items"] == "stretch"
    assert el.props["flex_direction"] == "column"


def test_row_with_children() -> None:
    el = Row(Text("x"), Text("y"), style={"spacing": 5})
    assert el.type == "Row"
    assert len(el.children) == 2
    assert el.props["spacing"] == 5
    assert el.props["flex_direction"] == "row"


def test_column_no_style_has_flex_direction() -> None:
    el = Column()
    assert el.props == {"flex_direction": "column"}


def test_column_layout_via_style() -> None:
    el = Column(style={"flex": 2, "margin": {"horizontal": 8}})
    assert el.props["flex"] == 2
    assert el.props["margin"] == {"horizontal": 8}
    assert el.props["flex_direction"] == "column"


def test_column_justify_content() -> None:
    el = Column(style={"justify_content": "center", "align_items": "center"})
    assert el.props["justify_content"] == "center"
    assert el.props["align_items"] == "center"


def test_row_justify_content() -> None:
    el = Row(style={"justify_content": "space_between"})
    assert el.props["justify_content"] == "space_between"


def test_column_direction_cannot_be_overridden() -> None:
    el = Column(style={"flex_direction": "row"})
    assert el.props["flex_direction"] == "column"


def test_row_direction_cannot_be_overridden() -> None:
    el = Row(style={"flex_direction": "column"})
    assert el.props["flex_direction"] == "row"


# ---------------------------------------------------------------------------
# ScrollView
# ---------------------------------------------------------------------------


def test_scrollview_with_child() -> None:
    child = Column(Text("a"))
    el = ScrollView(child)
    assert el.type == "ScrollView"
    assert len(el.children) == 1
    assert el.children[0] is child


def test_scrollview_empty() -> None:
    el = ScrollView()
    assert el.children == []


# ---------------------------------------------------------------------------
# TextInput
# ---------------------------------------------------------------------------


def test_textinput_defaults() -> None:
    el = TextInput()
    assert el.type == "TextInput"
    assert el.props["value"] == ""


def test_textinput_with_props() -> None:
    cb = lambda s: None  # noqa: E731
    el = TextInput(value="hi", placeholder="type...", on_change=cb, secure=True)
    assert el.props["value"] == "hi"
    assert el.props["placeholder"] == "type..."
    assert el.props["on_change"] is cb
    assert el.props["secure"] is True


# ---------------------------------------------------------------------------
# Other leaf components
# ---------------------------------------------------------------------------


def test_image() -> None:
    el = Image("icon.png", style={"width": 48, "height": 48})
    assert el.type == "Image"
    assert el.props["source"] == "icon.png"
    assert el.props["width"] == 48


def test_switch() -> None:
    el = Switch(value=True)
    assert el.type == "Switch"
    assert el.props["value"] is True


def test_progress_bar() -> None:
    el = ProgressBar(value=0.5)
    assert el.type == "ProgressBar"
    assert el.props["value"] == 0.5


def test_activity_indicator() -> None:
    el = ActivityIndicator(animating=False)
    assert el.type == "ActivityIndicator"
    assert el.props["animating"] is False


def test_webview() -> None:
    el = WebView(url="https://example.com")
    assert el.type == "WebView"
    assert el.props["url"] == "https://example.com"


def test_spacer() -> None:
    el = Spacer(size=20)
    assert el.type == "Spacer"
    assert el.props["size"] == 20


def test_spacer_empty() -> None:
    el = Spacer()
    assert el.type == "Spacer"
    assert el.props == {}


# ---------------------------------------------------------------------------
# Key support
# ---------------------------------------------------------------------------


def test_key_propagation() -> None:
    el = Text("keyed", key="k1")
    assert el.key == "k1"


def test_column_key() -> None:
    el = Column(key="col-1")
    assert el.key == "col-1"


# ---------------------------------------------------------------------------
# View (flex container)
# ---------------------------------------------------------------------------


def test_view_container() -> None:
    child = Text("inside")
    el = View(child, style={"background_color": "#FFF", "padding": 8, "width": 200})
    assert el.type == "View"
    assert len(el.children) == 1
    assert el.props["background_color"] == "#FFF"
    assert el.props["padding"] == 8
    assert el.props["width"] == 200
    assert el.props["flex_direction"] == "column"


def test_view_default_direction_column() -> None:
    el = View()
    assert el.props["flex_direction"] == "column"


def test_view_direction_override() -> None:
    el = View(style={"flex_direction": "row"})
    assert el.props["flex_direction"] == "row"


def test_view_flex_props() -> None:
    el = View(
        Text("a"),
        style={
            "flex_direction": "row",
            "justify_content": "space_between",
            "align_items": "center",
            "overflow": "hidden",
        },
    )
    assert el.props["flex_direction"] == "row"
    assert el.props["justify_content"] == "space_between"
    assert el.props["align_items"] == "center"
    assert el.props["overflow"] == "hidden"


def test_view_flex_grow_shrink() -> None:
    el = Text("flex child", style={"flex_grow": 1, "flex_shrink": 0})
    assert el.props["flex_grow"] == 1
    assert el.props["flex_shrink"] == 0


# ---------------------------------------------------------------------------
# Other containers
# ---------------------------------------------------------------------------


def test_safe_area_view() -> None:
    el = SafeAreaView(Text("safe"), style={"background_color": "#000"})
    assert callable(el.type)  # hook-driven composite
    assert len(el.children) == 1
    assert el.props["style"]["background_color"] == "#000"


def test_modal() -> None:
    cb = lambda: None  # noqa: E731
    el = Modal(Text("content"), visible=True, on_dismiss=cb, title="Alert")
    assert el.type == "Modal"
    assert el.props["visible"] is True
    assert el.props["on_dismiss"] is cb
    assert el.props["title"] == "Alert"
    assert len(el.children) == 1


def test_slider() -> None:
    cb = lambda v: None  # noqa: E731
    el = Slider(value=0.5, min_value=0, max_value=10, on_change=cb)
    assert el.type == "Slider"
    assert el.props["value"] == 0.5
    assert el.props["min_value"] == 0
    assert el.props["max_value"] == 10
    assert el.props["on_change"] is cb


def test_pressable() -> None:
    cb = lambda: None  # noqa: E731
    child = Text("tap me")
    el = Pressable(child, on_press=cb)
    assert el.type == "Pressable"
    assert el.props["on_press"] is cb
    assert len(el.children) == 1


def _mount(el):  # type: ignore[no-untyped-def]
    from pythonnative.reconciler import Reconciler

    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.on_render_requested = lambda: None
    root = rec.mount(el)
    return root, rec, backend


def test_flat_list_basic() -> None:
    el = FlatList(
        data=["a", "b", "c"],
        render_item=lambda item, i: Text(item),
    )
    # FlatList is a virtualized function component; mounting it renders
    # a ScrollView whose window contains every (small-list) row.
    assert callable(el.type)
    root, _rec, _backend = _mount(el)
    assert root.type_name == "ScrollView"
    texts = [v.props["text"] for v in root.find_all("Text")]
    assert texts == ["a", "b", "c"]


def test_flat_list_with_keys() -> None:
    el = FlatList(
        data=[{"id": "x", "name": "X"}, {"id": "y", "name": "Y"}],
        render_item=lambda item, i: Text(item["name"]),
        key_extractor=lambda item, i: item["id"],
    )
    rows = el.props["rows"]
    assert [r.key for r in rows] == ["x", "y"]


def test_flat_list_empty() -> None:
    el = FlatList(data=[], render_item=lambda item, i: Text(str(item)))
    root, _rec, _backend = _mount(el)
    assert root.find_all("Text") == []


def test_spacer_flex() -> None:
    el = Spacer(flex=1)
    assert el.props["flex"] == 1


# ======================================================================
# ErrorBoundary
# ======================================================================


def test_error_boundary_creates_element() -> None:
    child = Text("risky")
    fallback = Text("error")
    el = ErrorBoundary(child, fallback=fallback)
    assert el.type == ERROR_BOUNDARY
    assert el.props["fallback"] is fallback
    assert len(el.children) == 1
    assert el.children[0] is child


def test_error_boundary_callable_fallback() -> None:
    fn = lambda exc: Text(str(exc))  # noqa: E731
    el = ErrorBoundary(Text("risky"), fallback=fn)
    assert callable(el.props["fallback"])


def test_error_boundary_no_child() -> None:
    el = ErrorBoundary(fallback=Text("empty"))
    assert len(el.children) == 0


def test_error_boundary_with_key() -> None:
    el = ErrorBoundary(Text("x"), fallback=Text("err"), key="eb1")
    assert el.key == "eb1"


# ======================================================================
# Fragment
# ======================================================================


def test_fragment_no_children() -> None:
    el = Fragment()
    assert el.type == FRAGMENT
    assert el.children == []
    assert el.props == {}


def test_fragment_with_children() -> None:
    a = Text("a")
    b = Text("b")
    el = Fragment(a, b)
    assert el.type == FRAGMENT
    assert el.children == [a, b]


def test_fragment_with_key() -> None:
    el = Fragment(Text("a"), key="frag1")
    assert el.key == "frag1"
    assert "key" not in el.props


def test_fragment_drops_none_children() -> None:
    a = Text("a")
    c = Text("c")
    el = Fragment(a, None, c, None)
    assert el.children == [a, c]


# ======================================================================
# test_id / accessibility_state / accessibility_live_region
# ======================================================================


def test_test_id_and_accessibility_state_flow_into_props() -> None:
    state: AccessibilityState = {"disabled": True, "checked": False}
    el = Button(
        "Go",
        test_id="go_button",
        accessibility_state=state,
        accessibility_live_region="polite",
    )
    assert el.props["test_id"] == "go_button"
    assert el.props["accessibility_state"] == state
    assert el.props["accessibility_live_region"] == "polite"


def test_test_id_omitted_when_not_set() -> None:
    el = Button("Go")
    assert "test_id" not in el.props
    assert "accessibility_state" not in el.props
    assert "accessibility_live_region" not in el.props


# ======================================================================
# Pressable state-based styles
# ======================================================================


def test_pressable_static_style_stays_plain_element() -> None:
    el = Pressable(Text("tap"), style={"padding": 8})
    assert el.type == "Pressable"
    assert el.props["padding"] == 8


def test_pressable_callable_style_tracks_pressed_state() -> None:
    from pythonnative.events import dispatch_event
    from pythonnative.reconciler import Reconciler

    el = Pressable(
        Text("tap"),
        style=lambda s: {"background_color": "#222222" if s["pressed"] else "#EEEEEE"},
    )
    assert callable(el.type)  # stateful composite

    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.on_render_requested = lambda: None
    rec.mount(el)

    tag, view = next((t, v) for t, v in backend.views.items() if v.type_name == "Pressable")
    assert view.props["background_color"] == "#EEEEEE"

    assert dispatch_event(tag, "on_press_in") is True
    rec.flush_dirty()
    view = next(v for v in backend.views.values() if v.type_name == "Pressable")
    assert view.props["background_color"] == "#222222"

    dispatch_event(tag, "on_press_out")
    rec.flush_dirty()
    view = next(v for v in backend.views.values() if v.type_name == "Pressable")
    assert view.props["background_color"] == "#EEEEEE"


def test_pressable_callable_style_forwards_user_press_callbacks() -> None:
    from pythonnative.events import dispatch_event
    from pythonnative.reconciler import Reconciler

    calls = []
    el = Pressable(
        Text("tap"),
        style=lambda s: {"padding": 4},
        on_press_in=lambda: calls.append("in"),
        on_press_out=lambda: calls.append("out"),
    )
    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.on_render_requested = lambda: None
    rec.mount(el)

    tag = next(t for t, v in backend.views.items() if v.type_name == "Pressable")
    dispatch_event(tag, "on_press_in")
    dispatch_event(tag, "on_press_out")
    assert calls == ["in", "out"]
