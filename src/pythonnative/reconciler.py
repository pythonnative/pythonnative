"""Virtual-tree reconciler.

Maintains a tree of [`VNode`][pythonnative.reconciler.VNode] objects
(each wrapping a native view) and diffs incoming
[`Element`][pythonnative.Element] trees to apply the minimal set of
native mutations.

Supports:

- **Native elements** (`type` is a string like `"Text"`).
- **Function components** (`type` is a callable decorated with
  [`component`][pythonnative.component]). Their hook state is preserved
  across renders.
- **Provider elements** (`type == "__Provider__"`), which push and pop
  context values during tree traversal.
- **Error boundary elements** (`type == "__ErrorBoundary__"`), which
  catch exceptions in child subtrees and render a fallback.
- **Key-based child reconciliation** for stable identity across
  re-renders.
- **Post-render effect flushing**. After each mount or reconcile pass,
  all queued effects are executed so they see the committed native tree.
- **Layout pass**: after every commit, a parallel
  [`LayoutNode`][pythonnative.layout.LayoutNode] tree is built from
  the committed VNodes and fed through
  [`calculate_layout`][pythonnative.layout.calculate_layout]; the
  resulting per-node frames are applied via the backend's
  ``set_frame``. The viewport size is supplied by the screen host via
  [`set_viewport_size`][pythonnative.reconciler.Reconciler.set_viewport_size].
"""

import os
import sys
from typing import Any, List, Optional, Tuple

from .element import Element
from .layout import LayoutNode, calculate_layout, extract_layout_style

# Props the reconciler consumes itself (i.e., never forwards to the
# native handler). ``ref`` is one such prop: components pass a dict
# from ``use_ref()`` and the reconciler populates ``ref["current"]``
# with the underlying native view, mirroring React's ``ref`` semantics.
_RECONCILER_OWNED_PROPS = frozenset({"ref"})


class VNode:
    """A mounted [`Element`][pythonnative.Element] plus its native view.

    The reconciler walks parallel trees of `VNode` and incoming
    `Element` to compute the minimal set of native mutations.

    Attributes:
        element: The `Element` last rendered into this slot.
        native_view: The platform-native view (e.g., an Android `View`
            or an iOS `UIView`). May be `None` for purely virtual
            wrappers such as providers and error boundaries.
        children: Ordered list of child `VNode` instances.
        hook_state: The component's
            [`HookState`][pythonnative.hooks.HookState] when the node
            wraps a function component, otherwise `None`.
    """

    __slots__ = ("element", "native_view", "children", "hook_state", "_rendered")

    def __init__(self, element: Element, native_view: Any, children: List["VNode"]) -> None:
        self.element = element
        self.native_view = native_view
        self.children = children
        self.hook_state: Any = None
        self._rendered: Optional[Element] = None


class Reconciler:
    """Create, diff, and patch native view trees from `Element` descriptors.

    After each [`mount`][pythonnative.reconciler.Reconciler.mount] or
    [`reconcile`][pythonnative.reconciler.Reconciler.reconcile] call the
    reconciler walks the committed tree and flushes all pending effects
    so effect callbacks run *after* native mutations are applied.

    Args:
        backend: An object implementing the native-view protocol
            (`create_view`, `update_view`, `add_child`, `remove_child`,
            `insert_child`). PythonNative ships an Android backend and
            an iOS backend; tests can pass a mock.
    """

    def __init__(self, backend: Any) -> None:
        self.backend = backend
        self._tree: Optional[VNode] = None
        self._screen_re_render: Optional[Any] = None
        self._viewport_size: Tuple[float, float] = (0.0, 0.0)
        self._layout_pass = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def mount(self, element: Element) -> Any:
        """Build native views from `element` and return the root native view.

        Args:
            element: The root `Element` to render.

        Returns:
            The platform-native view that represents the root of the
            mounted tree.
        """
        self._log_viewport(
            f"mount: start type={self._type_label(element.type)!r} props={self._props_debug(element.props)}"
        )
        self._tree = self._create_tree(element)
        self._log_viewport(f"mount: tree created root={self._node_debug(self._tree)}")
        self._flush_effects()
        self._run_layout()
        self._log_viewport(f"mount: done root_view={self._obj_debug(self._tree.native_view)}")
        return self._tree.native_view

    def reconcile(self, new_element: Element) -> Any:
        """Diff `new_element` against the current tree and patch native views.

        Args:
            new_element: The desired root element after a state change.

        Returns:
            The (possibly replaced) root native view.
        """
        self._log_viewport(
            "reconcile: entering "
            f"(have_tree={self._tree is not None}) new_type={self._type_label(new_element.type)!r} "
            f"new_props={self._props_debug(new_element.props)}"
        )
        if self._tree is None:
            self._tree = self._create_tree(new_element)
            self._log_viewport(f"reconcile: created initial root={self._node_debug(self._tree)}")
            self._flush_effects()
            self._run_layout()
            return self._tree.native_view

        self._tree = self._reconcile_node(self._tree, new_element)
        self._log_viewport(f"reconcile: tree reconciled root={self._node_debug(self._tree)}")
        self._flush_effects()
        self._run_layout()
        self._log_viewport("reconcile: done")
        return self._tree.native_view

    def set_viewport_size(self, width: float, height: float) -> None:
        """Update the viewport size and re-run layout if it changed.

        Called by the screen host whenever the platform reports a new
        container size (Android: ``onLayoutChange``; iOS:
        ``viewDidLayoutSubviews``). The first call after mount
        triggers the initial layout pass; subsequent identical
        sizes are no-ops.

        Args:
            width: Viewport width in points.
            height: Viewport height in points.
        """
        if width <= 0 or height <= 0:
            self._log_viewport(f"set_viewport_size: ignored non-positive ({width},{height})")
            return
        if self._viewport_size == (width, height):
            self._log_viewport(f"set_viewport_size: unchanged at ({width},{height})")
            return
        prev = self._viewport_size
        self._viewport_size = (width, height)
        self._log_viewport(f"set_viewport_size: {prev} -> ({width},{height}); running layout")
        if self._tree is not None:
            self._run_layout()

    @staticmethod
    def _log_viewport(msg: str) -> None:
        """Emit optional layout diagnostics for local debugging."""
        if os.environ.get("PYTHONNATIVE_DEBUG", "").lower() not in {"1", "true", "yes", "on"}:
            return
        try:
            print(f"[PN] reconciler: {msg}", flush=True)
        except Exception:
            pass

    @staticmethod
    def _type_label(type_obj: Any) -> str:
        if isinstance(type_obj, str):
            return type_obj
        return getattr(type_obj, "__name__", repr(type_obj))

    @staticmethod
    def _obj_debug(obj: Any) -> str:
        if obj is None:
            return "<None>"
        ptr = getattr(obj, "ptr", None)
        addr: Optional[int] = None
        if isinstance(ptr, (bytes, bytearray)):
            try:
                addr = int.from_bytes(ptr, byteorder=sys.byteorder, signed=False)
            except Exception:
                addr = None
        elif isinstance(ptr, int):
            addr = ptr
        elif ptr is not None:
            value = getattr(ptr, "value", None)
            if isinstance(value, int):
                addr = value
            else:
                try:
                    addr = int(ptr)
                except Exception:
                    addr = None
        addr_part = f" ptr=0x{addr:x}" if addr is not None else ""
        return f"{type(obj).__name__}(py_id=0x{id(obj):x}{addr_part})"

    @classmethod
    def _props_debug(cls, props: dict) -> str:
        interesting = []
        for key in ("title", "text", "active_tab", "scroll_axis", "width", "height", "flex", "key"):
            if key in props:
                interesting.append(f"{key}={props[key]!r}")
        if "items" in props and isinstance(props["items"], list):
            names = [item.get("name", item.get("title", "")) for item in props["items"][:4]]
            interesting.append(f"items_len={len(props['items'])} items={names!r}")
        callback_keys = sorted(key for key, value in props.items() if callable(value))
        if callback_keys:
            interesting.append(f"callbacks={callback_keys!r}")
        return "{" + ", ".join(interesting) + "}"

    @classmethod
    def _node_debug(cls, vnode: VNode) -> str:
        element = vnode.element
        return (
            f"type={cls._type_label(element.type)!r} key={element.key!r} "
            f"props={cls._props_debug(element.props)} view={cls._obj_debug(vnode.native_view)}"
        )

    # ------------------------------------------------------------------
    # Effect flushing
    # ------------------------------------------------------------------

    def _flush_effects(self) -> None:
        """Walk the committed tree and flush pending effects (depth-first)."""
        if self._tree is not None:
            self._flush_tree_effects(self._tree)

    def _flush_tree_effects(self, node: VNode) -> None:
        for child in node.children:
            self._flush_tree_effects(child)
        if node.hook_state is not None:
            node.hook_state.flush_pending_effects()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_tree(self, element: Element) -> VNode:
        # Provider: push context, create child, pop context
        if element.type == "__Provider__":
            context = element.props["__context__"]
            context._stack.append(element.props["__value__"])
            try:
                child_node = self._create_tree(element.children[0]) if element.children else None
            finally:
                context._stack.pop()
            native_view = child_node.native_view if child_node else None
            children = [child_node] if child_node else []
            return VNode(element, native_view, children)

        # Error boundary: catch exceptions in the child subtree
        if element.type == "__ErrorBoundary__":
            return self._create_error_boundary(element)

        # Function component: call with hook context
        if callable(element.type):
            from .hooks import HookState, _set_hook_state

            hook_state = HookState()
            hook_state._trigger_render = self._screen_re_render
            _set_hook_state(hook_state)
            try:
                rendered = element.type(**element.props)
            finally:
                _set_hook_state(None)

            child_node = self._create_tree(rendered)
            vnode = VNode(element, child_node.native_view, [child_node])
            vnode.hook_state = hook_state
            vnode._rendered = rendered
            return vnode

        # Native element
        self._log_viewport(
            f"_create_tree: native start type={element.type!r} props={self._props_debug(element.props)} "
            f"children={len(element.children)}"
        )
        handler_props = self._strip_reconciler_props(element.props)
        try:
            native_view = self.backend.create_view(element.type, handler_props)
        except Exception as e:
            self._log_viewport(f"_create_tree: BACKEND.create_view({element.type!r}) RAISED {type(e).__name__}: {e!r}")
            raise
        self._log_viewport(f"_create_tree: native created type={element.type!r} view={self._obj_debug(native_view)}")
        self._attach_ref(element, native_view)
        children: List[VNode] = []
        for i, child_el in enumerate(element.children):
            child_type = self._type_label(child_el.type)
            self._log_viewport(f"_create_tree: creating child[{i}] type={child_type!r} of {element.type!r}")
            try:
                child_node = self._create_tree(child_el)
            except Exception as e:
                self._log_viewport(
                    f"_create_tree: child[{i}] (type={child_type!r}) of {element.type!r} RAISED "
                    f"{type(e).__name__}: {e!r}"
                )
                raise
            self._log_viewport(
                f"_create_tree: add child[{i}] parent={element.type!r} child={self._node_debug(child_node)}"
            )
            try:
                self.backend.add_child(native_view, child_node.native_view, element.type)
            except Exception as e:
                self._log_viewport(
                    f"_create_tree: backend.add_child(parent={element.type!r}, "
                    f"child={child_type!r}) RAISED {type(e).__name__}: {e!r}"
                )
                raise
            self._log_viewport(f"_create_tree: add child[{i}] done parent={element.type!r}")
            children.append(child_node)
        vnode = VNode(element, native_view, children)
        self._log_viewport(f"_create_tree: native done {self._node_debug(vnode)} children={len(children)}")
        return vnode

    def _create_error_boundary(self, element: Element) -> VNode:
        fallback_fn = element.props.get("__fallback__")
        try:
            child_node = self._create_tree(element.children[0]) if element.children else None
        except Exception as exc:
            if fallback_fn is not None:
                fallback_el = fallback_fn(exc) if callable(fallback_fn) else fallback_fn
                child_node = self._create_tree(fallback_el)
            else:
                raise
        native_view = child_node.native_view if child_node else None
        children = [child_node] if child_node else []
        return VNode(element, native_view, children)

    def _reconcile_node(self, old: VNode, new_el: Element) -> VNode:
        if not self._same_type(old.element, new_el):
            self._log_viewport(
                "_reconcile_node: replace "
                f"old={self._node_debug(old)} new_type={self._type_label(new_el.type)!r} "
                f"new_props={self._props_debug(new_el.props)}"
            )
            new_node = self._create_tree(new_el)
            self._destroy_tree(old)
            self._log_viewport(f"_reconcile_node: replace done new={self._node_debug(new_node)}")
            return new_node

        # Provider
        if new_el.type == "__Provider__":
            context = new_el.props["__context__"]
            context._stack.append(new_el.props["__value__"])
            try:
                if old.children and new_el.children:
                    child = self._reconcile_node(old.children[0], new_el.children[0])
                    old.children = [child]
                    old.native_view = child.native_view
                elif new_el.children:
                    child = self._create_tree(new_el.children[0])
                    old.children = [child]
                    old.native_view = child.native_view
            finally:
                context._stack.pop()
            old.element = new_el
            return old

        # Error boundary
        if new_el.type == "__ErrorBoundary__":
            return self._reconcile_error_boundary(old, new_el)

        # Function component
        if callable(new_el.type):
            from .hooks import _set_hook_state

            hook_state = old.hook_state
            if hook_state is None:
                from .hooks import HookState

                hook_state = HookState()
            hook_state.reset_index()
            hook_state._trigger_render = self._screen_re_render
            _set_hook_state(hook_state)
            try:
                rendered = new_el.type(**new_el.props)
            finally:
                _set_hook_state(None)

            if old.children:
                child = self._reconcile_node(old.children[0], rendered)
            else:
                child = self._create_tree(rendered)
            old.children = [child]
            old.native_view = child.native_view
            old.element = new_el
            old.hook_state = hook_state
            old._rendered = rendered
            return old

        # Native element
        changed = self._diff_props(old.element.props, new_el.props)
        if changed:
            self._log_viewport(
                "_reconcile_node: native update "
                f"type={old.element.type!r} view={self._obj_debug(old.native_view)} "
                f"changed={self._props_debug(changed)}"
            )
            self.backend.update_view(old.native_view, old.element.type, changed)
            self._log_viewport(f"_reconcile_node: native update done type={old.element.type!r}")
        else:
            self._log_viewport(f"_reconcile_node: native unchanged type={old.element.type!r}")

        # Re-attach the ref if the ref dict identity changed (so we
        # never leave a stale ref pointing at a destroyed view, and so
        # a freshly-supplied ref gets ``current`` populated on update).
        old_ref = old.element.props.get("ref") if old.element.props else None
        new_ref = new_el.props.get("ref") if new_el.props else None
        if old_ref is not new_ref:
            if isinstance(old_ref, dict):
                try:
                    old_ref["current"] = None
                except Exception:
                    pass
            self._attach_ref(new_el, old.native_view)

        self._log_viewport(
            f"_reconcile_node: reconcile children parent={old.element.type!r} new_children={len(new_el.children)}"
        )
        self._reconcile_children(old, new_el.children)
        old.element = new_el
        self._log_viewport(f"_reconcile_node: native done {self._node_debug(old)} children={len(old.children)}")
        return old

    def _reconcile_error_boundary(self, old: VNode, new_el: Element) -> VNode:
        fallback_fn = new_el.props.get("__fallback__")
        try:
            if old.children and new_el.children:
                child = self._reconcile_node(old.children[0], new_el.children[0])
                old.children = [child]
                old.native_view = child.native_view
            elif new_el.children:
                child = self._create_tree(new_el.children[0])
                old.children = [child]
                old.native_view = child.native_view
        except Exception as exc:
            for c in old.children:
                self._destroy_tree(c)
            if fallback_fn is not None:
                fallback_el = fallback_fn(exc) if callable(fallback_fn) else fallback_fn
                child = self._create_tree(fallback_el)
                old.children = [child]
                old.native_view = child.native_view
            else:
                raise
        old.element = new_el
        return old

    def _reconcile_children(self, parent: VNode, new_children: List[Element]) -> None:
        old_children = parent.children
        parent_type = parent.element.type
        is_native = isinstance(parent_type, str) and parent_type not in ("__Provider__", "__ErrorBoundary__")

        old_by_key: dict = {}
        old_unkeyed: list = []
        for child in old_children:
            if child.element.key is not None:
                old_by_key[child.element.key] = child
            else:
                old_unkeyed.append(child)

        new_child_nodes: List[VNode] = []
        used_keyed: set = set()
        unkeyed_iter = iter(old_unkeyed)

        for i, new_el in enumerate(new_children):
            matched: Optional[VNode] = None

            if new_el.key is not None and new_el.key in old_by_key:
                matched = old_by_key[new_el.key]
                used_keyed.add(new_el.key)
            elif new_el.key is None:
                matched = next(unkeyed_iter, None)

            if matched is None:
                self._log_viewport(
                    f"_reconcile_children: create child[{i}] parent={self._type_label(parent_type)!r} "
                    f"type={self._type_label(new_el.type)!r}"
                )
                node = self._create_tree(new_el)
                if is_native:
                    self._log_viewport(
                        f"_reconcile_children: add new child[{i}] parent={self._obj_debug(parent.native_view)} "
                        f"child={self._obj_debug(node.native_view)}"
                    )
                    self.backend.add_child(parent.native_view, node.native_view, parent_type)
                new_child_nodes.append(node)
            elif not self._same_type(matched.element, new_el):
                self._log_viewport(
                    f"_reconcile_children: replace child[{i}] old={self._node_debug(matched)} "
                    f"new_type={self._type_label(new_el.type)!r}"
                )
                if is_native:
                    self.backend.remove_child(parent.native_view, matched.native_view, parent_type)
                self._destroy_tree(matched)
                node = self._create_tree(new_el)
                if is_native:
                    self.backend.insert_child(parent.native_view, node.native_view, parent_type, i)
                new_child_nodes.append(node)
            else:
                old_native = matched.native_view
                self._log_viewport(f"_reconcile_children: update child[{i}] {self._node_debug(matched)}")
                updated = self._reconcile_node(matched, new_el)
                if is_native and updated.native_view is not old_native:
                    self._log_viewport(
                        f"_reconcile_children: child[{i}] native view changed "
                        f"old={self._obj_debug(old_native)} new={self._obj_debug(updated.native_view)}"
                    )
                    self.backend.remove_child(parent.native_view, old_native, parent_type)
                    self.backend.insert_child(parent.native_view, updated.native_view, parent_type, i)
                new_child_nodes.append(updated)

        # Destroy unused old nodes
        for key, node in old_by_key.items():
            if key not in used_keyed:
                self._log_viewport(f"_reconcile_children: destroy unused keyed key={key!r} {self._node_debug(node)}")
                if is_native:
                    self.backend.remove_child(parent.native_view, node.native_view, parent_type)
                self._destroy_tree(node)
        for node in unkeyed_iter:
            self._log_viewport(f"_reconcile_children: destroy unused unkeyed {self._node_debug(node)}")
            if is_native:
                self.backend.remove_child(parent.native_view, node.native_view, parent_type)
            self._destroy_tree(node)

        # Reorder native children when keyed children changed positions.
        # Without this, native sibling order drifts from the logical tree
        # when keyed children swap positions across reconcile passes.
        if is_native and used_keyed:
            old_key_order = [c.element.key for c in old_children if c.element.key in used_keyed]
            new_key_order = [n.element.key for n in new_child_nodes if n.element.key in used_keyed]
            if old_key_order != new_key_order:
                self._log_viewport(
                    f"_reconcile_children: reorder keyed children old={old_key_order!r} new={new_key_order!r}"
                )
                for node in new_child_nodes:
                    self.backend.remove_child(parent.native_view, node.native_view, parent_type)
                for node in new_child_nodes:
                    self.backend.add_child(parent.native_view, node.native_view, parent_type)

        parent.children = new_child_nodes
        self._log_viewport(
            f"_reconcile_children: done parent={self._type_label(parent_type)!r} children={len(parent.children)}"
        )

    def _destroy_tree(self, node: VNode) -> None:
        if node.hook_state is not None:
            node.hook_state.cleanup_all_effects()
        if node.element is not None:
            self._detach_ref(node.element)
        for child in node.children:
            self._destroy_tree(child)
        node.children = []

    @staticmethod
    def _strip_reconciler_props(props: dict) -> dict:
        """Return ``props`` with reconciler-owned keys removed.

        Reconciler-owned keys (``ref``, internal ``__*__`` keys) are
        consumed by the reconciler itself and must never reach the
        native handler — handlers don't know what to do with them and
        would incorrectly forward them to the underlying view.
        """
        if not props:
            return props
        stripped = {}
        for key, value in props.items():
            if key in _RECONCILER_OWNED_PROPS or key.startswith("__"):
                continue
            stripped[key] = value
        return stripped

    @staticmethod
    def _attach_ref(element: Element, native_view: Any) -> None:
        """Set ``ref["current"]`` if the element carries a ``ref`` prop."""
        ref = element.props.get("ref") if element.props else None
        if isinstance(ref, dict):
            ref["current"] = native_view

    @staticmethod
    def _detach_ref(element: Element) -> None:
        """Clear ``ref["current"]`` so consumers don't hold a stale handle."""
        ref = element.props.get("ref") if element.props else None
        if isinstance(ref, dict):
            try:
                ref["current"] = None
            except Exception:
                pass

    @staticmethod
    def _same_type(old_el: Element, new_el: Element) -> bool:
        if isinstance(old_el.type, str):
            return old_el.type == new_el.type
        return old_el.type is new_el.type

    @staticmethod
    def _diff_props(old: dict, new: dict) -> dict:
        """Return only the props that changed.

        Callables always count as changed (we cannot compare two
        closures cheaply, and event handlers are usually fresh on every
        render). Internal `__*__` props are skipped because they are
        consumed by the reconciler itself, not the native handler.
        Reconciler-owned props (``ref``) are also skipped because they
        are managed via ``_attach_ref`` / ``_detach_ref`` and never
        forwarded to the native handler.
        """
        changed = {}
        for key, new_val in new.items():
            if key.startswith("__") or key in _RECONCILER_OWNED_PROPS:
                continue
            old_val = old.get(key)
            if callable(new_val) or old_val != new_val:
                changed[key] = new_val
        for key in old:
            if key.startswith("__") or key in _RECONCILER_OWNED_PROPS:
                continue
            if key not in new:
                changed[key] = None
        return changed

    # ------------------------------------------------------------------
    # Layout pass
    # ------------------------------------------------------------------

    def _run_layout(self) -> None:
        """Build a layout tree from the committed VNodes and apply frames.

        Wraps the user's root VNode in a synthetic outer
        `LayoutNode` with the viewport size so the user's root
        always fills the screen by default (matching React Native).
        Skipped silently until the screen host has supplied a
        viewport size via
        [`set_viewport_size`][pythonnative.reconciler.Reconciler.set_viewport_size].

        The root native view's *frame* is intentionally NOT touched:
        its position and size are owned by the screen host (iOS
        ``_sync_root_frame`` places it below the top safe-area
        inset; Android attaches it with ``MATCH_PARENT``). Calling
        ``set_frame(root, 0, 0, w, h)`` here would silently reset
        the iOS root's ``y`` from ``insets.top`` back to ``0``,
        causing the root view to overlap the status bar / dynamic
        island after every tab switch.
        """
        if self._tree is None:
            return
        viewport_w, viewport_h = self._viewport_size
        if viewport_w <= 0 or viewport_h <= 0:
            self._log_viewport(f"_run_layout: skipped empty viewport=({viewport_w},{viewport_h})")
            return

        self._layout_pass += 1
        layout_pass = self._layout_pass
        self._log_viewport(
            f"_run_layout: pass#{layout_pass} start viewport=({viewport_w},{viewport_h}) "
            f"root={self._node_debug(self._tree)}"
        )
        layout_root = self._build_layout_tree(self._tree)
        if layout_root is None:
            self._log_viewport(f"_run_layout: pass#{layout_pass} no layout root")
            return

        self._log_viewport(
            f"_run_layout: pass#{layout_pass} layout root built children={len(layout_root.children)} "
            f"style={layout_root.style!r}"
        )
        viewport = LayoutNode(
            style={"width": viewport_w, "height": viewport_h},
            children=[layout_root],
        )
        self._log_viewport(f"_run_layout: pass#{layout_pass} calling calculate_layout")
        calculate_layout(viewport, viewport_w, viewport_h)
        self._log_viewport(
            f"_run_layout: pass#{layout_pass} calculate_layout done "
            f"root_size=({layout_root.width:.1f},{layout_root.height:.1f})"
        )
        # Skip set_frame for the root itself — descendants are
        # positioned relative to the root's local origin, which is
        # what they want regardless of where the host placed the
        # root in the screen.
        for child in layout_root.children:
            self._apply_layout(child, 0.0, 0.0)
        self._log_viewport(f"_run_layout: pass#{layout_pass} done")

    def _build_layout_tree(self, vnode: VNode) -> Optional[LayoutNode]:
        """Walk `vnode` and build a parallel `LayoutNode` tree of native nodes.

        Function components, providers, and error boundaries are
        transparent: they delegate to their (single) child. Native
        nodes contribute a `LayoutNode` whose ``user_data`` points
        back to the VNode so the layout pass can apply frames.

        Leaves whose intrinsic size depends on content (Text, Button,
        Image, TextInput) get a measure callback that delegates to
        the backend's ``measure_intrinsic``. ScrollView wraps its
        single child in a synthetic node that strips the scrollable
        axis bound, allowing the child to grow beyond the viewport.
        """
        element = vnode.element
        if not isinstance(element.type, str):
            return self._build_layout_tree(vnode.children[0]) if vnode.children else None
        if element.type in ("__Provider__", "__ErrorBoundary__"):
            return self._build_layout_tree(vnode.children[0]) if vnode.children else None
        if element.type == "Modal":
            return None  # Off-screen placeholder; not part of the visible flow.

        style = extract_layout_style(element.props)
        layout = LayoutNode(style=style, user_data=vnode)
        self._log_viewport(
            f"_build_layout_tree: node type={element.type!r} view={self._obj_debug(vnode.native_view)} "
            f"style={style!r} children={len(vnode.children)}"
        )

        if not vnode.children:
            measure = self._make_measure_callback(vnode)
            if measure is not None:
                layout.measure = measure
                self._log_viewport(f"_build_layout_tree: attached measure type={element.type!r}")

        for child_vnode in vnode.children:
            child_layout = self._build_layout_tree(child_vnode)
            if child_layout is None:
                continue
            if element.type == "ScrollView":
                # ScrollView's child sees an unbounded main-axis viewport so it
                # can size to its full content (the scrollable region).
                axis = element.props.get("scroll_axis", "vertical")
                if axis == "horizontal":
                    child_layout = self._wrap_scroll_axis(child_layout, axis="x")
                else:
                    child_layout = self._wrap_scroll_axis(child_layout, axis="y")
            layout.children.append(child_layout)

        return layout

    @staticmethod
    def _wrap_scroll_axis(child: LayoutNode, axis: str) -> LayoutNode:
        """Wrap ``child`` so the layout engine treats one axis as unbounded.

        Used by ScrollView to let its content grow beyond the viewport
        on the scroll axis. The wrapper is a transparent layout node
        whose ``user_data`` is the child VNode (so frames still apply
        correctly to the underlying native view).
        """
        wrapper_style = {"flex_direction": "column"} if axis == "y" else {"flex_direction": "row"}
        wrapper = LayoutNode(style=wrapper_style, user_data=None)
        wrapper.children.append(child)
        return wrapper

    _INTRINSIC_TYPES = frozenset(
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
        }
    )

    def _make_measure_callback(self, vnode: VNode) -> Optional[Any]:
        """Return a measure callback for ``vnode`` if it has an intrinsic size."""
        type_name = vnode.element.type
        if type_name not in self._INTRINSIC_TYPES:
            return None
        backend = self.backend
        view = vnode.native_view
        if view is None:
            return None
        node_label = self._node_debug(vnode)

        def measure(max_w: float, max_h: float) -> Tuple[float, float]:
            try:
                self._log_viewport(
                    "measure: before backend.measure_intrinsic " f"{node_label} max=({max_w!r},{max_h!r})"
                )
                w, h = backend.measure_intrinsic(view, type_name, max_w, max_h)
                result = (float(w), float(h))
                self._log_viewport(f"measure: after backend.measure_intrinsic type={type_name!r} result={result!r}")
                return result
            except Exception as e:
                self._log_viewport(
                    "measure: backend.measure_intrinsic raised "
                    f"type={type_name!r} {type(e).__name__}: {e!r}; fallback=(0,0)"
                )
                return (0.0, 0.0)

        return measure

    def _apply_layout(self, layout_node: LayoutNode, parent_x: float = 0.0, parent_y: float = 0.0) -> None:
        """Walk a positioned layout tree and call ``set_frame`` for each native view.

        Coordinates accumulate through transparent wrapper nodes
        (e.g., the ScrollView axis wrapper) so the underlying native
        view receives its position relative to its true native parent.
        """
        vnode = layout_node.user_data
        if vnode is not None and vnode.native_view is not None:
            try:
                self._log_viewport(
                    "apply_layout: before set_frame "
                    f"{self._node_debug(vnode)} frame=("
                    f"{layout_node.x + parent_x:.1f},{layout_node.y + parent_y:.1f},"
                    f"{layout_node.width:.1f},{layout_node.height:.1f})"
                )
                self.backend.set_frame(
                    vnode.native_view,
                    vnode.element.type,
                    layout_node.x + parent_x,
                    layout_node.y + parent_y,
                    layout_node.width,
                    layout_node.height,
                )
                self._log_viewport(f"apply_layout: after set_frame type={vnode.element.type!r}")
            except Exception as e:
                self._log_viewport(
                    "apply_layout: set_frame raised " f"type={vnode.element.type!r} {type(e).__name__}: {e!r}"
                )
                pass
            child_offset_x = 0.0
            child_offset_y = 0.0
        else:
            child_offset_x = layout_node.x + parent_x
            child_offset_y = layout_node.y + parent_y

        for child in layout_node.children:
            self._apply_layout(child, child_offset_x, child_offset_y)

    # ------------------------------------------------------------------
    # Test / debug accessor
    # ------------------------------------------------------------------

    def compute_layout_for_test(self, viewport_width: float, viewport_height: float) -> Optional[LayoutNode]:
        """Build and compute a layout tree without touching the backend.

        Test helper that returns the synthetic viewport `LayoutNode`
        with all descendants positioned. Returns ``None`` if no tree
        has been mounted yet.
        """
        if self._tree is None:
            return None
        layout_root = self._build_layout_tree(self._tree)
        if layout_root is None:
            return None
        viewport = LayoutNode(
            style={"width": viewport_width, "height": viewport_height},
            children=[layout_root],
        )
        calculate_layout(viewport, viewport_width, viewport_height)
        return viewport
