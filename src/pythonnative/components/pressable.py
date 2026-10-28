"""Touch wrappers: ``Pressable`` and its ``TouchableOpacity`` alias."""

import dataclasses
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Union, Unpack, cast

from ..component import component
from ..element import Element, Node
from ..hooks import Ref, use_state
from ..style import (
    Color,
    Style,
    StyleProp,
    resolve_style,
)
from ._base import _make_element
from .props import AccessibilityProps, ViewProps


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
    *children: Node,
    style_fn: Optional[Callable[[PressState], StyleProp]] = None,
    child_fn: Optional[Callable[[PressState], Node]] = None,
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
    *children: Union[Node, Callable[[PressState], Node]],
    on_press: Optional[Callable[[], Any]] = None,
    on_long_press: Optional[Callable[[], Any]] = None,
    on_press_in: Optional[Callable[[], Any]] = None,
    on_press_out: Optional[Callable[[], Any]] = None,
    disabled: bool = False,
    delay_long_press: float = 500,
    pressed_opacity: float = 0.6,
    android_ripple: Optional[Ripple] = None,
    style: Union[StyleProp, Callable[[PressState], StyleProp]] = None,
    ref: Optional[Ref] = None,
    key: Optional[str] = None,
    **props: Unpack[ViewProps],
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
        *children: Nodes to make pressable, or a single callable
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
        ref: Optional [`Ref`][pythonnative.Ref] from ``use_ref()``.
        key: Stable identity for keyed reconciliation.
        **props: Shared accessibility and test keywords; see
            [`ViewProps`][pythonnative.ViewProps] (layout, gestures, and accessibility).

    Returns:
        An [`Element`][pythonnative.Element] of type ``"Pressable"``
        (wrapped in a stateful composite when ``style`` or the child
        is callable).
    """
    if disabled and props.get("accessibility_state") is None:
        props["accessibility_state"] = {"disabled": True}
    child_fn: Optional[Callable[[PressState], Node]] = None
    elements: List[Node] = []
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
        **props,
    )
    if callable(style) or child_fn is not None:
        return _StatefulPressable(
            *elements,
            style_fn=style if callable(style) else (lambda _state: style),
            child_fn=child_fn,
            ref=ref,
            on_press_in=on_press_in,
            on_press_out=on_press_out,
            **common,
        ).with_key(key)
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
    *children: Node,
    on_press: Optional[Callable[[], Any]] = None,
    on_long_press: Optional[Callable[[], Any]] = None,
    active_opacity: float = 0.2,
    disabled: bool = False,
    style: StyleProp = None,
    key: Optional[str] = None,
    **props: Unpack[AccessibilityProps],
) -> Element:
    """Wrap children so they fade to ``active_opacity`` while pressed.

    A thin ergonomic alias over [`Pressable`][pythonnative.Pressable]
    that mirrors React Native's ``TouchableOpacity``: the only visual
    feedback is an opacity dip on touch-down. When ``disabled`` is set,
    the wrapper is inert and renders at reduced opacity.

    Args:
        *children: Nodes to make tappable.
        on_press: Callback invoked on a normal tap.
        on_long_press: Callback invoked on a sustained press.
        active_opacity: Opacity (0 to 1) applied while the finger is down.
        disabled: When ``True``, ignores presses and renders at reduced
            opacity.
        style: Style dict applied to the wrapper.
        key: Stable identity for keyed reconciliation.
        **props: Shared accessibility and test keywords; see
            [`AccessibilityProps`][pythonnative.AccessibilityProps].

    Returns:
        An [`Element`][pythonnative.Element] of type ``"Pressable"``.
    """
    merged_style: StyleProp
    if disabled:
        base = resolve_style(style)
        base.setdefault("opacity", 0.4)
        merged_style = cast(Style, base)
    else:
        merged_style = style
    return Pressable(
        *children,
        on_press=on_press,
        on_long_press=on_long_press,
        disabled=disabled,
        pressed_opacity=active_opacity,
        style=merged_style,
        key=key,
        **props,
    )
