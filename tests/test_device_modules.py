"""Unit tests for the device-environment modules added in RFC 0002.

``AccessibilityInfo``, ``Keyboard``, ``Device``, ``Localization``,
``Dimensions``, and ``PixelRatio`` run here against their Python
fallbacks and against scripted implementations installed with
``register_python_module``. Each section covers the synchronous readers,
native ``change`` events routed through ``dispatch_module_message``, and
the hooks built on ``use_subscription``.
"""

from __future__ import annotations

from typing import Any, Dict, Generator, List

import pytest

from pythonnative import platform_metrics as pm
from pythonnative.component import component
from pythonnative.element import Element
from pythonnative.hooks import Ref, use_keyboard_height, use_ref
from pythonnative.native_modules import (
    AccessibilityEvent,
    AccessibilityInfo,
    Device,
    DeviceInfo,
    Dimensions,
    Keyboard,
    KeyboardEvent,
    Locale,
    Localization,
    PixelRatio,
    accessibility_info,
    keyboard,
    localization,
    use_locales,
    use_reduce_motion,
    use_screen_reader_enabled,
)
from pythonnative.native_modules import registry as module_registry
from pythonnative.native_modules.dimensions import DimensionsEvent
from pythonnative.native_modules.registry import NativeModuleError
from pythonnative.platform_metrics import WindowDimensions
from pythonnative.reconciler import Reconciler
from pythonnative.testing import FakeBackend, settle


@pytest.fixture(autouse=True)
def _reset_module_state() -> Generator[None, None, None]:
    """Reset cached snapshots, listener lists, metrics, and scripted modules."""

    def reset() -> None:
        accessibility_info._state = None
        accessibility_info._listeners.clear()
        keyboard._listeners.clear()
        localization._locales = None
        localization._timezone = None
        localization._listeners.clear()
        pm.reset_window_dimensions()
        pm.reset_screen_dimensions()
        pm.reset_keyboard_height()
        for name in ("AccessibilityInfo", "Keyboard", "Device", "Localization"):
            module_registry.unregister_python_module(name)

    reset()
    yield
    reset()


def _mount(render: Any) -> tuple[Reconciler, List[Any]]:
    """Mount a component that records what ``render`` returns each pass."""
    rendered: List[Any] = []

    @component
    def comp() -> Element:
        rendered.append(render())
        return Element("Text", {"text": "ok"}, [])

    rec = Reconciler(FakeBackend())
    rec.on_render_requested = lambda: rec.reconcile(comp())
    rec.mount(comp())
    return rec, rendered


# ======================================================================
# AccessibilityInfo
# ======================================================================


def test_accessibility_info_fallback_defaults() -> None:
    assert AccessibilityInfo.is_screen_reader_enabled() is False
    assert AccessibilityInfo.is_reduce_motion_enabled() is False
    AccessibilityInfo.announce("Saved")  # no-op off device
    AccessibilityInfo.set_accessibility_focus(42)  # no-op off device


def test_accessibility_info_reads_scripted_module() -> None:
    class Scripted:
        announced: List[str] = []
        focused: List[int] = []

        def is_screen_reader_enabled(self) -> bool:
            return True

        def is_reduce_motion_enabled(self) -> bool:
            return False

        def announce(self, message: str) -> None:
            self.announced.append(message)

        def set_accessibility_focus(self, tag: int) -> None:
            self.focused.append(tag)

    module_registry.register_python_module("AccessibilityInfo", Scripted())
    assert AccessibilityInfo.is_screen_reader_enabled() is True
    assert AccessibilityInfo.is_reduce_motion_enabled() is False
    AccessibilityInfo.announce("Saved")
    assert Scripted.announced == ["Saved"]

    class Handle:
        tag = 7

    ref = Ref(Handle())
    AccessibilityInfo.set_accessibility_focus(ref)
    AccessibilityInfo.set_accessibility_focus(Handle())
    AccessibilityInfo.set_accessibility_focus(9)
    assert Scripted.focused == [7, 7, 9]


def test_accessibility_focus_rejects_unattached_ref() -> None:
    ref: Ref[Any] = Ref(None)
    with pytest.raises(ValueError, match="mounted element"):
        AccessibilityInfo.set_accessibility_focus(ref)
    with pytest.raises(ValueError):
        AccessibilityInfo.set_accessibility_focus(True)


def test_accessibility_focus_uses_the_ref_attached_by_the_reconciler() -> None:
    class Scripted:
        focused: List[int] = []

        def is_screen_reader_enabled(self) -> bool:
            return False

        def is_reduce_motion_enabled(self) -> bool:
            return False

        def announce(self, message: str) -> None:
            del message

        def set_accessibility_focus(self, tag: int) -> None:
            self.focused.append(tag)

    module_registry.register_python_module("AccessibilityInfo", Scripted())
    captured: Dict[str, Any] = {}

    @component
    def comp() -> Element:
        ref = use_ref()
        captured["ref"] = ref
        return Element("Text", {"text": "focus me", "ref": ref}, [])

    backend = FakeBackend()
    Reconciler(backend).mount(comp())
    AccessibilityInfo.set_accessibility_focus(captured["ref"])
    text = next(v for v in backend.views.values() if v.type_name == "Text")
    assert Scripted.focused == [text.tag]


def test_accessibility_listener_receives_frozen_event_and_dedupes() -> None:
    seen: List[AccessibilityEvent] = []
    unsubscribe = AccessibilityInfo.add_listener(seen.append)
    accessibility_info.dispatch_accessibility(True, False)
    settle()
    accessibility_info.dispatch_accessibility(True, False)  # unchanged: not redelivered
    settle()
    accessibility_info.dispatch_accessibility(True, True)
    settle()
    unsubscribe()
    accessibility_info.dispatch_accessibility(False, False)
    settle()
    assert seen == [AccessibilityEvent(True, False), AccessibilityEvent(True, True)]
    with pytest.raises(Exception):
        seen[0].screen_reader = False  # type: ignore[misc]


def test_accessibility_native_change_event_reaches_listeners() -> None:
    seen: List[AccessibilityEvent] = []
    AccessibilityInfo.add_listener(seen.append)
    module_registry.dispatch_module_message(
        "AccessibilityInfo", {"event": "change", "payload": {"screen_reader": True, "reduce_motion": True}}
    )
    settle()
    # A partial payload keeps the other flag.
    module_registry.dispatch_module_message(
        "AccessibilityInfo", {"event": "change", "payload": {"reduce_motion": False}}
    )
    settle()
    assert seen == [AccessibilityEvent(True, True), AccessibilityEvent(True, False)]


def test_use_screen_reader_enabled_and_use_reduce_motion_rerender() -> None:
    _, screen_reader = _mount(use_screen_reader_enabled)
    _, reduce_motion = _mount(use_reduce_motion)
    assert screen_reader[0] is False and reduce_motion[0] is False

    accessibility_info.dispatch_accessibility(True, False)
    settle()
    assert screen_reader[-1] is True
    assert reduce_motion[-1] is False

    accessibility_info.dispatch_accessibility(True, True)
    settle()
    assert reduce_motion[-1] is True


def test_use_screen_reader_enabled_seeds_from_native() -> None:
    class Scripted:
        def is_screen_reader_enabled(self) -> bool:
            return True

        def is_reduce_motion_enabled(self) -> bool:
            return True

    module_registry.register_python_module("AccessibilityInfo", Scripted())
    _, screen_reader = _mount(use_screen_reader_enabled)
    _, reduce_motion = _mount(use_reduce_motion)
    assert screen_reader[0] is True and reduce_motion[0] is True


# ======================================================================
# Keyboard
# ======================================================================


def test_keyboard_fallback_defaults() -> None:
    assert Keyboard.is_visible() is False
    Keyboard.dismiss()  # no-op off device


def test_keyboard_dismiss_reaches_scripted_module() -> None:
    class Scripted:
        dismissed = 0

        def dismiss(self) -> None:
            Scripted.dismissed += 1

        def is_visible(self) -> bool:
            return True

    module_registry.register_python_module("Keyboard", Scripted())
    Keyboard.dismiss()
    assert Scripted.dismissed == 1
    assert Keyboard.is_visible() is True


def test_keyboard_listener_and_metrics_follow_dispatch() -> None:
    seen: List[KeyboardEvent] = []
    unsubscribe = Keyboard.add_listener(seen.append)
    keyboard.dispatch_keyboard(300.0, True, 250.0)
    settle()
    assert seen == [KeyboardEvent(height=300.0, visible=True, duration_ms=250.0)]
    assert pm.get_keyboard_height() == 300.0

    keyboard.dispatch_keyboard(300.0, False, 250.0)
    settle()
    assert pm.get_keyboard_height() == 0.0, "a hidden keyboard reports height 0 to the metric hooks"
    unsubscribe()
    keyboard.dispatch_keyboard(100.0, True)
    settle()
    assert len(seen) == 2


def test_keyboard_native_change_event_updates_use_keyboard_height() -> None:
    _, heights = _mount(use_keyboard_height)
    assert heights[0] == 0.0
    module_registry.dispatch_module_message(
        "Keyboard", {"event": "change", "payload": {"height": 336.0, "visible": True, "duration_ms": 250}}
    )
    settle()
    assert heights[-1] == 336.0
    module_registry.dispatch_module_message("Keyboard", {"event": "change", "payload": {"height": 0, "visible": False}})
    settle()
    assert heights[-1] == 0.0


def test_keyboard_native_change_event_infers_visibility_from_height() -> None:
    seen: List[KeyboardEvent] = []
    Keyboard.add_listener(seen.append)
    module_registry.dispatch_module_message("Keyboard", {"event": "change", "payload": {"height": 200}})
    settle()
    assert seen == [KeyboardEvent(200.0, True, 0.0)]


# ======================================================================
# Device
# ======================================================================


def test_device_info_fallback_is_a_frozen_record_with_documented_keys() -> None:
    info = Device.info()
    assert isinstance(info, DeviceInfo)
    assert info.platform == "test"
    assert info.is_simulator is False and info.is_tablet is False
    assert info.scale == 1.0 and info.font_scale == 1.0
    assert info.app_version == "0.0.0" and info.build_number == "0"
    assert info.bundle_id == "com.pythonnative.preview"
    assert "-" in info.locale or info.locale.isalpha()
    with pytest.raises(Exception):
        info.model = "x"  # type: ignore[misc]


def test_device_fallback_returns_exactly_the_contract_keys_plus_directories() -> None:
    from pythonnative.native_modules.fallback import FallbackDevice

    raw = FallbackDevice().info()
    documented = {
        "platform",
        "os_version",
        "model",
        "manufacturer",
        "is_simulator",
        "is_tablet",
        "app_name",
        "app_version",
        "build_number",
        "bundle_id",
        "scale",
        "font_scale",
        "locale",
    }
    assert documented <= set(raw)
    assert set(raw) - documented == {"app_dir", "cache_dir"}
    for legacy in ("os", "temp_dir", "python_version"):
        assert legacy not in raw


def test_device_info_from_native_payload_ignores_extras_and_defaults_missing() -> None:
    class Native:
        def info(self) -> Dict[str, Any]:
            return {
                "platform": "ios",
                "os_version": "17.4",
                "model": "iPhone",
                "manufacturer": "Apple",
                "is_simulator": True,
                "is_tablet": True,
                "app_name": "Inbox",
                "app_version": "1.2.3",
                "build_number": "45",
                "bundle_id": "com.example.inbox",
                "scale": 3,
                "font_scale": 1.25,
                "locale": "en-US",
                "app_dir": "/var/mobile/Documents",
            }

    module_registry.register_python_module("Device", Native())
    info = Device.info()
    assert info == DeviceInfo(
        platform="ios",
        os_version="17.4",
        model="iPhone",
        manufacturer="Apple",
        is_simulator=True,
        is_tablet=True,
        app_name="Inbox",
        app_version="1.2.3",
        build_number="45",
        bundle_id="com.example.inbox",
        scale=3.0,
        font_scale=1.25,
        locale="en-US",
    )
    assert not hasattr(info, "app_dir")

    class Sparse:
        def info(self) -> Dict[str, Any]:
            return {"platform": "android", "os_version": "14", "model": "Pixel 8", "scale": 0}

    module_registry.register_python_module("Device", Sparse())
    sparse = Device.info()
    assert sparse.manufacturer == "" and sparse.is_simulator is False and sparse.scale == 1.0


def test_file_system_still_reads_app_dir_from_the_device_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    from pythonnative.native_modules import file_system

    monkeypatch.setattr(file_system, "_app_dir_cache", None)
    assert file_system.FileSystem.app_dir().endswith(".pythonnative_data")


# ======================================================================
# Localization
# ======================================================================


def test_localization_fallback_reads_lang(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LC_ALL", raising=False)
    monkeypatch.delenv("LC_MESSAGES", raising=False)
    monkeypatch.setenv("LANG", "ar_EG.UTF-8")
    locales = Localization.get_locales()
    assert locales == [Locale(language_tag="ar-EG", language_code="ar", region_code="EG", is_rtl=True)]
    assert Localization.is_rtl() is True
    assert Localization.get_timezone() == "UTC"


def test_localization_fallback_defaults_to_en_us(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(key, raising=False)
    assert Localization.get_locales() == [Locale("en-US", "en", "US", False)]
    monkeypatch.setenv("LANG", "C.UTF-8")
    localization._locales = None
    assert Localization.get_locales()[0].language_tag == "en-US"
    assert Localization.is_rtl() is False


def test_localization_from_scripted_module_and_change_event() -> None:
    class Scripted:
        def get_locales(self) -> List[Dict[str, Any]]:
            return [
                {"language_tag": "fr-CA", "language_code": "fr", "region_code": "CA", "is_rtl": False},
                {"language_tag": "en"},
                {"language_code": "xx"},
            ]

        def get_timezone(self) -> str:
            return "America/Toronto"

    module_registry.register_python_module("Localization", Scripted())
    assert Localization.get_locales() == [Locale("fr-CA", "fr", "CA", False), Locale("en", "en", "", False)]
    assert Localization.get_timezone() == "America/Toronto"

    seen: List[List[Locale]] = []
    Localization.add_listener(seen.append)
    module_registry.dispatch_module_message(
        "Localization",
        {
            "event": "change",
            "payload": {
                "locales": [{"language_tag": "he-IL", "language_code": "he", "region_code": "IL", "is_rtl": True}],
                "timezone": "Asia/Jerusalem",
            },
        },
    )
    settle()
    assert seen == [[Locale("he-IL", "he", "IL", True)]]
    assert Localization.is_rtl() is True
    assert Localization.get_timezone() == "Asia/Jerusalem"
    # A timezone-only change updates the cache without a locale notification.
    module_registry.dispatch_module_message("Localization", {"event": "change", "payload": {"timezone": "UTC"}})
    settle()
    assert Localization.get_timezone() == "UTC"
    assert len(seen) == 1


def test_use_locales_rerenders_on_change() -> None:
    _, rendered = _mount(use_locales)
    assert isinstance(rendered[0], list) and isinstance(rendered[0][0], Locale)
    localization.dispatch_localization([Locale("ja-JP", "ja", "JP", False)])
    settle()
    assert rendered[-1] == [Locale("ja-JP", "ja", "JP", False)]


# ======================================================================
# Dimensions / PixelRatio
# ======================================================================


def test_dimensions_get_reads_platform_metrics_with_screen_fallback() -> None:
    assert Dimensions.get() == WindowDimensions(0.0, 0.0, 1.0, 1.0)
    pm.set_window_dimensions(390.0, 844.0, scale=3.0, font_scale=1.2)
    settle()
    window = Dimensions.get("window")
    assert (window.width, window.height, window.scale, window.font_scale) == (390.0, 844.0, 3.0, 1.2)
    assert Dimensions.get("screen") == window, "screen falls back to the window until a host publishes one"
    pm.set_screen_dimensions(390.0, 900.0, scale=3.0)
    settle()
    assert Dimensions.get("screen").height == 900.0
    with pytest.raises(ValueError, match="'window' or 'screen'"):
        Dimensions.get("desk")  # type: ignore[arg-type]


def test_dimensions_listener_fires_only_for_size_changes() -> None:
    seen: List[DimensionsEvent] = []
    unsubscribe = Dimensions.add_listener(seen.append)
    pm.set_keyboard_height(200.0)
    settle()
    pm.set_safe_area_insets(44.0, 0.0, 34.0, 0.0)
    settle()
    assert seen == []
    pm.set_window_dimensions(390.0, 844.0)
    settle()
    assert len(seen) == 1
    assert seen[0].window.width == 390.0 and seen[0].screen.width == 390.0
    pm.set_screen_dimensions(390.0, 900.0)
    settle()
    assert len(seen) == 2 and seen[1].screen.height == 900.0
    unsubscribe()
    pm.set_window_dimensions(800.0, 600.0)
    settle()
    assert len(seen) == 2


def test_pixel_ratio_helpers() -> None:
    assert PixelRatio.get() == 1.0 and PixelRatio.get_font_scale() == 1.0
    pm.set_window_dimensions(390.0, 844.0, scale=3.0, font_scale=1.5)
    settle()
    assert PixelRatio.get() == 3.0
    assert PixelRatio.get_font_scale() == 1.5
    assert PixelRatio.get_pixel_size_for_layout_size(10.2) == 31
    assert isinstance(PixelRatio.get_pixel_size_for_layout_size(10.2), int)
    assert PixelRatio.round_to_nearest_pixel(0.5) == pytest.approx(2 / 3)
    assert PixelRatio.round_to_nearest_pixel(10.0) == 10.0


# ======================================================================
# Schema declarations
# ======================================================================


@pytest.mark.parametrize("name", ["AccessibilityInfo", "Keyboard", "Localization", "Battery", "NetInfo"])
def test_new_modules_declare_their_change_events(name: str) -> None:
    from pythonnative.sdk.schema import MODULES

    assert MODULES[name].events["change"]["type"] == "object"


def test_module_event_payloads_are_validated() -> None:
    from pythonnative.sdk.schema import MODULES

    with pytest.raises(TypeError):
        MODULES["Keyboard"].decode_event("change", "not-a-dict")
    assert MODULES["Localization"].methods["get_locales"]["result"]["type"] == "array"
    assert MODULES["AccessibilityInfo"].methods["set_accessibility_focus"]["arguments"]["tag"] == {"type": "integer"}


def test_fallback_modules_satisfy_the_contract() -> None:
    for name in ("AccessibilityInfo", "Keyboard", "Localization"):
        module = module_registry.native_module(name)
        assert isinstance(module, module_registry.PythonModule)
        assert module.impl is not None
    with pytest.raises(NativeModuleError):
        module_registry.native_module("Keyboard").call("nope")
