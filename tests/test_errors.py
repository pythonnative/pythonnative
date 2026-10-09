"""Structured error reports and component stacks (RFC 0006)."""

from __future__ import annotations

import traceback
from typing import Any, Iterator, List

import pytest

import pythonnative as pn
from pythonnative import diagnostics
from pythonnative.errors import (
    ComponentFrame,
    add_component_frame,
    complete_component_stack,
    component_stack,
    report,
    warning_report,
)
from pythonnative.testing import render


@pytest.fixture(autouse=True)
def dev_mode(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(diagnostics, "_dev_mode", True)
    yield


@pn.component
def Divide(n: int) -> pn.Node:
    return pn.Text(str(1 / n))


@pn.component
def Middle() -> pn.Node:
    return pn.Column(Divide(n=0))


@pn.component
def Root() -> pn.Node:
    return pn.Column(Middle())


def _raised(element: Any) -> BaseException:
    with pytest.raises(ZeroDivisionError) as info:
        render(element)
    return info.value


def test_render_errors_carry_the_component_path_innermost_first() -> None:
    exc = _raised(Root())
    assert [frame.name for frame in component_stack(exc)] == ["Divide", "Middle", "Root"]


def test_component_frames_point_at_their_definitions() -> None:
    exc = _raised(Root())
    divide = component_stack(exc)[0]
    assert divide.file.endswith("test_errors.py")
    assert divide.line == Divide.fn.__code__.co_firstlineno


def test_the_component_path_is_a_traceback_note() -> None:
    exc = _raised(Root())
    text = "".join(traceback.format_exception(exc))
    assert "The above error occurred in <Divide>" in text
    assert "  in <Middle>" in text
    assert "  in <Root>" in text
    # One note, rewritten as frames were added.
    assert sum("The above error occurred" in note for note in exc.__notes__) == 1


def test_update_errors_complete_the_stack_from_mounted_ancestors() -> None:
    @pn.component
    def Toggle() -> pn.Node:
        broken, set_broken = pn.use_state(False)
        if broken:
            raise ValueError("toggled")
        return pn.Button("Break", on_press=lambda: set_broken(True))

    @pn.component
    def Shell() -> pn.Node:
        return pn.Column(Toggle())

    caught: List[BaseException] = []

    @pn.component
    def Guarded() -> pn.Node:
        return pn.ErrorBoundary(Shell(), fallback=pn.Text("broken"), on_error=caught.append)

    result = render(Guarded())
    result.press(result.get_by_text("Break"))
    assert result.get_by_text("broken")
    assert [frame.name for frame in component_stack(caught[0])] == ["Toggle", "Shell", "Guarded"]


def test_effect_errors_carry_the_effects_component() -> None:
    @pn.component
    def Effectful() -> pn.Node:
        def effect() -> None:
            raise RuntimeError("effect failed")

        pn.use_effect(effect, [])
        return pn.Text("hi")

    @pn.component
    def Holder() -> pn.Node:
        return pn.Column(Effectful())

    with pytest.raises(RuntimeError) as info:
        render(Holder())
    assert [frame.name for frame in component_stack(info.value)] == ["Effectful", "Holder"]


def test_release_mode_adds_no_component_stack(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diagnostics, "_dev_mode", False)
    exc = _raised(Root())
    assert component_stack(exc) == ()
    assert not getattr(exc, "__notes__", [])


def test_frames_are_classified_and_app_frames_carry_excerpts() -> None:
    exc = _raised(Root())
    result = report(exc, "render")
    assert result.title == "ZeroDivisionError in render: division by zero"
    assert result.type == "ZeroDivisionError"
    framework = [frame for frame in result.frames if frame.framework]
    app = [frame for frame in result.frames if not frame.framework]
    assert any("reconciler" in frame.file for frame in framework)
    failing = app[-1]
    assert failing.function == "Divide"
    assert failing.code == "return pn.Text(str(1 / n))"
    assert failing.line in [number for number, _text in failing.excerpt]
    assert f"> {failing.line}" in failing.excerpt_text()


def test_report_round_trips_to_json_shape() -> None:
    data = report(_raised(Root()), "render").to_dict()
    assert data["level"] == "error"
    assert data["component_stack"][0]["name"] == "Divide"
    assert {"file", "line", "function", "code", "title", "excerpt", "framework"} <= set(data["frames"][0])
    assert "ZeroDivisionError" in data["text"]


def test_complete_component_stack_stops_further_frames() -> None:
    exc = RuntimeError("x")
    add_component_frame(exc, Divide)
    complete_component_stack(exc, [Divide, Middle])
    add_component_frame(exc, Root)
    assert [frame.name for frame in component_stack(exc)] == ["Divide", "Middle"]


def test_warning_reports_name_the_rendering_component() -> None:
    reports: List[Any] = []
    remove = diagnostics.add_listener(reports.append)
    try:

        @pn.component
        def Warns() -> pn.Node:
            diagnostics.warn("watch out")
            return pn.Text("x")

        render(Warns())
    finally:
        remove()
    warning = next(item for item in reports if item.level == "warning")
    assert warning.message == "watch out"
    assert [frame.name for frame in warning.component_stack] == ["Warns"]
    assert warning_report("plain").component_stack == ()


def test_component_frame_describe() -> None:
    assert ComponentFrame("A", "app/main.py", 3).describe() == "<A> (app/main.py:3)"
    assert ComponentFrame("A").describe() == "<A>"
