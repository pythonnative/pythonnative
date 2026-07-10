"""StyleSheet, typed `Style`, style resolution, and theming.

PythonNative ships a single, fully-typed [`Style`][pythonnative.Style]
TypedDict that enumerates every supported style property and constrains
enum-shaped values via [`typing.Literal`][typing.Literal]. The TypedDict
gives editors and type-checkers (mypy, pyright) full autocomplete and
validation: a typo such as ``flex_direction="collumn"`` is now a static
error, not a silent runtime no-op.

Style values remain plain dicts at runtime so they are trivial to
compose, diff, and store. Properties unrecognized by a platform handler
are still ignored, so third-party handlers may extend the palette
without modifying core types.

The runtime helpers ([`resolve_style`][pythonnative.style.resolve_style],
[`StyleSheet`][pythonnative.StyleSheet]) accept either a ``Style``
TypedDict, a regular ``Dict[str, Any]`` (for forward-compat or
unrestricted use), or a list of either kind of dict, and always
return a fresh, flat dict.

Example:
    ```python
    import pythonnative as pn

    styles = pn.StyleSheet.create(
        title=pn.style(font_size=24, bold=True, color="#333"),
        container=pn.style(padding=16, spacing=12),
    )

    pn.Column(
        pn.Text("Hello", style=styles["title"]),
        style=styles["container"],
    )
    ```
"""

import difflib
from typing import Any, Dict, List, Literal, Optional, Tuple, TypedDict, Union

from . import diagnostics
from .hooks import Context, create_context, use_color_scheme, use_context

# ======================================================================
# Atomic value types
# ======================================================================

Color = str
"""Color value: ``"#RRGGBB"``, ``"#AARRGGBB"``, or any string a platform
handler recognizes (e.g., ``"red"``). Stored verbatim and parsed by the
handler at apply-time, so palettes from third-party libraries pass through
unchanged."""

Dimension = Union[int, float, str]
"""A length value. Numbers are points/dp; strings ending in ``"%"`` are
parent-relative percentages."""


class EdgeInsets(TypedDict, total=False):
    """Per-edge spacing values used for ``padding`` and ``margin``.

    Mirrors React Native's ``EdgeInsets`` shape with PythonNative's
    convenience aliases. Any subset of keys may be supplied.
    """

    top: Dimension
    right: Dimension
    bottom: Dimension
    left: Dimension
    horizontal: Dimension
    vertical: Dimension
    all: Dimension


EdgeValue = Union[Dimension, EdgeInsets]
"""Padding/margin value: a uniform number, a ``"%"`` string, or an
[`EdgeInsets`][pythonnative.EdgeInsets] dict."""


class AccessibilityState(TypedDict, total=False):
    """Current widget state exposed to assistive technology.

    Passed via the ``accessibility_state=`` prop on interactive
    components. All keys are optional; omitted keys are treated as
    unset (not ``False``).

    Attributes:
        disabled: The widget is visible but not interactive.
        selected: The widget is currently selected (e.g. the active
            tab).
        checked: Toggle/checkbox state. ``"mixed"`` represents a
            tri-state checkbox.
        busy: The widget is loading or otherwise temporarily busy.
        expanded: A disclosure/accordion is currently expanded.
    """

    disabled: bool
    selected: bool
    checked: Union[bool, Literal["mixed"]]
    busy: bool
    expanded: bool


class ShadowOffset(TypedDict):
    """Shadow displacement in points."""

    width: float
    height: float


# ----------------------------------------------------------------------
# Transforms
# ----------------------------------------------------------------------


class TransformRotate(TypedDict):
    """Rotation transform in degrees (numeric) or with explicit unit suffix."""

    rotate: Union[float, str]


class TransformScale(TypedDict):
    """Uniform scale transform."""

    scale: float


class TransformScaleX(TypedDict):
    """Horizontal-only scale transform."""

    scale_x: float


class TransformScaleY(TypedDict):
    """Vertical-only scale transform."""

    scale_y: float


class TransformTranslate(TypedDict, total=False):
    """Translation transform along one or both axes."""

    translate_x: float
    translate_y: float


TransformEntry = Union[
    TransformRotate,
    TransformScale,
    TransformScaleX,
    TransformScaleY,
    TransformTranslate,
    Dict[str, Any],
]
"""A single transform operation."""

TransformSpec = Union[TransformEntry, List[TransformEntry]]
"""``transform`` style value: a single operation or an ordered list."""


# ----------------------------------------------------------------------
# Enum-shaped style values
# ----------------------------------------------------------------------

FlexDirection = Literal["row", "column", "row_reverse", "column_reverse"]
FlexWrap = Literal["nowrap", "wrap", "wrap_reverse"]
AlignContent = Literal[
    "flex_start",
    "center",
    "flex_end",
    "stretch",
    "space_between",
    "space_around",
    "space_evenly",
]
LayoutDirection = Literal["ltr", "rtl"]
JustifyContent = Literal[
    "flex_start",
    "center",
    "flex_end",
    "space_between",
    "space_around",
    "space_evenly",
    "start",
    "leading",
    "top",
    "end",
    "trailing",
    "bottom",
]
AlignItems = Literal[
    "stretch",
    "flex_start",
    "center",
    "flex_end",
    "auto",
    "start",
    "leading",
    "top",
    "end",
    "trailing",
    "bottom",
    "fill",
]
AlignSelf = AlignItems
Position = Literal["relative", "absolute"]
Overflow = Literal["visible", "hidden", "scroll"]
TextAlign = Literal["left", "center", "right", "justify", "start", "end"]
TextDecoration = Literal["none", "underline", "line_through"]
FontWeight = Literal[
    "normal",
    "bold",
    "100",
    "200",
    "300",
    "400",
    "500",
    "600",
    "700",
    "800",
    "900",
]
ScaleType = Literal["cover", "contain", "stretch", "center"]
KeyboardType = Literal[
    "default",
    "email_address",
    "number_pad",
    "decimal_pad",
    "phone_pad",
    "url",
]
AutoCapitalize = Literal["none", "sentences", "words", "characters"]
ReturnKeyType = Literal["default", "done", "go", "next", "send", "search"]


# ======================================================================
# Style TypedDict
# ======================================================================


class Style(TypedDict, total=False):
    """Statically-typed style dictionary.

    Lists every style property recognized by the built-in components
    plus their layout engine, with enum-shaped values constrained via
    [`Literal`][typing.Literal]. ``Style`` is a `total=False` TypedDict
    so any subset of keys is valid at construction time.

    Custom native components may accept additional, unlisted keys;
    they are ignored by the built-in handlers but flow through the
    reconciler unmodified, so third-party handlers can read them.

    Example:
        ```python
        import pythonnative as pn

        title: pn.Style = {
            "font_size": 24,
            "color": "#0A84FF",
            "text_align": "center",
        }

        pn.Text("Hello", style=title)
        ```
    """

    # --- Layout: sizing ---
    width: Dimension
    height: Dimension
    min_width: Dimension
    max_width: Dimension
    min_height: Dimension
    max_height: Dimension
    aspect_ratio: float

    # --- Layout: flex ---
    flex: float
    flex_grow: float
    flex_shrink: float
    flex_basis: Dimension
    flex_direction: FlexDirection
    flex_wrap: FlexWrap
    justify_content: JustifyContent
    align_items: AlignItems
    align_self: AlignSelf
    align_content: AlignContent
    direction: LayoutDirection

    # --- Layout: position ---
    position: Position
    top: Dimension
    right: Dimension
    bottom: Dimension
    left: Dimension
    start: Dimension
    end: Dimension

    # --- Layout: spacing ---
    padding: EdgeValue
    padding_top: Dimension
    padding_bottom: Dimension
    padding_left: Dimension
    padding_right: Dimension
    padding_start: Dimension
    padding_end: Dimension
    padding_horizontal: Dimension
    padding_vertical: Dimension
    margin: EdgeValue
    margin_top: Dimension
    margin_bottom: Dimension
    margin_left: Dimension
    margin_right: Dimension
    margin_start: Dimension
    margin_end: Dimension
    margin_horizontal: Dimension
    margin_vertical: Dimension
    spacing: float
    gap: float
    row_gap: float
    column_gap: float

    # --- Visual: clipping & overflow ---
    overflow: Overflow

    # --- Visual: colors ---
    background_color: Color
    color: Color
    border_color: Color
    placeholder_color: Color
    tint_color: Color

    # --- Visual: borders ---
    border_width: float
    border_radius: float
    border_top_width: float
    border_right_width: float
    border_bottom_width: float
    border_left_width: float
    border_top_color: Color
    border_right_color: Color
    border_bottom_color: Color
    border_left_color: Color

    # --- Visual: typography ---
    font_size: float
    font_family: str
    font_weight: FontWeight
    bold: bool
    italic: bool
    text_align: TextAlign
    text_decoration: TextDecoration
    line_height: float
    letter_spacing: float
    max_lines: int

    # --- Visual: shadows / effects ---
    shadow_color: Color
    shadow_offset: Union[ShadowOffset, Tuple[float, float], List[float]]
    shadow_opacity: float
    shadow_radius: float
    elevation: float
    opacity: float
    transform: TransformSpec


StyleProp = Union[Style, Dict[str, Any], List[Optional[Union[Style, Dict[str, Any]]]], None]
"""Public type for the ``style`` parameter on every component factory.

Accepts a [`Style`][pythonnative.Style] TypedDict (recommended), a
plain ``Dict[str, Any]`` (forward-compat / unrestricted), a list of
either with ``None`` entries skipped, or ``None``."""


# ======================================================================
# Runtime helpers
# ======================================================================


def style(**properties: Any) -> Style:
    """Construct a [`Style`][pythonnative.Style] from keyword arguments.

    Equivalent to ``Style(...)`` but works with any Python version
    (``TypedDict.__init__`` is fragile prior to 3.11) and reads more
    naturally inside expressions:

    ```python
    pn.View(child, style=pn.style(padding=16, background_color="#fff"))
    ```

    Unknown keys are accepted at runtime to keep the door open for
    third-party styling extensions; static type checkers will still
    reject them when this helper's return type is annotated as
    ``Style``.

    Args:
        **properties: Style key/value pairs.

    Returns:
        A fresh ``Style`` dict containing the supplied entries.
    """
    return properties  # type: ignore[return-value]


def resolve_style(value: StyleProp) -> Dict[str, Any]:
    """Flatten a `style` prop into a single dict.

    Accepts ``None``, a single dict (``Style`` or untyped), or a list of
    dicts (later entries override earlier ones, mirroring React Native's
    array-style pattern). Used by every built-in element factory in
    `pythonnative.components`.

    Args:
        value: The raw value of the component's `style` argument.

    Returns:
        A flat dict suitable for the native handler. Always a fresh
        dict, never the input.
    """
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    result: Dict[str, Any] = {}
    for entry in value:
        if entry:
            result.update(entry)
    return result


_KNOWN_STYLE_KEYS = frozenset(Style.__annotations__)
"""Every key declared on the [`Style`][pythonnative.Style] TypedDict."""


def validate_style_keys(style_dict: Dict[str, Any], owner: str = "") -> None:
    """Warn (once per key) about style keys no built-in handler reads.

    Dev-mode only; production skips the scan entirely. Typos get a
    "did you mean" suggestion via fuzzy matching against the declared
    [`Style`][pythonnative.Style] keys. Unknown keys still flow through
    to handlers untouched, so custom components that read extra keys
    keep working (at the cost of one dev warning).

    Args:
        style_dict: The flattened style dict about to be merged into an
            element's props.
        owner: Element type name for the warning message (e.g.
            ``"Text"``).
    """
    if not diagnostics.is_dev() or not style_dict:
        return
    for key in style_dict:
        if key in _KNOWN_STYLE_KEYS:
            continue
        matches = difflib.get_close_matches(str(key), _KNOWN_STYLE_KEYS, n=1)
        hint = f" Did you mean {matches[0]!r}?" if matches else ""
        diagnostics.warn_once(
            f"Unknown style key {key!r}"
            + (f" on {owner}" if owner else "")
            + f".{hint} Built-in components ignore keys they don't recognize.",
            key=f"style:{owner}:{key}",
        )


# ======================================================================
# StyleSheet
# ======================================================================


class StyleSheet:
    """Utility for creating, composing, and flattening style dictionaries.

    All methods are stateless and return fresh dicts, so the values can
    be reused safely across components.
    """

    @staticmethod
    def create(**named_styles: Style) -> Dict[str, Style]:
        """Create a set of named styles from keyword arguments.

        Args:
            **named_styles: Each keyword argument is a style name
                mapping to a [`Style`][pythonnative.Style] dict.

        Returns:
            A dict mapping each name to a copy of the supplied style,
            so the caller can mutate the result without affecting the
            originals.

        Example:
            ```python
            from pythonnative import StyleSheet, style

            styles = StyleSheet.create(
                heading=style(font_size=28, bold=True),
                body=style(font_size=16),
            )
            ```
        """
        return {name: dict(props) for name, props in named_styles.items()}  # type: ignore[misc]

    @staticmethod
    def compose(*styles: StyleProp) -> Style:
        """Merge multiple style dicts.

        Args:
            *styles: Style dicts to merge. Later dicts override keys
                from earlier ones. Falsy entries (``None``) are skipped.
                List entries are flattened in turn.

        Returns:
            A new ``Style`` dict containing the merged result.
        """
        merged: Dict[str, Any] = {}
        for entry in styles:
            if entry is None:
                continue
            if isinstance(entry, dict):
                merged.update(entry)
                continue
            for nested in entry:
                if nested:
                    merged.update(nested)
        return merged  # type: ignore[return-value]

    @staticmethod
    def flatten(styles: StyleProp) -> Style:
        """Flatten a style value or list of styles into a single dict.

        Equivalent to
        [`resolve_style`][pythonnative.style.resolve_style] but exposed
        on `StyleSheet` for parity with React Native's API and typed
        as returning a ``Style``.

        Args:
            styles: A single dict, a list of dicts, or `None`.

        Returns:
            A flat ``Style`` dict combining the inputs.
        """
        return resolve_style(styles)  # type: ignore[return-value]

    @staticmethod
    def absolute_fill() -> Style:
        """Return a style that absolutely fills the parent.

        Convenience preset matching React Native's
        ``StyleSheet.absoluteFill``: ``position: "absolute"`` with
        every inset pinned to ``0``.
        """
        return {"position": "absolute", "top": 0, "right": 0, "bottom": 0, "left": 0}


# ======================================================================
# Theming
# ======================================================================

DEFAULT_LIGHT_THEME: Dict[str, Any] = {
    "primary_color": "#007AFF",
    "secondary_color": "#5856D6",
    "background_color": "#FFFFFF",
    "surface_color": "#F2F2F7",
    "text_color": "#000000",
    "text_secondary_color": "#8E8E93",
    "error_color": "#FF3B30",
    "success_color": "#34C759",
    "warning_color": "#FF9500",
    "font_size": 16,
    "font_size_small": 13,
    "font_size_large": 20,
    "font_size_title": 28,
    "spacing": 8,
    "spacing_large": 16,
    "border_radius": 8,
}
"""Built-in light theme selected by [`use_theme`][pythonnative.use_theme]."""

DEFAULT_DARK_THEME: Dict[str, Any] = {
    "primary_color": "#0A84FF",
    "secondary_color": "#5E5CE6",
    "background_color": "#000000",
    "surface_color": "#1C1C1E",
    "text_color": "#FFFFFF",
    "text_secondary_color": "#8E8E93",
    "error_color": "#FF453A",
    "success_color": "#30D158",
    "warning_color": "#FF9F0A",
    "font_size": 16,
    "font_size_small": 13,
    "font_size_large": 20,
    "font_size_title": 28,
    "spacing": 8,
    "spacing_large": 16,
    "border_radius": 8,
}
"""Built-in dark theme selected by [`use_theme`][pythonnative.use_theme]."""

_FOLLOW_SYSTEM_THEME = object()
"""Sentinel default for `ThemeContext`: resolve from the color scheme."""

ThemeContext: Context = create_context(_FOLLOW_SYSTEM_THEME)
"""Theme context that follows the system color scheme by default.

Without a provider, [`use_theme`][pythonnative.use_theme] resolves to
[`DEFAULT_LIGHT_THEME`][pythonnative.style.DEFAULT_LIGHT_THEME] or
[`DEFAULT_DARK_THEME`][pythonnative.style.DEFAULT_DARK_THEME] based on
the current appearance. Wrap a subtree in
[`Provider(ThemeContext, my_theme, ...)`][pythonnative.Provider] to
pin an explicit theme for that subtree, then read it inside
descendants via [`use_theme`][pythonnative.use_theme] (or
[`use_context(ThemeContext)`][pythonnative.use_context]).
"""


def default_theme(scheme: str) -> Dict[str, Any]:
    """Return the built-in theme dict for ``scheme`` (``"light"`` / ``"dark"``)."""
    return DEFAULT_DARK_THEME if scheme == "dark" else DEFAULT_LIGHT_THEME


def use_theme() -> Dict[str, Any]:
    """Return the active theme, following the system appearance by default.

    If an ancestor mounted a ``Provider(ThemeContext, ...)``, that
    theme is returned as-is. Otherwise the built-in light or dark
    theme is selected from the effective color scheme (via
    [`use_color_scheme`][pythonnative.use_color_scheme], so the
    component re-renders when the system appearance flips).

    Returns:
        The active theme dict.

    Raises:
        RuntimeError: If called outside a `@component` function.

    Example:
        ```python
        import pythonnative as pn

        @pn.component
        def Card():
            theme = pn.use_theme()
            return pn.View(
                pn.Text("Hello", style=pn.style(color=theme["text_color"])),
                style=pn.style(background_color=theme["surface_color"]),
            )
        ```
    """
    scheme = use_color_scheme()
    theme = use_context(ThemeContext)
    if theme is _FOLLOW_SYSTEM_THEME:
        return default_theme(scheme)
    return theme


__all__ = [
    "AlignItems",
    "AlignSelf",
    "AutoCapitalize",
    "Color",
    "DEFAULT_DARK_THEME",
    "DEFAULT_LIGHT_THEME",
    "Dimension",
    "EdgeInsets",
    "EdgeValue",
    "FlexDirection",
    "FontWeight",
    "JustifyContent",
    "KeyboardType",
    "Overflow",
    "Position",
    "ReturnKeyType",
    "ScaleType",
    "ShadowOffset",
    "Style",
    "StyleProp",
    "StyleSheet",
    "TextAlign",
    "TextDecoration",
    "ThemeContext",
    "TransformEntry",
    "TransformRotate",
    "TransformScale",
    "TransformScaleX",
    "TransformScaleY",
    "TransformSpec",
    "TransformTranslate",
    "default_theme",
    "resolve_style",
    "style",
    "use_theme",
    "validate_style_keys",
]
