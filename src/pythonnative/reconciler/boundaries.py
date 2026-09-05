"""``ErrorBoundary`` and ``Suspense`` handling for the reconciler.

Both boundaries are transparent wrappers whose children are swapped
for a fallback subtree when something goes wrong beneath them:

- an **error boundary** catches exceptions raised while rendering its
  subtree, mounts its ``fallback`` (optionally receiving the error and
  a ``reset`` callable), and rebuilds the content when ``reset`` runs;
- a **Suspense** boundary catches [`Suspend`][pythonnative.suspense.Suspend]
  signals (an ``async`` body or a [`use_resource`][pythonnative.use_resource]
  read that isn't ready), shows its ``fallback``, and retries the
  content once the awaited work completes. Hook states of components
  that had already rendered are preserved across the retry so cached
  resources aren't refetched.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from .. import diagnostics
from ..element import Element
from ..hooks import HookState
from ..suspense import Suspend
from .vnode import VNode, normalize_children

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
    transitions: "TransitionQueue"

    # Methods provided by the concrete reconciler.
    def _create_child_list(self, elements: List[Element]) -> List[VNode]: ...  # pragma: no cover

    def _reconcile_child_list(self, old: List[VNode], new: List[Element]) -> List[VNode]: ...  # pragma: no cover

    def _destroy_tree(self, node: VNode, salvage: Optional[HydrationMap] = None) -> None: ...  # pragma: no cover

    def _refresh_identity(self, node: VNode) -> None: ...  # pragma: no cover

    def request_render(self) -> None:  # pragma: no cover
        """Ask for another render pass (provided by the concrete reconciler)."""
        ...

    # ------------------------------------------------------------------
    # Error boundaries
    # ------------------------------------------------------------------

    def _create_error_boundary(self, element: Element) -> VNode:
        node = VNode(element, [])
        try:
            children = self._create_child_list(normalize_children(element.children, owner="ErrorBoundary"))
        except Exception as exc:
            self._activate_boundary(node, exc)
            return node
        for child in children:
            child.parent = node
        node.children = children
        self._refresh_identity(node)
        return node

    def _reconcile_error_boundary(self, old: VNode, new_el: Element) -> VNode:
        old.element = new_el
        if old.error is not None:
            # Fallback is showing; keep showing it (rebuilt against the
            # latest fallback prop) until reset() clears the error.
            fallback_els = self._error_fallback_elements(old, old.error)
            old.children = self._reconcile_child_list(old.children, fallback_els)
            for child in old.children:
                child.parent = old
            self._refresh_identity(old)
            return old
        try:
            children = self._reconcile_child_list(
                old.children, normalize_children(new_el.children, owner="ErrorBoundary")
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
        props = node.element.props
        on_error = props.get("on_error")
        if callable(on_error):
            try:
                on_error(exc)
            except Exception as cb_exc:
                diagnostics.warn(f"ErrorBoundary on_error callback raised {cb_exc!r}")
        if props.get("fallback") is None:
            raise exc
        for child in node.children:
            self._destroy_tree(child)
        node.children = []
        node.error = exc
        children = self._create_child_list(self._error_fallback_elements(node, exc))
        for child in children:
            child.parent = node
        node.children = children
        self._refresh_identity(node)

    def _error_fallback_elements(self, node: VNode, exc: BaseException) -> List[Element]:
        """Render a boundary's fallback prop into a normalized child list."""
        fallback = node.element.props.get("fallback")
        if fallback is None:
            return []
        result: Any = fallback
        if callable(fallback) and not isinstance(fallback, Element):
            arity = _positional_arity(fallback)
            if arity >= 2:
                result = fallback(exc, self._make_boundary_reset(node))
            elif arity == 1:
                result = fallback(exc)
            else:
                result = fallback()
        return normalize_children(result, owner="ErrorBoundary.fallback")

    def _make_boundary_reset(self, node: VNode) -> Callable[[], None]:
        """Return the ``reset`` callable handed to a boundary's fallback."""

        def reset() -> None:
            if not node.mounted or node.error is None:
                return
            node.error = None
            self._dirty_boundaries[id(node)] = node
            from ..scheduler import schedule_trigger

            schedule_trigger(self.request_render)

        return reset

    # ------------------------------------------------------------------
    # Suspense boundaries
    # ------------------------------------------------------------------

    def _create_suspense(self, element: Element) -> VNode:
        node = VNode(element, [])
        self._attempt_suspense_content(node)
        return node

    def _reconcile_suspense(self, old: VNode, new_el: Element) -> VNode:
        old.element = new_el
        if old.suspense_showing_fallback:
            # Fallback showing; keep it in sync with the latest fallback
            # prop. Content retries are driven by waitable completions,
            # not by parent re-renders.
            old.children = self._reconcile_child_list(old.children, self._suspense_fallback_elements(old))
            for child in old.children:
                child.parent = old
            self._refresh_identity(old)
            return old
        try:
            children = self._reconcile_child_list(old.children, normalize_children(new_el.children, owner="Suspense"))
            old.children = children
            for child in children:
                child.parent = old
            self._refresh_identity(old)
        except Suspend as signal:
            self._teardown_suspense_content(old)
            self._suspend_boundary(old, signal)
        return old

    def _attempt_suspense_content(self, node: VNode) -> None:
        """Build a boundary's content from scratch (initial mount or retry).

        Components re-adopt hook states preserved from the previous
        attempt (the hydration map), so cached resources resolve
        instead of refetching. On success any still-showing fallback
        is swapped out for the content; on suspension the fallback
        mounts (or stays) and a retry is wired to the pending work.
        """
        hydration: HydrationMap = node.suspense_hydration or {}
        node.suspense_hydration = None
        saved_hydration = self._hydration
        saved_salvage = self._suspense_salvage
        self._hydration = hydration
        self._suspense_salvage = None
        try:
            children = self._create_child_list(normalize_children(node.element.children, owner="Suspense"))
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
        for child in children:
            child.parent = node
        node.children = children
        node.suspense_showing_fallback = False
        node.suspense_waits = None
        self._refresh_identity(node)

    def _teardown_suspense_content(self, node: VNode) -> None:
        """Destroy a boundary's live content, salvaging its hook states.

        Used when an *update* under the boundary suspends: the content
        components' hook states move into the boundary's hydration map,
        so when the retry re-mounts them their state, caches, and
        effect bookkeeping carry over (the fallback round-trip doesn't
        reset the subtree).
        """
        salvage: HydrationMap = {}
        for child in node.children:
            self._destroy_tree(child, salvage=salvage)
        node.children = []
        node.suspense_showing_fallback = False
        if salvage:
            hydration = node.suspense_hydration
            if hydration is None:
                hydration = node.suspense_hydration = {}
            for key, states in salvage.items():
                hydration.setdefault(key, []).extend(states)

    def _suspend_boundary(self, node: VNode, signal: Suspend) -> None:
        """Show a boundary's fallback and schedule a retry for ``signal``.

        A boundary without a fallback is transparent: the suspension
        propagates to the next Suspense ancestor (mirroring how an
        ErrorBoundary without a fallback re-raises).
        """
        if node.element.props.get("fallback") is None:
            raise signal

        # Fold in hook states salvaged while the Suspend unwound
        # (already-rendered siblings of the suspender), plus the
        # suspender's own state carried on the signal.
        salvage = self._suspense_salvage
        self._suspense_salvage = None
        if salvage or (signal.hook_state is not None and signal.key is not None):
            hydration = node.suspense_hydration
            if hydration is None:
                hydration = node.suspense_hydration = {}
            if salvage:
                for key, states in salvage.items():
                    hydration.setdefault(key, []).extend(states)
            if signal.hook_state is not None and signal.key is not None:
                bucket = hydration.setdefault(signal.key, [])
                if signal.hook_state not in bucket:
                    bucket.append(signal.hook_state)

        if not node.suspense_showing_fallback:
            children = self._create_child_list(self._suspense_fallback_elements(node))
            for child in children:
                child.parent = node
            node.children = children
            node.suspense_showing_fallback = True
            self._refresh_identity(node)

        self._watch_waitable(node, signal.waitable)

    @staticmethod
    def _suspense_fallback_elements(node: VNode) -> List[Element]:
        fallback = node.element.props.get("fallback")
        if fallback is None:
            return []
        result: Any = fallback
        if callable(fallback) and not isinstance(fallback, Element):
            result = fallback()
        return normalize_children(result, owner="Suspense.fallback")

    def _watch_waitable(self, node: VNode, waitable: Any) -> None:
        """Queue a content retry for ``node`` when ``waitable`` completes."""
        waits = node.suspense_waits
        if waits is None:
            waits = node.suspense_waits = set()
        marker = id(waitable)
        if marker in waits:
            return
        waits.add(marker)

        def _on_done(_w: Any = None) -> None:
            live_waits = node.suspense_waits
            if live_waits is not None:
                live_waits.discard(marker)
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

    @staticmethod
    def _dispose_hydration(hydration: HydrationMap) -> None:
        """Clean up preserved hook states that no component reclaimed."""
        for states in hydration.values():
            for hook_state in states:
                try:
                    hook_state.cleanup_all_effects()
                except Exception as exc:
                    diagnostics.warn(f"Error disposing a suspended component's state: {exc!r}")
        hydration.clear()

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
