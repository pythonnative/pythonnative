"""What a release build shows after an error nothing caught."""

from __future__ import annotations

from typing import Callable

import pythonnative as pn

from .theme import DARK, LIGHT, Styles
from .widgets import PrimaryButton


@pn.component
def CrashContent(error_text: str, reset: Callable[[], None]) -> pn.Node:
    """Own up to the problem, and promise only what's true: the journal is on disk."""
    styles = pn.use_styles(Styles)
    return pn.SafeAreaView(
        pn.Column(
            pn.Icon("notebook-pen", size=48, color=styles.colors.primary),
            pn.Text("This page came apart", style=styles.heading),
            pn.Text(
                "Your journal is safe on this device. The problem is in the error log, under Settings.",
                style=styles.center_text,
            ),
            pn.Text(error_text, style=styles.caption),
            PrimaryButton("Try again", reset),
            style=styles.center,
        ),
        style=styles.screen,
    )


def error_fallback(error: BaseException, reset: Callable[[], None]) -> pn.Element:
    """The renderer given to ``pn.set_error_fallback``.

    It replaces a whole screen, above where ``App`` provides the theme, so it provides
    the theme itself.

    Args:
        error: What was raised.
        reset: Remounts the screen with fresh state.

    Returns:
        The element to show.
    """
    return pn.ThemeProvider(
        CrashContent(error_text=f"{type(error).__name__}: {error}", reset=reset),
        light=LIGHT,
        dark=DARK,
    )
