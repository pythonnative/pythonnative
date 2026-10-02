"""Design tokens shared by the application and the navigators.

A [`Theme`][pythonnative.Theme] is a frozen, keyword-only dataclass:
whether it's dark, a [`Colors`][pythonnative.Colors] palette,
[`Typography`][pythonnative.Typography] text styles, a
[`Spacing`][pythonnative.Spacing] scale, and [`Radii`][pythonnative.Radii].
Components read it with [`use_theme`][pythonnative.use_theme]; the
built-in navigators draw their headers, tab bars, and drawers from the
same tokens, so one theme styles the whole app.

Without a provider, the theme follows the system appearance:
[`LIGHT_THEME`][pythonnative.LIGHT_THEME] or
[`DARK_THEME`][pythonnative.DARK_THEME]. Provide your own pair with
[`ThemeProvider`][pythonnative.ThemeProvider], and add tokens by
subclassing:

```python
from dataclasses import dataclass, replace

import pythonnative as pn


@dataclass(frozen=True, kw_only=True)
class BrandTheme(pn.Theme):
    accent: pn.Color = "#FF2D55"


LIGHT = BrandTheme(colors=replace(pn.LIGHT_THEME.colors, primary="#5B21B6"))
DARK = BrandTheme(dark=True, colors=replace(pn.DARK_THEME.colors, primary="#A78BFA"), accent="#FF6482")


@pn.component
def App() -> pn.Node:
    return pn.ThemeProvider(Home(), light=LIGHT, dark=DARK)


@pn.component
def Home() -> pn.Node:
    theme = pn.use_theme(BrandTheme)
    return pn.Text("Hello", style={"color": theme.accent})
```

Styles that depend on the theme are derived once per theme with
[`use_styles`][pythonnative.use_styles].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TypeVar, overload

from .component import component
from .element import Element, Node
from .hooks import Context, create_context, use_color_scheme, use_context, use_memo
from .style import Color, Style

__all__ = [
    "DARK_THEME",
    "LIGHT_THEME",
    "Colors",
    "Radii",
    "Spacing",
    "Theme",
    "ThemeProvider",
    "Typography",
    "use_styles",
    "use_theme",
]

ThemeT = TypeVar("ThemeT", bound="Theme")
S = TypeVar("S")


@dataclass(frozen=True, kw_only=True)
class Colors:
    """A theme's color palette.

    Attributes:
        primary: Accent for interactive elements. Navigators use it for
            the back button, header buttons, the selected tab, and the
            active drawer row.
        background: Screen background.
        surface: Raised surfaces such as cards, sheets, the navigation
            header, the tab bar, and the drawer panel.
        text: Primary text, including header titles.
        text_secondary: De-emphasized text.
        border: Hairlines and dividers, including the ones between the
            header or tab bar and the content.
        error: Destructive and error states, and tab badges.
        success: Success states.
        warning: Warning states.
    """

    primary: Color
    background: Color
    surface: Color
    text: Color
    text_secondary: Color
    border: Color
    error: Color
    success: Color
    warning: Color


def _text(**style: Any) -> Any:
    return field(default_factory=lambda: dict(style))


@dataclass(frozen=True, kw_only=True)
class Typography:
    """Named text styles; each is a [`Style`][pythonnative.Style] to pass to ``pn.Text``.

    Attributes:
        title: Screen titles.
        heading: Section headings.
        body: Body text.
        label: Labels on controls and list rows.
        caption: Captions and footnotes.
    """

    title: Style = _text(font_size=28, font_weight="700")
    heading: Style = _text(font_size=20, font_weight="600")
    body: Style = _text(font_size=16)
    label: Style = _text(font_size=15, font_weight="500")
    caption: Style = _text(font_size=13)


@dataclass(frozen=True, kw_only=True)
class Spacing:
    """A spacing scale in points, for padding, margins, and ``gap``."""

    xs: float = 4
    sm: float = 8
    md: float = 16
    lg: float = 24
    xl: float = 32


@dataclass(frozen=True, kw_only=True)
class Radii:
    """Corner radii in points; ``full`` makes a pill or circle."""

    sm: float = 4
    md: float = 8
    lg: float = 16
    full: float = 9999


@dataclass(frozen=True, kw_only=True)
class Theme:
    """Design tokens read through [`use_theme`][pythonnative.use_theme].

    Subclass it (keeping ``frozen=True, kw_only=True``) to add
    application tokens, and derive variations with
    [`dataclasses.replace`][dataclasses.replace].

    Attributes:
        dark: Whether the theme is meant for a dark appearance.
        colors: The [`Colors`][pythonnative.Colors] palette.
        typography: Named [`Typography`][pythonnative.Typography] text styles.
        spacing: The [`Spacing`][pythonnative.Spacing] scale.
        radii: Corner [`Radii`][pythonnative.Radii].
    """

    dark: bool = False
    colors: Colors
    typography: Typography = field(default_factory=Typography)
    spacing: Spacing = field(default_factory=Spacing)
    radii: Radii = field(default_factory=Radii)


LIGHT_THEME = Theme(
    colors=Colors(
        primary="#007AFF",
        background="#F2F2F7",
        surface="#FFFFFF",
        text="#000000",
        text_secondary="#6C6C70",
        border="#D1D1D6",
        error="#FF3B30",
        success="#34C759",
        warning="#FF9500",
    ),
)
"""The built-in light theme, used when the system appearance is light."""

DARK_THEME = Theme(
    dark=True,
    colors=Colors(
        primary="#0A84FF",
        background="#000000",
        surface="#1C1C1E",
        text="#FFFFFF",
        text_secondary="#98989F",
        border="#38383A",
        error="#FF453A",
        success="#30D158",
        warning="#FF9F0A",
    ),
)
"""The built-in dark theme, used when the system appearance is dark."""

_ThemeContext: Context[Optional[Theme]] = create_context(None, name="Theme")


@component
def ThemeProvider(*children: Node, light: Theme = LIGHT_THEME, dark: Theme = DARK_THEME) -> Element:
    """Provide ``light`` or ``dark`` to the subtree, following the effective color scheme.

    The effective scheme is the system appearance unless the app
    overrides it with
    [`appearance.set_color_scheme`][pythonnative.appearance.set_color_scheme].
    Pass the same theme for both to pin one regardless of appearance.

    Args:
        *children: The subtree that reads the theme.
        light: Theme used when the scheme is light.
        dark: Theme used when the scheme is dark.
    """
    scheme = use_color_scheme()
    return _ThemeContext.Provider(*children, value=dark if scheme == "dark" else light)


@overload
def use_theme() -> Theme: ...


@overload
def use_theme(kind: type[ThemeT], /) -> ThemeT: ...


def use_theme(kind: Optional[type[Theme]] = None, /) -> Theme:
    """Return the active [`Theme`][pythonnative.Theme] and re-render when it changes.

    The nearest [`ThemeProvider`][pythonnative.ThemeProvider] wins;
    without one, the built-in light or dark theme follows the effective
    color scheme.

    Args:
        kind: Optional ``Theme`` subclass. The return value is typed as
            that subclass, and a provided theme of another type raises.

    Raises:
        TypeError: If ``kind`` is given and the active theme isn't an
            instance of it.
        RuntimeError: If called outside a ``@component`` function.

    Example:
        ```python
        @pn.component
        def Card(*children: pn.Node) -> pn.Node:
            theme = pn.use_theme()
            return pn.View(
                *children,
                style={"background_color": theme.colors.surface, "padding": theme.spacing.md},
            )
        ```
    """
    scheme = use_color_scheme()
    provided = use_context(_ThemeContext)
    theme = provided if provided is not None else (DARK_THEME if scheme == "dark" else LIGHT_THEME)
    if kind is not None and not isinstance(theme, kind):
        raise TypeError(
            f"use_theme({kind.__name__}) found a {type(theme).__name__}; wrap the app in "
            f"pn.ThemeProvider(..., light=..., dark=...) with {kind.__name__} instances."
        )
    return theme


def use_styles(factory: Callable[[ThemeT], S]) -> S:
    """Return ``factory(theme)``, computed once per theme for this component.

    ``factory`` is usually a class whose ``__init__`` takes the theme
    and assigns styles as attributes, so they're typed and misspelled
    names are static errors:

    ```python
    class CardStyles:
        def __init__(self, theme: pn.Theme) -> None:
            self.card = pn.style(background_color=theme.colors.surface, border_radius=theme.radii.md)
            self.title = theme.typography.heading


    @pn.component
    def Card(title: str) -> pn.Node:
        styles = pn.use_styles(CardStyles)
        return pn.View(pn.Text(title, style=styles.title), style=styles.card)
    ```

    Args:
        factory: A callable taking the active theme.

    Returns:
        Whatever ``factory`` returns, with its type.
    """
    theme: Any = use_theme()
    return use_memo(lambda: factory(theme), [factory, theme])
