"""Bounded runtime profiling with exportable Chrome trace events."""

from __future__ import annotations

import atexit
import contextvars
import functools
import json
import os
import time
from collections import Counter, deque
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

_session: Profiler | None = None

_active: contextvars.ContextVar[Profiler | None] = contextvars.ContextVar("pn_profiler", default=None)


class Profiler:
    """Collect timings and work counters without retaining component trees."""

    def __init__(self, capacity: int = 10_000) -> None:
        if capacity < 1:
            raise ValueError("Profiler capacity must be positive")
        self.events: deque[dict[str, Any]] = deque(maxlen=capacity)
        self.counters: Counter[str] = Counter()
        self._token: Any = None

    def __enter__(self) -> Profiler:
        """Enable collection in this execution context and its tasks."""
        self._token = _active.set(self)
        return self

    def __exit__(self, *_: Any) -> None:
        """Restore the previous profiling context."""
        _active.reset(self._token)

    def export(self, path: str | Path) -> None:
        """Write a trace suitable for Perfetto or Chrome's trace viewer."""
        Path(path).write_text(
            json.dumps({"traceEvents": list(self.events), "counters": self.counters}), encoding="utf-8"
        )


def count(name: str, value: int = 1) -> None:
    """Increment a work counter when profiling is active."""
    profiler = _active.get() or _session
    if profiler is not None:
        profiler.counters[name] += value


@contextmanager
def span(name: str, **details: Any) -> Iterator[None]:
    """Measure one phase without retaining values from application state."""
    profiler = _active.get() or _session
    if profiler is None:
        yield
        return
    started = time.perf_counter_ns()
    try:
        yield
    finally:
        profiler.events.append(
            {
                "name": name,
                "ph": "X",
                "pid": 1,
                "tid": 1,
                "ts": started / 1000,
                "dur": (time.perf_counter_ns() - started) / 1000,
                "args": details,
            }
        )


def profiled(name: str) -> Any:
    """Measure a synchronous runtime phase when profiling is enabled."""

    def decorate(function: Any) -> Any:
        @functools.wraps(function)
        def run(*args: Any, **kwargs: Any) -> Any:
            with span(name):
                return function(*args, **kwargs)

        return run

    return decorate


def start_session() -> None:
    """Enable process-wide collection when PN_PROFILE names an output trace."""
    global _session
    path = os.environ.get("PN_PROFILE")
    if path and _session is None:
        _session = Profiler()
        atexit.register(_session.export, path)


start_session()
