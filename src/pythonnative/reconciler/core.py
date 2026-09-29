"""The [`Reconciler`][pythonnative.reconciler.core.Reconciler]: element trees in, native mutations out.

One reconciler owns a mounted application tree or headless test render.
Logical screens, overlays, and mounted list rows share that tree.
Each pass runs the same phases in order:

1. **Render**: component bodies run for the subtrees that need it,
   producing [`Element`][pythonnative.Element] descriptions. Hook state
   is installed for the duration of each body.
2. **Diff and stage**: elements are compared with the mounted
   [`VNode`][pythonnative.reconciler.VNode] in their slot. Creates,
   prop updates, attach/detach, and destroys are *staged* into an op
   list instead of being applied immediately.
3. **Commit**: the staged ops go to the backend in one batch, refs are
   populated, the layout pass runs (once a viewport is known), then
   effects flush: ``use_layout_effect`` first, ``use_effect`` after. An
   effect that raises is routed to the nearest ``ErrorBoundary``, exactly
   like a render-time exception.

State setters never render inline. [`request_render`][pythonnative.reconciler.core.Reconciler.request_render]
schedules one flush on the application loop with ``call_soon``, so every
setter call within one callback, effect, or task step coalesces into one
pass on every host. A render requested while a pass is in flight (an
effect setting state, a boundary reset) is drained before the pass
returns, so hosts never observe a half-committed tree. A flush that keeps
re-scheduling itself more than ``MAX_RENDER_PASSES`` times raises
``RuntimeError("Too many re-renders")`` from the component that keeps
dirtying itself, routed through the nearest boundary like any render
error.

The class is assembled from mixins to keep each concern readable:
this module holds the render/diff/commit pipeline,
``boundaries`` handles
``ErrorBoundary`` and ``Suspense``, and
``layout_pass`` runs flexbox.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from functools import partial
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Set, Tuple

from .. import diagnostics
from .. import journal as _journal
from ..component import Component
from ..element import ERROR_BOUNDARY, FRAGMENT, SUSPENSE, Element
from ..equality import equal, equal_props
from ..events import extract_events, get_event_registry
from ..hooks import Context, HookState, install_hook_state, provider_environment, restore_hook_state
from ..journal import Journal, JournalDict
from ..mutations import UNSET, CreateOp, DestroyOp, InsertOp, Mutation, UpdateOp
from ..profiling import profiled
from ..runtime import _on_loop_thread, _scope, get_loop
from ..scheduler import TransitionQueue, schedule_trigger
from ..suspense import Suspend, run_eagerly
from .boundaries import BoundaryMixin, HydrationMap
from .children import plan_child_moves
from .layout_pass import LayoutMixin, affects_layout
from .vnode import VNode, next_tag, normalize_children

__all__ = ["MAX_RENDER_PASSES", "Reconciler"]

# Props the reconciler consumes itself and never forwards to the
# native handler. ``ref`` receives an imperative handle after commit,
# mirroring React's ``ref`` semantics.
_RECONCILER_OWNED_PROPS = frozenset({"ref"})

MAX_RENDER_PASSES = 50
"""How many times one flush may re-schedule itself before it is a render storm.

A component that sets state unconditionally in an effect, or a setter
called on every render, keeps the tree dirty forever. After this many
drain iterations inside one flush the reconciler raises
``RuntimeError("Too many re-renders")`` from the offending component
and routes it through the nearest ``ErrorBoundary``.
"""


class Reconciler(BoundaryMixin, LayoutMixin):
    """Owns one mounted tree and translates element diffs into native mutations.

    Args:
        backend: An object implementing the backend protocol
            (``apply_mutations``, ``resolve_view``, ``measure_intrinsic``,
            ``command``). PythonNative ships the bridge backend for iOS,
            Android, and the browser preview; tests use
            [`FakeBackend`][pythonnative.testing.FakeBackend].

    Attributes:
        backend: The backend passed at construction.
        on_render_requested: Optional callback hosts set to be told a
            flush is due (to hop onto the UI thread or guard with a red
            box). It runs on the application loop, one turn after the
            first state change that scheduled it. When ``None`` the
            reconciler calls [`flush_dirty`][pythonnative.reconciler.core.Reconciler.flush_dirty]
            itself; whatever the callback does, it should end up calling
            ``flush_dirty``.
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
        self._tag_nodes: Dict[int, VNode] = JournalDict()
        self._effect_states: Dict[int, HookState] = JournalDict()
        self._native_children: Dict[int, List[int]] = JournalDict()
        self._publications: List[Callable[[], None]] = []
        if hasattr(backend, "subscribe_layout"):
            backend.subscribe_layout(self._accept_native_layout)
        elif hasattr(backend, "on_layout"):
            backend.on_layout = self._accept_native_layout
        self.on_render_requested: Optional[Callable[[], None]] = None
        self.on_back_registered: Optional[Callable[[], None]] = None
        self.transitions = TransitionQueue()

        self._events = get_event_registry()
        self._ops: List[Mutation] = []
        self._created: List[VNode] = []
        self._rendering = False
        self._render_queued = False
        self._pending_future: asyncio.Future[Any] | None = None
        self._commit_iterator: Any = None
        self._pending_journal: Journal | None = None
        self._pending_inputs: list[Callable[[], None]] = []
        self._queued_element: Element | None = None
        self._unmount_requested = False
        self.on_commit: Callable[[], None] | None = None
        self.on_commit_error: Callable[[BaseException], None] | None = None
        self._idle_waiters: list[asyncio.Future[None]] = []
        self._flush_scheduled = False
        # Drain iterations inside the current flush (the render-storm counter).
        self._storm = 0
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
        if self.root is not None or self.commit_pending:
            self.unmount()
        if self.commit_pending:
            self._queued_element = element
            return self.root_view()
        diagnostics.log(f"reconciler: mount {element!r}")
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
        if self._pending_future is not None:
            self._queued_element = element
            return self.root_view()
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

    @profiled("render")
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
        if self._pending_future is not None:
            self._unmount_requested = True
            self._queued_element = None
            return
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
        with self._pass():
            self._commit()

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
        """Schedule one flush on the application loop (automatic batching).

        Never renders inline: every request made during one callback,
        effect, or task step lands in the same ``call_soon`` flush.
        Requests made while a pass is in flight are drained by that
        pass instead.
        """
        if self._rendering:
            self._render_queued = True
            return
        if self._flush_scheduled:
            return
        self._flush_scheduled = True
        loop = get_loop()
        if _on_loop_thread(loop):
            loop.call_soon(self._run_scheduled_flush)
        else:
            loop.call_soon_threadsafe(self._run_scheduled_flush)

    def _run_scheduled_flush(self) -> None:
        self._flush_scheduled = False
        if self.root is None or self._rendering or not self._has_dirty_work():
            if not self._rendering:
                self._settled()
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
        """Mark a pass in flight and drain renders requested during it.

        Python failures roll back the bookkeeping the pass touched and
        propagate, leaving the committed tree in place. Only a commit the
        backend itself rejected retires the surface: native mutations
        can't be undone, so no Python tree may keep targeting partially
        mounted widgets.
        """
        if self._rendering:
            self._render_queued = True
            yield
            return
        self._rendering = True
        self._storm = 0
        journal = Journal()
        token = _journal.install(journal)
        journal.attribute(self, "root")
        try:
            yield
            while self._pending_future is None and self._render_queued and self.root is not None:
                self._render_queued = False
                if not self._has_dirty_work():
                    continue
                self._destroyed_tags.clear()
                self._drain_dirty()
                self._commit()
        except BaseException:
            self._abort_pass(journal)
            raise
        finally:
            _journal.uninstall(token)
            if self._pending_future is None:
                journal.active = False
                self._rendering = False
                self._render_queued = False
            else:
                self._pending_journal = journal

    def _abort_pass(self, journal: Journal) -> None:
        if getattr(self.backend, "_failed", False):
            rejected_nodes = list(self.walk())
            rejected_states = list(self._effect_states.values())
            journal.rollback()
            retired_nodes = rejected_nodes + list(self.walk())
            states = {id(state): state for state in rejected_states}
            for node in retired_nodes:
                if node.hook_state is not None:
                    states[id(node.hook_state)] = node.hook_state
                self._clear_ref(node.element.props.get("ref"))
                if node.tag is not None:
                    self._events.clear(node.tag)
            for state in states.values():
                state.cleanup_all_effects()
                state.detach()
            self.transitions.clear()
            self._back_handlers.clear()
            self._native_children.clear()
            self.root = None
            self._tag_nodes.clear()
            self._effect_states.clear()
        else:
            journal.rollback()
        self._ops.clear()
        self._created.clear()
        self._publications.clear()
        self._dirty_nodes.clear()
        self._dirty_boundaries.clear()
        self._dirty_suspense.clear()
        self._commit_iterator = None
        self._pending_future = None
        self._pending_journal = None

    @property
    def commit_pending(self) -> bool:
        """Whether native acknowledgement is holding the surface's next render."""
        return self._pending_future is not None

    def defer_input(self, callback: Callable[[], None]) -> bool:
        """Queue state writes during mounting, preserving their functional order."""
        if not self.commit_pending:
            return False
        self._pending_inputs.append(callback)
        return True

    async def wait_for_commit(self) -> None:
        """Wait until mounting and its queued state updates have settled."""
        while self.commit_pending or self._has_dirty_work() or self._flush_scheduled:
            waiter = get_loop().create_future()
            self._idle_waiters.append(waiter)
            if not self.commit_pending:
                self.request_render()
            await waiter

    def _settled(self, error: BaseException | None = None) -> None:
        waiters, self._idle_waiters = self._idle_waiters, []
        for waiter in waiters:
            if not waiter.done():
                if error is None:
                    waiter.set_result(None)
                else:
                    waiter.set_exception(error)

    def _drive_commit(self, iterator: Any) -> None:
        for pending in iterator:
            if pending is None:
                continue
            if pending.done():
                pending.result()
                continue
            self._commit_iterator = iterator
            self._pending_future = pending
            self._pending_journal = _journal.current()
            pending.add_done_callback(self._resume_commit, context=_journal.detached_context())
            return
        self._commit_iterator = None

    def _resume_commit(self, future: asyncio.Future[Any]) -> None:
        journal = self._pending_journal
        assert journal is not None
        iterator = self._commit_iterator
        self._pending_future = None
        token = _journal.install(journal)
        error: BaseException | None = None
        try:
            future.result()
            self._drive_commit(iterator)
        except BaseException as exc:
            error = exc
            self._abort_pass(journal)
        finally:
            _journal.uninstall(token)
        if self._pending_future is not None:
            return
        journal.active = False
        self._pending_journal = None
        self._rendering = False
        self._render_queued = False
        inputs, self._pending_inputs = self._pending_inputs, []
        if error is not None:
            if self.on_commit_error is not None:
                self.on_commit_error(error)
            elif not diagnostics.report_error(error, phase="native commit"):
                get_loop().call_exception_handler({"message": "Native commit failed", "exception": error})
            self._settled(error)
        if self._unmount_requested:
            self._unmount_requested = False
            self.unmount()
        if not self.commit_pending and self._queued_element is not None:
            element, self._queued_element = self._queued_element, None
            self.reconcile(element)
        if not getattr(self.backend, "_failed", False):
            for callback in inputs:
                callback()
            if self._has_dirty_work():
                self.request_render()
        self._settled()

    def _has_dirty_work(self) -> bool:
        return bool(self._dirty_nodes or self._dirty_boundaries or self._dirty_suspense)

    def _drain_dirty(self) -> None:
        """Process dirty components and boundary retries until none remain."""
        while self._has_dirty_work():
            self._storm += 1
            if self._storm > MAX_RENDER_PASSES:
                self._fail_render_storm()
                continue

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

    def _fail_render_storm(self) -> None:
        """Raise the render-storm error from the component that keeps dirtying itself.

        The error routes through the nearest ``ErrorBoundary`` above the
        offender (whose subtree is replaced by the fallback) and
        propagates to the host when there is none.
        """
        candidates = (
            list(self._dirty_nodes.values())
            or list(self._dirty_boundaries.values())
            or list(self._dirty_suspense.values())
        )
        offender = min(candidates, key=VNode.depth) if candidates else None
        label = offender.label if offender is not None else "A component"
        exc = RuntimeError(
            f"Too many re-renders: {label} keeps requesting updates while committing (for example an "
            "effect that sets state unconditionally, or a state setter called during render)."
        )
        self._dirty_nodes.clear()
        self._dirty_boundaries.clear()
        self._dirty_suspense.clear()
        self._storm = 0
        if offender is None:
            raise exc
        self._route_error(offender, exc)

    def _commit(self) -> None:
        self._drive_commit(self._commit_steps())

    def _commit_steps(self) -> Iterator[asyncio.Future[Any] | None]:
        """Apply the staged transaction and run the post-commit phases.

        Effects run per component; one that raises is routed to the
        nearest ``ErrorBoundary`` and the resulting fallback is committed
        in a nested commit, so the rest of the tree is unaffected.
        """
        yield self._flush_ops()
        self._run_layout()
        yield self._flush_ops()
        journal = _journal.current()
        if journal is not None:
            journal.accept()
            journal.attribute(self, "root")
        self._publish()
        self._dispatch_layout_events()
        routed = self._flush_layout_effects()
        yield self._flush_ops()
        routed = self._flush_passive_effects() or routed
        yield self._flush_ops()
        if routed:
            yield from self._commit_steps()

        if self.on_commit is not None:
            self.on_commit()
        release = getattr(self.backend, "release_events", None)
        if release is not None:
            release()
        self._settled()

    def _publish(self) -> None:
        publications, self._publications = self._publications, []
        for publish in publications:
            publish()

    @profiled("commit")
    def _flush_ops(self) -> asyncio.Future[Any] | None:
        """Send pending ops to the backend and resolve created views."""
        ops = self._ops
        created = self._created
        if ops:
            prepare_layout = getattr(self.backend, "prepare_layout", None)
            if prepare_layout is not None:
                roots = [node.tag for node in self._native_roots(self.root)] if self.root is not None else []
                prepare_layout(roots, *self._viewport_size)
            pending = self.backend.apply_mutations(ops)
            self._ops = []
            self._created = []
            if pending is not None:
                done = get_loop().create_future()

                def resolve(future: asyncio.Future[Any]) -> None:
                    try:
                        future.result()
                        self._resolve_created(created)
                        if not done.done():
                            done.set_result(None)
                    except BaseException as error:
                        if not done.done():
                            done.set_exception(error)

                pending.add_done_callback(resolve, context=_journal.detached_context())
                return done
        elif created:
            self._created = []
        self._resolve_created(created)
        return None

    def _resolve_created(self, created: list[VNode]) -> None:
        for node in created:
            if not node.mounted or node.tag is None:
                continue
            node.native_view = self.backend.resolve_view(node.tag)
            self._publications.append(partial(self._attach_ref, node.element, node.tag))
            ancestor = node.parent
            scope = None
            while ancestor is not None:
                if scope is None and ancestor.hook_state is not None:
                    scope = ancestor.hook_state.task_scope
                if not ancestor.is_native:
                    self._refresh_identity(ancestor)
                ancestor = ancestor.parent
            self._publications.append(partial(self._events.set_scope, node.tag, scope))

    def _flush_layout_effects(self) -> bool:
        """Run queued layout effects; returns whether a failure activated a boundary."""
        routed = False
        for state in sorted(
            self._effect_states.values(), key=lambda hs: hs.vnode.depth() if hs.vnode else 0, reverse=True
        ):
            if state.vnode is not None and state.vnode.mounted:
                try:
                    state.flush_layout_effects()
                except Exception as exc:
                    self._route_error(state.vnode, exc)
                    routed = True
        return routed

    def _flush_passive_effects(self) -> bool:
        """Run queued passive effects; returns whether a failure activated a boundary."""
        routed = False
        states, self._effect_states = self._effect_states, JournalDict()
        for state in sorted(states.values(), key=lambda hs: hs.vnode.depth() if hs.vnode else 0, reverse=True):
            if state.vnode is not None and state.vnode.mounted:
                try:
                    state.flush_pending_effects()
                except Exception as exc:
                    self._route_error(state.vnode, exc)
                    routed = True
        return routed

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
        self._tag_nodes[tag] = node
        node.clean_props = clean_props
        if events:
            self._publications.append(partial(self._events.set_events, tag, events))
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
        self._native_children[tag] = self._flattened_child_tags(node)
        return node

    def _create_component(self, element: Element) -> VNode:
        # A retrying Suspense boundary may have preserved this
        # component's hook state from the attempt that suspended;
        # reclaiming it keeps cached resources warm.
        hook_state = self._take_hydrated_hook_state(element) or HookState()
        journal = _journal.current()
        if journal is not None and hook_state.owner is None:
            journal.undo.append(hook_state.cleanup_all_effects)
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

    @profiled("component", lambda self, hook_state, element: {"component": element.type.display_name})
    def _render_component_body(self, hook_state: HookState, element: Element) -> List[Element]:
        """Render synchronously or suspend on a real, component-owned task.

        An ``async def`` body is stepped eagerly: its first step runs
        right here, and only when the first ``await`` is actually
        pending does the remainder become a task the component owns, at
        which point the render suspends on it.
        """
        from ..profiling import count

        count("components.rendered")
        journal = _journal.current()
        if journal is not None:
            for name in HookState.__slots__:
                journal.attribute(hook_state, name)
        self._effect_states[id(hook_state)] = hook_state
        component: Component = element.type
        label = component.display_name
        hook_state.owner = self
        if component.is_async:
            previous = hook_state._async_task
            inputs = (element.props, element.children, provider_environment())
            if previous is not None and not equal(hook_state._async_inputs, inputs):
                # Retire accepted work only after its replacement commits.
                # A later sibling can still reject this render pass.
                self._publications.append(previous.cancel)
                previous = hook_state._async_task = None
            if previous is None:

                async def render_body() -> Any:
                    hook_state.begin_render(label)
                    token = install_hook_state(hook_state)
                    try:
                        result = await component.render(element)
                        hook_state.finish_render()
                        return result
                    except BaseException:
                        hook_state.abort_render()
                        raise
                    finally:
                        restore_hook_state(token)

                previous = run_eagerly(render_body(), hook_state.task_scope)
                if journal is not None and journal.active:
                    journal.undo.append(previous.cancel)
                hook_state._async_task = previous
                hook_state._async_inputs = inputs
            if not previous.done():
                signal = Suspend(previous, hook_state=hook_state, label=label)
                signal.key = (id(element.type), element.key)
                raise signal
            hook_state._async_task = None
            hook_state._dirty = False
            return normalize_children(previous.result(), owner=label, dynamic=True)

        hook_state.begin_render(label)
        token = install_hook_state(hook_state)
        scope_token = _scope.set(hook_state.task_scope)
        try:
            rendered = component.render(element)
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
        except BaseException:
            hook_state.abort_render()
            raise
        finally:
            _scope.reset(scope_token)
            restore_hook_state(token)
            hook_state._dirty = False
        return normalize_children(rendered, owner=label, dynamic=True)

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
            try:
                children = self._reconcile_child_list(vnode.children, rendered)
            except Suspend:
                # The retry must re-run this body: its output was never adopted.
                hook_state._dirty = True
                raise
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
        before_roots = [root.tag for root in self._native_roots(node)]
        container = self._nearest_native_ancestor(node)
        before = self._native_children.get(container.tag, []) if container is not None else []
        work()
        current = node.parent
        while current is not None and current is not container:
            self._refresh_identity(current)
            current = current.parent
        after_roots = [root.tag for root in self._native_roots(node)]
        if before_roots == after_roots:
            return
        if container is not None and container.tag is not None:
            if self._sync_native_children(container.tag, before, self._flattened_child_roots(container)):
                self._mark_layout_dirty(container)

    def _route_error(self, vnode: VNode, exc: BaseException) -> None:
        """Route a render or effect failure to the nearest ``ErrorBoundary`` ancestor.

        Without an enclosing boundary the exception propagates, exactly
        as it would during a full render.
        """
        node = vnode.parent
        while node is not None:
            if node.is_error_boundary:
                try:
                    with self._providers_above(node):
                        self._local_update(node, partial(self._activate_boundary, node, exc))
                except Exception as escaped:
                    # A boundary without a fallback (or whose fallback failed)
                    # hands the error to the next boundary up.
                    exc = escaped
                else:
                    return
            node = node.parent
        raise exc

    def _route_suspend(self, vnode: VNode, signal: Suspend) -> None:
        """Route a suspension from a local update to the nearest Suspense ancestor.

        The boundary keeps its committed content mounted but hidden,
        shows its fallback beside it, and retries the content in place
        when the pending work settles, so sibling views, hook state,
        focus, and scroll position all survive.
        """
        node = vnode.parent
        while node is not None:
            if node.is_suspense:
                try:
                    with self._providers_above(node):
                        self._local_update(node, partial(self._hide_suspense_content, node, signal))
                except Suspend as escaped:
                    signal = escaped  # a boundary without a fallback is transparent
                else:
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
            self._publications.append(partial(self._events.set_events, old.tag, events))
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
            self._publications.append(partial(self._clear_ref, old_ref))
            self._publications.append(partial(self._attach_ref, new_el, old.tag))

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
        try:
            children = self._reconcile_child_list(old.children, rendered)
        except Suspend:
            hook_state._dirty = True
            raise
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
        new_value = new_el.props.get("value")
        if "value" not in old.element.props or not equal(old.element.props["value"], new_value):
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
        props that compare equal under its comparator (the framework
        [`equality`][pythonnative.equality] rule by default), children
        included.
        """
        component: Component = new_el.type
        if not component.memoized or old.rendered is None or old.hook_state is None or old.hook_state._dirty:
            return False
        compare = component.props_equal or equal_props
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
        swap in its fallback without leaking native views. When the
        failure is a ``Suspend`` their hook states are salvaged for the
        boundary's retry.
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
        except Suspend:
            if self._suspense_salvage is None:
                self._suspense_salvage = {}
            for node in fresh:
                self._destroy_tree(node, salvage=self._suspense_salvage)
            raise
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
        node.suspense_hidden = None
        hs = node.hook_state
        if hs is not None:
            self._effect_states.pop(id(hs), None)
            if salvage is not None and node.is_component:
                salvage.setdefault((id(node.element.type), node.element.key), []).append(hs)
            else:
                self._publications.append(hs.cleanup_all_effects)
            self._publications.append(hs.detach)
        self._publications.append(partial(self._clear_ref, node.element.props.get("ref")))
        for child in node.children:
            self._destroy_tree(child, salvage=salvage)
        if node.is_native and node.tag is not None:
            self._native_children.pop(node.tag, None)
            self._tag_nodes.pop(node.tag, None)
            self._publications.append(partial(self._events.clear, node.tag))
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
        self._native_children[parent_tag] = [root.tag for root in after_roots if root.tag is not None]
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
    def _split_props(props: Mapping[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Callable[..., Any]]]:
        """Strip reconciler-owned keys, then split event callables from native props.

        ``Animated.event`` callbacks additionally publish their node
        bindings under ``_pn_animated_events`` so the native animator can
        drive the bound values without a Python round trip.
        """
        if not props:
            return {}, {}
        stripped = {
            key: value for key, value in props.items() if key not in _RECONCILER_OWNED_PROPS and value is not UNSET
        }
        clean, events = extract_events(stripped)
        from ..animated import AnimatedEvent

        bindings = {
            name: {field: id(value) for field, value in callback._bindings.items()}
            for name, callback in events.items()
            if isinstance(callback, AnimatedEvent)
        }
        if bindings:
            clean["_pn_animated_events"] = bindings
        if props.get("ref") is not None or "on_layout" in events:
            clean["_pn_layout"] = True
        return clean, events

    @staticmethod
    def _diff_props(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
        """Return only the props that changed between two clean prop dicts.

        Values compare under the framework [`equality`][pythonnative.equality]
        rule; removed props map to ``UNSET``.
        """
        changed: Dict[str, Any] = {}
        for key, new_val in new.items():
            if key not in old or not equal(old[key], new_val):
                changed[key] = new_val
        for key in old:
            if key not in new:
                changed[key] = UNSET
        return changed

    def _attach_ref(self, element: Element, tag: Optional[int]) -> None:
        """Publish the typed imperative handle for a native element on its ``ref``."""
        ref = element.props.get("ref")
        if ref is None:
            return
        if hasattr(ref, "current"):
            from ..handles import make_handle

            handle = make_handle(element.type, tag, self.backend)
            node = self._tag_nodes.get(tag) if tag is not None else None
            if node is not None and node.last_frame is not None:
                self._publish_frame_to_handle(handle, node.last_frame)
            ref.current = handle
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
