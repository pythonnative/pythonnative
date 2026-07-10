"""Tests for screen-host lifecycle behavior."""

import os
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

from pythonnative.native_views import NativeViewRegistry
from pythonnative.native_views.base import ViewHandler
from pythonnative.screen import create_screen


class StubView:
    """Small native-view stand-in used by screen-host tests."""

    def __init__(self, props: Dict[str, Any]) -> None:
        self.props = dict(props)


class TextHandler(ViewHandler):
    """Minimal text handler for mounting screen roots on desktop."""

    def create(self, tag: int, props: Dict[str, Any]) -> StubView:
        return StubView(props)

    def update(self, native_view: StubView, changed_props: Dict[str, Any]) -> None:
        native_view.props.update(changed_props)


def _write_screen(path: Path, text: str) -> None:
    path.write_text(
        "from pythonnative.element import Element\n\n"
        "def MainPage():\n"
        f"    return Element('Text', {{'text': {text!r}}}, [])\n",
        encoding="utf-8",
    )


def test_screen_reload_reimports_root_component(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_dir = tmp_path / "reload_app"
    package_dir.mkdir()
    screen_path = package_dir / "screen.py"
    _write_screen(screen_path, "before")

    monkeypatch.syspath_prepend(os.fspath(tmp_path))
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    sys.modules.pop("reload_app.screen", None)
    sys.modules.pop("reload_app", None)

    registry = NativeViewRegistry()
    registry.register("Text", TextHandler())
    import pythonnative.native_views as native_views

    monkeypatch.setattr(native_views, "_registry", registry)

    host: Any = create_screen("reload_app.screen.MainPage")
    host.on_create()
    assert host._root_native_view.props["text"] == "before"

    _write_screen(screen_path, "after")
    host.reload(["reload_app.screen"])

    assert host._root_native_view.props["text"] == "after"


def test_screen_host_on_destroy_unmounts_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    """``on_destroy`` must unmount the reconciler: cleanups run, views die."""
    registry = NativeViewRegistry()
    registry.register("Text", TextHandler())
    import pythonnative.native_views as native_views

    monkeypatch.setattr(native_views, "_registry", registry)

    from pythonnative.element import Element
    from pythonnative.hooks import component, use_effect

    cleanups: list = []

    @component
    def Root() -> Element:
        use_effect(lambda: (lambda: cleanups.append("cleaned")), [])
        return Element("Text", {"text": "hi"}, [])

    import pythonnative.screen as screen_mod

    monkeypatch.setattr(screen_mod, "_import_component", lambda path: Root)

    host: Any = create_screen("dummy.path.Root")
    host.on_create()
    assert host._reconciler is not None
    assert cleanups == []

    host.on_destroy()
    assert cleanups == ["cleaned"], "effect cleanup must run on destroy"
    assert host._reconciler is None
    assert host._root_native_view is None


def test_screen_host_on_back_pressed_routes_to_handlers(monkeypatch: pytest.MonkeyPatch) -> None:
    """``on_back_pressed`` consults ``use_back_handler`` subscribers."""
    registry = NativeViewRegistry()
    registry.register("Text", TextHandler())
    import pythonnative.native_views as native_views

    monkeypatch.setattr(native_views, "_registry", registry)

    from pythonnative.element import Element
    from pythonnative.hooks import component, use_back_handler, use_state

    consume = {"value": True}

    @component
    def Root() -> Element:
        _count, _set_count = use_state(0)
        use_back_handler(lambda: consume["value"])
        return Element("Text", {"text": "hi"}, [])

    import pythonnative.screen as screen_mod

    monkeypatch.setattr(screen_mod, "_import_component", lambda path: Root)

    host: Any = create_screen("dummy.path.Root")
    host.on_create()
    assert host.on_back_pressed() is True

    consume["value"] = False
    assert host.on_back_pressed() is False

    host.on_destroy()
    assert host.on_back_pressed() is False, "destroyed host must decline back events"


def test_screen_host_exposes_on_layout_lifecycle_hook(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: every host class must accept an ``on_layout`` callback.

    The iOS template forwards ``viewDidLayoutSubviews`` as
    ``on_layout`` so the screen host can re-push the safe-area-aware
    viewport size; missing the method on the desktop or Android
    branches would raise ``AttributeError`` at runtime.
    """
    registry = NativeViewRegistry()
    registry.register("Text", TextHandler())
    import pythonnative.native_views as native_views

    monkeypatch.setattr(native_views, "_registry", registry)

    from pythonnative.element import Element

    def _root() -> Element:
        return Element("Text", {"text": "hi"}, [])

    import pythonnative.screen as screen_mod

    monkeypatch.setattr(screen_mod, "_import_component", lambda path: _root)

    host: Any = create_screen("dummy.path.Root")
    host.on_create()
    # Should be callable and idempotent on every host class.
    host.on_layout()
    host.on_layout()


class _StubObjC:
    """Mimics rubicon-objc's ``ObjCInstance.ptr`` attribute."""

    def __init__(self, ptr: Any) -> None:
        self.ptr = ptr


def test_objc_addr_handles_bytes_pointer() -> None:
    """Regression: rubicon-objc 0.5.x exposes ``ptr`` as raw bytes.

    Calling ``int(bytes_object)`` raises ``ValueError`` ("invalid
    literal for int() with base 10"), so the screen-host registry
    must decode the address with ``int.from_bytes``. Without this,
    the iOS screen host failed to register itself and every
    ``forward_lifecycle`` call (``on_layout`` / ``on_resume`` /
    ``on_pause``) silently dropped on the floor, which was exactly
    the bug surfaced by the missing ``[PN] on_layout`` log lines on
    iPhone 17 Pro.
    """
    import pythonnative.screen as screen_mod

    objc_addr = getattr(screen_mod, "_objc_addr", None)
    if objc_addr is None:
        pytest.skip("screen module did not export _objc_addr (Android branch)")

    bytes_le = (4_317_709_568).to_bytes(8, byteorder="little", signed=False)
    assert objc_addr(_StubObjC(bytes_le)) == 4_317_709_568
    assert objc_addr(_StubObjC(b"\x00\x05[\x01\x01\x00\x00\x00")) == 4_317_709_568


def test_objc_addr_handles_int_and_c_void_p_like_pointer() -> None:
    """``_objc_addr`` should accept legacy ``c_void_p``-style pointers too.

    Older rubicon-objc releases (and any direct caller) hand back an
    integer or a ``ctypes.c_void_p``-ish object whose ``.value`` is
    the address. Both paths must funnel to the same numeric key so a
    library upgrade does not silently break lifecycle dispatch.
    """
    import pythonnative.screen as screen_mod

    objc_addr = getattr(screen_mod, "_objc_addr", None)
    if objc_addr is None:
        pytest.skip("screen module did not export _objc_addr (Android branch)")

    assert objc_addr(_StubObjC(0xDEADBEEF)) == 0xDEADBEEF

    class _CVoidPLike:
        value = 0xCAFEF00D

    assert objc_addr(_StubObjC(_CVoidPLike())) == 0xCAFEF00D


def test_ios_register_screen_makes_forward_lifecycle_succeed() -> None:
    """End-to-end: a registered host receives the matching Swift event.

    Swift hands ``forward_lifecycle`` an ``UInt`` (Python ``int``) of
    the ``UIViewController`` address. The screen module must key its
    registry under the same numeric address, regardless of whether
    rubicon-objc gave it back as bytes, an int, or a ``c_void_p``.
    This test pins down that contract so the iOS lifecycle callbacks
    keep firing after dependency upgrades.
    """
    import pythonnative.screen as screen_mod

    register = getattr(screen_mod, "_ios_register_screen", None)
    forward = getattr(screen_mod, "forward_lifecycle", None)
    registry = getattr(screen_mod, "_IOS_SCREEN_REGISTRY", None)
    if register is None or forward is None or registry is None:
        pytest.skip("screen module is on the Android branch; no iOS hooks")

    addr_int = 4_317_709_568
    bytes_le = addr_int.to_bytes(8, byteorder="little", signed=False)

    class _Host:
        def __init__(self) -> None:
            self.received: list[str] = []

        def on_layout(self) -> None:
            self.received.append("on_layout")

    host = _Host()
    registry.clear()
    try:
        register(_StubObjC(bytes_le), host)
        assert addr_int in registry, "register_screen failed to decode bytes ptr"
        forward(addr_int, "on_layout")
        assert host.received == ["on_layout"]
    finally:
        registry.clear()


def test_import_component_propagates_real_dependency_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing import *inside* the app must not be masked.

    Regression: ``_import_component`` caught every ``ModuleNotFoundError``
    and reported a generic "could not resolve component", hiding the real
    cause (e.g. a dependency the developer forgot to install). The actual
    error must propagate, while a genuinely absent path still yields the
    friendly resolve error. This is what makes ``pn preview`` surface
    ``No module named 'emoji'`` instead of a misleading message.
    """
    from pythonnative.screen import _import_component

    pkg = tmp_path / "resolver_app"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "good.py").write_text("def App():\n    return None\n", encoding="utf-8")
    (pkg / "bad.py").write_text(
        "import a_dependency_that_is_not_installed_xyz\n\ndef App():\n    return None\n",
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(os.fspath(tmp_path))
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    for name in ("resolver_app", "resolver_app.good", "resolver_app.bad"):
        sys.modules.pop(name, None)

    # A resolvable module returns its ``App``.
    assert callable(_import_component("resolver_app.good"))

    # The module exists but imports a missing dependency: the real
    # ``ModuleNotFoundError`` (naming that dependency) must propagate.
    with pytest.raises(ModuleNotFoundError) as excinfo:
        _import_component("resolver_app.bad")
    assert excinfo.value.name == "a_dependency_that_is_not_installed_xyz"

    # A genuinely absent path still gives the friendly resolve error.
    with pytest.raises(ImportError, match="Could not resolve component"):
        _import_component("resolver_app.nope_does_not_exist")
