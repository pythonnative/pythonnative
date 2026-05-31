"""Built-in element factories and the typed prop schemas they share.

Each ``@dataclass(frozen=True)`` class in this module — ``TextProps``,
``ButtonProps``, etc. — is the canonical schema for one built-in
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

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Literal, Optional

from .element import Element
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


@dataclass(frozen=True)
class ViewProps(Props):
    """Props for [`View`][pythonnative.View], [`Column`][pythonnative.Column], and [`Row`][pythonnative.Row]."""

    accessibility_label: Optional[str] = None
    accessibility_hint: Optional[str] = None
    accessibility_role: Optional[str] = None
    accessible: Optional[bool] = None


@dataclass(frozen=True)
class ScrollViewProps(Props):
    """Props for [`ScrollView`][pythonnative.ScrollView]."""

    refresh_control: Optional[Dict[str, Any]] = None
    scroll_axis: Optional[Literal["vertical", "horizontal"]] = None
    on_scroll: Optional[Callable[[float, float], None]] = None
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
    pressed_opacity: float = 0.6
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
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """Display a toggle switch.

    Args:
        value: Current on/off state.
        on_change: Callback invoked with the new boolean state.
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
            on both axes — whichever axis the parent's
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
    )


# ======================================================================
# Container factories
# ======================================================================


def View(
    *children: Element,
    style: StyleProp = None,
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
    - ``justify_content``: main-axis distribution. Accepts
      ``"flex_start"`` (default), ``"center"``, ``"flex_end"``,
      ``"space_between"``, ``"space_around"``, ``"space_evenly"``.
    - ``align_items``: cross-axis alignment. Accepts ``"stretch"``
      (default), ``"flex_start"``, ``"center"``, ``"flex_end"``.
    - ``overflow``: ``"visible"`` (default) or ``"hidden"``.
    - ``spacing``, ``padding``, ``background_color``, ``border_radius``,
      ``border_width``, ``border_color``, ``shadow_color``,
      ``shadow_offset``, ``shadow_opacity``, ``shadow_radius``,
      ``elevation``, ``opacity``, ``transform``.

    Args:
        *children: Child elements rendered inside the container.
        style: Style dict (or list of dicts).
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
    on_scroll: Optional[Callable[[float, float], None]] = None,
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
        on_scroll: Callback invoked with ``(x, y)`` content offsets as
            the user scrolls.
        shows_scroll_indicator: When ``False``, hides the scroll bar.
        paging_enabled: When ``True``, the scroll view snaps to
            multiples of its own size (carousel behavior).
        bounces: When ``False``, disables the iOS rubber-band overscroll.
        content_container_style: Style applied to the inner content
            wrapper (padding, alignment, spacing of the scrollable
            content), distinct from ``style`` (the scroll view frame).
        keyboard_dismiss_mode: ``"none"`` (default), ``"on_drag"``, or
            ``"interactive"`` — controls whether scrolling dismisses
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
        presentation_style: iOS presentation style —
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
    pressed_opacity: float = 0.6,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessibility_hint: Optional[str] = None,
    accessibility_role: Optional[str] = None,
    accessible: Optional[bool] = None,
    key: Optional[str] = None,
) -> Element:
    """Wrap children with tap and long-press handlers.

    Useful for making non-button elements (text, images, custom views)
    respond to user taps. The wrapper view fades to ``pressed_opacity``
    on touch-down and back to full opacity on touch-up.

    Pressable gets ``accessibility_role="button"`` by default.

    Args:
        *children: Elements to make pressable.
        on_press: Callback invoked on a normal tap.
        on_long_press: Callback invoked on a sustained press.
        pressed_opacity: Opacity (0–1) applied while the user's finger
            is down. Set to ``1.0`` for no visual feedback.
        style: Style dict applied to the wrapper.
        accessibility_label: Spoken description for screen readers.
        accessibility_hint: Spoken extra detail (iOS only).
        accessibility_role: Override the default ``"button"`` role.
        accessible: Override whether the element is exposed to AT.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"Pressable"``.
    """
    return _make_element(
        "Pressable",
        *children,
        style=style,
        key=key,
        on_press=on_press,
        on_long_press=on_long_press,
        pressed_opacity=pressed_opacity,
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
# Lists
# ======================================================================


def FlatList(
    *,
    data: Optional[List[Any]] = None,
    render_item: Optional[Callable[[Any, int], Element]] = None,
    key_extractor: Optional[Callable[[Any, int], str]] = None,
    item_height: Optional[float] = None,
    separator_height: float = 0,
    refresh_control: Optional[Dict[str, Any]] = None,
    on_item_press: Optional[Callable[[int], None]] = None,
    horizontal: bool = False,
    num_columns: int = 1,
    list_header: Optional[Element] = None,
    list_footer: Optional[Element] = None,
    list_empty: Optional[Element] = None,
    on_end_reached: Optional[Callable[[], None]] = None,
    on_end_reached_threshold: float = 0.5,
    content_container_style: StyleProp = None,
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """Virtualized scrollable list that renders items from ``data`` lazily.

    Backed by ``UITableView`` on iOS and ``RecyclerView`` on Android via
    the ``VirtualList`` element. Each visible row is mounted on demand
    by a nested
    [`Reconciler`][pythonnative.reconciler.Reconciler] when
    ``item_height`` is specified.

    When ``item_height`` is omitted the implementation falls back to an
    eager (non-virtualized) ``ScrollView`` of every row — keep the data
    set small in that mode (the fallback is convenient for short lists
    where virtualization overhead would dominate).

    Args:
        data: Iterable of arbitrary item values.
        render_item: Function called per item, returning an
            [`Element`][pythonnative.Element]. Defaults to wrapping
            each item in a [`Text`][pythonnative.Text].
        key_extractor: Function returning a stable key per item.
        item_height: Fixed row height in layout units. Required to
            enable native virtualization. When omitted, the list
            falls back to an eager scroll of every row (not
            recommended for long lists).
        separator_height: Vertical gap between items, in layout units.
            Combined with ``item_height`` for the virtualized case.
        refresh_control: Optional ``{"refreshing": bool, "on_refresh":
            callable}`` for pull-to-refresh; see
            [`RefreshControl`][pythonnative.RefreshControl].
        on_item_press: Callback invoked with the row index when the
            user taps a row (virtualized backend only).
        horizontal: Lay rows out left-to-right instead of top-to-bottom
            (forces the eager backend).
        num_columns: Render items in a grid of this many columns
            (forces the eager backend). ``1`` (default) is a plain list.
        list_header: Optional element rendered once above all rows.
        list_footer: Optional element rendered once below all rows.
        list_empty: Optional element rendered when ``data`` is empty.
        on_end_reached: Callback invoked when the user scrolls within
            ``on_end_reached_threshold`` of the end (virtualized
            backend).
        on_end_reached_threshold: Fraction of the viewport from the end
            at which ``on_end_reached`` fires.
        content_container_style: Style applied to the inner content
            wrapper (forces the eager backend).
        style: Style dict (or list of dicts).
        key: Stable identity for keyed reconciliation of the list
            itself.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"VirtualList"``
        (virtualized) or ``"ScrollView"`` (eager fallback).

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

    has_ornaments = (
        num_columns > 1
        or horizontal
        or list_header is not None
        or list_footer is not None
        or content_container_style is not None
        or (not items_list and list_empty is not None)
    )

    if item_height is None or has_ornaments:
        # Eager fallback for short lists, grids, and lists with
        # header/footer/empty ornaments (which the fixed-height
        # virtualizer can't express).
        rendered: List[Element] = []
        for i, item in enumerate(items_list):
            el = render_item(item, i) if render_item else Text(str(item))
            if key_extractor is not None:
                el = Element(el.type, el.props, el.children, key=key_extractor(item, i))
            rendered.append(el)

        sep = separator_height or None

        if not has_ornaments:
            # Backward-compatible shape: ScrollView wrapping a single
            # Column of the rendered rows.
            inner = Column(*rendered, style={"spacing": sep} if sep else None)
            return ScrollView(inner, refresh_control=refresh_control, style=style, key=key)

        if not rendered and list_empty is not None:
            content: List[Element] = [list_empty]
        elif num_columns > 1:
            rows: List[Element] = []
            for start in range(0, len(rendered), num_columns):
                chunk = rendered[start : start + num_columns]
                rows.append(
                    Row(
                        *chunk,
                        style={"spacing": separator_height, "flex": 1} if separator_height else {"flex": 1},
                        key=f"row-{start}",
                    )
                )
            content = rows
        elif horizontal:
            content = [Row(*rendered, style={"spacing": sep} if sep else None)]
        else:
            content = [Column(*rendered, style={"spacing": sep} if sep else None)]

        body: List[Element] = []
        if list_header is not None:
            body.append(list_header)
        body.extend(content)
        if list_footer is not None:
            body.append(list_footer)

        axis: Literal["vertical", "horizontal"] = "horizontal" if horizontal else "vertical"
        wrapper = Row if horizontal else Column
        inner = wrapper(*body, style=content_container_style)
        return ScrollView(
            inner,
            refresh_control=refresh_control,
            scroll_axis=axis,
            style=style,
            key=key,
        )

    # Virtualized path: render_item is invoked lazily by the native
    # cell mount callback when each row scrolls into view.
    row_h = float(item_height) + float(separator_height)

    def _mount_row(
        index: int,
        content_view: Any,
        cell_width: float = 0.0,
        cell_height: float = 0.0,
    ) -> None:
        # Imported lazily so the components module stays importable in
        # off-device test environments.
        from .native_views import get_registry
        from .reconciler import Reconciler

        try:
            item = items_list[index]
        except IndexError:
            return

        element = render_item(item, index) if render_item else Text(str(item))
        backend = get_registry()
        reconciler = Reconciler(backend)
        native_root = reconciler.mount(element)

        layout_w = float(cell_width) if cell_width and cell_width > 0 else 0.0
        layout_h = float(cell_height) if cell_height and cell_height > 0 else float(item_height)
        if layout_w <= 0:
            try:
                bounds = content_view.bounds
                layout_w = float(bounds.size.width)
            except Exception:
                layout_w = 0.0
        if layout_w > 0 and layout_h > 0:
            backend.set_frame(native_root, "View", 0.0, 0.0, layout_w, layout_h)
            reconciler.set_viewport_size(layout_w, layout_h)

        backend.add_child(content_view, native_root, "View")

    return _make_element(
        "VirtualList",
        style=style,
        key=key,
        count=len(items_list),
        row_height=row_h,
        mount_row=_mount_row,
        on_row_press=on_item_press,
        on_end_reached=on_end_reached,
        on_end_reached_threshold=on_end_reached_threshold,
        refresh_control=refresh_control,
    )


def SectionList(
    *,
    sections: Optional[List[Dict[str, Any]]] = None,
    render_item: Optional[Callable[[Any, int, int], Element]] = None,
    render_section_header: Optional[Callable[[Dict[str, Any], int], Element]] = None,
    item_height: Optional[float] = None,
    section_header_height: float = 32.0,
    separator_height: float = 0,
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """Virtualized list that supports section headers.

    Internally flattens ``sections`` into a single virtualized list
    where each row is either a section header or a section item. The
    row mounter dispatches to ``render_section_header`` or
    ``render_item`` depending on the row's type.

    Args:
        sections: Each section is ``{"title": ..., "data": [...]}``.
        render_item: ``render_item(item, item_index, section_index) ->
            Element``.
        render_section_header: ``render_section_header(section,
            section_index) -> Element``.
        item_height: Fixed row height for items, in layout units.
        section_header_height: Fixed header height in layout units.
        separator_height: Gap appended below each item, in layout units.
        style: Style dict (or list of dicts).
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"VirtualList"``
        (virtualized). When ``item_height`` is omitted the layout falls
        back to an eager column.
    """
    sections_list = list(sections or [])

    flat: List[Dict[str, Any]] = []
    for s_idx, section in enumerate(sections_list):
        flat.append({"_kind": "header", "section": section, "section_index": s_idx})
        for i_idx, item in enumerate(section.get("data", []) or []):
            flat.append({"_kind": "item", "item": item, "item_index": i_idx, "section_index": s_idx})

    if item_height is None:
        # Eager fallback.
        children: List[Element] = []
        for entry in flat:
            if entry["_kind"] == "header":
                if render_section_header is not None:
                    children.append(render_section_header(entry["section"], entry["section_index"]))
                else:
                    children.append(Text(str(entry["section"].get("title", ""))))
            else:
                if render_item is not None:
                    children.append(render_item(entry["item"], entry["item_index"], entry["section_index"]))
                else:
                    children.append(Text(str(entry["item"])))
        inner = Column(*children, style={"spacing": separator_height} if separator_height else None)
        return ScrollView(inner, style=style, key=key)

    # Virtualized: mixed row heights aren't supported in v1, so we
    # use the larger of section_header_height and item_height + sep.
    row_h = max(float(section_header_height), float(item_height) + float(separator_height))

    def _mount_row(index: int, content_view: Any) -> None:
        from .native_views import get_registry
        from .reconciler import Reconciler

        try:
            entry = flat[index]
        except IndexError:
            return
        if entry["_kind"] == "header":
            if render_section_header is not None:
                element = render_section_header(entry["section"], entry["section_index"])
            else:
                element = Text(str(entry["section"].get("title", "")))
        else:
            if render_item is not None:
                element = render_item(entry["item"], entry["item_index"], entry["section_index"])
            else:
                element = Text(str(entry["item"]))

        backend = get_registry()
        reconciler = Reconciler(backend)
        native_root = reconciler.mount(element)
        try:
            backend.add_child(content_view, native_root, "View")
        except Exception:
            pass

    return _make_element(
        "VirtualList",
        style=style,
        key=key,
        count=len(flat),
        row_height=row_h,
        mount_row=_mount_row,
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
            only — iOS draws the bar transparent over your content).
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
