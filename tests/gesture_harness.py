"""Drive the renderer core's gesture arbiter with scripted pointer streams.

The arbiter lives in the C++ core (RFC 0007) and runs on the UI thread
of every platform. ``GestureArbiter`` here mounts one view carrying the
gesture specs on its own fake surface and feeds it pointer events, so
tests can pin down exactly when recognizers activate, fail, or cancel.
"""

from __future__ import annotations

import itertools
import json
from typing import Any, Callable, Dict, List, Optional, Sequence

from pythonnative.bridge import contract_document
from pythonnative.bridge.core import POINTER_CANCEL, POINTER_DOWN, POINTER_MOVE, POINTER_UP, PROTOCOL_VERSION
from pythonnative.bridge.fake import FakeTransport

_surfaces = itertools.count(1000)
_TAG = 2


class GestureArbiter:
    """One view's gestures in the core, reporting ``(index, payload)`` for every event.

    Times are in seconds, as the platforms report them.
    """

    def __init__(self, specs: Sequence[Dict[str, Any]], emit: Callable[[int, Dict[str, Any]], None]) -> None:
        self._emit = emit
        self._active = False
        self.surface = next(_surfaces)
        self.transport = FakeTransport(surface=self.surface)
        self.transport.set_callback(self._callback)
        self.transport.load_contracts(contract_document())
        envelope = {
            "version": PROTOCOL_VERSION,
            "application": "gestures",
            "surface": self.surface,
            "revision": 1,
            "ops": [
                ["c", 1, "View", {}],
                [
                    "c",
                    _TAG,
                    "View",
                    {
                        "width": 100,
                        "height": 100,
                        "gestures": [dict(spec) for spec in specs],
                        "_pn_events": [f"gesture:{index}" for index in range(len(specs))],
                    },
                ],
                ["i", 1, _TAG, 0],
            ],
            "layout": {"roots": [1], "width": 320, "height": 480, "selective": False},
        }
        ack = json.loads(self.transport.commit(json.dumps(envelope)))
        if not ack.get("ok"):
            raise ValueError(f"The core rejected the gesture specs: {ack.get('error')}")

    def _callback(self, kind: str, tag: int, name: str, payload: str) -> None:
        if kind == "event" and name.startswith("gesture:"):
            self._emit(int(name.split(":", 1)[1]), json.loads(payload)["args"][0])

    def _pointer(
        self, phase: int, pointer: int, x: float, y: float, t: float, ax: Optional[float], ay: Optional[float]
    ) -> None:
        event = (phase, pointer, x, y, x if ax is None else ax, y if ay is None else ay, t)
        self._active = self.transport.pointer(_TAG, [event])

    def pointer_down(
        self,
        pointer: int,
        x: float,
        y: float,
        t: float,
        *,
        absolute_x: Optional[float] = None,
        absolute_y: Optional[float] = None,
    ) -> None:
        self._pointer(POINTER_DOWN, pointer, x, y, t, absolute_x, absolute_y)

    def pointer_move(
        self,
        pointer: int,
        x: float,
        y: float,
        t: float,
        *,
        absolute_x: Optional[float] = None,
        absolute_y: Optional[float] = None,
    ) -> None:
        self._pointer(POINTER_MOVE, pointer, x, y, t, absolute_x, absolute_y)

    def pointer_up(
        self,
        pointer: int,
        x: float,
        y: float,
        t: float,
        *,
        absolute_x: Optional[float] = None,
        absolute_y: Optional[float] = None,
    ) -> None:
        self._pointer(POINTER_UP, pointer, x, y, t, absolute_x, absolute_y)

    def cancel(self, t: float) -> None:
        """The platform took the touch sequence away (a parent scroll view, a system gesture)."""
        self._pointer(POINTER_CANCEL, 0, 0.0, 0.0, t, None, None)

    def poll(self, t: float) -> None:
        """Advance time-based recognizers (long press, multi-tap windows) to ``t``."""
        self.transport.poll_gestures(_TAG, t)

    def next_deadline(self) -> Optional[float]:
        """When the arbiter next needs a ``poll``, or ``None``."""
        return self.transport.gesture_deadline(_TAG)

    def has_active_pan(self) -> bool:
        """Whether a pan owns the touch sequence (the platform then blocks parent scrolling)."""
        return self._active


__all__: List[str] = ["GestureArbiter"]
