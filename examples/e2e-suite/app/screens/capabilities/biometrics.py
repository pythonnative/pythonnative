"""Demo screen for [`Biometrics`][pythonnative.biometrics.Biometrics].

A simulator has no enrolled face, so the flow only asserts the capability answers.
"""

from __future__ import annotations

from app.screens.scaffold import DemoScreen, DemoSection, ResultText

import pythonnative as pn
from pythonnative.biometrics import Biometrics


@pn.component
def BiometricsDemo() -> pn.Node:
    """Report whether biometric authentication can be attempted."""
    available = Biometrics.is_available()
    return DemoScreen(
        "Biometrics",
        "Whether a biometric prompt can be attempted.",
        DemoSection(
            "Availability",
            ResultText("Biometrics answered", "yes" if available in (True, False) else "no"),
        ),
    )
