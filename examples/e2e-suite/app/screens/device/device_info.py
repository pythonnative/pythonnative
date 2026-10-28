"""Demo screen for [`pn.Device`][pythonnative.Device].

``Device.info()`` returns a frozen [`DeviceInfo`][pythonnative.DeviceInfo]
record. The demo prints every field so a flow can assert the platform
name and the fields the app configuration determines (``app_name``,
``bundle_id``), while device-specific values are asserted as present.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText


@pn.component
def DeviceInfoDemo() -> pn.Node:
    """Render every DeviceInfo field."""
    info = pn.Device.info()

    return DemoScreen(
        "Device info",
        "Device.info() fields for the running device.",
        DemoSection(
            "DeviceInfo",
            ResultText("Platform", info.platform),
            ResultText("OS version", info.os_version or "(unknown)"),
            ResultText("Model", info.model or "(unknown)"),
            ResultText("Manufacturer", info.manufacturer or "(unknown)"),
            ResultText("Simulator", "yes" if info.is_simulator else "no"),
            ResultText("Tablet", "yes" if info.is_tablet else "no"),
            ResultText("App name", info.app_name or "(unknown)"),
            ResultText("App version", info.app_version or "(unknown)"),
            ResultText("Build number", info.build_number or "(unknown)"),
            ResultText("Bundle id", info.bundle_id or "(unknown)"),
            ResultText("Scale positive", "yes" if info.scale > 0 else "no"),
            ResultText("Font scale positive", "yes" if info.font_scale > 0 else "no"),
            ResultText("Locale", info.locale or "(unknown)"),
            Hint("Maestro asserts the platform line and the bundle id from pythonnative.toml."),
        ),
    )
