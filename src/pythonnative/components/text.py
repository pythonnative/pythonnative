"""Text-centric leaf factories: ``Text``, ``Button``, and ``TextInput``."""

from typing import Any, Callable, Dict, Literal, Optional, Sequence, Tuple, TypedDict, Union

from ..element import Element
from ..hooks import Ref
from ..style import (
    AccessibilityAction,
    AccessibilityState,
    AccessibilityValue,
    AutoCapitalize,
    Color,
    ImportantForAccessibility,
    KeyboardType,
    ReturnKeyType,
    StyleProp,
)
from ._base import (
    _accessibility_actions,
    _accessibility_value,
    _flatten_text_spans,
    _make_element,
    _SpanPressDispatcher,
)
from .events import ContentSizeEvent, KeyPressEvent, SelectionEvent

EllipsizeMode = Literal["head", "middle", "tail", "clip"]
"""Where ``Text`` truncates when it exceeds ``max_lines``."""

KeyboardAppearance = Literal["default", "light", "dark"]
"""``TextInput.keyboard_appearance`` value (iOS keyboard theme)."""


class Selection(TypedDict):
    """The ``TextInput.selection`` wire record: UTF-16 offsets, ``start <= end``."""

    start: int
    end: int


def Text(
    *parts: Any,
    on_press: Optional[Callable[[], Any]] = None,
    ellipsize_mode: EllipsizeMode = "tail",
    selectable: bool = False,
    allow_font_scaling: bool = True,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessibility_hint: Optional[str] = None,
    accessibility_role: Optional[str] = None,
    accessible: Optional[bool] = None,
    accessibility_state: Optional[AccessibilityState] = None,
    accessibility_value: Optional[Union[str, AccessibilityValue]] = None,
    accessibility_actions: Optional[Sequence[AccessibilityAction]] = None,
    on_accessibility_action: Optional[Callable[[str], Any]] = None,
    accessibility_live_region: Optional[Literal["none", "polite", "assertive"]] = None,
    important_for_accessibility: Optional[ImportantForAccessibility] = None,
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
    wrapping flows across spans). A nested span may carry its own
    ``on_press``:

    ```python
    pn.Text(
        "Read the ",
        pn.Text("terms", on_press=open_terms, style=pn.style(color="#06F")),
        ".",
        max_lines=2,
        ellipsize_mode="tail",
        selectable=True,
    )
    ```

    Nested spans inherit the outer element's text styling and may
    override ``color``, ``background_color``, ``font_size``,
    ``font_family``, ``font_weight``, ``bold``, ``italic``,
    ``text_decoration``, and ``letter_spacing``. On the wire each
    pressable span carries ``pressable: True``; native reports
    ``on_span_press(index)`` and Python routes it to that span's
    callback.

    Args:
        *parts: Text content: a single string, or any mix of strings
            and nested ``Text`` elements for rich text.
        on_press: Callback invoked when the whole label is tapped (or,
            on a nested ``Text``, when that span is tapped).
        ellipsize_mode: Where to truncate when the text exceeds
            ``max_lines``: ``"head"``, ``"middle"``, ``"tail"``
            (default), or ``"clip"`` (no ellipsis). Android draws
            ``"head"`` and ``"middle"`` only on single-line text.
        selectable: Let the user select and copy the text.
        allow_font_scaling: Scale the font with the user's accessibility
            text size (iOS Dynamic Type, Android ``sp``). Set ``False``
            for text that must keep its exact size.
        style: Style dict (or list of dicts).
        accessibility_label: Spoken description for screen readers.
        accessibility_hint: Spoken extra detail. iOS reads it after the
            label; Android appends it to the content description.
        accessibility_role: Semantic role for assistive tech.
        accessible: Override whether the element is exposed to AT.
        accessibility_state: Current widget state for assistive tech,
            e.g. ``{"disabled": True, "selected": False}``. Recognized
            keys: ``disabled``, ``selected``, ``checked``, ``busy``,
            ``expanded``.
        accessibility_value: The widget's current value for assistive
            tech (a string or an
            [`AccessibilityValue`][pythonnative.AccessibilityValue]).
        accessibility_actions: Custom screen-reader actions, each an
            [`AccessibilityAction`][pythonnative.AccessibilityAction].
        on_accessibility_action: Callback invoked with the action name.
        accessibility_live_region: How AT announces dynamic changes to
            this view: ``"none"``, ``"polite"``, or ``"assertive"``.
        important_for_accessibility: Whether AT sees this view and its
            subtree.
        test_id: Stable identifier for UI tests; exposed as
            ``resource-id`` on Android and ``accessibilityIdentifier``
            on iOS.
        ref: Optional [`Ref`][pythonnative.Ref] from ``use_ref()``.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"Text"``.
    """
    rich = any(isinstance(p, Element) for p in parts) or len(parts) > 1
    on_span_press: Optional[_SpanPressDispatcher] = None
    if rich:
        # The label's own ``on_press`` is the whole-label event; spans
        # only become pressable through a nested ``Text(on_press=...)``.
        spans, callbacks = _flatten_text_spans(parts, {})
        text = "".join(s["text"] for s in spans)
        if any(callback is not None for callback in callbacks):
            on_span_press = _SpanPressDispatcher(callbacks)
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
        on_press=on_press,
        on_span_press=on_span_press,
        ellipsize_mode=ellipsize_mode if ellipsize_mode != "tail" else None,
        selectable=selectable or None,
        allow_font_scaling=False if allow_font_scaling is False else None,
        accessibility_label=accessibility_label,
        accessibility_hint=accessibility_hint,
        accessibility_role=accessibility_role,
        accessible=accessible,
        accessibility_state=accessibility_state,
        accessibility_value=_accessibility_value(accessibility_value),
        accessibility_actions=_accessibility_actions(accessibility_actions),
        on_accessibility_action=on_accessibility_action,
        accessibility_live_region=accessibility_live_region,
        important_for_accessibility=important_for_accessibility,
        test_id=test_id,
    )


def Button(
    title: str = "",
    *,
    on_press: Optional[Callable[[], Any]] = None,
    disabled: bool = False,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessibility_hint: Optional[str] = None,
    accessibility_role: Optional[str] = None,
    accessible: Optional[bool] = None,
    accessibility_state: Optional[AccessibilityState] = None,
    accessibility_value: Optional[Union[str, AccessibilityValue]] = None,
    accessibility_actions: Optional[Sequence[AccessibilityAction]] = None,
    on_accessibility_action: Optional[Callable[[str], Any]] = None,
    accessibility_live_region: Optional[Literal["none", "polite", "assertive"]] = None,
    important_for_accessibility: Optional[ImportantForAccessibility] = None,
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
        disabled: When ``True``, the button is disabled and cannot be
            tapped.
        style: Style dict (or list of dicts).
        accessibility_label: Spoken description for screen readers.
        accessibility_hint: Spoken extra detail. iOS reads it after the
            label; Android appends it to the content description.
        accessibility_role: Override the default ``"button"`` role.
        accessible: Override whether the element is exposed to AT.
        accessibility_state: Current widget state for assistive tech,
            e.g. ``{"disabled": True, "selected": False}``. Recognized
            keys: ``disabled``, ``selected``, ``checked``, ``busy``,
            ``expanded``.
        accessibility_value: The widget's current value for assistive
            tech (a string or an
            [`AccessibilityValue`][pythonnative.AccessibilityValue]).
        accessibility_actions: Custom screen-reader actions, each an
            [`AccessibilityAction`][pythonnative.AccessibilityAction].
        on_accessibility_action: Callback invoked with the action name.
        accessibility_live_region: How AT announces dynamic changes to
            this view: ``"none"``, ``"polite"``, or ``"assertive"``.
        important_for_accessibility: Whether AT sees this view and its
            subtree.
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
        disabled=disabled,
        accessibility_label=accessibility_label,
        accessibility_hint=accessibility_hint,
        accessibility_role=accessibility_role,
        accessible=accessible,
        accessibility_state=accessibility_state,
        accessibility_value=_accessibility_value(accessibility_value),
        accessibility_actions=_accessibility_actions(accessibility_actions),
        on_accessibility_action=on_accessibility_action,
        accessibility_live_region=accessibility_live_region,
        important_for_accessibility=important_for_accessibility,
        test_id=test_id,
        _defaults={"accessibility_role": "button"},
    )


def _selection_props(selection: Optional[Tuple[int, int]]) -> Optional[Dict[str, int]]:
    if selection is None:
        return None
    start, end = selection
    if start < 0 or end < start:
        raise ValueError(f"TextInput(selection=...) needs 0 <= start <= end, got {selection!r}")
    return {"start": int(start), "end": int(end)}


def TextInput(
    *,
    value: str = "",
    placeholder: Optional[str] = None,
    on_change: Optional[Callable[[str], Any]] = None,
    on_selection_change: Optional[Callable[[SelectionEvent], Any]] = None,
    on_submit: Optional[Callable[[str], Any]] = None,
    on_key_press: Optional[Callable[[KeyPressEvent], Any]] = None,
    on_content_size_change: Optional[Callable[[ContentSizeEvent], Any]] = None,
    selection: Optional[Tuple[int, int]] = None,
    secure: bool = False,
    multiline: bool = False,
    keyboard_type: Optional[KeyboardType] = None,
    keyboard_appearance: KeyboardAppearance = "default",
    auto_capitalize: Optional[AutoCapitalize] = None,
    auto_correct: Optional[bool] = None,
    auto_focus: bool = False,
    select_text_on_focus: bool = False,
    blur_on_submit: Optional[bool] = None,
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
    accessibility_value: Optional[Union[str, AccessibilityValue]] = None,
    accessibility_actions: Optional[Sequence[AccessibilityAction]] = None,
    on_accessibility_action: Optional[Callable[[str], Any]] = None,
    accessibility_live_region: Optional[Literal["none", "polite", "assertive"]] = None,
    important_for_accessibility: Optional[ImportantForAccessibility] = None,
    test_id: Optional[str] = None,
    ref: Optional[Ref] = None,
    key: Optional[str] = None,
) -> Element:
    """Display a text-entry field (single-line by default, or ``multiline``).

    Style properties: ``font_size``, ``color``, ``background_color``,
    ``border_*``, plus the common layout props.

    ```python
    pn.TextInput(
        value=text, on_change=set_text,
        selection=(start, end), on_selection_change=lambda e: ...,
        on_key_press=lambda e: ...,
        select_text_on_focus=True,
        keyboard_appearance="dark",
        ref=input_ref,
    )
    ```

    Args:
        value: Current text content (controlled-input pattern).
        placeholder: Hint shown when ``value`` is empty.
        on_change: Callback invoked with the new string each keystroke.
        on_selection_change: Callback invoked with a
            [`SelectionEvent`][pythonnative.SelectionEvent] (UTF-16
            offsets) when the caret or selection moves.
        on_submit: Callback invoked when the user submits (Return /
            Done / etc.). Receives the final text.
        on_key_press: Callback invoked with a
            [`KeyPressEvent`][pythonnative.KeyPressEvent] per key: the
            typed character, or ``"Backspace"`` / ``"Enter"``. iOS and
            Android report only what their input pipeline exposes
            (characters, backspace, and the return key); the browser
            reports every key.
        on_content_size_change: Callback invoked with a
            [`ContentSizeEvent`][pythonnative.ContentSizeEvent] when
            the text's measured size changes (auto-growing multiline
            fields).
        selection: Controlled selection as ``(start, end)`` UTF-16
            offsets; ``start == end`` places the caret.
        secure: When ``True``, characters are masked (use for passwords).
        multiline: When ``True``, allows multiple lines of input.
        keyboard_type: One of the [`KeyboardType`][pythonnative.KeyboardType]
            values, e.g. ``"email_address"``, ``"number_pad"``,
            ``"numbers_and_punctuation"``, ``"visible_password"``.
        keyboard_appearance: iOS keyboard theme: ``"default"``,
            ``"light"``, or ``"dark"``. Ignored elsewhere.
        auto_capitalize: One of ``"none"``, ``"sentences"``, ``"words"``,
            ``"characters"``.
        auto_correct: Enable/disable autocorrection.
        auto_focus: Request focus on mount.
        select_text_on_focus: Select the whole text when the field
            gains focus.
        blur_on_submit: Whether submitting blurs the field. ``None``
            (default) blurs single-line fields and keeps multiline
            fields focused, as React Native does.
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
        accessibility_hint: Spoken extra detail. iOS reads it after the
            label; Android appends it to the content description.
        accessible: Override whether the element is exposed to AT.
        accessibility_state: Current widget state for assistive tech,
            e.g. ``{"disabled": True, "selected": False}``. Recognized
            keys: ``disabled``, ``selected``, ``checked``, ``busy``,
            ``expanded``.
        accessibility_value: The widget's current value for assistive
            tech (a string or an
            [`AccessibilityValue`][pythonnative.AccessibilityValue]).
        accessibility_actions: Custom screen-reader actions, each an
            [`AccessibilityAction`][pythonnative.AccessibilityAction].
        on_accessibility_action: Callback invoked with the action name.
        accessibility_live_region: How AT announces dynamic changes to
            this view: ``"none"``, ``"polite"``, or ``"assertive"``.
        important_for_accessibility: Whether AT sees this view and its
            subtree.
        test_id: Stable identifier for UI tests; exposed as
            ``resource-id`` on Android and ``accessibilityIdentifier``
            on iOS.
        ref: Optional [`Ref`][pythonnative.Ref] from ``use_ref()``;
            receives a [`TextInputHandle`][pythonnative.TextInputHandle]
            with ``focus()``, ``blur()``, ``clear()``, and friends.
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
        on_selection_change=on_selection_change,
        on_submit=on_submit,
        on_key_press=on_key_press,
        on_content_size_change=on_content_size_change,
        selection=_selection_props(selection),
        secure=secure or None,
        multiline=multiline or None,
        keyboard_type=keyboard_type,
        keyboard_appearance=keyboard_appearance if keyboard_appearance != "default" else None,
        auto_capitalize=auto_capitalize,
        auto_correct=auto_correct,
        auto_focus=auto_focus or None,
        select_text_on_focus=select_text_on_focus or None,
        blur_on_submit=blur_on_submit,
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
        accessibility_value=_accessibility_value(accessibility_value),
        accessibility_actions=_accessibility_actions(accessibility_actions),
        on_accessibility_action=on_accessibility_action,
        accessibility_live_region=accessibility_live_region,
        important_for_accessibility=important_for_accessibility,
        test_id=test_id,
    )
