"""Built-in element factories and the typed prop schemas they share.

Each ``@dataclass(frozen=True)`` class in this module (``TextProps``,
``ButtonProps``, etc.) is the canonical schema for one built-in
component. Each factory function (``Text``, ``Button``, …) is a thin
ergonomic wrapper that builds an [`Element`][pythonnative.Element]
through the shared :func:`_make_element` helper, so style resolution,
``ref`` attachment, ``None``-default dropping, and forced overrides
(e.g. ``Column``'s fixed ``flex_direction``) live in exactly one place.

The same Props dataclasses are used by the `pythonnative.sdk` surface
for third-party components, so the built-in API and the extension API
speak the same shape.

Example:
    ```python
    import pythonnative as pn

    pn.Column(
        pn.Text("Hello", style=pn.style(font_size=18)),
        pn.Button("Tap", on_click=lambda: print("tapped")),
        style=pn.style(spacing=12, padding=16),
    )
    ```
"""

import bisect
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple

from .element import Element
from .hooks import component, use_effect, use_ref, use_state
from .sdk import Props
from .style import (
    AutoCapitalize,
    Color,
    KeyboardType,
    ReturnKeyType,
    ScaleType,
    StyleProp,
    resolve_style,
)

# ======================================================================
# Canonical element builder
# ======================================================================


def _make_element(
    name: str,
    *children: Element,
    style: StyleProp = None,
    ref: Optional[Dict[str, Any]] = None,
    key: Optional[str] = None,
    _defaults: Optional[Dict[str, Any]] = None,
    _forced: Optional[Dict[str, Any]] = None,
    **props: Any,
) -> Element:
    """Build an [`Element`][pythonnative.Element] of type ``name``.

    This is the single helper every built-in factory routes through, so
    the cross-cutting concerns that used to be duplicated per component
    live in one place:

    1. ``style`` is flattened via
       [`resolve_style`][pythonnative.style.resolve_style] (list-of-dicts
       and ``None`` both handled).
    2. ``_defaults`` are filled in for keys not already present (used for
       things like ``View``'s default ``flex_direction: "column"`` that
       a user style may legitimately override).
    3. ``**props`` are merged on top, with ``None`` values *dropped* so
       optional kwargs don't pollute the prop dict.
    4. ``ref`` is attached under the reserved ``"ref"`` key.
    5. ``_forced`` overrides everything (used by ``Column`` / ``Row`` to
       lock their flex direction regardless of user style).

    Args:
        name: Element type name (e.g. ``"Text"``).
        *children: Child elements.
        style: Style dict, list of dicts, or ``None``.
        ref: Optional ``use_ref()`` dict; the reconciler populates
            ``ref["current"]`` with the underlying native view.
        key: Stable identity for keyed reconciliation.
        _defaults: Internal: fill-only-if-missing prop defaults.
        _forced: Internal: prop overrides applied last.
        **props: Per-component props. ``None`` values are dropped.

    Returns:
        A fresh [`Element`][pythonnative.Element].
    """
    out: Dict[str, Any] = dict(resolve_style(style))
    if _defaults:
        for k, v in _defaults.items():
            out.setdefault(k, v)
    for k, v in props.items():
        if v is not None:
            out[k] = v
    if ref is not None:
        out["ref"] = ref
    if _forced:
        out.update(_forced)
    return Element(name, out, list(children), key=key)


# ======================================================================
# Props dataclasses
# ======================================================================
#
# These are the canonical schemas for every built-in component. They
# subclass the SDK's ``Props`` base, so the same shape works for both
# the built-in factory functions and the third-party
# [`element_factory`][pythonnative.element_factory] API.


@dataclass(frozen=True)
class TextProps(Props):
    """Props for [`Text`][pythonnative.Text]."""

    text: str = ""
    accessibility_label: Optional[str] = None
    accessibility_hint: Optional[str] = None
    accessibility_role: Optional[str] = None
    accessible: Optional[bool] = None


@dataclass(frozen=True)
class ButtonProps(Props):
    """Props for [`Button`][pythonnative.Button]."""

    title: str = ""
    on_click: Optional[Callable[[], None]] = None
    enabled: bool = True
    accessibility_label: Optional[str] = None
    accessibility_hint: Optional[str] = None
    accessibility_role: Optional[str] = None
    accessible: Optional[bool] = None


@dataclass(frozen=True)
class TextInputProps(Props):
    """Props for [`TextInput`][pythonnative.TextInput]."""

    value: str = ""
    placeholder: Optional[str] = None
    on_change: Optional[Callable[[str], None]] = None
    on_submit: Optional[Callable[[str], None]] = None
    secure: bool = False
    multiline: bool = False
    keyboard_type: Optional[KeyboardType] = None
    auto_capitalize: Optional[AutoCapitalize] = None
    auto_correct: Optional[bool] = None
    auto_focus: bool = False
    return_key_type: Optional[ReturnKeyType] = None
    max_length: Optional[int] = None
    placeholder_color: Optional[Color] = None
    editable: bool = True
    clear_button: bool = False
    on_focus: Optional[Callable[[], None]] = None
    on_blur: Optional[Callable[[], None]] = None
    selection_color: Optional[Color] = None
    text_content_type: Optional[str] = None
    accessibility_label: Optional[str] = None
    accessibility_hint: Optional[str] = None
    accessible: Optional[bool] = None


@dataclass(frozen=True)
class ImageProps(Props):
    """Props for [`Image`][pythonnative.Image]."""

    source: Optional[str] = None
    scale_type: Optional[ScaleType] = None
    tint_color: Optional[Color] = None
    accessibility_label: Optional[str] = None
    accessibility_role: Optional[str] = None
    accessible: Optional[bool] = None


@dataclass(frozen=True)
class SwitchProps(Props):
    """Props for [`Switch`][pythonnative.Switch]."""

    value: bool = False
    on_change: Optional[Callable[[bool], None]] = None
    accessibility_label: Optional[str] = None


@dataclass(frozen=True)
class ProgressBarProps(Props):
    """Props for [`ProgressBar`][pythonnative.ProgressBar]."""

    value: float = 0.0
    color: Optional[Color] = None
    track_color: Optional[Color] = None
    indeterminate: bool = False


@dataclass(frozen=True)
class ActivityIndicatorProps(Props):
    """Props for [`ActivityIndicator`][pythonnative.ActivityIndicator]."""

    animating: bool = True
    color: Optional[Color] = None
    size: Literal["small", "large"] = "small"


@dataclass(frozen=True)
class WebViewProps(Props):
    """Props for [`WebView`][pythonnative.WebView]."""

    url: Optional[str] = None
    html: Optional[str] = None
    on_load: Optional[Callable[[str], None]] = None
    on_message: Optional[Callable[[str], None]] = None
    on_navigation_state_change: Optional[Callable[[str], None]] = None
    inject_javascript: Optional[str] = None
    scroll_enabled: bool = True


@dataclass(frozen=True)
class SpacerProps(Props):
    """Props for [`Spacer`][pythonnative.Spacer]."""

    size: Optional[float] = None
    flex: Optional[float] = None


@dataclass(frozen=True)
class SliderProps(Props):
    """Props for [`Slider`][pythonnative.Slider]."""

    value: float = 0.0
    min_value: float = 0.0
    max_value: float = 1.0
    on_change: Optional[Callable[[float], None]] = None
    accessibility_label: Optional[str] = None


@dataclass(frozen=True)
class ViewProps(Props):
    """Props for [`View`][pythonnative.View], [`Column`][pythonnative.Column], and [`Row`][pythonnative.Row]."""

    gestures: Optional[List[Any]] = None
    accessibility_label: Optional[str] = None
    accessibility_hint: Optional[str] = None
    accessibility_role: Optional[str] = None
    accessible: Optional[bool] = None


@dataclass(frozen=True)
class ScrollViewProps(Props):
    """Props for [`ScrollView`][pythonnative.ScrollView].

    ``on_scroll`` receives a single payload dict with ``"x"`` and
    ``"y"`` content offsets in points.
    """

    refresh_control: Optional[Dict[str, Any]] = None
    scroll_axis: Optional[Literal["vertical", "horizontal"]] = None
    on_scroll: Optional[Callable[[Dict[str, float]], None]] = None
    shows_scroll_indicator: bool = True
    paging_enabled: bool = False
    bounces: bool = True
    content_container_style: StyleProp = None
    keyboard_dismiss_mode: Optional[Literal["none", "on_drag", "interactive"]] = None


@dataclass(frozen=True)
class SafeAreaViewProps(Props):
    """Props for [`SafeAreaView`][pythonnative.SafeAreaView]."""


@dataclass(frozen=True)
class ModalProps(Props):
    """Props for [`Modal`][pythonnative.Modal]."""

    visible: bool = False
    on_dismiss: Optional[Callable[[], None]] = None
    on_show: Optional[Callable[[], None]] = None
    title: Optional[str] = None
    animation_type: Literal["slide", "fade", "none"] = "slide"
    transparent: bool = False
    presentation_style: Literal["page_sheet", "form_sheet", "full_screen", "overlay"] = "page_sheet"
    dismiss_on_backdrop: bool = True


@dataclass(frozen=True)
class PressableProps(Props):
    """Props for [`Pressable`][pythonnative.Pressable]."""

    on_press: Optional[Callable[[], None]] = None
    on_long_press: Optional[Callable[[], None]] = None
    on_press_in: Optional[Callable[[], None]] = None
    on_press_out: Optional[Callable[[], None]] = None
    pressed_opacity: float = 0.6
    gestures: Optional[List[Any]] = None
    accessibility_label: Optional[str] = None
    accessibility_hint: Optional[str] = None
    accessibility_role: Optional[str] = None
    accessible: Optional[bool] = None


@dataclass(frozen=True)
class StatusBarProps(Props):
    """Props for [`StatusBar`][pythonnative.StatusBar]."""

    bar_style: Optional[Literal["light", "dark", "default"]] = None
    background_color: Optional[Color] = None
    hidden: Optional[bool] = None


@dataclass(frozen=True)
class KeyboardAvoidingViewProps(Props):
    """Props for [`KeyboardAvoidingView`][pythonnative.KeyboardAvoidingView]."""

    behavior: Literal["padding", "position"] = "padding"


@dataclass(frozen=True)
class PickerProps(Props):
    """Props for [`Picker`][pythonnative.Picker].

    ``items`` is an ordered list of ``{"value": Any, "label": str}``
    entries. ``value`` is matched against ``items[i]["value"]`` to
    determine the currently selected row.
    """

    value: Any = None
    items: List[Dict[str, Any]] = field(default_factory=list)
    on_change: Optional[Callable[[Any], None]] = None
    placeholder: str = "Select…"
    accessibility_label: Optional[str] = None
    accessibility_hint: Optional[str] = None
    accessible: Optional[bool] = None


@dataclass(frozen=True)
class TouchableOpacityProps(Props):
    """Props for [`TouchableOpacity`][pythonnative.TouchableOpacity]."""

    on_press: Optional[Callable[[], None]] = None
    on_long_press: Optional[Callable[[], None]] = None
    active_opacity: float = 0.2
    disabled: bool = False
    accessibility_label: Optional[str] = None
    accessibility_hint: Optional[str] = None
    accessibility_role: Optional[str] = None
    accessible: Optional[bool] = None


@dataclass(frozen=True)
class ImageBackgroundProps(Props):
    """Props for [`ImageBackground`][pythonnative.ImageBackground]."""

    source: Optional[str] = None
    scale_type: Optional[ScaleType] = None
    accessibility_label: Optional[str] = None
    accessible: Optional[bool] = None


@dataclass(frozen=True)
class CheckboxProps(Props):
    """Props for [`Checkbox`][pythonnative.Checkbox]."""

    value: bool = False
    on_change: Optional[Callable[[bool], None]] = None
    label: Optional[str] = None
    disabled: bool = False
    color: Optional[Color] = None
    accessibility_label: Optional[str] = None
    accessibility_hint: Optional[str] = None
    accessible: Optional[bool] = None


@dataclass(frozen=True)
class SegmentedControlProps(Props):
    """Props for [`SegmentedControl`][pythonnative.SegmentedControl]."""

    segments: List[str] = field(default_factory=list)
    selected_index: int = 0
    on_change: Optional[Callable[[int], None]] = None
    enabled: bool = True
    tint_color: Optional[Color] = None
    accessibility_label: Optional[str] = None
    accessible: Optional[bool] = None


@dataclass(frozen=True)
class DatePickerProps(Props):
    """Props for [`DatePicker`][pythonnative.DatePicker].

    ``value`` and the value passed to ``on_change`` are ISO-8601
    strings (``"2026-05-31"`` for ``mode="date"``, ``"14:30"`` for
    ``mode="time"``, ``"2026-05-31T14:30"`` for ``mode="datetime"``),
    so the schema stays JSON-serializable and platform-agnostic.
    """

    value: Optional[str] = None
    mode: Literal["date", "time", "datetime"] = "date"
    on_change: Optional[Callable[[str], None]] = None
    minimum: Optional[str] = None
    maximum: Optional[str] = None
    enabled: bool = True
    accessibility_label: Optional[str] = None
    accessible: Optional[bool] = None


# ======================================================================
# Leaf factories
# ======================================================================


def Text(
    text: str = "",
    *,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessibility_hint: Optional[str] = None,
    accessibility_role: Optional[str] = None,
    accessible: Optional[bool] = None,
    ref: Optional[Dict[str, Any]] = None,
    key: Optional[str] = None,
) -> Element:
    """Display a string of text.

    Style properties: ``font_size``, ``color``, ``bold``,
    ``font_weight``, ``font_family``, ``italic``, ``text_align``,
    ``background_color``, ``max_lines``, ``letter_spacing``,
    ``line_height``, ``text_decoration`` (``"underline"`` /
    ``"line_through"``), ``border_radius``, ``border_width``,
    ``border_color``, ``shadow_*``, ``opacity``, ``transform``, plus
    the common layout props.

    Args:
        text: Text content to display.
        style: Style dict (or list of dicts).
        accessibility_label: Spoken description for screen readers.
        accessibility_hint: Spoken extra detail (iOS only).
        accessibility_role: Semantic role for assistive tech.
        accessible: Override whether the element is exposed to AT.
        ref: Optional ``use_ref()`` dict.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"Text"``.
    """
    return _make_element(
        "Text",
        style=style,
        ref=ref,
        key=key,
        text=text,
        accessibility_label=accessibility_label,
        accessibility_hint=accessibility_hint,
        accessibility_role=accessibility_role,
        accessible=accessible,
    )


def Button(
    title: str = "",
    *,
    on_click: Optional[Callable[[], None]] = None,
    enabled: bool = True,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessibility_hint: Optional[str] = None,
    accessibility_role: Optional[str] = None,
    accessible: Optional[bool] = None,
    ref: Optional[Dict[str, Any]] = None,
    key: Optional[str] = None,
) -> Element:
    """Display a tappable button.

    Style properties: ``color``, ``background_color``, ``font_size``,
    ``border_radius``, ``border_width``, ``border_color``, ``shadow_*``,
    ``opacity``, ``transform``, plus the common layout props.

    Buttons get ``accessibility_role="button"`` by default.

    Args:
        title: Button label.
        on_click: Callback invoked when the user taps the button.
        enabled: When ``False``, the button is disabled and cannot be
            tapped.
        style: Style dict (or list of dicts).
        accessibility_label: Spoken description for screen readers.
        accessibility_hint: Spoken extra detail (iOS only).
        accessibility_role: Override the default ``"button"`` role.
        accessible: Override whether the element is exposed to AT.
        ref: Optional ``use_ref()`` dict.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"Button"``.
    """
    return _make_element(
        "Button",
        style=style,
        ref=ref,
        key=key,
        title=title,
        on_click=on_click,
        enabled=enabled,
        accessibility_label=accessibility_label,
        accessibility_hint=accessibility_hint,
        accessibility_role=accessibility_role,
        accessible=accessible,
        _defaults={"accessibility_role": "button"},
    )


def TextInput(
    *,
    value: str = "",
    placeholder: Optional[str] = None,
    on_change: Optional[Callable[[str], None]] = None,
    on_submit: Optional[Callable[[str], None]] = None,
    secure: bool = False,
    multiline: bool = False,
    keyboard_type: Optional[KeyboardType] = None,
    auto_capitalize: Optional[AutoCapitalize] = None,
    auto_correct: Optional[bool] = None,
    auto_focus: bool = False,
    return_key_type: Optional[ReturnKeyType] = None,
    max_length: Optional[int] = None,
    placeholder_color: Optional[Color] = None,
    editable: bool = True,
    clear_button: bool = False,
    on_focus: Optional[Callable[[], None]] = None,
    on_blur: Optional[Callable[[], None]] = None,
    selection_color: Optional[Color] = None,
    text_content_type: Optional[str] = None,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessibility_hint: Optional[str] = None,
    accessible: Optional[bool] = None,
    ref: Optional[Dict[str, Any]] = None,
    key: Optional[str] = None,
) -> Element:
    """Display a text-entry field (single-line by default, or ``multiline``).

    Style properties: ``font_size``, ``color``, ``background_color``,
    ``border_*``, plus the common layout props.

    Args:
        value: Current text content (controlled-input pattern).
        placeholder: Hint shown when ``value`` is empty.
        on_change: Callback invoked with the new string each keystroke.
        on_submit: Callback invoked when the user submits (Return /
            Done / etc.). Receives the final text.
        secure: When ``True``, characters are masked (use for passwords).
        multiline: When ``True``, allows multiple lines of input.
        keyboard_type: One of ``"default"``, ``"email_address"``,
            ``"number_pad"``, ``"decimal_pad"``, ``"phone_pad"``, ``"url"``.
        auto_capitalize: One of ``"none"``, ``"sentences"``, ``"words"``,
            ``"characters"``.
        auto_correct: Enable/disable autocorrection.
        auto_focus: Request focus on mount.
        return_key_type: One of ``"default"``, ``"done"``, ``"go"``,
            ``"next"``, ``"send"``, ``"search"``.
        max_length: Maximum number of characters allowed.
        placeholder_color: Color used for the placeholder string.
        editable: When ``False``, the field is read-only (still
            selectable).
        clear_button: When ``True``, shows a clear ("x") button while
            editing (iOS ``clearButtonMode``; an inline button on
            Android).
        on_focus: Callback invoked when the field gains focus.
        on_blur: Callback invoked when the field loses focus.
        selection_color: Cursor / selection highlight color.
        text_content_type: Semantic content hint for autofill (e.g.
            ``"username"``, ``"password"``, ``"one_time_code"``).
        style: Style dict (or list of dicts).
        accessibility_label: Spoken description for screen readers.
        accessibility_hint: Spoken extra detail (iOS only).
        accessible: Override whether the element is exposed to AT.
        ref: Optional ``use_ref()`` dict.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"TextInput"``.
    """
    return _make_element(
        "TextInput",
        style=style,
        ref=ref,
        key=key,
        value=value,
        placeholder=placeholder,
        on_change=on_change,
        on_submit=on_submit,
        secure=secure or None,
        multiline=multiline or None,
        keyboard_type=keyboard_type,
        auto_capitalize=auto_capitalize,
        auto_correct=auto_correct,
        auto_focus=auto_focus or None,
        return_key_type=return_key_type,
        max_length=max_length,
        placeholder_color=placeholder_color,
        editable=False if editable is False else None,
        clear_button=clear_button or None,
        on_focus=on_focus,
        on_blur=on_blur,
        selection_color=selection_color,
        text_content_type=text_content_type,
        accessibility_label=accessibility_label,
        accessibility_hint=accessibility_hint,
        accessible=accessible,
    )


def Image(
    source: str = "",
    *,
    scale_type: Optional[ScaleType] = None,
    tint_color: Optional[Color] = None,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessibility_role: Optional[str] = None,
    accessible: Optional[bool] = None,
    ref: Optional[Dict[str, Any]] = None,
    key: Optional[str] = None,
) -> Element:
    """Display an image from a resource path or URL.

    Style properties: ``background_color``, ``border_*``, ``opacity``,
    ``transform``, plus the common layout props.

    Network images (``http://`` / ``https://``) are loaded
    asynchronously off the main thread on both iOS (via
    ``NSURLSession``) and Android (via a worker thread plus
    ``BitmapFactory``).

    Args:
        source: Image resource name or URL.
        scale_type: Fit mode: ``"cover"``, ``"contain"``, ``"stretch"``,
            ``"center"``.
        tint_color: Color overlay applied to template images
            (monochrome icons).
        style: Style dict (or list of dicts).
        accessibility_label: Spoken description for screen readers.
        accessibility_role: Override the default ``"image"`` role.
        accessible: Override whether the element is exposed to AT.
        ref: Optional ``use_ref()`` dict.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"Image"``.
    """
    return _make_element(
        "Image",
        style=style,
        ref=ref,
        key=key,
        source=source or None,
        scale_type=scale_type,
        tint_color=tint_color,
        accessibility_label=accessibility_label,
        accessibility_role=accessibility_role,
        accessible=accessible,
        _defaults={"accessibility_role": "image"},
    )


def Switch(
    *,
    value: bool = False,
    on_change: Optional[Callable[[bool], None]] = None,
    accessibility_label: Optional[str] = None,
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """Display a toggle switch.

    Args:
        value: Current on/off state.
        on_change: Callback invoked with the new boolean state.
        accessibility_label: Label exposed to assistive technology (and
            UI test drivers) for the switch.
        style: Style dict (or list of dicts).
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"Switch"``.
    """
    return _make_element(
        "Switch",
        style=style,
        key=key,
        value=value,
        on_change=on_change,
        accessibility_label=accessibility_label,
    )


def ProgressBar(
    *,
    value: float = 0.0,
    color: Optional[Color] = None,
    track_color: Optional[Color] = None,
    indeterminate: bool = False,
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """Show determinate progress as a value between ``0.0`` and ``1.0``.

    For a spinner instead of a bar, use
    [`ActivityIndicator`][pythonnative.ActivityIndicator]; for an
    indeterminate *bar* pass ``indeterminate=True``.

    Args:
        value: Fraction complete (clamped to ``[0.0, 1.0]`` by the
            platform handler).
        color: Color of the filled portion of the bar.
        track_color: Color of the unfilled track behind the fill.
        indeterminate: When ``True``, the bar animates continuously and
            ``value`` is ignored.
        style: Style dict (or list of dicts).
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"ProgressBar"``.
    """
    return _make_element(
        "ProgressBar",
        style=style,
        key=key,
        value=value,
        color=color,
        track_color=track_color,
        indeterminate=indeterminate or None,
    )


def ActivityIndicator(
    *,
    animating: bool = True,
    color: Optional[Color] = None,
    size: Literal["small", "large"] = "small",
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """Show an indeterminate loading spinner.

    Args:
        animating: When ``False``, the spinner is hidden.
        color: Spinner color.
        size: ``"small"`` (default) or ``"large"``.
        style: Style dict (or list of dicts).
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type
        ``"ActivityIndicator"``.
    """
    return _make_element(
        "ActivityIndicator",
        style=style,
        key=key,
        animating=animating,
        color=color,
        size=size,
    )


def WebView(
    *,
    url: str = "",
    html: Optional[str] = None,
    on_load: Optional[Callable[[str], None]] = None,
    on_message: Optional[Callable[[str], None]] = None,
    on_navigation_state_change: Optional[Callable[[str], None]] = None,
    inject_javascript: Optional[str] = None,
    scroll_enabled: bool = True,
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """Embed web content from a URL or an inline HTML string.

    Args:
        url: HTTP(S) URL to load. Ignored when ``html`` is given.
        html: Inline HTML markup to render instead of loading a URL.
        on_load: Callback invoked with the final URL once a page
            finishes loading.
        on_message: Callback invoked with the string payload whenever
            page JavaScript calls
            ``window.pythonnative.postMessage(...)``.
        on_navigation_state_change: Callback invoked with the URL each
            time the top-level document begins navigating.
        inject_javascript: JavaScript evaluated after each page load
            (useful for installing the ``postMessage`` bridge or
            tweaking the DOM).
        scroll_enabled: When ``False``, disables scrolling inside the
            web content.
        style: Style dict (or list of dicts).
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"WebView"``.
    """
    return _make_element(
        "WebView",
        style=style,
        key=key,
        url=url or None,
        html=html,
        on_load=on_load,
        on_message=on_message,
        on_navigation_state_change=on_navigation_state_change,
        inject_javascript=inject_javascript,
        scroll_enabled=False if scroll_enabled is False else None,
    )


def Spacer(
    *,
    size: Optional[float] = None,
    flex: Optional[float] = None,
    key: Optional[str] = None,
) -> Element:
    """Insert empty space inside a flex container.

    Pass ``size`` for a fixed gap, or ``flex`` to expand and absorb
    remaining space.

    Args:
        size: Fixed gap in dp/pt along the parent's main axis. Mirrored
            on both axes: whichever axis the parent's
            ``flex_direction`` chooses as main becomes the actual gap.
        flex: Flex-grow weight; useful for pushing siblings to the
            opposite end of a [`Row`][pythonnative.Row] or
            [`Column`][pythonnative.Column].
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"Spacer"``.
    """
    width = size if size is not None else None
    height = size if size is not None else None
    return _make_element(
        "Spacer",
        key=key,
        size=size,
        width=width,
        height=height,
        flex=flex,
    )


def Slider(
    *,
    value: float = 0.0,
    min_value: float = 0.0,
    max_value: float = 1.0,
    on_change: Optional[Callable[[float], None]] = None,
    accessibility_label: Optional[str] = None,
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """Continuous-value slider between ``min_value`` and ``max_value``.

    Args:
        value: Current slider value.
        min_value: Lower bound.
        max_value: Upper bound.
        on_change: Callback invoked with the new value as the user
            drags.
        accessibility_label: Label exposed to assistive technology (and
            UI test drivers) for the slider.
        style: Style dict (or list of dicts).
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"Slider"``.
    """
    return _make_element(
        "Slider",
        style=style,
        key=key,
        value=value,
        min_value=min_value,
        max_value=max_value,
        on_change=on_change,
        accessibility_label=accessibility_label,
    )


# ======================================================================
# Container factories
# ======================================================================


def View(
    *children: Element,
    style: StyleProp = None,
    gestures: Optional[List[Any]] = None,
    accessibility_label: Optional[str] = None,
    accessibility_hint: Optional[str] = None,
    accessibility_role: Optional[str] = None,
    accessible: Optional[bool] = None,
    ref: Optional[Dict[str, Any]] = None,
    key: Optional[str] = None,
) -> Element:
    """Universal flex container (like React Native's ``View``).

    Defaults to ``flex_direction: "column"`` (override via ``style``).

    Flex container properties (passed via ``style``):

    - ``flex_direction``: ``"column"`` (default), ``"row"``,
      ``"column_reverse"``, ``"row_reverse"``.
    - ``flex_wrap``: ``"nowrap"`` (default), ``"wrap"``,
      ``"wrap_reverse"``, with ``align_content`` controlling how
      wrapped lines share leftover cross-axis space.
    - ``justify_content``: main-axis distribution. Accepts
      ``"flex_start"`` (default), ``"center"``, ``"flex_end"``,
      ``"space_between"``, ``"space_around"``, ``"space_evenly"``.
    - ``align_items``: cross-axis alignment. Accepts ``"stretch"``
      (default), ``"flex_start"``, ``"center"``, ``"flex_end"``.
    - ``direction``: ``"ltr"`` (default) or ``"rtl"``. Flips rows and
      resolves ``margin_start`` / ``padding_end`` / absolute ``start``
      / ``end`` insets.
    - ``overflow``: ``"visible"`` (default) or ``"hidden"``.
    - ``spacing`` (alias ``gap``; per-axis ``row_gap`` /
      ``column_gap``), ``padding``, ``background_color``,
      ``border_radius``, ``border_width``, ``border_color``,
      ``shadow_color``, ``shadow_offset``, ``shadow_opacity``,
      ``shadow_radius``, ``elevation``, ``opacity``, ``transform``.

    Args:
        *children: Child elements rendered inside the container.
        style: Style dict (or list of dicts).
        gestures: Optional list of gesture descriptors from
            `pythonnative.gestures` (e.g. ``[gestures.Pan(on_change=…)]``)
            recognized natively on this view.
        accessibility_label: Spoken description for screen readers.
        accessibility_hint: Spoken extra detail (iOS only).
        accessibility_role: Semantic role for assistive tech.
        accessible: Override whether the element is exposed to AT.
        ref: Optional ``use_ref()`` dict.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"View"``.
    """
    return _make_element(
        "View",
        *children,
        style=style,
        ref=ref,
        key=key,
        gestures=gestures,
        accessibility_label=accessibility_label,
        accessibility_hint=accessibility_hint,
        accessibility_role=accessibility_role,
        accessible=accessible,
        _defaults={"flex_direction": "column"},
    )


def Column(
    *children: Element,
    style: StyleProp = None,
    ref: Optional[Dict[str, Any]] = None,
    key: Optional[str] = None,
) -> Element:
    """Arrange children vertically.

    Convenience wrapper around [`View`][pythonnative.View] with
    ``flex_direction`` locked to ``"column"``. Use ``View`` directly if
    you need to switch between row and column at runtime.

    Args:
        *children: Child elements stacked top to bottom.
        style: Style dict (or list of dicts).
        ref: Optional ``use_ref()`` dict for native-view access.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"Column"``.
    """
    return _make_element(
        "Column",
        *children,
        style=style,
        ref=ref,
        key=key,
        _forced={"flex_direction": "column"},
    )


def Row(
    *children: Element,
    style: StyleProp = None,
    ref: Optional[Dict[str, Any]] = None,
    key: Optional[str] = None,
) -> Element:
    """Arrange children horizontally.

    Convenience wrapper around [`View`][pythonnative.View] with
    ``flex_direction`` locked to ``"row"``. Use ``View`` directly if you
    need to switch between row and column at runtime.

    Args:
        *children: Child elements arranged left to right.
        style: Style dict (or list of dicts).
        ref: Optional ``use_ref()`` dict for native-view access.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"Row"``.
    """
    return _make_element(
        "Row",
        *children,
        style=style,
        ref=ref,
        key=key,
        _forced={"flex_direction": "row"},
    )


def ScrollView(
    *children: Element,
    refresh_control: Optional[Dict[str, Any]] = None,
    scroll_axis: Optional[Literal["vertical", "horizontal"]] = None,
    on_scroll: Optional[Callable[[Dict[str, float]], None]] = None,
    shows_scroll_indicator: bool = True,
    paging_enabled: bool = False,
    bounces: bool = True,
    content_container_style: StyleProp = None,
    keyboard_dismiss_mode: Optional[Literal["none", "on_drag", "interactive"]] = None,
    style: StyleProp = None,
    ref: Optional[Dict[str, Any]] = None,
    key: Optional[str] = None,
) -> Element:
    """Wrap children in a scrollable container.

    ``ScrollView`` typically takes a single child (a ``Column`` or
    ``Row`` aggregating the scrollable content). It accepts ``*children``
    for ergonomic call sites; the underlying native scroll view stacks
    them on its content axis.

    Args:
        *children: Child elements to scroll.
        refresh_control: Optional pull-to-refresh spec, typically
            constructed via
            [`RefreshControl`][pythonnative.RefreshControl]. The dict
            must have ``refreshing`` (bool) and ``on_refresh``
            (callable).
        scroll_axis: ``"vertical"`` (default) or ``"horizontal"``.
        on_scroll: Callback invoked with ``{"x": …, "y": …}`` content
            offsets as the user scrolls.
        shows_scroll_indicator: When ``False``, hides the scroll bar.
        paging_enabled: When ``True``, the scroll view snaps to
            multiples of its own size (carousel behavior).
        bounces: When ``False``, disables the iOS rubber-band overscroll.
        content_container_style: Style applied to the inner content
            wrapper (padding, alignment, spacing of the scrollable
            content), distinct from ``style`` (the scroll view frame).
        keyboard_dismiss_mode: ``"none"`` (default), ``"on_drag"``, or
            ``"interactive"``. Controls whether scrolling dismisses
            the keyboard.
        style: Style dict (or list of dicts).
        ref: Optional ``use_ref()`` dict.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"ScrollView"``.
    """
    return _make_element(
        "ScrollView",
        *children,
        style=style,
        ref=ref,
        key=key,
        refresh_control=refresh_control,
        scroll_axis=scroll_axis,
        on_scroll=on_scroll,
        shows_scroll_indicator=False if shows_scroll_indicator is False else None,
        paging_enabled=paging_enabled or None,
        bounces=False if bounces is False else None,
        content_container_style=resolve_style(content_container_style) or None,
        keyboard_dismiss_mode=keyboard_dismiss_mode,
    )


def SafeAreaView(
    *children: Element,
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """Container that respects safe-area insets (notch, status bar, home indicator).

    Args:
        *children: Child elements that should avoid system UI overlays.
        style: Style dict (or list of dicts).
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"SafeAreaView"``.
    """
    return _make_element(
        "SafeAreaView",
        *children,
        style=style,
        key=key,
    )


def Modal(
    *children: Element,
    visible: bool = False,
    on_dismiss: Optional[Callable[[], None]] = None,
    on_show: Optional[Callable[[], None]] = None,
    title: Optional[str] = None,
    animation_type: Literal["slide", "fade", "none"] = "slide",
    transparent: bool = False,
    presentation_style: Literal["page_sheet", "form_sheet", "full_screen", "overlay"] = "page_sheet",
    dismiss_on_backdrop: bool = True,
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """Overlay modal dialog backed by a real native presentation.

    The modal is shown when ``visible=True`` and hidden when ``False``.
    Drive ``visible`` from a hook so the parent component can dismiss
    the modal in response to user actions. On iOS this presents a
    ``UIViewController``; on Android it shows an ``android.app.Dialog``.

    Children are mounted as the modal's content view, not into the
    on-tree placeholder, so they appear above all other native content
    and don't influence the underlying layout.

    Args:
        *children: Modal content.
        visible: Controls whether the modal is presented.
        on_dismiss: Callback invoked when the user dismisses the modal
            via system gesture.
        on_show: Callback invoked once the modal has finished
            presenting.
        title: Optional title-bar text.
        animation_type: ``"slide"`` (default), ``"fade"``, or ``"none"``.
        transparent: When ``True``, the underlying view is dimmed
            instead of fully covered.
        presentation_style: iOS presentation style,
            ``"page_sheet"`` (default), ``"form_sheet"``,
            ``"full_screen"``, or ``"overlay"`` (custom dimmed
            overlay). On Android, ``"overlay"`` keeps the dialog
            non-fullscreen.
        dismiss_on_backdrop: When ``True`` (default) and
            ``transparent`` / ``"overlay"``, tapping the dimmed
            backdrop dismisses the modal.
        style: Style dict (or list of dicts).
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"Modal"``.
    """
    return _make_element(
        "Modal",
        *children,
        style=style,
        key=key,
        visible=visible,
        animation_type=animation_type,
        transparent=transparent,
        presentation_style=presentation_style,
        dismiss_on_backdrop=False if dismiss_on_backdrop is False else None,
        on_dismiss=on_dismiss,
        on_show=on_show,
        title=title,
    )


def Pressable(
    *children: Element,
    on_press: Optional[Callable[[], None]] = None,
    on_long_press: Optional[Callable[[], None]] = None,
    on_press_in: Optional[Callable[[], None]] = None,
    on_press_out: Optional[Callable[[], None]] = None,
    pressed_opacity: float = 0.6,
    gestures: Optional[List[Any]] = None,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessibility_hint: Optional[str] = None,
    accessibility_role: Optional[str] = None,
    accessible: Optional[bool] = None,
    ref: Optional[Dict[str, Any]] = None,
    key: Optional[str] = None,
) -> Element:
    """Wrap children with tap / long-press / gesture handlers.

    Useful for making non-button elements (text, images, custom views)
    respond to user taps. The wrapper view fades to ``pressed_opacity``
    on touch-down and back to full opacity on touch-up.

    Pressable gets ``accessibility_role="button"`` by default.

    Args:
        *children: Elements to make pressable.
        on_press: Callback invoked on a normal tap.
        on_long_press: Callback invoked on a sustained press.
        on_press_in: Callback invoked the moment the press starts.
        on_press_out: Callback invoked when the press lifts or cancels.
        pressed_opacity: Opacity (0–1) applied while the user's finger
            is down. Set to ``1.0`` for no visual feedback.
        gestures: Optional list of gesture descriptors from
            `pythonnative.gestures` recognized natively on this view
            (pan / swipe / pinch / rotation / multi-tap).
        style: Style dict applied to the wrapper.
        accessibility_label: Spoken description for screen readers.
        accessibility_hint: Spoken extra detail (iOS only).
        accessibility_role: Override the default ``"button"`` role.
        accessible: Override whether the element is exposed to AT.
        ref: Optional ``use_ref()`` dict.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"Pressable"``.
    """
    return _make_element(
        "Pressable",
        *children,
        style=style,
        ref=ref,
        key=key,
        on_press=on_press,
        on_long_press=on_long_press,
        on_press_in=on_press_in,
        on_press_out=on_press_out,
        pressed_opacity=pressed_opacity,
        gestures=gestures,
        accessibility_label=accessibility_label,
        accessibility_hint=accessibility_hint,
        accessibility_role=accessibility_role,
        accessible=accessible,
        _defaults={"accessibility_role": "button"},
    )


# ======================================================================
# Touchables & controls
# ======================================================================


def TouchableOpacity(
    *children: Element,
    on_press: Optional[Callable[[], None]] = None,
    on_long_press: Optional[Callable[[], None]] = None,
    active_opacity: float = 0.2,
    disabled: bool = False,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessibility_hint: Optional[str] = None,
    accessibility_role: Optional[str] = None,
    accessible: Optional[bool] = None,
    key: Optional[str] = None,
) -> Element:
    """Wrap children so they fade to ``active_opacity`` while pressed.

    A thin ergonomic alias over [`Pressable`][pythonnative.Pressable]
    that mirrors React Native's ``TouchableOpacity``: the only visual
    feedback is an opacity dip on touch-down. When ``disabled`` is set,
    the press callbacks are dropped so the wrapper is inert.

    Args:
        *children: Elements to make tappable.
        on_press: Callback invoked on a normal tap.
        on_long_press: Callback invoked on a sustained press.
        active_opacity: Opacity (0–1) applied while the finger is down.
        disabled: When ``True``, ignores presses and renders at reduced
            opacity.
        style: Style dict applied to the wrapper.
        accessibility_label: Spoken description for screen readers.
        accessibility_hint: Spoken extra detail (iOS only).
        accessibility_role: Override the default ``"button"`` role.
        accessible: Override whether the element is exposed to AT.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"Pressable"``.
    """
    merged_style: StyleProp
    if disabled:
        base = resolve_style(style)
        base.setdefault("opacity", 0.4)
        merged_style = base
    else:
        merged_style = style
    return Pressable(
        *children,
        on_press=None if disabled else on_press,
        on_long_press=None if disabled else on_long_press,
        pressed_opacity=active_opacity,
        style=merged_style,
        accessibility_label=accessibility_label,
        accessibility_hint=accessibility_hint,
        accessibility_role=accessibility_role,
        accessible=accessible,
        key=key,
    )


def ImageBackground(
    *children: Element,
    source: str = "",
    scale_type: Optional[ScaleType] = None,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessible: Optional[bool] = None,
    key: Optional[str] = None,
) -> Element:
    """Render ``children`` layered on top of a background image.

    Composed entirely from existing primitives: an absolutely-filled
    [`Image`][pythonnative.Image] sits behind a content
    [`View`][pythonnative.View] holding ``children``. The container's
    ``style`` controls sizing/padding; the image stretches to fill it
    via ``position: "absolute"`` and zeroed insets.

    Args:
        *children: Foreground content drawn over the image.
        source: Image resource name or URL.
        scale_type: Background fit mode (``"cover"`` is the most common
            for backgrounds).
        style: Style dict for the container (size, padding, alignment).
        accessibility_label: Spoken description of the background image.
        accessible: Override whether the image is exposed to AT.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"View"`` wrapping
        the background image and foreground content.
    """
    fill = {"position": "absolute", "top": 0, "left": 0, "right": 0, "bottom": 0}
    background = Image(
        source,
        scale_type=scale_type or "cover",
        style=fill,
        accessibility_label=accessibility_label,
        accessible=accessible,
    )
    content = View(*children, style={"flex": 1})
    return View(
        background,
        content,
        style=[{"overflow": "hidden"}, resolve_style(style)],
        key=key,
    )


def Checkbox(
    *,
    value: bool = False,
    on_change: Optional[Callable[[bool], None]] = None,
    label: Optional[str] = None,
    disabled: bool = False,
    color: Optional[Color] = None,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessibility_hint: Optional[str] = None,
    accessible: Optional[bool] = None,
    key: Optional[str] = None,
) -> Element:
    """A boolean checkbox with an optional inline label.

    Backed by ``android.widget.CheckBox`` on Android and a checkmark
    ``UIButton`` on iOS. Tapping the control (or its label) toggles the
    value and fires ``on_change(new_value)``.

    Args:
        value: Current checked state.
        on_change: Callback invoked with the new boolean state.
        label: Optional text shown beside the box (also tappable).
        disabled: When ``True``, the control is greyed out and inert.
        color: Tint applied to the checked box.
        style: Style dict (or list of dicts).
        accessibility_label: Spoken description for screen readers.
        accessibility_hint: Spoken extra detail (iOS only).
        accessible: Override whether the element is exposed to AT.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"Checkbox"``.
    """
    return _make_element(
        "Checkbox",
        style=style,
        key=key,
        value=value,
        on_change=on_change,
        label=label,
        disabled=disabled or None,
        color=color,
        accessibility_label=accessibility_label,
        accessibility_hint=accessibility_hint,
        accessible=accessible,
        _defaults={"accessibility_role": "checkbox"},
    )


def SegmentedControl(
    *,
    segments: Optional[List[str]] = None,
    selected_index: int = 0,
    on_change: Optional[Callable[[int], None]] = None,
    enabled: bool = True,
    tint_color: Optional[Color] = None,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessible: Optional[bool] = None,
    key: Optional[str] = None,
) -> Element:
    """A horizontal multi-choice control (one selected segment at a time).

    Backed by ``UISegmentedControl`` on iOS and a styled toggle row on
    Android. Selecting a segment fires ``on_change(index)``.

    Args:
        segments: Ordered list of segment labels.
        selected_index: Index of the currently selected segment.
        on_change: Callback invoked with the newly selected index.
        enabled: When ``False``, the control is disabled.
        tint_color: Accent color for the selected segment.
        style: Style dict (or list of dicts).
        accessibility_label: Spoken description for screen readers.
        accessible: Override whether the element is exposed to AT.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type
        ``"SegmentedControl"``.
    """
    return _make_element(
        "SegmentedControl",
        style=style,
        key=key,
        segments=list(segments) if segments is not None else [],
        selected_index=selected_index,
        on_change=on_change,
        enabled=False if enabled is False else None,
        tint_color=tint_color,
        accessibility_label=accessibility_label,
        accessible=accessible,
    )


def DatePicker(
    *,
    value: Optional[str] = None,
    mode: Literal["date", "time", "datetime"] = "date",
    on_change: Optional[Callable[[str], None]] = None,
    minimum: Optional[str] = None,
    maximum: Optional[str] = None,
    enabled: bool = True,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessible: Optional[bool] = None,
    key: Optional[str] = None,
) -> Element:
    """A native date / time picker.

    Backed by ``UIDatePicker`` on iOS and a trigger button that opens
    the platform ``DatePickerDialog`` / ``TimePickerDialog`` on
    Android. ``value`` and the value reported to ``on_change`` are
    ISO-8601 strings (see [`DatePickerProps`][pythonnative.DatePickerProps]).

    Args:
        value: Currently selected value as an ISO-8601 string.
        mode: ``"date"`` (default), ``"time"``, or ``"datetime"``.
        on_change: Callback invoked with the new ISO-8601 string.
        minimum: Earliest selectable value (ISO-8601), if any.
        maximum: Latest selectable value (ISO-8601), if any.
        enabled: When ``False``, the picker is disabled.
        style: Style dict (or list of dicts).
        accessibility_label: Spoken description for screen readers.
        accessible: Override whether the element is exposed to AT.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"DatePicker"``.
    """
    return _make_element(
        "DatePicker",
        style=style,
        key=key,
        value=value,
        mode=mode,
        on_change=on_change,
        minimum=minimum,
        maximum=maximum,
        enabled=False if enabled is False else None,
        accessibility_label=accessibility_label,
        accessible=accessible,
        _defaults={"accessibility_role": "button"},
    )


# ======================================================================
# Fragment
# ======================================================================


def Fragment(*children: Optional[Element], key: Optional[str] = None) -> Element:
    """Group children without adding a wrapping native view.

    Like React's ``<></>``: returns multiple elements from a component
    without introducing an extra container. The reconciler flattens
    Fragment elements at the children-list level, so each child appears
    as a direct sibling of the Fragment's parent in the native tree.

    Useful inside [`Provider`][pythonnative.Provider] /
    [`memo`][pythonnative.memo] / conditional logic when grouping
    siblings inside another component's child list:

    ```python
    pn.Column(
        pn.Text("Top"),
        pn.Fragment(
            pn.Text("Middle A"),
            pn.Text("Middle B"),
        ),
        pn.Text("Bottom"),
    )
    ```

    Args:
        *children: Child elements to expose at the parent level. ``None``
            children are dropped, which makes conditional rendering with
            ``cond and pn.Text(...)`` ergonomic.
        key: Optional key for the Fragment itself (rarely useful since
            Fragment doesn't appear in the native tree).

    Returns:
        An [`Element`][pythonnative.Element] of type ``"__Fragment__"``.

    Note:
        Today, returning a Fragment from a ``@pn.component`` function
        only mounts its first child as the component's root. To return
        multiple top-level elements from a function component, use a
        container such as [`Column`][pythonnative.Column] or
        [`Row`][pythonnative.Row] instead.
    """
    filtered = [c for c in children if c is not None]
    return Element("__Fragment__", {}, filtered, key=key)


# ======================================================================
# Error boundary
# ======================================================================


def ErrorBoundary(
    *children: Element,
    fallback: Optional[Any] = None,
    key: Optional[str] = None,
) -> Element:
    """Catch render errors in the wrapped subtree and display ``fallback`` instead.

    ``fallback`` may be an [`Element`][pythonnative.Element] or a
    callable that receives the exception and returns an ``Element``.
    Useful for isolating risky subtrees so a single failure doesn't
    crash the page.

    When multiple children are passed they're grouped under a
    [`Fragment`][pythonnative.Fragment] so the boundary still wraps a
    single logical subtree.

    Args:
        *children: Subtree to wrap.
        fallback: Element rendered when the subtree raises during
            render, or a callable ``fallback(err) -> Element``.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type
        ``"__ErrorBoundary__"``.

    Example:
        ```python
        import pythonnative as pn

        pn.ErrorBoundary(
            MyRiskyComponent(),
            fallback=lambda err: pn.Text(f"Error: {err}"),
        )
        ```
    """
    props: Dict[str, Any] = {}
    if fallback is not None:
        props["__fallback__"] = fallback
    if len(children) <= 1:
        kids = list(children)
    else:
        kids = [Fragment(*children)]
    return Element("__ErrorBoundary__", props, kids, key=key)


# ======================================================================
# Lists (Python-windowed virtualization over ScrollView)
# ======================================================================
#
# FlatList and SectionList are pure Python components, not native
# elements. They render a windowed slice of rows into a ScrollView
# (leading spacer, visible rows, trailing spacer) and shift the window
# from scroll events (the same architecture as React Native's
# VirtualizedList). Because every windowed row lives in the *main*
# layout tree, rows may be any height: estimates only steer the spacer
# sizes, and each row's measured extent is fed back from the layout
# pass through its ref to correct the estimates over time.

_DEFAULT_ROW_EXTENT = 44.0


class _RowSpec:
    """One virtualized row: a stable key, a lazy renderer, and an extent hint."""

    __slots__ = ("key", "make", "extent", "item", "index")

    def __init__(
        self,
        key: str,
        make: Callable[[], Element],
        extent: Optional[float],
        item: Any = None,
        index: int = 0,
    ) -> None:
        self.key = key
        self.make = make
        self.extent = extent
        self.item = item
        self.index = index


def _dispatch_scroll_command(scroll_ref: Any, name: str, args: Dict[str, Any]) -> Any:
    """Send an imperative command to the ScrollView under ``scroll_ref``."""
    tag = scroll_ref.get("_pn_tag") if isinstance(scroll_ref, dict) else None
    if tag is None:
        return None
    from .native_views import get_registry

    try:
        return get_registry().command(tag, name, args)
    except Exception:
        return None


@component
def _VirtualizedList(**p: Any) -> Element:
    """Shared windowing engine behind FlatList and SectionList."""
    rows: List[_RowSpec] = p.get("rows") or []
    n = len(rows)
    horizontal: bool = bool(p.get("horizontal"))
    estimated: float = float(p.get("estimated_row_extent") or _DEFAULT_ROW_EXTENT)
    overscan: float = float(p.get("overscan_extent") or 0.0)
    initial_extent: float = float(p.get("initial_window_extent") or 800.0)

    window, set_window = use_state((0, -1))
    measured = use_ref({})  # row key -> measured extent (points)
    row_refs = use_ref({})  # row key -> ref dict for live rows
    end_latch = use_ref({"fired_for": -1})
    viewable_ref = use_ref({"keys": ()})
    scroll_pos = use_ref({"offset": 0.0})
    sv_ref = use_ref(None)

    # ------------------------------------------------------------------
    # Extent model: measured > per-row hint > estimate. ``starts`` are
    # prefix sums; ``starts[n]`` is the total content extent.
    # ------------------------------------------------------------------
    measured_map: Dict[str, float] = measured["current"]
    starts: List[float] = [0.0] * (n + 1)
    acc = 0.0
    for i, spec in enumerate(rows):
        starts[i] = acc
        extent = measured_map.get(spec.key)
        if extent is None:
            extent = spec.extent if spec.extent is not None else estimated
        acc += max(0.0, float(extent))
    starts[n] = acc
    total_extent = acc

    def _viewport_extent() -> float:
        frame = sv_ref.get("_pn_frame") if isinstance(sv_ref, dict) else None
        if frame:
            extent = frame[2] if horizontal else frame[3]
            if extent and extent > 0:
                return float(extent)
        return initial_extent

    def _window_for(offset: float, viewport: float) -> Tuple[int, int]:
        if n == 0:
            return (0, -1)
        pad = overscan if overscan > 0 else viewport
        lo = max(0.0, offset - pad)
        hi = offset + viewport + pad
        first = max(0, bisect.bisect_right(starts, lo, 0, n) - 1)
        last = min(n - 1, bisect.bisect_left(starts, hi, 0, n))
        return (first, last)

    first, last = window
    if last < 0 or first >= n:
        first, last = _window_for(scroll_pos["current"]["offset"], _viewport_extent())
    last = min(last, n - 1)
    first = max(0, min(first, max(0, n - 1)))

    # ------------------------------------------------------------------
    # Scroll handling: sweep measured extents, shift the window, fire
    # end-reached / viewability callbacks. State only changes when the
    # window actually moves, so steady scrolling inside the overscan
    # region costs no re-render.
    # ------------------------------------------------------------------
    on_end_reached = p.get("on_end_reached")
    end_threshold = float(p.get("on_end_reached_threshold") or 0.5)
    on_viewable = p.get("on_viewable_items_changed")
    user_on_scroll = p.get("on_scroll")

    def _sweep_measured() -> None:
        for row_key, ref in row_refs["current"].items():
            frame = ref.get("_pn_frame") if isinstance(ref, dict) else None
            if frame:
                extent = frame[2] if horizontal else frame[3]
                if extent and extent > 0:
                    measured_map[row_key] = float(extent)

    def _handle_scroll(payload: Any) -> None:
        if isinstance(payload, dict):
            offset = float(payload.get("x" if horizontal else "y", 0.0) or 0.0)
        else:
            offset = float(payload or 0.0)
        scroll_pos["current"]["offset"] = offset
        _sweep_measured()
        viewport = _viewport_extent()

        new_window = _window_for(offset, viewport)
        if new_window != (first, last):
            set_window(new_window)

        if on_end_reached is not None and total_extent > 0:
            remaining = total_extent - (offset + viewport)
            if remaining <= end_threshold * viewport:
                if end_latch["current"]["fired_for"] != n:
                    end_latch["current"]["fired_for"] = n
                    on_end_reached()
            elif remaining > end_threshold * viewport + viewport:
                end_latch["current"]["fired_for"] = -1

        if on_viewable is not None and n > 0:
            v_first = max(0, bisect.bisect_right(starts, offset, 0, n) - 1)
            v_last = min(n - 1, bisect.bisect_left(starts, offset + viewport, 0, n))
            keys = tuple(rows[i].key for i in range(v_first, v_last + 1))
            if keys != viewable_ref["current"]["keys"]:
                viewable_ref["current"]["keys"] = keys
                on_viewable(
                    [
                        {"index": rows[i].index, "key": rows[i].key, "item": rows[i].item}
                        for i in range(v_first, v_last + 1)
                    ]
                )

        if user_on_scroll is not None:
            user_on_scroll(payload)

    # ------------------------------------------------------------------
    # Imperative controller (scroll_to_index / offset / end) exposed on
    # the user's ref dict. Re-attached every render so the closures see
    # fresh extents; the effect itself must run unconditionally to keep
    # hook order stable.
    # ------------------------------------------------------------------
    controller = p.get("controller_ref")

    def _attach_controller() -> None:
        if not isinstance(controller, dict):
            return

        def scroll_to_offset(offset: float, animated: bool = True) -> None:
            axis = "x" if horizontal else "y"
            _dispatch_scroll_command(sv_ref, "scroll_to_offset", {axis: float(offset), "animated": animated})

        def scroll_to_index(index: int, animated: bool = True) -> None:
            idx = max(0, min(int(index), n - 1)) if n else 0
            scroll_to_offset(starts[idx], animated)

        def scroll_to_end(animated: bool = True) -> None:
            scroll_to_offset(max(0.0, total_extent - _viewport_extent()), animated)

        controller["scroll_to_offset"] = scroll_to_offset
        controller["scroll_to_index"] = scroll_to_index
        controller["scroll_to_end"] = scroll_to_end

    use_effect(_attach_controller, None)

    # ------------------------------------------------------------------
    # Children: header, leading spacer, windowed rows, trailing spacer,
    # footer. Rows keep per-key refs so their measured extents survive
    # recycling.
    # ------------------------------------------------------------------
    spacer_key = "width" if horizontal else "height"
    children: List[Element] = []
    header = p.get("header")
    footer = p.get("footer")
    if header is not None:
        children.append(View(header, key="__pn_header__"))

    if n == 0:
        empty = p.get("empty")
        if empty is not None:
            children.append(View(empty, key="__pn_empty__"))
    else:
        live_refs: Dict[str, Any] = {}
        lead = starts[first]
        if lead > 0:
            lead_style: Dict[str, Any] = {spacer_key: lead}
            children.append(View(style=lead_style, key="__pn_lead__"))
        for i in range(first, last + 1):
            spec = rows[i]
            row_ref = row_refs["current"].get(spec.key) or {"current": None}
            live_refs[spec.key] = row_ref
            children.append(View(spec.make(), ref=row_ref, key=spec.key))
        row_refs["current"] = live_refs
        trail = total_extent - starts[last + 1]
        if trail > 0:
            trail_style: Dict[str, Any] = {spacer_key: trail}
            children.append(View(style=trail_style, key="__pn_trail__"))

    if footer is not None:
        children.append(View(footer, key="__pn_footer__"))

    wrapper = Row if horizontal else Column
    inner = wrapper(*children, style=p.get("content_container_style"))
    return ScrollView(
        inner,
        scroll_axis="horizontal" if horizontal else "vertical",
        on_scroll=_handle_scroll,
        refresh_control=p.get("refresh_control"),
        shows_scroll_indicator=p.get("shows_scroll_indicator", True),
        style=p.get("list_style"),
        ref=sv_ref,
    )


def FlatList(
    *,
    data: Optional[List[Any]] = None,
    render_item: Optional[Callable[[Any, int], Element]] = None,
    key_extractor: Optional[Callable[[Any, int], str]] = None,
    item_height: Optional[float] = None,
    get_item_height: Optional[Callable[[Any, int], float]] = None,
    estimated_item_height: Optional[float] = None,
    separator_height: float = 0,
    refresh_control: Optional[Dict[str, Any]] = None,
    horizontal: bool = False,
    num_columns: int = 1,
    list_header: Optional[Element] = None,
    list_footer: Optional[Element] = None,
    list_empty: Optional[Element] = None,
    on_end_reached: Optional[Callable[[], None]] = None,
    on_end_reached_threshold: float = 0.5,
    on_viewable_items_changed: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    on_scroll: Optional[Callable[[Dict[str, float]], None]] = None,
    shows_scroll_indicator: bool = True,
    content_container_style: StyleProp = None,
    style: StyleProp = None,
    ref: Optional[Dict[str, Any]] = None,
    key: Optional[str] = None,
) -> Element:
    """Virtualized scrollable list that renders items from ``data`` lazily.

    Only the rows inside (and just beyond) the viewport are mounted;
    leading and trailing spacers stand in for everything else, and the
    window shifts as the user scrolls. Rows may have **variable
    heights**: pass ``item_height`` when rows are uniform,
    ``get_item_height`` for exact per-item extents, or nothing at all;
    unknown rows start at ``estimated_item_height`` and are corrected
    with their measured extent once they've been on screen.

    The ``ref`` dict (from [`use_ref`][pythonnative.use_ref]) is
    populated with an imperative controller:
    ``ref["scroll_to_index"](i)``, ``ref["scroll_to_offset"](pts)``,
    and ``ref["scroll_to_end"]()``.

    Args:
        data: List of arbitrary item values.
        render_item: ``render_item(item, index) -> Element``. Defaults
            to wrapping each item in a [`Text`][pythonnative.Text].
        key_extractor: Function returning a stable key per item
            (recommended whenever ``data`` can reorder).
        item_height: Uniform row extent in points, when known.
        get_item_height: ``get_item_height(item, index) -> float`` for
            exact variable extents without measurement.
        estimated_item_height: Starting extent estimate for rows whose
            true size isn't known yet (default 44).
        separator_height: Gap below each row, in points.
        refresh_control: Optional pull-to-refresh spec from
            [`RefreshControl`][pythonnative.RefreshControl].
        horizontal: Scroll horizontally (extents become widths).
        num_columns: Render items in a grid of this many columns.
        list_header: Element rendered once before all rows.
        list_footer: Element rendered once after all rows.
        list_empty: Element rendered when ``data`` is empty.
        on_end_reached: Called when the user scrolls within
            ``on_end_reached_threshold`` viewports of the end (fires
            once per data length).
        on_end_reached_threshold: Distance from the end, in viewport
            multiples, at which ``on_end_reached`` fires.
        on_viewable_items_changed: Called with a list of
            ``{"index", "key", "item"}`` dicts whenever the set of
            visible rows changes.
        on_scroll: Called with the raw scroll payload
            (``{"x": …, "y": …}``).
        shows_scroll_indicator: When ``False``, hides the scroll bar.
        content_container_style: Style applied to the inner content
            wrapper.
        style: Style for the outer scroll container.
        ref: Optional ``use_ref()`` dict; receives the scroll
            controller functions.
        key: Stable identity for keyed reconciliation of the list.

    Returns:
        A virtualized list element (a function component instance).

    Example:
        ```python
        import pythonnative as pn

        items = [{"id": i, "name": f"Item {i}"} for i in range(10000)]

        pn.FlatList(
            data=items,
            item_height=44,
            render_item=lambda item, _: pn.Text(item["name"]),
            key_extractor=lambda item, _: str(item["id"]),
        )
        ```
    """
    items_list = list(data or [])
    sep = float(separator_height or 0.0)

    def _row_key(item: Any, index: int) -> str:
        if key_extractor is not None:
            try:
                return str(key_extractor(item, index))
            except Exception:
                pass
        return f"__pn_row_{index}__"

    def _row_extent(item: Any, index: int) -> Optional[float]:
        if get_item_height is not None:
            try:
                return float(get_item_height(item, index)) + sep
            except Exception:
                return None
        if item_height is not None:
            return float(item_height) + sep
        return None

    def _make_row(item: Any, index: int) -> Callable[[], Element]:
        def _make() -> Element:
            el = render_item(item, index) if render_item else Text(str(item))
            if sep > 0:
                pad_style: Dict[str, Any] = {"padding_end" if horizontal else "padding_bottom": sep}
                return View(el, style=pad_style)
            return el

        return _make

    rows: List[_RowSpec] = []
    if num_columns > 1 and not horizontal:
        for start in range(0, len(items_list), num_columns):
            chunk = items_list[start : start + num_columns]

            def _make_group(group: List[Any] = chunk, base: int = start) -> Element:
                cells = [
                    View(
                        render_item(it, base + j) if render_item else Text(str(it)),
                        style={"flex": 1},
                        key=_row_key(it, base + j),
                    )
                    for j, it in enumerate(group)
                ]
                row = Row(*cells)
                if sep > 0:
                    return View(row, style={"padding_bottom": sep})
                return row

            group_key = "__pn_grp_" + "|".join(_row_key(it, start + j) for j, it in enumerate(chunk))
            extent = (float(item_height) + sep) if item_height is not None else None
            rows.append(_RowSpec(group_key, _make_group, extent, item=chunk, index=start))
    else:
        for i, item in enumerate(items_list):
            rows.append(_RowSpec(_row_key(item, i), _make_row(item, i), _row_extent(item, i), item=item, index=i))

    estimated = estimated_item_height if estimated_item_height is not None else (item_height or _DEFAULT_ROW_EXTENT)

    return _VirtualizedList(
        rows=rows,
        horizontal=horizontal,
        estimated_row_extent=float(estimated) + sep,
        header=list_header,
        footer=list_footer,
        empty=list_empty,
        refresh_control=refresh_control,
        on_end_reached=on_end_reached,
        on_end_reached_threshold=on_end_reached_threshold,
        on_viewable_items_changed=on_viewable_items_changed,
        on_scroll=on_scroll,
        shows_scroll_indicator=shows_scroll_indicator,
        content_container_style=resolve_style(content_container_style) or None,
        list_style=resolve_style(style) or None,
        controller_ref=ref,
        key=key,
    )


def SectionList(
    *,
    sections: Optional[List[Dict[str, Any]]] = None,
    render_item: Optional[Callable[[Any, int, int], Element]] = None,
    render_section_header: Optional[Callable[[Dict[str, Any], int], Element]] = None,
    key_extractor: Optional[Callable[[Any, int], str]] = None,
    item_height: Optional[float] = None,
    get_item_height: Optional[Callable[[Any, int, int], float]] = None,
    estimated_item_height: Optional[float] = None,
    section_header_height: Optional[float] = None,
    separator_height: float = 0,
    refresh_control: Optional[Dict[str, Any]] = None,
    list_header: Optional[Element] = None,
    list_footer: Optional[Element] = None,
    list_empty: Optional[Element] = None,
    on_end_reached: Optional[Callable[[], None]] = None,
    on_end_reached_threshold: float = 0.5,
    on_scroll: Optional[Callable[[Dict[str, float]], None]] = None,
    style: StyleProp = None,
    ref: Optional[Dict[str, Any]] = None,
    key: Optional[str] = None,
) -> Element:
    """Virtualized list with section headers interleaved between row groups.

    Flattens ``sections`` into a single virtualized sequence where each
    entry is either a header or an item, then reuses the same windowing
    engine as [`FlatList`][pythonnative.FlatList]; headers and items
    may have different (and variable) heights.

    Args:
        sections: Each section is ``{"title": ..., "data": [...]}``.
        render_item: ``render_item(item, item_index, section_index) ->
            Element``.
        render_section_header: ``render_section_header(section,
            section_index) -> Element``. Defaults to a bold
            [`Text`][pythonnative.Text] of the section title.
        key_extractor: Stable key per item: ``key_extractor(item,
            item_index) -> str``.
        item_height: Uniform item extent in points, when known.
        get_item_height: ``get_item_height(item, item_index,
            section_index) -> float`` for exact variable extents.
        estimated_item_height: Starting estimate for unmeasured rows.
        section_header_height: Header extent in points, when known.
        separator_height: Gap below each item, in points.
        refresh_control: Optional pull-to-refresh spec.
        list_header: Element rendered once before everything.
        list_footer: Element rendered once after everything.
        list_empty: Element rendered when there are no sections.
        on_end_reached: Called near the end of the content.
        on_end_reached_threshold: Distance from the end, in viewport
            multiples, at which ``on_end_reached`` fires.
        on_scroll: Called with the raw scroll payload.
        style: Style for the outer scroll container.
        ref: Optional ``use_ref()`` dict; receives the scroll
            controller functions.
        key: Stable identity for keyed reconciliation of the list.

    Returns:
        A virtualized list element (a function component instance).
    """
    sections_list = list(sections or [])
    sep = float(separator_height or 0.0)

    def _header_el(section: Dict[str, Any], s_idx: int) -> Element:
        if render_section_header is not None:
            return render_section_header(section, s_idx)
        return Text(str(section.get("title", "")), style={"bold": True, "padding": 8})

    def _item_el(item: Any, i_idx: int, s_idx: int) -> Element:
        if render_item is not None:
            return render_item(item, i_idx, s_idx)
        return Text(str(item))

    rows: List[_RowSpec] = []
    flat_index = 0
    for s_idx, section in enumerate(sections_list):

        def _make_header(sec: Dict[str, Any] = section, si: int = s_idx) -> Element:
            return _header_el(sec, si)

        rows.append(
            _RowSpec(
                f"__pn_sec_{s_idx}__",
                _make_header,
                float(section_header_height) if section_header_height is not None else None,
                item=section,
                index=flat_index,
            )
        )
        flat_index += 1
        for i_idx, item in enumerate(section.get("data", []) or []):
            if key_extractor is not None:
                try:
                    row_key = f"s{s_idx}:" + str(key_extractor(item, i_idx))
                except Exception:
                    row_key = f"__pn_row_{s_idx}_{i_idx}__"
            else:
                row_key = f"__pn_row_{s_idx}_{i_idx}__"

            def _make_item(it: Any = item, ii: int = i_idx, si: int = s_idx) -> Element:
                el = _item_el(it, ii, si)
                if sep > 0:
                    return View(el, style={"padding_bottom": sep})
                return el

            extent: Optional[float] = None
            if get_item_height is not None:
                try:
                    extent = float(get_item_height(item, i_idx, s_idx)) + sep
                except Exception:
                    extent = None
            elif item_height is not None:
                extent = float(item_height) + sep
            rows.append(_RowSpec(row_key, _make_item, extent, item=item, index=flat_index))
            flat_index += 1

    estimated = estimated_item_height if estimated_item_height is not None else (item_height or _DEFAULT_ROW_EXTENT)

    return _VirtualizedList(
        rows=rows,
        horizontal=False,
        estimated_row_extent=float(estimated) + sep,
        header=list_header,
        footer=list_footer,
        empty=list_empty,
        refresh_control=refresh_control,
        on_end_reached=on_end_reached,
        on_end_reached_threshold=on_end_reached_threshold,
        on_scroll=on_scroll,
        list_style=resolve_style(style) or None,
        controller_ref=ref,
        key=key,
    )


# ======================================================================
# StatusBar / KeyboardAvoidingView / RefreshControl / Picker
# ======================================================================


def StatusBar(
    *,
    bar_style: Optional[Literal["light", "dark", "default"]] = None,
    background_color: Optional[Color] = None,
    hidden: Optional[bool] = None,
    key: Optional[str] = None,
) -> Element:
    """Configure the device's status bar appearance.

    StatusBar is a side-effect element: it doesn't render any visible
    content but applies its props to the host platform's status bar.
    Mount one near the top of your tree.

    The ``bar_style`` parameter is named separately from the universal
    ``style`` kwarg (which is unused here) to avoid the conflict that
    ``style="light"`` would create with the visual-style dict used
    elsewhere.

    Args:
        bar_style: ``"light"`` (light icons over dark backgrounds),
            ``"dark"`` (dark icons over light backgrounds), or
            ``"default"`` (system default).
        background_color: Color of the status-bar background (Android
            only; iOS draws the bar transparent over your content).
        hidden: When ``True``, the status bar is hidden.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"StatusBar"``.
    """
    props: Dict[str, Any] = {}
    if bar_style is not None:
        props["bar_style"] = bar_style
    if background_color is not None:
        props["background_color"] = background_color
    if hidden is not None:
        props["hidden"] = hidden
    return Element("StatusBar", props, [], key=key)


def KeyboardAvoidingView(
    *children: Element,
    behavior: Literal["padding", "position"] = "padding",
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """Wrap content that should shift up when the keyboard is shown.

    Subscribes to the platform-reported keyboard height (via
    [`use_keyboard_height`][pythonnative.use_keyboard_height]
    internally) and applies it as bottom padding so the focused text
    input stays visible.

    Args:
        *children: Children rendered inside the avoiding container.
        behavior: ``"padding"`` (adds bottom padding) or ``"position"``
            (translates the container upward).
        style: Style dict (or list of dicts).
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type
        ``"KeyboardAvoidingView"``.
    """
    return _make_element(
        "KeyboardAvoidingView",
        *children,
        style=style,
        key=key,
        behavior=behavior,
    )


def RefreshControl(
    *,
    refreshing: bool = False,
    on_refresh: Optional[Callable[[], None]] = None,
    tint_color: Optional[Color] = None,
) -> Dict[str, Any]:
    """Pull-to-refresh spec for [`ScrollView`][pythonnative.ScrollView] / [`FlatList`][pythonnative.FlatList].

    Returns a plain dict that should be passed as the
    ``refresh_control=`` prop. Modeled as a dict (not an
    [`Element`][pythonnative.Element]) so the host scroll container can
    hold one without it appearing as a child node.

    Args:
        refreshing: Drive the spinner's visibility from a use_state
            value.
        on_refresh: Callback invoked when the user pulls down past the
            threshold. Set ``refreshing`` to ``True`` for the duration
            of the work, then back to ``False`` on completion.
        tint_color: Color of the spinner.

    Returns:
        Dict suitable for the ``refresh_control`` prop on a scroll
        container.

    Example:
        ```python
        import pythonnative as pn

        @pn.component
        def MyList():
            refreshing, set_refreshing = pn.use_state(False)

            def reload():
                set_refreshing(True)
                # ... fetch data ...
                set_refreshing(False)

            return pn.ScrollView(
                pn.Text("Pull me!"),
                refresh_control=pn.RefreshControl(
                    refreshing=refreshing, on_refresh=reload
                ),
            )
        ```
    """
    spec: Dict[str, Any] = {"refreshing": bool(refreshing)}
    if on_refresh is not None:
        spec["on_refresh"] = on_refresh
    if tint_color is not None:
        spec["tint_color"] = tint_color
    return spec


def Picker(
    *,
    value: Any = None,
    items: Optional[List[Dict[str, Any]]] = None,
    on_change: Optional[Callable[[Any], None]] = None,
    placeholder: str = "Select…",
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessibility_hint: Optional[str] = None,
    accessible: Optional[bool] = None,
    ref: Optional[Dict[str, Any]] = None,
    key: Optional[str] = None,
) -> Element:
    """A real native dropdown / select widget.

    Renders a tappable trigger labelled with the selected item; the
    iOS handler attaches a ``UIMenu`` (system dropdown) and the Android
    handler uses a native ``Spinner``. Selecting an item fires
    ``on_change(value)``.

    ``items`` is an ordered list of ``{"value": Any, "label": str}``
    entries (``label`` defaults to ``str(value)`` when omitted).

    Args:
        value: Currently selected value (matched against
            ``items[i]["value"]``).
        items: Selectable options.
        on_change: Callback invoked with the new value.
        placeholder: Label shown when no item matches ``value``.
        style: Style dict applied to the trigger.
        accessibility_label: Spoken description for screen readers.
        accessibility_hint: Spoken extra detail (iOS only).
        accessible: Override whether the element is exposed to AT.
        ref: Optional ``use_ref()`` dict.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"Picker"``.
    """
    return _make_element(
        "Picker",
        style=style,
        ref=ref,
        key=key,
        value=value,
        items=list(items) if items is not None else [],
        on_change=on_change,
        placeholder=placeholder,
        accessibility_label=accessibility_label,
        accessibility_hint=accessibility_hint,
        accessible=accessible,
        _defaults={"accessibility_role": "button"},
    )
