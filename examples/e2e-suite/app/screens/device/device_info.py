"""Demo screen for [`pn.Device`][pythonnative.Device].

``Device.info()`` returns a frozen [`DeviceInfo`][pythonnative.DeviceInfo]
record. The demo prints every field so a flow can assert the platform
name and the fields the app configuration determines (``app_name``,
``bundle_id``), while device-specific values are asserted as present.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


@pn.component
def DeviceInfoDemo() -> pn.Element:
    """Render every DeviceInfo field."""
    info = pn.Device.info()

    return demo_screen(
        "Device info",
        "Device.info() fields for the running device.",
        section(
            "DeviceInfo",
            result_text("Platform", info.platform),
            result_text("OS version", info.os_version or "(unknown)"),
            result_text("Model", info.model or "(unknown)"),
            result_text("Manufacturer", info.manufacturer or "(unknown)"),
            result_text("Simulator", "yes" if info.is_simulator else "no"),
            result_text("Tablet", "yes" if info.is_tablet else "no"),
            result_text("App name", info.app_name or "(unknown)"),
            result_text("App version", info.app_version or "(unknown)"),
            result_text("Build number", info.build_number or "(unknown)"),
            result_text("Bundle id", info.bundle_id or "(unknown)"),
            result_text("Scale positive", "yes" if info.scale > 0 else "no"),
            result_text("Font scale positive", "yes" if info.font_scale > 0 else "no"),
            result_text("Locale", info.locale or "(unknown)"),
            hint("Maestro asserts the platform line and the bundle id from pythonnative.toml."),
        ),
    )
