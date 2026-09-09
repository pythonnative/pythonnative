"""Canonical imperative view commands and their wire arguments."""

from typing import Any


def _command(*, result: Any = None, required: tuple[str, ...] = (), **fields: Any) -> dict[str, Any]:
    return {"arguments": fields, "required": list(required), "result": result or {"type": "null"}, "defaults": {}}


def commands(name: str) -> dict[str, Any]:
    """Return the portable commands implemented by native view managers."""
    number, integer, boolean, string = ({"type": kind} for kind in ("number", "integer", "boolean", "string"))
    scroll = {
        "scroll_to_offset": _command(x=number, y=number, animated=boolean),
        "scroll_to_end": _command(animated=boolean),
        "get_scroll_offset": _command(
            result={
                "type": "object",
                "properties": {"x": number, "y": number},
                "required": ["x", "y"],
                "additionalProperties": False,
            }
        ),
        "flash_scroll_indicators": _command(),
    }
    if name == "ScrollView":
        return scroll
    if name == "VirtualList":
        return scroll | {"scroll_to_index": _command(required=("index",), index=integer, animated=boolean)}
    if name == "TextInput":
        return {
            **{command: _command() for command in ("focus", "blur", "clear", "select_all")},
            "get_value": _command(result=string),
            "set_selection": _command(required=("start",), start=integer, end=integer),
        }
    if name == "ScreenStack":
        return {"restore_stack": _command()}
    if name == "WebView":
        return {key: _command() for key in ("reload", "go_back", "go_forward", "stop_loading")} | {
            "can_go_back": _command(result=boolean),
            "can_go_forward": _command(result=boolean),
            "get_url": _command(result=string),
            "eval_js": _command(required=("script",), script=string),
            "inject_javascript": _command(required=("script",), script=string),
            "load_url": _command(required=("url",), url=string),
        }
    return {}
