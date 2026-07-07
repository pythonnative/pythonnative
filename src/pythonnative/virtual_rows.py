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
reconciler dirty and a guarded flush re-renders just that row.
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
        # Guarded synchronous flush so ``use_state`` inside a row
        # re-renders the row. Re-entrant requests (a setter firing
        # during the flush itself) are queued and drained after.
        self._flushing = False
        self._flush_queued = False
        self._reconciler._screen_re_render = self._request_flush
        self.native_root: Any = None

    def _request_flush(self) -> None:
        if self._flushing:
            self._flush_queued = True
            return
        self._flushing = True
        try:
            for _ in range(8):
                self._flush_queued = False
                self.native_root = self._reconciler.flush_dirty()
                if not self._flush_queued:
                    break
        finally:
            self._flushing = False

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

    Platform handlers create one pool per virtualized list view. Keys
    are platform-stable container identities (Java identity hash on
    Android, ``contentView`` pointer on iOS).
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
