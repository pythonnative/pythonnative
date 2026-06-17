"""Demo screen for [`pn.sdk`][pythonnative.sdk] surface inspection.

Registering a real cross-platform custom native component requires
``ViewHandler`` implementations for iOS and Android, which is more
than a screen-level demo can do safely. The demo limits itself to
exercising the SDK surface: it confirms the headline exports are
importable, builds a frozen [`Props`][pythonnative.sdk.Props]
subclass, and reads back the registry. If any of those break, this
screen will fail to import and the flow will error out during boot,
which is exactly what we want.
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
    custom_registered = pn.sdk.list_components()
    props_instance = _DemoProps(label="hello")

    return demo_screen(
        "Custom component",
        "SDK surface check: Props subclass + registry inspection.",
        section(
            "SDK status",
            result_text("Props subclass works", "yes" if props_instance.label == "hello" else "no"),
            result_text("SDK module loaded", "yes" if hasattr(pn.sdk, "Props") else "no"),
            result_text("Custom components registered", len(custom_registered)),
            hint(
                "Both 'yes' lines must render. The count is 0 in a stock "
                "install (no third-party native components present)."
            ),
        ),
    )
