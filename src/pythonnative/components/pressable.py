"""Touch wrappers: ``Pressable`` and its ``TouchableOpacity`` alias."""

import dataclasses
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Union

from ..component import component
from ..element import Element
from ..hooks import Ref, use_state
from ..style import (
    AccessibilityAction,
    AccessibilityState,
    AccessibilityValue,
    Color,
    ImportantForAccessibility,
    StyleProp,
    StyleSheet,
)
from ._base import _accessibility_actions, _accessibility_value, _make_element
from .events import LayoutEvent


@dataclass(frozen=True, slots=True)
class PressState:
    """The interaction state handed to ``Pressable``'s callable ``style`` and child.

    Attributes:
        pressed: Whether a finger is currently down on the view.
    """

    pressed: bool


@dataclass(frozen=True, slots=True)
class Ripple:
    """Android's material ripple drawn while a ``Pressable`` is pressed.

    Passed as ``android_ripple=``; iOS and the browser preview ignore it
    (use ``pressed_opacity`` or a callable ``style`` for feedback
    there).

    Attributes:
        color: Ripple color.
        borderless: Draw the ripple beyond the view's bounds (a circle
            around the touch point) instead of clipping it.
        radius: Ripple radius in dp, or the view's size when ``None``.
        foreground: Draw the ripple over the children instead of behind
            them.
    """

    color: Color
    borderless: bool = False
    radius: Optional[float] = None
    foreground: bool = False


def _ripple_props(ripple: Optional[Ripple]) -> Optional[Dict[str, Any]]:
    if ripple is None:
        return None
    if not isinstance(ripple, Ripple):
        raise TypeError(f"Pressable(android_ripple=...) expects pn.Ripple(...), got {type(ripple).__name__}")
    return dataclasses.asdict(ripple)


@component
def _StatefulPressable(
    *children: Element,
    style_fn: Optional[Callable[[PressState], StyleProp]] = None,
    child_fn: Optional[Callable[[PressState], Element]] = None,
    on_press_in: Optional[Callable[[], Any]] = None,
    on_press_out: Optional[Callable[[], Any]] = None,
    **props: Any,
) -> Element:
    """Hook-driven Pressable used when ``style`` or the single child is callable.

    Tracks the pressed state with ``use_state`` and re-invokes the
    user's style function and child function with a
    [`PressState`][pythonnative.PressState] on every press transition,
    mirroring React Native's function-style ``style`` and children.
    Every other keyword (``on_press``, ``ref``, accessibility props,
    ...) is forwarded untouched to the native ``Pressable`` element.
    """
    pressed, set_pressed = use_state(False)

    def _press_in() -> None:
        set_pressed(True)
        if on_press_in is not None:
            on_press_in()

    def _press_out() -> None:
        set_pressed(False)
        if on_press_out is not None:
            on_press_out()

    state = PressState(pressed=pressed)
    style = style_fn(state) if style_fn is not None else None
    rendered = list(children)
    if child_fn is not None:
        rendered.append(child_fn(state))
    return _make_element(
        "Pressable",
        *rendered,
        style=style,
        on_press_in=_press_in,
        on_press_out=_press_out,
        _defaults={"accessibility_role": "button"},
        **props,
    )


def Pressable(
    *children: Union[Element, Callable[[PressState], Element]],
    on_press: Optional[Callable[[], Any]] = None,
    on_long_press: Optional[Callable[[], Any]] = None,
    on_press_in: Optional[Callable[[], Any]] = None,
    on_press_out: Optional[Callable[[], Any]] = None,
    disabled: bool = False,
    delay_long_press: float = 500,
    pressed_opacity: float = 0.6,
    android_ripple: Optional[Ripple] = None,
    gestures: Optional[List[Any]] = None,
    hit_slop: Optional[Union[float, Dict[str, float]]] = None,
    on_layout: Optional[Callable[[LayoutEvent], Any]] = None,
    style: Union[StyleProp, Callable[[PressState], StyleProp]] = None,
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
    """Wrap children with tap / long-press / gesture handlers.

    Useful for making non-button elements (text, images, custom views)
    respond to user taps. The wrapper view fades to ``pressed_opacity``
    on touch-down and back to full opacity on touch-up.

    Pressable gets ``accessibility_role="button"`` by default.

    ```python
    pn.Pressable(
        lambda state: pn.Text("Pressed" if state.pressed else "Press me"),
        on_press=save,
        disabled=not valid,
        delay_long_press=400,
        android_ripple=pn.Ripple(color="#33000000"),
        style=lambda state: pn.style(opacity=0.5 if state.pressed else 1),
    )
    ```

    Args:
        *children: Elements to make pressable, or a single callable
            receiving the [`PressState`][pythonnative.PressState] and
            returning the child to render.
        on_press: Callback invoked on a normal tap.
        on_long_press: Callback invoked on a sustained press.
        on_press_in: Callback invoked the moment the press starts.
        on_press_out: Callback invoked when the press lifts or cancels.
        disabled: When ``True``, no press callback fires and the view
            reports the disabled accessibility state (unless
            ``accessibility_state`` is given explicitly).
        delay_long_press: Milliseconds a press must be held before
            ``on_long_press`` fires.
        pressed_opacity: Opacity (0 to 1) applied while the user's
            finger is down. Set to ``1.0`` for no visual feedback.
        android_ripple: A [`Ripple`][pythonnative.Ripple] drawn on
            Android while pressed; ignored on iOS and in the browser.
        gestures: Optional list of gesture descriptors from
            `pythonnative.gestures` recognized natively on this view
            (pan / swipe / pinch / rotation / multi-tap).
        hit_slop: Extend the touch target beyond the view's bounds
            without changing layout: a uniform number of points, or a
            dict with any of ``top`` / ``left`` / ``bottom`` /
            ``right``. Essential for small touch targets (icons,
            chips) that should honor the 44-point guideline.
        on_layout: Callback invoked with a
            [`LayoutEvent`][pythonnative.LayoutEvent] after layout and
            on frame changes.
        style: Style dict applied to the wrapper, or a callable
            receiving the [`PressState`][pythonnative.PressState] and
            returning a style, re-evaluated on every press transition:

            ```python
            pn.Pressable(
                pn.Text("Tap"),
                style=lambda s: pn.style(
                    background_color="#0051A8" if s.pressed else "#007AFF",
                ),
            )
            ```
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
            tech: a string, or an
            [`AccessibilityValue`][pythonnative.AccessibilityValue]
            with ``min`` / ``max`` / ``now`` / ``text``.
        accessibility_actions: Custom actions a screen reader may
            invoke, each an
            [`AccessibilityAction`][pythonnative.AccessibilityAction].
        on_accessibility_action: Callback invoked with the action name
            when a screen reader triggers one of
            ``accessibility_actions``.
        accessibility_live_region: How AT announces dynamic changes to
            this view: ``"none"``, ``"polite"``, or ``"assertive"``.
        important_for_accessibility: Whether AT sees this view and its
            subtree: ``"auto"``, ``"yes"``, ``"no"``, or
            ``"no_hide_descendants"``.
        test_id: Stable identifier for UI tests; exposed as
            ``resource-id`` on Android and ``accessibilityIdentifier``
            on iOS.
        ref: Optional [`Ref`][pythonnative.Ref] from ``use_ref()``.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"Pressable"``
        (wrapped in a stateful composite when ``style`` or the child
        is callable).
    """
    if disabled and accessibility_state is None:
        accessibility_state = {"disabled": True}
    child_fn: Optional[Callable[[PressState], Element]] = None
    elements: List[Element] = []
    for child in children:
        if child is not None and not isinstance(child, Element) and callable(child):
            if child_fn is not None or len(children) != 1:
                raise TypeError("Pressable accepts a single callable child, receiving the PressState")
            child_fn = child
        else:
            elements.append(child)
    common: Dict[str, Any] = dict(
        on_press=on_press,
        on_long_press=on_long_press,
        disabled=disabled or None,
        delay_long_press=delay_long_press if delay_long_press != 500 else None,
        pressed_opacity=pressed_opacity,
        android_ripple=_ripple_props(android_ripple),
        gestures=gestures,
        hit_slop=hit_slop,
        on_layout=on_layout,
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
    if callable(style) or child_fn is not None:
        return _StatefulPressable(
            *elements,
            style_fn=style if callable(style) else (lambda _state: style),
            child_fn=child_fn,
            ref=ref,
            key=key,
            on_press_in=on_press_in,
            on_press_out=on_press_out,
            **common,
        )
    return _make_element(
        "Pressable",
        *elements,
        style=style,
        ref=ref,
        key=key,
        on_press_in=on_press_in,
        on_press_out=on_press_out,
        _defaults={"accessibility_role": "button"},
        **common,
    )


def TouchableOpacity(
    *children: Element,
    on_press: Optional[Callable[[], Any]] = None,
    on_long_press: Optional[Callable[[], Any]] = None,
    active_opacity: float = 0.2,
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
    key: Optional[str] = None,
) -> Element:
    """Wrap children so they fade to ``active_opacity`` while pressed.

    A thin ergonomic alias over [`Pressable`][pythonnative.Pressable]
    that mirrors React Native's ``TouchableOpacity``: the only visual
    feedback is an opacity dip on touch-down. When ``disabled`` is set,
    the wrapper is inert and renders at reduced opacity.

    Args:
        *children: Elements to make tappable.
        on_press: Callback invoked on a normal tap.
        on_long_press: Callback invoked on a sustained press.
        active_opacity: Opacity (0 to 1) applied while the finger is down.
        disabled: When ``True``, ignores presses and renders at reduced
            opacity.
        style: Style dict applied to the wrapper.
        accessibility_label: Spoken description for screen readers.
        accessibility_hint: Spoken extra detail (iOS reads it after the
            label; Android appends it to the content description).
        accessibility_role: Override the default ``"button"`` role.
        accessible: Override whether the element is exposed to AT.
        accessibility_state: Current widget state for assistive tech,
            e.g. ``{"disabled": True, "selected": False}``. Recognized
            keys: ``disabled``, ``selected``, ``checked``, ``busy``,
            ``expanded``.
        accessibility_value: The widget's current value for assistive
            tech (a string or an
            [`AccessibilityValue`][pythonnative.AccessibilityValue]).
        accessibility_actions: Custom screen-reader actions.
        on_accessibility_action: Callback invoked with the action name.
        accessibility_live_region: How AT announces dynamic changes to
            this view: ``"none"``, ``"polite"``, or ``"assertive"``.
        important_for_accessibility: Whether AT sees this view and its
            subtree.
        test_id: Stable identifier for UI tests; exposed as
            ``resource-id`` on Android and ``accessibilityIdentifier``
            on iOS.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"Pressable"``.
    """
    merged_style: StyleProp
    if disabled:
        base = StyleSheet.flatten(style)
        base.setdefault("opacity", 0.4)
        merged_style = base
    else:
        merged_style = style
    return Pressable(
        *children,
        on_press=on_press,
        on_long_press=on_long_press,
        disabled=disabled,
        pressed_opacity=active_opacity,
        style=merged_style,
        accessibility_label=accessibility_label,
        accessibility_hint=accessibility_hint,
        accessibility_role=accessibility_role,
        accessible=accessible,
        accessibility_state=accessibility_state,
        accessibility_value=accessibility_value,
        accessibility_actions=accessibility_actions,
        on_accessibility_action=on_accessibility_action,
        accessibility_live_region=accessibility_live_region,
        important_for_accessibility=important_for_accessibility,
        test_id=test_id,
        key=key,
    )
