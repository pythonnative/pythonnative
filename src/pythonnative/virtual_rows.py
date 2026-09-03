"""Row subtrees for natively virtualized lists.

Native virtualized lists (Android ``RecyclerView`` via
``PNVirtualListView``, iOS ``UITableView``) own row lifecycle on the
platform side: the platform decides when a row enters the viewport,
hands PythonNative an empty native container, and recycles that
container when the row scrolls away.

Each visible row hosts a full PythonNative subtree driven by its own
nested [`Reconciler`][pythonnative.reconciler.Reconciler]. The
[`RowSubtree`][pythonnative.virtual_rows.RowSubtree] class wraps that
per-row reconciler: it mounts the row element into fresh native views,
re-reconciles in place when the platform rebinds the same container to
a different row index (recycling), and tears everything down when the
list is destroyed.

State inside rows works: hooks like ``use_state`` mark the row's own
reconciler dirty and the reconciler's inline flush (its default when
no host render callback is set) re-renders just that row. Re-entrant
requests during a flush are drained by the reconciler itself.
"""

from typing import Any, Callable, Dict

from .element import Element

__all__ = ["RowSubtree", "RowHostPool"]


class RowSubtree:
    """One list row's mounted PythonNative subtree.

    Owns a nested reconciler whose viewport is the row's cell size.
    The native root view produced by
    [`mount`][pythonnative.virtual_rows.RowSubtree.mount] is what the
    platform handler attaches to the recycled cell container.
    """

    def __init__(self) -> None:
        from .native_views import get_registry
        from .reconciler import Reconciler

        self._reconciler = Reconciler(get_registry())
        # Rows flush synchronously: a ``use_state`` setter inside a row
        # re-renders that row before the setter returns. The reconciler
        # queues and drains re-entrant requests on its own, so no
        # extra guard is needed here.
        self._reconciler.on_render_requested = self._flush
        self.native_root: Any = None

    def _flush(self) -> None:
        self.native_root = self._reconciler.flush_dirty()

    def mount(self, element: Element, width: float, height: float) -> Any:
        """Mount ``element`` at the given cell size; returns the native root."""
        self.native_root = self._reconciler.mount(element)
        self._reconciler.set_viewport_size(float(width), float(height))
        return self.native_root

    def rebind(self, element: Element, width: float, height: float) -> Any:
        """Reconcile the subtree to ``element`` (cell recycled to a new row).

        Cheaper than unmount + mount when consecutive rows share a
        shape, which is the overwhelmingly common case in lists.
        Returns the (possibly replaced) native root.
        """
        self._reconciler.set_viewport_size(float(width), float(height))
        self.native_root = self._reconciler.reconcile(element)
        return self.native_root

    def unmount(self) -> None:
        """Destroy the subtree and release its native views."""
        try:
            self._reconciler.unmount()
        except Exception:
            pass
        self.native_root = None


class RowHostPool:
    """Per-list bookkeeping of row subtrees keyed by native container.

    The view backend creates one pool per virtualized list view. Keys
    are the container ids native sends with ``on_bind_row`` (stable for
    the life of a recycled cell).
    """

    def __init__(self) -> None:
        self._subtrees: Dict[int, RowSubtree] = {}

    def bind(
        self,
        container_key: int,
        make_element: Callable[[], Element],
        width: float,
        height: float,
    ) -> Any:
        """Mount or rebind the subtree for ``container_key``.

        Returns the subtree's native root. The caller must (re)attach
        it to the container: platforms strip a recycled cell's
        children before rebinding, so even an unchanged root needs
        re-attachment.
        """
        element = make_element()
        subtree = self._subtrees.get(container_key)
        if subtree is None:
            subtree = RowSubtree()
            self._subtrees[container_key] = subtree
            return subtree.mount(element, width, height)
        return subtree.rebind(element, width, height)

    def release(self, container_key: int) -> None:
        """Unmount the subtree for one recycled container, if any."""
        subtree = self._subtrees.pop(container_key, None)
        if subtree is not None:
            subtree.unmount()

    def release_all(self) -> None:
        """Unmount every subtree (list destroyed)."""
        subtrees = list(self._subtrees.values())
        self._subtrees.clear()
        for subtree in subtrees:
            subtree.unmount()

    def __len__(self) -> int:
        return len(self._subtrees)
