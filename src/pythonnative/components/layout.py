"""Container factories: ``View``, ``Column``, ``Row``, ``Spacer``, ``ScrollView``, and the inset-aware wrappers.

``SafeAreaView`` and ``KeyboardAvoidingView`` are thin factories over
hook-driven composites (``_SafeAreaContainer`` and
``_KeyboardAvoidingContainer``) that subscribe to the platform metrics
and re-render when the insets or keyboard height change.
"""

from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Union

from ..component import component
from ..element import Element
from ..hooks import Ref, use_keyboard_height, use_safe_area_insets, use_state
from ..style import AccessibilityState, StyleProp, resolve_style
from ._base import _make_element, _refresh_control_props


def View(
    *children: Element,
    style: StyleProp = None,
    gestures: Optional[List[Any]] = None,
    hit_slop: Optional[Union[float, Dict[str, float]]] = None,
    on_layout: Optional[Callable[[Dict[str, float]], None]] = None,
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
        hit_slop: Extend the touch target beyond the view's bounds
            without changing layout: a uniform number of points, or a
            dict with any of ``top`` / ``left`` / ``bottom`` /
            ``right``.
        on_layout: Callback invoked with
            ``{"x", "y", "width", "height"}`` after this view is laid
            out, and again whenever its frame changes.
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
        An [`Element`][pythonnative.Element] of type ``"View"``.
    """
    return _make_element(
        "View",
        *children,
        style=style,
        ref=ref,
        key=key,
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
        _defaults={"flex_direction": "column"},
    )


def Column(
    *children: Element,
    style: StyleProp = None,
    gestures: Optional[List[Any]] = None,
    hit_slop: Optional[Union[float, Dict[str, float]]] = None,
    on_layout: Optional[Callable[[Dict[str, float]], None]] = None,
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
    """Arrange children vertically.

    Convenience wrapper around [`View`][pythonnative.View] with
    ``flex_direction`` locked to ``"column"``. Use ``View`` directly if
    you need to switch between row and column at runtime.

    Accepts every [`View`][pythonnative.View] prop (gestures, hit slop,
    accessibility, ``test_id``); only ``flex_direction`` is fixed.

    Args:
        *children: Child elements stacked top to bottom.
        style: Style dict (or list of dicts).
        gestures: Gesture descriptors recognized natively on this view.
        hit_slop: Extra touch target beyond the bounds (see ``View``).
        on_layout: Callback invoked with
            ``{"x", "y", "width", "height"}`` after layout and on
            frame changes.
        accessibility_label: Spoken description for screen readers.
        accessibility_hint: Spoken extra detail (iOS only).
        accessibility_role: Semantic role for assistive tech.
        accessible: Override whether the element is exposed to AT.
        accessibility_state: Current widget state for assistive tech.
        accessibility_live_region: How AT announces dynamic changes
            (Android only).
        test_id: Stable identifier for UI tests.
        ref: Optional [`Ref`][pythonnative.Ref] for native-view access.
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
        _forced={"flex_direction": "column"},
    )


def Row(
    *children: Element,
    style: StyleProp = None,
    gestures: Optional[List[Any]] = None,
    hit_slop: Optional[Union[float, Dict[str, float]]] = None,
    on_layout: Optional[Callable[[Dict[str, float]], None]] = None,
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
    """Arrange children horizontally.

    Convenience wrapper around [`View`][pythonnative.View] with
    ``flex_direction`` locked to ``"row"``. Use ``View`` directly if you
    need to switch between row and column at runtime.

    Accepts every [`View`][pythonnative.View] prop (gestures, hit slop,
    accessibility, ``test_id``); only ``flex_direction`` is fixed.

    Args:
        *children: Child elements arranged left to right.
        style: Style dict (or list of dicts).
        gestures: Gesture descriptors recognized natively on this view.
        hit_slop: Extra touch target beyond the bounds (see ``View``).
        on_layout: Callback invoked with
            ``{"x", "y", "width", "height"}`` after layout and on
            frame changes.
        accessibility_label: Spoken description for screen readers.
        accessibility_hint: Spoken extra detail (iOS only).
        accessibility_role: Semantic role for assistive tech.
        accessible: Override whether the element is exposed to AT.
        accessibility_state: Current widget state for assistive tech.
        accessibility_live_region: How AT announces dynamic changes
            (Android only).
        test_id: Stable identifier for UI tests.
        ref: Optional [`Ref`][pythonnative.Ref] for native-view access.
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
        _forced={"flex_direction": "row"},
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


def ScrollView(
    *children: Element,
    refresh_control: Optional[Element] = None,
    scroll_axis: Optional[Literal["vertical", "horizontal"]] = None,
    on_scroll: Optional[Callable[[Dict[str, float]], None]] = None,
    shows_scroll_indicator: bool = True,
    paging_enabled: bool = False,
    bounces: bool = True,
    content_container_style: StyleProp = None,
    keyboard_dismiss_mode: Optional[Literal["none", "on_drag", "interactive"]] = None,
    style: StyleProp = None,
    ref: Optional[Ref] = None,
    key: Optional[str] = None,
) -> Element:
    """Wrap children in a scrollable container.

    ``ScrollView`` typically takes a single child (a ``Column`` or
    ``Row`` aggregating the scrollable content). It accepts ``*children``
    for ergonomic call sites; the underlying native scroll view stacks
    them on its content axis.

    Args:
        *children: Child elements to scroll.
        refresh_control: Optional [`RefreshControl`][pythonnative.RefreshControl]
            element attached to the scroll view for pull-to-refresh.
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
        ref: Optional [`Ref`][pythonnative.Ref] from ``use_ref()``.
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
        refresh_control=_refresh_control_props(refresh_control, owner="ScrollView"),
        scroll_axis=scroll_axis,
        on_scroll=on_scroll,
        shows_scroll_indicator=False if shows_scroll_indicator is False else None,
        paging_enabled=paging_enabled or None,
        bounces=False if bounces is False else None,
        content_container_style=resolve_style(content_container_style) or None,
        keyboard_dismiss_mode=keyboard_dismiss_mode,
    )


# ======================================================================
# SafeAreaView
# ======================================================================

_SAFE_AREA_EDGES: Tuple[str, ...] = ("top", "left", "bottom", "right")


def _numeric_edge_padding(style: Dict[str, Any], edge: str) -> float:
    """Return the numeric padding already declared for ``edge`` in ``style``.

    Only numeric values participate; percentage strings and dict
    shorthands are left alone (the inset simply overrides them for
    that edge). Resolution order matches the layout engine:
    ``padding_{edge}`` beats the axis shorthand, which beats
    ``padding``.
    """
    axis_key = "padding_vertical" if edge in ("top", "bottom") else "padding_horizontal"
    for key in (f"padding_{edge}", axis_key, "padding"):
        value = style.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return 0.0


@component
def _SafeAreaContainer(
    *children: Element,
    edges: Optional[Tuple[str, ...]] = None,
    style: Optional[Dict[str, Any]] = None,
) -> Element:
    """Hook-driven body of `SafeAreaView`.

    Reads the live insets via
    [`use_safe_area_insets`][pythonnative.use_safe_area_insets] (so the
    subtree re-renders when the platform publishes new values, e.g. on
    rotation) and adds each selected edge's inset on top of any padding
    the user declared for that edge.
    """
    insets = use_safe_area_insets()
    resolved: Dict[str, Any] = dict(style or {})
    selected = edges or _SAFE_AREA_EDGES
    for edge in _SAFE_AREA_EDGES:
        if edge not in selected:
            continue
        inset = float(getattr(insets, edge, 0.0) or 0.0)
        if inset > 0:
            resolved[f"padding_{edge}"] = _numeric_edge_padding(resolved, edge) + inset
    return Element("SafeAreaView", resolved, list(children))


def SafeAreaView(
    *children: Element,
    edges: Optional[Tuple[Literal["top", "left", "bottom", "right"], ...]] = None,
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """Container that respects safe-area insets (notch, status bar, home indicator).

    Applies the platform-reported insets as extra padding on the
    selected edges and re-renders automatically when the insets change
    (rotation, split view). User padding on an inset edge is added to
    the inset, matching ``react-native-safe-area-context``.

    Args:
        *children: Child elements that should avoid system UI overlays.
        edges: Which edges to pad; defaults to all four.
        style: Style dict (or list of dicts).
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] that renders a
        ``"SafeAreaView"`` container.
    """
    return _SafeAreaContainer(
        *children,
        edges=tuple(edges) if edges else None,
        style=resolve_style(style),
    ).with_key(key)


# ======================================================================
# KeyboardAvoidingView
# ======================================================================


@component
def _KeyboardAvoidingContainer(
    *children: Element,
    behavior: Literal["padding", "position", "height"] = "padding",
    keyboard_vertical_offset: float = 0.0,
    style: Optional[Dict[str, Any]] = None,
) -> Element:
    """Hook-driven body of `KeyboardAvoidingView`.

    Subscribes to the platform-reported keyboard height via
    [`use_keyboard_height`][pythonnative.use_keyboard_height] and
    applies the shift according to ``behavior``:

    - ``"padding"``: adds the shift as bottom padding, resizing the
      content area (the default, and the right choice for forms
      inside a full-height container).
    - ``"position"``: translates the whole container upward without
      resizing it (useful for pinned footers/toolbars).
    - ``"height"``: shrinks the container's own height by the shift.
      The resting height is captured via ``on_layout`` while the
      keyboard is hidden, so flex-sized containers work too.
    """
    keyboard = use_keyboard_height()
    base_height, set_base_height = use_state(0.0)
    mode = behavior or "padding"
    offset = float(keyboard_vertical_offset or 0.0)
    shift = max(0.0, keyboard - offset) if keyboard > 0 else 0.0
    resolved: Dict[str, Any] = dict(style or {})
    props: Dict[str, Any] = resolved
    if mode == "height":

        def _record_layout(frame: Dict[str, float]) -> None:
            if keyboard <= 0:
                measured = float(frame.get("height", 0.0))
                if measured > 0 and abs(measured - base_height) > 0.5:
                    set_base_height(measured)

        props = dict(resolved)
        props["on_layout"] = _record_layout
        if shift > 0 and base_height > 0:
            props["height"] = max(0.0, base_height - shift)
    elif shift > 0:
        if mode == "position":
            transform = list(resolved.get("transform") or [])
            transform.append({"translate_y": -shift})
            resolved["transform"] = transform
        else:
            resolved["padding_bottom"] = _numeric_edge_padding(resolved, "bottom") + shift
    return Element("KeyboardAvoidingView", props, list(children))


def KeyboardAvoidingView(
    *children: Element,
    behavior: Literal["padding", "position", "height"] = "padding",
    keyboard_vertical_offset: float = 0.0,
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """Wrap content that should shift up when the keyboard is shown.

    Subscribes to the platform-reported keyboard height (via
    [`use_keyboard_height`][pythonnative.use_keyboard_height]
    internally) and shifts its content so the focused text input stays
    visible. On iOS the height comes from
    ``UIKeyboardWillShowNotification``; on Android from the window's
    IME insets.

    Args:
        *children: Children rendered inside the avoiding container.
        behavior: ``"padding"`` (adds bottom padding, resizing the
            content), ``"position"`` (translates the container upward
            without resizing), or ``"height"`` (shrinks the
            container's height by the keyboard overlap, matching
            React Native's ``"height"`` behavior).
        keyboard_vertical_offset: Distance in layout units already
            covered by other UI (e.g. a nav bar); subtracted from the
            keyboard height before applying the shift.
        style: Style dict (or list of dicts).
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] that renders a
        ``"KeyboardAvoidingView"`` container.
    """
    return _KeyboardAvoidingContainer(
        *children,
        behavior=behavior,
        keyboard_vertical_offset=keyboard_vertical_offset,
        style=resolve_style(style),
    ).with_key(key)
