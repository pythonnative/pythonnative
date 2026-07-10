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
  across renders. Components may return a single element, a list of
  elements, or ``None``; every node in the tree can contribute zero or
  more native views to its native parent (**multi-child rendering**).
- **Provider elements** (`type == "__Provider__"`), which push and pop
  context values during traversal and, when their value changes,
  re-render every descendant that read the context on its last render
  (**reactive context**), even under memoized components that skipped.
- **Error boundary elements** (`type == "__ErrorBoundary__"`), which
  catch exceptions in child subtrees, invoke ``on_error``, render a
  fallback (optionally receiving a ``reset`` callable), and remount
  their children when ``reset`` is called.
- **Fragments** (`type == "__Fragment__"`), expanded inline unless
  keyed, in which case they participate in keyed reconciliation as a
  transparent multi-child wrapper.
- **Portals** (`type == "Portal"`), native elements whose handler hosts
  their children in a top-level overlay. Portals contribute no child to
  their native parent; their subtree is laid out against the viewport
  like a `Modal`.
- **Key-based child reconciliation** with indexed, move-aware inserts
  computed by simulating the native child list, so appends and keyed
  reorders emit the minimal set of `InsertOp`s.
- **Two effect phases**: layout effects
  ([`use_layout_effect`][pythonnative.use_layout_effect]) flush
  synchronously after mutations and layout; passive effects
  ([`use_effect`][pythonnative.use_effect]) flush afterwards.
- **Incremental layout**: a parallel
  [`LayoutNode`][pythonnative.layout.LayoutNode] tree is cached across
  passes; clean subtrees keep their cached nodes (enabling the layout
  engine's measurement memo) and only frames that actually changed are
  sent to the native side.
"""

import inspect
import itertools
import os
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from . import diagnostics
from .element import Element
from .events import extract_events, get_event_registry
from .layout import LayoutNode, calculate_layout, extract_layout_style
from .mutations import CreateOp, DestroyOp, InsertOp, Mutation, SetFrameOp, UpdateOp

# Props the reconciler consumes itself (i.e., never forwards to the
# native handler). ``ref`` is one such prop: components pass a
# [`Ref`][pythonnative.Ref] from ``use_ref()`` and the reconciler
# populates ``ref.current`` with the underlying native view (and
# ``ref._pn_tag`` with the view's tag), mirroring React's ``ref``
# semantics.
_RECONCILER_OWNED_PROPS = frozenset({"ref"})

# Element types that never own a native view: they are transparent
# wrappers whose children mount directly into the surrounding native
# parent.
_TRANSPARENT_TYPES = frozenset({"__Provider__", "__ErrorBoundary__", "__Fragment__"})

# Native element types whose subtree is laid out against the viewport
# in a detached pass instead of participating in the main layout flow.
_DETACHED_TYPES = frozenset({"Modal", "Portal"})

_MISSING = object()

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


def _normalize_children(children: Any, owner: str = "") -> List[Element]:
    """Normalize arbitrary render output into a flat list of Elements.

    Accepts a single element, ``None``, ``True``/``False`` (both
    skipped, enabling inline conditionals like ``cond and Text(...)``),
    lists/tuples (flattened recursively), and unkeyed Fragments
    (expanded inline so they never touch the native tree). Keyed
    Fragments are preserved so they can participate in keyed
    reconciliation as a unit.

    Non-Element values other than the above are dropped with a
    dev-mode warning.
    """
    out: List[Element] = []

    def add(item: Any) -> None:
        if item is None or item is True or item is False:
            return
        if isinstance(item, (list, tuple)):
            for sub in item:
                add(sub)
            return
        if isinstance(item, Element):
            if isinstance(item.type, str) and item.type == "__Fragment__" and item.key is None:
                for sub in item.children:
                    add(sub)
                return
            out.append(item)
            return
        diagnostics.warn_once(
            f"Ignoring non-Element child {item!r} ({type(item).__name__})"
            + (f" under {owner}" if owner else "")
            + ". Children must be Elements, lists of Elements, or None/False for conditionals.",
            key=f"badchild:{owner}:{type(item).__name__}",
        )

    add(children)

    if diagnostics.is_dev() and len(out) > 1:
        seen: Set[Any] = set()
        for el in out:
            if el.key is None:
                continue
            if el.key in seen:
                diagnostics.warn_once(
                    f"Duplicate key {el.key!r} among children"
                    + (f" of {owner}" if owner else "")
                    + ". Keys must be unique among siblings; duplicates break "
                    "keyed reconciliation and can cross-wire component state.",
                    key=f"dupkey:{owner}:{el.key!r}",
                )
            seen.add(el.key)
    return out


class VNode:
    """A mounted [`Element`][pythonnative.Element] plus its native identity.

    The reconciler walks parallel trees of `VNode` and incoming
    `Element` to compute the minimal set of native mutations.

    Attributes:
        element: The `Element` last rendered into this slot.
        tag: Integer identity of the underlying native view. Native
            elements own a fresh tag; transparent wrappers (function
            components, providers, boundaries, keyed fragments)
            delegate the tag of their first native root. ``None`` when
            the subtree renders no native view.
        native_view: The platform-native view object, resolved from the
            registry after commit. May be `None` for purely virtual
            wrappers that rendered nothing.
        children: Ordered list of child `VNode` instances. Wrappers may
            own any number of children; each child contributes zero or
            more native roots to the nearest native ancestor.
        parent: The owning `VNode`, or `None` for the tree root. Used
            by local (component-scoped) re-renders to bubble a changed
            subtree up to the nearest native container.
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
        "_error",
    )

    def __init__(self, element: Element, children: List["VNode"], tag: Optional[int] = None) -> None:
        self.element = element
        self.tag = tag
        self.native_view: Any = None
        self.children = children
        self.parent: Optional["VNode"] = None
        self.hook_state: Any = None
        self.mounted: bool = True
        self._rendered: Any = None
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
        # clean (see Reconciler._build_layout_list_cached).
        self._layout_node: Optional[LayoutNode] = None
        # True when this node's layout-relevant props or child list
        # changed since the last layout pass.
        self._layout_dirty: bool = True
        # For ``__ErrorBoundary__`` nodes: the caught exception while
        # the fallback is showing, else ``None``.
        self._error: Optional[BaseException] = None


class Reconciler:
    """Create, diff, and patch native view trees from `Element` descriptors.

    After each [`mount`][pythonnative.reconciler.Reconciler.mount],
    [`reconcile`][pythonnative.reconciler.Reconciler.reconcile], or
    [`flush_dirty`][pythonnative.reconciler.Reconciler.flush_dirty]
    pass the reconciler:

    1. applies the accumulated mutation ops in one batch,
    2. resolves freshly created native views and populates refs,
    3. runs the layout pass, emitting only changed frames,
    4. flushes layout effects (children-first), then
    5. flushes passive effects.

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
        # Error-boundary VNodes whose ``reset`` was called; drained
        # alongside dirty components.
        self._dirty_boundaries: Dict[int, VNode] = {}
        # Tags destroyed during the current pass, used when simulating
        # a native parent's child list. Tags are never reused, so stale
        # entries can never alias a live view.
        self._destroyed_tags: Set[int] = set()
        # ``use_back_handler`` registrations, oldest-first. Dispatch
        # walks the list in reverse so deeper / more recently mounted
        # handlers win.
        self._back_handlers: List[Callable[[], bool]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def mount(self, element: Element) -> Any:
        """Build native views from `element` and return the root native view.

        Args:
            element: The root `Element` to render.

        Returns:
            The platform-native view that represents the root of the
            mounted tree (the first native root when the root element
            renders several).
        """
        self._log(f"mount: start type={self._type_label(element.type)!r}")
        self._dirty_nodes.clear()
        self._dirty_boundaries.clear()
        self._destroyed_tags.clear()
        self._tree = self._create_tree(element)
        self._drain_dirty()
        self._commit()
        self._warn_on_multiple_roots()
        return self._tree.native_view

    def reconcile(self, new_element: Element) -> Any:
        """Diff `new_element` against the current tree and patch native views.

        Args:
            new_element: The desired root element after a state change.

        Returns:
            The (possibly replaced) root native view.
        """
        # A full reconcile rebuilds the whole tree from the root, so any
        # pending per-component dirty marks are now obsolete. Reactive
        # context invalidation may re-add entries during the pass; those
        # are drained before commit.
        self._dirty_nodes.clear()
        self._destroyed_tags.clear()
        if self._tree is None:
            self._tree = self._create_tree(new_element)
        else:
            self._tree = self._reconcile_node(self._tree, new_element)
        self._drain_dirty()
        self._commit()
        self._warn_on_multiple_roots()
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
        self._dirty_boundaries.clear()
        self._back_handlers.clear()
        self._flush_ops()

    def dispatch_command(self, tag: Optional[int], name: str, args: Optional[Dict[str, Any]] = None) -> Any:
        """Run an imperative command against the view registered under ``tag``."""
        if tag is None:
            return None
        return self.backend.command(tag, name, args or {})

    def mark_dirty(self, vnode: "VNode") -> None:
        """Queue ``vnode`` (a function component) for a local re-render.

        Called by a component's ``use_state`` / ``use_reducer`` setter
        when its own state changes, and by reactive context when a
        Provider's value changes for a consumer that a memoized
        ancestor would otherwise skip. The node is re-rendered on the
        next [`flush_dirty`][pythonnative.reconciler.Reconciler.flush_dirty]
        pass. Marking is idempotent and cheap; the actual render is
        deferred so several setters (e.g. inside
        [`batch_updates`][pythonnative.batch_updates]) coalesce into a
        single pass.
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
        if not self._dirty_nodes and not self._dirty_boundaries:
            return self._tree.native_view

        self._destroyed_tags.clear()
        self._drain_dirty()
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
    # Back handlers (use_back_handler)
    # ------------------------------------------------------------------

    def register_back_handler(self, handler: Callable[[], bool]) -> Callable[[], None]:
        """Register a back-press handler; returns an unregister callable.

        Used by [`use_back_handler`][pythonnative.use_back_handler].
        Handlers are dispatched most-recently-registered first.
        """
        self._back_handlers.append(handler)

        def unregister() -> None:
            try:
                self._back_handlers.remove(handler)
            except ValueError:
                pass

        return unregister

    def dispatch_back_press(self) -> bool:
        """Offer the system back action to registered handlers.

        Returns:
            ``True`` if a handler consumed the event (the platform
            should *not* run its default behavior).
        """
        for handler in reversed(list(self._back_handlers)):
            if handler():
                return True
        return False

    # ------------------------------------------------------------------
    # Dirty draining (local updates, reactive context, boundary resets)
    # ------------------------------------------------------------------

    def _drain_dirty(self) -> None:
        """Process dirty components and boundary resets until none remain.

        Reactive context can mark additional components dirty *during*
        a pass (a re-render changed a Provider value whose consumers sit
        under memoized subtrees), so this loops until quiescent, with a
        cap to break pathological update cycles.
        """
        guard = 0
        while self._dirty_nodes or self._dirty_boundaries:
            guard += 1
            if guard > 100:
                diagnostics.warn(
                    "Update loop did not settle after 100 iterations; a component is "
                    "likely setting state unconditionally during render or effects."
                )
                self._dirty_nodes.clear()
                self._dirty_boundaries.clear()
                return

            boundaries = list(self._dirty_boundaries.values())
            self._dirty_boundaries.clear()
            for boundary in boundaries:
                if not boundary.mounted:
                    continue
                providers = self._ancestor_providers(boundary)
                for context, value in providers:
                    context._stack.append(value)
                try:
                    self._reconcile_error_boundary(boundary, boundary.element)
                finally:
                    for context, _value in reversed(providers):
                        context._stack.pop()
                self._bubble_structure_change(boundary)

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
                    # boundary ancestor (which mounts its fallback). With no
                    # boundary the exception propagates, matching a full render.
                    self._handle_local_render_error(vnode, exc)

    # ------------------------------------------------------------------
    # Commit driver
    # ------------------------------------------------------------------

    def _commit(self) -> None:
        """Apply the accumulated transaction and run the post-commit phases."""
        self._flush_ops()
        self._fix_tree_links()
        self._run_layout()
        self._flush_ops()
        self._flush_layout_effects()
        self._flush_ops()
        self._flush_passive_effects()
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
    # Post-commit walks
    # ------------------------------------------------------------------

    def _fix_tree_links(self) -> None:
        """Refresh ``parent`` links and delegated wrapper identity.

        This walk is the single source of truth for *delegated*
        identity: transparent wrappers (components, providers,
        boundaries, keyed fragments) re-derive their ``tag`` /
        ``native_view`` from their first native root, so the rest of
        the reconciler never has to chase delegation chains by hand.
        """
        if self._tree is None:
            return
        self._tree.parent = None
        self._fix_node_links(self._tree)

    def _fix_node_links(self, node: VNode) -> None:
        for child in node.children:
            child.parent = node
            self._fix_node_links(child)
        if not self._is_native_node(node):
            self._refresh_identity(node)

    def _flush_layout_effects(self) -> None:
        """Flush queued layout effects, children before parents."""
        if self._tree is not None:
            self._walk_layout_effects(self._tree)

    def _walk_layout_effects(self, node: VNode) -> None:
        for child in node.children:
            self._walk_layout_effects(child)
        if node.hook_state is not None:
            node.hook_state.flush_layout_effects()

    def _flush_passive_effects(self) -> None:
        """Flush queued passive effects, children before parents."""
        if self._tree is not None:
            self._walk_passive_effects(self._tree)

    def _walk_passive_effects(self, node: VNode) -> None:
        for child in node.children:
            self._walk_passive_effects(child)
        if node.hook_state is not None:
            node.hook_state.flush_pending_effects()

    # ------------------------------------------------------------------
    # Native-root helpers (multi-child support)
    # ------------------------------------------------------------------

    def _native_roots(self, node: VNode) -> List[VNode]:
        """Return the ordered native views ``node`` contributes to its native parent.

        Native elements contribute themselves, except ``Portal``, whose
        handler self-attaches to a top-level overlay and therefore
        contributes nothing. Transparent wrappers contribute the
        concatenation of their children's roots.
        """
        if self._is_native_node(node):
            if node.element.type == "Portal":
                return []
            return [node]
        roots: List[VNode] = []
        for child in node.children:
            roots.extend(self._native_roots(child))
        return roots

    def _flattened_child_roots(self, node: VNode) -> List[VNode]:
        """Return the native child list of a native container node."""
        roots: List[VNode] = []
        for child in node.children:
            roots.extend(self._native_roots(child))
        return roots

    def _refresh_identity(self, node: VNode) -> None:
        """Point a wrapper's ``tag`` / ``native_view`` at its first native root."""
        if self._is_native_node(node):
            return
        for root in self._native_roots(node):
            node.tag = root.tag
            node.native_view = root.native_view
            return
        node.tag = None
        node.native_view = None

    def _sync_native_children(
        self, parent_tag: int, before_tags: List[Optional[int]], after_roots: List[VNode]
    ) -> bool:
        """Emit the `InsertOp`s that turn the parent's native child list into ``after_roots``.

        Simulates the native child list: it currently holds the
        surviving members of ``before_tags`` (destroys already emitted
        detach on the native side), and each emitted ensure-insert
        mirrors the handlers' move-aware semantics. Appends and keyed
        reorders therefore emit only the ops they need.

        Returns:
            Whether the native child list changed at all (used for
            layout invalidation).
        """
        surviving = [t for t in before_tags if t is not None and t not in self._destroyed_tags]
        after_tags = [r.tag for r in after_roots if r.tag is not None]
        if surviving == after_tags:
            return len(surviving) != len(before_tags)

        sim = list(surviving)
        for i, tag in enumerate(after_tags):
            if i < len(sim) and sim[i] == tag:
                continue
            try:
                j = sim.index(tag)
            except ValueError:
                j = -1
            if j >= 0:
                sim.pop(j)
            sim.insert(i, tag)
            self._ops.append(InsertOp(parent_tag, tag, i))
        return True

    def _bubble_structure_change(self, vnode: VNode) -> None:
        """Propagate a changed native-root set up to the nearest native container.

        A local re-render starts below the real native container, so
        when the dirty component's native roots change (view replaced,
        added, or removed), every transparent ancestor re-derives its
        identity and the nearest native ancestor re-ensures its full
        child order (handlers no-op for children already in place).
        """
        node = vnode.parent
        while node is not None:
            if self._is_native_node(node):
                if node.tag is not None:
                    roots = self._flattened_child_roots(node)
                    for i, root in enumerate(roots):
                        if root.tag is not None:
                            self._ops.append(InsertOp(node.tag, root.tag, i))
                self._mark_layout_dirty(node)
                return
            self._refresh_identity(node)
            node = node.parent
        # Reached the root with no native container above: the root's
        # identity was already refreshed. The host detects the change by
        # comparing ``root_view()`` after the flush.

    def _warn_on_multiple_roots(self) -> None:
        if not diagnostics.is_dev() or self._tree is None:
            return
        roots = self._native_roots(self._tree)
        if len(roots) > 1:
            diagnostics.warn_once(
                f"The screen root rendered {len(roots)} native views; only the first "
                "is attached to the window. Wrap your root in a View/Column (Portals "
                "are exempt and may appear anywhere).",
                key=f"multi-root:{id(self)}",
            )

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

    def _render_component_body(self, hook_state: Any, element: Element) -> List[Element]:
        """Run a function component's body and normalize its output."""
        from .hooks import _set_hook_state

        component_fn = element.type
        assert callable(component_fn), "component elements always carry a callable type"
        hook_state.begin_render(self._type_label(element.type))
        hook_state._trigger_render = self._screen_re_render
        _set_hook_state(hook_state)
        try:
            rendered = component_fn(**element.props)
            hook_state.finish_render()
        finally:
            _set_hook_state(None)
            hook_state._dirty = False
        return _normalize_children(rendered, owner=self._type_label(element.type))

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
        element = vnode.element
        if not callable(element.type):
            return
        hook_state = vnode.hook_state
        if hook_state is None:
            return

        before_tags = [r.tag for r in self._native_roots(vnode)]

        providers = self._ancestor_providers(vnode)
        for context, value in providers:
            context._stack.append(value)
        try:
            rendered = self._render_component_body(hook_state, element)
            new_children = self._reconcile_child_list(vnode.children, rendered)
        finally:
            for context, _value in reversed(providers):
                context._stack.pop()

        for child in new_children:
            child.parent = vnode
        vnode.children = new_children
        vnode._rendered = rendered
        self._refresh_identity(vnode)
        hook_state._vnode = vnode
        hook_state._reconciler = self

        after_tags = [r.tag for r in self._native_roots(vnode)]
        if after_tags != before_tags:
            self._bubble_structure_change(vnode)

    def _handle_local_render_error(self, vnode: "VNode", exc: Exception) -> None:
        """Route a local re-render failure to the nearest ``ErrorBoundary`` ancestor.

        Activates the boundary (destroying the failed subtree and
        mounting the fallback). If no boundary encloses ``vnode`` the
        exception propagates, exactly as it would during a full render;
        the screen host catches it and shows the dev error overlay.
        """
        node = vnode.parent
        while node is not None:
            if isinstance(node.element.type, str) and node.element.type == "__ErrorBoundary__":
                providers = self._ancestor_providers(node)
                for context, value in providers:
                    context._stack.append(value)
                try:
                    self._activate_boundary(node, exc)
                finally:
                    for context, _value in reversed(providers):
                        context._stack.pop()
                self._bubble_structure_change(node)
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

    @staticmethod
    def _is_native_node(node: "VNode") -> bool:
        t = node.element.type
        return isinstance(t, str) and t not in _TRANSPARENT_TYPES

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
        # Provider: push context, create children, pop context.
        if element.type == "__Provider__":
            context = element.props["__context__"]
            context._stack.append(element.props["__value__"])
            try:
                children = self._create_child_list(_normalize_children(element.children, owner="Provider"))
            finally:
                context._stack.pop()
            vnode = VNode(element, children)
            for child in children:
                child.parent = vnode
            self._refresh_identity(vnode)
            return vnode

        # Error boundary: catch exceptions in the child subtree.
        if element.type == "__ErrorBoundary__":
            return self._create_error_boundary(element)

        # Keyed fragment (or a fragment reaching here as a root):
        # a transparent multi-child wrapper.
        if element.type == "__Fragment__":
            children = self._create_child_list(_normalize_children(element.children, owner="Fragment"))
            vnode = VNode(element, children)
            for child in children:
                child.parent = vnode
            self._refresh_identity(vnode)
            return vnode

        # Function component: call with hook context.
        if callable(element.type):
            from .hooks import HookState

            hook_state = HookState()
            rendered = self._render_component_body(hook_state, element)
            children = self._create_child_list(rendered)
            vnode = VNode(element, children)
            for child in children:
                child.parent = vnode
            vnode.hook_state = hook_state
            vnode._rendered = rendered
            self._refresh_identity(vnode)
            hook_state._vnode = vnode
            hook_state._reconciler = self
            return vnode

        # Native element.
        tag = next_tag()
        clean_props, events = self._split_props(element.props)
        vnode = VNode(element, [], tag=tag)
        vnode._clean_props = clean_props
        if events:
            self._events.set_events(tag, events)
        self._ops.append(CreateOp(tag, element.type, clean_props))
        self._created.append(vnode)

        child_els = _normalize_children(element.children, owner=element.type)
        index = 0
        for child_el in child_els:
            child_node = self._create_tree(child_el)
            child_node.parent = vnode
            vnode.children.append(child_node)
            for root in self._native_roots(child_node):
                if root.tag is not None:
                    self._ops.append(InsertOp(tag, root.tag, index))
                    index += 1
        return vnode

    def _create_child_list(self, elements: List[Element]) -> List[VNode]:
        """Create VNodes for ``elements``, cleaning up on mid-list failure."""
        nodes: List[VNode] = []
        try:
            for el in elements:
                nodes.append(self._create_tree(el))
        except Exception:
            for node in nodes:
                self._destroy_tree(node)
            raise
        return nodes

    # ------------------------------------------------------------------
    # Error boundaries
    # ------------------------------------------------------------------

    def _create_error_boundary(self, element: Element) -> VNode:
        vnode = VNode(element, [])
        try:
            children = self._create_child_list(_normalize_children(element.children, owner="ErrorBoundary"))
        except Exception as exc:
            self._activate_boundary(vnode, exc)
            return vnode
        for child in children:
            child.parent = vnode
        vnode.children = children
        self._refresh_identity(vnode)
        return vnode

    def _reconcile_error_boundary(self, old: VNode, new_el: Element) -> VNode:
        old.element = new_el

        if old._error is not None:
            # Fallback is showing; keep showing it (rebuilt against the
            # latest fallback prop) until reset() clears the error.
            fallback_els = self._build_fallback_elements(old, old._error)
            old.children = self._reconcile_child_list(old.children, fallback_els)
            for child in old.children:
                child.parent = old
            self._refresh_identity(old)
            return old

        try:
            children = self._reconcile_child_list(
                old.children, _normalize_children(new_el.children, owner="ErrorBoundary")
            )
            old.children = children
            for child in children:
                child.parent = old
            self._refresh_identity(old)
        except Exception as exc:
            self._activate_boundary(old, exc)
        return old

    def _activate_boundary(self, node: VNode, exc: BaseException) -> None:
        """Destroy a boundary's failed subtree and mount its fallback.

        Calls the ``on_error`` prop (if any), records the error on the
        node, and replaces the children with the rendered fallback.
        Re-raises when the boundary has no fallback, letting an outer
        boundary (or the screen host) take over.
        """
        el = node.element
        on_error = el.props.get("__on_error__")
        if callable(on_error):
            try:
                on_error(exc)
            except Exception as cb_exc:
                diagnostics.warn(f"ErrorBoundary on_error callback raised {cb_exc!r}")

        if el.props.get("__fallback__") is None:
            raise exc

        for child in node.children:
            self._destroy_tree(child)
        node.children = []
        node._error = exc

        fallback_els = self._build_fallback_elements(node, exc)
        children = self._create_child_list(fallback_els)
        for child in children:
            child.parent = node
        node.children = children
        self._refresh_identity(node)

    def _build_fallback_elements(self, node: VNode, exc: BaseException) -> List[Element]:
        """Render a boundary's fallback prop into a normalized child list."""
        fallback = node.element.props.get("__fallback__")
        if fallback is None:
            return []
        result: Any = fallback
        if callable(fallback) and not isinstance(fallback, Element):
            arity = self._positional_arity(fallback)
            if arity >= 2:
                result = fallback(exc, self._make_boundary_reset(node))
            elif arity == 1:
                result = fallback(exc)
            else:
                result = fallback()
        return _normalize_children(result, owner="ErrorBoundary.fallback")

    @staticmethod
    def _positional_arity(fn: Callable) -> int:
        """Count positional parameters ``fn`` accepts (2+ means unbounded is fine)."""
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):
            return 1
        count = 0
        for p in sig.parameters.values():
            if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
                count += 1
            elif p.kind == inspect.Parameter.VAR_POSITIONAL:
                return 2
        return count

    def _make_boundary_reset(self, node: VNode) -> Callable[[], None]:
        """Return the ``reset`` callable handed to a boundary's fallback."""

        def reset() -> None:
            if not node.mounted or node._error is None:
                return
            node._error = None
            self._dirty_boundaries[id(node)] = node
            trigger = self._screen_re_render
            if trigger is not None:
                from .hooks import _schedule_trigger

                _schedule_trigger(trigger)

        return reset

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------

    def _reconcile_node(self, old: VNode, new_el: Element) -> VNode:
        if not self._same_type(old.element, new_el):
            new_node = self._create_tree(new_el)
            self._destroy_tree(old)
            return new_node

        # Provider: detect value changes for reactive context, then
        # reconcile children under the pushed value.
        if new_el.type == "__Provider__":
            context = new_el.props["__context__"]
            old_context = old.element.props.get("__context__")
            old_value = old.element.props.get("__value__", _MISSING)
            new_value = new_el.props["__value__"]
            if old_context is not context:
                if old_context is not None:
                    self._mark_context_consumers(old, old_context)
                self._mark_context_consumers(old, context)
            elif self._value_changed(old_value, new_value):
                self._mark_context_consumers(old, context)

            context._stack.append(new_value)
            try:
                children = self._reconcile_child_list(
                    old.children, _normalize_children(new_el.children, owner="Provider")
                )
            finally:
                context._stack.pop()
            old.children = children
            for child in children:
                child.parent = old
            old.element = new_el
            self._refresh_identity(old)
            return old

        # Error boundary.
        if new_el.type == "__ErrorBoundary__":
            return self._reconcile_error_boundary(old, new_el)

        # Keyed fragment: transparent multi-child wrapper.
        if new_el.type == "__Fragment__":
            children = self._reconcile_child_list(old.children, _normalize_children(new_el.children, owner="Fragment"))
            old.children = children
            for child in children:
                child.parent = old
            old.element = new_el
            self._refresh_identity(old)
            return old

        # Function component.
        if callable(new_el.type):
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
            rendered = self._render_component_body(hook_state, new_el)
            children = self._reconcile_child_list(old.children, rendered)
            old.children = children
            for child in children:
                child.parent = old
            old.element = new_el
            old.hook_state = hook_state
            old._rendered = rendered
            self._refresh_identity(old)
            hook_state._vnode = old
            hook_state._reconciler = self
            return old

        # Native element.
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

        # Re-attach the ref if the ref identity changed (so we never
        # leave a stale ref pointing at a destroyed view, and so a
        # freshly-supplied ref gets ``current`` populated on update).
        old_ref = old.element.props.get("ref") if old.element.props else None
        new_ref = new_el.props.get("ref") if new_el.props else None
        if old_ref is not new_ref:
            self._clear_ref(old_ref)
            self._attach_ref(new_el, old.native_view, old.tag)

        self._reconcile_native_children(old, new_el.children)
        old.element = new_el
        return old

    @staticmethod
    def _value_changed(old_value: Any, new_value: Any) -> bool:
        if old_value is _MISSING:
            return True
        if old_value is new_value:
            return False
        try:
            return bool(old_value != new_value)
        except Exception:
            return True

    def _mark_context_consumers(self, provider_vnode: VNode, context: Any) -> None:
        """Mark every descendant that read ``context`` for re-render.

        This is what makes context *reactive*: consumers re-render when
        the Provider value changes even if a memoized ancestor skips.
        Descent is pruned at nested Providers of the same context, since
        their subtrees read the inner (unchanged) value.
        """
        target = id(context)

        def walk(node: VNode) -> None:
            for child in node.children:
                el = child.element
                if isinstance(el.type, str) and el.type == "__Provider__" and el.props.get("__context__") is context:
                    continue
                hs = child.hook_state
                if hs is not None and target in hs.context_deps:
                    hs._dirty = True
                    self._dirty_nodes[id(child)] = child
                walk(child)

        walk(provider_vnode)

    @staticmethod
    def _can_skip_memoized(old: VNode, new_el: Element) -> bool:
        """Return whether a memo'd function component can skip its body.

        A component is skippable iff:

        1. Its type has the ``_pn_memo`` marker set by
           [`memo`][pythonnative.memo].
        2. It has been rendered before (``old._rendered`` is populated).
        3. None of its internal state setters fired since the last
           render, and no context it reads changed
           (``hook_state._dirty`` is ``False``).
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

    def _reconcile_child_list(self, old_children: List[VNode], new_children: List[Element]) -> List[VNode]:
        """Match, reconcile, create, and destroy one level of children.

        Pure structural pass shared by native containers and
        transparent wrappers: it emits no `InsertOp`s itself. Native
        attachment order is derived afterwards by the caller (see
        [`_reconcile_native_children`][pythonnative.reconciler.Reconciler._reconcile_native_children]
        and
        [`_bubble_structure_change`][pythonnative.reconciler.Reconciler._bubble_structure_change]).

        On failure, any fully created replacement nodes are destroyed
        before the exception propagates so an enclosing error boundary
        can swap in its fallback without leaking native views.
        """
        old_by_key: dict = {}
        old_unkeyed: list = []
        for child in old_children:
            if child.element.key is not None:
                old_by_key[child.element.key] = child
            else:
                old_unkeyed.append(child)

        new_child_nodes: List[VNode] = []
        fresh_nodes: List[VNode] = []
        used_keyed: set = set()
        unkeyed_iter = iter(old_unkeyed)

        try:
            for new_el in new_children:
                matched: Optional[VNode] = None

                if new_el.key is not None and new_el.key in old_by_key:
                    matched = old_by_key[new_el.key]
                    used_keyed.add(new_el.key)
                elif new_el.key is None:
                    matched = next(unkeyed_iter, None)

                if matched is None:
                    node = self._create_tree(new_el)
                    fresh_nodes.append(node)
                    new_child_nodes.append(node)
                elif not self._same_type(matched.element, new_el):
                    node = self._create_tree(new_el)
                    self._destroy_tree(matched)
                    fresh_nodes.append(node)
                    new_child_nodes.append(node)
                else:
                    new_child_nodes.append(self._reconcile_node(matched, new_el))
        except Exception:
            for node in fresh_nodes:
                self._destroy_tree(node)
            raise

        for key, node in old_by_key.items():
            if key not in used_keyed:
                self._destroy_tree(node)
        for node in unkeyed_iter:
            self._destroy_tree(node)

        return new_child_nodes

    def _reconcile_native_children(self, parent: VNode, new_children: List[Element]) -> None:
        """Reconcile a native container's children and sync its native child list."""
        before_tags = [r.tag for r in self._flattened_child_roots(parent)]
        new_els = _normalize_children(new_children, owner=self._type_label(parent.element.type))
        children = self._reconcile_child_list(parent.children, new_els)
        parent.children = children
        for child in children:
            child.parent = parent

        if parent.tag is not None:
            changed = self._sync_native_children(parent.tag, before_tags, self._flattened_child_roots(parent))
            if changed:
                self._mark_layout_dirty(parent)

    def _destroy_tree(self, node: VNode) -> None:
        if not node.mounted:
            return
        node.mounted = False
        # Drop the node from the pending-render sets so a setter that
        # fired moments before unmount can't resurrect a dead subtree.
        self._dirty_nodes.pop(id(node), None)
        self._dirty_boundaries.pop(id(node), None)
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
            self._destroyed_tags.add(node.tag)
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
        """Populate ``ref.current`` (and the internal tag) if a ``ref`` prop exists."""
        ref = element.props.get("ref") if element.props else None
        if ref is None:
            return
        if hasattr(ref, "current"):
            ref.current = native_view
            try:
                ref._pn_tag = tag
            except Exception:
                pass
        elif diagnostics.is_dev():
            diagnostics.warn_once(
                f"Ignoring ref of type {type(ref).__name__}; pass the Ref returned by use_ref().",
                key=f"badref:{type(ref).__name__}",
            )

    def _detach_ref(self, element: Element) -> None:
        """Clear ``ref.current`` so consumers don't hold a stale handle."""
        self._clear_ref(element.props.get("ref") if element.props else None)

    @staticmethod
    def _clear_ref(ref: Any) -> None:
        if ref is None or not hasattr(ref, "current"):
            return
        try:
            ref.current = None
            ref._pn_tag = None
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

    # Childless native leaves that get a measure callback. Extends the
    # intrinsic set with ``VirtualList``, whose handlers report "fill
    # the available space" (like a ScrollView clamped to its parent):
    # without the callback an unstyled list would collapse to 0 points
    # and the platform virtualizer would never bind a row. Kept out of
    # ``_INTRINSIC_TYPES`` because its *frame* depends only on
    # available space, so data-prop changes need no layout pass.
    _MEASURED_LEAF_TYPES = _INTRINSIC_TYPES | {"VirtualList"}

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

        Wraps the user's native roots in a synthetic outer `LayoutNode`
        with the viewport size so the user's root always fills the
        screen by default (matching React Native). Skipped silently
        until the screen host has supplied a viewport size via
        [`set_viewport_size`][pythonnative.reconciler.Reconciler.set_viewport_size].

        Subtrees whose props and children are unchanged since the last
        pass keep their cached `LayoutNode` objects, which lets the
        layout engine reuse memoized measurements instead of re-running
        flex math (see ``pythonnative.layout``). Only frames that
        differ from the previously applied frame produce `SetFrameOp`s.

        The first native root's *frame* is intentionally NOT touched:
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
        layout_roots = self._build_layout_list_cached(self._tree)
        if layout_roots:
            viewport = LayoutNode(
                style={"width": viewport_w, "height": viewport_h},
                children=list(layout_roots),
            )
            viewport.dirty = True
            calculate_layout(viewport, viewport_w, viewport_h)
            # Skip set_frame for the first (host-attached) root itself;
            # its descendants are positioned relative to the root's
            # local origin, which is what they want regardless of where
            # the host placed the root in the screen.
            for i, root in enumerate(layout_roots):
                if i == 0:
                    for child in root.children:
                        self._collect_frames(child, 0.0, 0.0)
                else:
                    self._collect_frames(root, 0.0, 0.0)
        # Lay out the children of every visible ``Modal`` and every
        # ``Portal`` as a fresh subtree sized to the viewport. Detached
        # subtrees are excluded from the main layout tree (their content
        # lives in a separately presented native container) so without
        # this pass the children's frames never get computed and the
        # overlay renders blank.
        self._layout_detached_subtrees(self._tree, viewport_w, viewport_h)
        self._clear_layout_dirty(self._tree)

    def _layout_detached_subtrees(
        self,
        vnode: VNode,
        viewport_w: float,
        viewport_h: float,
    ) -> None:
        element = vnode.element
        if isinstance(element.type, str) and element.type in _DETACHED_TYPES:
            active = bool(element.props.get("visible")) if element.type == "Modal" else True
            if not active:
                return
            child_layouts: List[LayoutNode] = []
            for child in vnode.children:
                child_layouts.extend(self._build_layout_list(child))
            if child_layouts:
                viewport = LayoutNode(
                    style={"width": viewport_w, "height": viewport_h},
                    children=child_layouts,
                )
                calculate_layout(viewport, viewport_w, viewport_h)
                for c in viewport.children:
                    self._collect_frames(c, 0.0, 0.0)
            # Recurse so overlays nested inside this overlay lay out too.
            for child in vnode.children:
                self._layout_detached_subtrees(child, viewport_w, viewport_h)
            return
        for child in vnode.children:
            self._layout_detached_subtrees(child, viewport_w, viewport_h)

    def _build_layout_list_cached(self, vnode: VNode) -> List[LayoutNode]:
        """Like `_build_layout_list` but reuses cached subtrees when clean.

        A VNode's cached `LayoutNode` is reused when the node itself is
        layout-clean and every child produced its cached node too (i.e.
        the whole subtree is untouched). Reused nodes keep
        ``dirty=False`` so the layout engine can serve their sizes from
        its measurement memo; rebuilt nodes are flagged dirty, which
        forces fresh flex math along the changed path.
        """
        element = vnode.element
        if not isinstance(element.type, str) or element.type in _TRANSPARENT_TYPES:
            out: List[LayoutNode] = []
            for child in vnode.children:
                out.extend(self._build_layout_list_cached(child))
            return out
        if element.type in _DETACHED_TYPES:
            return []  # Off-screen placeholder; not part of the visible flow.

        child_layouts: List[LayoutNode] = []
        for child_vnode in vnode.children:
            child_layouts.extend(self._build_layout_list_cached(child_vnode))

        cached = vnode._layout_node
        if cached is not None and not vnode._layout_dirty:
            cached_children = self._direct_child_layouts(cached, element)
            if len(cached_children) == len(child_layouts) and all(
                a is b for a, b in zip(cached_children, child_layouts)
            ):
                return [cached]

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
        return [layout]

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

    def _build_layout_list(self, vnode: VNode) -> List[LayoutNode]:
        """Build fresh (uncached) `LayoutNode`s for ``vnode``.

        Used for detached content (Modal / Portal, laid out against the
        viewport each pass) and by
        [`compute_layout_for_test`][pythonnative.reconciler.Reconciler.compute_layout_for_test].
        Function components, providers, boundaries, and fragments are
        transparent: they contribute their children's layout nodes.
        Native nodes contribute a `LayoutNode` whose ``user_data``
        points back to the VNode so the layout pass can apply frames.
        """
        element = vnode.element
        if not isinstance(element.type, str) or element.type in _TRANSPARENT_TYPES:
            out: List[LayoutNode] = []
            for child in vnode.children:
                out.extend(self._build_layout_list(child))
            return out
        if element.type in _DETACHED_TYPES:
            return []

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
            for child_layout in self._build_layout_list(child_vnode):
                if element.type == "ScrollView":
                    # ScrollView's child sees an unbounded main-axis viewport so it
                    # can size to its full content (the scrollable region).
                    axis = element.props.get("scroll_axis", "vertical")
                    child_layout = self._wrap_scroll_axis(child_layout, axis="x" if axis == "horizontal" else "y")
                    child_layout.dirty = True
                layout.children.append(child_layout)

        return [layout]

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
        if type_name not in self._MEASURED_LEAF_TYPES:
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
                if ref is not None and hasattr(ref, "current"):
                    try:
                        ref._pn_frame = frame
                    except Exception:
                        pass
            child_offset_x = 0.0
            child_offset_y = 0.0
        else:
            child_offset_x = layout_node.x + parent_x
            child_offset_y = layout_node.y + parent_y

        for child in layout_node.children:
            self._collect_frames(child, child_offset_x, child_offset_y)

    # ------------------------------------------------------------------
    # Hot-reload support
    # ------------------------------------------------------------------

    def reset_hook_signatures(self) -> None:
        """Forget recorded hook-order signatures across the whole tree.

        Called by the hot-reload machinery after a Fast Refresh swaps in
        new component bodies, since the old call signatures no longer
        apply.
        """

        def walk(node: VNode) -> None:
            if node.hook_state is not None:
                node.hook_state.reset_hook_signature()
            for child in node.children:
                walk(child)

        if self._tree is not None:
            walk(self._tree)

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
        layout_roots = self._build_layout_list(self._tree)
        if not layout_roots:
            return None
        viewport = LayoutNode(
            style={"width": viewport_width, "height": viewport_height},
            children=list(layout_roots),
        )
        calculate_layout(viewport, viewport_width, viewport_height)
        return viewport
