"""Unit tests for the native_views package: backend selection and the shared color helper.

The bridge backend itself is covered by ``test_bridge.py`` and
``test_runtime_contracts.py`` against ``FakeTransport``; headless renders
go through ``pythonnative.testing.FakeBackend``.
"""

from typing import Any

import pytest

import pythonnative.native_views as native_views
from pythonnative.layout import LAYOUT_STYLE_KEYS
from pythonnative.native_views import BridgeBackend, NativeViewRef, get_backend, parse_color_int, set_backend
from pythonnative.testing import FakeBackend

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
    """All flex / sizing props are owned by the layout engine, not renderers."""
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
        "display",
    ):
        assert key in LAYOUT_STYLE_KEYS


# ======================================================================
# Backend selection
# ======================================================================


@pytest.fixture
def _no_backend() -> Any:
    set_backend(None)
    yield
    set_backend(None)


def test_set_backend_injects(_no_backend: Any) -> None:
    fake = FakeBackend()
    set_backend(fake)
    assert get_backend() is fake
    set_backend(None)
    assert native_views._backend is None


def test_get_backend_off_device_raises(_no_backend: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    import pythonnative.utils as utils

    monkeypatch.setattr(utils, "IS_NATIVE", False)
    with pytest.raises(RuntimeError, match="FakeBackend"):
        get_backend()


def test_get_backend_on_device_builds_bridge_backend_after_discovery(
    _no_backend: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pythonnative.sdk._components as components
    import pythonnative.utils as utils

    discovered: list[bool] = []
    monkeypatch.setattr(utils, "IS_NATIVE", True)
    monkeypatch.setattr(components, "discover_components", lambda: discovered.append(True))
    backend = get_backend()
    assert isinstance(backend, BridgeBackend)
    assert discovered == [True]
    assert get_backend() is backend, "the backend is a process-wide singleton"


def test_package_exposes_only_the_bridge_surface() -> None:
    expected = {"BridgeBackend", "NativeViewRef", "get_backend", "parse_color_int", "set_backend"}
    assert set(native_views.__all__) == expected
    assert not hasattr(native_views, "NativeViewRegistry")
    assert not hasattr(native_views, "ViewHandler")
    assert not hasattr(native_views, "get_registry")
    assert not hasattr(BridgeBackend, "register")
    assert not hasattr(BridgeBackend, "handler_for")
    ref = NativeViewRef(7, "Text")
    assert int(ref) == 7 and ref.type_name == "Text"
