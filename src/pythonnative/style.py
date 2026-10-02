"""The typed [`Style`][pythonnative.Style], style resolution, and style sheets.

PythonNative ships a single, fully typed [`Style`][pythonnative.Style]
``TypedDict`` that enumerates every supported style property and
constrains enum-shaped values with [`typing.Literal`][typing.Literal].
Editors and type checkers (mypy, pyright) autocomplete and validate
every key: ``flex_direction="collumn"`` is a static error, not a silent
runtime no-op.

Style values are plain dicts at runtime, so they're trivial to compose,
diff, and store. Pass one dict or a list of them (later entries win,
``None`` entries are skipped); [`resolve_style`][pythonnative.style.resolve_style]
flattens the list and resolves the ``inset*`` shorthands.

Group related styles in a [`StyleSheet`][pythonnative.StyleSheet]
namespace, and derive theme-dependent styles with
[`use_styles`][pythonnative.use_styles]:

```python
import pythonnative as pn


class Styles(pn.StyleSheet):
    container = pn.style(padding=16, gap=12)
    title = pn.style(font_size=24, font_weight="700")


pn.Column(pn.Text("Hello", style=Styles.title), style=Styles.container)
```
"""

import difflib
from typing import (
    Any,
    Dict,
    List,
    Literal,
    NotRequired,
    Optional,
    Sequence,
    Tuple,
    TypedDict,
    Union,
    Unpack,
    get_args,
)

from . import diagnostics

# ======================================================================
# Atomic value types
# ======================================================================


class DynamicColor(TypedDict):
    """A color pair resolved against the current color scheme.

    Every renderer (iOS, Android, and the browser preview) picks
    ``light`` or ``dark`` when the style is applied and switches when
    the appearance changes.
    """

    light: str
    dark: str


Color = Union[str, DynamicColor]
"""Color value: ``"#RRGGBB"``, ``"#AARRGGBB"``, any string a platform
handler recognizes (e.g., ``"red"``), or a
[`DynamicColor`][pythonnative.DynamicColor] ``{"light": ..., "dark": ...}``
pair. Strings are stored verbatim and parsed by the handler at apply-time,
so palettes from third-party libraries pass through unchanged."""

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


class AccessibilityValue(TypedDict, total=False):
    """The current value of a range-like or text-valued widget, for assistive technology.

    Passed via ``accessibility_value=`` (a plain string is also
    accepted and equivalent to ``{"text": ...}``). Use ``min``, ``max``,
    and ``now`` for sliders and progress indicators, ``text`` for
    everything else.

    Attributes:
        min: Lower bound of the range.
        max: Upper bound of the range.
        now: Current value within the range.
        text: Spoken description of the current value.
    """

    min: float
    max: float
    now: float
    text: str


class AccessibilityAction(TypedDict):
    """One custom action a screen reader may invoke on a view.

    Passed via ``accessibility_actions=[...]``; the view's
    ``on_accessibility_action`` callback receives the action ``name``.
    The standard names ``"activate"``, ``"increment"``, ``"decrement"``,
    ``"longpress"``, ``"magicTap"``, and ``"escape"`` map to the
    platform's built-in actions; any other name is a custom action
    announced with ``label``.

    Attributes:
        name: Identifier reported to ``on_accessibility_action``.
        label: Spoken description of a custom action.
    """

    name: str
    label: NotRequired[str]


ImportantForAccessibility = Literal["auto", "yes", "no", "no_hide_descendants"]
"""``important_for_accessibility`` value: whether assistive technology
sees the view (``"yes"``), skips it (``"no"``), skips it and its subtree
(``"no_hide_descendants"``), or decides itself (``"auto"``)."""


class ShadowOffset(TypedDict):
    """Shadow displacement in points."""

    width: float
    height: float


ShadowOffsetValue = Union[ShadowOffset, Tuple[float, float], List[float]]
"""``shadow_offset`` / ``text_shadow_offset`` value: an
[`ShadowOffset`][pythonnative.ShadowOffset] dict or an ``(x, y)`` pair."""


# ----------------------------------------------------------------------
# Transforms
# ----------------------------------------------------------------------


class TransformRotate(TypedDict):
    """Rotation around the z axis in degrees (numeric) or with an explicit unit suffix."""

    rotate: Union[float, str]


class TransformRotateX(TypedDict):
    """Rotation around the x axis (a 3D tilt) in degrees or with a unit suffix."""

    rotate_x: Union[float, str]


class TransformRotateY(TypedDict):
    """Rotation around the y axis (a 3D flip) in degrees or with a unit suffix."""

    rotate_y: Union[float, str]


class TransformRotateZ(TypedDict):
    """Rotation around the z axis; an explicit spelling of ``rotate``."""

    rotate_z: Union[float, str]


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


class TransformSkewX(TypedDict):
    """Horizontal skew in degrees or with a unit suffix."""

    skew_x: Union[float, str]


class TransformSkewY(TypedDict):
    """Vertical skew in degrees or with a unit suffix."""

    skew_y: Union[float, str]


class TransformPerspective(TypedDict):
    """Perspective distance for the 3D rotations that follow it in the list."""

    perspective: float


TransformEntry = Union[
    TransformRotate,
    TransformRotateX,
    TransformRotateY,
    TransformRotateZ,
    TransformScale,
    TransformScaleX,
    TransformScaleY,
    TransformTranslate,
    TransformSkewX,
    TransformSkewY,
    TransformPerspective,
    Dict[str, Any],
]
"""A single transform operation. Every renderer supports the whole set;
iOS composes them into a ``CATransform3D``."""

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
    "baseline",
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
Display = Literal["flex", "none"]
"""``display`` style value. ``"none"`` removes the node and its subtree
from layout entirely (no size, gap, or margin contribution; every frame
in the subtree is ``(0, 0, 0, 0)``)."""
Overflow = Literal["visible", "hidden", "scroll"]
TextAlign = Literal["left", "center", "right", "justify", "start", "end"]
TextDecoration = Literal["none", "underline", "line_through"]
TextTransform = Literal["none", "uppercase", "lowercase", "capitalize"]
"""``text_transform`` style value. Applied in Python before the string
reaches the native label, so measurement and rendering agree."""
MarginValue = Union[Dimension, Literal["auto"]]
"""A margin length: points, a ``"%"`` string, or ``"auto"`` to absorb free space."""
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
BorderStyle = Literal["solid", "dashed", "dotted"]
"""``border_style`` style value, drawn the same way on every renderer."""
KeyboardType = Literal[
    "default",
    "email_address",
    "number_pad",
    "decimal_pad",
    "phone_pad",
    "url",
    "ascii",
    "numbers_and_punctuation",
    "web_search",
    "visible_password",
]
"""``keyboard_type`` value. ``"ascii"``, ``"numbers_and_punctuation"``,
and ``"web_search"`` are iOS keyboards (Android and the browser fall back
to the closest input type); ``"visible_password"`` is Android's
unmasked password keyboard."""
AutoCapitalize = Literal["none", "sentences", "words", "characters"]
ReturnKeyType = Literal["default", "done", "go", "next", "send", "search"]
PointerEvents = Literal["auto", "none", "box_none", "box_only"]
"""Touch-handling mode for a view and its subtree:

- ``"auto"``: the view and its children receive touches (default).
- ``"none"``: neither the view nor its children receive touches;
  touches pass through to whatever is underneath.
- ``"box_none"``: the view itself ignores touches but its children
  still receive them (decorative overlays with interactive content).
- ``"box_only"``: the view receives touches but its children do not.
"""


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
    display: Display

    # --- Layout: position ---
    position: Position
    top: Dimension
    right: Dimension
    bottom: Dimension
    left: Dimension
    start: Dimension
    end: Dimension
    # Shorthands resolved by ``resolve_style`` into the four edges above;
    # explicit ``top`` / ``right`` / ``bottom`` / ``left`` keys win.
    inset: Dimension
    inset_horizontal: Dimension
    inset_vertical: Dimension

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
    margin: Union[MarginValue, EdgeInsets]
    margin_top: MarginValue
    margin_bottom: MarginValue
    margin_left: MarginValue
    margin_right: MarginValue
    margin_start: MarginValue
    margin_end: MarginValue
    margin_horizontal: MarginValue
    margin_vertical: MarginValue
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
    border_style: BorderStyle
    border_radius: float
    border_top_left_radius: float
    border_top_right_radius: float
    border_bottom_left_radius: float
    border_bottom_right_radius: float
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
    text_transform: TextTransform
    line_height: float
    letter_spacing: float
    max_lines: int
    text_shadow_color: Color
    text_shadow_offset: ShadowOffsetValue
    text_shadow_radius: float

    # --- Visual: shadows / effects ---
    # Shadows follow React Native's platform split: the ``shadow_*``
    # keys draw on iOS and in the browser preview, ``elevation`` draws
    # Android's material shadow. Each platform ignores the other's keys.
    shadow_color: Color
    shadow_offset: ShadowOffsetValue
    shadow_opacity: float
    shadow_radius: float
    elevation: float
    opacity: float
    transform: TransformSpec

    # --- Interaction & stacking ---
    z_index: int
    pointer_events: PointerEvents


StyleProp = Union[Style, Sequence[Optional[Style]], None]
"""Public type for the ``style`` parameter on every component factory.

Accepts a [`Style`][pythonnative.Style] TypedDict, a sequence of them
with ``None`` entries skipped, or ``None``. ``Style`` is a ``TypedDict``,
so a plain dict literal type-checks against it and still works at
runtime."""


# ======================================================================
# Runtime helpers
# ======================================================================


def style(**properties: Unpack[Style]) -> Style:
    """Construct a [`Style`][pythonnative.Style] from keyword arguments.

    Equivalent to ``Style(...)`` but reads more naturally inside
    expressions, and typed with ``Unpack[Style]`` so a type checker
    rejects a misspelled key such as ``pn.style(colour="red")``:

    ```python
    pn.View(child, style=pn.style(padding=16, background_color="#fff"))
    ```

    At runtime the keys aren't checked here; the factories warn once
    per unknown key in dev mode through
    [`validate_style_keys`][pythonnative.style.validate_style_keys].

    Args:
        **properties: Style key/value pairs.

    Returns:
        A fresh ``Style`` dict containing the supplied entries.
    """
    return properties


_INSET_SHORTHANDS: Dict[str, Tuple[str, ...]] = {
    "inset": ("top", "right", "bottom", "left"),
    "inset_horizontal": ("left", "right"),
    "inset_vertical": ("top", "bottom"),
}
"""Position shorthands and the edges each one fills, least specific first."""


def _expand_insets(result: Dict[str, Any]) -> None:
    """Replace ``inset*`` shorthands with the four edge keys, in place.

    Mirrors the padding vocabulary: ``inset`` fills every edge, the axis
    shorthands override it, and an explicit ``top`` / ``right`` /
    ``bottom`` / ``left`` wins over both, regardless of key order. The
    wire only ever carries the four edges.
    """
    explicit: Dict[str, Any] = {edge: result[edge] for edge in ("top", "right", "bottom", "left") if edge in result}
    for shorthand, edges in _INSET_SHORTHANDS.items():
        if shorthand not in result:
            continue
        value = result.pop(shorthand)
        if value is None:
            continue
        for edge in edges:
            result[edge] = value
    result.update(explicit)


def resolve_style(value: StyleProp) -> Dict[str, Any]:
    """Flatten a `style` prop into a single dict.

    Accepts ``None``, a single dict, or a sequence of dicts (later
    entries override earlier ones, mirroring React Native's array-style
    pattern), then resolves the ``inset``, ``inset_horizontal``, and
    ``inset_vertical`` shorthands into ``top`` / ``right`` / ``bottom``
    / ``left``. Used by every built-in element factory in
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
        result: Dict[str, Any] = dict(value)
    else:
        result = {}
        for entry in value:
            if entry:
                result.update(entry)
    if result.keys() & _INSET_SHORTHANDS.keys():
        _expand_insets(result)
    return result


_KNOWN_STYLE_KEYS = frozenset(Style.__annotations__)
"""Every key declared on the [`Style`][pythonnative.Style] TypedDict."""

_STYLE_VALUE_CHOICES: Dict[str, frozenset] = {
    "display": frozenset(get_args(Display)),
    "position": frozenset(get_args(Position)),
    "direction": frozenset(get_args(LayoutDirection)),
    "text_decoration": frozenset(get_args(TextDecoration)),
    "text_transform": frozenset(get_args(TextTransform)),
    "pointer_events": frozenset(get_args(PointerEvents)),
    "border_style": frozenset(get_args(BorderStyle)),
}
"""Keys whose string values are checked against their ``Literal`` choices
in dev mode. Only keys whose handlers accept exactly the declared
literals are listed, so friendly aliases (``align_items: "leading"``,
``font_weight: "semibold"``) never trigger false positives."""


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _text_shadow_offset_ok(value: Any) -> bool:
    if isinstance(value, dict):
        return all(_is_number(value.get(k, 0)) for k in ("width", "height"))
    if isinstance(value, (tuple, list)) and len(value) == 2:
        return all(_is_number(v) for v in value)
    return False


def _bad_value_message(key: str, value: Any) -> Optional[str]:
    """Return a description of why ``value`` is invalid for ``key``, or ``None``."""
    choices = _STYLE_VALUE_CHOICES.get(key)
    if choices is not None:
        if not isinstance(value, str) or value not in choices:
            allowed = ", ".join(repr(c) for c in sorted(choices))
            return f"Invalid value {value!r} for style key {key!r}; expected one of {allowed}."
        return None
    if key == "text_shadow_offset" and not _text_shadow_offset_ok(value):
        return (
            f"Invalid value {value!r} for style key 'text_shadow_offset'; "
            "expected {'width': x, 'height': y} or an (x, y) pair."
        )
    if key == "text_shadow_radius" and (not _is_number(value) or value < 0):
        return f"Invalid value {value!r} for style key 'text_shadow_radius'; expected a non-negative number."
    return None


def validate_style_keys(style_dict: Dict[str, Any], owner: str = "") -> None:
    """Warn (once per key) about style keys no built-in handler reads.

    Dev-mode only; production skips the scan entirely. Typos get a
    "did you mean" suggestion via fuzzy matching against the declared
    [`Style`][pythonnative.Style] keys. Unknown keys still flow through
    to handlers untouched, so custom components that read extra keys
    keep working (at the cost of one dev warning).

    A small set of enum-shaped keys (``display``, ``position``,
    ``direction``, ``text_decoration``, ``text_transform``,
    ``pointer_events``, ``border_style``) and the ``text_shadow_*`` keys also have their
    values checked; a bad value warns once per key/value pair and is
    otherwise passed through (the engine and handlers ignore values
    they don't recognize).

    Args:
        style_dict: The flattened style dict about to be merged into an
            element's props.
        owner: Element type name for the warning message (e.g.
            ``"Text"``).
    """
    if not diagnostics.is_dev() or not style_dict:
        return
    for key, value in style_dict.items():
        if key in _KNOWN_STYLE_KEYS:
            if value is None:
                continue
            problem = _bad_value_message(key, value)
            if problem is not None:
                diagnostics.warn_once(
                    problem + (f" (on {owner})" if owner else ""),
                    key=f"style-value:{owner}:{key}:{value!r}",
                )
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
    """Base class for a namespace of named styles.

    Subclass it and assign [`Style`][pythonnative.Style] dicts as class
    attributes. Attribute access is typed, so a misspelled style name is
    a static error, and every style is checked for unknown keys once in
    dev mode:

    ```python
    class Styles(pn.StyleSheet):
        card = pn.style(padding=16, border_radius=12)
        title = pn.style(font_size=17, font_weight="600")


    pn.View(pn.Text("Hello", style=Styles.title), style=Styles.card)
    ```

    Compose styles with a list (``style=[Styles.card, {"opacity": 0.5}]``).
    For styles derived from the theme, see
    [`use_styles`][pythonnative.use_styles]. A style sheet is a
    namespace, not an object: instantiating one raises ``TypeError``.
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        for name, value in vars(cls).items():
            if not name.startswith("_") and isinstance(value, dict):
                validate_style_keys(value, owner=f"{cls.__name__}.{name}")

    def __new__(cls, *args: Any, **kwargs: Any) -> "StyleSheet":
        """Refuse instantiation: a style sheet is a namespace, not an object."""
        raise TypeError(f"{cls.__name__} is a namespace of styles; use {cls.__name__}.<name> instead of calling it")


ABSOLUTE_FILL: Style = {"position": "absolute", "top": 0, "right": 0, "bottom": 0, "left": 0}
"""A style that absolutely fills the parent, like React Native's ``StyleSheet.absoluteFill``."""


__all__ = [
    "ABSOLUTE_FILL",
    "AccessibilityAction",
    "AccessibilityState",
    "AccessibilityValue",
    "AlignItems",
    "AlignSelf",
    "AutoCapitalize",
    "BorderStyle",
    "Color",
    "Dimension",
    "Display",
    "DynamicColor",
    "EdgeInsets",
    "EdgeValue",
    "FlexDirection",
    "FontWeight",
    "ImportantForAccessibility",
    "JustifyContent",
    "KeyboardType",
    "MarginValue",
    "Overflow",
    "PointerEvents",
    "Position",
    "ReturnKeyType",
    "ScaleType",
    "ShadowOffset",
    "ShadowOffsetValue",
    "Style",
    "StyleProp",
    "StyleSheet",
    "TextAlign",
    "TextDecoration",
    "TextTransform",
    "TransformEntry",
    "TransformPerspective",
    "TransformRotate",
    "TransformRotateX",
    "TransformRotateY",
    "TransformRotateZ",
    "TransformScale",
    "TransformScaleX",
    "TransformScaleY",
    "TransformSkewX",
    "TransformSkewY",
    "TransformSpec",
    "TransformTranslate",
    "resolve_style",
    "style",
    "validate_style_keys",
]
