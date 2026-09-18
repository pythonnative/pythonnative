"""Container factories: ``View``, ``Column``, ``Row``, ``Spacer``, ``ScrollView``, and the inset-aware wrappers.

``SafeAreaView`` and ``KeyboardAvoidingView`` are thin factories over
hook-driven composites (``_SafeAreaContainer`` and
``_KeyboardAvoidingContainer``) that subscribe to the platform metrics
and re-render when the insets or keyboard height change.
"""

from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Tuple, Union

from ..component import component
from ..element import Element
from ..hooks import Ref, use_keyboard_height, use_safe_area_insets, use_state
from ..style import (
    AccessibilityAction,
    AccessibilityState,
    AccessibilityValue,
    EdgeInsets,
    ImportantForAccessibility,
    Style,
    StyleProp,
    StyleSheet,
    resolve_style,
)
from ._base import _accessibility_actions, _accessibility_value, _layout_callback, _make_element, _refresh_control_props
from .events import LayoutEvent, ScrollEvent


def View(
    *children: Element,
    style: StyleProp = None,
    gestures: Optional[List[Any]] = None,
    hit_slop: Optional[Union[float, Dict[str, float]]] = None,
    on_layout: Optional[Callable[[LayoutEvent], Any]] = None,
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
        on_layout: Callback invoked with a
            [`LayoutEvent`][pythonnative.LayoutEvent] after this view
            is laid out, and again whenever its frame changes.
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
        ref: Optional [`Ref`][pythonnative.Ref] from ``use_ref()``;
            receives a [`ViewHandle`][pythonnative.ViewHandle].
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
        accessibility_value=_accessibility_value(accessibility_value),
        accessibility_actions=_accessibility_actions(accessibility_actions),
        on_accessibility_action=on_accessibility_action,
        accessibility_live_region=accessibility_live_region,
        important_for_accessibility=important_for_accessibility,
        test_id=test_id,
        _defaults={"flex_direction": "column"},
    )


def Column(
    *children: Element,
    style: StyleProp = None,
    gestures: Optional[List[Any]] = None,
    hit_slop: Optional[Union[float, Dict[str, float]]] = None,
    on_layout: Optional[Callable[[LayoutEvent], Any]] = None,
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
        on_layout: Callback invoked with a
            [`LayoutEvent`][pythonnative.LayoutEvent] after layout and
            on frame changes.
        accessibility_label: Spoken description for screen readers.
        accessibility_hint: Spoken extra detail (appended to the
            content description on Android).
        accessibility_role: Semantic role for assistive tech.
        accessible: Override whether the element is exposed to AT.
        accessibility_state: Current widget state for assistive tech.
        accessibility_value: Current value for assistive tech (see
            ``View``).
        accessibility_actions: Custom screen-reader actions (see
            ``View``).
        on_accessibility_action: Callback invoked with the action name.
        accessibility_live_region: How AT announces dynamic changes.
        important_for_accessibility: Whether AT sees this view and its
            subtree.
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
        accessibility_value=_accessibility_value(accessibility_value),
        accessibility_actions=_accessibility_actions(accessibility_actions),
        on_accessibility_action=on_accessibility_action,
        accessibility_live_region=accessibility_live_region,
        important_for_accessibility=important_for_accessibility,
        test_id=test_id,
        _forced={"flex_direction": "column"},
    )


def Row(
    *children: Element,
    style: StyleProp = None,
    gestures: Optional[List[Any]] = None,
    hit_slop: Optional[Union[float, Dict[str, float]]] = None,
    on_layout: Optional[Callable[[LayoutEvent], Any]] = None,
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
        on_layout: Callback invoked with a
            [`LayoutEvent`][pythonnative.LayoutEvent] after layout and
            on frame changes.
        accessibility_label: Spoken description for screen readers.
        accessibility_hint: Spoken extra detail (appended to the
            content description on Android).
        accessibility_role: Semantic role for assistive tech.
        accessible: Override whether the element is exposed to AT.
        accessibility_state: Current widget state for assistive tech.
        accessibility_value: Current value for assistive tech (see
            ``View``).
        accessibility_actions: Custom screen-reader actions (see
            ``View``).
        on_accessibility_action: Callback invoked with the action name.
        accessibility_live_region: How AT announces dynamic changes.
        important_for_accessibility: Whether AT sees this view and its
            subtree.
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
        accessibility_value=_accessibility_value(accessibility_value),
        accessibility_actions=_accessibility_actions(accessibility_actions),
        on_accessibility_action=on_accessibility_action,
        accessibility_live_region=accessibility_live_region,
        important_for_accessibility=important_for_accessibility,
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


def _content_inset_props(inset: Optional[EdgeInsets]) -> Optional[Dict[str, Any]]:
    """Normalize an ``EdgeInsets`` into the ``{top, left, bottom, right}`` wire dict."""
    if not inset:
        return None
    out: Dict[str, Any] = {}
    if "all" in inset:
        out.update(top=inset["all"], left=inset["all"], bottom=inset["all"], right=inset["all"])
    if "horizontal" in inset:
        out.update(left=inset["horizontal"], right=inset["horizontal"])
    if "vertical" in inset:
        out.update(top=inset["vertical"], bottom=inset["vertical"])
    for edge in ("top", "left", "bottom", "right"):
        if edge in inset:
            out[edge] = inset[edge]
    return out or None


def ScrollView(
    *children: Element,
    horizontal: bool = False,
    refresh_control: Optional[Element] = None,
    content_container_style: StyleProp = None,
    content_inset: Optional[EdgeInsets] = None,
    scroll_enabled: bool = True,
    scroll_event_throttle: float = 16,
    on_scroll: Optional[Callable[[ScrollEvent], Any]] = None,
    on_scroll_begin_drag: Optional[Callable[[ScrollEvent], Any]] = None,
    on_scroll_end_drag: Optional[Callable[[ScrollEvent], Any]] = None,
    on_momentum_scroll_end: Optional[Callable[[ScrollEvent], Any]] = None,
    shows_scroll_indicator: bool = True,
    paging_enabled: bool = False,
    bounces: bool = True,
    keyboard_dismiss_mode: Optional[Literal["none", "on_drag", "interactive"]] = None,
    keyboard_should_persist_taps: Literal["never", "always", "handled"] = "never",
    snap_to_interval: Optional[float] = None,
    snap_to_alignment: Literal["start", "center", "end"] = "start",
    deceleration_rate: Union[Literal["normal", "fast"], float] = "normal",
    style: StyleProp = None,
    ref: Optional[Ref] = None,
    key: Optional[str] = None,
) -> Element:
    """Wrap children in a scrollable container.

    ``ScrollView`` typically takes a single child (a ``Column`` or
    ``Row`` aggregating the scrollable content). It accepts ``*children``
    for ergonomic call sites; the underlying native scroll view stacks
    them on its content axis.

    ```python
    pn.ScrollView(
        *rows,
        content_container_style=pn.style(padding=16, gap=12),
        content_inset=pn.EdgeInsets(bottom=80),
        on_scroll=lambda e: print(e.y),
        keyboard_should_persist_taps="handled",
        keyboard_dismiss_mode="on_drag",
        ref=scroll_ref,
    )
    ```

    Args:
        *children: Child elements to scroll.
        horizontal: Scroll along the x axis instead of the y axis.
        refresh_control: Optional [`RefreshControl`][pythonnative.RefreshControl]
            element attached to the scroll view for pull-to-refresh.
        content_container_style: Style applied to the scrollable
            content (padding, gap, alignment), distinct from ``style``
            (the scroll view frame). The children are wrapped in one
            inner [`View`][pythonnative.View] carrying this style, so
            every layout key works on every renderer.
        content_inset: Extra scrollable space around the content, as an
            [`EdgeInsets`][pythonnative.EdgeInsets]; useful for
            keeping the last row clear of a floating footer.
        scroll_enabled: When ``False``, the user can't scroll (the
            content still lays out and imperative scrolling works).
        scroll_event_throttle: Minimum milliseconds between ``on_scroll``
            callbacks while scrolling. Native emits ``on_scroll`` only
            when the app wired it.
        on_scroll: Callback invoked with a
            [`ScrollEvent`][pythonnative.ScrollEvent] as the user
            scrolls.
        on_scroll_begin_drag: Callback invoked with a ``ScrollEvent``
            when the user's finger starts dragging.
        on_scroll_end_drag: Callback invoked with a ``ScrollEvent`` when
            the user's finger lifts.
        on_momentum_scroll_end: Callback invoked with a ``ScrollEvent``
            when the deceleration after a fling comes to rest.
        shows_scroll_indicator: When ``False``, hides the scroll bar.
        paging_enabled: When ``True``, the scroll view snaps to
            multiples of its own size (carousel behavior).
        bounces: When ``False``, disables the iOS rubber-band overscroll.
        keyboard_dismiss_mode: ``"none"`` (default), ``"on_drag"``, or
            ``"interactive"``. Controls whether scrolling dismisses
            the keyboard.
        keyboard_should_persist_taps: Whether a tap inside the scroll
            view dismisses the keyboard: ``"never"`` (the default; a
            tap dismisses it), ``"always"`` (never dismiss), or
            ``"handled"`` (dismiss only when nothing inside handled the
            tap).
        snap_to_interval: Snap the resting offset to multiples of this
            many points (a carousel of fixed-size cards).
        snap_to_alignment: Which edge of the viewport the snapped
            offset aligns to: ``"start"``, ``"center"``, or ``"end"``.
        deceleration_rate: How quickly a fling comes to rest:
            ``"normal"``, ``"fast"``, or a per-millisecond factor
            (``0.998`` is normal, ``0.99`` is fast).
        style: Style dict (or list of dicts).
        ref: Optional [`Ref`][pythonnative.Ref] from ``use_ref()``;
            receives a [`ScrollViewHandle`][pythonnative.ScrollViewHandle].
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"ScrollView"``.
    """
    content: Tuple[Element, ...] = children
    container_style = StyleSheet.flatten(content_container_style)
    if container_style:
        inner: Style = {"flex_direction": "row" if horizontal else "column"}
        if not horizontal:
            inner["width"] = "100%"
        inner.update(container_style)
        content = (View(*children, style=inner),)
    return _make_element(
        "ScrollView",
        *content,
        style=style,
        ref=ref,
        key=key,
        # A horizontal ScrollView arranges its content in a row, as in React
        # Native. Every renderer's layout reads the direction from the
        # style, which is what lets the content grow past the viewport.
        _forced={"flex_direction": "row"} if horizontal else None,
        horizontal=horizontal or None,
        refresh_control=_refresh_control_props(refresh_control, owner="ScrollView"),
        content_inset=_content_inset_props(content_inset),
        scroll_enabled=False if scroll_enabled is False else None,
        scroll_event_throttle=float(scroll_event_throttle) if scroll_event_throttle != 16 else None,
        on_scroll=on_scroll,
        on_scroll_begin_drag=on_scroll_begin_drag,
        on_scroll_end_drag=on_scroll_end_drag,
        on_momentum_scroll_end=on_momentum_scroll_end,
        shows_scroll_indicator=False if shows_scroll_indicator is False else None,
        paging_enabled=paging_enabled or None,
        bounces=False if bounces is False else None,
        keyboard_dismiss_mode=keyboard_dismiss_mode,
        keyboard_should_persist_taps=keyboard_should_persist_taps if keyboard_should_persist_taps != "never" else None,
        snap_to_interval=snap_to_interval,
        snap_to_alignment=snap_to_alignment if snap_to_alignment != "start" else None,
        deceleration_rate=deceleration_rate if deceleration_rate != "normal" else None,
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

        def _record_layout(frame: LayoutEvent) -> None:
            if keyboard <= 0:
                measured = float(frame.height)
                if measured > 0 and abs(measured - base_height) > 0.5:
                    set_base_height(measured)

        props = dict(resolved)
        props["on_layout"] = _layout_callback(_record_layout)
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
