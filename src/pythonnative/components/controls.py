"""Form controls and side-effect elements.

``Switch``, ``Slider``, ``ProgressBar``, ``ActivityIndicator``,
``Checkbox``, ``SegmentedControl``, ``DatePicker``, ``Picker``, the
``RefreshControl``, and ``StatusBar``.
"""

from typing import Any, Callable, Dict, List, Literal, Optional

from ..element import Element
from ..hooks import Ref
from ..style import AccessibilityState, Color, StyleProp
from ._base import REFRESH_CONTROL_TYPE, _make_element


def Switch(
    *,
    value: bool = False,
    on_change: Optional[Callable[[bool], Any]] = None,
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


def Slider(
    *,
    value: float = 0.0,
    min_value: float = 0.0,
    max_value: float = 1.0,
    on_change: Optional[Callable[[float], Any]] = None,
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


def Checkbox(
    *,
    value: bool = False,
    on_change: Optional[Callable[[bool], Any]] = None,
    label: Optional[str] = None,
    disabled: bool = False,
    color: Optional[Color] = None,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessibility_hint: Optional[str] = None,
    accessible: Optional[bool] = None,
    accessibility_state: Optional[AccessibilityState] = None,
    accessibility_live_region: Optional[Literal["none", "polite", "assertive"]] = None,
    test_id: Optional[str] = None,
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
        accessibility_state=accessibility_state,
        accessibility_live_region=accessibility_live_region,
        test_id=test_id,
        _defaults={"accessibility_role": "checkbox"},
    )


def SegmentedControl(
    *,
    segments: Optional[List[str]] = None,
    selected_index: int = 0,
    on_change: Optional[Callable[[int], Any]] = None,
    enabled: bool = True,
    tint_color: Optional[Color] = None,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessible: Optional[bool] = None,
    accessibility_state: Optional[AccessibilityState] = None,
    accessibility_live_region: Optional[Literal["none", "polite", "assertive"]] = None,
    test_id: Optional[str] = None,
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
        accessibility_state=accessibility_state,
        accessibility_live_region=accessibility_live_region,
        test_id=test_id,
    )


def DatePicker(
    *,
    value: Optional[str] = None,
    mode: Literal["date", "time", "datetime"] = "date",
    on_change: Optional[Callable[[str], Any]] = None,
    minimum: Optional[str] = None,
    maximum: Optional[str] = None,
    enabled: bool = True,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessible: Optional[bool] = None,
    accessibility_state: Optional[AccessibilityState] = None,
    accessibility_live_region: Optional[Literal["none", "polite", "assertive"]] = None,
    test_id: Optional[str] = None,
    key: Optional[str] = None,
) -> Element:
    """A native date / time picker.

    Backed by ``UIDatePicker`` on iOS and a trigger button that opens
    the platform ``DatePickerDialog`` / ``TimePickerDialog`` on
    Android. ``value`` and the value reported to ``on_change`` are
    ISO-8601 strings (``"2026-05-31"`` for ``mode="date"``, ``"14:30"``
    for ``mode="time"``, ``"2026-05-31T14:30"`` for
    ``mode="datetime"``), so values stay JSON-serializable and
    platform-agnostic.

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
        accessibility_state=accessibility_state,
        accessibility_live_region=accessibility_live_region,
        test_id=test_id,
        _defaults={"accessibility_role": "button"},
    )


def Picker(
    *,
    value: Any = None,
    items: Optional[List[Dict[str, Any]]] = None,
    on_change: Optional[Callable[[Any], Any]] = None,
    placeholder: str = "Select…",
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
        accessibility_state=accessibility_state,
        accessibility_live_region=accessibility_live_region,
        test_id=test_id,
        _defaults={"accessibility_role": "button"},
    )


def RefreshControl(
    *,
    refreshing: bool = False,
    on_refresh: Optional[Callable[[], Any]] = None,
    tint_color: Optional[Color] = None,
) -> Element:
    """Pull-to-refresh control for [`ScrollView`][pythonnative.ScrollView] and the list components.

    Pass the result as the ``refresh_control=`` prop of a
    [`ScrollView`][pythonnative.ScrollView],
    [`FlatList`][pythonnative.FlatList], or
    [`SectionList`][pythonnative.SectionList]. It is a regular
    [`Element`][pythonnative.Element] (type ``"RefreshControl"``) built
    like every other piece of UI; the scroll container attaches it to
    its native scroll view rather than rendering it as a child, and
    rejects anything else with a ``TypeError``.

    Args:
        refreshing: Drive the spinner's visibility from a use_state
            value.
        on_refresh: Callback invoked when the user pulls down past the
            threshold. Set ``refreshing`` to ``True`` for the duration
            of the work, then back to ``False`` on completion.
        tint_color: Color of the spinner.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"RefreshControl"``.

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
    return _make_element(
        REFRESH_CONTROL_TYPE,
        refreshing=bool(refreshing),
        on_refresh=on_refresh,
        tint_color=tint_color,
    )


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
