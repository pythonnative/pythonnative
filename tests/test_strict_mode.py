"""``pn.StrictMode`` (RFC 0010): double renders and double effects in development."""

from __future__ import annotations

from typing import Any, Callable, Dict, List

import pytest

import pythonnative as pn
from pythonnative import diagnostics
from pythonnative.testing import render

log: List[str] = []
handles: Dict[str, Any] = {}


@pytest.fixture(autouse=True)
def _clear() -> Any:
    log.clear()
    handles.clear()
    yield
    diagnostics.set_dev_mode(True)


def note(event: str, value: Any = None) -> Any:
    log.append(event)
    return value


@pn.component
def Probe(label: str) -> pn.Node:
    log.append(f"body {label}")
    count, set_count = pn.use_state(lambda: note("init", 0))
    total, dispatch = pn.use_reducer(lambda state, action: note("reduce", state + action), 0)
    doubled = pn.use_memo(lambda: note("memo", count * 2), [count])

    def effect() -> Callable[[], None]:
        log.append("effect")
        return lambda: log.append("cleanup")

    def layout_effect() -> Callable[[], None]:
        log.append("layout effect")
        return lambda: log.append("layout cleanup")

    pn.use_effect(effect, [])
    pn.use_layout_effect(layout_effect, [])
    handles["increment"] = lambda: set_count(lambda value: note("updater", value + 1))
    handles["dispatch"] = dispatch
    return pn.Text(f"{label} {count} {doubled} {total}")


def test_strict_mode_runs_bodies_initializers_memos_and_mount_effects_twice() -> None:
    diagnostics.set_dev_mode(True)
    result = render(pn.StrictMode(Probe("a")))
    assert log.count("body a") == 2
    assert log.count("init") == 2
    assert log.count("memo") == 2
    assert log[-6:] == ["layout effect", "layout cleanup", "layout effect", "effect", "cleanup", "effect"]
    assert result.text() == ["a 0 0 0"]


def test_strict_mode_runs_updaters_and_reducers_twice_but_not_update_effects() -> None:
    diagnostics.set_dev_mode(True)
    result = render(pn.StrictMode(pn.Column(Probe("a"))))
    log.clear()
    handles["increment"]()
    handles["dispatch"](5)
    result.settle()
    assert log.count("updater") == 2
    assert log.count("reduce") == 2
    assert log.count("body a") == 2
    assert "effect" not in log and "cleanup" not in log
    assert result.text() == ["a 1 2 5"]


def test_strict_mode_does_nothing_in_release_builds() -> None:
    diagnostics.set_dev_mode(False)
    render(pn.StrictMode(Probe("a")))
    assert log.count("body a") == 1
    assert log.count("init") == 1
    assert log.count("effect") == 1 and "cleanup" not in log


def test_components_outside_strict_mode_render_once() -> None:
    diagnostics.set_dev_mode(True)
    render(pn.Column(Probe("outside"), pn.StrictMode(Probe("inside"))))
    assert log.count("body outside") == 1
    assert log.count("body inside") == 2


def test_strict_mode_adds_no_native_view() -> None:
    diagnostics.set_dev_mode(True)
    result = render(pn.Column(pn.StrictMode(pn.Text("a"), pn.Text("b")), pn.Text("c")))
    root = result.backend.views[result.reconciler.root_tag]
    assert [child.type_name for child in root.children] == ["Text", "Text", "Text"]


def test_strict_mode_surfaces_an_impure_body() -> None:
    diagnostics.set_dev_mode(True)
    rendered: List[int] = []

    @pn.component
    def Impure() -> pn.Node:
        rendered.append(len(rendered))
        return pn.Text(f"renders {len(rendered)}")

    result = render(pn.StrictMode(Impure()))
    assert result.text() == ["renders 2"], "the body's side effect happens twice"
