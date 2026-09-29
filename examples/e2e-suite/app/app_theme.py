"""Root navigation-theme switch shared by ``main.py`` and the theme demo.

The root ``NavigationContainer`` owns the active
[`NavigationTheme`][pythonnative.NavigationTheme]; this context exposes the
current preset name and its setter so a demo deep in the stack can flip
the whole app between ``DEFAULT_NAVIGATION_THEME`` and
``DARK_NAVIGATION_THEME`` and watch the native chrome follow.
"""

from __future__ import annotations

from typing import Callable, Optional, Tuple

import pythonnative as pn

ThemeSwitch = Tuple[str, Callable[[str], None]]
"""``(preset_name, set_preset_name)``; the name is ``"light"`` or ``"dark"``."""

ThemeSwitchContext: pn.Context[Optional[ThemeSwitch]] = pn.create_context(None)
"""Provided by ``main.App``; ``None`` when a screen renders outside it (headless tests)."""


def navigation_theme_for(name: str) -> pn.NavigationTheme:
    """Return the preset for a switch name."""
    return pn.DARK_NAVIGATION_THEME if name == "dark" else pn.DEFAULT_NAVIGATION_THEME
