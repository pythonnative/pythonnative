"""``ErrorBoundary`` and ``Suspense`` handling for the reconciler.

Both boundaries are transparent wrappers whose children are swapped
for a fallback subtree when something goes wrong beneath them:

- an **error boundary** catches exceptions raised while rendering its
  subtree or running its effects, mounts its ``fallback`` (optionally
  receiving the error and a ``reset`` callable), and rebuilds the
  content when ``reset`` runs;
- a **Suspense** boundary catches [`Suspend`][pythonnative.suspense.Suspend]
  signals (an ``async`` body or a [`use_resource`][pythonnative.use_resource]
  read that isn't ready) and shows its ``fallback``. On the initial
  mount the content is built from scratch once the awaited work
  completes, with the hook states of components that had already
  rendered preserved across the retry so cached resources aren't
  refetched. When a boundary that already has committed content
  suspends because a newly mounted descendant suspended, the content
  stays mounted and is hidden (``display: "none"`` on its native roots)
  while the fallback shows beside it, then reconciled in place when the
  work settles. Hook state, native views, focus, and scroll position of
  the siblings survive.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Sequence, Tuple

from .. import diagnostics
from ..element import Element
from ..hooks import HookState
from ..mutations import UNSET, Mutation, UpdateOp
from ..suspense import Suspend
from .vnode import BOUNDARY, SUSPENSE_KIND, VNode, child_slots, touch

if TYPE_CHECKING:
    from ..scheduler import TransitionQueue

HydrationMap = Dict[Tuple[int, Any], List[HookState]]


class BoundaryMixin:
    """Error-boundary and Suspense behavior mixed into the reconciler."""

    # Attributes provided by the concrete reconciler.
    _dirty_boundaries: Dict[int, VNode]
    _dirty_suspense: Dict[int, VNode]
    _hydration: Optional[HydrationMap]
    _suspense_salvage: Optional[HydrationMap]
    _ops: List[Mutation]
    _publications: List[Callable[[], None]]
    transitions: "TransitionQueue"

    # Methods provided by the concrete reconciler.
    def _create_child_list(self, slots: Sequence[Optional[Element]]) -> List[VNode]:
        raise NotImplementedError  # pragma: no cover

    def _reconcile_child_list(
        self, parent: VNode, old_children: List[VNode], slots: Sequence[Optional[Element]]
    ) -> List[VNode]:
        raise NotImplementedError  # pragma: no cover

    def _reconcile_children(self, parent: VNode, slots: Sequence[Optional[Element]]) -> bool:
        raise NotImplementedError  # pragma: no cover

    def _set_children(self, parent: VNode, children: List[VNode]) -> None:
        raise NotImplementedError  # pragma: no cover

    def _destroy_tree(self, node: VNode, salvage: Optional[HydrationMap] = None) -> None:
        raise NotImplementedError  # pragma: no cover

    def _refresh_identity(self, node: VNode) -> None:
        raise NotImplementedError  # pragma: no cover

    def _native_roots(self, node: VNode) -> List[VNode]:
        raise NotImplementedError  # pragma: no cover

    def _create_wrapper(self, element: Element) -> VNode:
        raise NotImplementedError  # pragma: no cover

    def request_render(self) -> None:  # pragma: no cover
        """Ask for another render pass (provided by the concrete reconciler)."""
        ...

    # ------------------------------------------------------------------
    # Error boundaries
    # ------------------------------------------------------------------

    def _create_error_boundary(self, element: Element) -> VNode:
        node = VNode(element, [], None, BOUNDARY)
        try:
            children = self._create_child_list(child_slots(element.children, "ErrorBoundary"))
        except Exception as exc:
            self._activate_boundary(node, exc)
            return node
        for child in children:
            child.parent = node
        node.children = children
        self._refresh_identity(node)
        return node

    def _reconcile_error_boundary(self, old: VNode, new_el: Element) -> VNode:
        touch(old)
        old.element = new_el
        if old.error is not None:
            # Fallback is showing; keep showing it (rebuilt against the
            # latest fallback prop) until reset() clears the error.
            self._reconcile_children(old, self._error_fallback_elements(old, old.error))
            return old
        try:
            self._reconcile_children(old, child_slots(new_el.children, "ErrorBoundary"))
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
        props = node.element.props
        on_error = props.get("on_error")
        if callable(on_error):
            try:
                on_error(exc)
            except Exception as cb_exc:
                diagnostics.warn(f"ErrorBoundary on_error callback raised {cb_exc!r}")
        if props.get("fallback") is None:
            raise exc
        touch(node)
        for child in node.children:
            self._destroy_tree(child)
        node.children = []
        node.error = exc
        self._set_children(node, self._create_child_list(self._error_fallback_elements(node, exc)))

    def _error_fallback_elements(self, node: VNode, exc: BaseException) -> Sequence[Optional[Element]]:
        """Render a boundary's fallback prop into a normalized child list."""
        fallback = node.element.props.get("fallback")
        if fallback is None:
            return []
        result = call_fallback(fallback, exc, lambda: self._make_boundary_reset(node))
        return child_slots(result, "ErrorBoundary.fallback", returned=True)

    def _make_boundary_reset(self, node: VNode) -> Callable[[], None]:
        """Return the ``reset`` callable handed to a boundary's fallback."""

        def reset() -> None:
            if not node.mounted or node.error is None:
                return
            touch(node)
            node.error = None
            self._dirty_boundaries[id(node)] = node
            from ..scheduler import schedule_trigger

            schedule_trigger(self.request_render)

        return reset

    # ------------------------------------------------------------------
    # Suspense boundaries
    # ------------------------------------------------------------------

    def _create_suspense(self, element: Element) -> VNode:
        node = VNode(element, [], None, SUSPENSE_KIND)
        if element.props.get("fallback") is None:
            children = self._create_child_list(child_slots(element.children, "Suspense"))
            for child in children:
                child.parent = node
            node.children = children
            self._refresh_identity(node)
            return node
        self._attempt_suspense_content(node)
        return node

    def _reconcile_suspense(self, old: VNode, new_el: Element) -> VNode:
        previous = old.element
        touch(old)
        old.element = new_el
        if old.suspense_showing_fallback:
            if previous.children != new_el.children:
                if old.suspense_hidden is None:
                    if old.suspense_hydration:
                        self._dispose_hydration(old.suspense_hydration)
                    old.suspense_hydration = None
                    old.suspense_waits = None
                self._attempt_suspense_content(old)
                return old
            # Fallback showing; keep it in sync with the latest fallback
            # prop. Content retries are driven by waitable completions,
            # not by parent re-renders.
            self._refresh_suspense_fallback(old)
            return old
        try:
            self._reconcile_children(old, child_slots(new_el.children, "Suspense"))
        except Suspend as signal:
            self._hide_suspense_content(old, signal)
        return old

    def _attempt_suspense_content(self, node: VNode) -> None:
        """Build or retry a boundary's content (initial mount, retry, or content change).

        Components re-adopt hook states preserved from the previous
        attempt (the hydration map), so cached resources resolve
        instead of refetching. A boundary with hidden committed content
        reconciles it in place; otherwise the content is built from
        scratch. On success any still-showing fallback is swapped out
        for the content; on suspension the fallback mounts (or stays)
        and a retry is wired to the pending work.
        """
        if node.suspense_hidden is not None:
            self._retry_hidden_suspense_content(node)
            return
        touch(node)
        # Claim states from a candidate map. A later render failure must leave
        # the committed boundary's buckets available for its original retry.
        hydration: HydrationMap = {key: list(states) for key, states in (node.suspense_hydration or {}).items()}
        node.suspense_hydration = None
        saved_hydration = self._hydration
        saved_salvage = self._suspense_salvage
        self._hydration = hydration
        self._suspense_salvage = None
        try:
            children = self._create_child_list(child_slots(node.element.children, "Suspense"))
        except Suspend as signal:
            # Unclaimed hook states from the previous attempt stay
            # preserved for the next retry; salvaged sibling states are
            # folded in by _suspend_boundary.
            merged = {key: states for key, states in hydration.items() if states}
            node.suspense_hydration = merged or None
            self._suspend_boundary(node, signal)
            return
        finally:
            self._hydration = saved_hydration
            self._suspense_salvage = saved_salvage

        self._dispose_hydration(hydration)
        for child in node.children:
            self._destroy_tree(child)
        node.suspense_showing_fallback = False
        node.suspense_waits = None
        self._set_children(node, children)

    def _retry_hidden_suspense_content(self, node: VNode) -> None:
        """Reconcile a boundary's hidden content in place and reveal it if it settles."""
        touch(node)
        hidden = node.suspense_hidden or []
        fallback = node.children[len(hidden) :]
        hydration: HydrationMap = {key: list(states) for key, states in (node.suspense_hydration or {}).items()}
        node.suspense_hydration = None
        saved_hydration = self._hydration
        saved_salvage = self._suspense_salvage
        self._hydration = hydration
        self._suspense_salvage = None
        try:
            children = self._reconcile_child_list(node, hidden, child_slots(node.element.children, "Suspense"))
        except Suspend as signal:
            merged = {key: states for key, states in hydration.items() if states}
            node.suspense_hydration = merged or None
            self._fold_suspended_state(node, signal)
            # Slots whose node was replaced mid-list are rebuilt on the next retry.
            still = [child for child in hidden if child.mounted]
            node.suspense_hidden = still
            self._set_children(node, [*still, *fallback])
            self._apply_suspense_hide(node)
            self._watch_waitable(node, signal.waitable)
            return
        finally:
            self._hydration = saved_hydration
            self._suspense_salvage = saved_salvage

        self._dispose_hydration(hydration)
        for child in fallback:
            self._destroy_tree(child)
        node.suspense_hidden = None
        node.suspense_showing_fallback = False
        node.suspense_waits = None
        self._set_children(node, children)
        self._reveal_suspense_content(node)

    def _hide_suspense_content(self, node: VNode, signal: Suspend) -> None:
        """Keep a boundary's committed content mounted but hidden, and show the fallback beside it.

        Called when an update under a boundary with committed content
        suspends. Hook states salvaged while the ``Suspend`` unwound
        move into the boundary's hydration map so the retry re-adopts
        them. A boundary without a fallback is transparent and re-raises.
        """
        if node.element.props.get("fallback") is None:
            raise signal
        touch(node)
        self._fold_suspended_state(node, signal)
        if not node.suspense_showing_fallback:
            node.suspense_hidden = list(node.children)
            self._apply_suspense_hide(node)
            fallback = self._create_child_list(self._suspense_fallback_elements(node))
            node.suspense_showing_fallback = True
            self._set_children(node, [*node.children, *fallback])
        elif node.suspense_hidden is not None:
            self._apply_suspense_hide(node)
        self._watch_waitable(node, signal.waitable)

    def _apply_suspense_hide(self, node: VNode) -> None:
        """Set ``display: "none"`` on every native root of the boundary's hidden content."""
        for child in node.suspense_hidden or ():
            for root in self._native_roots(child):
                if root.hidden_by_suspense:
                    continue
                touch(root)
                root.hidden_by_suspense = True
                if root.tag is not None:
                    self._ops.append(UpdateOp(root.tag, {"display": "none"}))

    def _reveal_suspense_content(self, node: VNode) -> None:
        """Lift the ``display`` override from the boundary's content roots."""
        for child in node.children:
            for root in self._native_roots(child):
                if not root.hidden_by_suspense:
                    continue
                touch(root)
                root.hidden_by_suspense = False
                if root.tag is not None:
                    self._ops.append(UpdateOp(root.tag, {"display": root.clean_props.get("display", UNSET)}))

    def _refresh_suspense_fallback(self, node: VNode) -> None:
        """Reconcile a showing fallback against the latest ``fallback`` prop."""
        touch(node)
        hidden = node.suspense_hidden or []
        current = node.children[len(hidden) :]
        fallback = self._reconcile_child_list(node, current, self._suspense_fallback_elements(node))
        if fallback is not current:
            self._set_children(node, [*hidden, *fallback])

    def _fold_suspended_state(self, node: VNode, signal: Suspend) -> None:
        """Move salvaged hook states and the suspender's own state into the boundary's hydration map.

        A suspender whose node is still mounted (a component re-rendered
        in place under hidden content) keeps its state on the node; only
        states that lost their node are preserved through hydration.
        """
        touch(node)
        salvage = self._suspense_salvage
        self._suspense_salvage = None
        suspender = signal.hook_state
        if suspender is not None and suspender.vnode is not None and suspender.vnode.mounted:
            suspender = None
        if not salvage and (suspender is None or signal.key is None):
            return
        hydration = node.suspense_hydration
        if hydration is None:
            hydration = node.suspense_hydration = {}
        if salvage:
            for key, states in salvage.items():
                hydration.setdefault(key, []).extend(states)
        if suspender is not None and signal.key is not None:
            bucket = hydration.setdefault(signal.key, [])
            if suspender not in bucket:
                bucket.append(suspender)

    def _suspend_boundary(self, node: VNode, signal: Suspend) -> None:
        """Show a boundary's fallback and schedule a retry for ``signal``.

        Used when the content is being built from scratch (initial mount
        or a retry). A boundary without a fallback is transparent: the
        suspension propagates to the next Suspense ancestor (mirroring
        how an ErrorBoundary without a fallback re-raises).
        """
        if node.element.props.get("fallback") is None:
            raise signal
        touch(node)
        self._fold_suspended_state(node, signal)
        if not node.suspense_showing_fallback:
            children = self._create_child_list(self._suspense_fallback_elements(node))
            node.suspense_showing_fallback = True
            self._set_children(node, children)
        self._watch_waitable(node, signal.waitable)

    @staticmethod
    def _suspense_fallback_elements(node: VNode) -> Sequence[Optional[Element]]:
        fallback = node.element.props.get("fallback")
        if fallback is None:
            return []
        result: Any = fallback
        if callable(fallback) and not isinstance(fallback, Element):
            result = fallback()
        return child_slots(result, "Suspense.fallback", returned=True)

    def _watch_waitable(self, node: VNode, waitable: Any) -> None:
        """Queue a content retry for ``node`` when ``waitable`` completes."""
        waits = node.suspense_waits
        marker = id(waitable)
        if waits is not None and marker in waits:
            return
        touch(node)
        node.suspense_waits = {*(waits or ()), marker}

        def _on_done(_w: Any = None) -> None:
            live_waits = node.suspense_waits
            if live_waits is None or marker not in live_waits:
                return
            touch(node)
            node.suspense_waits = live_waits - {marker}
            if not node.mounted or not node.suspense_showing_fallback:
                return
            self._dirty_suspense[id(node)] = node
            from ..scheduler import schedule_trigger

            schedule_trigger(self.request_render)

        waitable.add_done_callback(_on_done)

    def _take_hydrated_hook_state(self, element: Element) -> Optional[HookState]:
        """Pop a preserved hook state matching ``element`` from the hydration map."""
        hydration = self._hydration
        if not hydration:
            return None
        bucket = hydration.get((id(element.type), element.key))
        if not bucket:
            return None
        return bucket.pop(0)

    def _dispose_hydration(self, hydration: HydrationMap) -> None:
        """Clean up preserved hook states that no component reclaimed."""
        for states in hydration.values():
            for hook_state in states:
                self._publications.append(hook_state.cleanup_all_effects)

    def _discard_salvage(self) -> None:
        """Dispose hook states salvaged during a Suspend that no boundary caught."""
        salvage = self._suspense_salvage
        self._suspense_salvage = None
        if salvage:
            self._dispose_hydration(salvage)

    @staticmethod
    def _missing_suspense_error(signal: Suspend) -> RuntimeError:
        who = signal.label or "A component"
        return RuntimeError(
            f"{who} suspended while rendering, but no Suspense ancestor provides a "
            "fallback. Wrap the async part of the tree in pn.Suspense(..., "
            "fallback=...) to declare its loading state."
        )


def call_fallback(fallback: Any, error: BaseException, reset: Callable[[], Callable[[], None]]) -> Any:
    """Render an ``ErrorBoundary`` fallback in any of its forms.

    ``fallback`` is an element, ``fallback()``, ``fallback(error)``, or
    ``fallback(error, reset)``. ``reset`` builds the reset callable, only when
    the fallback takes one.
    """
    if not callable(fallback) or isinstance(fallback, Element):
        return fallback
    arity = _positional_arity(fallback)
    if arity >= 2:
        return fallback(error, reset())
    return fallback(error) if arity == 1 else fallback()


def _positional_arity(fn: Callable[..., Any]) -> int:
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
