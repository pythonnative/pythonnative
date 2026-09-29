"""Virtual time for the framework loop.

```python
from pythonnative.testing import fake_clock, render

def test_toast_disappears():
    with fake_clock() as clock:
        result = render(Toast())
        assert result.query_by_text("Saved")
        clock.advance(3.0)          # the effect's asyncio.sleep(3) fires now
        assert result.query_by_text("Saved") is None
```

[`FakeClock`][pythonnative.testing.FakeClock] replaces ``time()`` on the
framework's headless asyncio loop (see
[`runtime.get_loop`][pythonnative.runtime.get_loop]) with a clock that
runs ahead of the real one by a virtual offset. Every ``asyncio.sleep``,
``call_later``, and ``asyncio.timeout`` on that loop reads the patched
clock, so ``clock.advance(seconds)`` makes timers due and then runs them,
together with every callback and task they wake, without sleeping.
Patching the loop rather than ``asyncio.sleep`` means the framework's own
timers (transitions, animations, debounced hooks) move with the app's.

Real time still passes underneath: ``clock.now`` is the loop's monotonic
clock plus the virtual offset, so timers due in a few milliseconds still
fire during ``settle`` while long timers wait for ``advance``. Work that
needs a real thread to finish (``run_in_executor``) is outside the
clock's reach; drain it with
[`runtime.drain`][pythonnative.runtime.drain].
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from typing import Any, Iterator, Optional

__all__ = ["FakeClock", "current_fake_clock", "fake_clock"]

_active: Optional["FakeClock"] = None


class FakeClock:
    """Controllable clock installed on the framework's headless loop.

    Create one through [`fake_clock`][pythonnative.testing.fake_clock]
    (or the ``pn_clock`` pytest fixture) rather than directly; the
    context manager installs it on the loop the framework is using and
    restores the real clock afterwards.

    Attributes:
        loop: The asyncio loop whose ``time()`` this clock replaces.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop
        self._offset = 0.0
        self._installed = False

    # -- installation ---------------------------------------------------

    def install(self) -> None:
        """Patch ``loop.time`` (idempotent). Raises if the loop is running on another thread."""
        global _active
        if self._installed:
            return
        if self.loop.is_running():
            raise RuntimeError("fake_clock() needs the headless loop; it cannot drive a running application thread")
        if _active is not None and _active is not self:
            raise RuntimeError("A FakeClock is already installed; nest fake_clock() blocks one at a time")
        self.loop.time = self._time  # type: ignore[method-assign]
        self._installed = True
        _active = self

    def uninstall(self) -> None:
        """Restore the loop's real ``time()`` (idempotent)."""
        global _active
        if not self._installed:
            return
        self.loop.__dict__.pop("time", None)
        self._installed = False
        if _active is self:
            _active = None

    def _time(self) -> float:
        return type(self.loop).time(self.loop) + self._offset

    # -- reading ---------------------------------------------------------

    @property
    def now(self) -> float:
        """The loop's current time in seconds: monotonic real time plus the virtual offset."""
        return self._time()

    @property
    def offset(self) -> float:
        """Seconds of virtual time added so far by ``advance``."""
        return self._offset

    # -- driving ---------------------------------------------------------

    def advance(self, seconds: float) -> None:
        """Move the clock forward by ``seconds`` and run everything that becomes due.

        Timers fire in order at their scheduled instants (a timer that
        re-arms itself every second fires twice during ``advance(2.5)``),
        and the loop is drained after each so the tasks they wake run to
        their next await. Returns once the clock has reached its target
        and nothing further is due.

        Args:
            seconds: How far to advance; must not be negative.

        Raises:
            ValueError: If ``seconds`` is negative.
        """
        if seconds < 0:
            raise ValueError("advance() cannot move the clock backwards")
        target = self.now + seconds
        while True:
            self.run_until_idle()
            due = self._next_timer()
            if due is None or due > target:
                break
            self._jump_to(due)
        self._jump_to(target)
        self.run_until_idle()

    def run_until_idle(self, *, max_iterations: int = 10_000) -> None:
        """Run ready callbacks and timers due at the current time until the loop has nothing runnable.

        This never blocks: each iteration runs the loop for exactly one
        turn, so work queued by that turn runs on the next. Timers in
        the future are left alone.

        Raises:
            RuntimeError: If the loop is still producing work after ``max_iterations`` turns.
        """
        loop = self.loop
        if self._ready() is None or self._scheduled() is None:
            # A loop implementation without asyncio's queues: a fixed number of turns is the best we can do.
            for _ in range(10):
                loop.call_soon(loop.stop)
                loop.run_forever()
            return
        for _ in range(max_iterations):
            loop.call_soon(loop.stop)
            loop.run_forever()
            if self._idle():
                return
        raise RuntimeError("Framework loop did not go idle; a callback is rescheduling itself unconditionally")

    # -- internals -------------------------------------------------------

    def _jump_to(self, when: float) -> None:
        # ``now`` already includes real elapsed time, so only add what is still missing.
        missing = when - self.now
        if missing > 0:
            self._offset += missing

    def _ready(self) -> Any:
        return getattr(self.loop, "_ready", None)

    def _scheduled(self) -> Any:
        return getattr(self.loop, "_scheduled", None)

    def _next_timer(self) -> Optional[float]:
        scheduled = self._scheduled()
        if not scheduled:
            return None
        live = [handle._when for handle in scheduled if not getattr(handle, "_cancelled", False)]
        return min(live) if live else None

    def _idle(self) -> bool:
        if len(self._ready()):
            return False
        due = self._next_timer()
        return due is None or due > self.now


def current_fake_clock() -> Optional[FakeClock]:
    """Return the installed [`FakeClock`][pythonnative.testing.FakeClock], or ``None``."""
    return _active


@contextmanager
def fake_clock() -> Iterator[FakeClock]:
    """Install a [`FakeClock`][pythonnative.testing.FakeClock] on the framework loop for the block.

    The pytest fixture ``pn_clock`` (from ``pythonnative.testing.pytest_plugin``)
    wraps this for the duration of a test.
    """
    from .. import runtime

    clock = FakeClock(runtime.get_loop())
    clock.install()
    try:
        yield clock
    finally:
        clock.uninstall()
