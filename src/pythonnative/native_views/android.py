"""Android native-view handlers (Chaquopy / Java bridge).

Each handler class maps a PythonNative element type to an Android
widget, implementing view creation, property updates, child management,
and frame application. Handlers are registered with the
[`NativeViewRegistry`][pythonnative.native_views.NativeViewRegistry] by
[`register_handlers`][pythonnative.native_views.android.register_handlers].

**Batched protocol**: the registry applies the reconciler's mutation
ops; handlers receive callable-free props. User callbacks never reach
this module; every interaction (clicks, text changes, scrolls,
gestures) is forwarded through
[`dispatch_event`][pythonnative.events.dispatch_event] keyed by the
view's reconciler-assigned tag.

**Layout** is owned by the pure-Python flex engine in
`pythonnative.layout`: container handlers create plain `FrameLayout`s,
the engine computes per-child frames, and
[`set_frame`][pythonnative.native_views.android.AndroidViewHandler.set_frame]
applies those frames via per-child `MarginLayoutParams`.

**Gestures** feed raw ``MotionEvent`` streams into the shared
pure-Python [`GestureArbiter`][pythonnative.gestures.GestureArbiter],
so gesture semantics match the desktop preview exactly. Serialized
specs (including ``simultaneous`` / ``wait_for`` composition metadata
and ``fling`` configs) pass through untouched; this module only
schedules main-looper polls at the arbiter's ``next_deadline()`` so
long-press activation and multi-tap windows fire even when no
further touch events arrive.

**Animations**: ``timing`` animations on transform/opacity/color props
are driven natively by ``ObjectAnimator`` (Choreographer-paced, no
Python per-frame work); springs and decay fall back to the Python
ticker, whose per-frame values arrive through
``set_animated_property`` (floats for transforms and opacity,
interpolated "#AARRGGBB" strings for background and text colors that
re-bake through the border-drawable machinery instead of clobbering
it).

**Interaction props**: ``pointer_events`` maps onto the template's
``PNFrameLayout`` touch interception when available (with a
Python-side fallback for older projects), ``hit_slop`` expands touch
targets via a parent ``TouchDelegate`` sized after layout,
``z_index`` maps to ``View.setZ``, and per-corner radii extend the
``GradientDrawable`` border path.

This module is only imported on Android at runtime. Desktop tests
inject a mock registry via
[`set_registry`][pythonnative.native_views.set_registry] and never
trigger this import path.
"""

import math
import time
from typing import Any, Callable, Dict, Optional, Tuple

from java import dynamic_proxy, jclass

from .. import diagnostics
from ..events import dispatch_event, event_names
from ..gestures import make_arbiter
from ..utils import get_android_context
from .base import ViewHandler, _safe_max, parse_color_int

_SIDE_BORDER_WIDTH_KEYS = (
    "border_left_width",
    "border_top_width",
    "border_right_width",
    "border_bottom_width",
)
_SIDE_BORDER_COLOR_KEYS = (
    "border_left_color",
    "border_top_color",
    "border_right_color",
    "border_bottom_color",
)
# Order matches GradientDrawable.setCornerRadii: top-left, top-right,
# bottom-right, bottom-left (each corner takes an x and a y radius).
_CORNER_RADIUS_KEYS = (
    "border_top_left_radius",
    "border_top_right_radius",
    "border_bottom_right_radius",
    "border_bottom_left_radius",
)
_DRAWABLE_STYLE_KEYS = (
    "background_color",
    "border_radius",
    "border_width",
    "border_color",
    *_CORNER_RADIUS_KEYS,
    *_SIDE_BORDER_WIDTH_KEYS,
    *_SIDE_BORDER_COLOR_KEYS,
)


# ======================================================================
# Shared helpers
# ======================================================================


def _ctx() -> Any:
    return get_android_context()


def _pn_runtime_class(class_name: str) -> Any:
    """Resolve a PythonNative Android helper class for the running app.

    The Android template's helper classes (e.g.
    ``PNAccessibilityDelegate``, ``PNBorderDrawable``) live in the
    app's own package, which the ``pn`` CLI relocates to the configured
    ``application_id`` at build time. Deriving the package from the
    runtime ``Context`` (rather than hardcoding the template package)
    keeps these lookups correct for any app id.

    Args:
        class_name: The class name within the app package, e.g.
            ``"PNBorderDrawable"``.

    Returns:
        The resolved Java class.
    """
    package = _ctx().getPackageName()
    return jclass(f"{package}.{class_name}")


# Cached lookup for the template's PNFrameLayout container class.
# ``None`` means "not resolved yet"; ``False`` means "this generated
# project predates the class", so creation falls back to FrameLayout
# without retrying the (exception-throwing) lookup per view.
_pn_container_cls: Any = None


def _new_container() -> Any:
    """Create a container view, preferring the template's ``PNFrameLayout``.

    ``PNFrameLayout`` adds native ``pointer_events`` interception
    (``onInterceptTouchEvent`` / ``dispatchTouchEvent``), which
    Chaquopy can't express from Python. Older generated projects
    without the class get a plain ``FrameLayout``; the
    ``pointer_events`` prop then degrades to the Python-side
    approximation in
    [`_apply_pointer_events`][pythonnative.native_views.android._apply_pointer_events].
    """
    global _pn_container_cls
    if _pn_container_cls is None:
        try:
            _pn_container_cls = _pn_runtime_class("PNFrameLayout")
        except Exception:
            _pn_container_cls = False
    if _pn_container_cls is not False:
        try:
            return _pn_container_cls(_ctx())
        except Exception:
            diagnostics.swallowed("android._new_container")
    return jclass("android.widget.FrameLayout")(_ctx())


def _signed_color(value: int) -> int:
    """Clamp a Python color int into Java's signed 32-bit range."""
    value &= 0xFFFFFFFF
    if value >= 0x80000000:
        value -= 0x100000000
    return value


def _density() -> float:
    return float(_ctx().getResources().getDisplayMetrics().density)


def _dp(value: float) -> int:
    return int(round(value * _density()))


def _java_id(jobj: Any) -> int:
    """Return ``System.identityHashCode(jobj)`` as a stable lookup key.

    Chaquopy's ``JavaObject.__setattr__`` rejects unknown Python
    attributes, so per-view bookkeeping can't live on the wrapper.
    The JVM identity hash is stable for the lifetime of the Java
    object and identical across every Python wrapper that proxies it.
    """
    System = jclass("java.lang.System")
    return int(System.identityHashCode(jobj))


# Tag table: java identity -> reconciler tag, and tag -> per-view state.
_view_tags: Dict[int, int] = {}
_view_state: Dict[int, Dict[str, Any]] = {}


def _remember(view: Any, tag: int) -> None:
    _view_tags[_java_id(view)] = tag
    _view_state[tag] = {"props": {}}


def _tag_of(view: Any) -> Optional[int]:
    return _view_tags.get(_java_id(view))


def _state_of(view: Any) -> Dict[str, Any]:
    tag = _tag_of(view)
    if tag is None:
        return {}
    return _view_state.setdefault(tag, {"props": {}})


def _forget(view: Any) -> None:
    tag = _view_tags.pop(_java_id(view), None)
    if tag is not None:
        _view_state.pop(tag, None)


def _fire(view: Any, name: str, *args: Any) -> bool:
    """Dispatch event ``name`` for ``view`` through the tag registry."""
    tag = _tag_of(view)
    if tag is None:
        return False
    return dispatch_event(tag, name, *args)


def _has_event(view: Any, name: str) -> bool:
    """Whether the element wired a callback named ``name`` this render."""
    merged = _state_of(view).get("props") or {}
    return name in event_names(merged)


def _apply_side_border(view: Any, props: Dict[str, Any]) -> bool:
    """Apply per-side borders via the template's ``PNBorderDrawable``.

    Activated when any ``border_<side>_width`` key is present. In that
    mode the drawable owns all four edges: each side's width falls
    back to the uniform ``border_width`` (else 0) and its color to
    ``border_color`` (else black), and the background fill and corner
    radius are baked into the same drawable.

    Returns:
        ``True`` if the drawable was applied; ``False`` when no
        per-side key is present or the helper class is unavailable
        (older generated projects), in which case the caller falls
        back to the uniform ``GradientDrawable`` path.
    """
    if not any(props.get(k) is not None for k in _SIDE_BORDER_WIDTH_KEYS):
        return False
    try:
        PNBorderDrawable = _pn_runtime_class("PNBorderDrawable")
    except Exception:
        return False
    try:
        base_width = float(props.get("border_width") or 0.0)
        base_color = props.get("border_color") or "#000000"
        widths = [
            float(_dp(float(props[k]))) if props.get(k) is not None else float(_dp(base_width))
            for k in _SIDE_BORDER_WIDTH_KEYS
        ]
        colors = [
            _signed_color(parse_color_int(props[k] if props.get(k) is not None else base_color))
            for k in _SIDE_BORDER_COLOR_KEYS
        ]
        has_bg = props.get("background_color") is not None
        bg = _signed_color(parse_color_int(props["background_color"])) if has_bg else 0
        radius = float(_dp(float(props.get("border_radius") or 0.0)))
        drawable = PNBorderDrawable(has_bg, bg, radius, widths, colors)
        view.setBackground(drawable)
        try:
            view.invalidate()
        except Exception:
            diagnostics.swallowed("android._apply_side_border")
        return True
    except Exception:
        return False


def _apply_border(view: Any, props: Dict[str, Any]) -> None:
    """Apply border_radius / border_width / border_color via a GradientDrawable.

    Android's standard ``View`` doesn't natively support arbitrary
    rounded backgrounds; the canonical workaround is to set the
    background to a ``GradientDrawable`` (the "shape" XML primitive)
    that renders the corner radius and stroke. We preserve any
    existing ``background_color`` by re-baking it into the drawable.
    Per-side borders route through
    [`_apply_side_border`][pythonnative.native_views.android._apply_side_border]
    instead.
    """
    if _apply_side_border(view, props):
        return
    has_border = any(k in props for k in ("border_radius", "border_width", "border_color", *_CORNER_RADIUS_KEYS))
    has_bg = "background_color" in props and props["background_color"] is not None
    if not has_border and not has_bg:
        return
    try:
        GradientDrawable = jclass("android.graphics.drawable.GradientDrawable")
        drawable = GradientDrawable()
        if "background_color" in props and props["background_color"] is not None:
            try:
                drawable.setColor(parse_color_int(props["background_color"]))
            except Exception:
                diagnostics.swallowed("android._apply_border")
        if any(props.get(k) is not None for k in _CORNER_RADIUS_KEYS):
            # Per-corner radii: unspecified corners inherit the uniform
            # ``border_radius`` (else 0). ``setCornerRadii`` takes eight
            # floats, an (x, y) pair per corner in _CORNER_RADIUS_KEYS
            # order, each in pixels.
            try:
                base_radius = float(props.get("border_radius") or 0.0)
                radii = []
                for key in _CORNER_RADIUS_KEYS:
                    r = float(_dp(float(props[key] if props.get(key) is not None else base_radius)))
                    radii.extend([r, r])
                drawable.setCornerRadii(radii)
            except Exception:
                diagnostics.swallowed("android._apply_border")
        elif "border_radius" in props and props["border_radius"] is not None:
            try:
                drawable.setCornerRadius(float(_dp(float(props["border_radius"]))))
            except Exception:
                diagnostics.swallowed("android._apply_border")
        if ("border_width" in props and props["border_width"] is not None) or (
            "border_color" in props and props["border_color"] is not None
        ):
            width = props.get("border_width", 1)
            color = props.get("border_color", "#000000")
            try:
                drawable.setStroke(
                    int(_dp(float(width or 0))),
                    parse_color_int(color or "#000000"),
                )
            except Exception:
                diagnostics.swallowed("android._apply_border")
        view.setBackground(drawable)
        try:
            drawable.invalidateSelf()
        except Exception:
            diagnostics.swallowed("android._apply_border")
        try:
            view.invalidate()
        except Exception:
            diagnostics.swallowed("android._apply_border")
    except Exception:
        diagnostics.swallowed("android._apply_border")


def _set_animated_background(view: Any, value: Any) -> None:
    """Apply one animated ``background_color`` frame without losing borders.

    Interpolations hand this module raw color values ("#AARRGGBB" or
    "#RRGGBB" strings, or ints). Views whose background is a
    border-rendering drawable (the uniform ``GradientDrawable`` or the
    per-side ``PNBorderDrawable``) must keep their corner radii and
    strokes while the fill animates, so the color routes through the
    same [`_apply_border`][pythonnative.native_views.android._apply_border]
    machinery ``update()`` uses. When the current background already is
    a ``GradientDrawable``, its fill is mutated in place, so no
    drawable is allocated per animation frame. Plain views take the
    direct ``setBackgroundColor`` path.
    """
    state = _state_of(view)
    visual = state.get("visual")
    has_border = isinstance(visual, dict) and any(
        visual.get(k) is not None for k in _DRAWABLE_STYLE_KEYS if k != "background_color"
    )
    if has_border:
        visual = dict(visual)
        visual["background_color"] = value
        state["visual"] = visual
        try:
            GradientDrawable = jclass("android.graphics.drawable.GradientDrawable")
            bg = view.getBackground()
            if bg is not None and isinstance(bg, GradientDrawable):
                bg.setColor(parse_color_int(value))
                return
        except Exception:
            diagnostics.swallowed("android._set_animated_background")
        # Per-side ``PNBorderDrawable`` backgrounds (immutable fill) and
        # first frames before any drawable exists re-bake the full set.
        _apply_border(view, visual)
        return
    view.setBackgroundColor(parse_color_int(value))


def _apply_shadow(view: Any, props: Dict[str, Any]) -> None:
    """Apply shadow props via elevation plus tinted outline shadows.

    Android renders view shadows from ``elevation``; iOS-style
    ``shadow_radius`` maps onto it so cross-platform styles work.
    On API 28+ the ambient/spot shadow colors are tinted with
    ``shadow_color`` (with ``shadow_opacity`` baked into the alpha
    channel), which is as close to iOS's layer shadows as the
    platform allows. ``shadow_offset`` has no Android equivalent and
    is ignored.
    """
    elevation = props.get("elevation")
    if elevation is None and "shadow_radius" in props:
        elevation = props.get("shadow_radius")
    if elevation is None and (props.get("shadow_color") is not None or props.get("shadow_opacity") is not None):
        # Shadow requested without an explicit size: use a Material
        # card-like default so the shadow is actually visible.
        elevation = 4.0
    if elevation is None:
        return
    try:
        view.setElevation(float(_dp(float(elevation))))
    except Exception:
        diagnostics.swallowed("android._apply_shadow")
    color = props.get("shadow_color")
    if color is None:
        return
    try:
        Build = jclass("android.os.Build")
        if int(Build.VERSION.SDK_INT) < 28:
            return
        argb = parse_color_int(color) & 0xFFFFFFFF
        opacity = props.get("shadow_opacity")
        if opacity is not None:
            alpha = int(max(0.0, min(1.0, float(opacity))) * 255)
            argb = (argb & 0x00FFFFFF) | (alpha << 24)
        signed = _signed_color(argb)
        view.setOutlineAmbientShadowColor(signed)
        view.setOutlineSpotShadowColor(signed)
    except Exception:
        diagnostics.swallowed("android._apply_shadow")


def _apply_transform(view: Any, props: Dict[str, Any]) -> None:
    """Apply transform list to scale/rotation/translation properties."""
    if "transform" not in props:
        return
    spec = props["transform"]
    if spec is None:
        try:
            view.setRotation(0.0)
            view.setScaleX(1.0)
            view.setScaleY(1.0)
            view.setTranslationX(0.0)
            view.setTranslationY(0.0)
        except Exception:
            diagnostics.swallowed("android._apply_transform")
        return
    entries = spec if isinstance(spec, list) else [spec]
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        try:
            if "rotate" in entry:
                v = entry["rotate"]
                if isinstance(v, str) and v.endswith("deg"):
                    angle = float(v[:-3])
                elif isinstance(v, str) and v.endswith("rad"):
                    angle = math.degrees(float(v[:-3]))
                else:
                    angle = float(v)
                view.setRotation(angle)
            if "scale" in entry:
                s = float(entry["scale"])
                view.setScaleX(s)
                view.setScaleY(s)
            if "scale_x" in entry:
                view.setScaleX(float(entry["scale_x"]))
            if "scale_y" in entry:
                view.setScaleY(float(entry["scale_y"]))
            if "translate_x" in entry:
                view.setTranslationX(float(_dp(float(entry["translate_x"]))))
            if "translate_y" in entry:
                view.setTranslationY(float(_dp(float(entry["translate_y"]))))
        except Exception:
            diagnostics.swallowed("android._apply_transform")


def _apply_accessibility(view: Any, props: Dict[str, Any]) -> None:
    """Apply accessibility props (label / accessible / state / live region / test_id)."""
    if "accessible" in props:
        try:
            View = jclass("android.view.View")
            view.setImportantForAccessibility(
                View.IMPORTANT_FOR_ACCESSIBILITY_YES if props["accessible"] else View.IMPORTANT_FOR_ACCESSIBILITY_NO
            )
        except Exception:
            diagnostics.swallowed("android._apply_accessibility")
    if "accessibility_label" in props:
        try:
            label = props["accessibility_label"]
            view.setContentDescription(str(label) if label is not None else None)
        except Exception:
            diagnostics.swallowed("android._apply_accessibility")
    if "accessibility_live_region" in props:
        try:
            mode = {"none": 0, "polite": 1, "assertive": 2}.get(
                str(props["accessibility_live_region"] or "none").lower(), 0
            )
            view.setAccessibilityLiveRegion(mode)
        except Exception:
            diagnostics.swallowed("android._apply_accessibility")

    state = props.get("accessibility_state")
    if isinstance(state, dict) and "selected" in state:
        try:
            view.setSelected(bool(state["selected"]))
        except Exception:
            diagnostics.swallowed("android._apply_accessibility")
    test_id = props.get("test_id")
    if test_id is None and not isinstance(state, dict):
        return
    # test_id (exposed as `resource-id` to UI Automator tools) and the
    # remaining state flags need an AccessibilityDelegate, which Python
    # can't subclass directly (Chaquopy proxies interfaces only); the
    # template ships PNAccessibilityDelegate for this. Older generated
    # projects without the class simply skip these props.
    try:
        vs = _state_of(view)
        delegate = vs.get("a11y_delegate")
        if delegate is None:
            PNAccessibilityDelegate = _pn_runtime_class("PNAccessibilityDelegate")
            delegate = PNAccessibilityDelegate()
            view.setAccessibilityDelegate(delegate)
            vs["a11y_delegate"] = delegate
        if test_id is not None:
            delegate.setTestId(str(test_id))
            view.setTag(str(test_id))
        if isinstance(state, dict):
            delegate.setStateDisabled(state.get("disabled"))
            delegate.setStateSelected(state.get("selected"))
            delegate.setStateChecked(state.get("checked"))
            delegate.setStateBusy(state.get("busy"))
            delegate.setStateExpanded(state.get("expanded"))
    except Exception:
        diagnostics.swallowed("android._apply_accessibility")


def _pointer_events_blocked(view: Any) -> bool:
    """Whether ``pointer_events`` disables the view's own touch handling.

    Consulted at the top of every touch-stream proxy (gesture, press)
    so listeners installed at create time honor the prop without being
    re-wired: ``"none"`` and ``"box_none"`` both mean the view itself
    must not observe or consume the stream.
    """
    merged = _state_of(view).get("props") or {}
    return merged.get("pointer_events") in ("none", "box_none")


def _apply_pointer_events(view: Any, value: Any) -> None:
    """Apply the ``pointer_events`` prop (``None`` restores ``"auto"``).

    Two cooperating layers implement the modes:

    - **Native interception** (preferred): containers built by
      [`_new_container`][pythonnative.native_views.android._new_container]
      are the template's ``PNFrameLayout``, whose
      ``setPointerEventsMode(String)`` drives real
      ``dispatchTouchEvent`` / ``onInterceptTouchEvent`` overrides.
      ``"none"`` declines the whole dispatch so touches pass through
      to views underneath, ``"box_only"`` intercepts events away from
      children, and ``"box_none"`` never intercepts. The call is
      guarded so older generated projects without the class (and
      non-container views) fall back cleanly.
    - **Python-side muting**: ``setClickable`` toggles whether the
      view claims events, and the touch-stream proxies consult
      [`_pointer_events_blocked`][pythonnative.native_views.android._pointer_events_blocked]
      so gesture/press wiring goes quiet without being torn down.
      ``"auto"`` / removal restores the original clickability
      captured before the first override.

    On a plain ``FrameLayout`` (old template) the fallback keeps the
    previous approximation: ``"none"`` silences the view itself but
    interactive children keep receiving touches, and ``"box_only"``
    only claims events no interactive child consumed. ``"box_none"``
    is exact either way, since children need no help.
    """
    mode = value if value is not None else "auto"
    state = _state_of(view)
    try:
        view.setPointerEventsMode(str(mode))
    except Exception:
        # Plain FrameLayout, a leaf widget, or an older template
        # without PNFrameLayout; the Python-side fallback still runs.
        pass
    try:
        if mode in ("none", "box_none"):
            state.setdefault("pe_was_clickable", bool(view.isClickable()))
            view.setClickable(False)
        elif mode == "box_only":
            state.setdefault("pe_was_clickable", bool(view.isClickable()))
            view.setClickable(True)
        elif "pe_was_clickable" in state:
            view.setClickable(bool(state.pop("pe_was_clickable")))
    except Exception:
        diagnostics.swallowed("android._apply_pointer_events")


def _hit_slop_insets(value: Any) -> Optional[Tuple[float, float, float, float]]:
    """Normalize a ``hit_slop`` prop into ``(top, left, bottom, right)`` points.

    Accepts a uniform number or a dict with any of ``top`` / ``left``
    / ``bottom`` / ``right``. Returns ``None`` for absent or
    unparseable values.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        try:
            return (
                float(value.get("top") or 0.0),
                float(value.get("left") or 0.0),
                float(value.get("bottom") or 0.0),
                float(value.get("right") or 0.0),
            )
        except Exception:
            return None
    try:
        uniform = float(value)
    except Exception:
        return None
    return (uniform, uniform, uniform, uniform)


def _update_hit_slop(view: Any) -> None:
    """Extend the view's touch target via a ``TouchDelegate`` on its parent.

    The standard Android mechanism: the parent forwards touches
    landing inside an expanded ``Rect`` (the view's frame plus the
    slop insets, in parent-relative pixels) to the view. Parents are
    PythonNative-managed ``FrameLayout``s, so installing the delegate
    is safe; a parent only holds one delegate, so among siblings the
    last ``hit_slop`` applied wins (matching the platform limitation).

    Requires a known frame, so
    [`set_frame`][pythonnative.native_views.android.AndroidViewHandler.set_frame]
    records the frame and re-invokes this; prop-only updates before
    the first frame defer until layout runs.
    """
    state = _state_of(view)
    frame = state.get("frame")
    if frame is None:
        return
    merged = state.get("props") or {}
    insets = _hit_slop_insets(merged.get("hit_slop"))
    try:
        parent = view.getParent()
        if parent is None:
            return
        if insets is None:
            if state.pop("hit_slop_active", None):
                parent.setTouchDelegate(None)
            return
        top, left, bottom, right = insets
        x, y, width, height = frame
        Rect = jclass("android.graphics.Rect")
        TouchDelegate = jclass("android.view.TouchDelegate")
        rect = Rect(
            _dp(x - left),
            _dp(y - top),
            _dp(x + width + right),
            _dp(y + height + bottom),
        )
        parent.setTouchDelegate(TouchDelegate(rect, view))
        state["hit_slop_active"] = True
    except Exception:
        diagnostics.swallowed("android._update_hit_slop")


def _apply_common_visual(view: Any, props: Dict[str, Any]) -> None:
    """Apply visual properties shared across many handlers."""
    has_drawable_keys = any(k in props for k in _DRAWABLE_STYLE_KEYS)
    if has_drawable_keys:
        state = _state_of(view)
        visual_props = dict(state.get("visual") or {})
        for key in _DRAWABLE_STYLE_KEYS:
            if key in props:
                visual_props[key] = props[key]
        state["visual"] = visual_props
        _apply_border(view, visual_props)
    if "overflow" in props:
        clip = props["overflow"] == "hidden"
        try:
            view.setClipChildren(clip)
            view.setClipToPadding(clip)
        except Exception:
            diagnostics.swallowed("android._apply_common_visual")
    if "opacity" in props and props["opacity"] is not None:
        try:
            view.setAlpha(float(props["opacity"]))
        except Exception:
            diagnostics.swallowed("android._apply_common_visual")
    if "z_index" in props:
        # ``setZ`` takes pixels, so scale like other coordinates; a
        # removal (``None``) resets the view to the default plane.
        try:
            z = props["z_index"]
            view.setZ(float(_dp(float(z))) if z is not None else 0.0)
        except Exception:
            diagnostics.swallowed("android._apply_common_visual")
    if "pointer_events" in props:
        _apply_pointer_events(view, props["pointer_events"])
    if "hit_slop" in props:
        _update_hit_slop(view)
    _apply_shadow(view, props)
    _apply_transform(view, props)
    _apply_accessibility(view, props)


# ======================================================================
# Gesture wiring (MotionEvent -> GestureArbiter -> dispatch_event)
# ======================================================================


def _wire_gestures(view: Any, specs: Any) -> None:
    """Feed ``MotionEvent`` streams on ``view`` into a `GestureArbiter`.

    The arbiter emits ``(gesture_index, payload)`` pairs which are
    forwarded as ``gesture:<i>`` events for this view's tag. Specs
    (including ``simultaneous`` / ``wait_for`` metadata and fling
    configs) pass through to the arbiter untouched; all arbitration
    and recognition live in ``pythonnative.gestures``. Time-based
    deadlines (long press, multi-tap windows) are polled with a
    main-looper ``Handler`` scheduled at the arbiter's
    ``next_deadline()``. When a pan activates, the parent is asked
    not to intercept so an enclosing ScrollView can't steal the drag.
    """
    state = _state_of(view)
    if not isinstance(specs, (list, tuple)) or not specs:
        state["arbiter"] = None
        return

    def _emit(index: int, payload: Dict[str, Any]) -> None:
        _fire(view, f"gesture:{index}", payload)

    arbiter = make_arbiter([s for s in specs if isinstance(s, dict)], _emit)
    state["arbiter"] = arbiter
    if state.get("gestures_bound"):
        return
    state["gestures_bound"] = True
    _bind_touch_stream(view, state)


def _schedule_arbiter_poll(view: Any, state: Dict[str, Any]) -> None:
    """Schedule a main-looper poll at the arbiter's next deadline.

    Deadlines cover every time-based recognizer decision: long-press
    activation and the multi-tap windows that flush an Exclusive
    double-tap/single-tap buffer. Called after every pointer event
    (not just DOWN) because a deadline can appear on UP, when no
    further touch events arrive to drive the arbiter forward.

    A pending poll at or before the requested deadline is reused
    rather than stacking duplicate runnables; each poll reschedules
    itself for the following deadline until none remains.
    """
    arbiter = state.get("arbiter")
    if arbiter is None:
        return
    deadline = arbiter.next_deadline()
    if deadline is None:
        return
    pending = state.get("poll_deadline")
    if pending is not None and pending <= deadline + 0.001:
        return
    delay_ms = max(1, int((deadline - time.monotonic()) * 1000.0))
    try:
        Handler = jclass("android.os.Handler")
        Looper = jclass("android.os.Looper")
        Runnable = jclass("java.lang.Runnable")
        handler = state.get("poll_handler")
        if handler is None:
            handler = Handler(Looper.getMainLooper())
            state["poll_handler"] = handler
        token = state.get("poll_token", 0) + 1
        state["poll_token"] = token
        state["poll_deadline"] = deadline

        class _PollRunnable(dynamic_proxy(Runnable)):
            def run(self) -> None:
                if state.get("poll_token") == token:
                    state["poll_deadline"] = None
                live = state.get("arbiter")
                if live is not None:
                    live.poll(time.monotonic())
                    _schedule_arbiter_poll(view, state)

        handler.postDelayed(_PollRunnable(), delay_ms)
    except Exception:
        state["poll_deadline"] = None
        diagnostics.swallowed("android._schedule_arbiter_poll")


def _bind_touch_stream(view: Any, state: Dict[str, Any]) -> None:
    """Install one ``OnTouchListener`` that forwards every pointer to the arbiter."""
    try:
        OnTouchListener = jclass("android.view.View$OnTouchListener")

        class _GestureTouchProxy(dynamic_proxy(OnTouchListener)):
            def onTouch(self, v: Any, event: Any) -> bool:
                if _pointer_events_blocked(v):
                    return False
                return bool(_feed_motion_event(v, state, event))

        view.setOnTouchListener(_GestureTouchProxy())
    except Exception:
        diagnostics.swallowed("android._bind_touch_stream")


def _feed_motion_event(view: Any, state: Dict[str, Any], event: Any) -> bool:
    """Translate one ``MotionEvent`` into arbiter pointer calls.

    Returns ``True`` to keep receiving the stream while any gesture
    spec is wired.
    """
    arbiter = state.get("arbiter")
    if arbiter is None:
        return False
    try:
        action = int(event.getActionMasked())
        t = time.monotonic()
        density = _density() or 1.0
        if action in (0, 5):  # DOWN / POINTER_DOWN
            idx = int(event.getActionIndex())
            pid = int(event.getPointerId(idx))
            arbiter.pointer_down(pid, float(event.getX(idx)) / density, float(event.getY(idx)) / density, t)
        elif action == 2:  # MOVE
            for i in range(int(event.getPointerCount())):
                pid = int(event.getPointerId(i))
                arbiter.pointer_move(pid, float(event.getX(i)) / density, float(event.getY(i)) / density, t)
            if arbiter.has_active_pan():
                try:
                    parent = view.getParent()
                    if parent is not None:
                        parent.requestDisallowInterceptTouchEvent(True)
                except Exception:
                    diagnostics.swallowed("android._feed_motion_event")
        elif action in (1, 6):  # UP / POINTER_UP
            idx = int(event.getActionIndex())
            pid = int(event.getPointerId(idx))
            arbiter.pointer_up(pid, float(event.getX(idx)) / density, float(event.getY(idx)) / density, t)
        elif action == 3:  # CANCEL
            arbiter.cancel(t)
        # Every event can move the next time-based deadline (long-press
        # activation, multi-tap windows opened on UP), so reschedule
        # unconditionally; the scheduler dedups pending polls.
        _schedule_arbiter_poll(view, state)
        return True
    except Exception:
        return True


# ======================================================================
# Native-driven animations (ObjectAnimator)
# ======================================================================

_native_anims: Dict[int, Dict[str, Any]] = {}


def _interpolator_for(easing: str) -> Any:
    mapping = {
        "linear": "android.view.animation.LinearInterpolator",
        "ease_in": "android.view.animation.AccelerateInterpolator",
        "ease_out": "android.view.animation.DecelerateInterpolator",
        "ease_in_out": "android.view.animation.AccelerateDecelerateInterpolator",
    }
    cls = mapping.get(easing, "android.view.animation.AccelerateDecelerateInterpolator")
    return jclass(cls)()


_ANIMATABLE_FLOAT_PROPS = {
    "opacity": ("alpha", 1.0),
    "translate_x": ("translationX", None),  # dp -> px scaling
    "translate_y": ("translationY", None),
    "scale_x": ("scaleX", 1.0),
    "scale_y": ("scaleY", 1.0),
    "rotate": ("rotation", 1.0),
}


def _read_animated_value(view: Any, prop_name: str) -> Any:
    """Read the current (presentation) value of an animatable property."""
    try:
        density = _density() or 1.0
        if prop_name == "opacity":
            return float(view.getAlpha())
        if prop_name == "translate_x":
            return float(view.getTranslationX()) / density
        if prop_name == "translate_y":
            return float(view.getTranslationY()) / density
        if prop_name in ("scale", "scale_x"):
            return float(view.getScaleX())
        if prop_name == "scale_y":
            return float(view.getScaleY())
        if prop_name == "rotate":
            return float(view.getRotation())
    except Exception:
        diagnostics.swallowed("android._read_animated_value")
    return None


def _make_end_listener(anim_id: int) -> Any:
    """Build an ``Animator.AnimatorListener`` that reports completion to Python."""
    AnimatorListener = jclass("android.animation.Animator$AnimatorListener")

    class _EndProxy(dynamic_proxy(AnimatorListener)):
        # ``onAnimationStart`` / ``onAnimationEnd`` accept an optional
        # ``isReverse``: API 26 added default two-arg overloads to
        # ``AnimatorListener``, and ``ValueAnimator`` invokes those, so
        # the java.lang.reflect.Proxy forwards two arguments here.

        def __init__(self) -> None:
            super().__init__()
            self._cancelled = False

        def onAnimationStart(self, animation: Any, isReverse: bool = False) -> None:
            pass

        def onAnimationRepeat(self, animation: Any) -> None:
            pass

        def onAnimationCancel(self, animation: Any) -> None:
            self._cancelled = True

        def onAnimationEnd(self, animation: Any, isReverse: bool = False) -> None:
            entry = _native_anims.pop(anim_id, None)
            if entry is None:
                return
            try:
                from ..animated import native_animation_completed

                native_animation_completed(anim_id, not self._cancelled)
            except Exception:
                diagnostics.swallowed("android._make_end_listener._EndProxy.onAnimationEnd")

    return _EndProxy()


def _start_native_timing(view: Any, anim_id: int, prop_name: str, spec: Dict[str, Any]) -> bool:
    """Drive a ``timing`` spec with ``ObjectAnimator``. Returns success."""
    try:
        ObjectAnimator = jclass("android.animation.ObjectAnimator")
        from_val = float(spec.get("from", 0.0))
        to_val = float(spec.get("to", 0.0))
        duration = max(0, int(float(spec.get("duration_ms", 300.0))))
        density = _density() or 1.0

        if prop_name == "background_color":
            animator = ObjectAnimator.ofArgb(
                view,
                "backgroundColor",
                parse_color_int(int(from_val)),
                parse_color_int(int(to_val)),
            )
        elif prop_name == "scale":
            AnimatorSet = jclass("android.animation.AnimatorSet")
            sx = ObjectAnimator.ofFloat(view, "scaleX", from_val, to_val)
            sy = ObjectAnimator.ofFloat(view, "scaleY", from_val, to_val)
            group = AnimatorSet()
            group.playTogether([sx, sy])
            group.setDuration(duration)
            group.setInterpolator(_interpolator_for(str(spec.get("easing", "ease_in_out"))))
            group.addListener(_make_end_listener(anim_id))
            _native_anims[anim_id] = {"animator": group, "view": view, "prop": prop_name}
            group.start()
            return True
        else:
            java_prop, scale = _ANIMATABLE_FLOAT_PROPS.get(prop_name, (None, None))
            if java_prop is None:
                return False
            factor = density if scale is None else scale
            animator = ObjectAnimator.ofFloat(view, java_prop, from_val * factor, to_val * factor)

        animator.setDuration(duration)
        animator.setInterpolator(_interpolator_for(str(spec.get("easing", "ease_in_out"))))
        animator.addListener(_make_end_listener(anim_id))
        _native_anims[anim_id] = {"animator": animator, "view": view, "prop": prop_name}
        animator.start()
        return True
    except Exception:
        _native_anims.pop(anim_id, None)
        return False


# ======================================================================
# Base class with shared frame/measure/animation implementations
# ======================================================================


class AndroidViewHandler(ViewHandler):
    """Base class providing the shared protocol implementation.

    Subclasses implement
    [`_build`][pythonnative.native_views.android.AndroidViewHandler._build]
    (construct the widget) and
    [`_apply`][pythonnative.native_views.android.AndroidViewHandler._apply]
    (apply visual props); the base class owns tag registration,
    gesture wiring, frame application, intrinsic measurement, and the
    animation hooks.
    """

    def create(self, tag: int, props: Dict[str, Any]) -> Any:
        view = self._build(props)
        _remember(view, tag)
        _state_of(view)["props"] = dict(props)
        self._apply(view, props, initial=True)
        if props.get("gestures"):
            _wire_gestures(view, props.get("gestures"))
        return view

    def update(self, native_view: Any, changed_props: Dict[str, Any]) -> None:
        state = _state_of(native_view)
        merged = state.setdefault("props", {})
        merged.update(changed_props)
        self._apply(native_view, changed_props, initial=False)
        if "gestures" in changed_props:
            _wire_gestures(native_view, changed_props.get("gestures"))

    def destroy(self, native_view: Any) -> None:
        self._teardown(native_view)
        try:
            parent = native_view.getParent()
            if parent is not None:
                parent.removeView(native_view)
        except Exception:
            diagnostics.swallowed("android.AndroidViewHandler.destroy")
        _forget(native_view)

    def _build(self, props: Dict[str, Any]) -> Any:
        raise NotImplementedError

    def _apply(self, view: Any, props: Dict[str, Any], initial: bool) -> None:
        _apply_common_visual(view, props)

    def _teardown(self, native_view: Any) -> None:
        """Subclass hook for extra cleanup before the view is released."""

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        if native_view is None:
            return
        try:
            px_x = _dp(x)
            px_y = _dp(y)
            px_w = max(0, _dp(width))
            px_h = max(0, _dp(height))
            lp = native_view.getLayoutParams()
            if lp is None:
                FrameLP = jclass("android.widget.FrameLayout$LayoutParams")
                lp = FrameLP(px_w, px_h)
            else:
                try:
                    lp.width = px_w
                    lp.height = px_h
                except Exception:
                    diagnostics.swallowed("android.AndroidViewHandler.set_frame")
            try:
                lp.leftMargin = px_x
                lp.topMargin = px_y
                lp.rightMargin = 0
                lp.bottomMargin = 0
            except Exception:
                diagnostics.swallowed("android.AndroidViewHandler.set_frame")
            native_view.setLayoutParams(lp)
            # ``hit_slop`` needs the frame (and an attached parent, which
            # exists by the time frames are applied) to size its
            # TouchDelegate rect, so record the frame and recompute here.
            state = _state_of(native_view)
            state["frame"] = (x, y, width, height)
            if (state.get("props") or {}).get("hit_slop") is not None or state.get("hit_slop_active"):
                _update_hit_slop(native_view)
        except Exception:
            diagnostics.swallowed("android.AndroidViewHandler.set_frame")

    def measure_intrinsic(
        self,
        native_view: Any,
        max_width: float,
        max_height: float,
    ) -> Tuple[float, float]:
        try:
            density = _density()
            View = jclass("android.view.View")
            MeasureSpec = View.MeasureSpec
            w_spec = (
                MeasureSpec.makeMeasureSpec(int(_safe_max(max_width) * density), MeasureSpec.AT_MOST)
                if math.isfinite(max_width)
                else MeasureSpec.makeMeasureSpec(0, MeasureSpec.UNSPECIFIED)
            )
            h_spec = (
                MeasureSpec.makeMeasureSpec(int(_safe_max(max_height) * density), MeasureSpec.AT_MOST)
                if math.isfinite(max_height)
                else MeasureSpec.makeMeasureSpec(0, MeasureSpec.UNSPECIFIED)
            )
            native_view.measure(w_spec, h_spec)
            return (
                native_view.getMeasuredWidth() / density,
                native_view.getMeasuredHeight() / density,
            )
        except Exception:
            return (0.0, 0.0)

    def set_animated_property(self, native_view: Any, prop_name: str, value: Any) -> None:
        """Apply one Python-driven animation frame immediately.

        Handles float transform props (dp-scaled translations, scales,
        rotation degrees, opacity) and interpolated color frames for
        ``background_color`` / ``color`` ("#AARRGGBB" / "#RRGGBB"
        strings or ints). Unknown props are silently ignored.
        """
        if native_view is None:
            return
        try:
            if prop_name == "opacity":
                native_view.setAlpha(float(value))
            elif prop_name == "translate_x":
                native_view.setTranslationX(float(_dp(float(value))))
            elif prop_name == "translate_y":
                native_view.setTranslationY(float(_dp(float(value))))
            elif prop_name == "scale":
                native_view.setScaleX(float(value))
                native_view.setScaleY(float(value))
            elif prop_name == "scale_x":
                native_view.setScaleX(float(value))
            elif prop_name == "scale_y":
                native_view.setScaleY(float(value))
            elif prop_name == "rotate":
                native_view.setRotation(float(value))
            elif prop_name == "background_color":
                _set_animated_background(native_view, value)
            elif prop_name == "color":
                # Interpolations emit "#AARRGGBB" strings; parse_color_int
                # accepts strings and raw ints alike. Views without
                # setTextColor fall into the except below and skip.
                native_view.setTextColor(parse_color_int(value))
        except Exception:
            diagnostics.swallowed("android.AndroidViewHandler.set_animated_property")

    def start_animation(
        self,
        native_view: Any,
        anim_id: int,
        prop_name: str,
        spec: Dict[str, Any],
    ) -> bool:
        """Run ``timing`` specs on ``ObjectAnimator``; reject the rest.

        Springs and decay need the exact physics integration the
        Python ticker implements, so they return ``False`` and fall
        back rather than approximating with an interpolator.
        """
        if native_view is None or not isinstance(spec, dict):
            return False
        if str(spec.get("kind", "")) != "timing":
            return False
        return _start_native_timing(native_view, anim_id, prop_name, spec)

    def cancel_animation(self, native_view: Any, anim_id: int) -> Any:
        entry = _native_anims.pop(anim_id, None)
        if entry is None:
            return None
        try:
            entry["animator"].cancel()
        except Exception:
            diagnostics.swallowed("android.AndroidViewHandler.cancel_animation")
        return _read_animated_value(entry.get("view"), str(entry.get("prop", "")))


# ======================================================================
# Flex container handler (shared by Column, Row, View)
# ======================================================================


class FlexContainerHandler(AndroidViewHandler):
    """Container for flex layout, a bare `FrameLayout`.

    All flex semantics (direction, alignment, distribution, padding)
    are computed by the layout engine and applied via
    [`set_frame`][pythonnative.native_views.android.AndroidViewHandler.set_frame].
    The container itself is just a positioning surface (the template's
    ``PNFrameLayout`` when available, so ``pointer_events`` gets real
    touch interception).
    """

    def _build(self, props: Dict[str, Any]) -> Any:
        return _new_container()

    def insert_child(self, parent: Any, child: Any, index: int) -> None:
        _insert_view(parent, child, index)

    def remove_child(self, parent: Any, child: Any) -> None:
        try:
            parent.removeView(child)
        except Exception:
            diagnostics.swallowed("android.FlexContainerHandler.remove_child")


def _insert_view(parent: Any, child: Any, index: int) -> None:
    """Move-aware indexed insert into any ``ViewGroup``."""
    try:
        current_parent = child.getParent()
        count = int(parent.getChildCount())
        if current_parent is not None and _java_id(current_parent) == _java_id(parent):
            current_index = int(parent.indexOfChild(child))
            target = max(0, min(index, count - 1))
            if current_index == target:
                return
            parent.removeView(child)
            parent.addView(child, max(0, min(target, int(parent.getChildCount()))))
            return
        if current_parent is not None:
            current_parent.removeView(child)
        FrameLP = jclass("android.widget.FrameLayout$LayoutParams")
        if child.getLayoutParams() is None:
            child.setLayoutParams(FrameLP(0, 0))
        parent.addView(child, max(0, min(index, int(parent.getChildCount()))))
    except Exception:
        try:
            parent.addView(child)
        except Exception:
            diagnostics.swallowed("android._insert_view")


# ======================================================================
# Leaf handlers
# ======================================================================


def _typeface_for(weight: Any, italic: bool) -> Any:
    Typeface = jclass("android.graphics.Typeface")
    style = Typeface.NORMAL
    is_bold = False
    if isinstance(weight, str):
        is_bold = weight.lower() in ("bold", "semibold", "black", "heavy", "extrabold")
    elif isinstance(weight, (int, float)):
        is_bold = float(weight) >= 600
    if is_bold and italic:
        style = Typeface.BOLD_ITALIC
    elif is_bold:
        style = Typeface.BOLD
    elif italic:
        style = Typeface.ITALIC
    return style


def _build_spannable(spans: Any) -> Any:
    """Build a ``SpannableStringBuilder`` from a rich-text span list.

    Each span dict carries ``text`` plus optional per-span overrides
    (``color``, ``background_color``, ``font_size``, ``font_family``,
    ``bold`` / ``italic`` / ``font_weight``, ``text_decoration``).
    Spans without overrides inherit the TextView's base styling.
    """
    SpannableStringBuilder = jclass("android.text.SpannableStringBuilder")
    Typeface = jclass("android.graphics.Typeface")
    FLAG = 33  # Spanned.SPAN_EXCLUSIVE_EXCLUSIVE

    builder = SpannableStringBuilder()
    for span in spans:
        if not isinstance(span, dict):
            continue
        text = str(span.get("text", ""))
        if not text:
            continue
        start = builder.length()
        builder.append(text)
        end = builder.length()

        def _set(obj: Any) -> None:
            builder.setSpan(obj, start, end, FLAG)

        try:
            if span.get("color") is not None:
                ForegroundColorSpan = jclass("android.text.style.ForegroundColorSpan")
                _set(ForegroundColorSpan(parse_color_int(span["color"])))
            if span.get("background_color") is not None:
                BackgroundColorSpan = jclass("android.text.style.BackgroundColorSpan")
                _set(BackgroundColorSpan(parse_color_int(span["background_color"])))
            if span.get("font_size") is not None:
                AbsoluteSizeSpan = jclass("android.text.style.AbsoluteSizeSpan")
                _set(AbsoluteSizeSpan(int(float(span["font_size"])), True))  # dip units
            bold = bool(span.get("bold"))
            weight = span.get("font_weight")
            if not bold and weight is not None:
                try:
                    bold = str(weight) in ("bold", "600", "700", "800", "900")
                except Exception:
                    bold = False
            italic = bool(span.get("italic"))
            if bold or italic:
                StyleSpan = jclass("android.text.style.StyleSpan")
                if bold and italic:
                    _set(StyleSpan(Typeface.BOLD_ITALIC))
                elif bold:
                    _set(StyleSpan(Typeface.BOLD))
                else:
                    _set(StyleSpan(Typeface.ITALIC))
            if span.get("font_family"):
                TypefaceSpan = jclass("android.text.style.TypefaceSpan")
                _set(TypefaceSpan(str(span["font_family"])))
            decoration = span.get("text_decoration")
            if decoration == "underline":
                UnderlineSpan = jclass("android.text.style.UnderlineSpan")
                _set(UnderlineSpan())
            elif decoration == "line_through":
                StrikethroughSpan = jclass("android.text.style.StrikethroughSpan")
                _set(StrikethroughSpan())
        except Exception:
            diagnostics.swallowed("android._build_spannable")
    return builder


class TextHandler(AndroidViewHandler):
    def _build(self, props: Dict[str, Any]) -> Any:
        return jclass("android.widget.TextView")(_ctx())

    def _apply(self, tv: Any, props: Dict[str, Any], initial: bool) -> None:
        if "spans" in props or "text" in props:
            # ``update()`` merges changed props into the view state
            # before calling ``_apply``, so the merged dict always has
            # the latest text/spans pair (covering rich -> plain
            # transitions where only ``spans`` changed).
            merged = _state_of(tv).get("props") or props
            spans = merged.get("spans")
            if spans:
                try:
                    tv.setText(_build_spannable(spans))
                except Exception:
                    tv.setText(str(merged.get("text") or ""))
            else:
                text = merged.get("text")
                tv.setText(str(text) if text is not None else "")
        if "font_size" in props and props["font_size"] is not None:
            tv.setTextSize(float(props["font_size"]))
        if "color" in props and props["color"] is not None:
            tv.setTextColor(parse_color_int(props["color"]))
        if any(k in props for k in ("font_family", "font_weight", "italic", "bold")):
            try:
                Typeface = jclass("android.graphics.Typeface")
                merged = _state_of(tv).get("props") or props
                family = merged.get("font_family")
                weight = merged.get("font_weight") or ("bold" if merged.get("bold") else None)
                italic = bool(merged.get("italic"))
                style = _typeface_for(weight, italic)
                if family:
                    base = Typeface.create(str(family), style)
                    tv.setTypeface(base)
                else:
                    tv.setTypeface(tv.getTypeface(), style)
            except Exception:
                diagnostics.swallowed("android.TextHandler._apply")
        if "max_lines" in props and props["max_lines"] is not None:
            tv.setMaxLines(int(props["max_lines"]))
        if "text_align" in props:
            Gravity = jclass("android.view.Gravity")
            mapping = {"left": Gravity.START, "center": Gravity.CENTER, "right": Gravity.END}
            tv.setGravity(mapping.get(props["text_align"], Gravity.START))
        if "letter_spacing" in props and props["letter_spacing"] is not None:
            try:
                # Android expects letter_spacing as ems (a unitless ratio of font size).
                # Convert from points by dividing by ~font_size; if no font size, use 16.
                merged = _state_of(tv).get("props") or props
                size = float(merged.get("font_size") or 16.0)
                tv.setLetterSpacing(float(props["letter_spacing"]) / max(size, 1.0))
            except Exception:
                diagnostics.swallowed("android.TextHandler._apply")
        if "line_height" in props and props["line_height"] is not None:
            try:
                merged = _state_of(tv).get("props") or props
                size = float(merged.get("font_size") or 16.0)
                tv.setLineSpacing(0.0, float(props["line_height"]) / max(size, 1.0))
            except Exception:
                diagnostics.swallowed("android.TextHandler._apply")
        if "text_decoration" in props:
            try:
                Paint = jclass("android.graphics.Paint")
                flags = tv.getPaintFlags() & ~Paint.UNDERLINE_TEXT_FLAG & ~Paint.STRIKE_THRU_TEXT_FLAG
                if props["text_decoration"] == "underline":
                    flags |= Paint.UNDERLINE_TEXT_FLAG
                elif props["text_decoration"] == "line_through":
                    flags |= Paint.STRIKE_THRU_TEXT_FLAG
                tv.setPaintFlags(flags)
            except Exception:
                diagnostics.swallowed("android.TextHandler._apply")
        _apply_common_visual(tv, props)


class ButtonHandler(AndroidViewHandler):
    def _build(self, props: Dict[str, Any]) -> Any:
        btn = jclass("android.widget.Button")(_ctx())

        class ClickProxy(dynamic_proxy(jclass("android.view.View").OnClickListener)):
            def onClick(self, view: Any) -> None:
                _fire(view, "on_press")

        btn.setOnClickListener(ClickProxy())
        return btn

    def _apply(self, btn: Any, props: Dict[str, Any], initial: bool) -> None:
        if "title" in props:
            btn.setText(str(props["title"]) if props["title"] is not None else "")
        if "font_size" in props and props["font_size"] is not None:
            btn.setTextSize(float(props["font_size"]))
        if "color" in props and props["color"] is not None:
            btn.setTextColor(parse_color_int(props["color"]))
        if "enabled" in props:
            btn.setEnabled(bool(props["enabled"]))
        _apply_common_visual(btn, props)


class ScrollViewHandler(AndroidViewHandler):
    """Scroll container: wraps a single child whose height is unbounded.

    Uses ``androidx.core.widget.NestedScrollView`` (vertical) or
    ``android.widget.HorizontalScrollView`` so nested scroll views
    cooperate instead of fighting over gestures.

    When a ``refresh_control`` prop is provided at creation, the scroll
    view is wrapped in a ``SwipeRefreshLayout`` (the returned view is
    the wrapper, and child management forwards into the inner scroll
    view) so pull-to-refresh matches the iOS ``UIRefreshControl`` path.

    Scroll offsets are reported as ``on_scroll`` events with a
    ``{"x": pts, "y": pts}`` payload. Imperative commands:
    ``scroll_to_offset`` / ``scroll_to_end`` / ``get_scroll_offset``.
    """

    def create(self, tag: int, props: Dict[str, Any]) -> Any:
        horizontal = props.get("scroll_axis") == "horizontal"
        if horizontal:
            sv = jclass("android.widget.HorizontalScrollView")(_ctx())
        else:
            try:
                sv = jclass("androidx.core.widget.NestedScrollView")(_ctx())
            except Exception:
                sv = jclass("android.widget.ScrollView")(_ctx())

        # Vertical scroll views are *always* wrapped in a (disabled)
        # SwipeRefreshLayout. Wrapping later is impossible; the
        # reconciler may reuse this view for a screen that adds a
        # ``refresh_control`` prop afterwards (e.g. navigation swapping
        # screens of the same shape), and re-parenting a mounted view
        # mid-update is not safe. ``_apply_refresh`` simply toggles the
        # wrapper's enabled state as the prop comes and goes.
        outer = sv
        if not horizontal:
            wrapper = self._wrap_in_refresh(sv)
            if wrapper is not None:
                outer = wrapper

        _remember(outer, tag)
        state = _state_of(outer)
        state["props"] = dict(props)
        state["scroll"] = sv
        state["horizontal"] = horizontal
        if outer is not sv:
            state["refresh"] = outer
            self._bind_refresh_listener(outer)
            if not props.get("refresh_control"):
                try:
                    outer.setEnabled(False)
                except Exception:
                    diagnostics.swallowed("android.ScrollViewHandler.create")
        self._bind_scroll_listener(outer, sv)
        self._apply(outer, props, initial=True)
        if props.get("gestures"):
            _wire_gestures(outer, props.get("gestures"))
        return outer

    def _apply(self, outer: Any, props: Dict[str, Any], initial: bool) -> None:
        state = _state_of(outer)
        sv = state.get("scroll", outer)
        _apply_common_visual(sv, props)
        if "shows_scroll_indicator" in props:
            # Only present when ``False`` (hide); a removal restores bars.
            show = props["shows_scroll_indicator"] is not False
            try:
                sv.setVerticalScrollBarEnabled(show)
                sv.setHorizontalScrollBarEnabled(show)
            except Exception:
                diagnostics.swallowed("android.ScrollViewHandler._apply")
        if "bounces" in props:
            # ``bounces`` is only present when ``False``; map it to the
            # closest analogue, the over-scroll (glow) mode.
            try:
                View = jclass("android.view.View")
                mode = View.OVER_SCROLL_NEVER if props["bounces"] is False else View.OVER_SCROLL_IF_CONTENT_SCROLLS
                sv.setOverScrollMode(mode)
            except Exception:
                diagnostics.swallowed("android.ScrollViewHandler._apply")
        if "refresh_control" in props and state.get("refresh") is not None:
            self._apply_refresh(outer, props)
        # ``paging_enabled`` and ``keyboard_dismiss_mode`` have no clean
        # NestedScrollView analogue, so they are intentionally skipped
        # rather than approximated poorly.

    def insert_child(self, parent: Any, child: Any, index: int) -> None:
        sv = _state_of(parent).get("scroll", parent)
        _insert_view(sv, child, index)

    def remove_child(self, parent: Any, child: Any) -> None:
        sv = _state_of(parent).get("scroll", parent)
        try:
            sv.removeView(child)
        except Exception:
            diagnostics.swallowed("android.ScrollViewHandler.remove_child")

    def command(self, native_view: Any, name: str, args: Dict[str, Any]) -> Any:
        state = _state_of(native_view)
        sv = state.get("scroll", native_view)
        density = _density() or 1.0
        if name == "scroll_to_offset":
            x_px = int(float(args.get("x", 0.0) or 0.0) * density)
            y_px = int(float(args.get("y", 0.0) or 0.0) * density)
            animated = args.get("animated", True) is not False
            try:
                if animated and hasattr(sv, "smoothScrollTo"):
                    sv.smoothScrollTo(x_px, y_px)
                else:
                    sv.scrollTo(x_px, y_px)
            except Exception:
                diagnostics.swallowed("android.ScrollViewHandler.command")
            return None
        if name == "scroll_to_end":
            try:
                child = sv.getChildAt(0) if int(sv.getChildCount()) > 0 else None
                if child is None:
                    return None
                if state.get("horizontal"):
                    target_x = max(0, int(child.getWidth()) - int(sv.getWidth()))
                    sv.smoothScrollTo(target_x, 0)
                else:
                    target_y = max(0, int(child.getHeight()) - int(sv.getHeight()))
                    sv.smoothScrollTo(0, target_y)
            except Exception:
                diagnostics.swallowed("android.ScrollViewHandler.command")
            return None
        if name == "get_scroll_offset":
            try:
                return {
                    "x": float(sv.getScrollX()) / density,
                    "y": float(sv.getScrollY()) / density,
                }
            except Exception:
                return {"x": 0.0, "y": 0.0}
        return None

    def _bind_scroll_listener(self, outer: Any, sv: Any) -> None:
        try:
            if jclass("android.os.Build$VERSION").SDK_INT < 23:
                return

            class _ScrollChangeProxy(dynamic_proxy(jclass("android.view.View").OnScrollChangeListener)):
                def onScrollChange(
                    self,
                    v: Any,
                    scroll_x: int,
                    scroll_y: int,
                    old_x: int,
                    old_y: int,
                ) -> None:
                    try:
                        density = _density() or 1.0
                        _fire(outer, "on_scroll", {"x": scroll_x / density, "y": scroll_y / density})
                    except Exception:
                        diagnostics.swallowed(
                            "android.ScrollViewHandler._bind_scroll_listener._ScrollChangeProxy.onScrollChange"
                        )

            sv.setOnScrollChangeListener(_ScrollChangeProxy())
        except Exception:
            diagnostics.swallowed("android.ScrollViewHandler._bind_scroll_listener")

    def _wrap_in_refresh(self, sv: Any) -> Any:
        try:
            SwipeRefreshLayout = jclass("androidx.swiperefreshlayout.widget.SwipeRefreshLayout")
            srl = SwipeRefreshLayout(_ctx())
            LP = jclass("android.view.ViewGroup$LayoutParams")
            srl.addView(sv, LP(LP.MATCH_PARENT, LP.MATCH_PARENT))
            return srl
        except Exception:
            return None

    def _bind_refresh_listener(self, outer: Any) -> None:
        try:
            srl = _state_of(outer).get("refresh")

            class _RefreshProxy(
                dynamic_proxy(jclass("androidx.swiperefreshlayout.widget.SwipeRefreshLayout").OnRefreshListener)
            ):
                def onRefresh(self) -> None:
                    _fire(outer, "on_refresh")

            srl.setOnRefreshListener(_RefreshProxy())
        except Exception:
            diagnostics.swallowed("android.ScrollViewHandler._bind_refresh_listener")

    def _apply_refresh(self, outer: Any, props: Dict[str, Any]) -> None:
        srl = _state_of(outer).get("refresh")
        if srl is None:
            return
        spec = props.get("refresh_control")
        if not isinstance(spec, dict):
            try:
                srl.setEnabled(False)
            except Exception:
                diagnostics.swallowed("android.ScrollViewHandler._apply_refresh")
            return
        try:
            srl.setEnabled(True)
        except Exception:
            diagnostics.swallowed("android.ScrollViewHandler._apply_refresh")
        if spec.get("tint_color"):
            try:
                srl.setColorSchemeColors([parse_color_int(spec["tint_color"])])
            except Exception:
                diagnostics.swallowed("android.ScrollViewHandler._apply_refresh")
        try:
            srl.setRefreshing(bool(spec.get("refreshing")))
        except Exception:
            diagnostics.swallowed("android.ScrollViewHandler._apply_refresh")


class TextInputHandler(AndroidViewHandler):
    def _build(self, props: Dict[str, Any]) -> Any:
        et = jclass("android.widget.EditText")(_ctx())
        # Default to single-line so pressing Enter triggers IME_ACTION_DONE
        # (submit / dismiss) instead of inserting a newline. ``_apply``
        # overrides this when ``multiline=True``.
        try:
            if not props.get("multiline"):
                et.setSingleLine(True)
        except Exception:
            diagnostics.swallowed("android.TextInputHandler._build")
        self._bind_listeners(et, props)
        return et

    def _bind_listeners(self, et: Any, props: Dict[str, Any]) -> None:
        # Text watcher: dispatches on_change unless a programmatic
        # setText is in flight. State lookups happen at dispatch time,
        # after the registry has assigned the tag.
        try:
            TextWatcher = jclass("android.text.TextWatcher")

            class ChangeProxy(dynamic_proxy(TextWatcher)):
                def afterTextChanged(self, s: Any) -> None:
                    st = _state_of(et)
                    if st.get("suppress"):
                        return
                    _fire(et, "on_change", str(s))

                def beforeTextChanged(self, s: Any, start: int, count: int, after: int) -> None:
                    pass

                def onTextChanged(self, s: Any, start: int, before: int, count: int) -> None:
                    pass

            et.addTextChangedListener(ChangeProxy())
        except Exception:
            diagnostics.swallowed("android.TextInputHandler._bind_listeners")
        try:

            class _FocusProxy(dynamic_proxy(jclass("android.view.View").OnFocusChangeListener)):
                def onFocusChange(self, view: Any, has_focus: bool) -> None:
                    _fire(view, "on_focus" if has_focus else "on_blur")

            et.setOnFocusChangeListener(_FocusProxy())
        except Exception:
            diagnostics.swallowed("android.TextInputHandler._bind_listeners")

    def _apply(self, et: Any, props: Dict[str, Any], initial: bool) -> None:
        state = _state_of(et)
        if "value" in props:
            incoming = str(props["value"]) if props["value"] is not None else ""
            try:
                before = str(et.getText())
            except Exception:
                before = "<unavailable>"
            if before != incoming:
                selection_start = len(incoming)
                selection_end = len(incoming)
                try:
                    selection_start = et.getSelectionStart()
                    selection_end = et.getSelectionEnd()
                except Exception:
                    diagnostics.swallowed("android.TextInputHandler._apply")
                state["suppress"] = True
                try:
                    et.setText(incoming)
                    try:
                        max_pos = len(incoming)
                        start = max(0, min(int(selection_start), max_pos))
                        end = max(0, min(int(selection_end), max_pos))
                        if start == end:
                            et.setSelection(start)
                        else:
                            et.setSelection(start, end)
                    except Exception:
                        diagnostics.swallowed("android.TextInputHandler._apply")
                finally:
                    state["suppress"] = False
        if "placeholder" in props:
            et.setHint(str(props["placeholder"]) if props["placeholder"] is not None else "")
        if "placeholder_color" in props and props["placeholder_color"] is not None:
            try:
                et.setHintTextColor(parse_color_int(props["placeholder_color"]))
            except Exception:
                diagnostics.swallowed("android.TextInputHandler._apply")
        if "font_size" in props and props["font_size"] is not None:
            et.setTextSize(float(props["font_size"]))
        if "color" in props and props["color"] is not None:
            et.setTextColor(parse_color_int(props["color"]))
        if any(k in props for k in ("multiline", "secure", "keyboard_type", "auto_capitalize")):
            merged = state.get("props") or props
            try:
                InputType = jclass("android.text.InputType")
                base = InputType.TYPE_CLASS_TEXT
                if merged.get("secure"):
                    base = InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD
                else:
                    kt = merged.get("keyboard_type")
                    if kt == "email_address":
                        base = InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS
                    elif kt == "number_pad" or kt == "decimal_pad":
                        base = InputType.TYPE_CLASS_NUMBER
                        if kt == "decimal_pad":
                            base |= InputType.TYPE_NUMBER_FLAG_DECIMAL
                    elif kt == "phone_pad":
                        base = InputType.TYPE_CLASS_PHONE
                    elif kt == "url":
                        base = InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI
                    auto_cap = merged.get("auto_capitalize")
                    if auto_cap == "sentences":
                        base |= InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
                    elif auto_cap == "words":
                        base |= InputType.TYPE_TEXT_FLAG_CAP_WORDS
                    elif auto_cap == "characters":
                        base |= InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS
                if merged.get("multiline"):
                    base |= InputType.TYPE_TEXT_FLAG_MULTI_LINE
                    et.setSingleLine(False)
                else:
                    et.setSingleLine(True)
                et.setInputType(base)
            except Exception:
                diagnostics.swallowed("android.TextInputHandler._apply")
        if "max_length" in props and props["max_length"] is not None:
            try:
                InputFilter = jclass("android.text.InputFilter$LengthFilter")
                et.setFilters([InputFilter(int(props["max_length"]))])
            except Exception:
                diagnostics.swallowed("android.TextInputHandler._apply")
        if "auto_focus" in props and props["auto_focus"]:
            try:
                et.requestFocus()
            except Exception:
                diagnostics.swallowed("android.TextInputHandler._apply")
        if "editable" in props:
            # ``editable`` is only present when ``False`` (read-only); a
            # removal (``None``) restores editing. We keep the field
            # visible (not greyed) by toggling focusability rather than
            # ``setEnabled``.
            editable = props["editable"] is not False
            try:
                et.setFocusable(editable)
                et.setFocusableInTouchMode(editable)
                et.setCursorVisible(editable)
                et.setLongClickable(editable)
            except Exception:
                diagnostics.swallowed("android.TextInputHandler._apply")
        if "selection_color" in props and props["selection_color"] is not None:
            try:
                et.setHighlightColor(parse_color_int(props["selection_color"]))
            except Exception:
                diagnostics.swallowed("android.TextInputHandler._apply")
        if "text_content_type" in props and props["text_content_type"] is not None:
            self._apply_autofill(et, str(props["text_content_type"]))
        if "clear_button" in props:
            self._apply_clear_button(et, bool(props.get("clear_button")))
        if "return_key_type" in props and props["return_key_type"] is not None:
            # Map the cross-platform ``return_key_type`` to Android's
            # ``EditorInfo.IME_ACTION_*`` so the soft keyboard renders the
            # right action key. iOS has a richer set (Google / Yahoo /
            # Join / Route) with no direct AOSP equivalents; fall back
            # to ``IME_ACTION_DONE`` for those.
            try:
                EditorInfo = jclass("android.view.inputmethod.EditorInfo")
                rkt_mapping = {
                    "default": EditorInfo.IME_ACTION_UNSPECIFIED,
                    "go": EditorInfo.IME_ACTION_GO,
                    "google": EditorInfo.IME_ACTION_DONE,
                    "join": EditorInfo.IME_ACTION_DONE,
                    "next": EditorInfo.IME_ACTION_NEXT,
                    "route": EditorInfo.IME_ACTION_DONE,
                    "search": EditorInfo.IME_ACTION_SEARCH,
                    "send": EditorInfo.IME_ACTION_SEND,
                    "yahoo": EditorInfo.IME_ACTION_DONE,
                    "done": EditorInfo.IME_ACTION_DONE,
                }
                action = rkt_mapping.get(props["return_key_type"], EditorInfo.IME_ACTION_DONE)
                et.setImeOptions(action)
            except Exception:
                diagnostics.swallowed("android.TextInputHandler._apply")
        if initial or "multiline" in props:
            self._apply_editor_action(et)
        _apply_common_visual(et, props)

    def _apply_editor_action(self, et: Any) -> None:
        """Install the IME action listener for submit + keyboard dismissal.

        Single-line inputs always dismiss the keyboard on the action
        key (matching React Native's Android default) and fire
        ``on_submit`` first. Multi-line inputs only consume the action
        when an ``on_submit`` handler exists; otherwise Enter inserts
        a newline.
        """
        try:
            EditorListener = jclass("android.widget.TextView$OnEditorActionListener")
            Context = jclass("android.content.Context")

            class SubmitProxy(dynamic_proxy(EditorListener)):
                def onEditorAction(self, view: Any, action_id: int, event: Any) -> bool:
                    merged = _state_of(view).get("props") or {}
                    multiline = bool(merged.get("multiline"))
                    has_submit = _has_event(view, "on_submit")
                    if multiline and not has_submit:
                        return False
                    if has_submit:
                        try:
                            _fire(view, "on_submit", str(view.getText()))
                        except Exception:
                            diagnostics.swallowed(
                                "android.TextInputHandler._apply_editor_action.SubmitProxy.onEditorAction"
                            )
                    if not multiline:
                        try:
                            view.clearFocus()
                            ctx = view.getContext()
                            imm = ctx.getSystemService(Context.INPUT_METHOD_SERVICE)
                            imm.hideSoftInputFromWindow(view.getWindowToken(), 0)
                        except Exception:
                            diagnostics.swallowed(
                                "android.TextInputHandler._apply_editor_action.SubmitProxy.onEditorAction"
                            )
                    return True

            et.setOnEditorActionListener(SubmitProxy())
        except Exception:
            diagnostics.swallowed("android.TextInputHandler._apply_editor_action")

    @staticmethod
    def _autofill_hint(content_type: str) -> Optional[str]:
        mapping = {
            "username": "username",
            "password": "password",
            "new_password": "newPassword",
            "email": "emailAddress",
            "email_address": "emailAddress",
            "name": "name",
            "given_name": "personGivenName",
            "family_name": "personFamilyName",
            "telephone": "phone",
            "phone": "phone",
            "phone_number": "phone",
            "postal_code": "postalCode",
            "street_address": "postalAddress",
            "credit_card_number": "creditCardNumber",
            "one_time_code": "smsOTPCode",
        }
        return mapping.get(content_type)

    def _apply_autofill(self, et: Any, content_type: str) -> None:
        # Autofill hints are an API 26+ concept; older devices ignore them.
        try:
            if jclass("android.os.Build$VERSION").SDK_INT < 26:
                return
            hint = self._autofill_hint(content_type)
            if hint:
                et.setAutofillHints([hint])
        except Exception:
            diagnostics.swallowed("android.TextInputHandler._apply_autofill")

    def _apply_clear_button(self, et: Any, enabled: bool) -> None:
        # Best-effort drawableEnd "X": shows a system clear icon and wires
        # a touch listener that clears the field when the icon is tapped.
        try:
            state = _state_of(et)
            if not enabled:
                et.setCompoundDrawablesWithIntrinsicBounds(0, 0, 0, 0)
                return
            icon_id = int(getattr(jclass("android.R$drawable"), "ic_menu_close_clear_cancel", 0))
            if icon_id:
                et.setCompoundDrawablesWithIntrinsicBounds(0, 0, icon_id, 0)
            if state.get("clear_bound"):
                return
            state["clear_bound"] = True

            class _ClearTouchProxy(dynamic_proxy(jclass("android.view.View").OnTouchListener)):
                def onTouch(self, view: Any, event: Any) -> bool:
                    try:
                        if event.getAction() == 1:  # ACTION_UP
                            drawables = view.getCompoundDrawables()
                            right = drawables[2] if drawables is not None and len(drawables) > 2 else None
                            if right is not None:
                                threshold = view.getWidth() - view.getPaddingRight() - right.getBounds().width()
                                if event.getX() >= threshold:
                                    view.setText("")
                                    return True
                    except Exception:
                        diagnostics.swallowed("android.TextInputHandler._apply_clear_button._ClearTouchProxy.onTouch")
                    return False

            et.setOnTouchListener(_ClearTouchProxy())
        except Exception:
            diagnostics.swallowed("android.TextInputHandler._apply_clear_button")


class ImageHandler(AndroidViewHandler):
    def _build(self, props: Dict[str, Any]) -> Any:
        return jclass("android.widget.ImageView")(_ctx())

    def _apply(self, iv: Any, props: Dict[str, Any], initial: bool) -> None:
        if "tint_color" in props and props["tint_color"] is not None:
            try:
                ColorStateList = jclass("android.content.res.ColorStateList")
                iv.setImageTintList(ColorStateList.valueOf(parse_color_int(props["tint_color"])))
            except Exception:
                diagnostics.swallowed("android.ImageHandler._apply")
        if "placeholder_color" in props and props["placeholder_color"] is not None:
            try:
                iv.setBackgroundColor(parse_color_int(props["placeholder_color"]))
            except Exception:
                diagnostics.swallowed("android.ImageHandler._apply")
        if "source" in props and props["source"]:
            self._load_source(iv, str(props["source"]))
        if "scale_type" in props and props["scale_type"]:
            ScaleType = jclass("android.widget.ImageView$ScaleType")
            mapping = {
                "cover": ScaleType.CENTER_CROP,
                "contain": ScaleType.FIT_CENTER,
                "stretch": ScaleType.FIT_XY,
                "center": ScaleType.CENTER,
            }
            st = mapping.get(props["scale_type"])
            if st:
                iv.setScaleType(st)
        _apply_common_visual(iv, props)

    def _load_source(self, iv: Any, source: str) -> None:
        try:
            if source.startswith("data:"):
                self._load_data_uri(iv, source)
            elif source.startswith(("http://", "https://")):
                from ..images import fetch

                state = _state_of(iv)
                state["pending_uri"] = source

                def _on_ready(path: str) -> None:
                    if _state_of(iv).get("pending_uri") != source:
                        return  # a newer source superseded this load
                    bitmap = self._decode_downsampled(iv, path)
                    if bitmap is None:
                        _fire(iv, "on_error", "decode failed")
                        return
                    try:
                        iv.setImageBitmap(bitmap)
                        _fire(iv, "on_load")
                    except Exception:
                        diagnostics.swallowed("android.ImageHandler._load_source._on_ready")

                def _on_error(message: str) -> None:
                    if _state_of(iv).get("pending_uri") == source:
                        _fire(iv, "on_error", message)

                fetch(source, _on_ready, _on_error)
            elif source.startswith("/"):
                bitmap = self._decode_downsampled(iv, source)
                if bitmap is not None:
                    iv.setImageBitmap(bitmap)
                    _fire(iv, "on_load")
                else:
                    _fire(iv, "on_error", "decode failed")
            else:
                ctx = _ctx()
                res = ctx.getResources()
                pkg = ctx.getPackageName()
                res_name = source.rsplit(".", 1)[0] if "." in source else source
                res_id = res.getIdentifier(res_name, "drawable", pkg)
                if res_id != 0:
                    iv.setImageResource(res_id)
                    _fire(iv, "on_load")
                else:
                    _fire(iv, "on_error", f"drawable {res_name!r} not found")
        except Exception:
            diagnostics.swallowed("android.ImageHandler._load_source")

    def _load_data_uri(self, iv: Any, source: str) -> None:
        """Decode an inline ``data:`` URI (base64 payload) into the view."""
        try:
            import base64

            payload = source.split(",", 1)[1] if "," in source else ""
            raw = base64.b64decode(payload)
            BitmapFactory = jclass("android.graphics.BitmapFactory")
            bitmap = BitmapFactory.decodeByteArray(raw, 0, len(raw))
            if bitmap is not None:
                iv.setImageBitmap(bitmap)
                _fire(iv, "on_load")
            else:
                _fire(iv, "on_error", "data URI decode failed")
        except Exception:
            _fire(iv, "on_error", "data URI decode failed")

    def _decode_downsampled(self, iv: Any, path: str) -> Any:
        """Decode ``path`` with ``inSampleSize`` sized to the target view.

        A 4000px photo displayed in a 200dp thumbnail should not hold a
        48 MB bitmap; ``inSampleSize`` decodes at the nearest power-of-2
        fraction that still covers the view (falling back to the screen
        width when the view hasn't been laid out yet).
        """
        try:
            BitmapFactory = jclass("android.graphics.BitmapFactory")
            Options = jclass("android.graphics.BitmapFactory$Options")

            bounds = Options()
            bounds.inJustDecodeBounds = True
            BitmapFactory.decodeFile(path, bounds)
            src_w = int(bounds.outWidth)
            src_h = int(bounds.outHeight)
            if src_w <= 0 or src_h <= 0:
                return None

            target_w = 0
            target_h = 0
            try:
                target_w = int(iv.getWidth())
                target_h = int(iv.getHeight())
            except Exception:
                diagnostics.swallowed("android.ImageHandler._decode_downsampled")
            if target_w <= 0:
                try:
                    metrics = _ctx().getResources().getDisplayMetrics()
                    target_w = int(metrics.widthPixels)
                    target_h = int(metrics.heightPixels)
                except Exception:
                    target_w, target_h = src_w, src_h
            if target_h <= 0:
                target_h = target_w

            sample = 1
            while (src_w // (sample * 2)) >= target_w and (src_h // (sample * 2)) >= target_h:
                sample *= 2

            opts = Options()
            opts.inSampleSize = sample
            return BitmapFactory.decodeFile(path, opts)
        except Exception:
            return None


class SwitchHandler(AndroidViewHandler):
    def _build(self, props: Dict[str, Any]) -> Any:
        sw = jclass("android.widget.Switch")(_ctx())

        class CheckedProxy(dynamic_proxy(jclass("android.widget.CompoundButton").OnCheckedChangeListener)):
            def onCheckedChanged(self, button: Any, checked: bool) -> None:
                if _state_of(button).get("suppress"):
                    return
                _fire(button, "on_change", bool(checked))

        sw.setOnCheckedChangeListener(CheckedProxy())
        return sw

    def _apply(self, sw: Any, props: Dict[str, Any], initial: bool) -> None:
        if "value" in props:
            state = _state_of(sw)
            state["suppress"] = True
            try:
                sw.setChecked(bool(props["value"]))
            finally:
                state["suppress"] = False
        _apply_accessibility(sw, props)


class ProgressBarHandler(AndroidViewHandler):
    def _build(self, props: Dict[str, Any]) -> Any:
        style = jclass("android.R$attr").progressBarStyleHorizontal
        pb = jclass("android.widget.ProgressBar")(_ctx(), None, 0, style)
        pb.setMax(1000)
        return pb

    def _apply(self, pb: Any, props: Dict[str, Any], initial: bool) -> None:
        if "value" in props and props["value"] is not None:
            pb.setProgress(int(float(props["value"]) * 1000))
        if "color" in props and props["color"] is not None:
            try:
                ColorStateList = jclass("android.content.res.ColorStateList")
                pb.setProgressTintList(ColorStateList.valueOf(parse_color_int(props["color"])))
            except Exception:
                diagnostics.swallowed("android.ProgressBarHandler._apply")
        if "track_color" in props and props["track_color"] is not None:
            try:
                ColorStateList = jclass("android.content.res.ColorStateList")
                track = ColorStateList.valueOf(parse_color_int(props["track_color"]))
                pb.setProgressBackgroundTintList(track)
                pb.setSecondaryProgressTintList(track)
            except Exception:
                diagnostics.swallowed("android.ProgressBarHandler._apply")
        if "indeterminate" in props:
            try:
                pb.setIndeterminate(bool(props["indeterminate"]))
            except Exception:
                diagnostics.swallowed("android.ProgressBarHandler._apply")


class ActivityIndicatorHandler(AndroidViewHandler):
    def _build(self, props: Dict[str, Any]) -> Any:
        return jclass("android.widget.ProgressBar")(_ctx())

    def _apply(self, pb: Any, props: Dict[str, Any], initial: bool) -> None:
        if "animating" in props:
            View = jclass("android.view.View")
            pb.setVisibility(View.VISIBLE if props["animating"] else View.GONE)
        if "color" in props and props["color"] is not None:
            try:
                ColorStateList = jclass("android.content.res.ColorStateList")
                pb.setIndeterminateTintList(ColorStateList.valueOf(parse_color_int(props["color"])))
            except Exception:
                diagnostics.swallowed("android.ActivityIndicatorHandler._apply")
        if "size" in props and props["size"] is not None:
            # The framework ProgressBar has no runtime size switch, so
            # approximate "large" by scaling the indeterminate drawable.
            try:
                scale = 1.5 if str(props["size"]) == "large" else 1.0
                pb.setScaleX(scale)
                pb.setScaleY(scale)
            except Exception:
                diagnostics.swallowed("android.ActivityIndicatorHandler._apply")


def _make_web_client(wv: Any) -> Any:
    """Best-effort ``WebViewClient`` proxy driving the WebView events.

    ``android.webkit.WebViewClient`` is an abstract *class*, not an
    interface, so Chaquopy's ``dynamic_proxy`` may be unable to subclass
    it at runtime. We attempt it and return ``None`` on failure, in
    which case the caller falls back to the default client and page
    loading still works.

    When the proxy succeeds it fires ``on_navigation_state_change``
    (``onPageStarted``), ``on_load`` (``onPageFinished``), evaluates
    ``inject_javascript`` after each load, and bridges ``on_message``
    via a ``pythonnative://`` URL scheme plus a small JS shim installed
    as ``window.pythonnative.postMessage``.
    """
    scheme = "pythonnative://message/"
    try:

        class _WebClientProxy(dynamic_proxy(jclass("android.webkit.WebViewClient"))):
            def onPageStarted(self, view: Any, url: Any, favicon: Any) -> None:
                _fire(wv, "on_navigation_state_change", str(url))

            def onPageFinished(self, view: Any, url: Any) -> None:
                _fire(wv, "on_load", str(url))
                if _has_event(wv, "on_message"):
                    try:
                        shim = (
                            "(function(){window.pythonnative=window.pythonnative||{};"
                            "window.pythonnative.postMessage=function(m){"
                            "window.location.href='" + scheme + "'+encodeURIComponent(m);};})();"
                        )
                        view.evaluateJavascript(shim, None)
                    except Exception:
                        diagnostics.swallowed("android._make_web_client._WebClientProxy.onPageFinished")
                inject_js = (_state_of(wv).get("props") or {}).get("inject_javascript")
                if inject_js:
                    try:
                        view.evaluateJavascript(str(inject_js), None)
                    except Exception:
                        diagnostics.swallowed("android._make_web_client._WebClientProxy.onPageFinished")

            def shouldOverrideUrlLoading(self, view: Any, request: Any) -> bool:
                try:
                    url = request if isinstance(request, str) else str(request.getUrl())
                except Exception:
                    url = ""
                if url.startswith(scheme):
                    try:
                        from urllib.parse import unquote

                        _fire(wv, "on_message", unquote(url[len(scheme) :]))
                    except Exception:
                        diagnostics.swallowed("android._make_web_client._WebClientProxy.shouldOverrideUrlLoading")
                    return True
                return False

        return _WebClientProxy()
    except Exception:
        return None


class WebViewHandler(AndroidViewHandler):
    def _build(self, props: Dict[str, Any]) -> Any:
        return jclass("android.webkit.WebView")(_ctx())

    def _apply(self, wv: Any, props: Dict[str, Any], initial: bool) -> None:
        merged = _state_of(wv).get("props") or props
        needs_js = bool(merged.get("inject_javascript")) or bool(event_names(merged))
        if needs_js:
            try:
                wv.getSettings().setJavaScriptEnabled(True)
            except Exception:
                diagnostics.swallowed("android.WebViewHandler._apply")

        if initial:
            client = _make_web_client(wv)
            if client is not None:
                try:
                    wv.setWebViewClient(client)
                except Exception:
                    diagnostics.swallowed("android.WebViewHandler._apply")

        # ``html`` takes precedence over ``url`` when both are present.
        if "html" in props and props["html"]:
            try:
                wv.loadDataWithBaseURL(None, str(props["html"]), "text/html", "utf-8", None)
            except Exception:
                diagnostics.swallowed("android.WebViewHandler._apply")
        elif "url" in props and props["url"]:
            try:
                wv.loadUrl(str(props["url"]))
            except Exception:
                diagnostics.swallowed("android.WebViewHandler._apply")

        if "scroll_enabled" in props:
            self._apply_scroll_enabled(wv, props["scroll_enabled"])

    def _apply_scroll_enabled(self, wv: Any, scroll_enabled: Any) -> None:
        try:
            if scroll_enabled is False:

                class _NoScrollProxy(dynamic_proxy(jclass("android.view.View").OnTouchListener)):
                    def onTouch(self, view: Any, event: Any) -> bool:
                        return event.getAction() == 2  # consume ACTION_MOVE

                wv.setOnTouchListener(_NoScrollProxy())
            else:
                wv.setOnTouchListener(None)
        except Exception:
            diagnostics.swallowed("android.WebViewHandler._apply_scroll_enabled")


class SpacerHandler(AndroidViewHandler):
    """Empty layout placeholder used as a flexible gap.

    All sizing semantics live in the layout engine; ``Spacer``
    behaves identically to a `View` with the same style props (e.g.,
    ``flex: 1`` for an expanding spacer, ``size`` for a fixed gap).
    """

    def _build(self, props: Dict[str, Any]) -> Any:
        return jclass("android.view.View")(_ctx())

    def _apply(self, view: Any, props: Dict[str, Any], initial: bool) -> None:
        pass


class SafeAreaViewHandler(FlexContainerHandler):
    """Safe-area container using FrameLayout with ``fitsSystemWindows``."""

    def _build(self, props: Dict[str, Any]) -> Any:
        fl = _new_container()
        fl.setFitsSystemWindows(True)
        return fl


# ======================================================================
# Modal: actually presents a Dialog with the children inside
# ======================================================================


class ModalHandler(AndroidViewHandler):
    """Real modal presentation backed by an Android `Dialog`.

    The on-tree placeholder is a hidden ``View`` (so the layout
    engine can ignore it). When ``visible`` flips to ``True``, a
    ``Dialog`` is created with a ``FrameLayout`` as its content view;
    the reconciler's ``insert_child`` calls are forwarded into that
    content view.
    """

    def _build(self, props: Dict[str, Any]) -> Any:
        placeholder = jclass("android.view.View")(_ctx())
        placeholder.setVisibility(jclass("android.view.View").GONE)
        return placeholder

    def _apply(self, placeholder: Any, props: Dict[str, Any], initial: bool) -> None:
        state = _state_of(placeholder)
        # ``update`` only delivers the *changed* props. When ``visible`` is
        # not among them the presentation state must be left untouched: a
        # re-render that happens while the modal is open (e.g. an
        # ``on_show`` callback bumping some state) must NOT be read as
        # ``visible=False`` and tear the dialog down.
        if "visible" in props:
            visible = bool(props["visible"])
            if visible and state.get("dialog") is None:
                self._present(placeholder, state)
            elif not visible and state.get("dialog") is not None:
                self._dismiss(placeholder, state)
        dialog = state.get("dialog")
        if dialog is not None and "dismiss_on_backdrop" in props:
            try:
                dialog.setCanceledOnTouchOutside(props["dismiss_on_backdrop"] is not False)
            except Exception:
                diagnostics.swallowed("android.ModalHandler._apply")

    def insert_child(self, parent: Any, child: Any, index: int) -> None:
        state = _state_of(parent)
        content = state.get("content_view")
        if content is not None:
            _insert_view(content, child, index)
        else:
            state.setdefault("pending", []).insert(index, child)

    def remove_child(self, parent: Any, child: Any) -> None:
        state = _state_of(parent)
        content = state.get("content_view")
        if content is not None:
            try:
                content.removeView(child)
            except Exception:
                diagnostics.swallowed("android.ModalHandler.remove_child")
        else:
            buf = state.get("pending")
            if buf and child in buf:
                buf.remove(child)

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        return

    def _teardown(self, placeholder: Any) -> None:
        state = _state_of(placeholder)
        if state.get("dialog") is not None:
            self._dismiss(placeholder, state)

    def _present(self, placeholder: Any, state: Dict[str, Any]) -> None:
        try:
            props = state.get("props") or {}
            Dialog = jclass("android.app.Dialog")
            FrameLayout = jclass("android.widget.FrameLayout")
            LayoutParams = jclass("android.view.ViewGroup$LayoutParams")
            dialog = Dialog(_ctx())
            content = FrameLayout(_ctx())
            # ``overlay`` (or ``transparent``) keeps the dialog see-through
            # with a dimmed backdrop so children float over the host UI;
            # every other presentation style is the opaque, fullscreen-ish
            # sheet. The content stays MATCH_PARENT either way so the layout
            # engine keeps positioning children by absolute frame.
            presentation = props.get("presentation_style", "page_sheet")
            is_overlay = presentation == "overlay" or bool(props.get("transparent"))
            content.setBackgroundColor(parse_color_int("#00FFFFFF" if is_overlay else "#FFFFFF"))
            dialog.setContentView(
                content,
                LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT),
            )
            try:
                window = dialog.getWindow()
                if window is not None:
                    if is_overlay:
                        ColorDrawable = jclass("android.graphics.drawable.ColorDrawable")
                        window.setBackgroundDrawable(ColorDrawable(parse_color_int("#00000000")))
                        window.setDimAmount(0.5)
                    else:
                        WMLP = jclass("android.view.WindowManager$LayoutParams")
                        window.setLayout(WMLP.MATCH_PARENT, WMLP.MATCH_PARENT)
            except Exception:
                diagnostics.swallowed("android.ModalHandler._present")
            try:
                dialog.setCanceledOnTouchOutside(props.get("dismiss_on_backdrop") is not False)
            except Exception:
                diagnostics.swallowed("android.ModalHandler._present")
            state["dialog"] = dialog
            state["content_view"] = content
            for child in state.pop("pending", []):
                try:
                    content.addView(child)
                except Exception:
                    diagnostics.swallowed("android.ModalHandler._present")

            OnShowListener = jclass("android.content.DialogInterface$OnShowListener")

            class _ShowProxy(dynamic_proxy(OnShowListener)):
                def onShow(self, di: Any) -> None:
                    _fire(placeholder, "on_show")

            dialog.setOnShowListener(_ShowProxy())

            OnDismissListener = jclass("android.content.DialogInterface$OnDismissListener")

            class _DismissProxy(dynamic_proxy(OnDismissListener)):
                def onDismiss(self, di: Any) -> None:
                    _fire(placeholder, "on_dismiss")

            dialog.setOnDismissListener(_DismissProxy())
            dialog.show()
        except Exception:
            diagnostics.swallowed("android.ModalHandler._present")

    def _dismiss(self, placeholder: Any, state: Dict[str, Any]) -> None:
        dialog = state.pop("dialog", None)
        state.pop("content_view", None)
        if dialog is not None:
            try:
                dialog.dismiss()
            except Exception:
                diagnostics.swallowed("android.ModalHandler._dismiss")


# ======================================================================
# Portal: floats its children over the screen in a top-level overlay
# ======================================================================


class PortalHandler(AndroidViewHandler):
    """Overlay container hosting [`Portal`][pythonnative.Portal] children.

    The portal's native view is a full-size, non-clickable
    ``FrameLayout`` added directly to the screen's fragment container
    (the same parent as the screen root, so portal coordinates equal
    viewport coordinates). It is appended last, which stacks it above
    the main content; because the overlay itself never consumes
    touches, taps on empty areas fall through to the screen below
    while the portal's own children stay interactive.

    The overlay attaches lazily on the first child insert and re-homes
    itself if the fragment container was rebuilt (e.g. after popping
    back to a previously mounted screen).
    """

    def _build(self, props: Dict[str, Any]) -> Any:
        overlay = jclass("android.widget.FrameLayout")(_ctx())
        overlay.setClickable(False)
        return overlay

    def _apply(self, overlay: Any, props: Dict[str, Any], initial: bool) -> None:
        _apply_common_visual(overlay, props)
        if not initial:
            self._ensure_attached(overlay)

    def _ensure_attached(self, overlay: Any) -> None:
        try:
            from ..utils import get_android_fragment_container

            container = get_android_fragment_container()
        except Exception:
            return
        try:
            parent = overlay.getParent()
            if parent is not None and _java_id(parent) == _java_id(container):
                overlay.bringToFront()
                return
            if parent is not None:
                parent.removeView(overlay)
            LayoutParams = jclass("android.view.ViewGroup$LayoutParams")
            lp = LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT)
            container.addView(overlay, lp)
        except Exception:
            diagnostics.swallowed("android.PortalHandler._ensure_attached")

    def insert_child(self, parent: Any, child: Any, index: int) -> None:
        self._ensure_attached(parent)
        _insert_view(parent, child, index)

    def remove_child(self, parent: Any, child: Any) -> None:
        try:
            parent.removeView(child)
        except Exception:
            diagnostics.swallowed("android.PortalHandler.remove_child")

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        # The overlay fills its container via MATCH_PARENT layout params;
        # the engine frames only the portal's children.
        return

    def _teardown(self, overlay: Any) -> None:
        try:
            parent = overlay.getParent()
            if parent is not None:
                parent.removeView(overlay)
        except Exception:
            diagnostics.swallowed("android.PortalHandler._teardown")


class SliderHandler(AndroidViewHandler):
    def _build(self, props: Dict[str, Any]) -> Any:
        sb = jclass("android.widget.SeekBar")(_ctx())
        sb.setMax(1000)

        class SeekProxy(dynamic_proxy(jclass("android.widget.SeekBar").OnSeekBarChangeListener)):
            def onProgressChanged(self, seekBar: Any, progress: int, fromUser: bool) -> None:
                if not fromUser:
                    return
                merged = _state_of(seekBar).get("props") or {}
                mn = float(merged.get("min_value", 0))
                mx = float(merged.get("max_value", 1))
                rng = mx - mn if mx != mn else 1
                _fire(seekBar, "on_change", mn + (progress / 1000.0) * rng)

            def onStartTrackingTouch(self, seekBar: Any) -> None:
                pass

            def onStopTrackingTouch(self, seekBar: Any) -> None:
                pass

        sb.setOnSeekBarChangeListener(SeekProxy())
        return sb

    def _apply(self, sb: Any, props: Dict[str, Any], initial: bool) -> None:
        merged = _state_of(sb).get("props") or props
        min_val = float(merged.get("min_value", 0))
        max_val = float(merged.get("max_value", 1))
        rng = max_val - min_val if max_val != min_val else 1
        if "value" in props and props["value"] is not None:
            normalized = (float(props["value"]) - min_val) / rng
            sb.setProgress(int(normalized * 1000))
        _apply_accessibility(sb, props)


class TabBarHandler(AndroidViewHandler):
    """Native tab bar using ``BottomNavigationView`` from Material Components.

    Falls back to a horizontal ``LinearLayout`` with ``Button`` children
    when Material Components is unavailable.
    """

    _LABEL_VISIBILITY_LABELED = 1

    def _build(self, props: Dict[str, Any]) -> Any:
        try:
            bnv = jclass("com.google.android.material.bottomnavigation.BottomNavigationView")(_ctx())
            bnv.setBackgroundColor(parse_color_int("#FFFFFF"))
            try:
                bnv.setLabelVisibilityMode(self._LABEL_VISIBILITY_LABELED)
            except Exception:
                diagnostics.swallowed("android.TabBarHandler._build")
            return bnv
        except Exception:
            LinearLayout = jclass("android.widget.LinearLayout")
            ll = LinearLayout(_ctx())
            ll.setOrientation(LinearLayout.HORIZONTAL)
            ll.setBackgroundColor(parse_color_int("#F8F8F8"))
            return ll

    def create(self, tag: int, props: Dict[str, Any]) -> Any:
        view = super().create(tag, props)
        state = _state_of(view)
        state["is_material"] = "LinearLayout" not in str(type(view))
        try:
            state["is_material"] = bool(view.getMenu() is not None)
        except Exception:
            state["is_material"] = False
        if state["is_material"]:
            self._bind_material_listener(view)
        # Re-run the items now that we know which flavor we hold.
        self._apply(view, props, initial=True)
        return view

    def _apply(self, view: Any, props: Dict[str, Any], initial: bool) -> None:
        state = _state_of(view)
        if "is_material" not in state:
            return  # create() re-invokes once flavor detection is done.
        if state.get("is_material"):
            if "items" in props:
                self._set_menu(view, props["items"] or [])
            if "active_tab" in props:
                items = (state.get("props") or {}).get("items") or []
                self._set_active(view, props["active_tab"], items)
        else:
            self._apply_fallback(view, props)

    def _bind_material_listener(self, bnv: Any) -> None:
        try:
            listener_cls = jclass("com.google.android.material.navigation.NavigationBarView$OnItemSelectedListener")

            class _TabSelectProxy(dynamic_proxy(listener_cls)):
                def onNavigationItemSelected(self, menu_item: Any) -> bool:
                    idx = menu_item.getItemId()
                    items = (_state_of(bnv).get("props") or {}).get("items") or []
                    if 0 <= idx < len(items):
                        _fire(bnv, "on_tab_select", items[idx].get("name", ""))
                    return True

            bnv.setOnItemSelectedListener(_TabSelectProxy())
        except Exception:
            diagnostics.swallowed("android.TabBarHandler._bind_material_listener")

    def _set_menu(self, bnv: Any, items: list) -> None:
        try:
            menu = bnv.getMenu()
            menu.clear()
            for i, item in enumerate(items):
                title = item.get("title", item.get("name", ""))
                menu_item = menu.add(0, i, i, str(title))
                res_id = self._resolve_icon(item.get("icon"))
                if res_id:
                    try:
                        menu_item.setIcon(res_id)
                    except Exception:
                        diagnostics.swallowed("android.TabBarHandler._set_menu")
        except Exception:
            diagnostics.swallowed("android.TabBarHandler._set_menu")

    def _resolve_icon(self, icon: Any) -> int:
        """Resolve a tab icon spec to an `android.R.drawable.*` res id.

        Accepts a bare string (treated as the drawable's field name on
        ``android.R.drawable``) or a dict of the form
        ``{"ios": "...", "android": "ic_menu_home"}``. Returns ``0``
        when the icon can't be resolved, which the caller treats as
        "no icon".
        """
        if icon is None:
            return 0
        name: Any = None
        if isinstance(icon, str):
            name = icon
        elif isinstance(icon, dict):
            name = icon.get("android")
        if not name:
            return 0
        try:
            RDrawable = jclass("android.R$drawable")
            res_id = getattr(RDrawable, str(name), 0)
            return int(res_id) if res_id else 0
        except Exception:
            return 0

    def _set_active(self, bnv: Any, active: Any, items: list) -> None:
        if active and items:
            for i, item in enumerate(items):
                if item.get("name") == active:
                    try:
                        bnv.setSelectedItemId(i)
                    except Exception:
                        diagnostics.swallowed("android.TabBarHandler._set_active")
                    break

    def _apply_fallback(self, ll: Any, props: Dict[str, Any]) -> None:
        merged = _state_of(ll).get("props") or props
        items = merged.get("items", []) or []
        active = merged.get("active_tab")
        if "items" in props or "active_tab" in props:
            ll.removeAllViews()
            for item in items:
                name = item.get("name", "")
                title = item.get("title", name)
                btn = jclass("android.widget.Button")(_ctx())
                btn.setText(str(title))
                btn.setEnabled(name != active)

                class _ClickProxy(dynamic_proxy(jclass("android.view.View").OnClickListener)):
                    def __init__(self, tab_name: str) -> None:
                        super().__init__()
                        self.tab_name = tab_name

                    def onClick(self, view: Any) -> None:
                        _fire(ll, "on_tab_select", self.tab_name)

                btn.setOnClickListener(_ClickProxy(name))
                ll.addView(btn)


# ======================================================================
# Pressable: visual feedback + tap callbacks + gestures
# ======================================================================


class PressableHandler(FlexContainerHandler):
    """Container that dispatches press events through one touch stream.

    A single ``OnTouchListener`` drives the entire interaction:
    ``on_press_in`` at finger-down (plus the opacity dip),
    ``on_long_press`` on a 500 ms hold, ``on_press`` on a clean
    release, and ``on_press_out`` when the finger lifts or the touch
    cancels. The same stream feeds the gesture arbiter when
    ``gestures`` are attached, so press feedback and pan/pinch
    recognition coexist on one view.
    """

    _LONG_PRESS_MS = 500
    _TAP_SLOP_DP = 12.0

    def _build(self, props: Dict[str, Any]) -> Any:
        fl = _new_container()
        fl.setClickable(True)
        fl.setFocusable(True)
        self._bind_press_stream(fl)
        return fl

    def create(self, tag: int, props: Dict[str, Any]) -> Any:
        view = super().create(tag, props)
        # Press handling owns the touch listener; gesture specs are fed
        # from inside the press stream rather than a second listener.
        _state_of(view)["gestures_bound"] = True
        return view

    def update(self, native_view: Any, changed_props: Dict[str, Any]) -> None:
        _state_of(native_view)["gestures_bound"] = True
        super().update(native_view, changed_props)

    def _bind_press_stream(self, fl: Any) -> None:
        try:
            OnTouchListener = jclass("android.view.View$OnTouchListener")
            Handler = jclass("android.os.Handler")
            Looper = jclass("android.os.Looper")
            Runnable = jclass("java.lang.Runnable")
            handler = Handler(Looper.getMainLooper())
            slop = self._TAP_SLOP_DP
            long_ms = self._LONG_PRESS_MS

            class _PressTouchProxy(dynamic_proxy(OnTouchListener)):
                def onTouch(self, view: Any, event: Any) -> bool:
                    if _pointer_events_blocked(view):
                        return False
                    state = _state_of(view)
                    _feed_motion_event(view, state, event)
                    action = int(event.getActionMasked())
                    density = _density() or 1.0
                    x_dp = float(event.getX()) / density
                    y_dp = float(event.getY()) / density
                    if action == 0:  # DOWN
                        press = {
                            "down": (x_dp, y_dp),
                            "moved": False,
                            "long_fired": False,
                            "seq": state.get("press_seq", 0) + 1,
                        }
                        state["press"] = press
                        state["press_seq"] = press["seq"]
                        _fire(view, "on_press_in")
                        merged = state.get("props") or {}
                        opacity = float(merged.get("pressed_opacity", 0.6))
                        if opacity < 1.0:
                            try:
                                view.animate().alpha(opacity).setDuration(50).start()
                            except Exception:
                                diagnostics.swallowed(
                                    "android.PressableHandler._bind_press_stream._PressTouchProxy.onTouch"
                                )
                        if _has_event(view, "on_long_press"):
                            seq = press["seq"]

                            class _LongRunnable(dynamic_proxy(Runnable)):
                                def run(self) -> None:
                                    live = _state_of(view).get("press")
                                    if live is None or live.get("seq") != seq:
                                        return
                                    if live.get("moved") or live.get("long_fired"):
                                        return
                                    live["long_fired"] = True
                                    _fire(view, "on_long_press")

                            handler.postDelayed(_LongRunnable(), long_ms)
                        return True
                    press = state.get("press")
                    if press is None:
                        return True
                    if action == 2:  # MOVE
                        dx = x_dp - press["down"][0]
                        dy = y_dp - press["down"][1]
                        if math.hypot(dx, dy) > slop:
                            press["moved"] = True
                        return True
                    if action in (1, 3):  # UP / CANCEL
                        state["press"] = None
                        _fire(view, "on_press_out")
                        try:
                            view.animate().alpha(1.0).setDuration(100).start()
                        except Exception:
                            diagnostics.swallowed(
                                "android.PressableHandler._bind_press_stream._PressTouchProxy.onTouch"
                            )
                        if action == 1 and not press["moved"] and not press["long_fired"]:
                            _fire(view, "on_press")
                        return True
                    return True

            fl.setOnTouchListener(_PressTouchProxy())
        except Exception:
            diagnostics.swallowed("android.PressableHandler._bind_press_stream")


# ======================================================================
# StatusBar: global side effect
# ======================================================================


class StatusBarHandler(AndroidViewHandler):
    """Apply status-bar background color / style on the host activity."""

    def _build(self, props: Dict[str, Any]) -> Any:
        v = jclass("android.view.View")(_ctx())
        v.setVisibility(jclass("android.view.View").GONE)
        return v

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        return

    def _apply(self, view: Any, props: Dict[str, Any], initial: bool) -> None:
        try:
            ctx = _ctx()
            window = ctx.getWindow()
            if window is None:
                return
            if "background_color" in props and props["background_color"] is not None:
                window.setStatusBarColor(parse_color_int(props["background_color"]))
            View = jclass("android.view.View")
            decor = window.getDecorView()
            if "bar_style" in props and props["bar_style"] is not None:
                # API 23+: setSystemUiVisibility with SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
                # for dark-content (light backgrounds), 0 for light-content.
                bar_style = props["bar_style"]
                flags = decor.getSystemUiVisibility()
                if bar_style in ("dark", "default"):
                    flags |= View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
                else:
                    flags &= ~View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
                decor.setSystemUiVisibility(flags)
            if "hidden" in props and props["hidden"] is not None:
                flags = decor.getSystemUiVisibility()
                if props["hidden"]:
                    flags |= View.SYSTEM_UI_FLAG_FULLSCREEN
                else:
                    flags &= ~View.SYSTEM_UI_FLAG_FULLSCREEN
                decor.setSystemUiVisibility(flags)
        except Exception as exc:
            from .. import diagnostics

            diagnostics.warn_once(f"StatusBar: could not apply props on Android: {exc!r}")


class KeyboardAvoidingViewHandler(FlexContainerHandler):
    """Vanilla container; the user-land component computes the offset."""


# ======================================================================
# Imperative Alert helper
# ======================================================================


def _present_alert(
    *,
    title: str,
    message: Optional[str],
    buttons: list,
    style: str = "alert",
    on_result: Callable[[int], None] = lambda _idx: None,
) -> None:
    """Present an AlertDialog or BottomSheet (``style='action_sheet'``).

    Safe to call from any thread; the AlertDialog work is automatically
    marshalled to the main looper via
    [`pythonnative.runtime.call_on_main_thread`][pythonnative.runtime.call_on_main_thread].
    Returns immediately; the dialog appears on the next main-loop tick.

    ``buttons`` is a list of ``{"label": str, "style":
    "default"|"cancel"|"destructive"}`` dicts (no ``on_press``).
    Exactly one ``on_result(index)`` is invoked when the user picks a
    button; a dismiss delivers ``-1``. ``on_result`` always runs on
    the Android main thread; if it needs to wake an asyncio.Future,
    use
    [`pythonnative.runtime.resolve_future`][pythonnative.runtime.resolve_future]
    to hop back onto the loop thread.
    """
    del style  # AlertDialog has no distinct action-sheet style on Android.
    from ..runtime import call_on_main_thread

    delivered = [False]

    def _deliver(index: int) -> None:
        if delivered[0]:
            return
        delivered[0] = True
        try:
            on_result(index)
        except Exception:
            diagnostics.swallowed("android._present_alert._deliver")

    def _present_on_main() -> None:
        try:
            AlertDialog = jclass("android.app.AlertDialog$Builder")
            builder = AlertDialog(_ctx())
            builder.setTitle(str(title or ""))
            if message is not None:
                builder.setMessage(str(message))
            button_specs = buttons or [{"label": "OK", "style": "default"}]

            # AlertDialog only has three slots (positive/negative/neutral).
            # Assign the first matching style class to the conventional
            # slot, then spill any leftovers into whichever slot is free.
            slot_for: dict = {}
            free_slots = ["positive", "negative", "neutral"]
            for i, spec in enumerate(button_specs):
                kind = spec.get("style", "default")
                preferred = {
                    "default": "positive",
                    "cancel": "negative",
                    "destructive": "neutral",
                }.get(kind, "positive")
                if preferred in free_slots:
                    slot_for[i] = preferred
                    free_slots.remove(preferred)
            for i, spec in enumerate(button_specs):
                if i in slot_for:
                    continue
                if not free_slots:
                    break
                slot_for[i] = free_slots.pop(0)

            OnClickListener = jclass("android.content.DialogInterface$OnClickListener")

            def make_listener(button_index: int) -> Any:
                class _Proxy(dynamic_proxy(OnClickListener)):
                    def onClick(self, dialog: Any, which: int) -> None:
                        _deliver(button_index)

                return _Proxy()

            for i, spec in enumerate(button_specs):
                slot = slot_for.get(i)
                if slot is None:
                    continue
                label = str(spec.get("label", ""))
                listener = make_listener(i)
                if slot == "positive":
                    builder.setPositiveButton(label, listener)
                elif slot == "negative":
                    builder.setNegativeButton(label, listener)
                else:
                    builder.setNeutralButton(label, listener)

            OnCancelListener = jclass("android.content.DialogInterface$OnCancelListener")

            class _CancelProxy(dynamic_proxy(OnCancelListener)):
                def onCancel(self, dialog: Any) -> None:
                    _deliver(-1)

            builder.setOnCancelListener(_CancelProxy())
            builder.show()
        except Exception:
            _deliver(-1)

    call_on_main_thread(_present_on_main)


# ======================================================================
# Picker: native dropdown / select widget
# ======================================================================


class PickerHandler(AndroidViewHandler):
    """``Picker`` element handler, native ``Spinner`` dropdown."""

    def _build(self, props: Dict[str, Any]) -> Any:
        sp = jclass("android.widget.Spinner")(_ctx())

        class _PickerListener(dynamic_proxy(jclass("android.widget.AdapterView").OnItemSelectedListener)):
            def onItemSelected(
                self,
                parent: Any,
                view: Any,  # noqa: ARG002
                position: int,
                id_: int,  # noqa: ARG002
            ) -> None:
                state = _state_of(parent)
                if state.get("suppress"):
                    return
                items = (state.get("props") or {}).get("items") or []
                if 0 <= position < len(items):
                    item = items[position]
                    v = item.get("value") if isinstance(item, dict) else item
                    _fire(parent, "on_change", v)

            def onNothingSelected(self, parent: Any) -> None:  # noqa: ARG002
                pass

        sp.setOnItemSelectedListener(_PickerListener())
        return sp

    def _apply(self, sp: Any, props: Dict[str, Any], initial: bool) -> None:
        state = _state_of(sp)
        merged = state.get("props") or props

        if "items" in props or initial:
            items = list(merged.get("items") or [])
            labels = []
            for item in items:
                if isinstance(item, dict):
                    labels.append(str(item.get("label", item.get("value", ""))))
                else:
                    labels.append(str(item))
            ArrayAdapter = jclass("android.widget.ArrayAdapter")
            R = jclass("android.R")
            adapter = ArrayAdapter(_ctx(), R.layout.simple_spinner_item, labels)
            adapter.setDropDownViewResource(R.layout.simple_spinner_dropdown_item)
            state["suppress"] = True
            try:
                sp.setAdapter(adapter)
            finally:
                state["suppress"] = False

        if "value" in props or initial:
            items = list(merged.get("items") or [])
            value = merged.get("value")
            target_index = -1
            for i, item in enumerate(items):
                v = item.get("value") if isinstance(item, dict) else item
                if v == value:
                    target_index = i
                    break
            if target_index >= 0 and sp.getSelectedItemPosition() != target_index:
                state["suppress"] = True
                try:
                    sp.setSelection(target_index, False)
                finally:
                    state["suppress"] = False


# ======================================================================
# Checkbox: native CheckBox with an optional inline label
# ======================================================================


class CheckboxHandler(AndroidViewHandler):
    """``Checkbox`` element handler, native ``CheckBox`` widget.

    Programmatic ``value`` updates are wrapped in a per-view
    "suppress" guard so pushing a new state via ``setChecked`` never
    re-fires the user's ``on_change``.
    """

    def _build(self, props: Dict[str, Any]) -> Any:
        cb = jclass("android.widget.CheckBox")(_ctx())

        class _CheckedProxy(dynamic_proxy(jclass("android.widget.CompoundButton").OnCheckedChangeListener)):
            def onCheckedChanged(self, button: Any, is_checked: bool) -> None:
                if _state_of(button).get("suppress"):
                    return
                _fire(button, "on_change", bool(is_checked))

        cb.setOnCheckedChangeListener(_CheckedProxy())
        return cb

    def _apply(self, cb: Any, props: Dict[str, Any], initial: bool) -> None:
        state = _state_of(cb)
        if "label" in props:
            cb.setText(str(props["label"]) if props["label"] is not None else "")
        if "value" in props:
            state["suppress"] = True
            try:
                cb.setChecked(bool(props["value"]))
            finally:
                state["suppress"] = False
        if "disabled" in props:
            # ``disabled`` is only present when truthy; a removal (``None``)
            # re-enables the control.
            cb.setEnabled(not bool(props["disabled"]))
        if "color" in props and props["color"] is not None:
            try:
                ColorStateList = jclass("android.content.res.ColorStateList")
                cb.setButtonTintList(ColorStateList.valueOf(parse_color_int(props["color"])))
            except Exception:
                diagnostics.swallowed("android.CheckboxHandler._apply")
        _apply_accessibility(cb, props)


# ======================================================================
# SegmentedControl: horizontal toggle row (no UISegmentedControl on AOSP)
# ======================================================================


class SegmentedControlHandler(AndroidViewHandler):
    """``SegmentedControl`` element, a horizontal row of toggle buttons.

    Android has no ``UISegmentedControl`` equivalent, so the control is
    built from a horizontal ``LinearLayout`` holding one ``Button`` per
    segment. The selected segment is filled with the ``tint_color`` (or
    a default accent); the rest are drawn outlined. The control owns
    its own subviews, so ``insert_child`` / ``remove_child`` are
    intentional no-ops.
    """

    _DEFAULT_ACCENT = "#007AFF"

    def _build(self, props: Dict[str, Any]) -> Any:
        LinearLayout = jclass("android.widget.LinearLayout")
        ll = LinearLayout(_ctx())
        ll.setOrientation(LinearLayout.HORIZONTAL)
        return ll

    def insert_child(self, parent: Any, child: Any, index: int) -> None:
        return

    def remove_child(self, parent: Any, child: Any) -> None:
        return

    def _apply(self, ll: Any, props: Dict[str, Any], initial: bool) -> None:
        state = _state_of(ll)
        merged = state.get("props") or props

        segments_changed = False
        if "segments" in props or initial:
            raw = merged.get("segments")
            new_segments = [str(s) for s in raw] if raw else []
            if initial or new_segments != state.get("segments"):
                state["segments"] = new_segments
                segments_changed = True

        if "selected_index" in props and props["selected_index"] is not None:
            state["selected_index"] = int(props["selected_index"])

        if segments_changed:
            self._rebuild(ll, state)
        else:
            self._restyle(ll, state)

        _apply_accessibility(ll, props)

    def _rebuild(self, ll: Any, state: Dict[str, Any]) -> None:
        try:
            ll.removeAllViews()
        except Exception:
            diagnostics.swallowed("android.SegmentedControlHandler._rebuild")
        state["buttons"] = []
        LL_LP = jclass("android.widget.LinearLayout$LayoutParams")
        restyle = self._restyle
        for index, label in enumerate(state.get("segments") or []):
            btn = jclass("android.widget.Button")(_ctx())
            btn.setText(str(label))
            try:
                btn.setAllCaps(False)
            except Exception:
                diagnostics.swallowed("android.SegmentedControlHandler._rebuild")
            # Equal-width segments: zero base width + weight 1, full height.
            btn.setLayoutParams(LL_LP(0, LL_LP.MATCH_PARENT, 1.0))
            enabled = (state.get("props") or {}).get("enabled") is not False
            btn.setEnabled(enabled)

            class _SegmentClickProxy(dynamic_proxy(jclass("android.view.View").OnClickListener)):
                def __init__(self, seg_index: int) -> None:
                    super().__init__()
                    self._seg_index = seg_index

                def onClick(self, view: Any) -> None:
                    st = _state_of(ll)
                    if (st.get("props") or {}).get("enabled") is False:
                        return
                    st["selected_index"] = self._seg_index
                    restyle(ll, st)
                    _fire(ll, "on_change", self._seg_index)

            btn.setOnClickListener(_SegmentClickProxy(index))
            ll.addView(btn)
            state["buttons"].append(btn)
        self._restyle(ll, state)

    def _restyle(self, ll: Any, state: Dict[str, Any]) -> None:
        merged = state.get("props") or {}
        accent = merged.get("tint_color") or self._DEFAULT_ACCENT
        selected = state.get("selected_index", int(merged.get("selected_index", 0) or 0))
        enabled = merged.get("enabled") is not False
        for i, btn in enumerate(state.get("buttons") or []):
            self._style_segment(btn, i == selected, accent, enabled)

    def _style_segment(self, btn: Any, selected: bool, accent: Any, enabled: bool) -> None:
        try:
            GradientDrawable = jclass("android.graphics.drawable.GradientDrawable")
            drawable = GradientDrawable()
            drawable.setCornerRadius(float(_dp(6)))
            accent_int = parse_color_int(accent)
            drawable.setStroke(_dp(1), accent_int)
            if selected:
                drawable.setColor(accent_int)
                btn.setTextColor(parse_color_int("#FFFFFF"))
            else:
                drawable.setColor(parse_color_int("#00FFFFFF"))
                btn.setTextColor(accent_int)
            btn.setBackground(drawable)
            btn.setEnabled(enabled)
        except Exception:
            diagnostics.swallowed("android.SegmentedControlHandler._style_segment")

    def measure_intrinsic(
        self,
        native_view: Any,
        max_width: float,
        max_height: float,
    ) -> Tuple[float, float]:
        # Weighted children measure to ~0 under an unspecified spec, so
        # size to the sum of the segments' natural widths instead.
        try:
            density = _density()
            View = jclass("android.view.View")
            MeasureSpec = View.MeasureSpec
            spec = MeasureSpec.makeMeasureSpec(0, MeasureSpec.UNSPECIFIED)
            count = native_view.getChildCount()
            if count == 0:
                return (0.0, 0.0)
            total_w = 0
            max_h = 0
            for i in range(count):
                child = native_view.getChildAt(i)
                child.measure(spec, spec)
                total_w += child.getMeasuredWidth()
                max_h = max(max_h, child.getMeasuredHeight())
            return (total_w / density, max_h / density)
        except Exception:
            return (0.0, 0.0)


# ======================================================================
# DatePicker: trigger button opening native date/time dialogs
# ======================================================================


class DatePickerHandler(AndroidViewHandler):
    """``DatePicker`` element, a trigger ``Button`` opening native dialogs.

    The button text reflects the current ISO ``value`` (or a
    placeholder). Tapping it opens a ``DatePickerDialog`` (``mode``
    ``"date"``), a ``TimePickerDialog`` (``"time"``), or a chained
    date→time flow (``"datetime"``). Values are parsed / formatted with
    ``java.util.Calendar`` + ``java.text.SimpleDateFormat`` using
    per-mode ISO patterns, and the confirmed value is reported through
    the ``on_change`` event.
    """

    _PATTERNS = {"date": "yyyy-MM-dd", "time": "HH:mm", "datetime": "yyyy-MM-dd'T'HH:mm"}
    _PLACEHOLDERS = {"date": "Select date", "time": "Select time", "datetime": "Select date & time"}

    def _build(self, props: Dict[str, Any]) -> Any:
        btn = jclass("android.widget.Button")(_ctx())
        try:
            btn.setAllCaps(False)
        except Exception:
            diagnostics.swallowed("android.DatePickerHandler._build")
        open_dialog = self._open_dialog

        class _DateTriggerProxy(dynamic_proxy(jclass("android.view.View").OnClickListener)):
            def onClick(self, view: Any) -> None:
                st = _state_of(view)
                if (st.get("props") or {}).get("enabled") is False:
                    return
                open_dialog(view, st)

        btn.setOnClickListener(_DateTriggerProxy())
        return btn

    def _apply(self, btn: Any, props: Dict[str, Any], initial: bool) -> None:
        state = _state_of(btn)
        if "enabled" in props:
            btn.setEnabled(props["enabled"] is not False)
        if "value" in props or "mode" in props or initial:
            self._refresh_label(btn, state)
        _apply_accessibility(btn, props)

    def _refresh_label(self, btn: Any, state: Dict[str, Any]) -> None:
        merged = state.get("props") or {}
        value = merged.get("value")
        if value:
            btn.setText(str(value))
        else:
            btn.setText(self._PLACEHOLDERS.get(str(merged.get("mode", "date")), "Select"))

    def _open_dialog(self, btn: Any, state: Dict[str, Any]) -> None:
        merged = state.get("props") or {}
        mode = str(merged.get("mode", "date"))
        cal = self._parse_to_calendar(merged.get("value"), mode)
        if mode == "time":
            self._open_time(btn, state, cal)
        elif mode == "datetime":
            self._open_date(btn, state, cal, then_time=True)
        else:
            self._open_date(btn, state, cal, then_time=False)

    def _open_date(self, btn: Any, state: Dict[str, Any], cal: Any, then_time: bool) -> None:
        Calendar = jclass("java.util.Calendar")
        DatePickerDialog = jclass("android.app.DatePickerDialog")
        commit = self._commit
        open_time = self._open_time

        class _DateSetProxy(dynamic_proxy(jclass("android.app.DatePickerDialog").OnDateSetListener)):
            def __init__(self, owner_state: Dict[str, Any], trigger: Any, base_cal: Any) -> None:
                super().__init__()
                self._owner_state = owner_state
                self._trigger = trigger
                self._cal = base_cal

            def onDateSet(self, view: Any, year: int, month: int, day: int) -> None:
                self._cal.set(Calendar.YEAR, int(year))
                self._cal.set(Calendar.MONTH, int(month))
                self._cal.set(Calendar.DAY_OF_MONTH, int(day))
                if then_time:
                    open_time(self._trigger, self._owner_state, self._cal)
                else:
                    commit(self._trigger, self._owner_state, self._cal)

        dialog = DatePickerDialog(
            _ctx(),
            _DateSetProxy(state, btn, cal),
            cal.get(Calendar.YEAR),
            cal.get(Calendar.MONTH),
            cal.get(Calendar.DAY_OF_MONTH),
        )
        self._apply_min_max(dialog, state)
        dialog.show()

    def _open_time(self, btn: Any, state: Dict[str, Any], cal: Any) -> None:
        Calendar = jclass("java.util.Calendar")
        TimePickerDialog = jclass("android.app.TimePickerDialog")
        commit = self._commit

        class _TimeSetProxy(dynamic_proxy(jclass("android.app.TimePickerDialog").OnTimeSetListener)):
            def __init__(self, owner_state: Dict[str, Any], trigger: Any, base_cal: Any) -> None:
                super().__init__()
                self._owner_state = owner_state
                self._trigger = trigger
                self._cal = base_cal

            def onTimeSet(self, view: Any, hour: int, minute: int) -> None:
                self._cal.set(Calendar.HOUR_OF_DAY, int(hour))
                self._cal.set(Calendar.MINUTE, int(minute))
                commit(self._trigger, self._owner_state, self._cal)

        dialog = TimePickerDialog(
            _ctx(),
            _TimeSetProxy(state, btn, cal),
            cal.get(Calendar.HOUR_OF_DAY),
            cal.get(Calendar.MINUTE),
            True,
        )
        dialog.show()

    def _apply_min_max(self, dialog: Any, state: Dict[str, Any]) -> None:
        try:
            merged = state.get("props") or {}
            mode = str(merged.get("mode", "date"))
            picker = dialog.getDatePicker()
            minimum = merged.get("minimum")
            maximum = merged.get("maximum")
            if minimum:
                picker.setMinDate(self._parse_to_calendar(minimum, mode).getTimeInMillis())
            if maximum:
                picker.setMaxDate(self._parse_to_calendar(maximum, mode).getTimeInMillis())
        except Exception:
            diagnostics.swallowed("android.DatePickerHandler._apply_min_max")

    def _parse_to_calendar(self, value: Any, mode: str) -> Any:
        Calendar = jclass("java.util.Calendar")
        cal = Calendar.getInstance()
        if value:
            try:
                SimpleDateFormat = jclass("java.text.SimpleDateFormat")
                Locale = jclass("java.util.Locale")
                fmt = SimpleDateFormat(self._PATTERNS.get(mode, self._PATTERNS["date"]), Locale.US)
                cal.setTime(fmt.parse(str(value)))
            except Exception:
                diagnostics.swallowed("android.DatePickerHandler._parse_to_calendar")
        return cal

    def _format_calendar(self, cal: Any, mode: str) -> str:
        SimpleDateFormat = jclass("java.text.SimpleDateFormat")
        Locale = jclass("java.util.Locale")
        fmt = SimpleDateFormat(self._PATTERNS.get(mode, self._PATTERNS["date"]), Locale.US)
        return str(fmt.format(cal.getTime()))

    def _commit(self, btn: Any, state: Dict[str, Any], cal: Any) -> None:
        merged = state.get("props") or {}
        mode = str(merged.get("mode", "date"))
        try:
            iso = self._format_calendar(cal, mode)
        except Exception:
            return
        merged["value"] = iso
        try:
            btn.setText(iso)
        except Exception:
            diagnostics.swallowed("android.DatePickerHandler._commit")
        _fire(btn, "on_change", iso)


# ======================================================================
# VirtualList — RecyclerView-backed native virtualization
# ======================================================================
#
# The heavy lifting lives in the template's ``PNVirtualListView.java``:
# Chaquopy cannot subclass abstract Java classes (RecyclerView.Adapter,
# RecyclerView.ViewHolder), so the Java side owns the adapter and view
# holders and calls back into Python through the small ``Delegate``
# interface. Each visible row hosts a nested-reconciler subtree (see
# ``pythonnative.virtual_rows``): the delegate's ``mountRow`` renders
# the row element and attaches its native root to the recycled cell
# container; ``onRowRecycled`` tears the subtree down.

# Per-list mutable state, keyed by the RecyclerView's Java identity.
# The delegate proxy closes over this dict so prop updates (new
# ``render_row``, new ``count``) take effect without re-wiring Java.
_pn_vlist_info: Dict[int, Dict[str, Any]] = {}


class VirtualListHandler(AndroidViewHandler):
    """Natively virtualized list backed by ``RecyclerView``.

    Expects props:

    - ``count``: total number of rows.
    - ``row_height``: uniform row extent in points, or
    - ``row_heights``: per-row extents (section lists interleave
      headers and items of different heights).
    - ``render_row``: ``render_row(index) -> Element`` producing one
      row's subtree. Called lazily as rows enter the viewport.
    - ``shows_scroll_indicator``: hide the scroll bar when ``False``.

    Events (dispatched by tag): ``on_row_press`` with the row index,
    ``on_scroll`` with ``{"x", "y", "extent", "range"}`` in points.

    Commands: ``scroll_to_offset`` / ``scroll_to_index`` /
    ``scroll_to_end`` / ``get_scroll_offset``.
    """

    def _build(self, props: Dict[str, Any]) -> Any:
        from ..virtual_rows import RowHostPool

        PNVirtualListView = _pn_runtime_class("PNVirtualListView")
        info: Dict[str, Any] = {
            "count": int(props.get("count", 0) or 0),
            "row_height": float(props.get("row_height", 44.0) or 44.0),
            "row_heights": props.get("row_heights"),
            "render_row": props.get("render_row"),
            "pool": RowHostPool(),
        }

        class _Delegate(dynamic_proxy(PNVirtualListView.Delegate)):
            def getCount(self) -> int:
                return int(info["count"])

            def getRowHeightDp(self, position: int) -> float:
                heights = info.get("row_heights")
                if heights and 0 <= position < len(heights):
                    return float(heights[position])
                return float(info["row_height"])

            def mountRow(self, position: int, container: Any, width_dp: float, height_dp: float) -> None:
                render_row = info.get("render_row")
                if render_row is None:
                    return
                try:
                    pool = info["pool"]
                    root = pool.bind(
                        _java_id(container),
                        lambda: render_row(int(position)),
                        float(width_dp),
                        float(height_dp),
                    )
                    if root is not None:
                        _insert_view(container, root, 0)
                        # The layout engine frames only the *descendants*
                        # of a subtree root (screen hosts normally size
                        # the root themselves), so the row root would
                        # otherwise keep the 0x0 params ``_insert_view``
                        # assigns and render as nothing. Fill the cell.
                        FrameLP = jclass("android.widget.FrameLayout$LayoutParams")
                        root.setLayoutParams(FrameLP(FrameLP.MATCH_PARENT, FrameLP.MATCH_PARENT))
                except Exception:
                    import traceback

                    traceback.print_exc()

            def onRowPress(self, position: int) -> None:
                view = info.get("view")
                if view is not None:
                    _fire(view, "on_row_press", int(position))

            def onRowRecycled(self, container: Any) -> None:
                try:
                    info["pool"].release(_java_id(container))
                except Exception:
                    diagnostics.swallowed("android.VirtualListHandler._build._Delegate.onRowRecycled")

            def onScrolled(self, offset_dp: float, extent_dp: float, range_dp: float) -> None:
                view = info.get("view")
                if view is not None:
                    _fire(
                        view,
                        "on_scroll",
                        {
                            "x": 0.0,
                            "y": float(offset_dp),
                            "extent": float(extent_dp),
                            "range": float(range_dp),
                        },
                    )

        delegate = _Delegate()
        view = PNVirtualListView(_ctx(), delegate)
        info["view"] = view
        # Keep the proxy alive: Java holds only a weak-ish reference
        # through the field, and Chaquopy proxies are collectible once
        # the Python side drops them.
        info["delegate"] = delegate
        _pn_vlist_info[_java_id(view)] = info
        return view

    def _apply(self, view: Any, props: Dict[str, Any], initial: bool) -> None:
        _apply_common_visual(view, props)
        info = _pn_vlist_info.get(_java_id(view))
        if info is None:
            return
        data_changed = False
        if "count" in props:
            info["count"] = int(props.get("count") or 0)
            data_changed = True
        if "row_height" in props and props["row_height"] is not None:
            info["row_height"] = float(props["row_height"])
            data_changed = True
        if "row_heights" in props:
            info["row_heights"] = props.get("row_heights")
            data_changed = True
        if "render_row" in props:
            info["render_row"] = props.get("render_row")
            data_changed = True
        if "shows_scroll_indicator" in props:
            show = props["shows_scroll_indicator"] is not False
            try:
                view.setVerticalScrollBarEnabled(show)
            except Exception:
                diagnostics.swallowed("android.VirtualListHandler._apply")
        if data_changed and not initial:
            try:
                view.notifyDataChanged()
            except Exception:
                diagnostics.swallowed("android.VirtualListHandler._apply")

    def _teardown(self, native_view: Any) -> None:
        info = _pn_vlist_info.pop(_java_id(native_view), None)
        if info is not None:
            info.get("pool").release_all()
            info["view"] = None

    def measure_intrinsic(
        self,
        native_view: Any,
        max_width: float,
        max_height: float,
    ) -> Tuple[float, float]:
        # Fill the available space, like a ScrollView clamped to its
        # parent. Inside an unbounded axis (nested in another scroll
        # view) collapse to 0, matching React Native's behavior for
        # nested virtualized lists.
        w = max_width if math.isfinite(max_width) else 0.0
        h = max_height if math.isfinite(max_height) else 0.0
        return (max(0.0, w), max(0.0, h))

    def command(self, native_view: Any, name: str, args: Dict[str, Any]) -> Any:
        density = _density() or 1.0
        if name == "scroll_to_offset":
            try:
                native_view.scrollToOffsetDp(
                    float(args.get("y", 0.0) or 0.0),
                    args.get("animated", True) is not False,
                )
            except Exception:
                diagnostics.swallowed("android.VirtualListHandler.command")
            return None
        if name == "scroll_to_index":
            try:
                native_view.scrollToIndex(
                    int(args.get("index", 0) or 0),
                    args.get("animated", True) is not False,
                )
            except Exception:
                diagnostics.swallowed("android.VirtualListHandler.command")
            return None
        if name == "scroll_to_end":
            info = _pn_vlist_info.get(_java_id(native_view))
            count = int(info.get("count", 0)) if info else 0
            try:
                native_view.scrollToIndex(max(0, count - 1), args.get("animated", True) is not False)
            except Exception:
                diagnostics.swallowed("android.VirtualListHandler.command")
            return None
        if name == "get_scroll_offset":
            try:
                return {
                    "x": 0.0,
                    "y": float(native_view.computeVerticalScrollOffset()) / density,
                }
            except Exception:
                return {"x": 0.0, "y": 0.0}
        return None


# ======================================================================
# Registration
# ======================================================================


def register_handlers(registry: Any) -> None:
    """Register all Android view handlers with the given registry."""
    flex = FlexContainerHandler()
    registry.register("Text", TextHandler())
    registry.register("Button", ButtonHandler())
    registry.register("Column", flex)
    registry.register("Row", flex)
    registry.register("View", flex)
    registry.register("ScrollView", ScrollViewHandler())
    registry.register("TextInput", TextInputHandler())
    registry.register("Image", ImageHandler())
    registry.register("Switch", SwitchHandler())
    registry.register("ProgressBar", ProgressBarHandler())
    registry.register("ActivityIndicator", ActivityIndicatorHandler())
    registry.register("WebView", WebViewHandler())
    registry.register("Spacer", SpacerHandler())
    registry.register("SafeAreaView", SafeAreaViewHandler())
    registry.register("Modal", ModalHandler())
    registry.register("Portal", PortalHandler())
    registry.register("Slider", SliderHandler())
    registry.register("TabBar", TabBarHandler())
    registry.register("Pressable", PressableHandler())
    registry.register("StatusBar", StatusBarHandler())
    registry.register("KeyboardAvoidingView", KeyboardAvoidingViewHandler())
    registry.register("Picker", PickerHandler())
    registry.register("Checkbox", CheckboxHandler())
    registry.register("SegmentedControl", SegmentedControlHandler())
    registry.register("DatePicker", DatePickerHandler())
    registry.register("VirtualList", VirtualListHandler())


__all__ = [
    "AndroidViewHandler",
    "FlexContainerHandler",
    "TextHandler",
    "ButtonHandler",
    "ScrollViewHandler",
    "TextInputHandler",
    "ImageHandler",
    "SwitchHandler",
    "ProgressBarHandler",
    "ActivityIndicatorHandler",
    "WebViewHandler",
    "SpacerHandler",
    "SafeAreaViewHandler",
    "ModalHandler",
    "PortalHandler",
    "SliderHandler",
    "TabBarHandler",
    "PressableHandler",
    "StatusBarHandler",
    "KeyboardAvoidingViewHandler",
    "PickerHandler",
    "CheckboxHandler",
    "SegmentedControlHandler",
    "DatePickerHandler",
    "VirtualListHandler",
    "register_handlers",
]
