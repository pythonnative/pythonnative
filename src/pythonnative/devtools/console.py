"""The DevTools REPL: evaluate Python inside the running app.

Code runs on the application loop, so it sees the same state components
do and may ``await`` (``await pn.fetch(...)``, ``await asyncio.sleep(1)``).
Each agent keeps one namespace across evaluations. It starts with
``pn`` (``pythonnative``), ``asyncio``, ``app`` (the entry module, once
imported), and ``node``, a [`NodeHandle`][pythonnative.devtools.console.NodeHandle]
for the component selected in DevTools.
"""

from __future__ import annotations

import ast
import asyncio
import inspect
import sys
import traceback
from typing import Any, Dict, List, Optional

__all__ = ["Console", "NodeHandle"]


class NodeHandle:
    """The component selected in DevTools, as seen from the REPL.

    Attributes are read live from the mounted node, so ``node.state``
    reflects the latest render.
    """

    def __init__(self, vnode: Any) -> None:
        self._vnode = vnode

    @property
    def name(self) -> str:
        """The component or view name."""
        return str(self._vnode.label)

    @property
    def props(self) -> Dict[str, Any]:
        """The props the node last rendered with."""
        return {key: value for key, value in self._vnode.element.props.items() if key != "children"}

    @property
    def state(self) -> List[Any]:
        """The values of its ``use_state`` and ``use_reducer`` slots, in order."""
        hook_state = self._vnode.hook_state
        return list(hook_state.states) if hook_state is not None else []

    @property
    def refs(self) -> List[Any]:
        """The ``current`` values of its ``use_ref`` slots."""
        hook_state = self._vnode.hook_state
        return [ref.current for ref in hook_state.refs] if hook_state is not None else []

    def set_state(self, index: int, value: Any) -> None:
        """Call the setter of ``use_state`` slot ``index`` with ``value``."""
        hook_state = self._vnode.hook_state
        setter = hook_state._setters.get(index) if hook_state is not None else None
        if setter is None:
            raise IndexError(f"{self.name} has no use_state slot {index}")
        setter(lambda _previous: value)

    def __repr__(self) -> str:
        return f"<node {self.name}>"


class Console:
    """One persistent REPL namespace."""

    def __init__(self) -> None:
        import pythonnative

        self.namespace: Dict[str, Any] = {
            "__name__": "__pn_console__",
            "__builtins__": __builtins__,
            "pn": pythonnative,
            "asyncio": asyncio,
            "node": None,
        }

    def select(self, vnode: Optional[Any]) -> None:
        """Bind ``node`` to the selected component (``None`` clears it)."""
        self.namespace["node"] = NodeHandle(vnode) if vnode is not None else None

    def _refresh_app(self) -> None:
        import os

        entry = os.environ.get("PN_ENTRY_MODULE") or "app.main"
        module = sys.modules.get(entry)
        if module is not None:
            self.namespace["app"] = module

    async def evaluate(self, source: str) -> Dict[str, Any]:
        """Run ``source`` and describe the outcome.

        A single expression returns its ``repr``; statements return
        ``None``. Top-level ``await`` is allowed.

        Returns:
            ``{"ok": True, "repr": str | None, "type": str}`` or
            ``{"ok": False, "error": traceback text}``.
        """
        self._refresh_app()
        flags = ast.PyCF_ALLOW_TOP_LEVEL_AWAIT
        try:
            try:
                code = compile(source, "<devtools>", "eval", flags=flags)
                is_expression = True
            except SyntaxError:
                code = compile(source, "<devtools>", "exec", flags=flags)
                is_expression = False
        except SyntaxError:
            return {"ok": False, "error": traceback.format_exc(limit=0)}
        try:
            result = eval(code, self.namespace)
            if inspect.iscoroutine(result):
                result = await result
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
            # Drop this module's own frame from the top of the traceback.
            text = "".join(line for line in lines if "devtools/console.py" not in line)
            return {"ok": False, "error": text.rstrip()}
        if not is_expression:
            return {"ok": True, "repr": None, "type": "NoneType"}
        self.namespace["_"] = result
        try:
            text = repr(result)
        except Exception as exc:
            text = f"<repr failed: {exc!r}>"
        if len(text) > 20_000:
            text = text[:20_000] + "…"
        return {"ok": True, "repr": text, "type": type(result).__qualname__}
