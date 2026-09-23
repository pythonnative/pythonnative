"""Unit tests for the breadth expansion: new components and the new
props added to existing components.

These assert the Element shape produced by each factory (type, props,
children, dropped ``None`` defaults), which is the platform-agnostic
contract the native handlers consume.
"""

from __future__ import annotations

import pytest

from pythonnative.components import (
    ActivityIndicator,
    Checkbox,
    DatePicker,
    FlatList,
    Image,
    ImageBackground,
    Modal,
    Pressable,
    PressState,
    ProgressBar,
    Ripple,
    ScrollView,
    SegmentedControl,
    StatusBar,
    Text,
    TextInput,
    TouchableOpacity,
    View,
    WebView,
)
from pythonnative.components._base import _SpanPressDispatcher

# ======================================================================
# TouchableOpacity
# ======================================================================


def test_touchable_opacity_is_pressable_with_active_opacity() -> None:
    cb = lambda: None  # noqa: E731
    el = TouchableOpacity(Text("Tap"), on_press=cb, active_opacity=0.3)
    assert el.type == "Pressable"
    assert el.props["pressed_opacity"] == 0.3
    assert el.props["on_press"] is cb
    assert el.props["accessibility_role"] == "button"
    assert len(el.children) == 1


def test_touchable_opacity_disabled_forwards_disabled_and_dims() -> None:
    cb = lambda: None  # noqa: E731
    el = TouchableOpacity(Text("Tap"), on_press=cb, disabled=True)
    assert el.props["disabled"] is True
    assert el.props["accessibility_state"] == {"disabled": True}
    assert el.props["opacity"] == 0.4


# ======================================================================
# Pressable: disabled, delay, ripple, callable child
# ======================================================================


def test_pressable_disabled_sets_prop_and_accessibility_state() -> None:
    el = Pressable(Text("Save"), on_press=lambda: None, disabled=True)
    assert el.props["disabled"] is True
    assert el.props["accessibility_state"] == {"disabled": True}
    # The user's explicit state wins.
    el2 = Pressable(Text("Save"), disabled=True, accessibility_state={"selected": True})
    assert el2.props["accessibility_state"] == {"selected": True}
    assert "disabled" not in Pressable(Text("Save")).props


def test_pressable_delay_long_press_and_ripple() -> None:
    el = Pressable(Text("Hold"), delay_long_press=400, android_ripple=Ripple(color="#33000000", borderless=True))
    assert el.props["delay_long_press"] == 400
    assert el.props["android_ripple"] == {"color": "#33000000", "borderless": True, "radius": None, "foreground": False}
    assert "delay_long_press" not in Pressable(Text("Hold")).props
    with pytest.raises(TypeError, match="pn.Ripple"):
        Pressable(Text("Hold"), android_ripple={"color": "#000"})  # type: ignore[arg-type]


def test_pressable_callable_child_becomes_stateful_composite() -> None:
    el = Pressable(lambda state: Text("Pressed" if state.pressed else "Idle"), on_press=lambda: None)
    assert callable(el.type)
    assert el.children == ()
    with pytest.raises(TypeError, match="single callable child"):
        Pressable(Text("a"), lambda state: Text("b"))


def test_press_state_is_frozen() -> None:
    state = PressState(pressed=True)
    assert state.pressed is True
    with pytest.raises(Exception):
        state.pressed = False  # type: ignore[misc]


# ======================================================================
# Text: truncation, selection, pressable spans
# ======================================================================


def test_text_truncation_and_selection_props() -> None:
    on_press = lambda: None  # noqa: E731
    el = Text("Hello", ellipsize_mode="middle", selectable=True, allow_font_scaling=False, on_press=on_press)
    assert el.props["ellipsize_mode"] == "middle"
    assert el.props["selectable"] is True
    assert el.props["allow_font_scaling"] is False
    assert el.props["on_press"] is on_press
    plain = Text("Hello")
    for key in ("ellipsize_mode", "selectable", "allow_font_scaling", "on_press", "on_span_press"):
        assert key not in plain.props


def test_text_nested_span_press_is_flagged_and_routed_by_index() -> None:
    pressed: list = []
    el = Text(
        "Read the ",
        Text("terms", on_press=lambda: pressed.append("terms"), style={"color": "#06F"}),
        " and ",
        Text("policy", on_press=lambda: pressed.append("policy")),
        ".",
    )
    spans = el.props["spans"]
    assert [s.get("pressable") for s in spans] == [None, True, None, True, None]
    assert spans[1] == {"text": "terms", "color": "#06F", "pressable": True}
    assert "on_press" not in el.props
    dispatcher = el.props["on_span_press"]
    assert isinstance(dispatcher, _SpanPressDispatcher)
    dispatcher(1)
    dispatcher(3)
    dispatcher(0)
    dispatcher(99)
    assert pressed == ["terms", "policy"]


def test_text_pressable_span_inherits_through_nesting() -> None:
    hits: list = []
    inner = Text("deep", on_press=lambda: hits.append("deep"))
    middle = Text("mid ", inner, on_press=lambda: hits.append("mid"))
    el = Text("outer ", middle)
    spans = el.props["spans"]
    assert [s["text"] for s in spans] == ["outer ", "mid ", "deep"]
    assert [s.get("pressable") for s in spans] == [None, True, True]
    el.props["on_span_press"](1)
    el.props["on_span_press"](2)
    assert hits == ["mid", "deep"]


# ======================================================================
# Accessibility surface shared by every view
# ======================================================================


def test_accessibility_value_actions_and_importance_flow_to_props() -> None:
    on_action = lambda _name: None  # noqa: E731
    el = View(
        accessibility_value={"min": 0, "max": 10, "now": 3},
        accessibility_actions=[{"name": "increment"}, {"name": "archive", "label": "Archive"}],
        on_accessibility_action=on_action,
        important_for_accessibility="no_hide_descendants",
    )
    assert el.props["accessibility_value"] == {"min": 0, "max": 10, "now": 3}
    assert el.props["accessibility_actions"] == [{"name": "increment"}, {"name": "archive", "label": "Archive"}]
    assert el.props["on_accessibility_action"] is on_action
    assert el.props["important_for_accessibility"] == "no_hide_descendants"
    assert Text("x", accessibility_value="3 of 10").props["accessibility_value"] == "3 of 10"
    plain = View()
    for key in ("accessibility_value", "accessibility_actions", "important_for_accessibility"):
        assert key not in plain.props


@pytest.mark.parametrize("factory", [Text, TextInput, Image, Checkbox, SegmentedControl, DatePicker])
def test_every_view_factory_accepts_the_accessibility_surface(factory) -> None:  # type: ignore[no-untyped-def]
    el = factory(
        accessibility_value="v",
        accessibility_actions=[{"name": "activate"}],
        on_accessibility_action=lambda _n: None,
        important_for_accessibility="yes",
    )
    assert el.props["accessibility_value"] == "v"
    assert el.props["important_for_accessibility"] == "yes"


# ======================================================================
# Image, StatusBar
# ======================================================================


def test_image_load_lifecycle_fade_and_headers() -> None:
    start = lambda: None  # noqa: E731
    end = lambda: None  # noqa: E731
    el = Image(
        "https://example.com/a.png",
        on_load_start=start,
        on_load_end=end,
        fade_duration=300,
        headers={"Authorization": "Bearer x"},
    )
    assert el.props["on_load_start"] is start
    assert el.props["on_load_end"] is end
    assert el.props["fade_duration"] == 300
    assert el.props["headers"] == {"Authorization": "Bearer x"}
    plain = Image("a.png")
    for key in ("on_load_start", "on_load_end", "fade_duration", "headers"):
        assert key not in plain.props


def test_status_bar_translucent_and_animated() -> None:
    el = StatusBar(translucent=True, animated=True)
    assert el.props == {"translucent": True, "animated": True}
    assert StatusBar().props == {}


# ======================================================================
# ImageBackground
# ======================================================================


def test_image_background_layers_image_then_content() -> None:
    el = ImageBackground(Text("Overlay"), source="bg.png")
    assert el.type == "View"
    assert len(el.children) == 2
    background, content = el.children
    assert background.type == "Image"
    assert background.props["source"] == "bg.png"
    assert background.props["scale_type"] == "cover"
    assert background.props["position"] == "absolute"
    assert background.props["top"] == 0
    assert content.type == "View"
    assert content.children[0].props["text"] == "Overlay"


def test_image_background_respects_explicit_scale_type() -> None:
    el = ImageBackground(source="bg.png", scale_type="contain")
    assert el.children[0].props["scale_type"] == "contain"


# ======================================================================
# Checkbox
# ======================================================================


def test_checkbox_props_and_default_role() -> None:
    cb = lambda _v: None  # noqa: E731
    el = Checkbox(value=True, on_change=cb, label="Accept", color="#FF0000")
    assert el.type == "Checkbox"
    assert el.props["value"] is True
    assert el.props["on_change"] is cb
    assert el.props["label"] == "Accept"
    assert el.props["color"] == "#FF0000"
    assert el.props["accessibility_role"] == "checkbox"


def test_checkbox_disabled_flag_dropped_when_false() -> None:
    el = Checkbox(value=False)
    assert "disabled" not in el.props
    assert el.props["value"] is False


# ======================================================================
# SegmentedControl
# ======================================================================


def test_segmented_control_props() -> None:
    cb = lambda _i: None  # noqa: E731
    el = SegmentedControl(segments=["Day", "Week", "Month"], selected_index=1, on_change=cb)
    assert el.type == "SegmentedControl"
    assert el.props["segments"] == ["Day", "Week", "Month"]
    assert el.props["selected_index"] == 1
    assert el.props["on_change"] is cb


def test_segmented_control_defaults_empty() -> None:
    el = SegmentedControl()
    assert el.props["segments"] == []
    assert el.props["selected_index"] == 0


# ======================================================================
# DatePicker
# ======================================================================


def test_date_picker_props_and_default_role() -> None:
    cb = lambda _v: None  # noqa: E731
    el = DatePicker(value="2026-05-31", mode="date", on_change=cb, minimum="2026-01-01")
    assert el.type == "DatePicker"
    assert el.props["value"] == "2026-05-31"
    assert el.props["mode"] == "date"
    assert el.props["on_change"] is cb
    assert el.props["minimum"] == "2026-01-01"
    assert el.props["accessibility_role"] == "button"


def test_date_picker_time_mode() -> None:
    el = DatePicker(mode="time")
    assert el.props["mode"] == "time"


# ======================================================================
# Enriched existing components
# ======================================================================


def test_progress_bar_color_and_indeterminate() -> None:
    el = ProgressBar(value=0.5, color="#00FF00", track_color="#EEEEEE", indeterminate=True)
    assert el.props["value"] == 0.5
    assert el.props["color"] == "#00FF00"
    assert el.props["track_color"] == "#EEEEEE"
    assert el.props["indeterminate"] is True


def test_progress_bar_indeterminate_dropped_when_false() -> None:
    el = ProgressBar(value=0.25)
    assert "indeterminate" not in el.props


def test_activity_indicator_color_and_size() -> None:
    el = ActivityIndicator(color="#123456", size="large")
    assert el.props["color"] == "#123456"
    assert el.props["size"] == "large"


def test_web_view_html_and_callbacks() -> None:
    on_load = lambda _u: None  # noqa: E731
    on_message = lambda _m: None  # noqa: E731
    el = WebView(html="<h1>Hi</h1>", on_load=on_load, on_message=on_message, inject_javascript="1;")
    assert el.props["html"] == "<h1>Hi</h1>"
    assert el.props["on_load"] is on_load
    assert el.props["on_message"] is on_message
    assert el.props["inject_javascript"] == "1;"


def test_web_view_scroll_enabled_dropped_when_true() -> None:
    el = WebView(url="https://example.com")
    assert "scroll_enabled" not in el.props
    el2 = WebView(url="https://example.com", scroll_enabled=False)
    assert el2.props["scroll_enabled"] is False


def test_text_input_new_props() -> None:
    on_focus = lambda: None  # noqa: E731
    on_blur = lambda: None  # noqa: E731
    el = TextInput(
        value="x",
        editable=False,
        clear_button=True,
        on_focus=on_focus,
        on_blur=on_blur,
        selection_color="#FF00FF",
        text_content_type="password",
    )
    assert el.props["editable"] is False
    assert el.props["clear_button"] is True
    assert el.props["on_focus"] is on_focus
    assert el.props["on_blur"] is on_blur
    assert el.props["selection_color"] == "#FF00FF"
    assert el.props["text_content_type"] == "password"


def test_text_input_editable_dropped_when_true() -> None:
    el = TextInput(value="x")
    assert "editable" not in el.props
    assert "clear_button" not in el.props


def test_text_input_selection_key_and_keyboard_props() -> None:
    on_selection_change = lambda _e: None  # noqa: E731
    on_key_press = lambda _e: None  # noqa: E731
    on_content_size_change = lambda _e: None  # noqa: E731
    el = TextInput(
        value="hello",
        selection=(1, 3),
        on_selection_change=on_selection_change,
        on_key_press=on_key_press,
        on_content_size_change=on_content_size_change,
        select_text_on_focus=True,
        blur_on_submit=False,
        keyboard_appearance="dark",
        keyboard_type="numbers_and_punctuation",
    )
    assert el.props["selection"] == {"start": 1, "end": 3}
    assert el.props["on_selection_change"] is on_selection_change
    assert el.props["on_key_press"] is on_key_press
    assert el.props["on_content_size_change"] is on_content_size_change
    assert el.props["select_text_on_focus"] is True
    assert el.props["blur_on_submit"] is False
    assert el.props["keyboard_appearance"] == "dark"
    assert el.props["keyboard_type"] == "numbers_and_punctuation"


def test_text_input_new_defaults_are_omitted() -> None:
    el = TextInput(value="x")
    for key in ("selection", "select_text_on_focus", "blur_on_submit", "keyboard_appearance"):
        assert key not in el.props


def test_text_input_rejects_inverted_selection() -> None:
    with pytest.raises(ValueError, match="start <= end"):
        TextInput(selection=(3, 1))


def test_scroll_view_new_props() -> None:
    on_scroll = lambda _payload: None  # noqa: E731
    body = Text("body")
    el = ScrollView(
        body,
        on_scroll=on_scroll,
        shows_scroll_indicator=False,
        paging_enabled=True,
        bounces=False,
        keyboard_dismiss_mode="on_drag",
        content_container_style={"padding": 8},
    )
    assert el.props["on_scroll"] is on_scroll
    assert el.props["shows_scroll_indicator"] is False
    assert el.props["paging_enabled"] is True
    assert el.props["bounces"] is False
    assert el.props["keyboard_dismiss_mode"] == "on_drag"
    # The content container is an inner View, not a wire prop.
    assert "content_container_style" not in el.props
    (inner,) = el.children
    assert inner.type == "View"
    assert inner.props["padding"] == 8
    assert inner.props["flex_direction"] == "column"
    assert inner.props["width"] == "100%"
    assert inner.children == (body,)


def test_scroll_view_horizontal_content_container_is_a_row() -> None:
    el = ScrollView(Text("a"), Text("b"), horizontal=True, content_container_style={"gap": 4})
    assert el.props["horizontal"] is True
    (inner,) = el.children
    assert inner.props["flex_direction"] == "row"
    assert "width" not in inner.props
    assert len(inner.children) == 2


def test_horizontal_scroll_view_lays_its_content_out_in_a_row() -> None:
    # Every renderer's layout reads the direction from the style; a column
    # would squeeze the content to the viewport width and nothing scrolls.
    assert ScrollView(Text("a"), horizontal=True).props["flex_direction"] == "row"
    assert ScrollView(Text("a"), horizontal=True, style={"flex_direction": "column"}).props["flex_direction"] == "row"
    assert "flex_direction" not in ScrollView(Text("a")).props


def test_horizontal_scroll_view_content_is_wider_than_its_viewport() -> None:
    from pythonnative.testing import render

    tiles = [View(style={"width": 120, "height": 40}) for _ in range(5)]
    result = render(ScrollView(*tiles, horizontal=True, style={"width": 200, "height": 60}))
    scroll = result.get_all_by_type("ScrollView")[0]
    right_edges = [child.frame[0] + child.frame[2] for child in scroll.children]
    assert max(right_edges) >= 600, right_edges


def test_scroll_view_scroll_props_and_events() -> None:
    begin = lambda _e: None  # noqa: E731
    end = lambda _e: None  # noqa: E731
    momentum = lambda _e: None  # noqa: E731
    el = ScrollView(
        Text("body"),
        content_inset={"bottom": 80, "horizontal": 4},
        scroll_enabled=False,
        scroll_event_throttle=32,
        on_scroll_begin_drag=begin,
        on_scroll_end_drag=end,
        on_momentum_scroll_end=momentum,
        keyboard_should_persist_taps="handled",
        snap_to_interval=300,
        snap_to_alignment="center",
        deceleration_rate="fast",
    )
    assert el.props["content_inset"] == {"bottom": 80, "left": 4, "right": 4}
    assert el.props["scroll_enabled"] is False
    assert el.props["scroll_event_throttle"] == 32.0
    assert el.props["on_scroll_begin_drag"] is begin
    assert el.props["on_scroll_end_drag"] is end
    assert el.props["on_momentum_scroll_end"] is momentum
    assert el.props["keyboard_should_persist_taps"] == "handled"
    assert el.props["snap_to_interval"] == 300
    assert el.props["snap_to_alignment"] == "center"
    assert el.props["deceleration_rate"] == "fast"
    numeric = ScrollView(Text("body"), deceleration_rate=0.99)
    assert numeric.props["deceleration_rate"] == 0.99


def test_scroll_view_defaults_drop_noise() -> None:
    el = ScrollView(Text("body"))
    for noisy in (
        "shows_scroll_indicator",
        "paging_enabled",
        "bounces",
        "content_container_style",
        "horizontal",
        "scroll_enabled",
        "scroll_event_throttle",
        "keyboard_should_persist_taps",
        "snap_to_alignment",
        "deceleration_rate",
        "content_inset",
    ):
        assert noisy not in el.props
    assert "scroll_axis" not in el.props


def test_modal_new_props() -> None:
    on_show = lambda: None  # noqa: E731
    on_request_close = lambda: None  # noqa: E731
    el = Modal(
        Text("content"),
        visible=True,
        on_show=on_show,
        on_request_close=on_request_close,
        presentation_style="form_sheet",
        dismiss_on_backdrop=False,
        status_bar_translucent=True,
    )
    assert el.props["on_show"] is on_show
    assert el.props["on_request_close"] is on_request_close
    assert el.props["presentation_style"] == "form_sheet"
    assert el.props["dismiss_on_backdrop"] is False
    assert el.props["status_bar_translucent"] is True
    plain = Modal(Text("content"))
    assert "on_request_close" not in plain.props
    assert "status_bar_translucent" not in plain.props


# ======================================================================
# FlatList: grid, horizontal, header/footer, empty, on_end_reached
# ======================================================================


def _mount(el):  # type: ignore[no-untyped-def]
    from pythonnative.reconciler import Reconciler
    from pythonnative.testing import FakeBackend

    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.on_render_requested = lambda: None
    root = rec.mount(el)
    return root, rec, backend


def test_flatlist_grid_chunks_into_rows() -> None:
    el = FlatList(
        data=list(range(5)),
        num_columns=2,
        render_item=lambda item, _i: Text(str(item)),
    )
    # 3 virtual rows: [0,1], [2,3], [4]
    root, _rec, _backend = _mount(el)
    assert len(_backend.list_stores[root.tag].keys) == 3
    rows = root.find_all("Row")
    assert len(rows) == 3
    assert len(rows[0].children) == 2
    assert len(rows[2].children) == 1


def test_flatlist_horizontal_scrolls_on_x_axis() -> None:
    el = FlatList(data=[1, 2, 3], horizontal=True, render_item=lambda i, _i: Text(str(i)))
    assert el.props["horizontal"] is True

    root, _rec, _backend = _mount(el)
    assert root.type_name == "VirtualList"
    assert root.props["horizontal"] is True
    # The content wrapper lays rows out horizontally.
    assert len(root.children) == 3


def test_flatlist_header_and_footer() -> None:
    el = FlatList(
        data=[1, 2],
        item_height=20,
        render_item=lambda i, _i: Text(str(i)),
        list_header=Text("HEADER"),
        list_footer=Text("FOOTER"),
    )
    root, _rec, _backend = _mount(el)
    texts = [v.props["text"] for v in root.find_all("Text")]
    assert texts[0] == "HEADER"
    assert texts[-1] == "FOOTER"
    assert texts[1:-1] == ["1", "2"]


def test_flatlist_empty_state() -> None:
    el = FlatList(
        data=[],
        item_height=20,
        render_item=lambda i, _i: Text(str(i)),
        list_empty=Text("Nothing here"),
    )
    root, _rec, _backend = _mount(el)
    texts = [v.props["text"] for v in root.find_all("Text")]
    assert texts == ["Nothing here"]


def test_flatlist_on_end_reached_fires_near_the_end() -> None:

    fired: list = []
    el = FlatList(
        data=list(range(100)),
        item_height=30,
        on_end_reached=lambda: fired.append(1),
        on_end_reached_threshold=0.5,
    )
    assert el.props["on_end_reached_threshold"] == 0.5

    _root, rec, _backend = _mount(el)
    tag = rec.root_tag

    # Far from the end: no callback.
    _backend.request_list(tag, 0)
    assert fired == []

    # Content extent is 100 * 30 = 3000; the default viewport estimate is
    # 800, so an offset near the bottom crosses the 0.5-viewport line.
    _backend.request_list(tag, 70)
    assert fired == [1]

    # The latch prevents refiring while still near the end.
    _backend.request_list(tag, 71)
    assert fired == [1]
