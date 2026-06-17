"""Tests for the desktop (Tkinter) preview backend.

Split into two tiers:

- **Pure / headless tests** (always run): registration parity with the
  device backends, color conversion, font-weight detection, and the
  ``Platform`` desktop selector. These need no display.
- **GUI tests** (skipped when Tk can't open a display, e.g. on CI):
  mount a real element tree through a ``Reconciler`` + the desktop
  registry and assert widgets are created, laid out, measured, and
  wired to callbacks. A subprocess test exercises the full
  ``pn preview`` host + navigation stack under ``PN_PLATFORM=desktop``.
"""

import os
import subprocess
import sys
import textwrap
from typing import Any

import pytest

from pythonnative.native_views import NativeViewRegistry

# Importing the desktop backend pulls in ``tkinter`` (the module, not a
# live display). That's available on standard CPython, but guard it so a
# Python built entirely without Tk skips this module instead of erroring
# at collection.
try:
    from pythonnative.native_views import desktop as desktop_backend

    _DESKTOP_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - environment dependent
    desktop_backend = None
    _DESKTOP_IMPORT_ERROR = exc

pytestmark = pytest.mark.skipif(
    desktop_backend is None,
    reason=f"tkinter unavailable: {_DESKTOP_IMPORT_ERROR!r}",
)

# The 24 built-in element types every platform backend must service.
_EXPECTED_TYPES = {
    "View",
    "Column",
    "Row",
    "Text",
    "Button",
    "TextInput",
    "Image",
    "Switch",
    "ProgressBar",
    "ActivityIndicator",
    "WebView",
    "Spacer",
    "ScrollView",
    "SafeAreaView",
    "Modal",
    "Slider",
    "TabBar",
    "Pressable",
    "StatusBar",
    "KeyboardAvoidingView",
    "Picker",
    "Checkbox",
    "SegmentedControl",
    "DatePicker",
}


def _display_available() -> bool:
    """Return ``True`` if Tk can open a display in this environment.

    Probed in a *subprocess* on purpose: repeatedly creating and
    destroying Tk roots in a single process is unstable on macOS Aqua
    (it can segfault), so the GUI tests below each run in their own
    fresh interpreter and the probe must not leave a root behind here.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-c", "import tkinter; tkinter.Tk().destroy()"],
            capture_output=True,
            timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False


HAS_DISPLAY = _display_available()
requires_display = pytest.mark.skipif(not HAS_DISPLAY, reason="Tk display unavailable (e.g. headless CI)")


# ======================================================================
# Registration parity (headless)
# ======================================================================


def test_register_handlers_covers_all_builtin_types() -> None:
    registry = NativeViewRegistry()
    desktop_backend.register_handlers(registry)
    registered = set(registry._handlers.keys())
    assert registered == _EXPECTED_TYPES


def test_view_column_row_share_one_handler() -> None:
    registry = NativeViewRegistry()
    desktop_backend.register_handlers(registry)
    assert registry._handlers["View"] is registry._handlers["Column"]
    assert registry._handlers["View"] is registry._handlers["Row"]


# ======================================================================
# Color conversion (headless)
# ======================================================================


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("#abc", "#aabbcc"),
        ("#AABBCC", "#AABBCC"),
        ("#80ff0000", "#ff0000"),  # #aarrggbb -> drop alpha
        ("#f00a", "#ff0000"),  # #rgba -> drop alpha
        (0xFF0000, "#ff0000"),
        ((255, 0, 0), "#ff0000"),
        ("rgb(255, 0, 0)", "#ff0000"),
        ("rgba(0, 255, 0, 0.5)", "#00ff00"),
        ("red", "red"),
        ("transparent", None),
        ("", None),
        (None, None),
        (True, None),
    ],
)
def test_tk_color(value: Any, expected: Any) -> None:
    assert desktop_backend._tk_color(value) == expected


# ======================================================================
# Font-weight detection (headless)
# ======================================================================


@pytest.mark.parametrize(
    ("props", "expected"),
    [
        ({"bold": True}, True),
        ({"font_weight": "bold"}, True),
        ({"font_weight": "semibold"}, True),
        ({"font_weight": 700}, True),
        ({"font_weight": 600}, True),
        ({"font_weight": 500}, False),
        ({"font_weight": "normal"}, False),
        ({}, False),
    ],
)
def test_is_bold(props: dict, expected: bool) -> None:
    assert desktop_backend._is_bold(props) is expected


# ======================================================================
# Platform.select desktop branch (headless)
# ======================================================================


def test_platform_select_desktop() -> None:
    from pythonnative.platform import Platform, _set_platform_for_test

    try:
        _set_platform_for_test("desktop")
        assert Platform.OS == "desktop"
        assert Platform.is_desktop is True
        assert Platform.is_test is False
        assert Platform.select({"desktop": "d", "ios": "i", "default": "x"}) == "d"
        # ``native`` matches iOS/Android only; desktop is a dev surface.
        assert Platform.select({"native": "n", "default": "x"}) == "x"
    finally:
        _set_platform_for_test(None)


# ======================================================================
# GUI tests (require a display; each runs in its own subprocess)
# ======================================================================
#
# Tk is exercised in isolated subprocesses rather than in-process: macOS
# Aqua is unstable when a single interpreter creates and tears down
# multiple Tk roots across tests (observed segfaults). One root per
# process, with a clean exit, sidesteps that entirely and also keeps
# the global stage / registry state from leaking between tests.


def _run_gui_script(tmp_path: Any, name: str, body: str, sentinel: str, *, desktop_env: bool = False) -> None:
    script = tmp_path / name
    script.write_text(textwrap.dedent(body))
    env = dict(os.environ)
    if desktop_env:
        env["PN_PLATFORM"] = "desktop"
    result = subprocess.run(
        [sys.executable, str(script)],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    assert sentinel in result.stdout, f"missing {sentinel}; stdout={result.stdout!r} stderr={result.stderr!r}"


_BACKEND_SCRIPT = """
    import tkinter as tk
    import pythonnative as pn
    from pythonnative.reconciler import Reconciler
    from pythonnative.native_views import NativeViewRegistry
    from pythonnative.native_views import desktop as dk

    root = tk.Tk(); root.withdraw()
    stage = tk.Frame(root); stage.place(x=0, y=0, width=390, height=844)
    dk.set_root_container(stage)
    reg = NativeViewRegistry(); dk.register_handlers(reg)
    rec = Reconciler(reg)

    calls = []
    rec.mount(pn.Column(
        pn.Text("Hi there", style={"font_size": 18}),
        pn.Button("OK", on_click=lambda: calls.append(1)),
        style={"padding": 10, "spacing": 8},
    ))
    rec.set_viewport_size(390.0, 844.0)
    root.update_idletasks()

    def walk(w, acc):
        for c in w.winfo_children():
            acc.append(c); walk(c, acc)
        return acc

    widgets = walk(stage, [])
    text = next(w for w in widgets if isinstance(w, tk.Label) and w.cget("text") == "Hi there")
    assert text.winfo_width() > 0 and text.winfo_height() > 0, (text.winfo_width(), text.winfo_height())
    assert text.winfo_x() >= 10, text.winfo_x()  # padding pushed it in

    button = next(w for w in widgets if isinstance(w, tk.Button) and w.cget("text") == "OK")
    button.invoke()
    assert calls == [1], calls

    rec.reconcile(pn.Column(
        pn.Text("changed", style={"font_size": 18}),
        pn.Button("OK"),
        style={"padding": 10, "spacing": 8},
    ))
    root.update_idletasks()
    texts = [w.cget("text") for w in walk(stage, []) if isinstance(w, tk.Label)]
    assert "changed" in texts and "Hi there" not in texts, texts

    handler = dk.TextHandler()
    label = handler.create(9999, {"text": "hello world wrapping test", "font_size": 16})
    wide_w, wide_h = handler.measure_intrinsic(label, 10000.0, 10000.0)
    narrow_w, narrow_h = handler.measure_intrinsic(label, 40.0, 10000.0)
    assert wide_w > 0 and wide_h > 0, (wide_w, wide_h)
    assert narrow_w <= 40.0 and narrow_h >= wide_h, (narrow_w, narrow_h, wide_h)

    root.destroy()
    print("BACKEND_OK")
"""


@requires_display
def test_backend_mount_layout_and_measure(tmp_path: Any) -> None:
    _run_gui_script(tmp_path, "backend_script.py", _BACKEND_SCRIPT, "BACKEND_OK")


# ======================================================================
# Full preview host + navigation stack (subprocess, requires display)
# ======================================================================

_NAV_SCRIPT = """
    import sys, types
    import tkinter as tk
    import pythonnative as pn
    from pythonnative import preview, screen as sc
    from pythonnative.native_views import desktop as dk
    from pythonnative.platform import Platform
    from pythonnative.utils import IS_DESKTOP

    assert IS_DESKTOP, "IS_DESKTOP must be True under PN_PLATFORM=desktop"
    assert Platform.OS == "desktop", Platform.OS

    Stack = pn.create_stack_navigator()

    @pn.component
    def Home():
        count, set_count = pn.use_state(0)
        nav = pn.use_navigation()
        return pn.Column(
            pn.Text("HOME"),
            pn.Text("count=%d" % count),
            pn.Button("inc", on_click=lambda: set_count(count + 1)),
            pn.Button("detail", on_click=lambda: nav.navigate("Detail", {"x": count})),
        )

    @pn.component
    def Detail():
        nav = pn.use_navigation()
        p = pn.use_route()
        return pn.Column(
            pn.Text("DETAIL x=%s" % p.get("x")),
            pn.Button("back", on_click=nav.go_back),
        )

    @pn.component
    def App():
        return pn.NavigationContainer(Stack.Navigator(
            Stack.Screen("Home", component=Home),
            Stack.Screen("Detail", component=Detail),
        ))

    mod = types.ModuleType("nav_app")
    mod.App = App
    sys.modules["nav_app"] = mod

    def walk(w, acc):
        for c in w.winfo_children():
            acc.append(c); walk(c, acc)
        return acc

    def labels(stage):
        return [w.cget("text") for w in walk(stage, []) if isinstance(w, tk.Label)]

    def button(stage, text):
        for b in walk(stage, []):
            if isinstance(b, tk.Button) and b.cget("text") == text:
                return b
        raise AssertionError("no button " + text)

    root = tk.Tk(); root.withdraw()
    stage = tk.Frame(root); stage.place(x=0, y=0, width=390, height=844)
    dk.set_root_container(stage)
    app = preview.DesktopApp(root, stage, 390, 844)
    app.mount_root("nav_app")
    root.update()
    assert any("HOME" in t for t in labels(stage)), labels(stage)
    assert any("count=0" in t for t in labels(stage)), labels(stage)

    button(stage, "inc").invoke(); sc.drain_desktop_scheduled_renders(); root.update()
    assert any("count=1" in t for t in labels(stage)), labels(stage)

    button(stage, "detail").invoke(); sc.drain_desktop_scheduled_renders(); root.update()
    assert any("DETAIL x=1" in t for t in labels(stage)), labels(stage)
    assert len(app._stack) == 2, len(app._stack)

    button(stage, "back").invoke(); sc.drain_desktop_scheduled_renders(); root.update()
    assert len(app._stack) == 1, len(app._stack)
    assert any("count=1" in t for t in labels(stage)), labels(stage)  # state preserved

    root.destroy()
    print("NAV_OK")
"""


@requires_display
def test_preview_navigation_stack_subprocess(tmp_path: Any) -> None:
    _run_gui_script(tmp_path, "nav_script.py", _NAV_SCRIPT, "NAV_OK", desktop_env=True)
