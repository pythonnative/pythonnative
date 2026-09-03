"""Touch wrappers: ``Pressable`` and its ``TouchableOpacity`` alias."""

from typing import Any, Callable, Dict, List, Literal, Optional, Union

from ..component import component
from ..element import Element
from ..hooks import Ref, use_state
from ..style import AccessibilityState, StyleProp, resolve_style
from ._base import _make_element


@component
def _StatefulPressable(
    *children: Element,
    style_fn: Optional[Callable[[Dict[str, bool]], StyleProp]] = None,
    on_press_in: Optional[Callable[[], Any]] = None,
    on_press_out: Optional[Callable[[], Any]] = None,
    **props: Any,
) -> Element:
    """Hook-driven Pressable used when ``style`` is a callable.

    Tracks the pressed state with ``use_state`` and re-invokes the
    user's style function with ``{"pressed": bool}`` on every press
    transition, mirroring React Native's function-style ``style`` prop.
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

    style = resolve_style(style_fn({"pressed": pressed})) if style_fn is not None else None
    return _make_element(
        "Pressable",
        *children,
        style=style,
        on_press_in=_press_in,
        on_press_out=_press_out,
        _defaults={"accessibility_role": "button"},
        **props,
    )


def Pressable(
    *children: Element,
    on_press: Optional[Callable[[], Any]] = None,
    on_long_press: Optional[Callable[[], Any]] = None,
    on_press_in: Optional[Callable[[], Any]] = None,
    on_press_out: Optional[Callable[[], Any]] = None,
    pressed_opacity: float = 0.6,
    gestures: Optional[List[Any]] = None,
    hit_slop: Optional[Union[float, Dict[str, float]]] = None,
    on_layout: Optional[Callable[[Dict[str, float]], None]] = None,
    style: Union[StyleProp, Callable[[Dict[str, bool]], StyleProp]] = None,
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
        hit_slop: Extend the touch target beyond the view's bounds
            without changing layout: a uniform number of points, or a
            dict with any of ``top`` / ``left`` / ``bottom`` /
            ``right``. Essential for small touch targets (icons,
            chips) that should honor the 44-point guideline.
        on_layout: Callback invoked with
            ``{"x", "y", "width", "height"}`` after layout and on
            frame changes.
        style: Style dict applied to the wrapper, or a callable
            receiving the interaction state (``{"pressed": bool}``)
            and returning a style, re-evaluated on every press
            transition:

            ```python
            pn.Pressable(
                pn.Text("Tap"),
                style=lambda s: pn.style(
                    background_color="#0051A8" if s["pressed"] else "#007AFF",
                ),
            )
            ```
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
        An [`Element`][pythonnative.Element] of type ``"Pressable"``
        (wrapped in a stateful composite when ``style`` is callable).
    """
    if callable(style):
        return _StatefulPressable(
            *children,
            style_fn=style,
            ref=ref,
            key=key,
            on_press=on_press,
            on_long_press=on_long_press,
            on_press_in=on_press_in,
            on_press_out=on_press_out,
            pressed_opacity=pressed_opacity,
            gestures=gestures,
            hit_slop=hit_slop,
            on_layout=on_layout,
            accessibility_label=accessibility_label,
            accessibility_hint=accessibility_hint,
            accessibility_role=accessibility_role,
            accessible=accessible,
            accessibility_state=accessibility_state,
            accessibility_live_region=accessibility_live_region,
            test_id=test_id,
        )
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
        hit_slop=hit_slop,
        on_layout=on_layout,
        accessibility_label=accessibility_label,
        accessibility_hint=accessibility_hint,
        accessibility_role=accessibility_role,
        accessible=accessible,
        accessibility_state=accessibility_state,
        accessibility_live_region=accessibility_live_region,
        test_id=test_id,
        _defaults={"accessibility_role": "button"},
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
    accessibility_live_region: Optional[Literal["none", "polite", "assertive"]] = None,
    test_id: Optional[str] = None,
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
        accessibility_state=accessibility_state,
        accessibility_live_region=accessibility_live_region,
        test_id=test_id,
        key=key,
    )
