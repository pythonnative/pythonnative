"""Exercise SDK props, platform capabilities, and a live native reset.

The separately packaged Inbox extension covers generated native components,
services, events, resources, and cancellation on both platforms.
"""

from __future__ import annotations

from dataclasses import dataclass

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText


@dataclass(frozen=True)
class _DemoProps(pn.Props):
    """Tiny custom Props subclass used purely to exercise the SDK type."""

    label: str = ""


@pn.component
def CustomComponentDemo() -> pn.Node:
    """Inspect the SDK surface without registering a new platform handler."""
    removed, set_removed = pn.use_state(False)
    custom_registered = pn.sdk.list_components()
    props_instance = _DemoProps(label="hello")

    return DemoScreen(
        "Custom component",
        "SDK surface check: Props subclass + registry inspection.",
        DemoSection(
            "SDK status",
            pn.Element("Text", {"text": "Contract reset target", "font_size": pn.UNSET if removed else 24}),
            pn.Button("Reset native property", on_press=lambda: set_removed(True)),
            ResultText("Property removed", "yes" if removed else "no"),
            ResultText("Native text supported", "yes" if pn.Platform.supports("Text", "text") else "no"),
            ResultText("Props subclass works", "yes" if props_instance.label == "hello" else "no"),
            ResultText("SDK module loaded", "yes" if hasattr(pn.sdk, "Props") else "no"),
            ResultText("Custom components registered", len(custom_registered)),
            Hint(
                "The status lines must render. The count is 0 in a stock "
                "install (no third-party native components present)."
            ),
        ),
    )
