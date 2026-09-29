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
from typing import Any, Callable, Iterator

_session: Profiler | None = None

_active: contextvars.ContextVar[Profiler | None] = contextvars.ContextVar("pn_profiler", default=None)


class Profiler:
    """Collect timings and work counters without retaining component trees."""

    def __init__(self, capacity: int = 10_000) -> None:
        if capacity < 1:
            raise ValueError("Profiler capacity must be positive")
        self.events: deque[dict[str, Any]] = deque(maxlen=capacity)
        self.counters: Counter[str] = Counter()
        self.gauges: dict[str, int] = {}
        self._token: Any = None

    def __enter__(self) -> Profiler:
        """Enable collection in this execution context and its tasks."""
        self._token = _active.set(self)
        return self

    def __exit__(self, *_: Any) -> None:
        """Restore the previous profiling context."""
        _active.reset(self._token)

    def summary(self) -> dict[str, Any]:
        """Summarize retained samples; durations are microseconds, not CI budgets."""
        samples: dict[str, list[float]] = {}
        for event in self.events:
            if event["ph"] == "X":
                samples.setdefault(event["name"], []).append(event["dur"])
        phases = {}
        for name, values in samples.items():
            values.sort()
            phases[name] = {
                "samples": len(values),
                "p50_us": values[(len(values) - 1) // 2],
                "p95_us": values[min(len(values) - 1, int(len(values) * 0.95))],
                "max_us": values[-1],
            }
        return {"counters": dict(self.counters), "gauges": dict(self.gauges), "phases": phases}

    def export(self, path: str | Path) -> None:
        """Write a trace suitable for Perfetto or Chrome's trace viewer."""
        Path(path).write_text(json.dumps({"traceEvents": list(self.events), **self.summary()}), encoding="utf-8")


def count(name: str, value: int = 1) -> None:
    """Increment a work counter when profiling is active."""
    profiler = _active.get() or _session
    if profiler is not None:
        profiler.counters[name] += value


def gauge(name: str, value: int) -> None:
    """Record the latest bounded runtime quantity, such as live views or backlog."""
    profiler = _active.get() or _session
    if profiler is not None:
        profiler.gauges[name] = value


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


def profiled(name: str, details: Callable[..., dict[str, Any]] | None = None) -> Any:
    """Measure a synchronous runtime phase when profiling is enabled."""

    def decorate(function: Any) -> Any:
        @functools.wraps(function)
        def run(*args: Any, **kwargs: Any) -> Any:
            with span(name, **(details(*args, **kwargs) if details and (_active.get() or _session) else {})):
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


def native_sample(phase: str, duration_ns: int, **work: int) -> None:
    """Record a completed native phase without mixing native and host clocks."""
    profiler = _active.get() or _session
    if profiler is None:
        return
    profiler.events.append(
        {
            "name": "native." + phase,
            "ph": "X",
            "pid": 1,
            "tid": 2,
            "ts": (time.perf_counter_ns() - duration_ns) / 1000,
            "dur": duration_ns / 1000,
            "args": {"clock": "duration placed at host receipt", **work},
        }
    )
    for name, value in work.items():
        profiler.counters["native." + phase + "." + name] += value
