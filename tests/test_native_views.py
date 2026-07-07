"""Unit tests for the native_views package.

Tests the registry's batched ``apply_mutations`` commit channel, the tag
table, the base handler protocol, and shared utility functions.
Platform-specific handlers (android/ios) are not tested here since they
require their respective runtime environments; they are exercised by
E2E tests on device.
"""

import itertools
from typing import Any, Dict, Tuple

import pytest

from pythonnative.layout import LAYOUT_STYLE_KEYS
from pythonnative.mutations import CreateOp, DestroyOp, InsertOp, SetFrameOp, UpdateOp
from pythonnative.native_views import NativeViewRegistry, set_registry
from pythonnative.native_views.base import (
    ViewHandler,
    parse_color_int,
)

# ======================================================================
# parse_color_int
# ======================================================================


def test_parse_color_hex6() -> None:
    result = parse_color_int("#FF0000")
    assert result == parse_color_int("FF0000")
    expected = int("FFFF0000", 16)
    if expected > 0x7FFFFFFF:
        expected -= 0x100000000
    assert result == expected


def test_parse_color_hex8() -> None:
    result = parse_color_int("#80FF0000")
    raw = int("80FF0000", 16)
    expected = raw - 0x100000000  # signed conversion
    assert result == expected


def test_parse_color_int_passthrough() -> None:
    assert parse_color_int(0x00FF00) == 0x00FF00


def test_parse_color_signed_conversion() -> None:
    result = parse_color_int("#FFFFFFFF")
    assert result < 0


def test_parse_color_with_whitespace() -> None:
    assert parse_color_int("  #FF0000  ") == parse_color_int("#FF0000")


# ======================================================================
# Layout-engine ownership
# ======================================================================


def test_layout_style_keys_includes_flex_props() -> None:
    """All flex / sizing props are owned by the layout engine, not handlers."""
    for key in (
        "width",
        "height",
        "flex",
        "flex_grow",
        "flex_shrink",
        "flex_basis",
        "flex_direction",
        "flex_wrap",
        "justify_content",
        "align_items",
        "align_self",
        "align_content",
        "padding",
        "margin",
        "spacing",
        "gap",
        "position",
        "top",
        "right",
        "bottom",
        "left",
        "aspect_ratio",
    ):
        assert key in LAYOUT_STYLE_KEYS


# ======================================================================
# ViewHandler protocol
# ======================================================================


def test_view_handler_create_raises() -> None:
    handler = ViewHandler()
    with pytest.raises(NotImplementedError):
        handler.create(1, {})


def test_view_handler_update_raises() -> None:
    handler = ViewHandler()
    with pytest.raises(NotImplementedError):
        handler.update(None, {})


def test_view_handler_child_ops_default_noop() -> None:
    handler = ViewHandler()
    handler.insert_child(None, None, 0)
    handler.remove_child(None, None)
    handler.destroy(None)


def test_view_handler_set_frame_default_noop() -> None:
    """Default ``set_frame`` is a no-op so virtual nodes can opt out."""
    handler = ViewHandler()
    handler.set_frame(None, 0, 0, 100, 50)


def test_view_handler_measure_intrinsic_default_zero() -> None:
    """Default ``measure_intrinsic`` returns ``(0, 0)`` for handlers without intrinsic size."""
    handler = ViewHandler()
    assert handler.measure_intrinsic(None, 100.0, 100.0) == (0.0, 0.0)


def test_view_handler_command_default_none() -> None:
    handler = ViewHandler()
    assert handler.command(None, "anything", {}) is None


def test_view_handler_animation_defaults() -> None:
    """Default animation hooks: no native driving, no presentation value."""
    handler = ViewHandler()
    handler.set_animated_property(None, "opacity", 0.5)
    assert handler.start_animation(None, 1, "opacity", {"kind": "timing"}) is False
    assert handler.cancel_animation(None, 1) is None


# ======================================================================
# NativeViewRegistry (tag table + apply_mutations)
# ======================================================================

_tags = itertools.count(1)


def _next_tag() -> int:
    return next(_tags)


class StubView:
    def __init__(self, tag: int, type_name: str, props: Dict[str, Any]) -> None:
        self.tag = tag
        self.type_name = type_name
        self.props = dict(props)
        self.children: list = []
        self.frame: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
        self.destroyed = False


class StubHandler(ViewHandler):
    def __init__(self, type_name: str = "Stub") -> None:
        self.type_name = type_name
        self.commands: list = []

    def create(self, tag: int, props: Dict[str, Any]) -> StubView:
        return StubView(tag, self.type_name, props)

    def update(self, native_view: Any, changed_props: Dict[str, Any]) -> None:
        native_view.props.update(changed_props)

    def insert_child(self, parent: Any, child: Any, index: int) -> None:
        if child in parent.children:
            parent.children.remove(child)
        parent.children.insert(min(index, len(parent.children)), child)

    def remove_child(self, parent: Any, child: Any) -> None:
        if child in parent.children:
            parent.children.remove(child)

    def destroy(self, native_view: Any) -> None:
        native_view.destroyed = True

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        native_view.frame = (x, y, width, height)

    def measure_intrinsic(self, native_view: Any, max_width: float, max_height: float) -> Tuple[float, float]:
        # Pretend the stub view is 40x10 plus its content length.
        return (min(40.0 + len(native_view.props.get("text", "")), max_width), 10.0)

    def command(self, native_view: Any, name: str, args: Dict[str, Any]) -> Any:
        self.commands.append((name, dict(args)))
        return "ok"


def _make_registry() -> NativeViewRegistry:
    reg = NativeViewRegistry()
    reg.register("Text", StubHandler("Text"))
    reg.register("Column", StubHandler("Column"))
    return reg


def test_registry_create_registers_tag() -> None:
    reg = _make_registry()
    tag = _next_tag()
    reg.apply_mutations([CreateOp(tag, "Text", {"text": "hello"})])
    view = reg.resolve_view(tag)
    assert isinstance(view, StubView)
    assert view.props["text"] == "hello"
    assert reg.live_view_count() == 1


def test_registry_unknown_type_is_isolated(capsys: pytest.CaptureFixture[str]) -> None:
    """A CreateOp for an unknown type is logged but does not abort the batch."""
    reg = _make_registry()
    bad_tag, good_tag = _next_tag(), _next_tag()
    reg.apply_mutations(
        [
            CreateOp(bad_tag, "NonExistent", {}),
            CreateOp(good_tag, "Text", {"text": "still applied"}),
        ]
    )
    captured = capsys.readouterr()
    assert "CreateOp failed" in captured.err
    assert reg.resolve_view(bad_tag) is None
    assert reg.resolve_view(good_tag) is not None


def test_registry_update_view() -> None:
    reg = _make_registry()
    tag = _next_tag()
    reg.apply_mutations([CreateOp(tag, "Text", {"text": "old"})])
    reg.apply_mutations([UpdateOp(tag, {"text": "new"})])
    assert reg.resolve_view(tag).props["text"] == "new"


def test_registry_update_unknown_tag_noop() -> None:
    reg = _make_registry()
    reg.apply_mutations([UpdateOp(999_999, {"a": 1})])


def test_registry_insert_child() -> None:
    reg = _make_registry()
    parent_tag, child_tag = _next_tag(), _next_tag()
    reg.apply_mutations(
        [
            CreateOp(parent_tag, "Column", {}),
            CreateOp(child_tag, "Text", {"text": "x"}),
            InsertOp(parent_tag, child_tag, 0),
        ]
    )
    parent = reg.resolve_view(parent_tag)
    child = reg.resolve_view(child_tag)
    assert parent.children == [child]


def test_registry_child_ops_unknown_tags_noop() -> None:
    reg = _make_registry()
    reg.apply_mutations([InsertOp(111_111, 222_222, 0)])


def test_registry_destroy_releases_tag_and_calls_handler() -> None:
    reg = _make_registry()
    tag = _next_tag()
    reg.apply_mutations([CreateOp(tag, "Text", {"text": "x"})])
    view = reg.resolve_view(tag)
    reg.apply_mutations([DestroyOp(tag)])
    assert view.destroyed is True
    assert reg.resolve_view(tag) is None
    assert reg.live_view_count() == 0


def test_registry_set_frame_dispatches_to_handler() -> None:
    reg = _make_registry()
    tag = _next_tag()
    reg.apply_mutations(
        [
            CreateOp(tag, "Text", {"text": "x"}),
            SetFrameOp(tag, 5.0, 10.0, 100.0, 50.0),
        ]
    )
    assert reg.resolve_view(tag).frame == (5.0, 10.0, 100.0, 50.0)


def test_registry_set_frame_unknown_tag_noop() -> None:
    reg = _make_registry()
    reg.apply_mutations([SetFrameOp(999_999, 0, 0, 100, 50)])


def test_registry_ops_apply_in_order() -> None:
    """One transaction may create, attach, frame, and update in sequence."""
    reg = _make_registry()
    parent_tag, child_tag = _next_tag(), _next_tag()
    reg.apply_mutations(
        [
            CreateOp(parent_tag, "Column", {}),
            CreateOp(child_tag, "Text", {"text": "a"}),
            InsertOp(parent_tag, child_tag, 0),
            UpdateOp(child_tag, {"text": "b"}),
            SetFrameOp(child_tag, 0.0, 0.0, 60.0, 16.0),
        ]
    )
    child = reg.resolve_view(child_tag)
    assert child.props["text"] == "b"
    assert child.frame == (0.0, 0.0, 60.0, 16.0)
    assert reg.resolve_view(parent_tag).children == [child]


def test_registry_measure_intrinsic_dispatches() -> None:
    reg = _make_registry()
    tag = _next_tag()
    reg.apply_mutations([CreateOp(tag, "Text", {"text": "abc"})])
    w, h = reg.measure_intrinsic(tag, 1000.0, 1000.0)
    assert w == 43.0  # 40 + 3
    assert h == 10.0


def test_registry_measure_intrinsic_unknown_tag_zero() -> None:
    reg = _make_registry()
    assert reg.measure_intrinsic(999_999, 1000.0, 1000.0) == (0.0, 0.0)


def test_registry_command_dispatches_by_tag() -> None:
    reg = NativeViewRegistry()
    handler = StubHandler("Text")
    reg.register("Text", handler)
    tag = _next_tag()
    reg.apply_mutations([CreateOp(tag, "Text", {"text": "x"})])
    result = reg.command(tag, "focus", {"select_all": True})
    assert result == "ok"
    assert handler.commands == [("focus", {"select_all": True})]


def test_registry_command_unknown_tag_none() -> None:
    reg = _make_registry()
    assert reg.command(999_999, "focus") is None


def test_registry_animation_hooks_resolve_through_tag_table() -> None:
    class AnimHandler(StubHandler):
        def __init__(self) -> None:
            super().__init__("Text")
            self.applied: list = []
            self.started: list = []
            self.cancelled: list = []

        def set_animated_property(self, native_view: Any, prop_name: str, value: Any) -> None:
            self.applied.append((prop_name, value))

        def start_animation(self, native_view: Any, anim_id: int, prop_name: str, spec: Dict[str, Any]) -> bool:
            self.started.append((anim_id, prop_name))
            return True

        def cancel_animation(self, native_view: Any, anim_id: int) -> Any:
            self.cancelled.append(anim_id)
            return 0.5

    reg = NativeViewRegistry()
    handler = AnimHandler()
    reg.register("Text", handler)
    tag = _next_tag()
    reg.apply_mutations([CreateOp(tag, "Text", {})])

    reg.set_animated_property(tag, "opacity", 0.7)
    assert handler.applied == [("opacity", 0.7)]
    assert reg.start_animation(tag, 1, "opacity", {"kind": "timing"}) is True
    assert handler.started == [(1, "opacity")]
    assert reg.cancel_animation(tag, 1) == 0.5

    # Unknown tags: animation hooks are safe no-ops.
    reg.set_animated_property(999_999, "opacity", 1.0)
    assert reg.start_animation(999_999, 2, "opacity", {}) is False
    assert reg.cancel_animation(999_999, 2) is None


def test_set_registry_injects() -> None:
    reg = NativeViewRegistry()
    set_registry(reg)
    from pythonnative.native_views import _registry

    assert _registry is reg
    set_registry(None)


# ======================================================================
# _tripwire_log rate limiter
# ======================================================================


@pytest.fixture
def _tripwire_state() -> Any:
    """Reset the per-label tripwire state before each test."""
    import pythonnative.native_views as nv

    nv._TRIPWIRE_LAST_LOG_TIME.clear()
    nv._TRIPWIRE_SUPPRESSED_COUNT.clear()
    yield nv
    nv._TRIPWIRE_LAST_LOG_TIME.clear()
    nv._TRIPWIRE_SUPPRESSED_COUNT.clear()


def test_tripwire_log_first_call_emits(capsys: pytest.CaptureFixture[str], _tripwire_state: Any) -> None:
    _tripwire_state._tripwire_log("test:basic", "first message")
    captured = capsys.readouterr()
    assert "first message" in captured.err


def test_tripwire_log_subsequent_within_window_suppressed(
    capsys: pytest.CaptureFixture[str], _tripwire_state: Any
) -> None:
    _tripwire_state._tripwire_log("test:burst", "first")
    capsys.readouterr()
    _tripwire_state._tripwire_log("test:burst", "second")
    _tripwire_state._tripwire_log("test:burst", "third")
    captured = capsys.readouterr()
    assert captured.err == ""
    assert _tripwire_state._TRIPWIRE_SUPPRESSED_COUNT["test:burst"] == 2


def test_tripwire_log_after_window_emits_with_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    _tripwire_state: Any,
) -> None:
    """After the window expires, the next emit includes a ``+N similar`` suffix."""
    import time as _time

    monkeypatch.setattr(_tripwire_state, "_TRIPWIRE_RATE_LIMIT_S", 0.05)
    _tripwire_state._tripwire_log("test:summary", "first sample")
    capsys.readouterr()
    _tripwire_state._tripwire_log("test:summary", "suppressed-A")
    _tripwire_state._tripwire_log("test:summary", "suppressed-B")
    _time.sleep(0.06)
    _tripwire_state._tripwire_log("test:summary", "third sample")
    captured = capsys.readouterr()
    assert "third sample" in captured.err
    assert "+2 similar" in captured.err
    assert _tripwire_state._TRIPWIRE_SUPPRESSED_COUNT["test:summary"] == 0


def test_tripwire_log_distinct_labels_independent(capsys: pytest.CaptureFixture[str], _tripwire_state: Any) -> None:
    """A burst on one label must not silence a different label's first emit."""
    _tripwire_state._tripwire_log("test:a", "from a")
    _tripwire_state._tripwire_log("test:a", "still a, suppressed")
    _tripwire_state._tripwire_log("test:b", "from b")
    captured = capsys.readouterr()
    assert "from a" in captured.err
    assert "from b" in captured.err
    assert "still a" not in captured.err


def test_tripwire_log_suffix_omitted_when_zero_suppressed(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    _tripwire_state: Any,
) -> None:
    """The ``+N similar`` suffix only appears when at least one was suppressed."""
    import time as _time

    monkeypatch.setattr(_tripwire_state, "_TRIPWIRE_RATE_LIMIT_S", 0.01)
    _tripwire_state._tripwire_log("test:nosuffix", "alpha")
    _time.sleep(0.02)
    _tripwire_state._tripwire_log("test:nosuffix", "beta")
    captured = capsys.readouterr()
    assert "beta" in captured.err
    assert "similar" not in captured.err


def test_registry_set_frame_nan_emits_tripwire(capsys: pytest.CaptureFixture[str], _tripwire_state: Any) -> None:
    """A ``SetFrameOp`` with a NaN dimension fires the rate-limited tripwire."""
    reg = _make_registry()
    tag = _next_tag()
    reg.apply_mutations(
        [
            CreateOp(tag, "Text", {"text": "x"}),
            SetFrameOp(tag, 0.0, 0.0, float("nan"), 50.0),
        ]
    )
    captured = capsys.readouterr()
    assert "[set_frame:nan]" in captured.err
    assert "type='Text'" in captured.err
