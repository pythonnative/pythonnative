#!/usr/bin/env python3
"""Measure incremental list work with deterministic bounds and JSON output.

Run ``python scripts/benchmark-rendering.py --rows 100000 --edits 20``.
The headless renderer measures Python preparation, reconciliation, and wire
work, not device frame rate. Native phase timings come from PN_PROFILE traces.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time
from dataclasses import dataclass
from typing import Any

import pythonnative as pn
from pythonnative.bridge import codec
from pythonnative.profiling import Profiler
from pythonnative.testing import render


@dataclass(frozen=True)
class Item:
    """Immutable application record with stable identity."""

    key: str
    title: str


def row(item: Item, index: int) -> pn.Element:
    """Keep the renderer stable so only actual data changes invalidate rows."""
    return pn.Text(f"{index}: {item.title}")


def benchmark(size: int, edits: int, incremental: bool) -> dict[str, Any]:
    """Report work for one-item edits after the initial snapshot is committed."""
    initial = [Item(str(i), str(i)) for i in range(size)]
    data = pn.ListData(initial, key=lambda item: item.key) if incremental else initial
    result = render(pn.FlatList(data=data, render_item=row, item_height=44), viewport=None)
    durations, sizes = [], []
    with Profiler() as profile:
        for edit in range(edits):
            started = time.perf_counter_ns()
            replacement = Item("0", f"edit {edit}")
            if isinstance(data, pn.ListData):
                data.update("0", replacement)
                result.settle()
            else:
                data = [replacement, *data[1:]]
                result.rerender(pn.FlatList(data=data, render_item=row, item_height=44))
            durations.append((time.perf_counter_ns() - started) / 1e6)
            packet = result.get_by_type("VirtualList").props["dataset"]
            sizes.append(len(codec.dumps(packet).encode()))
    mounted = result.backend.live_view_count()
    report = {
        "source": "ListData" if incremental else "Sequence",
        "rows": size,
        "edits": edits,
        "median_ms": statistics.median(durations),
        "max_ms": max(durations),
        "max_dataset_bytes": max(sizes),
        "mounted_views": mounted,
        **profile.summary(),
    }
    result.unmount()
    assert result.backend.live_view_count() == 0
    if incremental:
        assert profile.counters["list.snapshot_rows"] == 0
        assert profile.counters["list.incremental_changes"] == edits
        assert profile.counters["list.rows_validated"] == edits
        assert max(sizes) < 128 and mounted < 128
    return report


def main() -> None:
    """Compare the intentional sequence adapter with a keyed incremental source."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--edits", type=int, default=20)
    args = parser.parse_args()
    if args.rows < 1 or args.edits < 1:
        parser.error("rows and edits must be positive")
    print(
        json.dumps(
            {
                "environment": {
                    "python": platform.python_version(),
                    "system": platform.platform(),
                    "renderer": "headless; timings include profiling",
                },
                "results": [benchmark(args.rows, args.edits, mode) for mode in (False, True)],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
