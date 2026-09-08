"""Unit tests for the breadth expansion: new components and the new
props added to existing components.

These assert the Element shape produced by each factory (type, props,
children, dropped ``None`` defaults), which is the platform-agnostic
contract the native handlers consume.
"""

from __future__ import annotations

from pythonnative.components import (
    ActivityIndicator,
    Checkbox,
    DatePicker,
    FlatList,
    ImageBackground,
    Modal,
    ProgressBar,
    ScrollView,
    SegmentedControl,
    Text,
    TextInput,
    TouchableOpacity,
    WebView,
)

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


def test_touchable_opacity_disabled_drops_callbacks_and_dims() -> None:
    cb = lambda: None  # noqa: E731
    el = TouchableOpacity(Text("Tap"), on_press=cb, disabled=True)
    assert "on_press" not in el.props
    assert el.props["opacity"] == 0.4


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


def test_scroll_view_new_props() -> None:
    on_scroll = lambda _payload: None  # noqa: E731
    el = ScrollView(
        Text("body"),
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
    assert el.props["content_container_style"] == {"padding": 8}


def test_scroll_view_defaults_drop_noise() -> None:
    el = ScrollView(Text("body"))
    for noisy in ("shows_scroll_indicator", "paging_enabled", "bounces", "content_container_style"):
        assert noisy not in el.props


def test_modal_new_props() -> None:
    on_show = lambda: None  # noqa: E731
    el = Modal(
        Text("content"), visible=True, on_show=on_show, presentation_style="form_sheet", dismiss_on_backdrop=False
    )
    assert el.props["on_show"] is on_show
    assert el.props["presentation_style"] == "form_sheet"
    assert el.props["dismiss_on_backdrop"] is False


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
    assert len(el.props["rows"]) == 3

    root, _rec, _backend = _mount(el)
    rows = root.find_all("Row")
    assert len(rows) == 3
    assert len(rows[0].children) == 2
    assert len(rows[2].children) == 1


def test_flatlist_horizontal_scrolls_on_x_axis() -> None:
    el = FlatList(data=[1, 2, 3], horizontal=True, render_item=lambda i, _i: Text(str(i)))
    assert el.props["horizontal"] is True

    root, _rec, _backend = _mount(el)
    assert root.type_name == "ScrollView"
    assert root.props["scroll_axis"] == "horizontal"
    # The content wrapper lays rows out horizontally.
    assert root.find_first("Row") is not None


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
    from pythonnative.events import dispatch_event

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
    dispatch_event(tag, "on_scroll", {"x": 0.0, "y": 0.0})
    assert fired == []

    # Content extent is 100 * 30 = 3000; the default viewport estimate is
    # 800, so an offset near the bottom crosses the 0.5-viewport line.
    dispatch_event(tag, "on_scroll", {"x": 0.0, "y": 3000.0 - 800.0 - 100.0})
    assert fired == [1]

    # The latch prevents refiring while still near the end.
    dispatch_event(tag, "on_scroll", {"x": 0.0, "y": 3000.0 - 800.0 - 50.0})
    assert fired == [1]
