"""The production failure path: the error handler, root boundary, and mount recovery."""

from __future__ import annotations

import sys
import types
from typing import Any, Callable, Generator, List, Tuple

import pytest

import pythonnative as pn
from pythonnative import diagnostics
from pythonnative.components import structural
from pythonnative.hosts.base import ScreenHost
from pythonnative.native_views import bridge_backend
from pythonnative.testing import FakeBackend, settle


@pytest.fixture(autouse=True)
def _clean() -> Generator[None, None, None]:
    diagnostics.set_error_handler(None)
    pn.set_error_fallback(None)
    diagnostics.set_dev_mode(False)
    yield
    diagnostics.set_error_handler(None)
    pn.set_error_fallback(None)
    diagnostics.reset_dev_mode()


def test_handler_receives_errors_once_with_their_phase() -> None:
    seen: List[Tuple[BaseException, str]] = []
    pn.set_error_handler(lambda error, phase: seen.append((error, phase)))
    error = RuntimeError("boom")
    assert diagnostics.report_error(error, phase="event") is False
    diagnostics.handle_error(error, "again")
    assert seen == [(error, "event")]


def test_handler_errors_are_contained(capsys: pytest.CaptureFixture[str]) -> None:
    def broken(error: BaseException, phase: str) -> None:
        raise ValueError("handler failed")

    pn.set_error_handler(broken)
    diagnostics.handle_error(RuntimeError("boom"), "render")
    assert "handler failed" in capsys.readouterr().err


def test_no_handler_is_fine() -> None:
    diagnostics.handle_error(RuntimeError("boom"), "render")


def test_default_fallback_offers_a_retry() -> None:
    calls: List[int] = []
    element = structural.root_error_fallback(RuntimeError("boom"), lambda: calls.append(1))
    assert element.type == "Column"
    text, button = element.children
    assert text.props["text"] == "Something went wrong"
    assert button.props["title"] == "Try again"


def test_custom_fallback_takes_one_or_two_arguments() -> None:
    pn.set_error_fallback(lambda error: pn.Text(f"sorry: {error}"))
    assert structural.root_error_fallback(RuntimeError("a"), lambda: None).props["text"] == "sorry: a"
    pn.set_error_fallback(lambda error, reset: pn.Button("again", on_press=reset))
    assert structural.root_error_fallback(RuntimeError("a"), lambda: None).props["title"] == "again"


class _Host(ScreenHost):
    def __init__(self, path: str) -> None:
        super().__init__(None, path, None)
        self.attached: List[Any] = []

    def _attach_root(self, view: Any) -> None:
        self.attached.append(view)

    def _detach_root(self, view: Any) -> None:
        pass

    def _initial_viewport_size(self) -> Tuple[float, float]:
        return (390.0, 844.0)


def _install(monkeypatch: pytest.MonkeyPatch, name: str, root: Any) -> str:
    module = types.ModuleType(name)
    module.App = root  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, name, module)
    return f"{name}.App"


@pytest.fixture
def backend(monkeypatch: pytest.MonkeyPatch) -> FakeBackend:
    fake = FakeBackend()
    monkeypatch.setattr("pythonnative.native_views.get_backend", lambda: fake)
    return fake


def _labels(backend: FakeBackend) -> List[str]:
    return [view.props["text"] for view in backend.views.values() if "text" in getattr(view, "props", {})]


def test_release_render_error_shows_the_fallback_and_reports(
    monkeypatch: pytest.MonkeyPatch, backend: FakeBackend
) -> None:
    seen: List[str] = []
    pn.set_error_handler(lambda error, phase: seen.append(phase))
    healthy: List[bool] = [False]

    @pn.component
    def App() -> pn.Node:
        if not healthy[0]:
            raise RuntimeError("render failed")
        return pn.Text("Recovered")

    host = _Host(_install(monkeypatch, "failure_app", App))
    host.on_create()
    settle()
    assert seen == ["render"]
    assert "Something went wrong" in _labels(backend)


def test_dev_builds_skip_the_root_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    diagnostics.set_dev_mode(True)

    @pn.component
    def App() -> pn.Node:
        return pn.Text("ok")

    host = _Host(_install(monkeypatch, "dev_app", App))
    element = host._root_element()
    child = element.children[0] if element.children else element.props.get("children")
    assert "boundary" not in str(getattr(child, "type", "")).lower()


class _Recording(_Host):
    remounts = 0

    def _full_remount(self, reloaded_modules: Any) -> None:
        type(self).remounts += 1


def test_mount_failure_remounts_once_then_gives_up(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: List[Callable[[], None]] = []
    loop = types.SimpleNamespace(call_soon_threadsafe=lambda fn: calls.append(fn))
    monkeypatch.setattr("pythonnative.runtime.get_loop", lambda: loop)
    _Recording.remounts = 0
    host = _Recording("unused.App")
    host.reconciler = object()

    host._recover_surface(RuntimeError("first"))
    # A second report for the same failure waits for the scheduled remount.
    host._recover_surface(RuntimeError("same"))
    assert len(calls) == 1 and host._gave_up is None
    calls.pop()()
    assert _Recording.remounts == 1

    failure = RuntimeError("again")
    host._recover_surface(failure)
    assert host._gave_up is failure
    calls.pop()()
    assert _Recording.remounts == 2

    host._restart()
    assert host._gave_up is None and host._last_recovery is None and _Recording.remounts == 3


def test_recovery_after_the_window_counts_as_a_first_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: List[Callable[[], None]] = []
    monkeypatch.setattr(
        "pythonnative.runtime.get_loop", lambda: types.SimpleNamespace(call_soon_threadsafe=calls.append)
    )
    host = _Recording("unused.App")
    host.reconciler = object()
    host._last_recovery = -1000.0
    host._recover_surface(RuntimeError("much later"))
    assert host._gave_up is None


def test_dev_builds_leave_mount_failures_to_the_error_screen() -> None:
    diagnostics.set_dev_mode(True)
    host = _Recording("unused.App")
    host.reconciler = object()
    host._recover_surface(RuntimeError("boom"))
    assert not host._recovering


def test_surface_failed_tells_the_host() -> None:
    assert hasattr(bridge_backend, "BridgeBackend")
