"""The [`Reconciler`][pythonnative.reconciler.core.Reconciler]: element trees in, native mutations out.

One reconciler owns one mounted tree (a screen, a list row, a test
render). Each pass runs the same phases in order:

1. **Render**: component bodies run for the subtrees that need it,
   producing [`Element`][pythonnative.Element] descriptions. Hook state
   is installed for the duration of each body.
2. **Diff and stage**: elements are compared with the mounted
   [`VNode`][pythonnative.reconciler.VNode] in their slot. Creates,
   prop updates, attach/detach, and destroys are *staged* into an op
   list instead of being applied immediately.
3. **Commit**: the staged ops go to the backend in one batch, refs are
   populated, the layout pass runs (once a viewport is known), then
   effects flush: ``use_layout_effect`` first, ``use_effect`` after.

A render requested while a pass is in flight (an effect setting
state, a boundary reset) is queued and drained before the call
returns, bounded so runaway update loops surface as an error rather
than a hang. Hosts never observe a half-committed tree.

The class is assembled from mixins to keep each concern readable:
this module holds the render/diff/commit pipeline,
``boundaries`` handles
``ErrorBoundary`` and ``Suspense``, and
``layout_pass`` runs flexbox.
"""

from __future__ import annotations

import asyncio
import inspect
import os
from contextlib import contextmanager
from functools import partial
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Tuple

from .. import diagnostics
from ..component import Component
from ..element import ERROR_BOUNDARY, FRAGMENT, SUSPENSE, Element
from ..events import extract_events, get_event_registry
from ..hooks import Context, HookState, install_hook_state, restore_hook_state
from ..mutations import CreateOp, DestroyOp, InsertOp, Mutation, UpdateOp
from ..scheduler import TransitionQueue, schedule_trigger
from ..suspense import CoroDriver, Suspend
from .boundaries import BoundaryMixin, HydrationMap
from .children import plan_child_moves
from .layout_pass import LayoutMixin, affects_layout
from .vnode import VNode, next_tag, normalize_children, shallow_equal_props

__all__ = ["Reconciler"]

# Props the reconciler consumes itself and never forwards to the
# native handler. ``ref`` is populated with the native view after
# commit, mirroring React's ``ref`` semantics.
_RECONCILER_OWNED_PROPS = frozenset({"ref"})

# Hard ceiling on renders drained inside one host call, so a component
# that sets state unconditionally in an effect surfaces as an error
# instead of hanging the UI thread.
_MAX_RENDERS_PER_PASS = 25

_MISSING = object()


class Reconciler(BoundaryMixin, LayoutMixin):
    """Owns one mounted tree and translates element diffs into native mutations.

    Args:
        backend: An object implementing the registry protocol
            (``apply_mutations``, ``resolve_view``, ``measure_intrinsic``,
            ``command``). PythonNative ships Android, iOS, and desktop
            registries; tests use
            [`FakeBackend`][pythonnative.testing.FakeBackend].

    Attributes:
        backend: The backend passed at construction.
        on_render_requested: Optional callback hosts set to be told a
            re-render is wanted (to hop onto the UI thread or guard
            with a red box). When ``None`` the reconciler re-renders
            inline. Whatever the callback does, it should end up
            calling [`flush_dirty`][pythonnative.reconciler.core.Reconciler.flush_dirty].
        on_back_registered: Optional callback fired when the first
            [`use_back_handler`][pythonnative.use_back_handler]
            registers, so hosts can enable hardware back interception.
        transitions: Deferred-render queue behind
            [`use_transition`][pythonnative.use_transition]; owned per
            reconciler so screens never delay each other.
    """

    def __init__(self, backend: Any) -> None:
        self.backend = backend
        self.root: Optional[VNode] = None
        self.on_render_requested: Optional[Callable[[], None]] = None
        self.on_back_registered: Optional[Callable[[], None]] = None
        self.transitions = TransitionQueue()

        self._events = get_event_registry()
        self._ops: List[Mutation] = []
        self._created: List[VNode] = []
        self._rendering = False
        self._render_queued = False
        # Component nodes whose own state changed since the last flush,
        # keyed by ``id`` to dedupe while keeping a strong reference.
        self._dirty_nodes: Dict[int, VNode] = {}
        # Error boundaries whose ``reset`` was called.
        self._dirty_boundaries: Dict[int, VNode] = {}
        # Suspense nodes whose awaited work completed.
        self._dirty_suspense: Dict[int, VNode] = {}
        # Hydration map active while a Suspense boundary retries its
        # content, and hook states salvaged while a Suspend unwinds.
        self._hydration: Optional[HydrationMap] = None
        self._suspense_salvage: Optional[HydrationMap] = None
        # Tags destroyed during the current pass; tags are never
        # reused, so stale entries can never alias a live view.
        self._destroyed_tags: Set[int] = set()
        # ``use_back_handler`` registrations, oldest first.
        self._back_handlers: List[Callable[[], bool]] = []
        self._init_layout_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def root_tag(self) -> Optional[int]:
        """Tag of the root native view, or ``None`` when nothing is mounted."""
        return self.root.tag if self.root is not None else None

    def root_view(self) -> Any:
        """The root native view object, or ``None`` before mount."""
        return self.root.native_view if self.root is not None else None

    def mount(self, element: Element) -> Any:
        """Build native views for ``element`` and return the root native view.

        Any previously mounted tree is unmounted first.
        """
        if self.root is not None:
            self.unmount()
        self._log(f"mount: {element!r}")
        with self._pass():
            self._destroyed_tags.clear()
            try:
                self.root = self._create_tree(element)
            except Suspend as signal:
                self._discard_salvage()
                raise self._missing_suspense_error(signal) from None
            self._drain_dirty()
            self._commit()
            self._warn_on_multiple_roots()
        return self.root_view()

    def reconcile(self, element: Element) -> Any:
        """Diff ``element`` against the mounted tree and patch native views.

        Pending state updates are drained as part of the pass, so hosts
        only call this when the root element itself changed (new props
        from outside the tree).
        """
        if self.root is None:
            return self.mount(element)
        with self._pass():
            # A full pass covers every dirty component; reactive context
            # may re-add entries during it, which the drain picks up.
            self._dirty_nodes.clear()
            self._destroyed_tags.clear()
            try:
                self.root = self._reconcile_node(self.root, element)
            except Suspend as signal:
                self._discard_salvage()
                raise self._missing_suspense_error(signal) from None
            self._drain_dirty()
            self._commit()
            self._warn_on_multiple_roots()
        return self.root_view()

    def flush_dirty(self) -> Any:
        """Re-render only the components whose state changed, then commit.

        This is the hot path for state-driven updates: each dirty
        component re-runs its own body and reconciles its subtree in
        place; the batch commits as one native transaction. Returns the
        (possibly replaced) root native view.
        """
        if self.root is None:
            return None
        if self._rendering:
            self._render_queued = True
            return self.root_view()
        if not self._has_dirty_work():
            return self.root_view()
        with self._pass():
            self._destroyed_tags.clear()
            self._drain_dirty()
            self._commit()
        return self.root_view()

    def unmount(self) -> None:
        """Tear down the mounted tree, running effect cleanups and destroying native views."""
        root = self.root
        if root is None:
            return
        self._destroy_tree(root)
        self.root = None
        self._dirty_nodes.clear()
        self._dirty_boundaries.clear()
        self._dirty_suspense.clear()
        self._back_handlers.clear()
        self.transitions.clear()
        self._flush_ops()

    def dispatch_command(self, tag: Optional[int], name: str, args: Optional[Dict[str, Any]] = None) -> Any:
        """Run an imperative command against the view registered under ``tag``."""
        if tag is None:
            return None
        return self.backend.command(tag, name, args or {})

    def dispatch_back_press(self) -> bool:
        """Offer the system back action to registered handlers, newest first.

        Returns ``True`` if a handler consumed the event (the platform
        should not run its default behavior).
        """
        for handler in reversed(list(self._back_handlers)):
            if handler():
                return True
        return False

    def reset_hook_signatures(self) -> None:
        """Forget recorded hook-order signatures across the whole tree (Fast Refresh)."""

        def walk(node: VNode) -> None:
            if node.hook_state is not None:
                node.hook_state.reset_hook_signature()
            for child in node.children:
                walk(child)

        if self.root is not None:
            walk(self.root)

    def walk(self) -> Iterator[VNode]:
        """Yield every mounted node in depth-first, document order."""
        stack = [self.root] if self.root is not None else []
        while stack:
            node = stack.pop()
            yield node
            stack.extend(reversed(node.children))

    # ------------------------------------------------------------------
    # RenderOwner protocol (called by hooks)
    # ------------------------------------------------------------------

    def mark_dirty(self, vnode: VNode) -> None:
        """Queue ``vnode`` (a component) for a local re-render on the next flush."""
        if vnode is None or vnode.hook_state is None or not vnode.mounted:
            return
        self._dirty_nodes[id(vnode)] = vnode

    def request_render(self) -> None:
        """Ask for a flush: via the host callback when set, inline otherwise."""
        if self._rendering:
            self._render_queued = True
            return
        if self.on_render_requested is not None:
            self.on_render_requested()
        else:
            self.flush_dirty()

    def register_back_handler(self, handler: Callable[[], bool]) -> Callable[[], None]:
        """Register a back-press handler; returns an unregister callable."""
        self._back_handlers.append(handler)
        if len(self._back_handlers) == 1 and self.on_back_registered is not None:
            self.on_back_registered()

        def unregister() -> None:
            try:
                self._back_handlers.remove(handler)
            except ValueError:
                pass

        return unregister

    # ------------------------------------------------------------------
    # Pass bookkeeping
    # ------------------------------------------------------------------

    @contextmanager
    def _pass(self) -> Iterator[None]:
        """Mark a pass in flight and drain renders requested during it."""
        if self._rendering:
            self._render_queued = True
            yield
            return
        self._rendering = True
        try:
            yield
            passes = 0
            while self._render_queued and self.root is not None:
                self._render_queued = False
                if not self._has_dirty_work():
                    continue
                passes += 1
                if passes > _MAX_RENDERS_PER_PASS:
                    raise RuntimeError(
                        "Too many re-renders: a component keeps requesting updates while committing "
                        "(for example an effect that sets state unconditionally)."
                    )
                self._destroyed_tags.clear()
                self._drain_dirty()
                self._commit()
        finally:
            self._rendering = False
            self._render_queued = False

    def _has_dirty_work(self) -> bool:
        return bool(self._dirty_nodes or self._dirty_boundaries or self._dirty_suspense)

    def _drain_dirty(self) -> None:
        """Process dirty components and boundary retries until none remain."""
        guard = 0
        while self._has_dirty_work():
            guard += 1
            if guard > 100:
                diagnostics.warn(
                    "Update loop did not settle after 100 iterations; a component is "
                    "likely setting state unconditionally during render or effects."
                )
                self._dirty_nodes.clear()
                self._dirty_boundaries.clear()
                self._dirty_suspense.clear()
                return

            boundaries = list(self._dirty_boundaries.values())
            self._dirty_boundaries.clear()
            for boundary in boundaries:
                if boundary.mounted:
                    with self._providers_above(boundary):
                        self._local_update(
                            boundary, partial(self._reconcile_error_boundary, boundary, boundary.element)
                        )

            suspended = list(self._dirty_suspense.values())
            self._dirty_suspense.clear()
            for node in suspended:
                if node.mounted and node.suspense_showing_fallback:
                    with self._providers_above(node):
                        try:
                            self._local_update(node, partial(self._attempt_suspense_content, node))
                        except Exception as exc:
                            self._route_error(node, exc)

            pending = sorted(self._dirty_nodes.values(), key=VNode.depth)
            self._dirty_nodes.clear()
            for vnode in pending:
                hs = vnode.hook_state
                if not vnode.mounted or hs is None or not hs._dirty:
                    continue  # already covered by a dirty ancestor's pass
                try:
                    self._update_component(vnode)
                except Suspend as signal:
                    self._route_suspend(vnode, signal)
                except Exception as exc:
                    self._route_error(vnode, exc)

    def _commit(self) -> None:
        """Apply the staged transaction and run the post-commit phases."""
        self._flush_ops()
        self._fix_tree_links()
        self._run_layout()
        self._flush_ops()
        self._dispatch_layout_events()
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
        for node in created:
            if not node.mounted or node.tag is None:
                continue
            node.native_view = self.backend.resolve_view(node.tag)
            self._attach_ref(node.element, node.native_view, node.tag)

    def _fix_tree_links(self) -> None:
        """Refresh ``parent`` links and delegated wrapper identity across the tree."""
        if self.root is None:
            return
        self.root.parent = None
        self._fix_node_links(self.root)

    def _fix_node_links(self, node: VNode) -> None:
        for child in node.children:
            child.parent = node
            self._fix_node_links(child)
        if not node.is_native:
            self._refresh_identity(node)

    def _flush_layout_effects(self) -> None:
        if self.root is not None:
            self._walk_effects(self.root, layout=True)

    def _flush_passive_effects(self) -> None:
        if self.root is not None:
            self._walk_effects(self.root, layout=False)

    def _walk_effects(self, node: VNode, layout: bool) -> None:
        for child in node.children:
            self._walk_effects(child, layout)
        hs = node.hook_state
        if hs is not None:
            if layout:
                hs.flush_layout_effects()
            else:
                hs.flush_pending_effects()

    # ------------------------------------------------------------------
    # Tree creation
    # ------------------------------------------------------------------

    def _create_tree(self, element: Element) -> VNode:
        type_obj = element.type
        if isinstance(type_obj, str):
            return self._create_native(element)
        if isinstance(type_obj, Component):
            return self._create_component(element)
        if isinstance(type_obj, Context):
            return self._create_provider(element)
        if type_obj is ERROR_BOUNDARY:
            return self._create_error_boundary(element)
        if type_obj is SUSPENSE:
            return self._create_suspense(element)
        if type_obj is FRAGMENT:
            return self._create_wrapper(element, "Fragment")
        raise TypeError(
            f"Unsupported element type {type_obj!r}. Element types are native view names, "
            "@component functions, contexts (providers), or the structural types."
        )

    def _create_native(self, element: Element) -> VNode:
        tag = next_tag()
        clean_props, events = self._split_props(element.props)
        node = VNode(element, [], tag=tag)
        node.clean_props = clean_props
        if events:
            self._events.set_events(tag, events)
        self._ops.append(CreateOp(tag, element.type, clean_props))
        self._created.append(node)

        index = 0
        try:
            for child_el in normalize_children(element.children, owner=element.type):
                child = self._create_tree(child_el)
                child.parent = node
                node.children.append(child)
                for root in self._native_roots(child):
                    if root.tag is not None:
                        self._ops.append(InsertOp(tag, root.tag, index))
                        index += 1
        except Suspend:
            # Don't leak the container (and already-built siblings) when
            # a child suspends; hook states are salvaged for the retry.
            if self._suspense_salvage is None:
                self._suspense_salvage = {}
            self._destroy_tree(node, salvage=self._suspense_salvage)
            raise
        except Exception:
            self._destroy_tree(node)
            raise
        return node

    def _create_component(self, element: Element) -> VNode:
        # A retrying Suspense boundary may have preserved this
        # component's hook state from the attempt that suspended;
        # reclaiming it keeps cached resources warm.
        hook_state = self._take_hydrated_hook_state(element) or HookState()
        rendered = self._render_component_body(hook_state, element)
        try:
            children = self._create_child_list(rendered)
        except Suspend:
            # The body rendered fine but a descendant suspended: salvage
            # this component's own state too, so the retry re-adopts it.
            if self._suspense_salvage is None:
                self._suspense_salvage = {}
            self._suspense_salvage.setdefault((id(element.type), element.key), []).append(hook_state)
            raise
        node = VNode(element, children)
        for child in children:
            child.parent = node
        node.hook_state = hook_state
        node.rendered = rendered
        self._refresh_identity(node)
        hook_state.vnode = node
        hook_state.owner = self
        return node

    def _create_provider(self, element: Element) -> VNode:
        context: Context = element.type
        context._push(element.props.get("value"))
        try:
            children = self._create_child_list(
                normalize_children(element.children, owner=self._provider_label(context))
            )
        finally:
            context._pop()
        node = VNode(element, children)
        for child in children:
            child.parent = node
        self._refresh_identity(node)
        return node

    def _create_wrapper(self, element: Element, owner: str) -> VNode:
        children = self._create_child_list(normalize_children(element.children, owner=owner))
        node = VNode(element, children)
        for child in children:
            child.parent = node
        self._refresh_identity(node)
        return node

    def _create_child_list(self, elements: List[Element]) -> List[VNode]:
        """Create nodes for ``elements``, cleaning up on mid-list failure.

        When the failure is a ``Suspend``, already-built siblings are
        torn down with their hook states *salvaged*, so the boundary's
        retry re-mounts them with their caches intact.
        """
        nodes: List[VNode] = []
        try:
            for el in elements:
                nodes.append(self._create_tree(el))
        except Suspend:
            if self._suspense_salvage is None:
                self._suspense_salvage = {}
            for node in nodes:
                self._destroy_tree(node, salvage=self._suspense_salvage)
            raise
        except Exception:
            for node in nodes:
                self._destroy_tree(node)
            raise
        return nodes

    # ------------------------------------------------------------------
    # Component bodies
    # ------------------------------------------------------------------

    def _render_component_body(self, hook_state: HookState, element: Element) -> List[Element]:
        """Run a component's function with hook state installed and normalize its output.

        ``async def`` bodies are driven synchronously as far as they can
        go (see [`CoroDriver`][pythonnative.suspense.CoroDriver]); if
        the body blocks on pending work, ``Suspend`` propagates,
        annotated with the component's hook state so a Suspense
        boundary can preserve it across retries.
        """
        component: Component = element.type
        label = component.display_name
        hook_state.begin_render(label)
        hook_state.owner = self
        token = install_hook_state(hook_state)
        try:
            rendered = component.render(element)
            if inspect.iscoroutine(rendered):
                rendered = self._drive_async_body(hook_state, label, rendered)
            hook_state.finish_render()
        except Suspend as signal:
            hook_state.abort_render()
            if signal.hook_state is None:
                signal.hook_state = hook_state
            if signal.key is None:
                signal.key = (id(element.type), element.key)
            if not signal.label:
                signal.label = label
            raise
        finally:
            restore_hook_state(token)
            hook_state._dirty = False
        return normalize_children(rendered, owner=label)

    @staticmethod
    def _drive_async_body(hook_state: HookState, label: str, coro: Any) -> Any:
        """Drive an ``async def`` component body, suspending when it blocks.

        A previous in-flight body for the same component is cancelled
        first: only the newest render's coroutine may deliver a tree.
        When the previous attempt finished while the component was
        suspended, its result is consumed instead of re-running the
        body, so bodies awaiting one-shot work make progress.
        """
        prev = hook_state._async_driver
        if prev is not None:
            if prev.done and not prev.cancelled():
                coro.close()
                hook_state._async_driver = None
                hook_state._hook_log = None
                error = prev.exception()
                if error is not None:
                    raise error
                return prev.result()
            if not prev.done:
                prev.cancel()
        driver = CoroDriver(coro)
        hook_state._async_driver = driver
        driver.start()
        if driver.done:
            hook_state._async_driver = None
            if driver.cancelled():
                raise asyncio.CancelledError()
            error = driver.exception()
            if error is not None:
                raise error
            return driver.result()
        raise Suspend(driver, hook_state=hook_state, label=label)

    def _register_component_retry(self, vnode: VNode, signal: Suspend) -> None:
        """Re-render ``vnode`` once the work it suspended on completes.

        Update-time suspensions keep the previous content on screen (no
        fallback flash) and re-run the body when the awaited work is
        done, matching transition semantics.
        """
        hook_state = vnode.hook_state

        def _on_done(_waitable: Any) -> None:
            if not vnode.mounted or vnode.hook_state is not hook_state or hook_state is None:
                return
            hook_state._dirty = True
            self.mark_dirty(vnode)
            schedule_trigger(self.request_render)

        signal.waitable.add_done_callback(_on_done)

    def _update_component(self, vnode: VNode) -> None:
        """Re-run one component's body and reconcile its subtree in place.

        A local update starts in the middle of the tree, so the provider
        chain above the component is re-established before the body
        runs. When the body itself suspends, the previous subtree stays
        on screen and the component re-renders once the awaited work
        completes; suspensions from descendant mounts propagate to the
        caller, which routes them to the nearest Suspense boundary.
        """
        hook_state = vnode.hook_state
        if hook_state is None or not vnode.is_component:
            return

        def work() -> None:
            try:
                rendered = self._render_component_body(hook_state, vnode.element)
            except Suspend as signal:
                if signal.hook_state is hook_state:
                    self._register_component_retry(vnode, signal)
                    return
                raise
            children = self._reconcile_child_list(vnode.children, rendered)
            for child in children:
                child.parent = vnode
            vnode.children = children
            vnode.rendered = rendered
            self._refresh_identity(vnode)
            hook_state.vnode = vnode
            hook_state.owner = self

        with self._providers_above(vnode):
            self._local_update(vnode, work)

    def _local_update(self, node: VNode, work: Callable[[], Any]) -> None:
        """Run ``work`` on ``node`` and repair the surrounding native structure.

        Captures the nearest native container's child tags before the
        work, then refreshes transparent ancestors' delegated identity
        and re-syncs that container's children afterwards, so only the
        moves the update actually caused reach the native side.
        """
        container = self._nearest_native_ancestor(node)
        before = self._flattened_child_tags(container) if container is not None else []
        work()
        current = node.parent
        while current is not None and current is not container:
            self._refresh_identity(current)
            current = current.parent
        if container is not None and container.tag is not None:
            if self._sync_native_children(container.tag, before, self._flattened_child_roots(container)):
                self._mark_layout_dirty(container)

    def _route_error(self, vnode: VNode, exc: BaseException) -> None:
        """Route a local render failure to the nearest ``ErrorBoundary`` ancestor.

        Without an enclosing boundary the exception propagates, exactly
        as it would during a full render.
        """
        node = vnode.parent
        while node is not None:
            if node.is_error_boundary:
                with self._providers_above(node):
                    self._local_update(node, partial(self._activate_boundary, node, exc))
                return
            node = node.parent
        raise exc

    def _route_suspend(self, vnode: VNode, signal: Suspend) -> None:
        """Route a suspension from a local update to the nearest Suspense ancestor.

        The child reconcile that suspended may have left the boundary's
        content partially updated, so the whole content is torn down and
        rebuilt through the fallback-and-retry path (hook states are
        preserved for the retry).
        """
        node = vnode.parent
        while node is not None:
            if node.is_suspense:
                with self._providers_above(node):

                    def work(n: VNode = node) -> None:
                        self._teardown_suspense_content(n)
                        self._suspend_boundary(n, signal)

                    self._local_update(node, work)
                return
            node = node.parent
        self._discard_salvage()
        raise self._missing_suspense_error(signal) from None

    @contextmanager
    def _providers_above(self, vnode: VNode) -> Iterator[None]:
        """Push the provided values of every provider above ``vnode``, outermost first."""
        chain: List[Tuple[Context, Any]] = []
        node = vnode.parent
        while node is not None:
            if node.is_provider:
                chain.append((node.element.type, node.element.props.get("value")))
            node = node.parent
        chain.reverse()
        for context, value in chain:
            context._push(value)
        try:
            yield
        finally:
            for context, _value in reversed(chain):
                context._pop()

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------

    def _reconcile_node(self, old: VNode, new_el: Element) -> VNode:
        if not self._same_type(old.element, new_el):
            new_node = self._create_tree(new_el)
            self._destroy_tree(old)
            return new_node
        if old.is_native:
            return self._reconcile_native(old, new_el)
        if old.is_component:
            return self._reconcile_component(old, new_el)
        if old.is_provider:
            return self._reconcile_provider(old, new_el)
        if old.is_error_boundary:
            return self._reconcile_error_boundary(old, new_el)
        if old.is_suspense:
            return self._reconcile_suspense(old, new_el)
        return self._reconcile_wrapper(old, new_el, "Fragment")

    def _reconcile_native(self, old: VNode, new_el: Element) -> VNode:
        new_clean, events = self._split_props(new_el.props)
        if old.tag is not None:
            self._events.set_events(old.tag, events)
        changed = self._diff_props(old.clean_props, new_clean)
        if changed:
            if old.tag is not None:
                self._ops.append(UpdateOp(old.tag, changed))
            old.measure_cache = None
            if affects_layout(old.element.type, changed):
                self._mark_layout_dirty(old)
        old.clean_props = new_clean

        old_ref = old.element.props.get("ref")
        new_ref = new_el.props.get("ref")
        if old_ref is not new_ref:
            self._clear_ref(old_ref)
            self._attach_ref(new_el, old.native_view, old.tag)

        before = self._flattened_child_tags(old)
        children = self._reconcile_child_list(old.children, normalize_children(new_el.children, owner=new_el.type))
        old.children = children
        for child in children:
            child.parent = old
        old.element = new_el
        if old.tag is not None and self._sync_native_children(old.tag, before, self._flattened_child_roots(old)):
            self._mark_layout_dirty(old)
        return old

    def _reconcile_component(self, old: VNode, new_el: Element) -> VNode:
        if self._can_skip_memoized(old, new_el):
            old.element = new_el
            return old
        hook_state = old.hook_state or HookState()
        rendered = self._render_component_body(hook_state, new_el)
        children = self._reconcile_child_list(old.children, rendered)
        old.children = children
        for child in children:
            child.parent = old
        old.element = new_el
        old.hook_state = hook_state
        old.rendered = rendered
        self._refresh_identity(old)
        hook_state.vnode = old
        hook_state.owner = self
        return old

    def _reconcile_provider(self, old: VNode, new_el: Element) -> VNode:
        context: Context = new_el.type
        old_value = old.element.props.get("value", _MISSING)
        new_value = new_el.props.get("value")
        if self._value_changed(old_value, new_value):
            self._mark_context_consumers(old, context)
        context._push(new_value)
        try:
            children = self._reconcile_child_list(
                old.children, normalize_children(new_el.children, owner=self._provider_label(context))
            )
        finally:
            context._pop()
        old.children = children
        for child in children:
            child.parent = old
        old.element = new_el
        self._refresh_identity(old)
        return old

    def _reconcile_wrapper(self, old: VNode, new_el: Element, owner: str) -> VNode:
        children = self._reconcile_child_list(old.children, normalize_children(new_el.children, owner=owner))
        old.children = children
        for child in children:
            child.parent = old
        old.element = new_el
        self._refresh_identity(old)
        return old

    def _mark_context_consumers(self, provider: VNode, context: Context) -> None:
        """Mark every descendant that read ``context`` for re-render.

        Descent is pruned at nested providers of the same context, since
        their subtrees read the inner (unchanged) value.
        """
        target = id(context)

        def walk(node: VNode) -> None:
            for child in node.children:
                if child.is_provider and child.element.type is context:
                    continue
                hs = child.hook_state
                if hs is not None and target in hs.context_deps:
                    hs._dirty = True
                    self._dirty_nodes[id(child)] = child
                walk(child)

        walk(provider)

    @staticmethod
    def _can_skip_memoized(old: VNode, new_el: Element) -> bool:
        """Whether a memoized component can reuse its last render.

        Requires the component to be memoized, to have rendered before,
        to have no pending state change (``hook_state._dirty``), and
        props that compare equal under its comparator (shallow equality
        by default), children included.
        """
        component: Component = new_el.type
        if not component.memoized or old.rendered is None or old.hook_state is None or old.hook_state._dirty:
            return False
        compare = component.props_equal or shallow_equal_props
        try:
            return bool(compare(old.element.props, new_el.props)) and old.element.children == new_el.children
        except Exception:
            return False

    def _reconcile_child_list(self, old_children: List[VNode], new_children: List[Element]) -> List[VNode]:
        """Match, reconcile, create, and destroy one level of children.

        Keyed children match by key; unkeyed children match by position
        among the unkeyed siblings. Type changes replace the node. This
        pass is purely structural: native attachment order is derived
        afterwards by the nearest native container via
        [`_sync_native_children`][pythonnative.reconciler.core.Reconciler._sync_native_children].

        On failure, any freshly created replacement nodes are destroyed
        before the exception propagates so an enclosing boundary can
        swap in its fallback without leaking native views.
        """
        old_by_key: Dict[Any, VNode] = {}
        old_unkeyed: List[VNode] = []
        for child in old_children:
            if child.element.key is not None:
                old_by_key[child.element.key] = child
            else:
                old_unkeyed.append(child)

        result: List[VNode] = []
        fresh: List[VNode] = []
        used_keys: Set[Any] = set()
        unkeyed_iter = iter(old_unkeyed)
        try:
            for new_el in new_children:
                matched: Optional[VNode] = None
                if new_el.key is not None:
                    matched = old_by_key.get(new_el.key)
                    if matched is not None:
                        used_keys.add(new_el.key)
                else:
                    matched = next(unkeyed_iter, None)

                if matched is None:
                    node = self._create_tree(new_el)
                    fresh.append(node)
                    result.append(node)
                elif not self._same_type(matched.element, new_el):
                    node = self._create_tree(new_el)
                    self._destroy_tree(matched)
                    fresh.append(node)
                    result.append(node)
                else:
                    result.append(self._reconcile_node(matched, new_el))
        except Exception:
            for node in fresh:
                self._destroy_tree(node)
            raise

        for key, node in old_by_key.items():
            if key not in used_keys:
                self._destroy_tree(node)
        for node in unkeyed_iter:
            self._destroy_tree(node)
        return result

    # ------------------------------------------------------------------
    # Destruction
    # ------------------------------------------------------------------

    def _destroy_tree(self, node: VNode, salvage: Optional[HydrationMap] = None) -> None:
        """Tear down a subtree, destroying native views and cleaning hook state.

        Args:
            node: Root of the subtree to destroy.
            salvage: When given (a Suspense boundary is unwinding),
                component hook states move into this map keyed by
                ``(component identity, element key)`` instead of being
                cleaned up, so the boundary's retry can re-adopt them.
        """
        if not node.mounted:
            return
        node.mounted = False
        self._dirty_nodes.pop(id(node), None)
        self._dirty_boundaries.pop(id(node), None)
        self._dirty_suspense.pop(id(node), None)
        if node.suspense_hydration:
            self._dispose_hydration(node.suspense_hydration)
            node.suspense_hydration = None
        hs = node.hook_state
        if hs is not None:
            if salvage is not None and node.is_component:
                salvage.setdefault((id(node.element.type), node.element.key), []).append(hs)
            else:
                hs.cleanup_all_effects()
            hs.detach()
        self._clear_ref(node.element.props.get("ref"))
        for child in node.children:
            self._destroy_tree(child, salvage=salvage)
        if node.is_native and node.tag is not None:
            self._events.clear(node.tag)
            self._ops.append(DestroyOp(node.tag))
            self._destroyed_tags.add(node.tag)
        node.children = []
        node.parent = None
        node.layout_node = None

    # ------------------------------------------------------------------
    # Native structure helpers
    # ------------------------------------------------------------------

    def _native_roots(self, node: VNode) -> List[VNode]:
        """The native views ``node`` contributes to its native parent, in order.

        Native elements contribute themselves, except ``Portal``, whose
        handler self-attaches to a top-level overlay. Transparent
        wrappers contribute the concatenation of their children's roots.
        """
        if node.is_native:
            return [] if node.element.type == "Portal" else [node]
        roots: List[VNode] = []
        for child in node.children:
            roots.extend(self._native_roots(child))
        return roots

    def _flattened_child_roots(self, node: VNode) -> List[VNode]:
        roots: List[VNode] = []
        for child in node.children:
            roots.extend(self._native_roots(child))
        return roots

    def _flattened_child_tags(self, node: VNode) -> List[int]:
        return [root.tag for root in self._flattened_child_roots(node) if root.tag is not None]

    @staticmethod
    def _nearest_native_ancestor(node: VNode) -> Optional[VNode]:
        current = node.parent
        while current is not None:
            if current.is_native:
                return current
            current = current.parent
        return None

    def _refresh_identity(self, node: VNode) -> None:
        """Point a wrapper's ``tag`` / ``native_view`` at its first native root."""
        if node.is_native:
            return
        for root in self._native_roots(node):
            node.tag = root.tag
            node.native_view = root.native_view
            return
        node.tag = None
        node.native_view = None

    def _sync_native_children(self, parent_tag: int, before_tags: List[int], after_roots: List[VNode]) -> bool:
        """Emit the inserts that turn the parent's native child list into ``after_roots``.

        Children destroyed this pass have already had their views torn
        down, so they're dropped from the "before" picture; the
        remaining difference is expressed as the minimal move-aware
        insert sequence (longest-increasing-subsequence based, so a
        keyed reorder of *n* children costs at most *n* minus the
        length of the already-ordered run).

        Returns whether the native child list changed at all.
        """
        surviving = [t for t in before_tags if t not in self._destroyed_tags]
        after_tags = [r.tag for r in after_roots if r.tag is not None]
        if surviving == after_tags:
            return len(surviving) != len(before_tags)
        for tag, index in plan_child_moves(surviving, after_tags):
            self._ops.append(InsertOp(parent_tag, tag, index))
        return True

    def _warn_on_multiple_roots(self) -> None:
        if not diagnostics.is_dev() or self.root is None:
            return
        roots = self._native_roots(self.root)
        if len(roots) > 1:
            diagnostics.warn_once(
                f"The screen root rendered {len(roots)} native views; only the first "
                "is attached to the window. Wrap your root in a View/Column (Portals "
                "are exempt and may appear anywhere).",
                key=f"multi-root:{id(self)}",
            )

    # ------------------------------------------------------------------
    # Props and refs
    # ------------------------------------------------------------------

    @staticmethod
    def _split_props(props: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Callable[..., Any]]]:
        """Strip reconciler-owned keys, then split event callables from native props."""
        if not props:
            return {}, {}
        stripped = {key: value for key, value in props.items() if key not in _RECONCILER_OWNED_PROPS}
        return extract_events(stripped)

    @staticmethod
    def _diff_props(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
        """Return only the props that changed between two clean prop dicts (removed props map to ``None``)."""
        changed: Dict[str, Any] = {}
        for key, new_val in new.items():
            if key not in old:
                changed[key] = new_val
                continue
            old_val = old[key]
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
    def _value_changed(old_value: Any, new_value: Any) -> bool:
        if old_value is _MISSING:
            return True
        if old_value is new_value:
            return False
        try:
            return bool(old_value != new_value)
        except Exception:
            return True

    @staticmethod
    def _attach_ref(element: Element, native_view: Any, tag: Optional[int]) -> None:
        ref = element.props.get("ref")
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

    @staticmethod
    def _provider_label(context: Context) -> str:
        return f"{context.name}.Provider" if context.name else "Provider"

    @staticmethod
    def _log(msg: str) -> None:
        if os.environ.get("PYTHONNATIVE_DEBUG", "").lower() not in {"1", "true", "yes", "on"}:
            return
        try:
            print(f"[PN] reconciler: {msg}", flush=True)
        except Exception:
            pass
