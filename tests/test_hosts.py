"""Tests for screen-host lifecycle behavior (``pythonnative.hosts``).

Off-device the host class is the headless ``ScreenHost``; these tests
drive it against a ``FakeBackend`` installed as the process registry.
The on-device host is covered by ``test_bridge.py`` through a
``FakeTransport``.
"""

import os
import sys
import types
from pathlib import Path
from typing import Any, Iterator, List, Optional

import pytest

from pythonnative import diagnostics
from pythonnative.component import component
from pythonnative.element import Element
from pythonnative.hooks import use_back_handler, use_effect, use_state
from pythonnative.hosts import ScreenHost, create_screen, import_component
from pythonnative.native_views import set_registry
from pythonnative.testing import FakeBackend, FakeView


@pytest.fixture
def backend() -> Iterator[FakeBackend]:
    """Install a ``FakeBackend`` as the registry the host mounts into."""
    fake = FakeBackend()
    set_registry(fake)
    try:
        yield fake
    finally:
        set_registry(None)


def _install_app_module(monkeypatch: pytest.MonkeyPatch, name: str, root: Any) -> str:
    """Register an in-memory module exposing ``root`` as its ``App``."""
    module = types.ModuleType(name)
    module.App = root  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, name, module)
    return name


def _text_of(view: Optional[FakeView]) -> List[str]:
    return [v.text for v in view.walk() if v.text is not None] if view is not None else []


def _write_screen(path: Path, text: str) -> None:
    path.write_text(
        "from pythonnative.component import component\n"
        "from pythonnative.element import Element\n\n"
        "@component\n"
        "def MainPage():\n"
        f"    return Element('Text', {{'text': {text!r}}}, [])\n",
        encoding="utf-8",
    )


# ======================================================================
# Hot reload
# ======================================================================


def test_screen_reload_reimports_root_component(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    backend: FakeBackend,
) -> None:
    package_dir = tmp_path / "reload_app"
    package_dir.mkdir()
    screen_path = package_dir / "screen.py"
    _write_screen(screen_path, "before")

    monkeypatch.syspath_prepend(os.fspath(tmp_path))
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    sys.modules.pop("reload_app.screen", None)
    sys.modules.pop("reload_app", None)

    host = create_screen("reload_app.screen.MainPage")
    host.on_create()
    assert _text_of(host.root_native_view) == ["before"]

    _write_screen(screen_path, "after")
    host.reload(["reload_app.screen"])

    assert _text_of(host.root_native_view) == ["after"]
    host.on_destroy()


# ======================================================================
# Lifecycle
# ======================================================================


def test_screen_host_on_destroy_unmounts_tree(monkeypatch: pytest.MonkeyPatch, backend: FakeBackend) -> None:
    """``on_destroy`` must unmount the reconciler: cleanups run, views die."""
    cleanups: list = []

    @component
    def Root() -> Element:
        use_effect(lambda: lambda: cleanups.append("cleaned"), [])
        return Element("Text", {"text": "hi"}, [])

    host = create_screen(_install_app_module(monkeypatch, "destroy_app", Root))
    host.on_create()
    assert host.reconciler is not None
    assert backend.live_view_count() > 0
    assert cleanups == []

    host.on_destroy()
    assert cleanups == ["cleaned"], "effect cleanup must run on destroy"
    assert host.reconciler is None
    assert host.root_native_view is None
    assert backend.live_view_count() == 0


def test_screen_host_on_create_is_idempotent_across_view_recreation(
    monkeypatch: pytest.MonkeyPatch, backend: FakeBackend
) -> None:
    """Android recreates a fragment's view on pop-back; the tree must persist."""
    mounts: list = []

    @component
    def Root() -> Element:
        use_effect(lambda: mounts.append("mounted"), [])
        return Element("Text", {"text": "hi"}, [])

    host = create_screen(_install_app_module(monkeypatch, "recreate_app", Root))
    host.on_create()
    reconciler, root = host.reconciler, host.root_native_view

    host.on_create()
    assert host.reconciler is reconciler
    assert host.root_native_view is root
    assert mounts == ["mounted"]
    host.on_destroy()


def test_screen_host_focus_and_args(monkeypatch: pytest.MonkeyPatch, backend: FakeBackend) -> None:
    """``on_pause`` / ``on_resume`` drive focus listeners; ``set_args`` accepts JSON."""

    @component
    def Root() -> Element:
        return Element("Text", {"text": "hi"}, [])

    host = create_screen(_install_app_module(monkeypatch, "focus_app", Root), None, '{"pn_nav": {"routes": []}}')
    assert host.args == {"pn_nav": {"routes": []}}
    assert host.initial_navigation_state() is None, "an empty route list is not a navigation state"

    host.set_args("not json")
    assert host.args == {}
    host.set_args({"k": 1})
    assert host.args == {"k": 1}

    seen: List[bool] = []
    remove = host.add_focus_listener(seen.append)
    host.on_create()
    assert host.is_focused is True

    host.on_pause()
    host.on_pause()
    host.on_resume()
    assert seen == [False, True], "focus listeners fire once per transition"

    remove()
    host.on_pause()
    assert seen == [False, True]
    host.on_destroy()


def test_screen_host_on_back_pressed_routes_to_handlers(monkeypatch: pytest.MonkeyPatch, backend: FakeBackend) -> None:
    """``on_back_pressed`` consults ``use_back_handler`` subscribers."""
    consume = {"value": True}

    @component
    def Root() -> Element:
        _count, _set_count = use_state(0)
        use_back_handler(lambda: consume["value"])
        return Element("Text", {"text": "hi"}, [])

    host = create_screen(_install_app_module(monkeypatch, "back_app", Root))
    host.on_create()
    assert host.on_back_pressed() is True

    consume["value"] = False
    assert host.on_back_pressed() is False

    host.on_destroy()
    assert host.on_back_pressed() is False, "destroyed host must decline back events"


def test_every_host_class_exposes_on_layout() -> None:
    """Regression: every host class must accept an ``on_layout`` callback.

    The iOS template forwards ``viewDidLayoutSubviews`` as
    ``on_layout`` so the screen host can re-push the safe-area-aware
    viewport size; missing the method on the base or native classes
    would raise ``AttributeError`` at runtime.
    """
    from pythonnative.hosts.native import NativeScreenHost

    for host_class in (ScreenHost, NativeScreenHost):
        assert callable(getattr(host_class, "on_layout", None))


def test_screen_host_on_layout_is_idempotent(monkeypatch: pytest.MonkeyPatch, backend: FakeBackend) -> None:
    @component
    def Root() -> Element:
        return Element("Text", {"text": "hi"}, [])

    host = create_screen(_install_app_module(monkeypatch, "layout_app", Root))
    host.on_create()
    host.on_layout()
    host.on_layout()
    assert _text_of(host.root_native_view) == ["hi"]
    host.on_destroy()


# ======================================================================
# Viewport
# ======================================================================


def test_set_viewport_size_forwards_to_reconciler(monkeypatch: pytest.MonkeyPatch, backend: FakeBackend) -> None:
    @component
    def Root() -> Element:
        return Element("Column", {}, [Element("Text", {"text": "hi"}, [])])

    host = create_screen(_install_app_module(monkeypatch, "viewport_app", Root))
    host.set_viewport_size(390, 844)  # before mount: nothing to forward to
    host.on_create()
    assert host.reconciler is not None
    assert backend.ops_of("set_frame") == [], "the headless host supplies no viewport, so no layout yet"

    host.set_viewport_size(390, 844)
    assert host.reconciler.viewport_size == (390.0, 844.0)
    # The root's own frame is owned by the platform host; children get laid out to the viewport width.
    text = host.root_native_view.find_first("Text")
    assert text is not None and text.frame[2] == 390.0

    host.set_viewport_size(0, 844)
    assert host.reconciler.viewport_size == (390.0, 844.0), "non-positive sizes are ignored"
    host.on_destroy()


# ======================================================================
# RedBox
# ======================================================================


def test_mount_error_shows_redbox_in_dev_mode(monkeypatch: pytest.MonkeyPatch, backend: FakeBackend) -> None:
    monkeypatch.setattr(diagnostics, "_dev_mode", True)

    @component
    def Root() -> Element:
        raise RuntimeError("kaboom")

    host = create_screen(_install_app_module(monkeypatch, "redbox_app", Root))
    host.on_create()

    assert host._redbox_reconciler is not None
    overlay = _text_of(host._redbox_root)
    assert "RuntimeError in mount" in overlay
    assert "kaboom" in overlay

    host.clear_redbox()
    assert host._redbox_reconciler is None
    assert host._redbox_root is None
    host.on_destroy()


def test_render_error_shows_redbox_and_dismiss_restores_tree(
    monkeypatch: pytest.MonkeyPatch, backend: FakeBackend
) -> None:
    monkeypatch.setattr(diagnostics, "_dev_mode", True)
    setter: dict = {}

    @component
    def Root() -> Element:
        broken, set_broken = use_state(False)
        setter["set"] = set_broken
        if broken:
            raise RuntimeError("render broke")
        return Element("Text", {"text": "fine"}, [])

    host = create_screen(_install_app_module(monkeypatch, "redbox_render_app", Root))
    host.on_create()
    assert host._redbox_reconciler is None
    assert _text_of(host.root_native_view) == ["fine"]

    setter["set"](True)
    assert host._redbox_reconciler is not None
    assert "RuntimeError in render" in _text_of(host._redbox_root)

    dismiss = host._redbox_root.find_first("Button")
    assert dismiss is not None and dismiss.text == "Dismiss"
    host.clear_redbox()
    assert host._redbox_reconciler is None
    host.on_destroy()


def test_mount_error_propagates_outside_dev_mode(monkeypatch: pytest.MonkeyPatch, backend: FakeBackend) -> None:
    monkeypatch.setattr(diagnostics, "_dev_mode", False)

    @component
    def Root() -> Element:
        raise RuntimeError("kaboom")

    host = create_screen(_install_app_module(monkeypatch, "redbox_off_app", Root))
    with pytest.raises(RuntimeError, match="kaboom"):
        host.on_create()
    assert host._redbox_reconciler is None
    host.on_destroy()


# ======================================================================
# Component resolution
# ======================================================================


def test_import_component_propagates_real_dependency_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing import *inside* the app must not be masked.

    Regression: ``import_component`` caught every ``ModuleNotFoundError``
    and reported a generic "could not resolve component", hiding the real
    cause (e.g. a dependency the developer forgot to install). The actual
    error must propagate, while a genuinely absent path still yields the
    friendly resolve error. This is what makes ``pn preview`` surface
    ``No module named 'emoji'`` instead of a misleading message.
    """
    pkg = tmp_path / "resolver_app"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "good.py").write_text("def App():\n    return None\n\ndef Other():\n    return None\n", encoding="utf-8")
    (pkg / "bad.py").write_text(
        "import a_dependency_that_is_not_installed_xyz\n\ndef App():\n    return None\n",
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(os.fspath(tmp_path))
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    for name in ("resolver_app", "resolver_app.good", "resolver_app.bad"):
        sys.modules.pop(name, None)

    # A resolvable module returns its ``App``; a dotted path returns the named attribute.
    assert import_component("resolver_app.good").__name__ == "App"
    assert import_component("resolver_app.good.Other").__name__ == "Other"

    # The module exists but imports a missing dependency: the real
    # ``ModuleNotFoundError`` (naming that dependency) must propagate.
    with pytest.raises(ModuleNotFoundError) as excinfo:
        import_component("resolver_app.bad")
    assert excinfo.value.name == "a_dependency_that_is_not_installed_xyz"

    # A genuinely absent path still gives the friendly resolve error.
    with pytest.raises(ImportError, match="Could not resolve component"):
        import_component("resolver_app.nope_does_not_exist")
