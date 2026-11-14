"""The [`Reconciler`][pythonnative.reconciler.core.Reconciler]: element trees in, native mutations out.

One reconciler owns a mounted application tree or headless test render.
Logical screens, overlays, and mounted list rows share that tree.
Each pass runs the same phases in order:

1. **Render**: component bodies run for the subtrees that need it,
   producing [`Element`][pythonnative.Element] descriptions. Hook state
   is installed for the duration of each body.
2. **Diff and stage**: elements are compared with the mounted
   [`VNode`][pythonnative.reconciler.VNode] in their slot, and the
   committed tree is updated in place. Creates, prop updates, child
   moves, and destroys are *staged* into an op list instead of being
   applied immediately. Every node is recorded in the render journal
   before its first change, so a pass that fails or is preempted rolls
   back to the committed tree.
3. **Commit**: the staged ops go to the backend in one batch, refs are
   populated, the layout pass runs (once a viewport is known), then
   effects flush: ``use_layout_effect`` first, ``use_effect`` after. An
   effect that raises is routed to the nearest ``ErrorBoundary``, exactly
   like a render-time exception.

Child lists follow React's identity rule (RFC 0010): each entry of a
child list occupies a slot, ``None`` and ``False`` keep their slot empty,
and a list is a group whose items are matched among themselves. A keyed
element matches the old child with the same key; an unkeyed one matches
the old unkeyed child in the same slot. A list that keeps its shape is
updated in place without building any lookup tables, and native child
order is recomputed only for containers whose children were created,
destroyed, moved, or replaced.

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

Updates marked as transitions render in a pass of their own after urgent
work. Until that pass flushes its first mutation, it checks for queued
urgent input before each component body; when input is waiting, it rolls
back, the input is handled and committed, and the transition renders
again.

The class is assembled from mixins to keep each concern readable:
this module holds the render/diff/commit pipeline,
``boundaries`` handles
``ErrorBoundary`` and ``Suspense``, and
``layout_pass`` runs flexbox.
"""

from __future__ import annotations

import asyncio
import weakref
from contextlib import contextmanager
from functools import partial
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Sequence, Set, Tuple

from .. import diagnostics
from .. import journal as _journal
from .. import profiling as _profiling
from ..component import Component
from ..element import STRICT_MODE, Element, type_label
from ..equality import equal, equal_props
from ..errors import add_component_frame, complete_component_stack
from ..events import EVENTS_PROP, extract_events, get_event_registry
from ..hooks import Context, HookState, install_hook_state, provider_environment, restore_hook_state
from ..journal import Journal, JournalDict
from ..mutations import UNSET, CreateOp, DestroyOp, InsertOp, Mutation, UpdateOp
from ..profiling import profiled
from ..runtime import _on_loop_thread, _scope, get_loop
from ..scheduler import TransitionQueue, schedule_trigger, urgent_context, urgent_input_pending
from ..style import MOTION_STYLE_KEY
from ..suspense import Suspend, run_eagerly
from .boundaries import BoundaryMixin, HydrationMap
from .children import plan_child_moves
from .layout_pass import LayoutMixin
from .vnode import (
    BOUNDARY,
    COMPONENT,
    NATIVE,
    PROVIDER,
    SUSPENSE_KIND,
    WRAPPER,
    VNode,
    child_slots,
    kind_of,
    next_tag,
    touch,
)

__all__ = ["MAX_RENDER_PASSES", "Preempted", "Reconciler"]

_MOTION_PROPS = ("entering", "exiting", "layout", "shared_transition", "item_entering", "item_exiting", "item_layout")

# Props that take the general path (``_split_props``): the reconciler owns
# ``ref``, the core reports layout for ``on_layout``, gesture and refresh
# callbacks are nested in their prop, and motion props are encoded for
# the core.
_SPECIAL_PROPS = frozenset({"ref", "on_layout", "gestures", "refresh_control", MOTION_STYLE_KEY, *_MOTION_PROPS})
_WORKLET_MARK = "__pn_worklet__"
_MISSING = object()
_PLAIN_VALUES = frozenset({str, int, float, bool, type(None)})

MAX_RENDER_PASSES = 50
"""How many times one flush may re-schedule itself before it is a render storm.

A component that sets state unconditionally in an effect, or a setter
called on every render, keeps the tree dirty forever. After this many
drain iterations inside one flush the reconciler raises
``RuntimeError("Too many re-renders")`` from the offending component
and routes it through the nearest ``ErrorBoundary``.
"""


def _effect_depth(state: HookState) -> int:
    node = state.vnode
    depth = 0
    while node is not None:
        depth += 1
        node = node.parent
    return depth


class Preempted(BaseException):
    """Raised inside a transition pass when urgent input is waiting; the pass rolls back.

    Derives from :class:`BaseException` so neither error boundaries nor
    application code catch it.
    """


class Reconciler(BoundaryMixin, LayoutMixin):
    """Owns one mounted tree and translates element diffs into native mutations.

    Args:
        backend: An object implementing the backend protocol
            (``apply_mutations``, ``resolve_view``, ``compute_layout``,
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
        transitions: The components with updates waiting for this
            reconciler's transition pass; owned per reconciler so screens
            never delay each other.
    """

    def __init__(self, backend: Any) -> None:
        self.backend = backend
        self.root: Optional[VNode] = None
        self._tag_nodes: Dict[int, VNode] = JournalDict()
        # Hook states rendered since the last commit; empty between passes,
        # so a rolled-back pass simply clears it.
        self._effect_states: Dict[int, HookState] = {}
        # The tags each native container has attached, in order.
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
        # Native containers whose attached children may no longer match
        # their child list, keyed by ``id``; synced before each flush.
        self._stale: Dict[int, VNode] = {}
        self._rendering = False
        self._render_queued = False
        # Whether the pass in progress yields to urgent input (a
        # transition pass, until its first flush).
        self._preemptible = False
        self._transition_pass = False
        # How many StrictMode wrappers enclose the subtree being rendered.
        self._strict = 0
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
            # Dirty components stay queued: the pass may skip an unchanged
            # subtree, and the drain skips any component the pass rendered.
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
        """Render what's waiting, then commit: urgent updates first, then a transition.

        This is the hot path for state-driven updates: each dirty
        component re-runs its own body and reconciles its subtree in
        place; the batch commits as one native transaction. When no
        urgent update is waiting, the queued transition updates render
        in a preemptible pass. Returns the (possibly replaced) root
        native view.
        """
        if self.root is None:
            return None
        if self._rendering:
            self._render_queued = True
            return self.root_view()
        if self._has_dirty_work():
            with self._pass():
                self._destroyed_tags.clear()
                self._drain_dirty()
                self._commit()
        elif self.transitions.pending:
            self._render_transition()
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
        self._stale.clear()
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
        self._schedule_flush()

    def request_transition(self) -> None:
        """Schedule a flush that renders the queued transition updates after any urgent work."""
        if self._rendering:
            # The pass in flight schedules the transition when it ends.
            return
        self._schedule_flush()

    def _schedule_flush(self) -> None:
        if self._flush_scheduled:
            return
        self._flush_scheduled = True
        loop = get_loop()
        # A flush starts from a clean context: the caller may be inside a
        # transition, a batch, or a render.
        if _on_loop_thread(loop):
            loop.call_soon(self._run_scheduled_flush, context=urgent_context())
        else:
            loop.call_soon_threadsafe(self._run_scheduled_flush, context=urgent_context())

    def _run_scheduled_flush(self) -> None:
        self._flush_scheduled = False
        if self.root is None or self._rendering or not (self._has_dirty_work() or self.transitions.pending):
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
    # Transitions
    # ------------------------------------------------------------------

    def _render_transition(self) -> None:
        """Apply the queued transition updates and render them in a preemptible pass."""
        transitions = self.transitions
        preemptible = not transitions.must_finish(get_loop().time())
        if preemptible and urgent_input_pending():
            # Input is already on its way to the loop; let it run first.
            self._schedule_flush()
            return
        try:
            with self._pass(preemptible=preemptible, transition=True):
                self._destroyed_tags.clear()
                journal = _journal.active
                for hook_state in transitions.take():
                    if journal is not None and hook_state._journal_stamp != journal.identity:
                        journal.record(hook_state)
                    vnode = hook_state.vnode
                    if hook_state.apply_transition_updates() and vnode is not None and vnode.mounted:
                        self._dirty_nodes[id(vnode)] = vnode
                self._drain_dirty()
                self._commit()
        except Preempted:
            transitions.preempted()
            _profiling.count("transitions.preempted")
            diagnostics.log(f"reconciler: transition preempted ({transitions.preemptions})")
            self._schedule_flush()

    # ------------------------------------------------------------------
    # Pass bookkeeping
    # ------------------------------------------------------------------

    @contextmanager
    def _pass(self, preemptible: bool = False, transition: bool = False) -> Iterator[None]:
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
        self._preemptible = preemptible
        self._transition_pass = transition
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
            self._preemptible = False
            if self._pending_future is None:
                journal.active = False
                self._rendering = False
                self._render_queued = False
                self._pass_finished()
            else:
                self._pending_journal = journal

    def _pass_finished(self) -> None:
        """After a pass settles: reset the counters of a committed transition, and schedule any transition waiting."""
        if self._transition_pass:
            self._transition_pass = False
            self.transitions.committed()
        if self.transitions.pending and self.root is not None:
            self._schedule_flush()

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
        self._effect_states.clear()
        self._stale.clear()
        self._dirty_nodes.clear()
        self._dirty_boundaries.clear()
        self._dirty_suspense.clear()
        self._strict = 0
        # A rolled-back transition didn't commit: keep its starvation counters.
        self._transition_pass = False
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
        while self.commit_pending or self._has_dirty_work() or self._flush_scheduled or self.transitions.pending:
            waiter = get_loop().create_future()
            self._idle_waiters.append(waiter)
            if not self.commit_pending:
                self._schedule_flush()
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
        if not self._rendering:
            self._pass_finished()
        self._settled()

    def _has_dirty_work(self) -> bool:
        return bool(self._dirty_nodes or self._dirty_boundaries or self._dirty_suspense)

    def _drain_dirty(self) -> None:
        """Process dirty components and boundary retries until none remain."""
        while self._dirty_nodes or self._dirty_boundaries or self._dirty_suspense:
            self._storm += 1
            if self._storm > MAX_RENDER_PASSES:
                self._fail_render_storm()
                continue

            if self._dirty_boundaries:
                boundaries = list(self._dirty_boundaries.values())
                self._dirty_boundaries.clear()
                for boundary in boundaries:
                    if boundary.mounted:
                        with self._providers_above(boundary):
                            self._reconcile_error_boundary(boundary, boundary.element)

            if self._dirty_suspense:
                suspended = list(self._dirty_suspense.values())
                self._dirty_suspense.clear()
                for node in suspended:
                    if node.mounted and node.suspense_showing_fallback:
                        with self._providers_above(node):
                            try:
                                self._attempt_suspense_content(node)
                            except Exception as exc:
                                self._route_error(node, exc)

            if not self._dirty_nodes:
                continue
            pending = list(self._dirty_nodes.values())
            self._dirty_nodes.clear()
            if len(pending) > 1:
                pending.sort(key=VNode.depth)
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
        self._preemptible = False
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
        if self._stale:
            self._sync_stale()
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
        if not created:
            return
        resolve_view = self.backend.resolve_view
        publications = self._publications
        register = self._events.register
        for node in created:
            tag = node.tag
            if not node.mounted or tag is None:
                continue
            view = node.native_view = resolve_view(tag)
            element = node.element
            if "ref" in element.props:
                publications.append(partial(self._attach_ref, element, tag))
            # Wrappers whose first native root is this view take its
            # identity; events run in the nearest component's task scope.
            scope = None
            delegating = True
            ancestor = node.parent
            while ancestor is not None:
                if delegating:
                    if ancestor.kind != NATIVE and ancestor.tag == tag:
                        if ancestor.native_view is not view:
                            touch(ancestor)
                            ancestor.native_view = view
                    else:
                        delegating = False
                hook_state = ancestor.hook_state
                if hook_state is not None and scope is None:
                    scope = hook_state.task_scope
                    if not delegating:
                        break
                elif scope is not None and not delegating:
                    break
                ancestor = ancestor.parent
            publications.append(partial(register, tag, node, scope))

    def _flush_layout_effects(self) -> bool:
        """Run queued layout effects; returns whether a failure activated a boundary."""
        routed = False
        due = [
            state for state in self._effect_states.values() if state._pending_layout_effects or state._strict_effects
        ]
        if len(due) > 1:
            due.sort(key=_effect_depth, reverse=True)
        for state in due:
            if state.vnode is not None and state.vnode.mounted:
                try:
                    state.flush_layout_effects()
                except Exception as exc:
                    if diagnostics.is_dev():
                        complete_component_stack(exc, self._component_path(state.vnode))
                    self._route_error(state.vnode, exc)
                    routed = True
        return routed

    def _flush_passive_effects(self) -> bool:
        """Run queued passive effects; returns whether a failure activated a boundary."""
        routed = False
        states, self._effect_states = self._effect_states, {}
        due = [state for state in states.values() if state._pending_effects or state._strict_effects]
        if len(due) > 1:
            due.sort(key=_effect_depth, reverse=True)
        for state in due:
            if state.vnode is not None and state.vnode.mounted:
                try:
                    state.flush_pending_effects()
                except Exception as exc:
                    if diagnostics.is_dev():
                        complete_component_stack(exc, self._component_path(state.vnode))
                    self._route_error(state.vnode, exc)
                    routed = True
        return routed

    # ------------------------------------------------------------------
    # Tree creation
    # ------------------------------------------------------------------

    def _create_tree(self, element: Element) -> VNode:
        kind = kind_of(element.type)
        if kind == NATIVE:
            return self._create_native(element)
        if kind == COMPONENT:
            return self._create_component(element)
        if kind == WRAPPER:
            return self._create_wrapper(element)
        if kind == PROVIDER:
            return self._create_provider(element)
        if kind == BOUNDARY:
            return self._create_error_boundary(element)
        return self._create_suspense(element)

    def _create_native(self, element: Element) -> VNode:
        tag = next_tag()
        type_name = element.type
        node = VNode(element, [], tag, NATIVE)
        clean, events = self._native_props(element.props)
        node.clean_props = clean
        node.events = events
        self._tag_nodes[tag] = node
        ops = self._ops
        ops.append(CreateOp(tag, type_name, clean))
        self._created.append(node)

        attached: List[int] = []
        children = node.children
        try:
            for slot, child_el in enumerate(child_slots(element.children, type_name)):
                if child_el is None:
                    continue
                child = self._create_tree(child_el)
                child.slot = slot
                child.parent = node
                children.append(child)
                if child.kind == NATIVE:
                    if child_el.type != "Portal":
                        child_tag: int = child.tag  # type: ignore[assignment]
                        ops.append(InsertOp(tag, child_tag, len(attached)))
                        attached.append(child_tag)
                else:
                    for root in self._native_roots(child):
                        ops.append(InsertOp(tag, root.tag, len(attached)))  # type: ignore[arg-type]
                        attached.append(root.tag)  # type: ignore[arg-type]
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
        self._native_children[tag] = attached
        return node

    def _create_component(self, element: Element) -> VNode:
        # A retrying Suspense boundary may have preserved this
        # component's hook state from the attempt that suspended;
        # reclaiming it keeps cached resources warm.
        hook_state = self._take_hydrated_hook_state(element) or HookState()
        journal = _journal.active
        if journal is not None and hook_state.owner is None:
            journal.undo.append(hook_state.cleanup_all_effects)
        if self._strict and hook_state.owner is None and diagnostics.is_dev():
            hook_state.strict = True
            hook_state._strict_effects = 3
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
        except Exception as exc:
            if diagnostics.is_dev():
                add_component_frame(exc, element.type)
            raise
        node = VNode(element, children, None, COMPONENT)
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
        consumers: "weakref.WeakSet[HookState]" = weakref.WeakSet()
        context._push(element.props.get("value"), consumers)
        try:
            children = self._create_child_list(child_slots(element.children, self._provider_label(context)))
        finally:
            context._pop()
        node = VNode(element, children, None, PROVIDER)
        node.context_consumers = consumers
        for child in children:
            child.parent = node
        self._refresh_identity(node)
        return node

    def _create_wrapper(self, element: Element) -> VNode:
        strict = element.type is STRICT_MODE
        if strict:
            self._strict += 1
        try:
            children = self._create_child_list(child_slots(element.children, type_label(element.type)))
        finally:
            if strict:
                self._strict -= 1
        node = VNode(element, children, None, WRAPPER)
        for child in children:
            child.parent = node
        self._refresh_identity(node)
        return node

    def _create_child_list(self, slots: Sequence[Optional[Element]]) -> List[VNode]:
        """Create nodes for a child list, cleaning up on mid-list failure.

        When the failure is a ``Suspend``, already-built siblings are
        torn down with their hook states *salvaged*, so the boundary's
        retry re-mounts them with their caches intact.
        """
        nodes: List[VNode] = []
        try:
            for slot, el in enumerate(slots):
                if el is None:
                    continue
                node = self._create_tree(el)
                node.slot = slot
                nodes.append(node)
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

    def _render_component_body(self, hook_state: HookState, element: Element) -> Sequence[Optional[Element]]:
        """Render synchronously or suspend on a real, component-owned task.

        An ``async def`` body is stepped eagerly: its first step runs
        right here, and only when the first ``await`` is actually
        pending does the remainder become a task the component owns, at
        which point the render suspends on it.

        In a transition pass this is where urgent input preempts the
        render: before the body runs.
        """
        if self._preemptible and urgent_input_pending():
            raise Preempted()
        if _profiling._session is None and _profiling._active.get() is None:
            return self._run_component_body(hook_state, element)
        _profiling.count("components.rendered")
        with _profiling.span("component", component=element.type.display_name):
            return self._run_component_body(hook_state, element)

    def _run_component_body(self, hook_state: HookState, element: Element) -> Sequence[Optional[Element]]:
        journal = _journal.active
        if journal is not None and hook_state._journal_stamp != journal.identity:
            journal.record(hook_state)
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
            try:
                result = previous.result()
            except Exception as exc:
                if diagnostics.is_dev():
                    add_component_frame(exc, component)
                raise
            return child_slots(result, label, returned=True)

        token = install_hook_state(hook_state)
        scope_token = _scope.set(hook_state.task_scope)
        try:
            if hook_state.strict:
                # Strict mode: run the body once more and discard the
                # result, so an impure body shows itself.
                hook_state.begin_render(label)
                marks = (len(hook_state._pending_effects), len(hook_state._pending_layout_effects))
                component.render(element)
                hook_state.finish_render()
                del hook_state._pending_effects[marks[0] :]
                del hook_state._pending_layout_effects[marks[1] :]
            hook_state.begin_render(label)
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
        except Exception as exc:
            hook_state.abort_render()
            if diagnostics.is_dev():
                add_component_frame(exc, component)
            raise
        except BaseException:
            hook_state.abort_render()
            raise
        finally:
            _scope.reset(scope_token)
            restore_hook_state(token)
            hook_state._dirty = False
        if rendered.__class__ is Element:
            return (rendered,)
        return child_slots(rendered, label, returned=True)

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
        if hook_state is None or vnode.kind != COMPONENT:
            return
        try:
            with self._providers_above(vnode):
                try:
                    rendered = self._render_component_body(hook_state, vnode.element)
                except Suspend as signal:
                    if signal.hook_state is hook_state:
                        self._register_component_retry(vnode, signal)
                        return
                    raise
                touch(vnode)
                try:
                    self._reconcile_children(vnode, rendered)
                except Suspend:
                    # The retry must re-run this body: its output was never adopted.
                    hook_state._dirty = True
                    raise
                vnode.rendered = rendered
        except (Suspend, Preempted):
            raise
        except Exception as exc:
            if diagnostics.is_dev():
                complete_component_stack(exc, self._component_path(vnode))
            raise

    @staticmethod
    def _component_path(node: Optional[VNode]) -> List[Any]:
        """The components from ``node`` up to the root, innermost first."""
        path: List[Any] = []
        while node is not None:
            if node.kind == COMPONENT:
                path.append(node.element.type)
            node = node.parent
        return path

    def _route_error(self, vnode: VNode, exc: BaseException) -> None:
        """Route a render or effect failure to the nearest ``ErrorBoundary`` ancestor.

        Without an enclosing boundary the exception propagates, exactly
        as it would during a full render.
        """
        node = vnode.parent
        while node is not None:
            if node.kind == BOUNDARY:
                try:
                    with self._providers_above(node):
                        self._activate_boundary(node, exc)
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
            if node.kind == SUSPENSE_KIND:
                try:
                    with self._providers_above(node):
                        self._hide_suspense_content(node, signal)
                except Suspend as escaped:
                    signal = escaped  # a boundary without a fallback is transparent
                else:
                    return
            node = node.parent
        self._discard_salvage()
        raise self._missing_suspense_error(signal) from None

    @contextmanager
    def _providers_above(self, vnode: VNode) -> Iterator[None]:
        """Push the provided values of every provider above ``vnode``, and its StrictMode, outermost first."""
        chain: List[Tuple[Context, Any, Any]] = []
        strict = 0
        node = vnode.parent
        while node is not None:
            kind = node.kind
            if kind == PROVIDER:
                chain.append((node.element.type, node.element.props.get("value"), node.context_consumers))
            elif kind == WRAPPER and node.element.type is STRICT_MODE:
                strict += 1
            node = node.parent
        chain.reverse()
        for context, value, consumers in chain:
            context._push(value, consumers)
        saved = self._strict
        self._strict = strict
        try:
            yield
        finally:
            self._strict = saved
            for context, _value, _consumers in reversed(chain):
                context._pop()

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------

    def _reconcile_node(self, old: VNode, new_el: Element) -> VNode:
        """Update ``old`` to describe ``new_el``; returns the node now in the slot."""
        old_el = old.element
        if new_el is old_el and self._reusable(old):
            # The parent rendered the identical element: nothing in this
            # subtree changed through props. Components with their own
            # pending state are still in the dirty queue and render there.
            return old
        new_type = new_el.type
        old_type = old_el.type
        if old_type is not new_type and not (old_type.__class__ is str and old_type == new_type):
            new_node = self._create_tree(new_el)
            self._destroy_tree(old)
            return new_node
        kind = old.kind
        if kind == NATIVE:
            self._reconcile_native(old, new_el)
        elif kind == COMPONENT:
            self._reconcile_component(old, new_el)
        elif kind == WRAPPER:
            self._reconcile_wrapper(old, new_el)
        elif kind == PROVIDER:
            self._reconcile_provider(old, new_el)
        elif kind == BOUNDARY:
            self._reconcile_error_boundary(old, new_el)
        else:
            self._reconcile_suspense(old, new_el)
        return old

    @staticmethod
    def _reusable(node: VNode) -> bool:
        """Whether ``node`` can be kept as is when its parent renders the identical element."""
        if node.kind == COMPONENT:
            hs = node.hook_state
            return hs is not None and node.rendered is not None and not hs._dirty
        return True

    def _reconcile_native(self, old: VNode, new_el: Element) -> None:
        old_props = old.element.props
        new_props = new_el.props
        changed = False
        if new_props is not old_props:
            result = (
                self._update_native_props(old, old_props, new_props)
                if _SPECIAL_PROPS.isdisjoint(new_props) and _SPECIAL_PROPS.isdisjoint(old_props)
                else None
            )
            if result is None:
                self._update_native_props_slow(old, new_el)
                changed = True
            else:
                changed = result
        children = new_el.children
        if children or old.children:
            if self._reconcile_children(old, child_slots(children, new_el.type)):
                changed = True
        if changed:
            touch(old)
            old.element = new_el

    def _update_native_props(self, node: VNode, old: Mapping[str, Any], new: Mapping[str, Any]) -> Optional[bool]:
        """The one-pass prop update; returns whether anything changed, or ``None`` for the general path.

        Values identical to the old ones are skipped, a changed ``on_*``
        callable only updates the node's handler table, and anything
        else is compared under the framework equality rule. Nothing is
        written until the walk has decided the fast path applies.
        """
        changed: Optional[Dict[str, Any]] = None
        events: Optional[Dict[str, Any]] = None
        shared = 0
        for key, value in new.items():
            previous = old.get(key, _MISSING)
            if previous is _MISSING:
                if value is UNSET or (key[:3] == "on_" and callable(value)):
                    return None
            else:
                shared += 1
                if previous is value:
                    continue
                if key[:3] == "on_" and (callable(value) or callable(previous)):
                    if not (callable(value) and callable(previous)) or getattr(value, _WORKLET_MARK, False):
                        return None
                    if getattr(previous, _WORKLET_MARK, False):
                        return None
                    if events is None:
                        events = dict(node.events or ())
                    events[key] = value
                    continue
                if value is UNSET:
                    return None
                cls = value.__class__
                if cls is previous.__class__ and cls in _PLAIN_VALUES:
                    if previous == value:
                        continue
                elif equal(previous, value):
                    continue
            if changed is None:
                changed = {}
            changed[key] = value
        if shared != len(old):
            for key in old:
                if key not in new:
                    if key[:3] == "on_" and callable(old[key]):
                        return None
                    if changed is None:
                        changed = {}
                    changed[key] = UNSET
        if changed is None and events is None:
            return False
        touch(node)
        if changed is not None:
            clean = dict(node.clean_props)
            for key, value in changed.items():
                if value is UNSET:
                    clean.pop(key, None)
                else:
                    clean[key] = value
            node.clean_props = clean
            self._ops.append(UpdateOp(node.tag, changed))  # type: ignore[arg-type]
        if events is not None:
            node.events = events
        return True

    def _update_native_props_slow(self, node: VNode, new_el: Element) -> None:
        """The general prop update: refs, layout observers, gestures, refresh controls, and motion props."""
        touch(node)
        new_clean, events = self._split_props(new_el.props)
        changed = self._diff_props(node.clean_props, new_clean)
        if changed and node.tag is not None:
            self._ops.append(UpdateOp(node.tag, changed))
        node.clean_props = new_clean
        node.events = events or None
        old_ref = node.element.props.get("ref")
        new_ref = new_el.props.get("ref")
        if old_ref is not new_ref:
            self._publications.append(partial(self._clear_ref, old_ref))
            self._publications.append(partial(self._attach_ref, new_el, node.tag))

    def _native_props(self, props: Mapping[str, Any]) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """Split a new view's props into its native payload and its Python handlers."""
        if not props:
            return {}, None
        if not _SPECIAL_PROPS.isdisjoint(props):
            clean, events = self._split_props(props)
            return clean, events or None
        clean = {}
        handlers: Optional[Dict[str, Any]] = None
        for key, value in props.items():
            if key[:3] == "on_" and callable(value):
                if getattr(value, _WORKLET_MARK, False):
                    clean, events = self._split_props(props)
                    return clean, events or None
                if handlers is None:
                    handlers = {}
                handlers[key] = value
            elif value is UNSET:
                continue
            else:
                clean[key] = value
        if handlers is not None:
            clean[EVENTS_PROP] = frozenset(handlers)
        return clean, handlers

    def _reconcile_component(self, old: VNode, new_el: Element) -> None:
        if self._can_skip_memoized(old, new_el):
            touch(old)
            old.element = new_el
            return
        hook_state = old.hook_state
        assert hook_state is not None
        rendered = self._render_component_body(hook_state, new_el)
        touch(old)
        old.element = new_el
        try:
            self._reconcile_children(old, rendered)
        except Suspend:
            hook_state._dirty = True
            raise
        except Exception as exc:
            if diagnostics.is_dev():
                add_component_frame(exc, new_el.type)
            raise
        old.rendered = rendered

    def _reconcile_provider(self, old: VNode, new_el: Element) -> None:
        context: Context = new_el.type
        new_value = new_el.props.get("value")
        old_props = old.element.props
        changed = old.element.key != new_el.key
        if "value" not in old_props or not equal(old_props["value"], new_value):
            self._mark_context_consumers(old, context)
            changed = True
        context._push(new_value, old.context_consumers)
        try:
            if self._reconcile_children(old, child_slots(new_el.children, self._provider_label(context))):
                changed = True
        finally:
            context._pop()
        if changed:
            touch(old)
            old.element = new_el

    def _reconcile_wrapper(self, old: VNode, new_el: Element) -> None:
        strict = new_el.type is STRICT_MODE
        if strict:
            self._strict += 1
        try:
            changed = self._reconcile_children(old, child_slots(new_el.children, type_label(new_el.type)))
        finally:
            if strict:
                self._strict -= 1
        if changed or old.element.key != new_el.key:
            touch(old)
            old.element = new_el

    def _mark_context_consumers(self, provider: VNode, context: Context) -> None:
        """Mark every component that read ``context`` from ``provider`` for re-render.

        ``use_context`` registers each reader with the innermost
        provider, so this touches exactly the consumers instead of
        walking the provider's subtree. Readers that stopped reading the
        context or unmounted are skipped.
        """
        target = id(context)
        for hs in list(provider.context_consumers or ()):
            node = hs.vnode
            if node is None or not node.mounted or target not in hs.context_deps:
                continue
            hs._dirty = True
            self._dirty_nodes[id(node)] = node

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
        except Exception as exc:
            # A failing comparator means "changed": render rather than risk a stale subtree.
            if diagnostics.is_dev():
                diagnostics.warn_once(
                    f"The memo comparator of {component.display_name} raised {type(exc).__name__}: {exc}. "
                    "The component re-renders instead of skipping.",
                    key=f"memo-comparator:{component.display_name}",
                )
            return False

    def _reconcile_children(self, parent: VNode, slots: Sequence[Optional[Element]]) -> bool:
        """Reconcile ``parent``'s child list against ``slots``; return whether its structure changed.

        The caller has recorded ``parent`` in the journal if it's going
        to write it; this writes ``parent.children`` only when the list
        changed, recording the parent first.
        """
        old = parent.children
        children = self._reconcile_child_list(parent, old, slots)
        if children is old:
            return False
        touch(parent)
        parent.children = children
        self._structure_changed(parent)
        return True

    def _set_children(self, parent: VNode, children: List[VNode]) -> None:
        """Replace ``parent``'s children with nodes already reconciled or created (boundaries)."""
        for child in children:
            if child.parent is not parent:
                touch(child)
                child.parent = parent
        touch(parent)
        parent.children = children
        self._structure_changed(parent)

    def _reconcile_child_list(
        self, parent: VNode, old_children: List[VNode], slots: Sequence[Optional[Element]]
    ) -> List[VNode]:
        """Match, reconcile, create, and destroy one child list.

        Returns ``old_children`` itself when the list kept its shape (the
        same element type and key in the same slots), after updating each
        child in place; no lookup tables are built for that case.
        Otherwise keyed elements match the old child with the same key
        wherever it was, unkeyed elements match the old unkeyed child in
        the same slot, and a different type replaces the node. Native
        attachment order is synced later, for containers whose structure
        changed.

        On failure, any freshly created replacement nodes are destroyed
        before the exception propagates so an enclosing boundary can
        swap in its fallback without leaking native views. When the
        failure is a ``Suspend`` their hook states are salvaged for the
        boundary's retry.
        """
        count = len(slots)
        old_count = len(old_children)
        limit = count if count < old_count else old_count
        index = 0
        reconcile = self._reconcile_node
        while index < limit:
            child = old_children[index]
            el = slots[index]
            if el is None or child.slot != index:
                break
            old_el = child.element
            if old_el.key != el.key:
                break
            new_type = el.type
            old_type = old_el.type
            if old_type is not new_type and not (old_type.__class__ is str and old_type == new_type):
                break
            if el is not old_el or not self._reusable(child):
                reconcile(child, el)
            index += 1
        if index == count == old_count:
            return old_children

        result = old_children[:index]
        by_key: Dict[Any, VNode] = {}
        by_slot: Dict[int, VNode] = {}
        # Duplicate keys are an application bug (dev mode warns), but they
        # must never corrupt the tree: each old node matches at most once,
        # and every old node that doesn't match is destroyed.
        leftovers: List[VNode] = []
        for child in old_children[index:]:
            key = child.element.key
            if key is None:
                by_slot[child.slot] = child
            elif key in by_key:
                leftovers.append(child)
            else:
                by_key[key] = child

        fresh: List[VNode] = []
        try:
            for slot in range(index, count):
                el = slots[slot]
                if el is None:
                    continue
                key = el.key
                matched = by_key.pop(key, None) if key is not None else by_slot.pop(slot, None)
                if matched is None:
                    node = self._create_tree(el)
                    fresh.append(node)
                else:
                    old_type = matched.element.type
                    new_type = el.type
                    if old_type is not new_type and not (old_type.__class__ is str and old_type == new_type):
                        node = self._create_tree(el)
                        fresh.append(node)
                        self._destroy_tree(matched)
                    else:
                        node = reconcile(matched, el)
                if node.slot != slot or node.parent is not parent:
                    touch(node)
                    node.slot = slot
                    node.parent = parent
                result.append(node)
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

        for node in by_key.values():
            self._destroy_tree(node)
        for node in by_slot.values():
            self._destroy_tree(node)
        for node in leftovers:
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
        touch(node)
        node.mounted = False
        self._dirty_nodes.pop(id(node), None)
        if node.kind == BOUNDARY:
            self._dirty_boundaries.pop(id(node), None)
        elif node.kind == SUSPENSE_KIND:
            self._dirty_suspense.pop(id(node), None)
            if node.suspense_hydration:
                self._dispose_hydration(node.suspense_hydration)
                node.suspense_hydration = None
            node.suspense_hidden = None
        hs = node.hook_state
        publications = self._publications
        if hs is not None:
            self._effect_states.pop(id(hs), None)
            if salvage is not None and node.kind == COMPONENT:
                salvage.setdefault((id(node.element.type), node.element.key), []).append(hs)
            else:
                publications.append(hs.cleanup_all_effects)
            publications.append(hs.detach)
        for child in node.children:
            self._destroy_tree(child, salvage=salvage)
        if node.kind == NATIVE:
            ref = node.element.props.get("ref")
            if ref is not None:
                publications.append(partial(self._clear_ref, ref))
            tag = node.tag
            if tag is not None:
                self._native_children.pop(tag, None)
                self._tag_nodes.pop(tag, None)
                publications.append(partial(self._events.clear, tag))
                self._ops.append(DestroyOp(tag))
                self._destroyed_tags.add(tag)
        node.children = []
        node.parent = None

    # ------------------------------------------------------------------
    # Native structure helpers
    # ------------------------------------------------------------------

    def _native_roots(self, node: VNode) -> List[VNode]:
        """The native views ``node`` contributes to its native parent, in order.

        Native elements contribute themselves, except ``Portal``, whose
        handler self-attaches to a top-level overlay. Transparent
        wrappers contribute the concatenation of their children's roots.
        """
        if node.kind == NATIVE:
            return [] if node.element.type == "Portal" else [node]
        roots: List[VNode] = []
        for child in node.children:
            roots.extend(self._native_roots(child))
        return roots

    def _flattened_child_roots(self, node: VNode) -> List[VNode]:
        roots: List[VNode] = []
        for child in node.children:
            if child.kind == NATIVE:
                if child.element.type != "Portal":
                    roots.append(child)
            else:
                roots.extend(self._native_roots(child))
        return roots

    def _flattened_child_tags(self, node: VNode) -> List[int]:
        return [root.tag for root in self._flattened_child_roots(node) if root.tag is not None]

    @staticmethod
    def _nearest_native_ancestor(node: VNode) -> Optional[VNode]:
        current = node.parent
        while current is not None:
            if current.kind == NATIVE:
                return current
            current = current.parent
        return None

    def _refresh_identity(self, node: VNode) -> None:
        """Point a wrapper's ``tag`` / ``native_view`` at its first native root."""
        if node.kind == NATIVE:
            return
        first = node
        while first.kind != NATIVE:
            for child in first.children:
                if child.kind != NATIVE or child.element.type != "Portal":
                    roots = self._native_roots(child)
                    if roots:
                        first = roots[0]
                        break
            else:
                if node.tag is not None or node.native_view is not None:
                    touch(node)
                    node.tag = None
                    node.native_view = None
                return
        if node.tag != first.tag or node.native_view is not first.native_view:
            touch(node)
            node.tag = first.tag
            node.native_view = first.native_view

    def _structure_changed(self, node: VNode) -> None:
        """Note that ``node``'s child list changed: refresh wrapper identities and mark its container stale."""
        current: Optional[VNode] = node
        while current is not None and current.kind != NATIVE:
            self._refresh_identity(current)
            current = current.parent
        if current is not None:
            self._stale[id(current)] = current

    def _sync_stale(self) -> None:
        """Emit the inserts that bring each stale container's native children in line with its child list."""
        stale, self._stale = self._stale, {}
        for node in stale.values():
            tag = node.tag
            if not node.mounted or tag is None:
                continue
            self._sync_native_children(tag, self._native_children.get(tag, []), self._flattened_child_roots(node))

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
        after_tags = [root.tag for root in after_roots if root.tag is not None]
        if after_tags == before_tags:
            return False
        self._native_children[parent_tag] = after_tags
        destroyed = self._destroyed_tags
        surviving = [t for t in before_tags if t not in destroyed]
        if surviving == after_tags:
            return True
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

    def _split_props(self, props: Mapping[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Callable[..., Any]]]:
        """Strip reconciler-owned keys, then split event callables from native props.

        Worklet event and gesture handlers become handler bindings the
        renderer core runs (RFC 0009), and layout animation props become
        the descriptors the core reads.
        """
        if not props:
            return {}, {}
        stripped = {key: value for key, value in props.items() if key != "ref" and value is not UNSET}
        from ..motion.runtime import runtime as motion

        for key in _MOTION_PROPS:
            if key in stripped:
                stripped[key] = motion.prop_wire(self.backend, stripped[key])
        binder = None
        if motion.target(self.backend) is not None:
            backend = self.backend

            def binder(fn: Callable[..., Any]) -> Optional[int]:
                return motion.handler(backend, fn)

        clean, events = extract_events(stripped, binder)
        if props.get("ref") is not None or "on_layout" in events:
            clean["_pn_layout"] = True
        if "on_layout" in events:
            # The core reports layout itself; native never fires it, and
            # leaving it out keeps a layout-only wrapper flattenable.
            names = clean[EVENTS_PROP] - {"on_layout"}
            if names:
                clean[EVENTS_PROP] = names
            else:
                del clean[EVENTS_PROP]
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

            handle = make_handle(element.type, tag, self.backend)  # type: ignore[arg-type]
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
        old_type = old_el.type
        if old_type.__class__ is str:
            return bool(old_type == new_el.type)
        return old_type is new_el.type

    @staticmethod
    def _provider_label(context: Context) -> str:
        return f"{context.name}.Provider" if context.name else "Provider"
