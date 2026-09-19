"""Unit tests for the typed imperative handles in ``pythonnative.handles``."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple

import pytest

import pythonnative as pn
from pythonnative.handles import HANDLE_TYPES, make_handle


class _RecordingBackend:
    """Minimal backend: records ``command`` calls and answers from a canned table."""

    def __init__(self, answers: Optional[Dict[str, Any]] = None) -> None:
        self.commands: List[Tuple[int, str, Dict[str, Any]]] = []
        self.answers = dict(answers or {})

    def command(self, tag: int, name: str, args: Optional[Dict[str, Any]] = None) -> Any:
        self.commands.append((tag, name, dict(args or {})))
        return self.answers.get(name)


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


# ======================================================================
# make_handle / ViewHandle
# ======================================================================


def test_make_handle_picks_the_type_specific_class() -> None:
    backend = _RecordingBackend()
    assert type(make_handle("TextInput", 1, backend)) is pn.TextInputHandle
    assert type(make_handle("ScrollView", 2, backend)) is pn.ScrollViewHandle
    assert type(make_handle("WebView", 3, backend)) is pn.WebViewHandle
    assert type(make_handle("View", 4, backend)) is pn.ViewHandle
    assert type(make_handle("Text", 5, backend)) is pn.ViewHandle
    assert set(HANDLE_TYPES) == {"TextInput", "ScrollView", "WebView"}
    for cls in HANDLE_TYPES.values():
        assert issubclass(cls, pn.ViewHandle)


def test_view_handle_exposes_tag_type_and_writable_frame() -> None:
    handle = pn.ViewHandle(7, "View", _RecordingBackend())
    assert handle.tag == 7
    assert handle.type_name == "View"
    assert handle.frame is None
    handle.frame = pn.LayoutEvent(x=1, y=2, width=30, height=40)
    assert handle.frame.width == 30
    assert "View #7" in repr(handle)


def test_view_handle_command_forwards_tag_name_and_args() -> None:
    backend = _RecordingBackend({"custom": {"ok": True}})
    handle = pn.ViewHandle(9, "Badge", backend)
    assert handle.command("custom", level=2, label="x") == {"ok": True}
    assert backend.commands == [(9, "custom", {"level": 2, "label": "x"})]


# ======================================================================
# TextInputHandle
# ======================================================================


def test_text_input_handle_commands() -> None:
    backend = _RecordingBackend({"get_value": "hello"})
    handle = pn.TextInputHandle(3, "TextInput", backend)
    handle.focus()
    handle.blur()
    handle.clear()
    handle.select_all()
    handle.set_selection(2)
    handle.set_selection(1, 4)
    assert [(name, args) for _tag, name, args in backend.commands] == [
        ("focus", {}),
        ("blur", {}),
        ("clear", {}),
        ("select_all", {}),
        ("set_selection", {"start": 2, "end": 2}),
        ("set_selection", {"start": 1, "end": 4}),
    ]
    assert _run(handle.get_value()) == "hello"


def test_text_input_handle_get_value_defaults_to_empty_string() -> None:
    handle = pn.TextInputHandle(3, "TextInput", _RecordingBackend())
    assert _run(handle.get_value()) == ""


# ======================================================================
# ScrollViewHandle
# ======================================================================


def test_scroll_view_handle_commands() -> None:
    backend = _RecordingBackend({"get_scroll_offset": {"x": 0, "y": 120.5}})
    handle = pn.ScrollViewHandle(4, "ScrollView", backend)
    handle.scroll_to(y=200)
    handle.scroll_to(x=10, y=20, animated=False)
    handle.scroll_to_end()
    handle.flash_scroll_indicators()
    assert [(name, args) for _tag, name, args in backend.commands] == [
        ("scroll_to_offset", {"animated": True, "y": 200.0}),
        ("scroll_to_offset", {"animated": False, "x": 10.0, "y": 20.0}),
        ("scroll_to_end", {"animated": True}),
        ("flash_scroll_indicators", {}),
    ]
    offset = _run(handle.get_scroll_offset())
    assert offset == pn.ScrollOffset(x=0.0, y=120.5)
    assert isinstance(offset.y, float)


def test_scroll_offset_is_frozen() -> None:
    offset = pn.ScrollOffset(x=1.0, y=2.0)
    with pytest.raises(Exception):
        offset.x = 5.0  # type: ignore[misc]


# ======================================================================
# WebViewHandle
# ======================================================================


def test_web_view_handle_commands() -> None:
    backend = _RecordingBackend({"can_go_back": True, "can_go_forward": False, "get_url": "https://example.com/"})
    handle = pn.WebViewHandle(5, "WebView", backend)
    handle.reload()
    handle.go_back()
    handle.go_forward()
    handle.stop_loading()
    handle.load_url("https://example.com/next")
    handle.inject_javascript("document.title = 'x'")
    assert [(name, args) for _tag, name, args in backend.commands] == [
        ("reload", {}),
        ("go_back", {}),
        ("go_forward", {}),
        ("stop_loading", {}),
        ("load_url", {"url": "https://example.com/next"}),
        ("inject_javascript", {"script": "document.title = 'x'"}),
    ]
    assert _run(handle.can_go_back()) is True
    assert _run(handle.can_go_forward()) is False
    assert _run(handle.get_url()) == "https://example.com/"


def test_handle_commands_match_the_native_contract() -> None:
    """Every handle method issues a command the component's contract declares with valid arguments."""
    from pythonnative.sdk.schema import COMPONENTS, ModuleSchema

    cases = [
        ("TextInput", pn.TextInputHandle, lambda h: (h.focus(), h.set_selection(1, 2), _run(h.get_value()))),
        (
            "ScrollView",
            pn.ScrollViewHandle,
            lambda h: (h.scroll_to(y=5), h.scroll_to_end(), h.flash_scroll_indicators()),
        ),
        (
            "WebView",
            pn.WebViewHandle,
            lambda h: (h.reload(), h.load_url("https://a.b"), h.inject_javascript("1")),
        ),
    ]
    for type_name, cls, drive in cases:
        backend = _RecordingBackend()
        drive(cls(1, type_name, backend))
        schema = COMPONENTS[type_name]
        contract = ModuleSchema(schema.name, schema.commands)
        for _tag, name, args in backend.commands:
            contract.validate_call(name, args)


def test_web_view_eval_js_awaits_the_webviews_module() -> None:
    from pythonnative.native_modules.registry import register_python_module

    calls = []

    class Page:
        def eval_js(self, tag: int, script: str) -> str:
            calls.append((tag, script))
            return "42"

    register_python_module("WebViews", Page())
    try:
        backend = _RecordingBackend()
        handle = pn.WebViewHandle(5, "WebView", backend)
        assert _run(handle.eval_js("6 * 7")) == "42"
        assert calls == [(5, "6 * 7")]
        assert backend.commands == [], "eval_js is a module call, not a view command"
    finally:
        from pythonnative.native_modules import fallback

        register_python_module("WebViews", fallback.FallbackWebViews())


def test_web_view_eval_js_answers_empty_off_device() -> None:
    handle = pn.WebViewHandle(5, "WebView", _RecordingBackend())
    assert _run(handle.eval_js("1 + 1")) == ""
