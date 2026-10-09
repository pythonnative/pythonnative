"""The devtools agent: tree, inspection, state edits, REPL, network, problems, perf (RFC 0006)."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Iterator, List, Tuple

import pytest

import pythonnative as pn
from pythonnative import diagnostics, net
from pythonnative.devtools import inspector
from pythonnative.devtools.agent import Agent
from pythonnative.devtools.console import Console
from pythonnative.devtools.perf import Sampler
from pythonnative.testing import RenderResult, render, settle


@pytest.fixture(autouse=True)
def dev_mode(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(diagnostics, "_dev_mode", True)
    yield


@pn.component
def Counter(label: str) -> pn.Node:
    count, set_count = pn.use_state(0)
    ref = pn.use_ref("kept")
    doubled = pn.use_memo(lambda: count * 2, [count])
    pn.use_effect(lambda: None, [count])
    del ref, doubled
    return pn.Column(
        pn.Text(f"{label}: {count}"),
        pn.Button("Add", on_press=lambda: set_count(count + 1)),
    )


@pn.component
def App() -> pn.Node:
    return pn.Column(Counter(label="Taps").with_key("taps"))


def _reconcilers(result: RenderResult) -> List[Tuple[str, Any]]:
    return [("app.main", result.reconciler)]


def _find(screens: List[Dict[str, Any]], name: str) -> Dict[str, Any]:
    stack = [screen["root"] for screen in screens]
    while stack:
        node = stack.pop()
        if node["name"] == name:
            return node
        stack.extend(node["children"])
    raise AssertionError(f"{name} not in tree")


class Recorder:
    def __init__(self) -> None:
        self.events: List[Tuple[str, Any]] = []

    def __call__(self, topic: str, data: Any) -> None:
        self.events.append((topic, data))

    def topic(self, name: str) -> List[Any]:
        return [data for topic, data in self.events if topic == name]


# ======================================================================
# Inspector
# ======================================================================


def test_tree_lists_components_and_views_with_sources_and_keys() -> None:
    result = render(App())
    screens = inspector.tree(_reconcilers(result))
    counter = _find(screens, "Counter")
    assert counter["kind"] == "component"
    assert counter["key"] == "'taps'"
    assert counter["source"]["file"].endswith("test_devtools.py")
    assert not counter.get("framework")
    text = _find(screens, "Text")
    assert text["kind"] == "native" and text["tag"] > 0


def test_inspect_reports_props_hooks_and_path() -> None:
    result = render(App())
    counter = inspector.find_node(_find(inspector.tree(_reconcilers(result)), "Counter")["id"], _reconcilers(result))
    details = inspector.inspect_node(counter)
    assert details["props"]["label"] == {"type": "str", "repr": "'Taps'", "literal": True}
    hooks = details["hooks"]
    assert [hook["hook"] for hook in hooks] == ["use_state", "use_ref", "use_memo", "use_effect"]
    assert hooks[0]["value"]["repr"] == "0" and hooks[0]["editable"] is True
    assert hooks[1]["value"]["repr"] == "'kept'"
    assert hooks[2]["value"]["repr"] == "0"
    assert details["path"] == ["App", "Counter"]


def test_set_state_rerenders_with_a_literal() -> None:
    result = render(App())
    counter = inspector.find_node(_find(inspector.tree(_reconcilers(result)), "Counter")["id"], _reconcilers(result))
    inspector.set_state(counter, 0, "41")
    settle()
    assert result.get_by_text("Taps: 41")
    with pytest.raises(ValueError):
        inspector.set_state(counter, 0, "__import__('os')")
    with pytest.raises(ValueError):
        inspector.set_state(counter, 9, "1")


def test_find_node_by_tag_maps_views_back_to_nodes() -> None:
    result = render(App())
    text = _find(inspector.tree(_reconcilers(result)), "Text")
    node = inspector.find_node_by_tag(text["tag"], _reconcilers(result))
    assert node is not None and node.label == "Text"
    assert inspector.owner_component(node).label == "Counter"
    assert inspector.node_label_path(node) == ["App", "Counter", "Text"]


def test_summaries_are_short_and_safe() -> None:
    class Broken:
        def __repr__(self) -> str:
            raise RuntimeError("no")

    assert "repr failed" in inspector.summarize(Broken())["repr"]
    assert inspector.summarize(lambda: None)["type"] == "function"
    big = inspector.summarize(list(range(100)))
    assert big["repr"] == "list(100)" and big["more"] is True and len(big["items"]) == 25
    assert inspector.summarize("x" * 1000)["repr"].endswith("…")
    assert inspector.summarize(pn.Text("hi"))["repr"] == "<Text>"


# ======================================================================
# Console
# ======================================================================


def test_console_evaluates_expressions_statements_and_await() -> None:
    console = Console()

    async def run() -> List[Dict[str, Any]]:
        return [
            await console.evaluate("1 + 1"),
            await console.evaluate("x = 5"),
            await console.evaluate("x * 2"),
            await console.evaluate("await asyncio.sleep(0, result='slept')"),
            await console.evaluate("1 / 0"),
            await console.evaluate("def ("),
        ]

    two, assign, ten, slept, error, syntax = asyncio.run(run())
    assert two == {"ok": True, "repr": "2", "type": "int"}
    assert assign["repr"] is None
    assert ten["repr"] == "10"
    assert slept["repr"] == "'slept'"
    assert error["ok"] is False and "ZeroDivisionError" in error["error"]
    assert syntax["ok"] is False and "SyntaxError" in syntax["error"]
    assert console.namespace["pn"] is pn


def test_console_node_handle_reads_and_sets_state() -> None:
    result = render(App())
    counter = inspector.find_node(_find(inspector.tree(_reconcilers(result)), "Counter")["id"], _reconcilers(result))
    console = Console()
    console.select(counter)

    async def run() -> Dict[str, Any]:
        await console.evaluate("node.set_state(0, 7)")
        return await console.evaluate("node.props['label'], node.name")

    answer = asyncio.run(run())
    settle()
    assert answer["repr"] == "('Taps', 'Counter')"
    assert result.get_by_text("Taps: 7")


# ======================================================================
# Agent
# ======================================================================


def test_agent_publishes_warnings_and_errors_as_problems() -> None:
    recorder = Recorder()
    agent = Agent(recorder)
    agent.start()
    try:
        diagnostics.warn("careful")
        diagnostics.notify_error(ValueError("bad"), "render")
    finally:
        agent.stop()
    problems = recorder.topic("problem")
    assert [problem["level"] for problem in problems] == ["warning", "error"]
    assert problems[1]["title"] == "ValueError in render: bad"
    diagnostics.warn("after stop")
    assert len(recorder.topic("problem")) == 2


def test_agent_records_fetch_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = Recorder()
    agent = Agent(recorder)
    agent.start()

    def fake_dispatch(request: Any, timeout: float) -> net.Response:
        return net.Response(status=201, url=request.full_url, headers={"X": "1"}, content=b'{"ok": true}')

    monkeypatch.setattr(net, "_dispatch_request", fake_dispatch)
    try:
        response = asyncio.run(pn.fetch("https://example.com/items", method="POST", body={"a": 1}))
    finally:
        agent.stop()
    assert response.status == 201
    start, end = recorder.topic("network")
    assert start["phase"] == "start" and start["method"] == "POST" and start["request_body"] == '{"a": 1}'
    assert end["phase"] == "end" and end["status"] == 201 and end["response_body"] == '{"ok": true}'
    assert start["id"] == end["id"]


def test_agent_requests_run_on_the_loop_and_report_errors() -> None:
    agent = Agent(Recorder())

    async def run() -> Tuple[Any, str]:
        status = await agent.request("status")
        try:
            await agent.request("nope")
        except RuntimeError as exc:
            return status, str(exc)
        return status, ""

    status, error = asyncio.run(run())
    assert status["kind"] == "app" and status["inspecting"] is False
    assert "unknown devtools method" in error


def test_menu_items_follow_state_and_kind() -> None:
    agent = Agent(Recorder(), kind="go", disconnect=lambda: None)
    titles = [item.title for item in agent.menu_items()]
    assert titles[0] == "Reload"
    assert "Show element inspector" in titles and "Disconnect" in titles
    agent.inspecting = True
    assert "Hide element inspector" in [item.title for item in agent.menu_items()]
    assert "Disconnect" not in [item.title for item in Agent(Recorder()).menu_items()]


def test_open_devtools_menu_item_publishes() -> None:
    recorder = Recorder()
    agent = Agent(recorder)
    next(item for item in agent.menu_items() if item.title.startswith("Open DevTools")).action()
    assert recorder.topic("open_devtools") == [{}]


# ======================================================================
# Perf
# ======================================================================


def test_sampler_summarizes_render_and_commit_phases() -> None:
    import time

    from pythonnative import profiling

    sampler = Sampler(lambda sample: None)
    sampler._install()
    try:
        started = time.perf_counter()
        result = render(App())
        result.press(result.get_by_text("Add"))
        sample = sampler._summarize(started, time.perf_counter(), {})
    finally:
        sampler._uninstall()
    assert profiling._session is None
    assert sample["phases"]["render"]["count"] >= 1
    assert sample["phases"]["component"]["count"] >= 2
    assert sample["components_rendered"] >= 2
    sampler.latest = {**sample, "loop_lag_ms": 3.0}
    lines = sampler.monitor_lines()
    assert lines[0] == "PY lag 3 ms" and lines[1].startswith("renders ")


def test_sampler_publishes_every_second_while_acquired() -> None:
    samples: List[Dict[str, Any]] = []

    async def run() -> None:
        sampler = Sampler(samples.append, lambda: {"fps": 60.0, "dropped": 0})
        sampler.acquire()
        await asyncio.sleep(1.1)
        sampler.release()

    asyncio.run(run())
    assert samples and samples[0]["ui_fps"] == 60.0 and samples[0]["loop_lag_ms"] >= 0


def test_trace_capture_returns_a_chrome_trace() -> None:
    sampler = Sampler(lambda sample: None)
    sampler.start_trace()
    render(App())
    document = sampler.stop_trace()
    names = {event["name"] for event in document["traceEvents"]}
    assert "render" in names or "component" in names
    from pythonnative import profiling

    assert profiling._session is None
