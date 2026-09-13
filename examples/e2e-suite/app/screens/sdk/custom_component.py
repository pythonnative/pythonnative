"""Exercise SDK props, platform capabilities, and a live native reset.

The separately packaged Inbox extension covers generated native components,
services, events, resources, and cancellation on both platforms.
"""

from __future__ import annotations

from dataclasses import dataclass

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


@dataclass(frozen=True)
class _DemoProps(pn.Props):
    """Tiny custom Props subclass used purely to exercise the SDK type."""

    label: str = ""


@pn.component
def CustomComponentDemo() -> pn.Element:
    """Inspect the SDK surface without registering a new platform handler."""
    removed, set_removed = pn.use_state(False)
    custom_registered = pn.sdk.list_components()
    props_instance = _DemoProps(label="hello")

    return demo_screen(
        "Custom component",
        "SDK surface check: Props subclass + registry inspection.",
        section(
            "SDK status",
            pn.Element("Text", {"text": "Contract reset target", "font_size": pn.UNSET if removed else 24}),
            pn.Button("Reset native property", on_press=lambda: set_removed(True)),
            result_text("Property removed", "yes" if removed else "no"),
            result_text("Native text supported", "yes" if pn.Platform.supports("Text", "text") else "no"),
            result_text("Props subclass works", "yes" if props_instance.label == "hello" else "no"),
            result_text("SDK module loaded", "yes" if hasattr(pn.sdk, "Props") else "no"),
            result_text("Custom components registered", len(custom_registered)),
            hint(
                "The status lines must render. The count is 0 in a stock "
                "install (no third-party native components present)."
            ),
        ),
    )
