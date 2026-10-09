"""Live performance numbers and trace capture for DevTools.

While DevTools' Performance panel or the on-device performance monitor is
open, [`Sampler`][pythonnative.devtools.perf.Sampler] keeps a
`Profiler` installed as the process
session and summarizes it once a second:

- **Loop lag:** how late a timer scheduled on the application loop fired,
  the Python counterpart of a dropped frame.
- **Renders and commits:** reconciler passes, components rendered, native
  commits, operations, and the time each phase took.
- **UI frame rate:** reported by the native ``DevSupport`` module.

Trace capture records the same profiler's events into a Chrome trace
document that Perfetto and Chrome's trace viewer open.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional

from .. import profiling

__all__ = ["Sampler"]

_INTERVAL = 1.0
_PHASES = ("render", "commit", "layout", "component", "acknowledgement", "transport.apply", "validation")


class Sampler:
    """Summarize runtime work once a second while enabled.

    Args:
        publish: Called with each sample dict on the application loop.
        frame_stats: Returns the native UI thread's ``{"fps", "dropped"}``,
            or ``None`` where there's no native UI thread.
    """

    def __init__(
        self,
        publish: Callable[[Dict[str, Any]], None],
        frame_stats: Optional[Callable[[], Optional[Dict[str, Any]]]] = None,
    ) -> None:
        self._publish = publish
        self._frame_stats = frame_stats
        self._task: Optional[asyncio.Task[None]] = None
        self._profiler: Optional[profiling.Profiler] = None
        self._previous_session: Optional[profiling.Profiler] = None
        self._recording = False
        self._record_started = 0.0
        self._consumers = 0
        self.latest: Dict[str, Any] = {}

    # -- lifecycle -------------------------------------------------------

    @property
    def running(self) -> bool:
        """Whether samples are being produced."""
        return self._task is not None and not self._task.done()

    def acquire(self) -> None:
        """Start sampling (reference counted: the panel and the monitor share it)."""
        self._consumers += 1
        if self._consumers == 1:
            self._install()
            self._task = asyncio.get_running_loop().create_task(self._run())

    def release(self) -> None:
        """Stop sampling once the last consumer releases it."""
        self._consumers = max(0, self._consumers - 1)
        if self._consumers == 0:
            if self._task is not None:
                self._task.cancel()
                self._task = None
            if not self._recording:
                self._uninstall()

    def _install(self) -> None:
        if self._profiler is not None:
            return
        self._previous_session = profiling._session
        self._profiler = profiling._session or profiling.Profiler(capacity=50_000)
        profiling._session = self._profiler

    def _uninstall(self) -> None:
        if self._profiler is None:
            return
        profiling._session = self._previous_session
        self._profiler = None
        self._previous_session = None

    # -- tracing ---------------------------------------------------------

    def start_trace(self) -> None:
        """Begin recording a trace (sampling may continue alongside it)."""
        self._install()
        assert self._profiler is not None
        self._profiler.events.clear()
        self._profiler.counters.clear()
        self._recording = True
        self._record_started = time.time()

    def stop_trace(self) -> Dict[str, Any]:
        """Stop recording and return the Chrome trace document."""
        profiler = self._profiler
        self._recording = False
        if profiler is None:
            return {"traceEvents": []}
        document = {
            "traceEvents": list(profiler.events),
            "metadata": {"source": "PythonNative DevTools", "started": self._record_started},
            **profiler.summary(),
        }
        if self._consumers == 0:
            self._uninstall()
        return document

    # -- sampling --------------------------------------------------------

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        last = time.perf_counter()
        counters_before: Dict[str, int] = {}
        while True:
            scheduled = loop.time()
            await asyncio.sleep(_INTERVAL)
            lag_ms = max(0.0, (loop.time() - scheduled - _INTERVAL) * 1000.0)
            now = time.perf_counter()
            sample = self._summarize(last, now, counters_before)
            sample["loop_lag_ms"] = round(lag_ms, 1)
            stats = self._frame_stats() if self._frame_stats is not None else None
            if stats:
                sample["ui_fps"] = stats.get("fps")
                sample["ui_dropped"] = stats.get("dropped")
            last = now
            self.latest = sample
            try:
                self._publish(sample)
            except Exception:
                pass

    def _summarize(self, since: float, until: float, counters_before: Dict[str, int]) -> Dict[str, Any]:
        profiler = self._profiler
        phases: Dict[str, Dict[str, float]] = {}
        commits: List[Dict[str, Any]] = []
        if profiler is not None:
            start_us = since * 1_000_000
            for event in reversed(profiler.events):
                if event.get("ts", 0) < start_us:
                    break
                if event.get("ph") != "X":
                    continue
                name = str(event.get("name"))
                if name not in _PHASES and not name.startswith("native."):
                    continue
                bucket = phases.setdefault(name, {"count": 0, "total_ms": 0.0, "max_ms": 0.0})
                duration = float(event.get("dur", 0.0)) / 1000.0
                bucket["count"] += 1
                bucket["total_ms"] = round(bucket["total_ms"] + duration, 3)
                bucket["max_ms"] = round(max(bucket["max_ms"], duration), 3)
                if name == "commit" and len(commits) < 20:
                    commits.append({"ms": round(duration, 3), "ts": event.get("ts")})
            counters = dict(profiler.counters)
        else:
            counters = {}
        delta = {key: value - counters_before.get(key, 0) for key, value in counters.items()}
        counters_before.clear()
        counters_before.update(counters)
        return {
            "time": time.time(),
            "interval_s": round(until - since, 3),
            "phases": phases,
            "commits": list(reversed(commits)),
            "components_rendered": delta.get("components.rendered", 0),
            "bridge_commits": delta.get("bridge.commits", 0),
            "bridge_operations": delta.get("bridge.operations", 0),
            "bridge_bytes": delta.get("bridge.bytes", 0),
        }

    def monitor_lines(self) -> List[str]:
        """Text lines for the on-device performance monitor."""
        sample = self.latest
        if not sample:
            return ["PY sampling…"]
        commit = sample.get("phases", {}).get("commit", {})
        render = sample.get("phases", {}).get("render", {})
        return [
            f"PY lag {sample.get('loop_lag_ms', 0):.0f} ms",
            f"renders {int(render.get('count', 0))}/s  {render.get('max_ms', 0):.1f} ms max",
            f"commits {int(commit.get('count', 0))}/s  {commit.get('max_ms', 0):.1f} ms max",
            f"components {sample.get('components_rendered', 0)}/s",
        ]
