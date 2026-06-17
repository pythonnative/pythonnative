"""Virtual-tree reconciler with a batched, tag-based commit protocol.

Maintains a tree of [`VNode`][pythonnative.reconciler.VNode] objects
(each owning an integer **tag** that identifies its native view) and
diffs incoming [`Element`][pythonnative.Element] trees to compute the
minimal set of native mutations.

The diff phase is *pure*: it never touches the native layer. Each pass
appends ops (`pythonnative.mutations`) to a transaction list, and the
commit applies them through a single
``backend.apply_mutations(ops)`` call. Event callbacks never cross into
the native layer at all; they live in the Python-side
[`EventRegistry`][pythonnative.events.EventRegistry], keyed by tag, so
re-renders that only produce fresh closures cost nothing natively.

Supports:

- **Native elements** (`type` is a string like `"Text"`).
- **Function components** (`type` is a callable decorated with
  [`component`][pythonnative.component]). Their hook state is preserved
  across renders.
- **Provider elements** (`type == "__Provider__"`), which push and pop
  context values during tree traversal.
- **Error boundary elements** (`type == "__ErrorBoundary__"`), which
  catch exceptions in child subtrees and render a fallback.
- **Key-based child reconciliation** with indexed, move-aware inserts
  (keyed reorders emit one move per child instead of detach-all /
  re-attach-all).
- **Post-render effect flushing**. After each commit, all queued
  effects are executed so they see the committed native tree.
- **Incremental layout**: a parallel
  [`LayoutNode`][pythonnative.layout.LayoutNode] tree is cached across
  passes; clean subtrees keep their cached nodes (enabling the layout
  engine's measurement memo) and only frames that actually changed are
  sent to the native side.
"""

import itertools
import os
from typing import Any, Dict, List, Optional, Tuple

from .element import Element
from .events import extract_events, get_event_registry
from .layout import LayoutNode, calculate_layout, extract_layout_style
from .mutations import CreateOp, DestroyOp, InsertOp, Mutation, SetFrameOp, UpdateOp

# Props the reconciler consumes itself (i.e., never forwards to the
# native handler). ``ref`` is one such prop: components pass a dict
# from ``use_ref()`` and the reconciler populates ``ref["current"]``
# with the underlying native view (and ``ref["_pn_tag"]`` with the
# view's tag), mirroring React's ``ref`` semantics.
_RECONCILER_OWNED_PROPS = frozenset({"ref"})

# Tags are globally unique so multiple reconcilers (screens, list rows)
# can share one registry without collisions.
_tag_counter = itertools.count(1)


def next_tag() -> int:
    """Allocate a fresh, process-unique view tag."""
    return next(_tag_counter)


def _shallow_equal_props(old: dict, new: dict) -> bool:
    """Return whether two prop dicts are equal under shallow comparison.

    Used by [`memo`][pythonnative.memo] to skip re-rendering when none
    of a component's props changed identity. Callables only count as
    equal if they're the *same object*; fresh closures always invalidate
    the memo (matching React's behavior; pair with
    [`use_callback`][pythonnative.use_callback] when stability matters).
    """
    if old is new:
        return True
    if set(old.keys()) != set(new.keys()):
        return False
    for key, ov in old.items():
        nv = new[key]
        if ov is nv:
            continue
        if callable(ov) or callable(nv):
            return False
        try:
            if ov != nv:
                return False
        except Exception:
            return False
    return True


def _flatten_children(children: List[Element]) -> List[Element]:
    """Expand [`Fragment`][pythonnative.Fragment] elements inline.

    The reconciler treats Fragments as transparent: when one appears in
    a child list, its own children become direct siblings of the
    Fragment's location in the parent's child list. This keeps the
    Fragment element out of the native tree entirely.

    Args:
        children: An ordered child list possibly containing Fragments.

    Returns:
        A new list with every Fragment recursively expanded in place.
    """
    if not children:
        return list(children)
    out: List[Element] = []
    for el in children:
        if isinstance(el.type, str) and el.type == "__Fragment__":
            out.extend(_flatten_children(el.children))
        else:
            out.append(el)
    return out


class VNode:
    """A mounted [`Element`][pythonnative.Element] plus its native identity.

    The reconciler walks parallel trees of `VNode` and incoming
    `Element` to compute the minimal set of native mutations.

    Attributes:
        element: The `Element` last rendered into this slot.
        tag: Integer identity of the underlying native view. Native
            elements own a fresh tag; transparent wrappers (function
            components, providers, error boundaries) delegate the tag
            of their rendered subtree root. ``None`` before the subtree
            renders anything.
        native_view: The platform-native view object, resolved from the
            registry after commit. May be `None` for purely virtual
            wrappers that rendered nothing.
        children: Ordered list of child `VNode` instances.
        parent: The owning `VNode`, or `None` for the tree root. Used
            by local (component-scoped) re-renders to bubble a changed
            subtree root up to the nearest native container.
        hook_state: The component's
            [`HookState`][pythonnative.hooks.HookState] when the node
            wraps a function component, otherwise `None`.
        mounted: `False` once the node has been destroyed, so stale
            entries in the reconciler's dirty set are skipped.
    """

    __slots__ = (
        "element",
        "tag",
        "native_view",
        "children",
        "parent",
        "hook_state",
        "mounted",
        "_rendered",
        "_clean_props",
        "_measure_cache",
        "_last_frame",
        "_layout_node",
        "_layout_dirty",
    )

    def __init__(self, element: Element, children: List["VNode"], tag: Optional[int] = None) -> None:
        self.element = element
        self.tag = tag
        self.native_view: Any = None
        self.children = children
        self.parent: Optional["VNode"] = None
        self.hook_state: Any = None
        self.mounted: bool = True
        self._rendered: Optional[Element] = None
        # Native-safe props (callables stripped) from the last commit;
        # the baseline for prop diffing.
        self._clean_props: Dict[str, Any] = {}
        # Cache for the leaf intrinsic-size measure callback:
        # ``(max_w, max_h, width, height)``. Invalidated whenever the
        # node's props change, so unchanged leaves skip native
        # ``measure_intrinsic`` calls entirely.
        self._measure_cache: Optional[Tuple[float, float, float, float]] = None
        # Last frame sent to the native side; frames that don't change
        # are skipped (frame diffing).
        self._last_frame: Optional[Tuple[float, float, float, float]] = None
        # Cached LayoutNode reused across passes while the subtree is
        # clean (see Reconciler._build_layout_tree_cached).
        self._layout_node: Optional[LayoutNode] = None
        # True when this node's layout-relevant props or child list
        # changed since the last layout pass.
        self._layout_dirty: bool = True


class Reconciler:
    """Create, diff, and patch native view trees from `Element` descriptors.

    After each [`mount`][pythonnative.reconciler.Reconciler.mount],
    [`reconcile`][pythonnative.reconciler.Reconciler.reconcile], or
    [`flush_dirty`][pythonnative.reconciler.Reconciler.flush_dirty]
    pass the reconciler:

    1. applies the accumulated mutation ops in one batch,
    2. resolves freshly created native views and populates refs,
    3. flushes pending effects (so they see the committed tree), and
    4. runs the layout pass, emitting only changed frames.

    Args:
        backend: An object implementing the registry protocol
            (``apply_mutations``, ``resolve_view``,
            ``measure_intrinsic``, ``command``). PythonNative ships
            Android, iOS, and desktop registries; tests can pass a
            registry stocked with mock handlers.
    """

    def __init__(self, backend: Any) -> None:
        self.backend = backend
        self._tree: Optional[VNode] = None
        self._screen_re_render: Optional[Any] = None
        self._viewport_size: Tuple[float, float] = (0.0, 0.0)
        self._layout_pass = 0
        self._events = get_event_registry()
        # Transaction state for the in-flight pass.
        self._ops: List[Mutation] = []
        self._created: List[VNode] = []
        # Function-component VNodes whose own state changed since the
        # last flush, keyed by ``id`` to dedupe while keeping a strong
        # reference. Drained by
        # [`flush_dirty`][pythonnative.reconciler.Reconciler.flush_dirty].
        self._dirty_nodes: Dict[int, VNode] = {}

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
        self._log(f"mount: start type={self._type_label(element.type)!r}")
        self._dirty_nodes.clear()
        self._tree = self._create_tree(element)
        self._commit()
        return self._tree.native_view

    def reconcile(self, new_element: Element) -> Any:
        """Diff `new_element` against the current tree and patch native views.

        Args:
            new_element: The desired root element after a state change.

        Returns:
            The (possibly replaced) root native view.
        """
        # A full reconcile rebuilds the whole tree from the root, so any
        # pending per-component dirty marks are now obsolete.
        self._dirty_nodes.clear()
        if self._tree is None:
            self._tree = self._create_tree(new_element)
        else:
            self._tree = self._reconcile_node(self._tree, new_element)
        self._commit()
        return self._tree.native_view

    def root_view(self) -> Any:
        """Return the current root native view, or ``None`` before mount."""
        return self._tree.native_view if self._tree is not None else None

    def root_tag(self) -> Optional[int]:
        """Return the root native view's tag, or ``None`` before mount."""
        return self._tree.tag if self._tree is not None else None

    def unmount(self) -> None:
        """Destroy the entire mounted tree and release native views."""
        if self._tree is None:
            return
        self._destroy_tree(self._tree)
        self._tree = None
        self._dirty_nodes.clear()
        self._flush_ops()

    def dispatch_command(self, tag: Optional[int], name: str, args: Optional[Dict[str, Any]] = None) -> Any:
        """Run an imperative command against the view registered under ``tag``."""
        if tag is None:
            return None
        return self.backend.command(tag, name, args or {})

    def mark_dirty(self, vnode: "VNode") -> None:
        """Queue ``vnode`` (a function component) for a local re-render.

        Called by a component's ``use_state`` / ``use_reducer`` setter
        when its own state changes. The node is re-rendered on the next
        [`flush_dirty`][pythonnative.reconciler.Reconciler.flush_dirty]
        pass, which the screen host schedules. Marking is idempotent and
        cheap; the actual render is deferred so several setters (e.g.
        inside [`batch_updates`][pythonnative.batch_updates]) coalesce
        into a single pass.
        """
        if vnode is None or vnode.hook_state is None or not vnode.mounted:
            return
        self._dirty_nodes[id(vnode)] = vnode

    def flush_dirty(self) -> Any:
        """Re-render only the component subtrees marked dirty since the last pass.

        This is the hot path for state-driven updates: instead of
        re-running the whole app from the root, each dirty function
        component re-runs its own body (reusing its
        [`HookState`][pythonnative.hooks.HookState]) and reconciles just
        its subtree. Nodes are processed shallowest-first so that when a
        dirty ancestor's re-render already covers a dirty descendant, the
        descendant is skipped (its ``_dirty`` flag is cleared by the
        ancestor pass). The whole batch commits as one native
        transaction.

        Returns:
            The (possibly replaced) root native view, so the host can
            re-attach it if the root changed.
        """
        if self._tree is None:
            return None
        if not self._dirty_nodes:
            return self._tree.native_view

        pending = list(self._dirty_nodes.values())
        self._dirty_nodes.clear()
        pending.sort(key=self._node_depth)
        for vnode in pending:
            if not vnode.mounted:
                continue
            hook_state = vnode.hook_state
            if hook_state is None or not hook_state._dirty:
                # Already re-rendered as part of a dirty ancestor's pass.
                continue
            try:
                self._update_component(vnode)
            except Exception as exc:
                # A local re-render starts below any enclosing
                # ``ErrorBoundary``, so route the failure to the nearest
                # boundary ancestor (re-rendering its subtree through the
                # boundary, which mounts the fallback). With no boundary
                # the exception propagates, matching a full render.
                self._handle_local_render_error(vnode, exc)

        self._commit()
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
            return
        if self._viewport_size == (width, height):
            return
        self._viewport_size = (width, height)
        if self._tree is not None:
            self._run_layout()
            self._flush_ops()

    # ------------------------------------------------------------------
    # Commit driver
    # ------------------------------------------------------------------

    def _commit(self) -> None:
        """Apply the accumulated transaction and run the post-commit phases."""
        self._flush_ops()
        self._flush_effects()
        self._run_layout()
        self._flush_ops()

    def _flush_ops(self) -> None:
        """Send pending ops to the backend and resolve created views."""
        ops = self._ops
        created = self._created
        if ops:
            self._ops = []
            self._created = []
            self.backend.apply_mutations(ops)
        elif created:
            self._created = []
        for vnode in created:
            if not vnode.mounted or vnode.tag is None:
                continue
            vnode.native_view = self.backend.resolve_view(vnode.tag)
            self._attach_ref(vnode.element, vnode.native_view, vnode.tag)

    # ------------------------------------------------------------------
    # Effect flushing
    # ------------------------------------------------------------------

    def _flush_effects(self) -> None:
        """Walk the committed tree and flush pending effects (depth-first).

        This post-commit walk doubles as the single source of truth for
        ``VNode.parent`` links and for *delegated* identity: transparent
        wrappers (components, providers, boundaries) re-derive their
        ``tag`` / ``native_view`` from their subtree root here, so the
        rest of the reconciler never has to chase delegation chains by
        hand. The cost is folded into a walk the reconciler already runs
        after every commit.
        """
        if self._tree is not None:
            self._tree.parent = None
            self._flush_tree_effects(self._tree)

    def _flush_tree_effects(self, node: VNode) -> None:
        for child in node.children:
            child.parent = node
            self._flush_tree_effects(child)
        if not self._is_native_node(node):
            if node.children:
                node.tag = node.children[0].tag
                node.native_view = node.children[0].native_view
            else:
                node.tag = None
                node.native_view = None
        if node.hook_state is not None:
            node.hook_state.flush_pending_effects()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _node_depth(vnode: "VNode") -> int:
        depth = 0
        node = vnode.parent
        while node is not None:
            depth += 1
            node = node.parent
        return depth

    def _update_component(self, vnode: "VNode") -> None:
        """Re-run one function component's body and reconcile its subtree in place.

        Unlike a full reconcile from the root, a local update starts in
        the *middle* of the tree, so the context stack of every
        ``__Provider__`` ancestor must be re-established before the body
        runs (otherwise [`use_context`][pythonnative.use_context], and
        therefore [`use_navigation`][pythonnative.use_navigation], would
        read the context default instead of the provided value). Nested
        providers *inside* this subtree are pushed/popped normally by the
        recursive reconcile beneath us.
        """
        from .hooks import _set_hook_state

        new_el = vnode.element
        if not callable(new_el.type):
            return
        hook_state = vnode.hook_state
        if hook_state is None:
            return

        providers = self._ancestor_providers(vnode)
        for context, value in providers:
            context._stack.append(value)
        try:
            hook_state.reset_index()
            hook_state._trigger_render = self._screen_re_render
            hook_state._vnode = vnode
            hook_state._reconciler = self
            _set_hook_state(hook_state)
            try:
                rendered = new_el.type(**new_el.props)
            finally:
                _set_hook_state(None)
                hook_state._dirty = False

            old_tag = vnode.tag
            if vnode.children:
                child = self._reconcile_node(vnode.children[0], rendered)
            else:
                child = self._create_tree(rendered)
        finally:
            for context, _value in reversed(providers):
                context._stack.pop()

        child.parent = vnode
        vnode.children = [child]
        vnode.tag = child.tag
        vnode.native_view = child.native_view
        vnode._rendered = rendered

        if child.tag != old_tag:
            self._bubble_root_change(vnode, child)

    def _handle_local_render_error(self, vnode: "VNode", exc: Exception) -> None:
        """Route a local re-render failure to the nearest ``ErrorBoundary`` ancestor.

        Re-reconciles the boundary against its own element so the throw
        is re-triggered *inside*
        [`_reconcile_error_boundary`][pythonnative.reconciler.Reconciler._reconcile_error_boundary],
        which destroys the failed subtree and mounts the boundary's
        fallback. If no boundary encloses ``vnode`` the exception
        propagates, exactly as it would during a full render.
        """
        node = vnode.parent
        while node is not None:
            if isinstance(node.element.type, str) and node.element.type == "__ErrorBoundary__":
                old_tag = node.tag
                # Like a local component update, this re-reconcile starts
                # mid-tree, so restore the boundary's own ancestor
                # provider context first.
                providers = self._ancestor_providers(node)
                for context, value in providers:
                    context._stack.append(value)
                try:
                    self._reconcile_node(node, node.element)
                finally:
                    for context, _value in reversed(providers):
                        context._stack.pop()
                if node.tag != old_tag and node.children:
                    self._bubble_root_change(node, node.children[0])
                return
            node = node.parent
        raise exc

    @staticmethod
    def _ancestor_providers(vnode: "VNode") -> List[Tuple[Any, Any]]:
        """Collect ``(context, value)`` for every ``__Provider__`` above ``vnode``.

        Returned outermost-first so that pushing them in order leaves the
        nearest provider on top of each context's stack (nearest wins,
        matching React).
        """
        chain: List[Tuple[Any, Any]] = []
        node = vnode.parent
        while node is not None:
            el = node.element
            if isinstance(el.type, str) and el.type == "__Provider__":
                chain.append((el.props["__context__"], el.props["__value__"]))
            node = node.parent
        chain.reverse()
        return chain

    def _bubble_root_change(self, vnode: "VNode", new_subtree_root: "VNode") -> None:
        """Propagate a swapped subtree-root view up to its native parent.

        A local re-render starts below the real native container, so when
        the dirty component's root native view is replaced (e.g. its
        output changed type), the change must be reflected in (a) every
        transparent ancestor that delegated its identity to this subtree
        and (b) the nearest native-container ancestor's child list. The
        old view's detach is implied by its `DestroyOp` (handlers detach
        on destroy); only the indexed insert of the new root is emitted.
        """
        child = vnode
        node = vnode.parent
        while node is not None:
            if self._is_native_node(node):
                try:
                    idx = node.children.index(child)
                except ValueError:
                    idx = len(node.children) - 1
                if node.tag is not None and new_subtree_root.tag is not None:
                    self._ops.append(InsertOp(node.tag, new_subtree_root.tag, idx))
                self._mark_layout_dirty(node)
                return
            # Transparent ancestor delegates its identity to this subtree.
            node.tag = new_subtree_root.tag
            node.native_view = new_subtree_root.native_view
            child = node
            node = node.parent
        # Reached the root with no native container above: the root's
        # identity was already updated in the loop. The host detects the
        # change by comparing ``root_view()`` after the flush.

    @staticmethod
    def _is_native_node(node: "VNode") -> bool:
        t = node.element.type
        return isinstance(t, str) and t not in ("__Provider__", "__ErrorBoundary__", "__Fragment__")

    @staticmethod
    def _log(msg: str) -> None:
        """Emit optional diagnostics for local debugging."""
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

    # ------------------------------------------------------------------
    # Tree creation
    # ------------------------------------------------------------------

    def _create_tree(self, element: Element) -> VNode:
        # Provider: push context, create children, pop context
        if element.type == "__Provider__":
            context = element.props["__context__"]
            context._stack.append(element.props["__value__"])
            try:
                provider_children = _flatten_children(element.children)
                child_node = self._create_tree(provider_children[0]) if provider_children else None
            finally:
                context._stack.pop()
            children = [child_node] if child_node else []
            vnode = VNode(element, children)
            vnode.tag = child_node.tag if child_node else None
            return vnode

        # Error boundary: catch exceptions in the child subtree
        if element.type == "__ErrorBoundary__":
            return self._create_error_boundary(element)

        # Fragment elements should never reach here directly (the parent
        # flattens them out of its child list). If we somehow get one as
        # a root element, mount its first child.
        if element.type == "__Fragment__":
            kids = _flatten_children(element.children)
            if not kids:
                return VNode(element, [])
            child_node = self._create_tree(kids[0])
            vnode = VNode(element, [child_node])
            vnode.tag = child_node.tag
            return vnode

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
                hook_state._dirty = False

            child_node = self._create_tree(rendered)
            vnode = VNode(element, [child_node])
            vnode.tag = child_node.tag
            vnode.hook_state = hook_state
            vnode._rendered = rendered
            hook_state._vnode = vnode
            hook_state._reconciler = self
            return vnode

        # Native element
        tag = next_tag()
        clean_props, events = self._split_props(element.props)
        vnode = VNode(element, [], tag=tag)
        vnode._clean_props = clean_props
        if events:
            self._events.set_events(tag, events)
        self._ops.append(CreateOp(tag, element.type, clean_props))
        self._created.append(vnode)

        flat_children = _flatten_children(element.children)
        for i, child_el in enumerate(flat_children):
            child_node = self._create_tree(child_el)
            if child_node.tag is not None:
                self._ops.append(InsertOp(tag, child_node.tag, i))
            vnode.children.append(child_node)
        return vnode

    def _create_error_boundary(self, element: Element) -> VNode:
        fallback_fn = element.props.get("__fallback__")
        eb_children = _flatten_children(element.children)
        try:
            child_node = self._create_tree(eb_children[0]) if eb_children else None
        except Exception as exc:
            if fallback_fn is not None:
                fallback_el = fallback_fn(exc) if callable(fallback_fn) else fallback_fn
                child_node = self._create_tree(fallback_el)
            else:
                raise
        children = [child_node] if child_node else []
        vnode = VNode(element, children)
        vnode.tag = child_node.tag if child_node else None
        return vnode

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------

    def _reconcile_node(self, old: VNode, new_el: Element) -> VNode:
        if not self._same_type(old.element, new_el):
            new_node = self._create_tree(new_el)
            self._destroy_tree(old)
            return new_node

        # Provider
        if new_el.type == "__Provider__":
            context = new_el.props["__context__"]
            context._stack.append(new_el.props["__value__"])
            try:
                provider_kids = _flatten_children(new_el.children)
                if old.children and provider_kids:
                    child = self._reconcile_node(old.children[0], provider_kids[0])
                    old.children = [child]
                    old.tag = child.tag
                    old.native_view = child.native_view
                elif provider_kids:
                    child = self._create_tree(provider_kids[0])
                    old.children = [child]
                    old.tag = child.tag
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

            # ``@memo`` skip: if the props haven't changed shallowly and
            # the component's own hook state is clean (no setter fired
            # while we were rebuilding the parent tree), reuse the
            # previously-rendered subtree without invoking the body.
            if self._can_skip_memoized(old, new_el):
                old.element = new_el
                return old

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
                hook_state._dirty = False

            if old.children:
                child = self._reconcile_node(old.children[0], rendered)
            else:
                child = self._create_tree(rendered)
            old.children = [child]
            old.tag = child.tag
            old.native_view = child.native_view
            old.element = new_el
            old.hook_state = hook_state
            old._rendered = rendered
            hook_state._vnode = old
            hook_state._reconciler = self
            return old

        # Native element
        new_clean, events = self._split_props(new_el.props)
        if old.tag is not None:
            self._events.set_events(old.tag, events)
        changed = self._diff_props(old._clean_props, new_clean)
        if changed:
            if old.tag is not None:
                self._ops.append(UpdateOp(old.tag, changed))
            old._measure_cache = None
            if self._affects_layout(old.element.type, changed):
                self._mark_layout_dirty(old)
        old._clean_props = new_clean

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
            self._attach_ref(new_el, old.native_view, old.tag)

        self._reconcile_children(old, new_el.children)
        old.element = new_el
        return old

    def _reconcile_error_boundary(self, old: VNode, new_el: Element) -> VNode:
        fallback_fn = new_el.props.get("__fallback__")
        eb_kids = _flatten_children(new_el.children)
        try:
            if old.children and eb_kids:
                child = self._reconcile_node(old.children[0], eb_kids[0])
                old.children = [child]
                old.tag = child.tag
                old.native_view = child.native_view
            elif eb_kids:
                child = self._create_tree(eb_kids[0])
                old.children = [child]
                old.tag = child.tag
                old.native_view = child.native_view
        except Exception as exc:
            for c in old.children:
                self._destroy_tree(c)
            if fallback_fn is not None:
                fallback_el = fallback_fn(exc) if callable(fallback_fn) else fallback_fn
                child = self._create_tree(fallback_el)
                old.children = [child]
                old.tag = child.tag
                old.native_view = child.native_view
            else:
                raise
        old.element = new_el
        return old

    @staticmethod
    def _can_skip_memoized(old: VNode, new_el: Element) -> bool:
        """Return whether a memo'd function component can skip its body.

        A component is skippable iff:

        1. Its type has the ``_pn_memo`` marker set by
           [`memo`][pythonnative.memo].
        2. It has been rendered before (``old._rendered`` is populated).
        3. None of its internal state setters fired since the last
           render (``hook_state._dirty`` is ``False``).
        4. The new props are shallowly equal to the old props.
        """
        fn = new_el.type
        if not getattr(fn, "_pn_memo", False):
            return False
        if old._rendered is None:
            return False
        hook_state = old.hook_state
        if hook_state is None:
            return False
        if hook_state._dirty:
            return False
        return _shallow_equal_props(old.element.props, new_el.props)

    def _reconcile_children(self, parent: VNode, new_children: List[Element]) -> None:
        new_children = _flatten_children(new_children)
        old_children = parent.children
        is_native = self._is_native_node(parent)
        parent_tag = parent.tag if is_native else None

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
        # ``(index, vnode)`` pairs that need an indexed insert once the
        # stale children have been removed (see op-ordering note below).
        pending_inserts: List[Tuple[int, VNode]] = []
        structure_changed = False

        for i, new_el in enumerate(new_children):
            matched: Optional[VNode] = None

            if new_el.key is not None and new_el.key in old_by_key:
                matched = old_by_key[new_el.key]
                used_keyed.add(new_el.key)
            elif new_el.key is None:
                matched = next(unkeyed_iter, None)

            if matched is None:
                node = self._create_tree(new_el)
                pending_inserts.append((i, node))
                structure_changed = True
                new_child_nodes.append(node)
            elif not self._same_type(matched.element, new_el):
                node = self._create_tree(new_el)
                self._destroy_tree(matched)
                pending_inserts.append((i, node))
                structure_changed = True
                new_child_nodes.append(node)
            else:
                old_tag = matched.tag
                updated = self._reconcile_node(matched, new_el)
                if updated.tag != old_tag:
                    # The child's subtree root was replaced in place
                    # (transparent wrapper whose output changed type).
                    pending_inserts.append((i, updated))
                    structure_changed = True
                new_child_nodes.append(updated)

        # Destroy unused old nodes first: handlers detach on destroy, so
        # the native child list contains only kept children (in their old
        # relative order) by the time the indexed inserts apply.
        for key, node in old_by_key.items():
            if key not in used_keyed:
                self._destroy_tree(node)
                structure_changed = True
        for node in unkeyed_iter:
            self._destroy_tree(node)
            structure_changed = True

        if is_native and parent_tag is not None:
            for index, node in pending_inserts:
                if node.tag is not None:
                    self._ops.append(InsertOp(parent_tag, node.tag, index))

            # Keyed reorder: when the kept children changed relative
            # order, emit one move-aware insert per child in final
            # order. Applying "ensure child at index i" sequentially for
            # i = 0..n-1 converges to the target order, and handlers
            # no-op when the child is already in place.
            if used_keyed:
                old_key_order = [c.element.key for c in old_children if c.element.key in used_keyed]
                new_key_order = [n.element.key for n in new_child_nodes if n.element.key in used_keyed]
                if old_key_order != new_key_order:
                    structure_changed = True
                    for i, node in enumerate(new_child_nodes):
                        if node.tag is not None:
                            self._ops.append(InsertOp(parent_tag, node.tag, i))

        if structure_changed:
            self._mark_layout_dirty(parent)

        parent.children = new_child_nodes

    def _destroy_tree(self, node: VNode) -> None:
        node.mounted = False
        # Drop the node from the pending-render set so a setter that
        # fired moments before unmount can't resurrect a dead subtree.
        self._dirty_nodes.pop(id(node), None)
        if node.hook_state is not None:
            node.hook_state.cleanup_all_effects()
            # Break the back-references so the unmounted component's hook
            # state (and the closures it captured) can be freed by plain
            # refcounting, important on iOS, where the cyclic GC is
            # disabled.
            node.hook_state._vnode = None
            node.hook_state._reconciler = None
            node.hook_state._trigger_render = None
        if node.element is not None:
            self._detach_ref(node.element)
        for child in node.children:
            self._destroy_tree(child)
        if self._is_native_node(node) and node.tag is not None:
            self._events.clear(node.tag)
            self._ops.append(DestroyOp(node.tag))
        node.children = []
        node.parent = None
        node._layout_node = None

    # ------------------------------------------------------------------
    # Prop handling
    # ------------------------------------------------------------------

    def _split_props(self, props: dict) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Strip reconciler-owned keys, then split events from native props.

        Reconciler-owned keys (``ref``, internal ``__*__`` keys) are
        consumed by the reconciler itself and must never reach the
        native handler. Event callables are routed to the
        [`EventRegistry`][pythonnative.events.EventRegistry] and the
        remaining payload is safe to diff with plain ``==``.
        """
        if not props:
            return {}, {}
        stripped = {}
        for key, value in props.items():
            if key in _RECONCILER_OWNED_PROPS or key.startswith("__"):
                continue
            stripped[key] = value
        return extract_events(stripped)

    @staticmethod
    def _diff_props(old: dict, new: dict) -> dict:
        """Return only the props that changed between two clean prop dicts.

        Event callables never appear here (they live in the event
        registry), so listener identity churn produces no native
        traffic; only the ``_pn_events`` name set is compared.
        """
        changed = {}
        for key, new_val in new.items():
            old_val = old.get(key)
            if key not in old:
                changed[key] = new_val
                continue
            try:
                if callable(new_val) or callable(old_val):
                    if old_val is not new_val:
                        changed[key] = new_val
                elif old_val != new_val:
                    changed[key] = new_val
            except Exception:
                changed[key] = new_val
        for key in old:
            if key not in new:
                changed[key] = None
        return changed

    @staticmethod
    def _attach_ref(element: Element, native_view: Any, tag: Optional[int]) -> None:
        """Populate ``ref["current"]`` (and the internal tag) if a ``ref`` prop exists."""
        ref = element.props.get("ref") if element.props else None
        if isinstance(ref, dict):
            ref["current"] = native_view
            ref["_pn_tag"] = tag

    @staticmethod
    def _detach_ref(element: Element) -> None:
        """Clear ``ref["current"]`` so consumers don't hold a stale handle."""
        ref = element.props.get("ref") if element.props else None
        if isinstance(ref, dict):
            try:
                ref["current"] = None
                ref["_pn_tag"] = None
            except Exception:
                pass

    @staticmethod
    def _same_type(old_el: Element, new_el: Element) -> bool:
        if isinstance(old_el.type, str):
            return old_el.type == new_el.type
        return old_el.type is new_el.type

    # ------------------------------------------------------------------
    # Layout pass
    # ------------------------------------------------------------------

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
            "Picker",
            "Checkbox",
            "SegmentedControl",
            "DatePicker",
        }
    )

    @classmethod
    def _affects_layout(cls, type_name: str, changed: Dict[str, Any]) -> bool:
        """Whether ``changed`` props can alter the node's layout.

        Content-sized leaves re-measure on *any* prop change (text,
        font, image source: almost everything affects their intrinsic
        size). Containers only care about the layout style keys.
        """
        if type_name in cls._INTRINSIC_TYPES:
            return True
        from .layout import LAYOUT_STYLE_KEYS

        return any(key in LAYOUT_STYLE_KEYS for key in changed)

    @staticmethod
    def _mark_layout_dirty(vnode: VNode) -> None:
        vnode._layout_dirty = True
        vnode._layout_node = None

    def _run_layout(self) -> None:
        """Build/refresh the layout tree, compute frames, and emit changed ones.

        Wraps the user's root VNode in a synthetic outer `LayoutNode`
        with the viewport size so the user's root always fills the
        screen by default (matching React Native). Skipped silently
        until the screen host has supplied a viewport size via
        [`set_viewport_size`][pythonnative.reconciler.Reconciler.set_viewport_size].

        Subtrees whose props and children are unchanged since the last
        pass keep their cached `LayoutNode` objects, which lets the
        layout engine reuse memoized measurements instead of re-running
        flex math (see ``pythonnative.layout``). Only frames that
        differ from the previously applied frame produce `SetFrameOp`s.

        The root native view's *frame* is intentionally NOT touched:
        its position and size are owned by the screen host (iOS
        ``_sync_root_frame`` places it below the top safe-area
        inset; Android attaches it with ``MATCH_PARENT``). Framing
        the root here would silently reset the iOS root's ``y`` from
        ``insets.top`` back to ``0``, causing the root view to overlap
        the status bar / dynamic island after every tab switch.
        """
        if self._tree is None:
            return
        viewport_w, viewport_h = self._viewport_size
        if viewport_w <= 0 or viewport_h <= 0:
            return

        self._layout_pass += 1
        layout_root = self._build_layout_tree_cached(self._tree)
        if layout_root is None:
            return

        viewport = LayoutNode(
            style={"width": viewport_w, "height": viewport_h},
            children=[layout_root],
        )
        viewport.dirty = True
        calculate_layout(viewport, viewport_w, viewport_h)
        # Skip set_frame for the root itself; descendants are
        # positioned relative to the root's local origin, which is
        # what they want regardless of where the host placed the
        # root in the screen.
        for child in layout_root.children:
            self._collect_frames(child, 0.0, 0.0)
        # Lay out the children of every visible ``Modal`` as a fresh
        # subtree sized to the viewport. Modals are excluded from the
        # main layout tree (their content lives in a separately
        # presented native container) so without this pass the
        # children's frames never get computed and the modal renders
        # blank.
        self._layout_visible_modals(self._tree, viewport_w, viewport_h)
        self._clear_layout_dirty(self._tree)

    def _layout_visible_modals(
        self,
        vnode: VNode,
        viewport_w: float,
        viewport_h: float,
    ) -> None:
        element = vnode.element
        if isinstance(element.type, str) and element.type == "Modal":
            if element.props.get("visible") and vnode.children:
                child_layout = self._build_layout_tree(vnode.children[0])
                if child_layout is not None:
                    viewport = LayoutNode(
                        style={"width": viewport_w, "height": viewport_h},
                        children=[child_layout],
                    )
                    calculate_layout(viewport, viewport_w, viewport_h)
                    for c in viewport.children:
                        self._collect_frames(c, 0.0, 0.0)
            return
        for child in vnode.children:
            self._layout_visible_modals(child, viewport_w, viewport_h)

    def _build_layout_tree_cached(self, vnode: VNode) -> Optional[LayoutNode]:
        """Like `_build_layout_tree` but reuses cached subtrees when clean.

        A VNode's cached `LayoutNode` is reused when the node itself is
        layout-clean and every child produced its cached node too (i.e.
        the whole subtree is untouched). Reused nodes keep
        ``dirty=False`` so the layout engine can serve their sizes from
        its measurement memo; rebuilt nodes are flagged dirty, which
        forces fresh flex math along the changed path.
        """
        element = vnode.element
        if not isinstance(element.type, str) or element.type in (
            "__Provider__",
            "__ErrorBoundary__",
            "__Fragment__",
        ):
            return self._build_layout_tree_cached(vnode.children[0]) if vnode.children else None
        if element.type == "Modal":
            return None  # Off-screen placeholder; not part of the visible flow.

        child_layouts: List[LayoutNode] = []
        for child_vnode in vnode.children:
            child_layout = self._build_layout_tree_cached(child_vnode)
            if child_layout is not None:
                child_layouts.append(child_layout)

        cached = vnode._layout_node
        if cached is not None and not vnode._layout_dirty:
            cached_children = self._direct_child_layouts(cached, element)
            if len(cached_children) == len(child_layouts) and all(
                a is b for a, b in zip(cached_children, child_layouts)
            ):
                return cached

        layout = LayoutNode(style=extract_layout_style(element.props), user_data=vnode)
        layout.dirty = True
        if element.type == "ScrollView":
            # Mark the scroll axis so the layout engine clamps the
            # container's own main-axis size to its parent's available
            # space (otherwise the container grows to fit its content
            # and there is no overflow for the native ScrollView to
            # actually scroll). The children are still wrapped below so
            # they see an unbounded main axis when measured.
            scroll_axis = element.props.get("scroll_axis", "vertical")
            layout._pn_scroll_axis = "x" if scroll_axis == "horizontal" else "y"

        if not vnode.children:
            measure = self._make_measure_callback(vnode)
            if measure is not None:
                layout.measure = measure

        for child_layout in child_layouts:
            if element.type == "ScrollView":
                axis = element.props.get("scroll_axis", "vertical")
                child_layout = self._wrap_scroll_axis(child_layout, axis="x" if axis == "horizontal" else "y")
                child_layout.dirty = True
            layout.children.append(child_layout)

        vnode._layout_node = layout
        return layout

    @staticmethod
    def _direct_child_layouts(layout: LayoutNode, element: Element) -> List[LayoutNode]:
        """Return the cached child layout nodes, unwrapping ScrollView wrappers."""
        if element.type == "ScrollView":
            out: List[LayoutNode] = []
            for wrapper in layout.children:
                out.extend(wrapper.children)
            return out
        return list(layout.children)

    def _clear_layout_dirty(self, vnode: VNode) -> None:
        vnode._layout_dirty = False
        node = vnode._layout_node
        if node is not None:
            node.dirty = False
            for wrapper_or_child in node.children:
                wrapper_or_child.dirty = False
        for child in vnode.children:
            self._clear_layout_dirty(child)

    def _build_layout_tree(self, vnode: VNode) -> Optional[LayoutNode]:
        """Build a fresh (uncached) `LayoutNode` tree for ``vnode``.

        Used for Modal content (laid out against the viewport each
        pass) and by
        [`compute_layout_for_test`][pythonnative.reconciler.Reconciler.compute_layout_for_test].
        Function components, providers, and error boundaries are
        transparent: they delegate to their (single) child. Native
        nodes contribute a `LayoutNode` whose ``user_data`` points
        back to the VNode so the layout pass can apply frames.
        """
        element = vnode.element
        if not isinstance(element.type, str):
            return self._build_layout_tree(vnode.children[0]) if vnode.children else None
        if element.type in ("__Provider__", "__ErrorBoundary__", "__Fragment__"):
            return self._build_layout_tree(vnode.children[0]) if vnode.children else None
        if element.type == "Modal":
            return None

        style = extract_layout_style(element.props)
        layout = LayoutNode(style=style, user_data=vnode)
        layout.dirty = True
        if element.type == "ScrollView":
            scroll_axis = element.props.get("scroll_axis", "vertical")
            layout._pn_scroll_axis = "x" if scroll_axis == "horizontal" else "y"

        if not vnode.children:
            measure = self._make_measure_callback(vnode)
            if measure is not None:
                layout.measure = measure

        for child_vnode in vnode.children:
            child_layout = self._build_layout_tree(child_vnode)
            if child_layout is None:
                continue
            if element.type == "ScrollView":
                # ScrollView's child sees an unbounded main-axis viewport so it
                # can size to its full content (the scrollable region).
                axis = element.props.get("scroll_axis", "vertical")
                child_layout = self._wrap_scroll_axis(child_layout, axis="x" if axis == "horizontal" else "y")
                child_layout.dirty = True
            layout.children.append(child_layout)

        return layout

    @staticmethod
    def _wrap_scroll_axis(child: LayoutNode, axis: str) -> LayoutNode:
        """Wrap ``child`` so the layout engine treats one axis as unbounded.

        Used by ScrollView to let its content grow beyond the viewport
        on the scroll axis. The wrapper is a transparent layout node
        whose ``user_data`` is ``None`` (frames still apply to the
        underlying native views through the child's own node).
        """
        wrapper_style = {"flex_direction": "column"} if axis == "y" else {"flex_direction": "row"}
        wrapper = LayoutNode(style=wrapper_style, user_data=None)
        wrapper.children.append(child)
        return wrapper

    def _make_measure_callback(self, vnode: VNode) -> Optional[Any]:
        """Return a measure callback for ``vnode`` if it has an intrinsic size."""
        type_name = vnode.element.type
        if type_name not in self._INTRINSIC_TYPES:
            return None
        if vnode.tag is None:
            return None
        backend = self.backend

        def measure(max_w: float, max_h: float) -> Tuple[float, float]:
            cache = vnode._measure_cache
            if cache is not None and cache[0] == max_w and cache[1] == max_h:
                return (cache[2], cache[3])
            try:
                w, h = backend.measure_intrinsic(vnode.tag, max_w, max_h)
                result = (float(w), float(h))
                vnode._measure_cache = (max_w, max_h, result[0], result[1])
                return result
            except Exception:
                return (0.0, 0.0)

        return measure

    def _collect_frames(self, layout_node: LayoutNode, parent_x: float, parent_y: float) -> None:
        """Walk a positioned layout tree and emit `SetFrameOp`s for changed frames.

        Coordinates accumulate through transparent wrapper nodes
        (e.g., the ScrollView axis wrapper) so the underlying native
        view receives its position relative to its true native parent.
        """
        vnode = layout_node.user_data
        if vnode is not None and vnode.tag is not None:
            frame = (
                layout_node.x + parent_x,
                layout_node.y + parent_y,
                layout_node.width,
                layout_node.height,
            )
            if vnode._last_frame != frame:
                vnode._last_frame = frame
                self._ops.append(SetFrameOp(vnode.tag, frame[0], frame[1], frame[2], frame[3]))
                # Mirror the frame into the element's ref (if any) so
                # Python code can read measured geometry without a
                # native round-trip (used by FlatList's virtualization).
                ref = vnode.element.props.get("ref") if vnode.element.props else None
                if isinstance(ref, dict):
                    ref["_pn_frame"] = frame
            child_offset_x = 0.0
            child_offset_y = 0.0
        else:
            child_offset_x = layout_node.x + parent_x
            child_offset_y = layout_node.y + parent_y

        for child in layout_node.children:
            self._collect_frames(child, child_offset_x, child_offset_y)

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
