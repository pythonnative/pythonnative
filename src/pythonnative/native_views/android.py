"""Android native-view handlers (Chaquopy / Java bridge).

Each handler class maps a PythonNative element type to an Android
widget, implementing view creation, property updates, child management,
and frame application. Handlers are registered with the
[`NativeViewRegistry`][pythonnative.native_views.NativeViewRegistry] by
[`register_handlers`][pythonnative.native_views.android.register_handlers].

Layout is owned by the pure-Python flex engine in
[`pythonnative.layout`][pythonnative.layout]: container handlers create
plain `FrameLayout`s, the engine computes per-child frames, and
[`set_frame`][pythonnative.native_views.android.AndroidViewHandler.set_frame]
applies those frames via per-child `MarginLayoutParams`. Handlers
therefore only deal with *visual* props — text, colors, callbacks — and
ignore everything in
[`pythonnative.layout.LAYOUT_STYLE_KEYS`][pythonnative.layout.LAYOUT_STYLE_KEYS].

This module is only imported on Android at runtime. Desktop tests
inject a mock registry via
[`set_registry`][pythonnative.native_views.set_registry] and never
trigger this import path.
"""

import math
from typing import Any, Callable, Dict, Optional, Tuple

from java import dynamic_proxy, jclass

from ..utils import get_android_context
from .base import ViewHandler, _safe_max, parse_color_int

_pn_text_input_watchers: dict = {}
_pn_text_input_callbacks: dict = {}
_pn_text_input_suppress_callbacks: dict = {}
_pn_text_input_focus_listeners: dict = {}
_pn_text_input_focus_callbacks: dict = {}
_pn_text_input_clear_touch: dict = {}
_pn_view_visual_props: dict = {}
_DRAWABLE_STYLE_KEYS = ("background_color", "border_radius", "border_width", "border_color")


# ======================================================================
# Shared helpers
# ======================================================================


def _ctx() -> Any:
    return get_android_context()


def _pn_runtime_class(class_name: str) -> Any:
    """Resolve a PythonNative Android helper class for the running app.

    The Android template's helper classes (e.g. ``PNVirtualListView``)
    live in the app's own package, which the ``pn`` CLI relocates to the
    configured ``application_id`` at build time. Deriving the package from
    the runtime ``Context`` (rather than hardcoding the template package)
    keeps these lookups correct for any app id.

    Args:
        class_name: The class name within the app package, e.g.
            ``"PNVirtualListView"`` or ``"PNVirtualListView$Delegate"``.

    Returns:
        The resolved Java class.
    """
    package = _ctx().getPackageName()
    return jclass(f"{package}.{class_name}")


def _density() -> float:
    return float(_ctx().getResources().getDisplayMetrics().density)


def _dp(value: float) -> int:
    return int(round(value * _density()))


def _apply_border(view: Any, props: Dict[str, Any]) -> None:
    """Apply border_radius / border_width / border_color via a GradientDrawable.

    Android's standard ``View`` doesn't natively support arbitrary
    rounded backgrounds; the canonical workaround is to set the
    background to a ``GradientDrawable`` (the "shape" XML primitive)
    that renders the corner radius and stroke. We preserve any
    existing ``background_color`` by re-baking it into the drawable.
    """
    has_border = any(k in props for k in ("border_radius", "border_width", "border_color"))
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
                pass
        if "border_radius" in props and props["border_radius"] is not None:
            try:
                drawable.setCornerRadius(float(_dp(float(props["border_radius"]))))
            except Exception:
                pass
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
                pass
        view.setBackground(drawable)
        try:
            drawable.invalidateSelf()
        except Exception:
            pass
        try:
            view.invalidate()
        except Exception:
            pass
    except Exception:
        pass


def _apply_shadow(view: Any, props: Dict[str, Any]) -> None:
    """Apply elevation as a Material-style shadow approximation."""
    elevation = props.get("elevation")
    if elevation is None and "shadow_radius" in props:
        elevation = props.get("shadow_radius")
    if elevation is None:
        return
    try:
        view.setElevation(float(_dp(float(elevation))))
    except Exception:
        pass


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
            pass
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
            pass


def _apply_accessibility(view: Any, props: Dict[str, Any]) -> None:
    """Apply accessibility_label / hint / accessible to a view."""
    if "accessible" in props:
        try:
            View = jclass("android.view.View")
            view.setImportantForAccessibility(
                View.IMPORTANT_FOR_ACCESSIBILITY_YES if props["accessible"] else View.IMPORTANT_FOR_ACCESSIBILITY_NO
            )
        except Exception:
            pass
    if "accessibility_label" in props:
        try:
            label = props["accessibility_label"]
            view.setContentDescription(str(label) if label is not None else None)
        except Exception:
            pass
    # Android's accessibility role / hint mostly comes through
    # AccessibilityNodeInfo — full plumbing is non-trivial. We keep
    # the API surface symmetrical with iOS but apply only the label
    # for now.


def _apply_common_visual(view: Any, props: Dict[str, Any]) -> None:
    """Apply visual properties shared across many handlers."""
    has_drawable_keys = any(k in props for k in _DRAWABLE_STYLE_KEYS)
    if has_drawable_keys:
        visual_props = dict(_pn_view_visual_props.get(id(view), {}))
        for key in _DRAWABLE_STYLE_KEYS:
            if key in props:
                visual_props[key] = props[key]
        _pn_view_visual_props[id(view)] = visual_props
        _apply_border(view, visual_props)
    if "overflow" in props:
        clip = props["overflow"] == "hidden"
        try:
            view.setClipChildren(clip)
            view.setClipToPadding(clip)
        except Exception:
            pass
    if "opacity" in props and props["opacity"] is not None:
        try:
            view.setAlpha(float(props["opacity"]))
        except Exception:
            pass
    _apply_shadow(view, props)
    _apply_transform(view, props)
    _apply_accessibility(view, props)


# ======================================================================
# Base class with shared frame/measure implementations
# ======================================================================


class AndroidViewHandler(ViewHandler):
    """Base class providing the shared `set_frame` / measure contract.

    All Android handlers go through `set_frame` to apply the layout
    engine's computed frames as `MarginLayoutParams` mutations.
    Container handlers inherit the default `add_child` /
    `remove_child` implementations; leaves leave them as no-ops.
    """

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
                    pass
            try:
                lp.leftMargin = px_x
                lp.topMargin = px_y
                lp.rightMargin = 0
                lp.bottomMargin = 0
            except Exception:
                pass
            native_view.setLayoutParams(lp)
        except Exception:
            pass

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

    def set_animated_property(
        self,
        native_view: Any,
        prop_name: str,
        value: Any,
        duration_ms: float = 0.0,
        easing: str = "linear",
    ) -> None:
        """Apply ``prop_name`` to ``native_view`` immediately or animated.

        When ``duration_ms > 0``, the change is wrapped in a
        ``ViewPropertyAnimator`` so Choreographer drives the
        per-frame interpolation.
        """
        if native_view is None:
            return
        try:
            if duration_ms > 0:
                animator = native_view.animate()
                animator.setDuration(int(duration_ms))
                if prop_name == "opacity":
                    animator.alpha(float(value))
                elif prop_name == "translate_x":
                    animator.translationX(float(_dp(float(value))))
                elif prop_name == "translate_y":
                    animator.translationY(float(_dp(float(value))))
                elif prop_name == "scale":
                    animator.scaleX(float(value))
                    animator.scaleY(float(value))
                elif prop_name == "scale_x":
                    animator.scaleX(float(value))
                elif prop_name == "scale_y":
                    animator.scaleY(float(value))
                elif prop_name == "rotate":
                    animator.rotation(float(value))
                else:
                    return
                animator.start()
                return
            # Immediate path.
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
                native_view.setBackgroundColor(parse_color_int(value))
        except Exception:
            pass


# ======================================================================
# Flex container handler (shared by Column, Row, View)
# ======================================================================


class FlexContainerHandler(AndroidViewHandler):
    """Container for flex layout — a bare `FrameLayout`.

    All flex semantics (direction, alignment, distribution, padding)
    are computed by the layout engine and applied via
    [`set_frame`][pythonnative.native_views.android.AndroidViewHandler.set_frame].
    The container itself is just a positioning surface.
    """

    def create(self, props: Dict[str, Any]) -> Any:
        fl = jclass("android.widget.FrameLayout")(_ctx())
        _apply_common_visual(fl, props)
        return fl

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        _apply_common_visual(native_view, changed)

    def add_child(self, parent: Any, child: Any) -> None:
        FrameLP = jclass("android.widget.FrameLayout$LayoutParams")
        lp = child.getLayoutParams()
        if lp is None:
            lp = FrameLP(0, 0)
            child.setLayoutParams(lp)
        parent.addView(child)

    def remove_child(self, parent: Any, child: Any) -> None:
        parent.removeView(child)

    def insert_child(self, parent: Any, child: Any, index: int) -> None:
        FrameLP = jclass("android.widget.FrameLayout$LayoutParams")
        lp = child.getLayoutParams()
        if lp is None:
            lp = FrameLP(0, 0)
            child.setLayoutParams(lp)
        parent.addView(child, index)


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


class TextHandler(AndroidViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        tv = jclass("android.widget.TextView")(_ctx())
        self._apply(tv, props)
        return tv

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _apply(self, tv: Any, props: Dict[str, Any]) -> None:
        if "text" in props:
            tv.setText(str(props["text"]) if props["text"] is not None else "")
        if "font_size" in props and props["font_size"] is not None:
            tv.setTextSize(float(props["font_size"]))
        if "color" in props and props["color"] is not None:
            tv.setTextColor(parse_color_int(props["color"]))
        if any(k in props for k in ("font_family", "font_weight", "italic", "bold")):
            try:
                Typeface = jclass("android.graphics.Typeface")
                family = props.get("font_family")
                weight = props.get("font_weight") or ("bold" if props.get("bold") else None)
                italic = bool(props.get("italic"))
                style = _typeface_for(weight, italic)
                if family:
                    base = Typeface.create(str(family), style)
                    tv.setTypeface(base)
                else:
                    tv.setTypeface(tv.getTypeface(), style)
            except Exception:
                pass
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
                size = float(props.get("font_size") or 16.0)
                tv.setLetterSpacing(float(props["letter_spacing"]) / max(size, 1.0))
            except Exception:
                pass
        if "line_height" in props and props["line_height"] is not None:
            try:
                size = float(props.get("font_size") or 16.0)
                tv.setLineSpacing(0.0, float(props["line_height"]) / max(size, 1.0))
            except Exception:
                pass
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
                pass
        _apply_common_visual(tv, props)


class ButtonHandler(AndroidViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        btn = jclass("android.widget.Button")(_ctx())
        self._apply(btn, props)
        return btn

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _apply(self, btn: Any, props: Dict[str, Any]) -> None:
        if "title" in props:
            btn.setText(str(props["title"]) if props["title"] is not None else "")
        if "font_size" in props and props["font_size"] is not None:
            btn.setTextSize(float(props["font_size"]))
        if "color" in props and props["color"] is not None:
            btn.setTextColor(parse_color_int(props["color"]))
        if "enabled" in props:
            btn.setEnabled(bool(props["enabled"]))
        if "on_click" in props:
            cb = props["on_click"]
            if cb is not None:

                class ClickProxy(dynamic_proxy(jclass("android.view.View").OnClickListener)):
                    def __init__(self, callback: Callable[[], None]) -> None:
                        super().__init__()
                        self.callback = callback

                    def onClick(self, view: Any) -> None:
                        self.callback()

                btn.setOnClickListener(ClickProxy(cb))
            else:
                btn.setOnClickListener(None)
        _apply_common_visual(btn, props)


_pn_scrollview_state: Dict[int, Dict[str, Any]] = {}


class ScrollViewHandler(AndroidViewHandler):
    """Scroll container — wraps a single child whose height is unbounded.

    Uses ``androidx.core.widget.NestedScrollView`` rather than the
    framework ``android.widget.ScrollView`` because the framework
    ScrollView always intercepts vertical gestures, even when it has
    no overflow. That breaks the common case of nesting a small
    fixed-height scroll view inside a screen-level scroll view (the
    outer steals every gesture and the inner never scrolls).
    ``NestedScrollView`` implements the standard
    ``NestedScrollingParent2`` / ``NestedScrollingChild2`` protocol so
    the outer cooperates with any nested scroll, only consuming
    leftover scroll when its child reaches its limit.

    When a ``refresh_control`` prop is provided at creation, the scroll
    view is wrapped in an ``androidx.swiperefreshlayout.widget.SwipeRefreshLayout``
    (the returned view is the wrapper, and child management forwards
    into the inner scroll view) so pull-to-refresh matches the iOS
    ``UIRefreshControl`` path. Without ``refresh_control`` the bare
    scroll view is returned unchanged.
    """

    def create(self, props: Dict[str, Any]) -> Any:
        try:
            sv = jclass("androidx.core.widget.NestedScrollView")(_ctx())
        except Exception:
            sv = jclass("android.widget.ScrollView")(_ctx())
        _apply_common_visual(sv, props)
        self._apply_scroll_props(sv, props)
        if props.get("refresh_control"):
            wrapper = self._wrap_in_refresh(sv)
            if wrapper is not None:
                _pn_scrollview_state[id(wrapper)] = {
                    "scroll": sv,
                    "refresh": wrapper,
                    "on_refresh": None,
                    "listener_bound": False,
                }
                self._apply_refresh(wrapper, props)
                return wrapper
        return sv

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        state = _pn_scrollview_state.get(id(native_view))
        scroll = state["scroll"] if state else native_view
        _apply_common_visual(scroll, changed)
        self._apply_scroll_props(scroll, changed)
        if state is not None and "refresh_control" in changed:
            self._apply_refresh(native_view, changed)

    def add_child(self, parent: Any, child: Any) -> None:
        state = _pn_scrollview_state.get(id(parent))
        target = state["scroll"] if state else parent
        target.addView(child)

    def remove_child(self, parent: Any, child: Any) -> None:
        state = _pn_scrollview_state.get(id(parent))
        target = state["scroll"] if state else parent
        target.removeView(child)

    def _apply_scroll_props(self, sv: Any, props: Dict[str, Any]) -> None:
        if "shows_scroll_indicator" in props:
            # Only present when ``False`` (hide); a removal restores bars.
            show = props["shows_scroll_indicator"] is not False
            try:
                sv.setVerticalScrollBarEnabled(show)
                sv.setHorizontalScrollBarEnabled(show)
            except Exception:
                pass
        if "bounces" in props:
            # ``bounces`` is only present when ``False``; map it to the
            # closest analogue, the over-scroll (glow) mode.
            try:
                View = jclass("android.view.View")
                mode = View.OVER_SCROLL_NEVER if props["bounces"] is False else View.OVER_SCROLL_IF_CONTENT_SCROLLS
                sv.setOverScrollMode(mode)
            except Exception:
                pass
        if "on_scroll" in props:
            self._apply_on_scroll(sv, props.get("on_scroll"))
        # ``paging_enabled`` and ``keyboard_dismiss_mode`` have no clean
        # NestedScrollView analogue, so they are intentionally skipped
        # rather than approximated poorly.

    def _apply_on_scroll(self, sv: Any, cb: Optional[Callable[[float, float], None]]) -> None:
        if cb is None:
            return
        try:
            if jclass("android.os.Build$VERSION").SDK_INT < 23:
                return
            density = _density()

            class _ScrollChangeProxy(dynamic_proxy(jclass("android.view.View").OnScrollChangeListener)):
                def __init__(self, callback: Callable[[float, float], None], dens: float) -> None:
                    super().__init__()
                    self.callback = callback
                    self.dens = dens if dens else 1.0

                def onScrollChange(
                    self,
                    v: Any,
                    scroll_x: int,
                    scroll_y: int,
                    old_x: int,
                    old_y: int,
                ) -> None:
                    try:
                        self.callback(scroll_x / self.dens, scroll_y / self.dens)
                    except Exception:
                        pass

            sv.setOnScrollChangeListener(_ScrollChangeProxy(cb, density))
        except Exception:
            pass

    def _wrap_in_refresh(self, sv: Any) -> Any:
        try:
            SwipeRefreshLayout = jclass("androidx.swiperefreshlayout.widget.SwipeRefreshLayout")
            srl = SwipeRefreshLayout(_ctx())
            LP = jclass("android.view.ViewGroup$LayoutParams")
            srl.addView(sv, LP(LP.MATCH_PARENT, LP.MATCH_PARENT))
            return srl
        except Exception:
            return None

    def _apply_refresh(self, wrapper: Any, props: Dict[str, Any]) -> None:
        state = _pn_scrollview_state.get(id(wrapper))
        if state is None:
            return
        srl = state.get("refresh")
        if srl is None:
            return
        spec = props.get("refresh_control")
        if not isinstance(spec, dict):
            try:
                srl.setEnabled(False)
            except Exception:
                pass
            return
        try:
            srl.setEnabled(True)
        except Exception:
            pass
        state["on_refresh"] = spec.get("on_refresh")
        if not state.get("listener_bound"):
            owner = state

            class _RefreshProxy(
                dynamic_proxy(jclass("androidx.swiperefreshlayout.widget.SwipeRefreshLayout").OnRefreshListener)
            ):
                def onRefresh(self) -> None:
                    callback = owner.get("on_refresh")
                    if callback is not None:
                        try:
                            callback()
                        except Exception:
                            pass

            try:
                srl.setOnRefreshListener(_RefreshProxy())
                state["listener_bound"] = True
            except Exception:
                pass
        if spec.get("tint_color"):
            try:
                srl.setColorSchemeColors([parse_color_int(spec["tint_color"])])
            except Exception:
                pass
        try:
            srl.setRefreshing(bool(spec.get("refreshing")))
        except Exception:
            pass


class TextInputHandler(AndroidViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        et = jclass("android.widget.EditText")(_ctx())
        # Default to single-line so pressing Enter triggers IME_ACTION_DONE
        # (submit / dismiss) instead of inserting a newline. The
        # ``_apply`` path will override this if ``multiline=True`` is
        # set in props. Without this, every TextInput without an
        # explicit ``multiline`` value falls back to Android's
        # multi-line default and Enter inserts ``\n``.
        try:
            if not props.get("multiline"):
                et.setSingleLine(True)
        except Exception:
            pass
        self._apply(et, props)
        return et

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _apply(self, et: Any, props: Dict[str, Any]) -> None:
        if "value" in props:
            key = id(et)
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
                    pass
                _pn_text_input_suppress_callbacks[key] = True
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
                        pass
                finally:
                    _pn_text_input_suppress_callbacks[key] = False
        if "placeholder" in props:
            et.setHint(str(props["placeholder"]) if props["placeholder"] is not None else "")
        if "placeholder_color" in props and props["placeholder_color"] is not None:
            try:
                et.setHintTextColor(parse_color_int(props["placeholder_color"]))
            except Exception:
                pass
        if "font_size" in props and props["font_size"] is not None:
            et.setTextSize(float(props["font_size"]))
        if "color" in props and props["color"] is not None:
            et.setTextColor(parse_color_int(props["color"]))
        if any(k in props for k in ("multiline", "secure", "keyboard_type", "auto_capitalize")):
            try:
                InputType = jclass("android.text.InputType")
                base = InputType.TYPE_CLASS_TEXT
                if props.get("secure"):
                    base = InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD
                else:
                    kt = props.get("keyboard_type")
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
                    auto_cap = props.get("auto_capitalize")
                    if auto_cap == "sentences":
                        base |= InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
                    elif auto_cap == "words":
                        base |= InputType.TYPE_TEXT_FLAG_CAP_WORDS
                    elif auto_cap == "characters":
                        base |= InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS
                if props.get("multiline"):
                    base |= InputType.TYPE_TEXT_FLAG_MULTI_LINE
                    et.setSingleLine(False)
                else:
                    et.setSingleLine(True)
                et.setInputType(base)
            except Exception:
                pass
        if "max_length" in props and props["max_length"] is not None:
            try:
                InputFilter = jclass("android.text.InputFilter$LengthFilter")
                et.setFilters([InputFilter(int(props["max_length"]))])
            except Exception:
                pass
        if "auto_focus" in props and props["auto_focus"]:
            try:
                et.requestFocus()
            except Exception:
                pass
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
                pass
        if "selection_color" in props and props["selection_color"] is not None:
            try:
                et.setHighlightColor(parse_color_int(props["selection_color"]))
            except Exception:
                pass
        if "text_content_type" in props and props["text_content_type"] is not None:
            self._apply_autofill(et, str(props["text_content_type"]))
        if "clear_button" in props:
            self._apply_clear_button(et, bool(props.get("clear_button")))
        if "on_focus" in props or "on_blur" in props:
            self._apply_focus_listener(et, props)
        if "on_change" in props:
            key = id(et)
            cb = props["on_change"]
            if cb is not None:
                _pn_text_input_callbacks[key] = cb
                if key not in _pn_text_input_watchers:
                    TextWatcher = jclass("android.text.TextWatcher")

                    class ChangeProxy(dynamic_proxy(TextWatcher)):
                        def __init__(self, view_key: int) -> None:
                            super().__init__()
                            self.view_key = view_key

                        def afterTextChanged(self, s: Any) -> None:
                            text = str(s)
                            if _pn_text_input_suppress_callbacks.get(self.view_key):
                                return
                            callback = _pn_text_input_callbacks.get(self.view_key)
                            if callback is None:
                                return
                            callback(text)

                        def beforeTextChanged(self, s: Any, start: int, count: int, after: int) -> None:
                            pass

                        def onTextChanged(self, s: Any, start: int, before: int, count: int) -> None:
                            pass

                    watcher = ChangeProxy(key)
                    _pn_text_input_watchers[key] = watcher
                    et.addTextChangedListener(watcher)
            else:
                _pn_text_input_callbacks[key] = None
        if "return_key_type" in props and props["return_key_type"] is not None:
            # Map the cross-platform ``return_key_type`` to Android's
            # ``EditorInfo.IME_ACTION_*`` so the soft keyboard renders the
            # right action key (Done / Go / Search / Send / Next), which
            # is what triggers the ``OnEditorActionListener`` below. iOS
            # has a richer set (Google / Yahoo / Join / Route) with no
            # direct AOSP equivalents — fall back to ``IME_ACTION_DONE``
            # for those so the keyboard at least dismisses cleanly.
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
                pass
        if not props.get("multiline"):
            # Always install an editor-action listener on single-line
            # inputs so pressing the IME action key (Done / Go / etc.)
            # *or* the Enter key on a single-line ``EditText`` dismisses
            # the soft keyboard. Without this the keyboard stays up after
            # ``inputText`` + ``pressKey: Enter`` in Maestro and on smaller
            # screens hides the rest of the layout — and matches React
            # Native's default Android behavior. ``on_submit`` (if any) is
            # fired before dismissal so the callback sees the final text.
            try:
                on_submit_cb = props.get("on_submit")
                EditorListener = jclass("android.widget.TextView$OnEditorActionListener")
                Context = jclass("android.content.Context")

                class SubmitProxy(dynamic_proxy(EditorListener)):
                    def __init__(self, callback: Optional[Callable[[str], None]]) -> None:
                        super().__init__()
                        self.callback = callback

                    def onEditorAction(self, view: Any, action_id: int, event: Any) -> bool:
                        if self.callback is not None:
                            try:
                                self.callback(str(view.getText()))
                            except Exception:
                                pass
                        try:
                            view.clearFocus()
                            ctx = view.getContext()
                            imm = ctx.getSystemService(Context.INPUT_METHOD_SERVICE)
                            imm.hideSoftInputFromWindow(view.getWindowToken(), 0)
                        except Exception:
                            pass
                        return True

                et.setOnEditorActionListener(SubmitProxy(on_submit_cb))
            except Exception:
                pass
        elif "on_submit" in props and props["on_submit"] is not None:
            # Multi-line inputs: only install the listener when an explicit
            # ``on_submit`` is provided. Enter inserts a newline by default
            # on multi-line ``EditText`` and we don't want to override that.
            try:
                cb = props["on_submit"]
                EditorListener = jclass("android.widget.TextView$OnEditorActionListener")

                class SubmitProxy(dynamic_proxy(EditorListener)):
                    def __init__(self, callback: Callable[[str], None]) -> None:
                        super().__init__()
                        self.callback = callback

                    def onEditorAction(self, view: Any, action_id: int, event: Any) -> bool:
                        try:
                            self.callback(str(view.getText()))
                        except Exception:
                            pass
                        return True

                et.setOnEditorActionListener(SubmitProxy(cb))
            except Exception:
                pass
        _apply_common_visual(et, props)

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
            pass

    def _apply_clear_button(self, et: Any, enabled: bool) -> None:
        # Best-effort drawableEnd "X": shows a system clear icon and wires
        # a touch listener that clears the field when the icon is tapped.
        try:
            if not enabled:
                et.setCompoundDrawablesWithIntrinsicBounds(0, 0, 0, 0)
                return
            icon_id = int(getattr(jclass("android.R$drawable"), "ic_menu_close_clear_cancel", 0))
            if icon_id:
                et.setCompoundDrawablesWithIntrinsicBounds(0, 0, icon_id, 0)
            key = id(et)
            if key in _pn_text_input_clear_touch:
                return

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
                        pass
                    return False

            listener = _ClearTouchProxy()
            _pn_text_input_clear_touch[key] = listener
            et.setOnTouchListener(listener)
        except Exception:
            pass

    def _apply_focus_listener(self, et: Any, props: Dict[str, Any]) -> None:
        key = id(et)
        entry = _pn_text_input_focus_callbacks.setdefault(key, {"on_focus": None, "on_blur": None})
        if "on_focus" in props:
            entry["on_focus"] = props.get("on_focus")
        if "on_blur" in props:
            entry["on_blur"] = props.get("on_blur")
        if key in _pn_text_input_focus_listeners:
            return

        class _FocusProxy(dynamic_proxy(jclass("android.view.View").OnFocusChangeListener)):
            def __init__(self, view_key: int) -> None:
                super().__init__()
                self.view_key = view_key

            def onFocusChange(self, view: Any, has_focus: bool) -> None:
                callbacks = _pn_text_input_focus_callbacks.get(self.view_key) or {}
                cb = callbacks.get("on_focus") if has_focus else callbacks.get("on_blur")
                if cb is not None:
                    try:
                        cb()
                    except Exception:
                        pass

        listener = _FocusProxy(key)
        _pn_text_input_focus_listeners[key] = listener
        et.setOnFocusChangeListener(listener)


class ImageHandler(AndroidViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        iv = jclass("android.widget.ImageView")(_ctx())
        self._apply(iv, props)
        return iv

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _apply(self, iv: Any, props: Dict[str, Any]) -> None:
        if "tint_color" in props and props["tint_color"] is not None:
            try:
                ColorStateList = jclass("android.content.res.ColorStateList")
                iv.setImageTintList(ColorStateList.valueOf(parse_color_int(props["tint_color"])))
            except Exception:
                pass
        if "source" in props and props["source"]:
            self._load_source(iv, props["source"])
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
            if source.startswith(("http://", "https://")):
                Thread = jclass("java.lang.Thread")
                Runnable = jclass("java.lang.Runnable")
                URL = jclass("java.net.URL")
                BitmapFactory = jclass("android.graphics.BitmapFactory")
                Handler = jclass("android.os.Handler")
                Looper = jclass("android.os.Looper")
                handler = Handler(Looper.getMainLooper())

                class LoadTask(dynamic_proxy(Runnable)):
                    def __init__(self, image_view: Any, url_str: str, main_handler: Any) -> None:
                        super().__init__()
                        self.image_view = image_view
                        self.url_str = url_str
                        self.main_handler = main_handler

                    def run(self) -> None:
                        try:
                            url = URL(self.url_str)
                            stream = url.openStream()
                            bitmap = BitmapFactory.decodeStream(stream)
                            stream.close()

                            class SetImage(dynamic_proxy(Runnable)):
                                def __init__(self, view: Any, bmp: Any) -> None:
                                    super().__init__()
                                    self.view = view
                                    self.bmp = bmp

                                def run(self) -> None:
                                    self.view.setImageBitmap(self.bmp)

                            self.main_handler.post(SetImage(self.image_view, bitmap))
                        except Exception:
                            pass

                Thread(LoadTask(iv, source, handler)).start()
            else:
                ctx = _ctx()
                res = ctx.getResources()
                pkg = ctx.getPackageName()
                res_name = source.rsplit(".", 1)[0] if "." in source else source
                res_id = res.getIdentifier(res_name, "drawable", pkg)
                if res_id != 0:
                    iv.setImageResource(res_id)
        except Exception:
            pass


class SwitchHandler(AndroidViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        sw = jclass("android.widget.Switch")(_ctx())
        self._apply(sw, props)
        return sw

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _apply(self, sw: Any, props: Dict[str, Any]) -> None:
        if "value" in props:
            sw.setChecked(bool(props["value"]))
        if "on_change" in props and props["on_change"] is not None:
            cb = props["on_change"]

            class CheckedProxy(dynamic_proxy(jclass("android.widget.CompoundButton").OnCheckedChangeListener)):
                def __init__(self, callback: Callable[[bool], None]) -> None:
                    super().__init__()
                    self.callback = callback

                def onCheckedChanged(self, button: Any, checked: bool) -> None:
                    self.callback(checked)

            sw.setOnCheckedChangeListener(CheckedProxy(cb))
        _apply_accessibility(sw, props)


class ProgressBarHandler(AndroidViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        style = jclass("android.R$attr").progressBarStyleHorizontal
        pb = jclass("android.widget.ProgressBar")(_ctx(), None, 0, style)
        pb.setMax(1000)
        self._apply(pb, props)
        return pb

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _apply(self, pb: Any, props: Dict[str, Any]) -> None:
        if "value" in props and props["value"] is not None:
            pb.setProgress(int(float(props["value"]) * 1000))
        if "color" in props and props["color"] is not None:
            try:
                ColorStateList = jclass("android.content.res.ColorStateList")
                pb.setProgressTintList(ColorStateList.valueOf(parse_color_int(props["color"])))
            except Exception:
                pass
        if "track_color" in props and props["track_color"] is not None:
            try:
                ColorStateList = jclass("android.content.res.ColorStateList")
                track = ColorStateList.valueOf(parse_color_int(props["track_color"]))
                pb.setProgressBackgroundTintList(track)
                pb.setSecondaryProgressTintList(track)
            except Exception:
                pass
        if "indeterminate" in props:
            try:
                pb.setIndeterminate(bool(props["indeterminate"]))
            except Exception:
                pass


class ActivityIndicatorHandler(AndroidViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        pb = jclass("android.widget.ProgressBar")(_ctx())
        self._apply(pb, props)
        return pb

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _apply(self, pb: Any, props: Dict[str, Any]) -> None:
        if "animating" in props:
            View = jclass("android.view.View")
            pb.setVisibility(View.VISIBLE if props["animating"] else View.GONE)
        if "color" in props and props["color"] is not None:
            try:
                ColorStateList = jclass("android.content.res.ColorStateList")
                pb.setIndeterminateTintList(ColorStateList.valueOf(parse_color_int(props["color"])))
            except Exception:
                pass
        if "size" in props and props["size"] is not None:
            # The framework ProgressBar has no runtime size switch, so
            # approximate "large" by scaling the indeterminate drawable.
            try:
                scale = 1.5 if str(props["size"]) == "large" else 1.0
                pb.setScaleX(scale)
                pb.setScaleY(scale)
            except Exception:
                pass


_pn_webview_props: Dict[int, Dict[str, Any]] = {}


def _make_web_client(store: Dict[str, Any]) -> Any:
    """Best-effort ``WebViewClient`` proxy driving the WebView callbacks.

    ``android.webkit.WebViewClient`` is an abstract *class*, not an
    interface, so Chaquopy's ``dynamic_proxy`` may be unable to subclass
    it at runtime. We attempt it and return ``None`` on failure, in
    which case the caller falls back to the default client and page
    loading still works.

    When the proxy succeeds it drives ``on_navigation_state_change``
    (``onPageStarted``), ``on_load`` (``onPageFinished``), evaluates
    ``inject_javascript`` after each load, and bridges ``on_message``
    via a ``pythonnative://`` URL scheme plus a small JS shim installed
    as ``window.pythonnative.postMessage`` — so no ``@JavascriptInterface``
    Java helper is required.
    """
    on_load = store.get("on_load")
    on_nav = store.get("on_navigation_state_change")
    inject_js = store.get("inject_javascript")
    on_message = store.get("on_message")
    scheme = "pythonnative://message/"
    try:

        class _WebClientProxy(dynamic_proxy(jclass("android.webkit.WebViewClient"))):
            def onPageStarted(self, view: Any, url: Any, favicon: Any) -> None:
                if on_nav is not None:
                    try:
                        on_nav(str(url))
                    except Exception:
                        pass

            def onPageFinished(self, view: Any, url: Any) -> None:
                if on_load is not None:
                    try:
                        on_load(str(url))
                    except Exception:
                        pass
                if on_message is not None:
                    try:
                        shim = (
                            "(function(){window.pythonnative=window.pythonnative||{};"
                            "window.pythonnative.postMessage=function(m){"
                            "window.location.href='" + scheme + "'+encodeURIComponent(m);};})();"
                        )
                        view.evaluateJavascript(shim, None)
                    except Exception:
                        pass
                if inject_js:
                    try:
                        view.evaluateJavascript(str(inject_js), None)
                    except Exception:
                        pass

            def shouldOverrideUrlLoading(self, view: Any, request: Any) -> bool:
                try:
                    url = request if isinstance(request, str) else str(request.getUrl())
                except Exception:
                    url = ""
                if on_message is not None and url.startswith(scheme):
                    try:
                        from urllib.parse import unquote

                        on_message(unquote(url[len(scheme) :]))
                    except Exception:
                        pass
                    return True
                return False

        return _WebClientProxy()
    except Exception:
        return None


class WebViewHandler(AndroidViewHandler):
    _CLIENT_KEYS = ("on_load", "on_navigation_state_change", "inject_javascript", "on_message")

    def create(self, props: Dict[str, Any]) -> Any:
        wv = jclass("android.webkit.WebView")(_ctx())
        _pn_webview_props[id(wv)] = {}
        self._apply(wv, props, initial=True)
        return wv

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed, initial=False)

    def _apply(self, wv: Any, props: Dict[str, Any], initial: bool) -> None:
        store = _pn_webview_props.setdefault(id(wv), {})
        for key in self._CLIENT_KEYS:
            if key in props:
                store[key] = props[key]

        # Enable JS whenever a callback / injection needs it.
        if any(store.get(k) for k in self._CLIENT_KEYS):
            try:
                wv.getSettings().setJavaScriptEnabled(True)
            except Exception:
                pass

        if initial or any(k in props for k in self._CLIENT_KEYS):
            client = _make_web_client(store)
            if client is not None:
                try:
                    wv.setWebViewClient(client)
                except Exception:
                    pass

        # ``html`` takes precedence over ``url`` when both are present.
        if "html" in props and props["html"]:
            try:
                wv.loadDataWithBaseURL(None, str(props["html"]), "text/html", "utf-8", None)
            except Exception:
                pass
        elif "url" in props and props["url"]:
            try:
                wv.loadUrl(str(props["url"]))
            except Exception:
                pass

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
            pass


class SpacerHandler(AndroidViewHandler):
    """Empty layout placeholder used as a flexible gap.

    All sizing semantics now live in the layout engine — ``Spacer``
    behaves identically to a `View` with the same style props (e.g.,
    ``flex: 1`` for an expanding spacer, ``size`` for a fixed gap).
    """

    def create(self, props: Dict[str, Any]) -> Any:
        return jclass("android.view.View")(_ctx())

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        pass


class SafeAreaViewHandler(AndroidViewHandler):
    """Safe-area container using FrameLayout with ``fitsSystemWindows``."""

    def create(self, props: Dict[str, Any]) -> Any:
        fl = jclass("android.widget.FrameLayout")(_ctx())
        fl.setFitsSystemWindows(True)
        _apply_common_visual(fl, props)
        return fl

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        _apply_common_visual(native_view, changed)

    def add_child(self, parent: Any, child: Any) -> None:
        parent.addView(child)

    def remove_child(self, parent: Any, child: Any) -> None:
        parent.removeView(child)


# ======================================================================
# Modal — actually presents a Dialog with the children inside
# ======================================================================


_pn_modal_states: Dict[int, dict] = {}
_pn_modal_pending: Dict[int, list] = {}


class ModalHandler(AndroidViewHandler):
    """Real modal presentation backed by an Android `Dialog`.

    The on-tree placeholder is a hidden ``View`` (so the layout
    engine can ignore it). When ``visible`` flips to ``True``, a
    ``Dialog`` is created with a ``FrameLayout`` as its content view;
    the reconciler's ``add_child`` calls are forwarded into that
    content view.
    """

    def create(self, props: Dict[str, Any]) -> Any:
        placeholder = jclass("android.view.View")(_ctx())
        placeholder.setVisibility(jclass("android.view.View").GONE)
        self._apply(placeholder, props, mounting=True)
        return placeholder

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed, mounting=False)

    def add_child(self, parent: Any, child: Any) -> None:
        state = _pn_modal_states.get(id(parent))
        if state and state.get("content_view") is not None:
            try:
                state["content_view"].addView(child)
            except Exception:
                pass
        else:
            _pn_modal_pending.setdefault(id(parent), []).append(child)

    def remove_child(self, parent: Any, child: Any) -> None:
        state = _pn_modal_states.get(id(parent))
        if state and state.get("content_view") is not None:
            try:
                state["content_view"].removeView(child)
            except Exception:
                pass
        else:
            buf = _pn_modal_pending.get(id(parent))
            if buf and child in buf:
                buf.remove(child)

    def insert_child(self, parent: Any, child: Any, index: int) -> None:
        state = _pn_modal_states.get(id(parent))
        if state and state.get("content_view") is not None:
            try:
                state["content_view"].addView(child, index)
            except Exception:
                pass
        else:
            _pn_modal_pending.setdefault(id(parent), []).insert(index, child)

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        return

    def _apply(self, placeholder: Any, props: Dict[str, Any], *, mounting: bool) -> None:
        state = _pn_modal_states.get(id(placeholder))
        # ``update`` only delivers the *changed* props. When ``visible`` is
        # not among them the presentation state must be left untouched: a
        # re-render that happens while the modal is open (e.g. an
        # ``on_show`` callback bumping some state) must NOT be read as
        # ``visible=False`` and tear the dialog down. So only react to an
        # explicitly supplied ``visible`` value.
        if "visible" in props:
            visible = bool(props["visible"])
            if visible and state is None:
                self._present(placeholder, props)
            elif not visible and state is not None:
                self._dismiss(placeholder)
        # Forward live prop updates to an already-presented dialog.
        state = _pn_modal_states.get(id(placeholder))
        if state is not None:
            if "on_dismiss" in props:
                state["on_dismiss"] = props.get("on_dismiss")
            dialog = state.get("dialog")
            if dialog is not None and "dismiss_on_backdrop" in props:
                try:
                    dialog.setCanceledOnTouchOutside(props["dismiss_on_backdrop"] is not False)
                except Exception:
                    pass

    def _present(self, placeholder: Any, props: Dict[str, Any]) -> None:
        try:
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
                pass
            try:
                dialog.setCanceledOnTouchOutside(props.get("dismiss_on_backdrop") is not False)
            except Exception:
                pass
            on_dismiss = props.get("on_dismiss")
            _pn_modal_states[id(placeholder)] = {
                "dialog": dialog,
                "content_view": content,
                "on_dismiss": on_dismiss,
            }
            for child in _pn_modal_pending.pop(id(placeholder), []):
                try:
                    content.addView(child)
                except Exception:
                    pass
            on_show = props.get("on_show")
            if on_show is not None:
                OnShowListener = jclass("android.content.DialogInterface$OnShowListener")

                class _ShowProxy(dynamic_proxy(OnShowListener)):
                    def __init__(self, callback: Callable[[], None]) -> None:
                        super().__init__()
                        self.callback = callback

                    def onShow(self, di: Any) -> None:
                        try:
                            self.callback()
                        except Exception:
                            pass

                dialog.setOnShowListener(_ShowProxy(on_show))
            if on_dismiss is not None:
                OnDismissListener = jclass("android.content.DialogInterface$OnDismissListener")

                class _DismissProxy(dynamic_proxy(OnDismissListener)):
                    def __init__(self, callback: Callable[[], None]) -> None:
                        super().__init__()
                        self.callback = callback

                    def onDismiss(self, di: Any) -> None:
                        try:
                            self.callback()
                        except Exception:
                            pass

                dialog.setOnDismissListener(_DismissProxy(on_dismiss))
            dialog.show()
        except Exception:
            pass

    def _dismiss(self, placeholder: Any) -> None:
        state = _pn_modal_states.pop(id(placeholder), None)
        if state is None:
            return
        dialog = state.get("dialog")
        if dialog is not None:
            try:
                dialog.dismiss()
            except Exception:
                pass


class SliderHandler(AndroidViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        sb = jclass("android.widget.SeekBar")(_ctx())
        sb.setMax(1000)
        self._apply(sb, props)
        return sb

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _apply(self, sb: Any, props: Dict[str, Any]) -> None:
        min_val = float(props.get("min_value", 0))
        max_val = float(props.get("max_value", 1))
        rng = max_val - min_val if max_val != min_val else 1
        if "value" in props:
            normalized = (float(props["value"]) - min_val) / rng
            sb.setProgress(int(normalized * 1000))
        if "on_change" in props and props["on_change"] is not None:
            cb = props["on_change"]

            class SeekProxy(dynamic_proxy(jclass("android.widget.SeekBar").OnSeekBarChangeListener)):
                def __init__(self, callback: Callable[[float], None], mn: float, rn: float) -> None:
                    super().__init__()
                    self.callback = callback
                    self.mn = mn
                    self.rn = rn

                def onProgressChanged(self, seekBar: Any, progress: int, fromUser: bool) -> None:
                    if fromUser:
                        self.callback(self.mn + (progress / 1000.0) * self.rn)

                def onStartTrackingTouch(self, seekBar: Any) -> None:
                    pass

                def onStopTrackingTouch(self, seekBar: Any) -> None:
                    pass

            sb.setOnSeekBarChangeListener(SeekProxy(cb, min_val, rng))


_android_tabbar_state: dict = {"callback": None, "items": []}


class TabBarHandler(AndroidViewHandler):
    """Native tab bar using ``BottomNavigationView`` from Material Components.

    Falls back to a horizontal ``LinearLayout`` with ``Button`` children
    when Material Components is unavailable.
    """

    _LABEL_VISIBILITY_LABELED = 1
    _is_material: bool = True

    def create(self, props: Dict[str, Any]) -> Any:
        try:
            bnv = jclass("com.google.android.material.bottomnavigation.BottomNavigationView")(_ctx())
            bnv.setBackgroundColor(parse_color_int("#FFFFFF"))
            self._configure_material_bar(bnv)
            self._is_material = True
            self._apply_full(bnv, props)
            return bnv
        except Exception:
            self._is_material = False
            return self._create_fallback(props)

    def _create_fallback(self, props: Dict[str, Any]) -> Any:
        """Horizontal LinearLayout with Button children as a tab-bar fallback."""
        LinearLayout = jclass("android.widget.LinearLayout")
        ll = LinearLayout(_ctx())
        ll.setOrientation(LinearLayout.HORIZONTAL)
        ll.setBackgroundColor(parse_color_int("#F8F8F8"))
        self._apply_fallback(ll, props)
        return ll

    def _configure_material_bar(self, bnv: Any) -> None:
        """Keep text visible for every tab, including 4+ item bars."""
        try:
            bnv.setLabelVisibilityMode(self._LABEL_VISIBILITY_LABELED)
        except Exception:
            pass

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        if self._is_material:
            self._apply_partial(native_view, changed)
        else:
            self._apply_fallback(native_view, changed)

    def _apply_full(self, bnv: Any, props: Dict[str, Any]) -> None:
        """Initial creation — all props are present."""
        items = props.get("items", [])
        self._set_menu(bnv, items)
        self._set_active(bnv, props.get("active_tab"), items)
        cb = props.get("on_tab_select")
        if cb is not None:
            self._set_listener(bnv, cb, items)

    def _apply_partial(self, bnv: Any, changed: Dict[str, Any]) -> None:
        """Reconciler update — only changed props are present."""
        prev_items = _android_tabbar_state["items"]

        if "items" in changed:
            items = changed["items"]
            self._set_menu(bnv, items)
        else:
            items = prev_items

        if "active_tab" in changed:
            self._set_active(bnv, changed["active_tab"], items)

        if "on_tab_select" in changed:
            cb = changed["on_tab_select"]
            if cb is not None:
                self._set_listener(bnv, cb, items)

    def _set_menu(self, bnv: Any, items: list) -> None:
        _android_tabbar_state["items"] = items
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
                        pass
        except Exception:
            pass

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
                        pass
                    break

    def _set_listener(self, bnv: Any, cb: Callable, items: list) -> None:
        _android_tabbar_state["callback"] = cb
        _android_tabbar_state["items"] = items
        try:
            listener_cls = jclass("com.google.android.material.navigation.NavigationBarView$OnItemSelectedListener")

            class _TabSelectProxy(dynamic_proxy(listener_cls)):
                def __init__(self, callback: Callable, tab_items: list) -> None:
                    super().__init__()
                    self.callback = callback
                    self.tab_items = tab_items

                def onNavigationItemSelected(self, menu_item: Any) -> bool:
                    idx = menu_item.getItemId()
                    if 0 <= idx < len(self.tab_items):
                        self.callback(self.tab_items[idx].get("name", ""))
                    return True

            bnv.setOnItemSelectedListener(_TabSelectProxy(cb, items))
        except Exception:
            pass

    def _apply_fallback(self, ll: Any, props: Dict[str, Any]) -> None:
        items = props.get("items", [])
        active = props.get("active_tab")
        cb = props.get("on_tab_select")
        if "items" in props:
            ll.removeAllViews()
            for item in items:
                name = item.get("name", "")
                title = item.get("title", name)
                btn = jclass("android.widget.Button")(_ctx())
                btn.setText(str(title))
                btn.setEnabled(name != active)
                if cb is not None:
                    tab_name = name

                    def _make_click(n: str) -> Callable[[], None]:
                        return lambda: cb(n)

                    class _ClickProxy(dynamic_proxy(jclass("android.view.View").OnClickListener)):
                        def __init__(self, callback: Callable[[], None]) -> None:
                            super().__init__()
                            self.callback = callback

                        def onClick(self, view: Any) -> None:
                            self.callback()

                    btn.setOnClickListener(_ClickProxy(_make_click(tab_name)))
                ll.addView(btn)


# ======================================================================
# Pressable — visual feedback + tap callbacks
# ======================================================================


class PressableHandler(AndroidViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        fl = jclass("android.widget.FrameLayout")(_ctx())
        fl.setClickable(True)
        fl.setFocusable(True)
        self._apply(fl, props)
        return fl

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _apply(self, fl: Any, props: Dict[str, Any]) -> None:
        if "on_press" in props and props["on_press"] is not None:
            cb = props["on_press"]

            class PressProxy(dynamic_proxy(jclass("android.view.View").OnClickListener)):
                def __init__(self, callback: Callable[[], None]) -> None:
                    super().__init__()
                    self.callback = callback

                def onClick(self, view: Any) -> None:
                    self.callback()

            fl.setOnClickListener(PressProxy(cb))
        if "on_long_press" in props and props["on_long_press"] is not None:
            cb = props["on_long_press"]

            class LongPressProxy(dynamic_proxy(jclass("android.view.View").OnLongClickListener)):
                def __init__(self, callback: Callable[[], None]) -> None:
                    super().__init__()
                    self.callback = callback

                def onLongClick(self, view: Any) -> bool:
                    self.callback()
                    return True

            fl.setOnLongClickListener(LongPressProxy(cb))
        # Press feedback via OnTouchListener that fades the alpha.
        if "pressed_opacity" in props or "on_press" in props:
            try:
                pressed_opacity = float(props.get("pressed_opacity", 0.6))
                OnTouchListener = jclass("android.view.View$OnTouchListener")
                MotionEvent = jclass("android.view.MotionEvent")  # noqa: F841

                class _TouchProxy(dynamic_proxy(OnTouchListener)):
                    def __init__(self, opacity: float) -> None:
                        super().__init__()
                        self.opacity = opacity

                    def onTouch(self, view: Any, event: Any) -> bool:
                        action = event.getAction()
                        if action == 0:  # ACTION_DOWN
                            view.animate().alpha(self.opacity).setDuration(50).start()
                        elif action in (1, 3):  # ACTION_UP / ACTION_CANCEL
                            view.animate().alpha(1.0).setDuration(100).start()
                        return False

                fl.setOnTouchListener(_TouchProxy(pressed_opacity))
            except Exception:
                pass
        _apply_common_visual(fl, props)

    def add_child(self, parent: Any, child: Any) -> None:
        parent.addView(child)

    def remove_child(self, parent: Any, child: Any) -> None:
        parent.removeView(child)


# ======================================================================
# StatusBar — global side effect
# ======================================================================


class StatusBarHandler(AndroidViewHandler):
    """Apply status-bar background color / style on the host activity."""

    def create(self, props: Dict[str, Any]) -> Any:
        v = jclass("android.view.View")(_ctx())
        v.setVisibility(jclass("android.view.View").GONE)
        self._apply(props)
        return v

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(changed)

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        return

    def _apply(self, props: Dict[str, Any]) -> None:
        try:
            ctx = _ctx()
            window = ctx.getWindow()
            if window is None:
                return
            if "background_color" in props and props["background_color"] is not None:
                window.setStatusBarColor(parse_color_int(props["background_color"]))
            if "bar_style" in props and props["bar_style"] is not None:
                # API 23+: setSystemUiVisibility with SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
                # for dark-content (light backgrounds), 0 for light-content.
                View = jclass("android.view.View")
                bar_style = props["bar_style"]
                decor = window.getDecorView()
                flags = decor.getSystemUiVisibility()
                if bar_style in ("dark", "default"):
                    flags |= View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
                else:
                    flags &= ~View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
                decor.setSystemUiVisibility(flags)
        except Exception:
            pass


# ======================================================================
# KeyboardAvoidingView — vanilla container; the user-land component
# computes the offset from manifest-driven insets.
# ======================================================================


class KeyboardAvoidingViewHandler(AndroidViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        fl = jclass("android.widget.FrameLayout")(_ctx())
        _apply_common_visual(fl, props)
        return fl

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        _apply_common_visual(native_view, changed)

    def add_child(self, parent: Any, child: Any) -> None:
        parent.addView(child)

    def remove_child(self, parent: Any, child: Any) -> None:
        parent.removeView(child)


# ======================================================================
# VirtualList — RecyclerView-backed virtualized list
# ======================================================================


_pn_recyclerview_state: Dict[int, Any] = {}


def _java_id(jobj: Any) -> int:
    """Return ``System.identityHashCode(jobj)`` as a stable lookup key.

    Chaquopy's ``JavaObject.__setattr__`` rejects unknown Python attributes,
    so we cannot stash custom IDs on the Java view wrapper. Instead, we use
    the JVM's identity hash code, which is stable for the lifetime of the
    Java object and the same across all Python wrappers that may proxy it.
    """
    System = jclass("java.lang.System")
    return int(System.identityHashCode(jobj))


def _make_recyclerview_delegate(props: Dict[str, Any]) -> Any:
    Delegate = _pn_runtime_class("PNVirtualListView$Delegate")

    class _Delegate(dynamic_proxy(Delegate)):
        def __init__(self, initial: Dict[str, Any]) -> None:
            super().__init__()
            self.count = int(initial.get("count", 0))
            self.row_height = float(initial.get("row_height", 44.0))
            self.mount_row = initial.get("mount_row")
            self.on_row_press = initial.get("on_row_press")

        def update(self, changed: Dict[str, Any]) -> None:
            if "count" in changed:
                self.count = int(changed["count"])
            if "row_height" in changed and changed["row_height"] is not None:
                self.row_height = float(changed["row_height"])
            if "mount_row" in changed:
                self.mount_row = changed["mount_row"]
            if "on_row_press" in changed:
                self.on_row_press = changed["on_row_press"]

        def getCount(self) -> int:
            return self.count

        def getRowHeightDp(self) -> float:
            return self.row_height

        def mountRow(self, position: int, container: Any, width_dp: float, height_dp: float) -> None:
            if self.mount_row is None:
                return
            try:
                self.mount_row(int(position), container, float(width_dp), float(height_dp))
            except Exception:
                import traceback as _tb

                _tb.print_exc()

        def onRowPress(self, position: int) -> None:
            idx = int(position)
            if idx < 0 or self.on_row_press is None:
                return
            try:
                self.on_row_press(idx)
            except Exception:
                import traceback as _tb

                _tb.print_exc()

    return _Delegate(props)


class VirtualListHandler(AndroidViewHandler):
    """Backed by ``RecyclerView`` through a tiny Android template helper.

    Chaquopy cannot proxy ``RecyclerView.Adapter`` directly because it is an
    abstract Java class, so the Android template provides
    ``PNVirtualListView``. Python implements that helper's small ``Delegate``
    interface, while Java owns the adapter/view-holder lifecycle.
    """

    def create(self, props: Dict[str, Any]) -> Any:
        try:
            PNVirtualListView = _pn_runtime_class("PNVirtualListView")
            delegate = _make_recyclerview_delegate(props)
            rv = PNVirtualListView(_ctx(), delegate)
            if "background_color" in props and props["background_color"] is not None:
                rv.setBackgroundColor(parse_color_int(props["background_color"]))
            key = _java_id(rv)
            _pn_recyclerview_state[key] = delegate
            return rv
        except Exception:
            return self._fallback(props)

    def _fallback(self, props: Dict[str, Any]) -> Any:
        """Eagerly mount all rows in a ScrollView (controller init failed).

        Sets each row's LinearLayout.LayoutParams to MATCH_PARENT × row_h_px
        so cells have a real visual size, and forwards the screen width (in
        dp) to ``mount_row`` so the layout engine can position child
        elements.
        """
        n = int(props.get("count", 0))
        row_h_dp = float(props.get("row_height", 44.0))
        density = _density()
        row_h_px = max(1, int(round(row_h_dp * density)))

        try:
            screen_w_px = float(_ctx().getResources().getDisplayMetrics().widthPixels)
            screen_w_dp = screen_w_px / density if density else screen_w_px
        except Exception:
            screen_w_dp = 0.0

        sv = jclass("android.widget.ScrollView")(_ctx())
        LinearLayout = jclass("android.widget.LinearLayout")
        LL_LP = jclass("android.widget.LinearLayout$LayoutParams")
        ll = LinearLayout(_ctx())
        ll.setOrientation(LinearLayout.VERTICAL)
        sv.addView(ll)

        mount = props.get("mount_row")

        for i in range(n):
            try:
                cell = jclass("android.widget.FrameLayout")(_ctx())
                cell.setLayoutParams(LL_LP(LL_LP.MATCH_PARENT, row_h_px))
                if mount is not None:
                    mount(i, cell, screen_w_dp, row_h_dp)
                ll.addView(cell)
            except Exception:
                continue
        return sv

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        delegate = _pn_recyclerview_state.get(_java_id(native_view))
        if delegate is None:
            return
        delegate.update(changed)
        if "background_color" in changed and changed["background_color"] is not None:
            try:
                native_view.setBackgroundColor(parse_color_int(changed["background_color"]))
            except Exception:
                pass
        try:
            native_view.notifyDataChanged()
        except Exception:
            pass


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

    Safe to call from any thread — the AlertDialog work is automatically
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
            pass

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
# Picker — native dropdown / select widget
# ======================================================================
#
# Renders the PythonNative `Picker` element as an Android ``Spinner``,
# which is the platform's standard dropdown widget. The selected item is
# pushed to the user's callback via ``OnItemSelectedListener``.


class PickerHandler(AndroidViewHandler):
    """``Picker`` element handler — native ``Spinner`` dropdown."""

    def create(self, props: Dict[str, Any]) -> Any:
        Spinner = jclass("android.widget.Spinner")
        sp = Spinner(_ctx())
        self._state: Dict[int, Dict[str, Any]] = getattr(self, "_state", {})
        self._state[id(sp)] = {"items": [], "on_change": None, "suppress": False}
        self._apply(sp, props, initial=True)
        return sp

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed, initial=False)

    def _apply(self, sp: Any, props: Dict[str, Any], initial: bool) -> None:
        state = self._state.setdefault(id(sp), {"items": [], "on_change": None, "suppress": False})

        if "items" in props or initial:
            items = list(props.get("items") or state.get("items") or [])
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
            sp.setAdapter(adapter)
            state["suppress"] = False
            state["items"] = items

        if "value" in props or initial:
            items = state["items"]
            value = props.get("value") if "value" in props else None
            target_index = -1
            for i, item in enumerate(items):
                v = item.get("value") if isinstance(item, dict) else item
                if v == value:
                    target_index = i
                    break
            if target_index >= 0 and sp.getSelectedItemPosition() != target_index:
                state["suppress"] = True
                sp.setSelection(target_index, False)
                state["suppress"] = False

        if "on_change" in props or initial:
            state["on_change"] = props.get("on_change") if "on_change" in props else state.get("on_change")

            class _PickerListener(dynamic_proxy(jclass("android.widget.AdapterView").OnItemSelectedListener)):
                def __init__(self, owner_state: Dict[str, Any]) -> None:
                    super().__init__()
                    self._owner_state = owner_state

                def onItemSelected(
                    self,
                    parent: Any,
                    view: Any,  # noqa: ARG002
                    position: int,
                    id_: int,  # noqa: ARG002
                ) -> None:
                    if self._owner_state.get("suppress"):
                        return
                    items = self._owner_state.get("items") or []
                    if 0 <= position < len(items):
                        item = items[position]
                        v = item.get("value") if isinstance(item, dict) else item
                        cb = self._owner_state.get("on_change")
                        if cb is not None:
                            try:
                                cb(v)
                            except Exception:
                                pass

                def onNothingSelected(self, parent: Any) -> None:  # noqa: ARG002
                    pass

            sp.setOnItemSelectedListener(_PickerListener(state))


# ======================================================================
# Checkbox — native CheckBox with an optional inline label
# ======================================================================


class CheckboxHandler(AndroidViewHandler):
    """``Checkbox`` element handler — native ``CheckBox`` widget.

    Programmatic ``value`` updates are wrapped in a per-view
    "suppress" guard (mirroring ``PickerHandler``) so pushing a new
    state via ``setChecked`` never re-fires the user's ``on_change``.
    """

    def create(self, props: Dict[str, Any]) -> Any:
        cb = jclass("android.widget.CheckBox")(_ctx())
        self._state: Dict[int, Dict[str, Any]] = getattr(self, "_state", {})
        self._state[id(cb)] = {"on_change": None, "suppress": False}
        self._apply(cb, props, initial=True)
        return cb

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed, initial=False)

    def _apply(self, cb: Any, props: Dict[str, Any], initial: bool) -> None:
        state = self._state.setdefault(id(cb), {"on_change": None, "suppress": False})

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
                pass

        if "on_change" in props or initial:
            state["on_change"] = props.get("on_change") if "on_change" in props else state.get("on_change")

            class _CheckboxCheckedProxy(dynamic_proxy(jclass("android.widget.CompoundButton").OnCheckedChangeListener)):
                def __init__(self, owner_state: Dict[str, Any]) -> None:
                    super().__init__()
                    self._owner_state = owner_state

                def onCheckedChanged(self, button: Any, is_checked: bool) -> None:
                    if self._owner_state.get("suppress"):
                        return
                    callback = self._owner_state.get("on_change")
                    if callback is not None:
                        try:
                            callback(bool(is_checked))
                        except Exception:
                            pass

            cb.setOnCheckedChangeListener(_CheckboxCheckedProxy(state))

        _apply_accessibility(cb, props)


# ======================================================================
# SegmentedControl — horizontal toggle row (no UISegmentedControl on AOSP)
# ======================================================================


class SegmentedControlHandler(AndroidViewHandler):
    """``SegmentedControl`` element — a horizontal row of toggle buttons.

    Android has no ``UISegmentedControl`` equivalent, so the control is
    built from a horizontal ``LinearLayout`` holding one ``Button`` per
    segment. The selected segment is filled with the ``tint_color`` (or
    a default accent); the rest are drawn outlined. Selection state and
    the change callback live in a per-view dict, and a "suppress" guard
    keeps programmatic ``selected_index`` updates from re-firing
    ``on_change``. The control owns its own subviews, so
    ``add_child`` / ``remove_child`` are intentional no-ops.
    """

    _DEFAULT_ACCENT = "#007AFF"

    def create(self, props: Dict[str, Any]) -> Any:
        LinearLayout = jclass("android.widget.LinearLayout")
        ll = LinearLayout(_ctx())
        ll.setOrientation(LinearLayout.HORIZONTAL)
        self._state: Dict[int, Dict[str, Any]] = getattr(self, "_state", {})
        self._state[id(ll)] = {
            "segments": [],
            "selected_index": 0,
            "on_change": None,
            "tint_color": None,
            "enabled": True,
            "buttons": [],
            "suppress": False,
        }
        self._apply(ll, props, initial=True)
        return ll

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed, initial=False)

    def add_child(self, parent: Any, child: Any) -> None:
        # SegmentedControl renders its own segment buttons.
        return

    def remove_child(self, parent: Any, child: Any) -> None:
        return

    def _default_state(self) -> Dict[str, Any]:
        return {
            "segments": [],
            "selected_index": 0,
            "on_change": None,
            "tint_color": None,
            "enabled": True,
            "buttons": [],
            "suppress": False,
        }

    def _apply(self, ll: Any, props: Dict[str, Any], initial: bool) -> None:
        state = self._state.setdefault(id(ll), self._default_state())

        if "on_change" in props:
            state["on_change"] = props.get("on_change")
        if "tint_color" in props:
            state["tint_color"] = props.get("tint_color")
        if "enabled" in props:
            # ``enabled`` is only present when ``False``; a removal (``None``)
            # re-enables the control.
            state["enabled"] = props["enabled"] is not False

        segments_changed = False
        if "segments" in props or initial:
            raw = props.get("segments")
            new_segments = [str(s) for s in raw] if raw else []
            if initial or new_segments != state["segments"]:
                state["segments"] = new_segments
                segments_changed = True

        if "selected_index" in props and props["selected_index"] is not None:
            state["selected_index"] = int(props["selected_index"])

        if segments_changed:
            self._rebuild(ll, state)
        else:
            self._restyle(state)

        _apply_accessibility(ll, props)

    def _rebuild(self, ll: Any, state: Dict[str, Any]) -> None:
        try:
            ll.removeAllViews()
        except Exception:
            pass
        state["buttons"] = []
        LL_LP = jclass("android.widget.LinearLayout$LayoutParams")
        restyle = self._restyle
        for index, label in enumerate(state["segments"]):
            btn = jclass("android.widget.Button")(_ctx())
            btn.setText(str(label))
            try:
                btn.setAllCaps(False)
            except Exception:
                pass
            # Equal-width segments: zero base width + weight 1, full height.
            btn.setLayoutParams(LL_LP(0, LL_LP.MATCH_PARENT, 1.0))
            btn.setEnabled(bool(state["enabled"]))

            class _SegmentClickProxy(dynamic_proxy(jclass("android.view.View").OnClickListener)):
                def __init__(self, owner_state: Dict[str, Any], seg_index: int, container: Any) -> None:
                    super().__init__()
                    self._owner_state = owner_state
                    self._seg_index = seg_index
                    self._container = container

                def onClick(self, view: Any) -> None:
                    if self._owner_state.get("suppress") or not self._owner_state.get("enabled", True):
                        return
                    self._owner_state["selected_index"] = self._seg_index
                    restyle(self._owner_state)
                    cb = self._owner_state.get("on_change")
                    if cb is not None:
                        try:
                            cb(self._seg_index)
                        except Exception:
                            pass

            btn.setOnClickListener(_SegmentClickProxy(state, index, ll))
            ll.addView(btn)
            state["buttons"].append(btn)
        self._restyle(state)

    def _restyle(self, state: Dict[str, Any]) -> None:
        accent = state.get("tint_color") or self._DEFAULT_ACCENT
        selected = state.get("selected_index", 0)
        enabled = bool(state.get("enabled", True))
        for i, btn in enumerate(state.get("buttons", [])):
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
            pass

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
# DatePicker — trigger button opening native date/time dialogs
# ======================================================================


class DatePickerHandler(AndroidViewHandler):
    """``DatePicker`` element — a trigger ``Button`` opening native dialogs.

    The button text reflects the current ISO ``value`` (or a
    placeholder). Tapping it opens a ``DatePickerDialog`` (``mode``
    ``"date"``), a ``TimePickerDialog`` (``"time"``), or a chained
    date→time flow (``"datetime"``). Values are parsed / formatted with
    ``java.util.Calendar`` + ``java.text.SimpleDateFormat`` using
    per-mode ISO patterns, and the confirmed value is reported through
    ``on_change``.
    """

    _PATTERNS = {"date": "yyyy-MM-dd", "time": "HH:mm", "datetime": "yyyy-MM-dd'T'HH:mm"}
    _PLACEHOLDERS = {"date": "Select date", "time": "Select time", "datetime": "Select date & time"}

    def create(self, props: Dict[str, Any]) -> Any:
        btn = jclass("android.widget.Button")(_ctx())
        try:
            btn.setAllCaps(False)
        except Exception:
            pass
        self._state: Dict[int, Dict[str, Any]] = getattr(self, "_state", {})
        self._state[id(btn)] = {
            "value": None,
            "mode": "date",
            "on_change": None,
            "minimum": None,
            "maximum": None,
            "enabled": True,
        }
        self._apply(btn, props, initial=True)
        return btn

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed, initial=False)

    def _apply(self, btn: Any, props: Dict[str, Any], initial: bool) -> None:
        state = self._state.setdefault(
            id(btn),
            {"value": None, "mode": "date", "on_change": None, "minimum": None, "maximum": None, "enabled": True},
        )

        if "mode" in props and props["mode"]:
            state["mode"] = str(props["mode"])
        if "on_change" in props:
            state["on_change"] = props.get("on_change")
        if "minimum" in props:
            state["minimum"] = props.get("minimum")
        if "maximum" in props:
            state["maximum"] = props.get("maximum")
        if "enabled" in props:
            state["enabled"] = props["enabled"] is not False
            btn.setEnabled(bool(state["enabled"]))
        if "value" in props or initial:
            state["value"] = props.get("value") if "value" in props else state.get("value")

        self._refresh_label(btn, state)
        if initial:
            self._attach_trigger(btn, state)

        _apply_accessibility(btn, props)

    def _refresh_label(self, btn: Any, state: Dict[str, Any]) -> None:
        value = state.get("value")
        if value:
            btn.setText(str(value))
        else:
            btn.setText(self._PLACEHOLDERS.get(state.get("mode", "date"), "Select"))

    def _attach_trigger(self, btn: Any, state: Dict[str, Any]) -> None:
        open_dialog = self._open_dialog

        class _DateTriggerProxy(dynamic_proxy(jclass("android.view.View").OnClickListener)):
            def __init__(self, owner_state: Dict[str, Any], trigger: Any) -> None:
                super().__init__()
                self._owner_state = owner_state
                self._trigger = trigger

            def onClick(self, view: Any) -> None:
                if not self._owner_state.get("enabled", True):
                    return
                open_dialog(self._trigger, self._owner_state)

        btn.setOnClickListener(_DateTriggerProxy(state, btn))

    def _open_dialog(self, btn: Any, state: Dict[str, Any]) -> None:
        mode = state.get("mode", "date")
        cal = self._parse_to_calendar(state.get("value"), mode)
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
            mode = state.get("mode", "date")
            picker = dialog.getDatePicker()
            minimum = state.get("minimum")
            maximum = state.get("maximum")
            if minimum:
                picker.setMinDate(self._parse_to_calendar(minimum, mode).getTimeInMillis())
            if maximum:
                picker.setMaxDate(self._parse_to_calendar(maximum, mode).getTimeInMillis())
        except Exception:
            pass

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
                pass
        return cal

    def _format_calendar(self, cal: Any, mode: str) -> str:
        SimpleDateFormat = jclass("java.text.SimpleDateFormat")
        Locale = jclass("java.util.Locale")
        fmt = SimpleDateFormat(self._PATTERNS.get(mode, self._PATTERNS["date"]), Locale.US)
        return str(fmt.format(cal.getTime()))

    def _commit(self, btn: Any, state: Dict[str, Any], cal: Any) -> None:
        mode = state.get("mode", "date")
        try:
            iso = self._format_calendar(cal, mode)
        except Exception:
            return
        state["value"] = iso
        try:
            btn.setText(iso)
        except Exception:
            pass
        cb = state.get("on_change")
        if cb is not None:
            try:
                cb(iso)
            except Exception:
                pass


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
    registry.register("Slider", SliderHandler())
    registry.register("TabBar", TabBarHandler())
    registry.register("Pressable", PressableHandler())
    registry.register("StatusBar", StatusBarHandler())
    registry.register("KeyboardAvoidingView", KeyboardAvoidingViewHandler())
    registry.register("VirtualList", VirtualListHandler())
    registry.register("Picker", PickerHandler())
    registry.register("Checkbox", CheckboxHandler())
    registry.register("SegmentedControl", SegmentedControlHandler())
    registry.register("DatePicker", DatePickerHandler())


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
    "SliderHandler",
    "TabBarHandler",
    "PressableHandler",
    "StatusBarHandler",
    "KeyboardAvoidingViewHandler",
    "VirtualListHandler",
    "PickerHandler",
    "CheckboxHandler",
    "SegmentedControlHandler",
    "DatePickerHandler",
    "register_handlers",
]
