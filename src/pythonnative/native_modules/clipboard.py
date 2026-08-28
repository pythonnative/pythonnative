"""Cross-platform clipboard access.

[`Clipboard`][pythonnative.Clipboard] reads and writes the system
pasteboard. All methods are synchronous: ``UIPasteboard`` (iOS) and
``ClipboardManager`` (Android) both answer immediately, so there's no
need for a coroutine.

On a desktop machine (neither Android nor iOS) the module falls back to
a process-local string buffer. That keeps it usable in the desktop
mock target and unit tests instead of raising.

Example:
    ```python
    import pythonnative as pn

    pn.Clipboard.set_string("hello")
    assert pn.Clipboard.get_string() == "hello"
    ```
"""

from __future__ import annotations

from typing import Optional

from .. import diagnostics
from ..utils import IS_ANDROID, IS_IOS

# Desktop fallback buffer so the API is usable off-device.
_desktop_buffer: str = ""


class Clipboard:
    """System clipboard interface (synchronous)."""

    @staticmethod
    def set_string(text: str) -> None:
        """Copy ``text`` onto the system clipboard."""
        global _desktop_buffer
        value = "" if text is None else str(text)
        if IS_ANDROID:
            _android_set(value)
        elif IS_IOS:
            _ios_set(value)
        else:
            _desktop_buffer = value

    @staticmethod
    def get_string() -> str:
        """Return the current clipboard string (``""`` when empty)."""
        if IS_ANDROID:
            return _android_get()
        if IS_IOS:
            return _ios_get()
        return _desktop_buffer

    @staticmethod
    def has_string() -> bool:
        """Return ``True`` when the clipboard holds non-empty text."""
        return bool(Clipboard.get_string())


# ======================================================================
# iOS: UIPasteboard
# ======================================================================


def _ios_pasteboard() -> Optional[object]:
    try:
        from rubicon.objc import ObjCClass

        return ObjCClass("UIPasteboard").generalPasteboard
    except Exception:
        return None


def _ios_set(text: str) -> None:
    pb = _ios_pasteboard()
    if pb is None:
        return
    try:
        pb.string = text
    except Exception:
        diagnostics.swallowed("clipboard._ios_set")


def _ios_get() -> str:
    pb = _ios_pasteboard()
    if pb is None:
        return ""
    try:
        value = pb.string
        return str(value) if value is not None else ""
    except Exception:
        return ""


# ======================================================================
# Android: ClipboardManager
# ======================================================================


def _android_manager() -> Optional[object]:
    try:
        from java import jclass

        from ..utils import get_android_context

        ctx = get_android_context()
        Context = jclass("android.content.Context")
        return ctx.getSystemService(Context.CLIPBOARD_SERVICE)
    except Exception:
        return None


def _android_set(text: str) -> None:
    manager = _android_manager()
    if manager is None:
        return
    try:
        from java import jclass

        ClipData = jclass("android.content.ClipData")
        clip = ClipData.newPlainText("pythonnative", text)
        manager.setPrimaryClip(clip)
    except Exception:
        diagnostics.swallowed("clipboard._android_set")


def _android_get() -> str:
    manager = _android_manager()
    if manager is None:
        return ""
    try:
        if not manager.hasPrimaryClip():
            return ""
        clip = manager.getPrimaryClip()
        if clip is None or clip.getItemCount() == 0:
            return ""
        item = clip.getItemAt(0)
        text = item.getText()
        return str(text) if text is not None else ""
    except Exception:
        return ""
