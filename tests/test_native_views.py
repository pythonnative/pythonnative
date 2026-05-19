"""Unit tests for the native_views package.

Tests the registry, base handler protocol, and shared utility functions.
Platform-specific handlers (android/ios) are not tested here since they
require their respective runtime environments; they are exercised by
E2E tests on device.
"""

from typing import Any, Dict, Tuple

import pytest

from pythonnative.layout import LAYOUT_STYLE_KEYS
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
        "justify_content",
        "align_items",
        "align_self",
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
        handler.create({})


def test_view_handler_update_raises() -> None:
    handler = ViewHandler()
    with pytest.raises(NotImplementedError):
        handler.update(None, {})


def test_view_handler_add_child_noop() -> None:
    handler = ViewHandler()
    handler.add_child(None, None)


def test_view_handler_remove_child_noop() -> None:
    handler = ViewHandler()
    handler.remove_child(None, None)


def test_view_handler_insert_child_delegates() -> None:
    calls: list = []

    class TestHandler(ViewHandler):
        def add_child(self, parent: Any, child: Any) -> None:
            calls.append(("add", parent, child))

    handler = TestHandler()
    handler.insert_child("parent", "child", 0)
    assert calls == [("add", "parent", "child")]


def test_view_handler_set_frame_default_noop() -> None:
    """Default ``set_frame`` is a no-op so virtual nodes can opt out."""
    handler = ViewHandler()
    handler.set_frame(None, 0, 0, 100, 50)


def test_view_handler_measure_intrinsic_default_zero() -> None:
    """Default ``measure_intrinsic`` returns ``(0, 0)`` for handlers without intrinsic size."""
    handler = ViewHandler()
    assert handler.measure_intrinsic(None, 100.0, 100.0) == (0.0, 0.0)


# ======================================================================
# NativeViewRegistry
# ======================================================================


class StubView:
    def __init__(self, type_name: str, props: Dict[str, Any]) -> None:
        self.type_name = type_name
        self.props = dict(props)
        self.frame: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)


class StubHandler(ViewHandler):
    def create(self, props: Dict[str, Any]) -> StubView:
        return StubView("Stub", props)

    def update(self, native_view: Any, changed_props: Dict[str, Any]) -> None:
        native_view.props.update(changed_props)

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        native_view.frame = (x, y, width, height)

    def measure_intrinsic(self, native_view: Any, max_width: float, max_height: float) -> Tuple[float, float]:
        # Pretend the stub view is 40x10 plus its content length.
        return (min(40.0 + len(native_view.props.get("text", "")), max_width), 10.0)


def test_registry_create_view() -> None:
    reg = NativeViewRegistry()
    reg.register("Text", StubHandler())
    view = reg.create_view("Text", {"text": "hello"})
    assert isinstance(view, StubView)
    assert view.props["text"] == "hello"


def test_registry_unknown_type_raises() -> None:
    reg = NativeViewRegistry()
    with pytest.raises(ValueError, match="Unknown element type"):
        reg.create_view("NonExistent", {})


def test_registry_update_view() -> None:
    reg = NativeViewRegistry()
    reg.register("Text", StubHandler())
    view = reg.create_view("Text", {"text": "old"})
    reg.update_view(view, "Text", {"text": "new"})
    assert view.props["text"] == "new"


def test_registry_update_unknown_type_noop() -> None:
    reg = NativeViewRegistry()
    reg.update_view(StubView("X", {}), "X", {"a": 1})


def test_registry_child_ops_unknown_type_noop() -> None:
    reg = NativeViewRegistry()
    reg.add_child(None, None, "Unknown")
    reg.remove_child(None, None, "Unknown")
    reg.insert_child(None, None, "Unknown", 0)


def test_registry_set_frame_dispatches_to_handler() -> None:
    reg = NativeViewRegistry()
    reg.register("Text", StubHandler())
    view = reg.create_view("Text", {"text": "x"})
    reg.set_frame(view, "Text", 5.0, 10.0, 100.0, 50.0)
    assert view.frame == (5.0, 10.0, 100.0, 50.0)


def test_registry_set_frame_unknown_type_noop() -> None:
    reg = NativeViewRegistry()
    reg.set_frame(None, "Unknown", 0, 0, 100, 50)


def test_registry_measure_intrinsic_dispatches() -> None:
    reg = NativeViewRegistry()
    reg.register("Text", StubHandler())
    view = reg.create_view("Text", {"text": "abc"})
    w, h = reg.measure_intrinsic(view, "Text", 1000.0, 1000.0)
    assert w == 43.0  # 40 + 3
    assert h == 10.0


def test_registry_measure_intrinsic_unknown_type_zero() -> None:
    reg = NativeViewRegistry()
    assert reg.measure_intrinsic(None, "Unknown", 1000.0, 1000.0) == (0.0, 0.0)


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
    """``set_frame`` with a NaN dimension fires the rate-limited tripwire."""
    reg = NativeViewRegistry()
    reg.register("Text", StubHandler())
    view = reg.create_view("Text", {"text": "x"})
    reg.set_frame(view, "Text", 0.0, 0.0, float("nan"), 50.0)
    captured = capsys.readouterr()
    assert "[set_frame:nan]" in captured.err
    assert "type='Text'" in captured.err
