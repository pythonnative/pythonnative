"""Navigation themes: the colors every navigator draws its chrome with.

A [`NavigationTheme`][pythonnative.NavigationTheme] is a frozen record
of six colors plus a ``dark`` flag, the same shape as React
Navigation's theme object. Pass one to
``NavigationContainer(theme=...)`` and every navigator below reads it
through [`use_navigation_theme`][pythonnative.use_navigation_theme]:
the Python-drawn stack header, back label, drawer panel, and
unknown-route fallback use it directly, and the native ``Screen`` and
``TabBar`` elements receive its colors as their default header tint,
header background, title color, tab tint, and tab bar background when
the app didn't set those options itself.

When no theme is provided, the hook picks
[`DEFAULT_NAVIGATION_THEME`][pythonnative.DEFAULT_NAVIGATION_THEME] or
[`DARK_NAVIGATION_THEME`][pythonnative.DARK_NAVIGATION_THEME] from the
current color scheme (see
[`use_color_scheme`][pythonnative.use_color_scheme]) and re-renders
when the scheme changes.

Example:
    ```python
    @pn.component
    def App():
        scheme = pn.use_color_scheme()
        return pn.NavigationContainer(
            Stack.Navigator(...),
            theme=pn.DARK_NAVIGATION_THEME if scheme == "dark" else pn.DEFAULT_NAVIGATION_THEME,
        )
    ```
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..hooks import Context, create_context, use_color_scheme, use_context

__all__ = [
    "DARK_NAVIGATION_THEME",
    "DEFAULT_NAVIGATION_THEME",
    "NavigationColors",
    "NavigationTheme",
    "NavigationThemeContext",
    "use_navigation_theme",
]


@dataclass(frozen=True)
class NavigationColors:
    """The color slots a navigation theme fills.

    Attributes:
        primary: Tint of interactive chrome: the back label, header
            buttons, the selected tab, and the active drawer row.
        background: Color behind screens and the drawer's active row.
        card: Background of the header, tab bar, and drawer panel.
        text: Header title and drawer label color.
        border: Hairline separating the header, tab bar, and drawer
            panel from the content.
        notification: Badge color for tab items.
    """

    primary: str
    background: str
    card: str
    text: str
    border: str
    notification: str


@dataclass(frozen=True)
class NavigationTheme:
    """A navigation theme: whether it's dark, and its colors.

    Build one with the dataclass constructor or derive one from a
    preset with ``dataclasses.replace``:

    ```python
    import dataclasses

    brand = dataclasses.replace(
        pn.DEFAULT_NAVIGATION_THEME,
        colors=dataclasses.replace(pn.DEFAULT_NAVIGATION_THEME.colors, primary="#FF2D55"),
    )
    ```

    Attributes:
        dark: Whether the theme is meant for a dark appearance. Native
            hosts use it to pick light or dark status bar content.
        colors: The [`NavigationColors`][pythonnative.NavigationColors].
    """

    dark: bool
    colors: NavigationColors


DEFAULT_NAVIGATION_THEME = NavigationTheme(
    dark=False,
    colors=NavigationColors(
        primary="#007AFF",
        background="#F2F2F2",
        card="#FFFFFF",
        text="#1C1C1E",
        border="#D8D8D8",
        notification="#FF3B30",
    ),
)
"""The light theme, matching React Navigation's ``DefaultTheme``."""

DARK_NAVIGATION_THEME = NavigationTheme(
    dark=True,
    colors=NavigationColors(
        primary="#0A84FF",
        background="#010101",
        card="#121212",
        text="#E5E5E7",
        border="#272729",
        notification="#FF453A",
    ),
)
"""The dark theme, matching React Navigation's ``DarkTheme``."""

NavigationThemeContext: Context[Optional[NavigationTheme]] = create_context(None, name="NavigationTheme")
"""Provides the theme set on ``NavigationContainer(theme=...)``; ``None`` means follow the color scheme."""


def theme_for_scheme(scheme: str) -> NavigationTheme:
    """Return the preset theme for a color scheme (``"dark"`` or anything else)."""
    return DARK_NAVIGATION_THEME if scheme == "dark" else DEFAULT_NAVIGATION_THEME


def use_navigation_theme() -> NavigationTheme:
    """Return the active [`NavigationTheme`][pythonnative.NavigationTheme].

    The theme passed to ``NavigationContainer(theme=...)`` wins. Without
    one, the hook returns
    [`DARK_NAVIGATION_THEME`][pythonnative.DARK_NAVIGATION_THEME] when
    the color scheme is dark and
    [`DEFAULT_NAVIGATION_THEME`][pythonnative.DEFAULT_NAVIGATION_THEME]
    otherwise, and the component re-renders when the scheme changes.

    Raises:
        RuntimeError: If called outside a ``@component`` function.

    Example:
        ```python
        @pn.component
        def Card(*children):
            theme = pn.use_navigation_theme()
            return pn.View(*children, style=pn.style(background_color=theme.colors.card))
        ```
    """
    provided = use_context(NavigationThemeContext)
    scheme = use_color_scheme()
    if provided is not None:
        return provided
    return theme_for_scheme(scheme)
