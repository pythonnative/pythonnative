"""Typed imperative handles published on ``ref.current`` for built-in elements.

When a [`Ref`][pythonnative.Ref] is passed to a built-in element, the
reconciler publishes a handle chosen by element type on ``ref.current``
after commit and clears it back to ``None`` on unmount:

| Element | ``ref.current`` |
| --- | --- |
| ``TextInput`` | [`TextInputHandle`][pythonnative.TextInputHandle] |
| ``ScrollView`` | [`ScrollViewHandle`][pythonnative.ScrollViewHandle] |
| ``WebView`` | [`WebViewHandle`][pythonnative.WebViewHandle] |
| everything else | [`ViewHandle`][pythonnative.ViewHandle] |

Every handle exposes the view's ``tag``, its ``type_name``, and
``frame`` (the last committed [`LayoutEvent`][pythonnative.LayoutEvent],
written by the layout pass). Methods that act on the view are plain
calls; methods that need an answer from the native view are ``async``.
Composite components (``FlatList``, ``SectionList``) publish their own
[`ListController`][pythonnative.ListController] instead.

Example:
    ```python
    import pythonnative as pn

    @pn.component
    def Search():
        field = pn.use_ref()
        pn.use_effect(lambda: field.current and field.current.focus(), [])
        return pn.TextInput(placeholder="Search", ref=field)
    ```
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .components.events import LayoutEvent

__all__ = [
    "HANDLE_TYPES",
    "ScrollOffset",
    "ScrollViewHandle",
    "TextInputHandle",
    "ViewHandle",
    "WebViewHandle",
    "make_handle",
]


@dataclass(frozen=True, slots=True)
class ScrollOffset:
    """A scroll container's content offset in logical units."""

    x: float
    y: float


class ViewHandle:
    """The imperative handle for a mounted built-in element.

    Attributes:
        tag: The reconciler-assigned view tag.
        type_name: The element type (``"View"``, ``"Text"``, ...).
        frame: The last committed frame as a
            [`LayoutEvent`][pythonnative.LayoutEvent], or ``None``
            before the first layout. Written by the layout pass.
    """

    __slots__ = ("tag", "type_name", "frame", "_backend")

    def __init__(self, tag: int, type_name: str, backend: Any) -> None:
        self.tag = tag
        self.type_name = type_name
        self.frame: Optional[LayoutEvent] = None
        self._backend = backend

    def command(self, name: str, **args: Any) -> Any:
        """Run a native view command by name and return its result.

        The typed methods on the subclasses are thin wrappers over this;
        it stays public for commands a custom native component declares
        in its own contract.
        """
        return self._backend.command(self.tag, name, dict(args))

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.type_name} #{self.tag})"


class TextInputHandle(ViewHandle):
    """Handle for [`TextInput`][pythonnative.TextInput]."""

    __slots__ = ()

    def focus(self) -> None:
        """Give the field keyboard focus."""
        self.command("focus")

    def blur(self) -> None:
        """Remove keyboard focus from the field."""
        self.command("blur")

    def clear(self) -> None:
        """Empty the field (``on_change`` reports the empty string)."""
        self.command("clear")

    def select_all(self) -> None:
        """Select the whole text."""
        self.command("select_all")

    def set_selection(self, start: int, end: Optional[int] = None) -> None:
        """Move the caret to ``start``, or select ``start`` to ``end`` (UTF-16 offsets)."""
        self.command("set_selection", start=int(start), end=int(start if end is None else end))

    async def get_value(self) -> str:
        """Return the field's current text as the native view holds it."""
        result = self.command("get_value")
        return "" if result is None else str(result)


class ScrollViewHandle(ViewHandle):
    """Handle for [`ScrollView`][pythonnative.ScrollView]."""

    __slots__ = ()

    def scroll_to(self, x: Optional[float] = None, y: Optional[float] = None, animated: bool = True) -> None:
        """Scroll to a content offset; an omitted axis keeps its current offset."""
        args: Dict[str, Any] = {"animated": bool(animated)}
        if x is not None:
            args["x"] = float(x)
        if y is not None:
            args["y"] = float(y)
        self.command("scroll_to_offset", **args)

    def scroll_to_end(self, animated: bool = True) -> None:
        """Scroll to the end of the content along the scroll axis."""
        self.command("scroll_to_end", animated=bool(animated))

    def flash_scroll_indicators(self) -> None:
        """Briefly show the scroll indicators."""
        self.command("flash_scroll_indicators")

    async def get_scroll_offset(self) -> ScrollOffset:
        """Return the current content offset."""
        result = self.command("get_scroll_offset") or {}
        return ScrollOffset(x=float(result.get("x", 0.0)), y=float(result.get("y", 0.0)))


class WebViewHandle(ViewHandle):
    """Handle for [`WebView`][pythonnative.WebView]."""

    __slots__ = ()

    def reload(self) -> None:
        """Reload the current page."""
        self.command("reload")

    def go_back(self) -> None:
        """Navigate back in the page history."""
        self.command("go_back")

    def go_forward(self) -> None:
        """Navigate forward in the page history."""
        self.command("go_forward")

    def stop_loading(self) -> None:
        """Stop the current load."""
        self.command("stop_loading")

    def load_url(self, url: str) -> None:
        """Navigate to ``url``."""
        self.command("load_url", url=str(url))

    def inject_javascript(self, script: str) -> None:
        """Evaluate ``script`` in the page without waiting for a result."""
        self.command("inject_javascript", script=str(script))

    async def eval_js(self, script: str) -> str:
        """Evaluate ``script`` in the page and return its result as a string.

        The page answers asynchronously, so this awaits the ``WebViews``
        native module rather than issuing a view command. Strings come back
        as-is, ``null`` and ``undefined`` as ``""``, and other values in
        their JSON form (``"42"``, ``"true"``).

        Raises:
            NativeModuleError: If the script throws or the page can't be
                reached (a cross-origin page in the browser preview).
        """
        from .native_modules.registry import native_module

        result = await native_module("WebViews").call_async("eval_js", tag=self.tag, script=str(script))
        return "" if result is None else str(result)

    async def can_go_back(self) -> bool:
        """Whether the page history has an entry to go back to."""
        return bool(self.command("can_go_back"))

    async def can_go_forward(self) -> bool:
        """Whether the page history has an entry to go forward to."""
        return bool(self.command("can_go_forward"))

    async def get_url(self) -> str:
        """Return the URL of the current page."""
        result = self.command("get_url")
        return "" if result is None else str(result)


HANDLE_TYPES: Dict[str, type[ViewHandle]] = {
    "TextInput": TextInputHandle,
    "ScrollView": ScrollViewHandle,
    "WebView": WebViewHandle,
}
"""Element types with a specialized handle; every other type gets a ``ViewHandle``."""


def make_handle(type_name: str, tag: int, backend: Any) -> ViewHandle:
    """Build the handle the reconciler publishes on ``ref.current`` for ``type_name``."""
    return HANDLE_TYPES.get(type_name, ViewHandle)(tag, type_name, backend)
