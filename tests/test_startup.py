"""The startup timeline (RFC 0010): marks, the launch log line, and profiling gauges.

Marks are recorded once per process, so each scenario runs in a fresh
interpreter.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import textwrap

_PREAMBLE = """
import json, sys, types
import pythonnative as pn
from pythonnative import diagnostics, profiling
from pythonnative.bridge import set_transport
from pythonnative.bridge.fake import FakeTransport
from pythonnative.native_views import set_backend
from pythonnative.testing import FakeBackend

set_backend(FakeBackend())
set_transport(FakeTransport())
app = types.ModuleType("startup_app")
exec("import pythonnative as pn\\n@pn.component\\ndef App():\\n    return pn.Text('hi')\\n", app.__dict__)
sys.modules["startup_app"] = app
"""


def _run(body: str) -> subprocess.CompletedProcess[str]:
    script = _PREAMBLE + textwrap.dedent(body)
    return subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True)


def test_a_launch_records_every_phase_and_logs_one_line() -> None:
    result = _run("""
        profiler = profiling.Profiler()
        with profiler:
            assert list(diagnostics.startup_timeline()) == ["framework"]
            status = __import__("pythonnative.bootstrap").bootstrap.start(entry="startup_app")
            assert "error" not in status, status
            assert list(diagnostics.startup_timeline()) == ["framework", "contracts", "bridge", "app"]
            from pythonnative.hosts import create_screen

            first = create_screen("startup_app")
            first.on_create()
            second = create_screen("startup_app")
            second.on_create()
        print(json.dumps({"timeline": diagnostics.startup_timeline(), "gauges": profiler.gauges}))
        """)
    lines = result.stdout.splitlines()
    logged = [line for line in lines if line.startswith("[PN] startup:")]
    assert len(logged) == 1, result.stdout
    assert re.fullmatch(
        r"\[PN\] startup: framework \d+ ms, contracts \d+ ms, bridge \d+ ms, app \d+ ms, "
        r"render \d+ ms, commit \d+ ms, total \d+ ms",
        logged[0],
    )
    report = json.loads(lines[-1])
    timeline = report["timeline"]
    assert list(timeline) == [*("framework", "contracts", "bridge", "app", "render", "commit"), "total"]
    assert all(value >= 0 for value in timeline.values())
    assert timeline["total"] >= sum(value for key, value in timeline.items() if key != "total") * 0.99
    assert set(report["gauges"]) >= {"startup.contracts_ms", "startup.render_ms", "startup.commit_ms"}


def test_a_process_without_bootstrap_records_its_first_render_quietly() -> None:
    result = _run("""
        from pythonnative.hosts import create_screen

        create_screen("startup_app").on_create()
        print(json.dumps(diagnostics.startup_timeline()))
        """)
    assert "[PN] startup:" not in result.stdout
    assert list(json.loads(result.stdout.splitlines()[-1])) == ["framework", "render", "commit", "total"]


def test_a_commit_is_counted_only_after_the_render_it_follows() -> None:
    result = _run("""
        diagnostics.mark_startup("commit")
        assert "commit" not in diagnostics.startup_timeline()
        diagnostics.mark_startup("render", since=0.0)
        diagnostics.mark_startup("render")
        diagnostics.mark_startup("commit")
        print(json.dumps(diagnostics.startup_timeline()))
        """)
    timeline = json.loads(result.stdout.splitlines()[-1])
    assert list(timeline) == ["framework", "render", "commit", "total"]
    # ``since=0.0`` measures from the clock's origin, and the second render mark is ignored.
    assert timeline["render"] > timeline["framework"]
