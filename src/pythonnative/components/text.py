"""Text-centric leaf factories: ``Text``, ``Button``, and ``TextInput``."""

from typing import Any, Callable, Literal, Optional

from ..element import Element
from ..hooks import Ref
from ..style import (
    AccessibilityState,
    AutoCapitalize,
    Color,
    KeyboardType,
    ReturnKeyType,
    StyleProp,
)
from ._base import _flatten_text_spans, _make_element


def Text(
    *parts: Any,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessibility_hint: Optional[str] = None,
    accessibility_role: Optional[str] = None,
    accessible: Optional[bool] = None,
    accessibility_state: Optional[AccessibilityState] = None,
    accessibility_live_region: Optional[Literal["none", "polite", "assertive"]] = None,
    test_id: Optional[str] = None,
    ref: Optional[Ref] = None,
    key: Optional[str] = None,
) -> Element:
    """Display a string of text, optionally with styled nested spans.

    Style properties: ``font_size``, ``color``, ``bold``,
    ``font_weight``, ``font_family``, ``italic``, ``text_align``,
    ``background_color``, ``max_lines``, ``letter_spacing``,
    ``line_height``, ``text_decoration`` (``"underline"`` /
    ``"line_through"``), ``border_radius``, ``border_width``,
    ``border_color``, ``shadow_*``, ``opacity``, ``transform``, plus
    the common layout props.

    **Rich text**: pass multiple parts, mixing plain strings and
    nested ``Text`` elements, to render one paragraph with per-span
    styling (a single ``TextView`` / ``UILabel`` natively, so line
    wrapping flows across spans):

    ```python
    pn.Text(
        "Hello, ",
        pn.Text("world", style=pn.style(bold=True, color="#0A84FF")),
        "!",
        style=pn.style(font_size=18),
    )
    ```

    Nested spans inherit the outer element's text styling and may
    override ``color``, ``background_color``, ``font_size``,
    ``font_family``, ``font_weight``, ``bold``, ``italic``,
    ``text_decoration``, and ``letter_spacing``.

    Args:
        *parts: Text content: a single string, or any mix of strings
            and nested ``Text`` elements for rich text.
        style: Style dict (or list of dicts).
        accessibility_label: Spoken description for screen readers.
        accessibility_hint: Spoken extra detail (iOS only).
        accessibility_role: Semantic role for assistive tech.
        accessible: Override whether the element is exposed to AT.
        accessibility_state: Current widget state for assistive tech,
            e.g. ``{"disabled": True, "selected": False}``. Recognized
            keys: ``disabled``, ``selected``, ``checked``, ``busy``,
            ``expanded``.
        accessibility_live_region: How AT announces dynamic changes to
            this view: ``"none"``, ``"polite"``, or ``"assertive"``
            (Android only).
        test_id: Stable identifier for UI tests; exposed as
            ``resource-id`` on Android and ``accessibilityIdentifier``
            on iOS.
        ref: Optional [`Ref`][pythonnative.Ref] from ``use_ref()``.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"Text"``.
    """
    rich = any(isinstance(p, Element) for p in parts) or len(parts) > 1
    if rich:
        spans = _flatten_text_spans(parts, {})
        text = "".join(s["text"] for s in spans)
    else:
        spans = None
        text = str(parts[0]) if parts else ""
    return _make_element(
        "Text",
        style=style,
        ref=ref,
        key=key,
        text=text,
        spans=spans,
        accessibility_label=accessibility_label,
        accessibility_hint=accessibility_hint,
        accessibility_role=accessibility_role,
        accessible=accessible,
        accessibility_state=accessibility_state,
        accessibility_live_region=accessibility_live_region,
        test_id=test_id,
    )


def Button(
    title: str = "",
    *,
    on_press: Optional[Callable[[], Any]] = None,
    enabled: bool = True,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessibility_hint: Optional[str] = None,
    accessibility_role: Optional[str] = None,
    accessible: Optional[bool] = None,
    accessibility_state: Optional[AccessibilityState] = None,
    accessibility_live_region: Optional[Literal["none", "polite", "assertive"]] = None,
    test_id: Optional[str] = None,
    ref: Optional[Ref] = None,
    key: Optional[str] = None,
) -> Element:
    """Display a tappable button.

    Style properties: ``color``, ``background_color``, ``font_size``,
    ``border_radius``, ``border_width``, ``border_color``, ``shadow_*``,
    ``opacity``, ``transform``, plus the common layout props.

    Buttons get ``accessibility_role="button"`` by default.

    Args:
        title: Button label.
        on_press: Callback invoked when the user taps the button.
        enabled: When ``False``, the button is disabled and cannot be
            tapped.
        style: Style dict (or list of dicts).
        accessibility_label: Spoken description for screen readers.
        accessibility_hint: Spoken extra detail (iOS only).
        accessibility_role: Override the default ``"button"`` role.
        accessible: Override whether the element is exposed to AT.
        accessibility_state: Current widget state for assistive tech,
            e.g. ``{"disabled": True, "selected": False}``. Recognized
            keys: ``disabled``, ``selected``, ``checked``, ``busy``,
            ``expanded``.
        accessibility_live_region: How AT announces dynamic changes to
            this view: ``"none"``, ``"polite"``, or ``"assertive"``
            (Android only).
        test_id: Stable identifier for UI tests; exposed as
            ``resource-id`` on Android and ``accessibilityIdentifier``
            on iOS.
        ref: Optional [`Ref`][pythonnative.Ref] from ``use_ref()``.
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
        on_press=on_press,
        enabled=enabled,
        accessibility_label=accessibility_label,
        accessibility_hint=accessibility_hint,
        accessibility_role=accessibility_role,
        accessible=accessible,
        accessibility_state=accessibility_state,
        accessibility_live_region=accessibility_live_region,
        test_id=test_id,
        _defaults={"accessibility_role": "button"},
    )


def TextInput(
    *,
    value: str = "",
    placeholder: Optional[str] = None,
    on_change: Optional[Callable[[str], Any]] = None,
    on_submit: Optional[Callable[[str], Any]] = None,
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
    on_focus: Optional[Callable[[], Any]] = None,
    on_blur: Optional[Callable[[], Any]] = None,
    selection_color: Optional[Color] = None,
    text_content_type: Optional[str] = None,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessibility_hint: Optional[str] = None,
    accessible: Optional[bool] = None,
    accessibility_state: Optional[AccessibilityState] = None,
    accessibility_live_region: Optional[Literal["none", "polite", "assertive"]] = None,
    test_id: Optional[str] = None,
    ref: Optional[Ref] = None,
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
        accessibility_state: Current widget state for assistive tech,
            e.g. ``{"disabled": True, "selected": False}``. Recognized
            keys: ``disabled``, ``selected``, ``checked``, ``busy``,
            ``expanded``.
        accessibility_live_region: How AT announces dynamic changes to
            this view: ``"none"``, ``"polite"``, or ``"assertive"``
            (Android only).
        test_id: Stable identifier for UI tests; exposed as
            ``resource-id`` on Android and ``accessibilityIdentifier``
            on iOS.
        ref: Optional [`Ref`][pythonnative.Ref] from ``use_ref()``.
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
        accessibility_state=accessibility_state,
        accessibility_live_region=accessibility_live_region,
        test_id=test_id,
    )
