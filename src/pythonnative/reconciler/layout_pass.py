"""The layout phase of a reconciler pass.

After native mutations commit, the reconciler builds a
[`LayoutNode`][pythonnative.layout.LayoutNode] tree mirroring the
native nodes of the mounted tree, runs the flexbox engine against the
viewport, and emits a ``SetFrameOp`` for every frame that changed.

Two details keep this cheap on every state update:

- **Incremental rebuild.** Each native ``VNode`` caches its
  ``LayoutNode``; subtrees whose props and child list are unchanged
  reuse the cached node with ``dirty=False`` so the engine can serve
  their sizes from its measurement memo.
- **Frame diffing.** Frames equal to the last applied frame produce no
  op at all.

Detached subtrees (``Modal``, ``Portal``) are excluded from the main
flow and laid out against the viewport as independent trees, since
their content lives in a separately presented native container.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from .. import diagnostics
from ..element import Element
from ..layout import LAYOUT_STYLE_KEYS, LayoutNode, calculate_layout, extract_layout_style
from ..mutations import Mutation, SetFrameOp
from .vnode import DETACHED_TYPES, VNode

if TYPE_CHECKING:
    pass

Frame = Tuple[float, float, float, float]

# Native leaves whose size derives from their content; any prop change
# invalidates their measurement.
INTRINSIC_TYPES = frozenset(
    {
        "Text",
        "Button",
        "Image",
        "TextInput",
        "Switch",
        "Slider",
        "ProgressBar",
        "ActivityIndicator",
        "TabBar",
        "Picker",
        "Checkbox",
        "SegmentedControl",
        "DatePicker",
    }
)

# Childless native leaves that get a measure callback. Extends the
# intrinsic set with ``VirtualList``, whose handlers report "fill the
# available space" (like a ScrollView clamped to its parent): without
# the callback an unstyled list would collapse to 0 points and the
# platform virtualizer would never bind a row.
MEASURED_LEAF_TYPES = INTRINSIC_TYPES | {"VirtualList"}


def affects_layout(type_name: str, changed: Dict[str, Any]) -> bool:
    """Whether ``changed`` props can alter a native node's layout."""
    if type_name in INTRINSIC_TYPES:
        return True
    return any(key in LAYOUT_STYLE_KEYS for key in changed)


class LayoutMixin:
    """Layout-pass behavior mixed into the reconciler."""

    # Provided by the concrete reconciler.
    backend: Any
    root: Optional[VNode]
    _ops: List[Mutation]

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
        if self.root is not None:
            self._run_layout()
            self._flush_ops()
            self._dispatch_layout_events()

    def compute_layout_for_test(self, viewport_width: float, viewport_height: float) -> Optional[LayoutNode]:
        """Build and compute a layout tree without touching the backend.

        Returns the synthetic viewport ``LayoutNode`` with all
        descendants positioned, or ``None`` if nothing is mounted.
        """
        if self.root is None:
            return None
        roots = self._build_layout_list(self.root)
        if not roots:
            return None
        viewport = LayoutNode(style={"width": viewport_width, "height": viewport_height}, children=list(roots))
        calculate_layout(viewport, viewport_width, viewport_height)
        return viewport

    # ------------------------------------------------------------------
    # Hooks used by the core
    # ------------------------------------------------------------------

    def _flush_ops(self) -> None: ...  # pragma: no cover

    @staticmethod
    def _mark_layout_dirty(node: VNode) -> None:
        node.layout_dirty = True
        node.layout_node = None

    # ------------------------------------------------------------------
    # The pass
    # ------------------------------------------------------------------

    def _run_layout(self) -> None:
        """Build/refresh the layout tree, compute frames, and emit changed ones.

        Wraps the user's native roots in a synthetic outer ``LayoutNode``
        sized to the viewport so the root fills the screen by default.
        Skipped until the host has supplied a viewport size.

        The first native root's own frame is intentionally left alone:
        its position and size are owned by the screen host (iOS places
        it below the safe-area inset; Android attaches it with
        ``MATCH_PARENT``).
        """
        root = self.root
        if root is None:
            return
        viewport_w, viewport_h = self._viewport_size
        if viewport_w <= 0 or viewport_h <= 0:
            return

        self._layout_pass_count += 1
        layout_roots = self._build_layout_list_cached(root)
        if layout_roots:
            viewport = LayoutNode(style={"width": viewport_w, "height": viewport_h}, children=list(layout_roots))
            viewport.dirty = True
            calculate_layout(viewport, viewport_w, viewport_h)
            for i, layout_root in enumerate(layout_roots):
                if i == 0:
                    for child in layout_root.children:
                        self._collect_frames(child, 0.0, 0.0)
                else:
                    self._collect_frames(layout_root, 0.0, 0.0)
        self._layout_detached_subtrees(root, viewport_w, viewport_h)
        self._clear_layout_dirty(root)

    def _layout_detached_subtrees(self, node: VNode, viewport_w: float, viewport_h: float) -> None:
        element = node.element
        if isinstance(element.type, str) and element.type in DETACHED_TYPES:
            active = bool(element.props.get("visible")) if element.type == "Modal" else True
            if not active:
                return
            child_layouts: List[LayoutNode] = []
            for child in node.children:
                child_layouts.extend(self._build_layout_list(child))
            if child_layouts:
                viewport = LayoutNode(style={"width": viewport_w, "height": viewport_h}, children=child_layouts)
                calculate_layout(viewport, viewport_w, viewport_h)
                for c in viewport.children:
                    self._collect_frames(c, 0.0, 0.0)
            for child in node.children:
                self._layout_detached_subtrees(child, viewport_w, viewport_h)
            return
        for child in node.children:
            self._layout_detached_subtrees(child, viewport_w, viewport_h)

    def _build_layout_list_cached(self, node: VNode) -> List[LayoutNode]:
        """Like ``_build_layout_list`` but reuses cached subtrees when clean."""
        element = node.element
        if not node.is_native:
            out: List[LayoutNode] = []
            for child in node.children:
                out.extend(self._build_layout_list_cached(child))
            return out
        if element.type in DETACHED_TYPES:
            return []

        child_layouts: List[LayoutNode] = []
        for child in node.children:
            child_layouts.extend(self._build_layout_list_cached(child))

        cached = node.layout_node
        if cached is not None and not node.layout_dirty:
            cached_children = self._direct_child_layouts(cached, element)
            if len(cached_children) == len(child_layouts) and all(
                a is b for a, b in zip(cached_children, child_layouts)
            ):
                return [cached]

        layout = self._new_layout_node(node)
        for child_layout in child_layouts:
            if element.type == "ScrollView":
                child_layout = self._wrap_scroll_axis(child_layout, self._scroll_axis(element))
                child_layout.dirty = True
            layout.children.append(child_layout)
        node.layout_node = layout
        return [layout]

    def _build_layout_list(self, node: VNode) -> List[LayoutNode]:
        """Build fresh (uncached) ``LayoutNode`` for ``node`` and its subtree."""
        element = node.element
        if not node.is_native:
            out: List[LayoutNode] = []
            for child in node.children:
                out.extend(self._build_layout_list(child))
            return out
        if element.type in DETACHED_TYPES:
            return []
        layout = self._new_layout_node(node)
        for child in node.children:
            for child_layout in self._build_layout_list(child):
                if element.type == "ScrollView":
                    child_layout = self._wrap_scroll_axis(child_layout, self._scroll_axis(element))
                    child_layout.dirty = True
                layout.children.append(child_layout)
        return [layout]

    def _new_layout_node(self, node: VNode) -> LayoutNode:
        element = node.element
        layout = LayoutNode(style=extract_layout_style(element.props), user_data=node)
        layout.dirty = True
        if element.type == "ScrollView":
            # Mark the scroll axis so the engine clamps the container's
            # main-axis size to its parent's available space; otherwise
            # the container grows to fit its content and nothing scrolls.
            layout._pn_scroll_axis = self._scroll_axis(element)
        if not node.children:
            measure = self._make_measure_callback(node)
            if measure is not None:
                layout.measure = measure
        return layout

    @staticmethod
    def _scroll_axis(element: Element) -> str:
        return "x" if element.props.get("scroll_axis", "vertical") == "horizontal" else "y"

    @staticmethod
    def _direct_child_layouts(layout: LayoutNode, element: Element) -> List[LayoutNode]:
        """Return the cached child layout nodes, unwrapping ScrollView wrappers."""
        if element.type == "ScrollView":
            out: List[LayoutNode] = []
            for wrapper in layout.children:
                out.extend(wrapper.children)
            return out
        return list(layout.children)

    def _clear_layout_dirty(self, node: VNode) -> None:
        node.layout_dirty = False
        layout = node.layout_node
        if layout is not None:
            layout.dirty = False
            for layout_child in layout.children:
                layout_child.dirty = False
        for child in node.children:
            self._clear_layout_dirty(child)

    @staticmethod
    def _wrap_scroll_axis(child: LayoutNode, axis: str) -> LayoutNode:
        """Wrap ``child`` so the layout engine treats one axis as unbounded."""
        wrapper = LayoutNode(style={"flex_direction": "column" if axis == "y" else "row"}, user_data=None)
        wrapper.children.append(child)
        return wrapper

    def _make_measure_callback(self, node: VNode) -> Optional[Callable[[float, float], Tuple[float, float]]]:
        """Return a measure callback for ``node`` if it has an intrinsic size."""
        if node.element.type not in MEASURED_LEAF_TYPES or node.tag is None:
            return None
        backend = self.backend
        tag = node.tag

        def measure(max_w: float, max_h: float) -> Tuple[float, float]:
            cache = node.measure_cache
            if cache is not None and cache[0] == max_w and cache[1] == max_h:
                return (cache[2], cache[3])
            try:
                w, h = backend.measure_intrinsic(tag, max_w, max_h)
                result = (float(w), float(h))
                node.measure_cache = (max_w, max_h, result[0], result[1])
                return result
            except Exception:
                return (0.0, 0.0)

        return measure

    def _collect_frames(self, layout_node: LayoutNode, parent_x: float, parent_y: float) -> None:
        """Walk a positioned layout tree and emit ``SetFrameOp`` for changed frames.

        Coordinates accumulate through transparent wrapper nodes (the
        ScrollView axis wrapper) so the native view receives its
        position relative to its true native parent.
        """
        node: Optional[VNode] = layout_node.user_data
        if node is not None and node.tag is not None:
            frame: Frame = (
                layout_node.x + parent_x,
                layout_node.y + parent_y,
                layout_node.width,
                layout_node.height,
            )
            if node.last_frame != frame:
                node.last_frame = frame
                self._ops.append(SetFrameOp(node.tag, *frame))
                ref = node.element.props.get("ref")
                if ref is not None and hasattr(ref, "current"):
                    try:
                        ref._pn_frame = frame
                    except Exception:
                        pass
                if "on_layout" in node.element.props:
                    self._pending_layout_events.append((node.tag, frame))
            child_x = child_y = 0.0
        else:
            child_x = layout_node.x + parent_x
            child_y = layout_node.y + parent_y
        for child in layout_node.children:
            self._collect_frames(child, child_x, child_y)

    def _dispatch_layout_events(self) -> None:
        """Fire queued ``on_layout`` callbacks after frames were applied."""
        if not self._pending_layout_events:
            return
        from ..events import dispatch_event

        pending, self._pending_layout_events = self._pending_layout_events, []
        for tag, frame in pending:
            try:
                dispatch_event(tag, "on_layout", {"x": frame[0], "y": frame[1], "width": frame[2], "height": frame[3]})
            except Exception as exc:
                diagnostics.report_error(exc, phase="event")
