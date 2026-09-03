"""Cross-platform clipboard access.

[`Clipboard`][pythonnative.Clipboard] reads and writes the system
pasteboard through the native ``Clipboard`` module (``UIPasteboard``
on iOS, ``ClipboardManager`` on Android). The pasteboard lives in
process memory on both platforms, so every method is synchronous.

Off device the module is a process-local string buffer, which keeps it
usable in ``pn preview`` and unit tests.

Example:
    ```python
    import pythonnative as pn

    pn.Clipboard.set_string("hello")
    assert pn.Clipboard.get_string() == "hello"
    ```
"""

from __future__ import annotations

from .registry import native_module


class Clipboard:
    """System clipboard interface (synchronous).

    Raises:
        NativeModuleError: If the native module reports a failure.
    """

    @staticmethod
    def set_string(text: str) -> None:
        """Copy ``text`` onto the system clipboard."""
        native_module("Clipboard").call("set_string", text="" if text is None else str(text))

    @staticmethod
    def get_string() -> str:
        """Return the current clipboard string (``""`` when empty)."""
        value = native_module("Clipboard").call("get_string")
        return "" if value is None else str(value)

    @staticmethod
    def has_string() -> bool:
        """Return ``True`` when the clipboard holds non-empty text."""
        return bool(Clipboard.get_string())
