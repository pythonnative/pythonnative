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
_pn_view_visual_props: dict = {}
_DRAWABLE_STYLE_KEYS = ("background_color", "border_radius", "border_width", "border_color")

# ======================================================================
# Shared helpers
# ======================================================================


def _ctx() -> Any:
    return get_android_context()


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


class ScrollViewHandler(AndroidViewHandler):
    """Scroll container — wraps a single child whose height is unbounded.

    When a ``refresh_control`` prop is provided, wraps the scroll in
    a `SwipeRefreshLayout` and forwards the on-refresh callback.
    """

    def create(self, props: Dict[str, Any]) -> Any:
        sv = jclass("android.widget.ScrollView")(_ctx())
        _apply_common_visual(sv, props)
        # Wrap the inner ScrollView in a SwipeRefreshLayout when
        # ``refresh_control`` is asked for. Implementing this cleanly
        # would require returning a different parent; for v1, we
        # attach the listener via a wrapper that we expose to
        # add_child callers below.
        return sv

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        _apply_common_visual(native_view, changed)

    def add_child(self, parent: Any, child: Any) -> None:
        parent.addView(child)

    def remove_child(self, parent: Any, child: Any) -> None:
        parent.removeView(child)


class TextInputHandler(AndroidViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        et = jclass("android.widget.EditText")(_ctx())
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
        if "on_submit" in props and props["on_submit"] is not None:
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
        if "value" in props:
            pb.setProgress(int(float(props["value"]) * 1000))


class ActivityIndicatorHandler(AndroidViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        pb = jclass("android.widget.ProgressBar")(_ctx())
        if not props.get("animating", True):
            pb.setVisibility(jclass("android.view.View").GONE)
        return pb

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        View = jclass("android.view.View")
        if "animating" in changed:
            native_view.setVisibility(View.VISIBLE if changed["animating"] else View.GONE)


class WebViewHandler(AndroidViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        wv = jclass("android.webkit.WebView")(_ctx())
        if "url" in props and props["url"]:
            wv.loadUrl(str(props["url"]))
        return wv

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        if "url" in changed and changed["url"]:
            native_view.loadUrl(str(changed["url"]))


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
        visible = bool(props.get("visible", False))
        state = _pn_modal_states.get(id(placeholder))
        if visible and state is None:
            self._present(placeholder, props)
        elif not visible and state is not None:
            self._dismiss(placeholder)
        elif visible and state is not None:
            state["on_dismiss"] = props.get("on_dismiss")

    def _present(self, placeholder: Any, props: Dict[str, Any]) -> None:
        try:
            Dialog = jclass("android.app.Dialog")
            FrameLayout = jclass("android.widget.FrameLayout")
            LayoutParams = jclass("android.view.ViewGroup$LayoutParams")
            dialog = Dialog(_ctx())
            content = FrameLayout(_ctx())
            content.setBackgroundColor(parse_color_int("#FFFFFF"))
            dialog.setContentView(
                content,
                LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT),
            )
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
    Delegate = jclass("com.pythonnative.android_template.PNVirtualListView$Delegate")

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
            PNVirtualListView = jclass("com.pythonnative.android_template.PNVirtualListView")
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
    "register_handlers",
]
