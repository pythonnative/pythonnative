"""The layout phase of a reconciler pass.

Layout runs in the renderer core (RFC 0007), beside the shadow tree the
commits build. Each commit carries the screen's layout roots and viewport;
the core answers with the frames Python observes (views with a ref or an
``on_layout`` callback). This mixin publishes those frames to imperative
handles and queues ``on_layout`` events. A viewport change without a
commit asks the core to lay out again.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from .. import diagnostics
from ..mutations import Mutation
from ..profiling import profiled
from ..style import LAYOUT_STYLE_KEYS
from .vnode import VNode

if TYPE_CHECKING:
    pass

Frame = Tuple[float, float, float, float]

_ViewHandle: Any = None
_LayoutEvent: Any = None


def _layout_event(frame: Frame) -> Any:
    """Build the ``LayoutEvent`` record for ``frame`` (import deferred to avoid a cycle)."""
    global _LayoutEvent
    if _LayoutEvent is None:
        from ..components.events import LayoutEvent

        _LayoutEvent = LayoutEvent
    return _LayoutEvent(*frame)


def _is_view_handle(value: Any) -> bool:
    """Whether ``value`` is an imperative handle whose ``frame`` the layout pass maintains."""
    global _ViewHandle
    if _ViewHandle is None:
        from ..handles import ViewHandle

        _ViewHandle = ViewHandle
    return isinstance(value, _ViewHandle)


def affects_layout(type_name: str, changed: Dict[str, Any]) -> bool:
    """Whether ``changed`` props can alter a native node's layout."""
    from ..sdk.schema import COMPONENTS

    schema = COMPONENTS.get(type_name)
    if schema is None:
        return True
    if any(schema.props.get(key, {}).get("native", {}).get("invalidates_layout") for key in changed):
        return True
    return any(key in LAYOUT_STYLE_KEYS for key in changed)


class LayoutMixin:
    """Layout-pass behavior mixed into the reconciler."""

    # Provided by the concrete reconciler.
    backend: Any
    root: Optional[VNode]
    _ops: List[Mutation]
    _rendering: bool
    _tag_nodes: Dict[int, VNode]
    _native_roots: Callable[[VNode], List[VNode]]

    def _init_layout_state(self) -> None:
        self._viewport_size: Tuple[float, float] = (0.0, 0.0)
        self._layout_pass_count = 0
        # ``(tag, frame)`` pairs whose ``on_layout`` should fire after
        # the layout pass commits (frames are only queued on change).
        self._pending_layout_events: List[Tuple[int, Frame]] = []

    # ------------------------------------------------------------------
    # Public surface
    # ------------------------------------------------------------------

    @property
    def viewport_size(self) -> Tuple[float, float]:
        """The last viewport size supplied by the host, ``(0, 0)`` before layout is possible."""
        return self._viewport_size

    def set_viewport_size(self, width: float, height: float) -> None:
        """Update the viewport size and re-run layout if it changed.

        Called by the screen host whenever the platform reports a new
        container size. The first call after mount triggers the
        initial layout pass; identical sizes are no-ops.
        """
        if width <= 0 or height <= 0:
            return
        if self._viewport_size == (width, height):
            return
        self._viewport_size = (width, height)
        if self.root is not None and not getattr(self, "commit_pending", False):
            self._run_layout()
            self._flush_ops()
            self._dispatch_layout_events()

    # ------------------------------------------------------------------
    # Hooks used by the core
    # ------------------------------------------------------------------

    def _flush_ops(self) -> None: ...  # pragma: no cover

    # ------------------------------------------------------------------
    # The pass
    # ------------------------------------------------------------------

    @profiled("layout")
    def _run_layout(self) -> None:
        """Ask the core to lay out the screen's roots at the current viewport.

        A commit already carries its layout request, so this only does
        work when the viewport changed or nothing was committed since the
        last layout. The first native root's own frame is left to the
        screen host (iOS places it below the safe-area inset; Android
        attaches it with ``MATCH_PARENT``).
        """
        root = self.root
        if root is None:
            return
        viewport_w, viewport_h = self._viewport_size
        if viewport_w <= 0 or viewport_h <= 0:
            return
        compute = getattr(self.backend, "compute_layout", None)
        if compute is None:
            return
        self._layout_pass_count += 1
        compute([node.tag for node in self._native_roots(root)], viewport_w, viewport_h)

    def _accept_native_layout(self, frames: list[list[float]]) -> None:
        """Update handles and queue observations only for acknowledged native frames."""
        for tag, x, y, width, height in frames:
            node = self._tag_nodes.get(int(tag))
            if node is None or not node.mounted:
                continue
            self._publish_frame(node, (x, y, width, height))
        if not self._rendering:
            self._dispatch_layout_events()

    def _publish_frame(self, node: VNode, frame: Frame) -> None:
        """Record a committed frame on the node, its ref's handle, and the ``on_layout`` queue."""
        if node.last_frame == frame:
            return
        node.last_frame = frame
        ref = node.element.props.get("ref")
        if ref is not None:
            handle = getattr(ref, "current", None)
            if handle is not None:
                self._publish_frame_to_handle(handle, frame)
        if "on_layout" in node.element.props and node.tag is not None:
            self._pending_layout_events.append((node.tag, frame))

    @staticmethod
    def _publish_frame_to_handle(handle: Any, frame: Frame) -> None:
        """Write ``frame`` to ``handle.frame`` when ``handle`` is an imperative view handle."""
        if _is_view_handle(handle):
            handle.frame = _layout_event(frame)

    def _dispatch_layout_events(self) -> None:
        """Fire queued ``on_layout`` callbacks (with a ``LayoutEvent``) after frames were applied."""
        if not self._pending_layout_events:
            return
        from ..events import dispatch_event

        pending, self._pending_layout_events = self._pending_layout_events, []
        for tag, frame in pending:
            try:
                dispatch_event(tag, "on_layout", _layout_event(frame))
            except Exception as exc:
                diagnostics.report_error(exc, phase="event")
