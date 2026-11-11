#!/usr/bin/env python3
"""Measure startup and rendering costs as JSON (RFC 0005).

Run ``python scripts/benchmark-runtime.py [--output report.json]``. The
numbers are host timings for comparing changes on one machine, not device
measurements: ``import pythonnative`` in a fresh interpreter, element
construction, re-rendering a 300-component tree headlessly, and a first
commit of 300 views to the renderer core (validation, layout, and the
mount transaction, RFC 0007), and one display frame of the motion runtime
driving 200 animated styles from a running spring (RFC 0009).
``tests/test_performance_budgets.py`` enforces the deterministic properties
behind these timings.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
import time
from typing import Any, Callable

import pythonnative as pn
from pythonnative import diagnostics
from pythonnative.bridge import codec, contract_document
from pythonnative.bridge.core import PROTOCOL_VERSION, load_core
from pythonnative.testing import render

_IMPORT = "import time; t = time.perf_counter(); import pythonnative; print(time.perf_counter() - t)"


def import_seconds(runs: int) -> list[float]:
    """Time ``import pythonnative`` in fresh interpreters with warm bytecode."""
    subprocess.run([sys.executable, "-c", "import pythonnative"], check=True)
    return [
        float(subprocess.run([sys.executable, "-c", _IMPORT], capture_output=True, text=True, check=True).stdout)
        for _ in range(runs)
    ]


@pn.component
def Cell(label: str, n: int) -> pn.Node:
    """A typical leaf component: state, an effect, and a few native views."""
    value, _set_value = pn.use_state(0)
    pn.use_effect(lambda: None, [n])
    return pn.Row(pn.Text(label), pn.Text(str(n + value)), style=pn.style(padding=4))


@pn.component
def Grid(n: int) -> pn.Node:
    """300 keyed cells whose props change on every render."""
    return pn.Column(*(Cell(f"cell {i}", n).with_key(str(i)) for i in range(300)))


def per_call_ms(action: Callable[[int], Any], repeat: int, rounds: int = 5) -> list[float]:
    """Milliseconds per call of ``action`` across ``rounds`` timed rounds."""
    action(0)
    samples = []
    for round_index in range(rounds):
        started = time.perf_counter()
        for index in range(repeat):
            action(round_index * repeat + index + 1)
        samples.append((time.perf_counter() - started) * 1000 / repeat)
    return samples


def commit_envelope(views: int) -> dict[str, Any]:
    """A first commit that mounts ``views`` text views under one container and lays them out."""
    ops: list[list[Any]] = [["c", 1, "View", {"flex": 1}]]
    for tag in range(2, views + 2):
        ops += [["c", tag, "Text", {"text": f"row {tag}", "font_size": 14}], ["i", 1, tag, tag - 2]]
    layout = {"roots": [1], "width": 390, "height": 844, "selective": True}
    return {
        "version": PROTOCOL_VERSION,
        "application": "bench",
        "surface": 1,
        "revision": 1,
        "ops": ops,
        "layout": layout,
    }


def core_committer(envelope: dict[str, Any]) -> Callable[[int], Any]:
    """Commit ``envelope`` as a fresh application each call and take its mount transaction."""
    from pythonnative.bridge.fake import FakeTransport

    transport = FakeTransport(surface=envelope["surface"])
    transport.load_contracts(contract_document())
    core = load_core()

    def commit(index: int) -> None:
        text = codec.dumps(envelope | {"application": f"bench-{index}"})
        if not codec.loads(core.commit(text)).get("ok"):
            raise RuntimeError("The renderer core rejected the benchmark commit")
        while (transaction := core.mount_next()) is not None:
            core.mount_finished(transaction[1])

    return commit


_driver: list[Any] = []


@pn.component
def Moving(index: int) -> pn.Node:
    """A view whose animated style reads the shared driver every frame."""
    style = pn.use_animated_style(
        lambda: {
            "opacity": pn.interpolate(_driver[0].value, (0, 100), (0.2, 1), "clamp"),
            "transform": [{"translate_x": _driver[0].value * 0.5}, {"rotate": _driver[0].value / 10}],
        }
    )
    return pn.View(style=[{"width": 10, "height": 10}, style])


@pn.component
def Field() -> pn.Node:
    """200 views, each with its own animated style worklet."""
    driver = pn.use_shared_value(0.0)
    _driver[:] = [driver]
    return pn.Column(*(Moving(i).with_key(str(i)) for i in range(200)))


def motion_frame_us(frames: int = 120) -> list[float]:
    """Microseconds per display frame: one spring step, then 200 animated style worklets and their writes."""
    tree = render(Field())
    core = tree.backend.native.core
    from pythonnative.motion.runtime import runtime as motion

    _driver[0].value = pn.with_spring(100, stiffness=40, damping=4)
    motion.flush_all()
    tree.backend.native.drain()
    runs = core.motion(tree.backend.surface, '{"op": "batch", "requests": []}')
    assert '"ok":true' in runs.replace(" ", ""), runs
    import ctypes

    from pythonnative.bridge.core import _Bytes

    samples = []
    buffer = _Bytes()
    for index in range(frames):
        started = time.perf_counter()
        running = core.animation_frame(1000 + index * 1000 / 60)
        # The platform reads the writes natively; take them without decoding them in Python.
        core._take_writes(core._handle, ctypes.byref(buffer))
        if running:
            samples.append((time.perf_counter() - started) * 1e6)
    assert core.shared_read(_driver[0].id) != "0.0", "the spring never ran"
    tree.unmount()
    return samples


def summary(samples: list[float]) -> dict[str, float]:
    """Median and best of a set of samples."""
    return {"median": round(statistics.median(samples), 3), "min": round(min(samples), 3)}


def main() -> None:
    """Measure, print, and optionally save the report."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", help="Write the JSON report to this path")
    parser.add_argument("--imports", type=int, default=9, help="Fresh interpreters to time")
    args = parser.parse_args()

    diagnostics.set_dev_mode(False)
    tree = render(Grid(0), viewport=None)
    envelope = commit_envelope(300)
    report = {
        "environment": {
            "python": platform.python_version(),
            "system": platform.platform(),
            "machine": platform.machine(),
        },
        "import_ms": summary([seconds * 1000 for seconds in import_seconds(args.imports)]),
        "element_us": summary([ms * 1000 for ms in per_call_ms(lambda i: Cell(f"cell {i}", i), 2000)]),
        "rerender_300_ms": summary(per_call_ms(lambda i: tree.rerender(Grid(i)), 5)),
        "core_commit_300_ms": summary(per_call_ms(core_committer(envelope), 20)),
        "motion_frame_200_styles_us": summary(motion_frame_us()),
    }
    text = json.dumps(report, indent=2)
    print(text)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")


if __name__ == "__main__":
    main()
