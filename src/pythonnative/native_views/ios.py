"""iOS native-view handlers (rubicon-objc).

Each handler class maps a PythonNative element type to a UIKit view,
implementing view creation, property updates, child management, and
frame application. Handlers are registered with the
[`NativeViewRegistry`][pythonnative.native_views.NativeViewRegistry] by
[`register_handlers`][pythonnative.native_views.ios.register_handlers].

Layout is owned by the pure-Python flex engine in
[`pythonnative.layout`][pythonnative.layout]: container handlers create
plain `UIView`s, the engine computes per-child frames in points, and
[`set_frame`][pythonnative.native_views.ios.IOSViewHandler.set_frame]
applies those frames via UIKit's classic ``frame`` property (with Auto
Layout disabled). Handlers therefore only deal with *visual* props and
ignore everything in
[`pythonnative.layout.LAYOUT_STYLE_KEYS`][pythonnative.layout.LAYOUT_STYLE_KEYS].

This module is only imported on iOS at runtime. Desktop tests inject a
mock registry via
[`set_registry`][pythonnative.native_views.set_registry] and never
trigger this import path.
"""

import ctypes as _ct
import math
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from rubicon.objc import SEL, ObjCClass, objc_method

from . import _tripwire_log
from .base import ViewHandler, _safe_max, parse_color_int


def _safe_finite(value: Any, default: float = 0.0) -> float:
    """Coerce ``value`` to a finite float, falling back to ``default``.

    Used as a defensive guard around every call into UIKit that takes a
    geometry value. Without this, a single NaN or inf produced upstream
    (layout edge case, stale prop during a reload, etc.) crashes the
    process via `CALayerInvalidGeometry`. Clamping to ``default``
    converts that into a recoverable visual glitch and lets the
    `[set_frame:nan]` / `[set_transform:nan]` tripwire logs surface
    where the bad value came from.
    """
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    return f if math.isfinite(f) else default


NSObject = ObjCClass("NSObject")
UIColor = ObjCClass("UIColor")
UIFont = ObjCClass("UIFont")

# Declare ``superview`` as a property on UIView so rubicon-objc returns
# the actual UIView (or None) on attribute access, instead of an
# ObjCBoundMethod. Without this, accessing ``view.superview`` returns a
# method handle and the entire codepath that updates UIScrollView's
# ``contentSize`` would raise silently. See rubicon-objc docs on
# ``declare_property`` for why some ``@property`` declarations aren't
# auto-detected by the runtime introspection.
try:
    _UIView = ObjCClass("UIView")
    _UIView.declare_property("superview")
except Exception:
    pass


def _objc_ptr(obj: Any) -> Optional[int]:
    """Return the raw Objective-C pointer for a Rubicon object."""
    if obj is None:
        return None
    if isinstance(obj, int):
        return obj
    ptr = getattr(obj, "ptr", None)
    if isinstance(ptr, int):
        return ptr
    if isinstance(ptr, (bytes, bytearray)):
        try:
            return int.from_bytes(ptr, byteorder="little", signed=False)
        except Exception:
            return None
    value = getattr(ptr, "value", None)
    if isinstance(value, int):
        return value
    try:
        return int(ptr) if ptr is not None else None
    except Exception:
        return None


# ======================================================================
# Raw libobjc helpers
# ======================================================================
#
# rubicon-objc's ``@objc_method`` FFI bridge is unreliable on iOS arm64
# for some delegate callback shapes — in particular when UIKit passes
# tagged pointers (e.g. NSIndexPath) or invokes selectors that return
# objects, the FFI closure ends up in CPython's ``_ctypes.O_get`` and
# crashes on bogus PyObject* dereferences.
#
# These helpers let us bypass rubicon-objc entirely: allocate a brand
# new ObjC class via ``objc_allocateClassPair``, attach plain
# CFUNCTYPE-wrapped Python functions as ``IMP``s, and dispatch via
# ``objc_msgSend``. Every delegate that takes ObjC object arguments
# beyond ``UITableView*`` / plain integers should use this pattern
# (UITabBar's selection delegate and UITableView's data source both do).

_libobjc = _ct.cdll.LoadLibrary("libobjc.A.dylib")

_sel_reg = _libobjc.sel_registerName
_sel_reg.restype = _ct.c_void_p
_sel_reg.argtypes = [_ct.c_char_p]

_get_cls = _libobjc.objc_getClass
_get_cls.restype = _ct.c_void_p
_get_cls.argtypes = [_ct.c_char_p]

_alloc_cls = _libobjc.objc_allocateClassPair
_alloc_cls.restype = _ct.c_void_p
_alloc_cls.argtypes = [_ct.c_void_p, _ct.c_char_p, _ct.c_size_t]

_reg_cls = _libobjc.objc_registerClassPair
_reg_cls.argtypes = [_ct.c_void_p]

_add_method = _libobjc.class_addMethod
_add_method.restype = _ct.c_bool
_add_method.argtypes = [_ct.c_void_p, _ct.c_void_p, _ct.c_void_p, _ct.c_char_p]

_objc_msgSend = _libobjc.objc_msgSend

_SEL_ALLOC = _sel_reg(b"alloc")
_SEL_INIT = _sel_reg(b"init")
_SEL_RETAIN = _sel_reg(b"retain")
_SEL_SET_DELEGATE = _sel_reg(b"setDelegate:")
_SEL_SET_DATA_SOURCE = _sel_reg(b"setDataSource:")
_SEL_TAG = _sel_reg(b"tag")
_SEL_ROW = _sel_reg(b"row")
_SEL_DESELECT_ROW = _sel_reg(b"deselectRowAtIndexPath:animated:")
_SEL_TEXT = _sel_reg(b"text")
_SEL_UTF8STRING = _sel_reg(b"UTF8String")
_SEL_ADD_TARGET_ACTION_EVENTS = _sel_reg(b"addTarget:action:forControlEvents:")
_SEL_ON_EDIT = _sel_reg(b"onEdit:")
_SEL_ON_SUBMIT = _sel_reg(b"onSubmit:")
_SEL_RESIGN_FIRST_RESPONDER = _sel_reg(b"resignFirstResponder")
_SEL_TEXT_FIELD_SHOULD_RETURN = _sel_reg(b"textFieldShouldReturn:")

_NS_OBJECT_CLS = _get_cls(b"NSObject")


# ======================================================================
# Shared visual helpers
# ======================================================================

_pn_view_border_radius_map: dict = {}
_SHADOW_STYLE_KEYS = ("shadow_color", "shadow_offset", "shadow_opacity", "shadow_radius", "elevation")


def _has_shadow_props(props: Dict[str, Any]) -> bool:
    return any(key in props and props[key] is not None for key in _SHADOW_STYLE_KEYS)


def _uicolor(color: Any) -> Any:
    """Convert a color value to a `UIColor` instance."""
    argb = parse_color_int(color)
    if argb < 0:
        argb += 0x100000000
    a = ((argb >> 24) & 0xFF) / 255.0
    r = ((argb >> 16) & 0xFF) / 255.0
    g = ((argb >> 8) & 0xFF) / 255.0
    b = (argb & 0xFF) / 255.0
    return UIColor.colorWithRed_green_blue_alpha_(r, g, b, a)


def _cgcolor(color: Any) -> Any:
    """Convert a color value to a `CGColorRef` for layer-level APIs."""
    return _uicolor(color).CGColor


def _apply_border(layer: Any, props: Dict[str, Any]) -> None:
    """Apply border_radius / border_width / border_color to a CALayer."""
    if "border_radius" in props and props["border_radius"] is not None:
        try:
            layer.setCornerRadius_(float(props["border_radius"]))
            # Without ``masksToBounds`` rounded corners only clip if
            # ``overflow: "hidden"`` is set; that's the RN default for
            # corner-radius use cases. Honor it implicitly when the user
            # asks for corners (matches iOS UIKit common practice).
            layer.setMasksToBounds_(True)
        except Exception:
            pass
    if "border_width" in props and props["border_width"] is not None:
        try:
            layer.setBorderWidth_(float(props["border_width"]))
        except Exception:
            pass
    if "border_color" in props and props["border_color"] is not None:
        try:
            layer.setBorderColor_(_cgcolor(props["border_color"]))
        except Exception:
            pass


def _apply_view_border(view: Any, props: Dict[str, Any]) -> None:
    """Apply border props and remember requested radius for frame-time clamping."""
    if "border_radius" in props and props["border_radius"] is not None:
        try:
            requested = float(props["border_radius"])
            _pn_view_border_radius_map[id(view)] = requested
            radius = 0.0
            try:
                bounds = view.bounds
                width = float(bounds.size.width)
                height = float(bounds.size.height)
                if width > 0.0 and height > 0.0:
                    radius = min(requested, min(width, height) / 2.0)
            except Exception:
                pass
            border_props = dict(props)
            border_props["border_radius"] = radius
            _apply_border(view.layer, border_props)
            return
        except Exception:
            pass
    _apply_border(view.layer, props)


def _clamp_view_corner_radius(view: Any, width: float, height: float) -> None:
    """Clamp oversized pill radii to the view's rendered bounds."""
    requested = _pn_view_border_radius_map.get(id(view))
    if requested is None:
        return
    max_radius = max(0.0, min(float(width), float(height)) / 2.0)
    if max_radius <= 0.0:
        return
    try:
        view.layer.setCornerRadius_(min(float(requested), max_radius))
    except Exception:
        pass


def _clamp_layer_corner_radius(layer: Any, width: float, height: float) -> None:
    try:
        requested = float(layer.cornerRadius)
    except Exception:
        return
    if requested <= 0.0:
        return
    max_radius = max(0.0, min(float(width), float(height)) / 2.0)
    if max_radius <= 0.0:
        return
    try:
        layer.setCornerRadius_(min(requested, max_radius))
    except Exception:
        pass


def _apply_shadow(view: Any, props: Dict[str, Any]) -> None:
    """Apply shadow_color/shadow_offset/shadow_opacity/shadow_radius via the view's layer.

    Shadows on iOS require ``masksToBounds=False`` on the layer, so a
    shadowed view cannot also clip its children unless ``overflow:
    hidden`` is explicitly requested.
    """
    layer = view.layer
    if _has_shadow_props(props) and props.get("overflow") != "hidden":
        try:
            layer.setMasksToBounds_(False)
            view.setClipsToBounds_(False)
        except Exception:
            pass
    if "shadow_color" in props and props["shadow_color"] is not None:
        try:
            layer.setShadowColor_(_cgcolor(props["shadow_color"]))
        except Exception:
            pass
    if "shadow_opacity" in props and props["shadow_opacity"] is not None:
        try:
            layer.setShadowOpacity_(float(props["shadow_opacity"]))
        except Exception:
            pass
    if "shadow_radius" in props and props["shadow_radius"] is not None:
        try:
            layer.setShadowRadius_(float(props["shadow_radius"]))
        except Exception:
            pass
    if "shadow_offset" in props and props["shadow_offset"] is not None:
        offset = props["shadow_offset"]
        try:
            if isinstance(offset, dict):
                w = float(offset.get("width", 0))
                h = float(offset.get("height", 0))
            else:
                w, h = float(offset[0]), float(offset[1])
            layer.setShadowOffset_((w, h))
        except Exception:
            pass


def _make_transform(spec: Any) -> Any:
    """Build a `CGAffineTransform` from a list of transform dicts.

    Each dict has exactly one of ``rotate`` (degrees), ``scale`` (uniform),
    ``scale_x``, ``scale_y``, ``translate_x``, ``translate_y``.
    """
    try:
        from rubicon.objc.api import objc_const  # noqa: F401
    except Exception:
        pass
    # rubicon-objc doesn't expose CGAffineTransformIdentity directly;
    # we reconstruct it via the C struct.
    ct = _ct
    libc = ct.cdll.LoadLibrary("/usr/lib/libobjc.A.dylib")  # noqa: F841

    class CGAffineTransform(ct.Structure):
        _fields_ = [
            ("a", ct.c_double),
            ("b", ct.c_double),
            ("c", ct.c_double),
            ("d", ct.c_double),
            ("tx", ct.c_double),
            ("ty", ct.c_double),
        ]

    coregraphics = ct.cdll.LoadLibrary(
        "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics",
    )
    coregraphics.CGAffineTransformMakeIdentity = getattr(coregraphics, "CGAffineTransformMakeIdentity", None)
    coregraphics.CGAffineTransformRotate = coregraphics.CGAffineTransformRotate
    coregraphics.CGAffineTransformRotate.restype = CGAffineTransform
    coregraphics.CGAffineTransformRotate.argtypes = [CGAffineTransform, ct.c_double]
    coregraphics.CGAffineTransformScale = coregraphics.CGAffineTransformScale
    coregraphics.CGAffineTransformScale.restype = CGAffineTransform
    coregraphics.CGAffineTransformScale.argtypes = [CGAffineTransform, ct.c_double, ct.c_double]
    coregraphics.CGAffineTransformTranslate = coregraphics.CGAffineTransformTranslate
    coregraphics.CGAffineTransformTranslate.restype = CGAffineTransform
    coregraphics.CGAffineTransformTranslate.argtypes = [CGAffineTransform, ct.c_double, ct.c_double]

    # Identity matrix.
    transform = CGAffineTransform(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

    if spec is None:
        return transform

    entries = spec if isinstance(spec, list) else [spec]
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if "rotate" in entry:
            v = entry["rotate"]
            if isinstance(v, str) and v.endswith("deg"):
                angle = math.radians(float(v[:-3]))
            elif isinstance(v, str) and v.endswith("rad"):
                angle = float(v[:-3])
            else:
                angle = math.radians(float(v))
            transform = coregraphics.CGAffineTransformRotate(transform, angle)
        if "scale" in entry:
            s = float(entry["scale"])
            transform = coregraphics.CGAffineTransformScale(transform, s, s)
        if "scale_x" in entry:
            transform = coregraphics.CGAffineTransformScale(transform, float(entry["scale_x"]), 1.0)
        if "scale_y" in entry:
            transform = coregraphics.CGAffineTransformScale(transform, 1.0, float(entry["scale_y"]))
        if "translate_x" in entry or "translate_y" in entry:
            tx = float(entry.get("translate_x", 0.0))
            ty = float(entry.get("translate_y", 0.0))
            transform = coregraphics.CGAffineTransformTranslate(transform, tx, ty)

    return transform


def _apply_transform(view: Any, props: Dict[str, Any]) -> None:
    """Apply the ``transform`` style prop via ``view.transform = ...``."""
    if "transform" not in props:
        return
    spec = props["transform"]
    if spec is None:
        try:
            view.setTransform_((1.0, 0.0, 0.0, 1.0, 0.0, 0.0))
        except Exception:
            pass
        return
    try:
        transform = _make_transform(spec)
        a = float(transform.a)
        b = float(transform.b)
        c = float(transform.c)
        d = float(transform.d)
        tx = float(transform.tx)
        ty = float(transform.ty)
        if not (
            math.isfinite(a)
            and math.isfinite(b)
            and math.isfinite(c)
            and math.isfinite(d)
            and math.isfinite(tx)
            and math.isfinite(ty)
        ):
            # Tripwire: a NaN/inf transform crashes UIKit. Log
            # (rate-limited to avoid 60 Hz spam from stuck Animated
            # values) and fall back to identity so the app keeps
            # running.
            _tripwire_log(
                "set_transform:nan",
                f"[set_transform:nan] spec={spec!r} -> " f"(a={a!r}, b={b!r}, c={c!r}, d={d!r}, tx={tx!r}, ty={ty!r})",
            )
            view.setTransform_((1.0, 0.0, 0.0, 1.0, 0.0, 0.0))
            return
        # rubicon-objc accepts the C struct as a tuple of its fields.
        view.setTransform_((a, b, c, d, tx, ty))
    except Exception:
        pass


def _apply_accessibility(view: Any, props: Dict[str, Any]) -> None:
    """Apply accessibility_label / hint / role / accessible to a view."""
    if "accessible" in props:
        try:
            view.setIsAccessibilityElement_(bool(props["accessible"]))
        except Exception:
            pass
    if "accessibility_label" in props:
        v = props["accessibility_label"]
        try:
            view.setAccessibilityLabel_(str(v) if v is not None else "")
        except Exception:
            pass
    if "accessibility_hint" in props:
        v = props["accessibility_hint"]
        try:
            view.setAccessibilityHint_(str(v) if v is not None else "")
        except Exception:
            pass
    if "accessibility_role" in props and props["accessibility_role"] is not None:
        # UIAccessibilityTraits bitmask.
        traits = {
            "button": 1 << 0,
            "link": 1 << 1,
            "image": 1 << 2,
            "search": 1 << 3,
            "header": 1 << 28,
            "summary_element": 1 << 6,
            "selected": 1 << 5,
            "static_text": 1 << 4,
            "none": 0,
        }
        trait = traits.get(str(props["accessibility_role"]).lower())
        if trait is not None:
            try:
                view.setAccessibilityTraits_(trait)
            except Exception:
                pass


def _apply_common_visual(view: Any, props: Dict[str, Any]) -> None:
    """Apply visual properties shared across many handlers."""
    if "background_color" in props and props["background_color"] is not None:
        color = _uicolor(props["background_color"])
        view.setBackgroundColor_(color)
        try:
            view.layer.setBackgroundColor_(color.CGColor)
        except Exception:
            pass
    if "overflow" in props:
        view.setClipsToBounds_(props["overflow"] == "hidden")
    if "opacity" in props and props["opacity"] is not None:
        try:
            view.setAlpha_(float(props["opacity"]))
        except Exception:
            pass
    _apply_view_border(view, props)
    _apply_shadow(view, props)
    _apply_transform(view, props)
    _apply_accessibility(view, props)


# Properties that handlers can animate via
# [`set_animated_property`][pythonnative.native_views.ios.IOSViewHandler.set_animated_property].
_ANIMATABLE_PROPS = {
    "opacity",
    "translate_x",
    "translate_y",
    "scale",
    "scale_x",
    "scale_y",
    "rotate",  # degrees
    "background_color",
}


# ======================================================================
# Base class with shared frame/measure implementations
# ======================================================================


class IOSViewHandler(ViewHandler):
    """Base class providing the shared `set_frame` / measure contract.

    All iOS handlers go through `set_frame` to apply the layout
    engine's computed frames via classic ``CGRect`` positioning (Auto
    Layout off). Child management defaults to UIKit's
    `addSubview_:` / `removeFromSuperview` API.
    """

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        if native_view is None:
            return
        try:
            frame_x = _safe_finite(x, 0.0)
            frame_y = _safe_finite(y, 0.0)
            frame_w = max(0.0, _safe_finite(width, 0.0))
            frame_h = max(0.0, _safe_finite(height, 0.0))
            native_view.setTranslatesAutoresizingMaskIntoConstraints_(True)
            native_view.setFrame_(((frame_x, frame_y), (frame_w, frame_h)))
            _clamp_view_corner_radius(native_view, frame_w, frame_h)
            try:
                _clamp_layer_corner_radius(native_view.layer, frame_w, frame_h)
            except Exception:
                pass
            try:
                parent = native_view.superview
                parent_cls = ""
                try:
                    parent_cls = str(parent.objc_class.name) if parent is not None else ""
                except Exception:
                    parent_cls = ""
                # Expand the parent UIScrollView's contentSize whenever a
                # child's frame extends past the visible bounds, so the
                # scroll view can actually scroll to reveal it.
                if "UIScrollView" in parent_cls:
                    bounds = parent.bounds
                    content_w = max(float(bounds.size.width), frame_x + frame_w)
                    content_h = max(float(bounds.size.height), frame_y + frame_h)
                    parent.setContentSize_((content_w, content_h))
            except Exception:
                pass
        except Exception:
            pass

    def measure_intrinsic(
        self,
        native_view: Any,
        max_width: float,
        max_height: float,
    ) -> Tuple[float, float]:
        try:
            mw = _safe_max(max_width, fallback=10000.0)
            mh = _safe_max(max_height, fallback=10000.0)
            size = native_view.sizeThatFits_((mw, mh))
            w = float(size.width)
            h = float(size.height)
            if math.isfinite(max_width):
                w = min(w, max_width)
            return (w, h)
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

        Used by ``Animated.View`` to bypass the reconciler when the
        bound `Animated.Value` ticks. When
        ``duration_ms > 0``, the change is wrapped in
        ``UIView.animate(withDuration:)`` so UIKit interpolates between
        the current and target value at 60 FPS without further Python
        involvement.

        Args:
            native_view: The target ``UIView``-derived instance.
            prop_name: One of ``opacity``, ``translate_x``,
                ``translate_y``, ``scale``, ``scale_x``, ``scale_y``,
                ``rotate`` (degrees), ``background_color``.
            value: The new property value.
            duration_ms: Optional UIKit animation duration in ms; ``0``
                applies the change immediately.
            easing: Easing curve name (``linear``, ``ease_in``,
                ``ease_out``, ``ease_in_out``).
        """
        if native_view is None:
            return
        try:
            applier = _animated_applier_for(prop_name, value)
        except Exception:
            return
        if applier is None:
            return
        if duration_ms <= 0:
            try:
                applier(native_view)
            except Exception:
                pass
            return
        try:
            UIView = ObjCClass("UIView")
            options = {
                "linear": 1 << 16,
                "ease_in": 1 << 17,
                "ease_out": 1 << 18,
                "ease_in_out": 0,
            }.get(easing, 0)
            UIView.animateWithDuration_delay_options_animations_completion_(
                duration_ms / 1000.0,
                0.0,
                options,
                lambda: applier(native_view),
                None,
            )
        except Exception:
            try:
                applier(native_view)
            except Exception:
                pass


def _animated_applier_for(prop: str, value: Any) -> Optional[Callable[[Any], None]]:
    if prop == "opacity":
        v = float(value)

        def _apply(view: Any) -> None:
            view.setAlpha_(v)

        return _apply
    if prop == "background_color":

        def _apply(view: Any) -> None:
            view.setBackgroundColor_(_uicolor(value))

        return _apply
    if prop in ("translate_x", "translate_y", "scale", "scale_x", "scale_y", "rotate"):
        spec = {prop: value} if prop != "rotate" else {"rotate": value}

        def _apply(view: Any) -> None:
            _apply_transform(view, {"transform": [spec]})

        return _apply
    return None


# ======================================================================
# ObjC callback targets (retained at module level)
# ======================================================================

_pn_btn_handler_map: dict = {}
_pn_btn_callback_map: dict = {}
_pn_retained_views: list = []


class _PNButtonTarget(NSObject):  # type: ignore[valid-type]
    @objc_method
    def onTap_(self, sender: object) -> None:
        # Do not introspect ``sender`` here. On rubicon-objc 0.5.x the
        # selector trampoline can hand this callback a raw ObjC pointer;
        # calling ``getattr(sender, "ptr", ...)`` has been observed to
        # segfault before the user's callback runs.
        cb = _pn_btn_callback_map.get(id(self))
        if cb is not None:
            cb()


_pn_tf_change_callback_map: dict = {}
_pn_tf_submit_callback_map: dict = {}
_pn_tf_raw_target_map: dict = {}
_PN_TEXTFIELD_TARGET_CLS: Optional[int] = None
_textfield_edit_imp_ref: Any = None
_textfield_submit_imp_ref: Any = None
_textfield_should_return_imp_ref: Any = None


def _textfield_text(sender_ptr: int) -> str:
    if not sender_ptr:
        return ""
    try:
        _objc_msgSend.restype = _ct.c_void_p
        _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p]
        nsstring_ptr = _objc_msgSend(_ct.c_void_p(sender_ptr), _SEL_TEXT)
        if not nsstring_ptr:
            return ""
        _objc_msgSend.restype = _ct.c_char_p
        _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p]
        raw = _objc_msgSend(_ct.c_void_p(nsstring_ptr), _SEL_UTF8STRING)
        if not raw:
            return ""
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _textfield_on_edit_imp(self_ptr: int, _cmd: int, sender_ptr: int) -> None:
    cb = _pn_tf_change_callback_map.get(int(self_ptr))
    if cb is None:
        return
    text = _textfield_text(int(sender_ptr or 0))
    try:
        cb(text)
    except Exception:
        pass


def _textfield_on_submit_imp(self_ptr: int, _cmd: int, sender_ptr: int) -> None:
    cb = _pn_tf_submit_callback_map.get(int(self_ptr))
    if cb is None:
        return
    text = _textfield_text(int(sender_ptr or 0))
    try:
        cb(text)
    except Exception:
        pass


def _textfield_should_return_imp(self_ptr: int, _cmd: int, tf_ptr: int) -> bool:
    """``UITextFieldDelegate.textFieldShouldReturn:`` — dismiss the keyboard.

    iOS doesn't dismiss the keyboard on Return by default; the standard
    pattern is for the delegate to call ``resignFirstResponder`` and
    return ``YES``. Matching that here brings PythonNative's
    ``TextInput`` in line with React Native's default behavior and with
    what users expect from a ``return_key_type="done"`` style.
    """
    try:
        _objc_msgSend.restype = None
        _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p]
        _objc_msgSend(_ct.c_void_p(int(tf_ptr or 0)), _SEL_RESIGN_FIRST_RESPONDER)
    except Exception:
        pass
    return True


def _ensure_textfield_target_class() -> Optional[int]:
    global _PN_TEXTFIELD_TARGET_CLS
    global _textfield_edit_imp_ref, _textfield_submit_imp_ref, _textfield_should_return_imp_ref
    if _PN_TEXTFIELD_TARGET_CLS is not None:
        return _PN_TEXTFIELD_TARGET_CLS
    existing = _get_cls(b"PNTextFieldActionTarget")
    if existing:
        _PN_TEXTFIELD_TARGET_CLS = int(existing)
        return _PN_TEXTFIELD_TARGET_CLS
    cls = _alloc_cls(_NS_OBJECT_CLS, b"PNTextFieldActionTarget", 0)
    if not cls:
        return None
    action_type = _ct.CFUNCTYPE(None, _ct.c_void_p, _ct.c_void_p, _ct.c_void_p)
    bool_type = _ct.CFUNCTYPE(_ct.c_bool, _ct.c_void_p, _ct.c_void_p, _ct.c_void_p)
    _textfield_edit_imp_ref = action_type(_textfield_on_edit_imp)
    _textfield_submit_imp_ref = action_type(_textfield_on_submit_imp)
    _textfield_should_return_imp_ref = bool_type(_textfield_should_return_imp)
    _add_method(cls, _SEL_ON_EDIT, _ct.cast(_textfield_edit_imp_ref, _ct.c_void_p), b"v@:@")
    _add_method(cls, _SEL_ON_SUBMIT, _ct.cast(_textfield_submit_imp_ref, _ct.c_void_p), b"v@:@")
    _add_method(
        cls,
        _SEL_TEXT_FIELD_SHOULD_RETURN,
        _ct.cast(_textfield_should_return_imp_ref, _ct.c_void_p),
        b"c@:@",
    )
    _reg_cls(cls)
    _PN_TEXTFIELD_TARGET_CLS = int(cls)
    return _PN_TEXTFIELD_TARGET_CLS


def _new_textfield_target() -> Optional[int]:
    cls = _ensure_textfield_target_class()
    if not cls:
        return None
    _objc_msgSend.restype = _ct.c_void_p
    _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p]
    raw = _objc_msgSend(_ct.c_void_p(cls), _SEL_ALLOC)
    raw = _objc_msgSend(_ct.c_void_p(raw), _SEL_INIT)
    raw = _objc_msgSend(_ct.c_void_p(raw), _SEL_RETAIN)
    return int(raw) if raw else None


def _attach_textfield_raw_target(tf: Any, props: Dict[str, Any]) -> None:
    tf_ptr = _objc_ptr(tf)
    if not tf_ptr:
        return
    target_ptr = _pn_tf_raw_target_map.get(id(tf))
    if target_ptr is None:
        target_ptr = _new_textfield_target()
        if not target_ptr:
            return
        _pn_tf_raw_target_map[id(tf)] = target_ptr
        _pn_retained_views.append(target_ptr)
        _objc_msgSend.restype = None
        _objc_msgSend.argtypes = [
            _ct.c_void_p,
            _ct.c_void_p,
            _ct.c_void_p,
            _ct.c_void_p,
            _ct.c_ulong,
        ]
        _objc_msgSend(
            _ct.c_void_p(tf_ptr),
            _SEL_ADD_TARGET_ACTION_EVENTS,
            _ct.c_void_p(target_ptr),
            _SEL_ON_EDIT,
            1 << 17,
        )
        _objc_msgSend(
            _ct.c_void_p(tf_ptr),
            _SEL_ADD_TARGET_ACTION_EVENTS,
            _ct.c_void_p(target_ptr),
            _SEL_ON_SUBMIT,
            1 << 6,
        )
        # Wire the same object as the UITextFieldDelegate so its
        # ``textFieldShouldReturn:`` runs and resigns first responder
        # — without this iOS keeps the keyboard up after Return.
        _objc_msgSend.restype = None
        _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p, _ct.c_void_p]
        _objc_msgSend(
            _ct.c_void_p(tf_ptr),
            _SEL_SET_DELEGATE,
            _ct.c_void_p(target_ptr),
        )
    if "on_change" in props:
        _pn_tf_change_callback_map[int(target_ptr)] = props["on_change"]
    if "on_submit" in props:
        _pn_tf_submit_callback_map[int(target_ptr)] = props["on_submit"]


_pn_switch_handler_map: dict = {}


class _PNSwitchTarget(NSObject):  # type: ignore[valid-type]
    _callback: Optional[Callable[[bool], None]] = None

    @objc_method
    def onToggle_(self, sender: object) -> None:
        if self._callback is not None:
            try:
                self._callback(bool(sender.isOn()))
            except Exception:
                pass


_pn_slider_handler_map: dict = {}


class _PNSliderTarget(NSObject):  # type: ignore[valid-type]
    _callback: Optional[Callable[[float], None]] = None

    @objc_method
    def onSlide_(self, sender: object) -> None:
        if self._callback is not None:
            try:
                self._callback(float(sender.value))
            except Exception:
                pass


_pn_pressable_state: dict = {}


class _PNPressableTarget(NSObject):  # type: ignore[valid-type]
    @objc_method
    def onTouchDown_(self, sender: object) -> None:
        info = _pn_pressable_state.get(id(self))
        if not info:
            return
        view = info.get("view")
        opacity = info.get("pressed_opacity", 0.6)
        if view is not None:
            try:
                UIView = ObjCClass("UIView")
                UIView.animateWithDuration_animations_(0.05, lambda: view.setAlpha_(float(opacity)))
            except Exception:
                pass

    @objc_method
    def onTouchUp_(self, sender: object) -> None:
        info = _pn_pressable_state.get(id(self))
        if not info:
            return
        view = info.get("view")
        cb = info.get("on_press")
        if view is not None:
            try:
                UIView = ObjCClass("UIView")
                UIView.animateWithDuration_animations_(0.1, lambda: view.setAlpha_(1.0))
            except Exception:
                pass
        if cb is not None:
            try:
                cb()
            except Exception:
                pass

    @objc_method
    def onTouchCancel_(self, sender: object) -> None:
        info = _pn_pressable_state.get(id(self))
        if not info:
            return
        view = info.get("view")
        if view is not None:
            try:
                UIView = ObjCClass("UIView")
                UIView.animateWithDuration_animations_(0.1, lambda: view.setAlpha_(1.0))
            except Exception:
                pass

    @objc_method
    def onLongPress_(self, sender: object) -> None:
        info = _pn_pressable_state.get(id(self))
        if not info:
            return
        # UILongPressGestureRecognizer fires on state Began (state==1).
        try:
            state = int(sender.state)
        except Exception:
            state = 1
        if state != 1:
            return
        cb = info.get("on_long_press")
        if cb is not None:
            try:
                cb()
            except Exception:
                pass


# ======================================================================
# Flex container handler (shared by Column, Row, View)
# ======================================================================


class FlexContainerHandler(IOSViewHandler):
    """Container for flex layout — a bare `UIView`.

    All flex semantics (direction, alignment, distribution, padding)
    are computed by the layout engine and applied via
    [`set_frame`][pythonnative.native_views.ios.IOSViewHandler.set_frame].
    """

    def create(self, props: Dict[str, Any]) -> Any:
        v = ObjCClass("UIView").alloc().init()
        v.setTranslatesAutoresizingMaskIntoConstraints_(True)
        _apply_common_visual(v, props)
        return v

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        _apply_common_visual(native_view, changed)

    def add_child(self, parent: Any, child: Any) -> None:
        try:
            child.setTranslatesAutoresizingMaskIntoConstraints_(True)
        except Exception:
            pass
        parent.addSubview_(child)

    def remove_child(self, parent: Any, child: Any) -> None:
        child.removeFromSuperview()

    def insert_child(self, parent: Any, child: Any, index: int) -> None:
        try:
            child.setTranslatesAutoresizingMaskIntoConstraints_(True)
        except Exception:
            pass
        parent.insertSubview_atIndex_(child, index)


# ======================================================================
# Leaf handlers
# ======================================================================


class TextHandler(IOSViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        label = ObjCClass("UILabel").alloc().init()
        label.setNumberOfLines_(0)
        label.setTranslatesAutoresizingMaskIntoConstraints_(True)
        self._apply(label, props)
        return label

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _font_for(self, size: float, weight: Any, family: Optional[str], italic: bool) -> Any:
        """Resolve a UIFont from family/weight/italic/size keys."""
        size = float(size)
        if family:
            font = UIFont.fontWithName_size_(str(family), size)
            if font is not None:
                if italic:
                    desc = font.fontDescriptor.fontDescriptorWithSymbolicTraits_(2)  # italic trait
                    if desc is not None:
                        font = UIFont.fontWithDescriptor_size_(desc, size)
                return font
        # Numeric weight: 100..900. UIFontWeight constants are:
        # ultraLight=-0.8, thin=-0.6, light=-0.4, regular=0, medium=0.23,
        # semibold=0.3, bold=0.4, heavy=0.56, black=0.62.
        weight_const = 0.0
        if isinstance(weight, str):
            named = {
                "ultralight": -0.8,
                "thin": -0.6,
                "light": -0.4,
                "regular": 0.0,
                "normal": 0.0,
                "medium": 0.23,
                "semibold": 0.3,
                "bold": 0.4,
                "heavy": 0.56,
                "black": 0.62,
            }
            weight_const = named.get(weight.lower(), 0.0)
        elif isinstance(weight, (int, float)):
            n = max(100.0, min(900.0, float(weight)))
            mapping = [
                (100, -0.8),
                (200, -0.6),
                (300, -0.4),
                (400, 0.0),
                (500, 0.23),
                (600, 0.3),
                (700, 0.4),
                (800, 0.56),
                (900, 0.62),
            ]
            for w, c in mapping:
                if n <= w:
                    weight_const = c
                    break
        font = UIFont.systemFontOfSize_weight_(size, weight_const)
        if italic:
            try:
                desc = font.fontDescriptor.fontDescriptorWithSymbolicTraits_(2)
                if desc is not None:
                    font = UIFont.fontWithDescriptor_size_(desc, size)
            except Exception:
                pass
        return font

    def _apply(self, label: Any, props: Dict[str, Any]) -> None:
        if "text" in props:
            label.setText_(str(props["text"]) if props["text"] is not None else "")
        # Font requires combining size + weight + family + italic + bold.
        font_keys_present = any(k in props for k in ("font_size", "font_weight", "font_family", "italic", "bold"))
        if font_keys_present:
            current = label.font
            try:
                current_size = float(current.pointSize) if current is not None else 17.0
            except Exception:
                current_size = 17.0
            size = float(props.get("font_size", current_size)) if props.get("font_size") is not None else current_size
            weight = props.get("font_weight")
            if weight is None and props.get("bold"):
                weight = "bold"
            family = props.get("font_family")
            italic = bool(props.get("italic"))
            label.setFont_(self._font_for(size, weight, family, italic))
        if "color" in props and props["color"] is not None:
            label.setTextColor_(_uicolor(props["color"]))
        if "background_color" in props and props["background_color"] is not None:
            label.setBackgroundColor_(_uicolor(props["background_color"]))
        if "max_lines" in props and props["max_lines"] is not None:
            label.setNumberOfLines_(int(props["max_lines"]))
        if "text_align" in props:
            mapping = {"left": 0, "center": 1, "right": 2, "natural": 4, "justify": 3}
            label.setTextAlignment_(mapping.get(props["text_align"], 0))
        if "letter_spacing" in props or "line_height" in props or "text_decoration" in props:
            self._apply_attributed(label, props)
        _apply_view_border(label, props)
        _apply_shadow(label, props)
        _apply_transform(label, props)
        _apply_accessibility(label, props)
        if "opacity" in props and props["opacity"] is not None:
            try:
                label.setAlpha_(float(props["opacity"]))
            except Exception:
                pass

    def _apply_attributed(self, label: Any, props: Dict[str, Any]) -> None:
        """Re-render the label's text as an NSAttributedString.

        Needed for ``letter_spacing`` (NSKernAttributeName),
        ``line_height`` (paragraph style), and ``text_decoration``
        (underline/strikethrough). Plain text setters do not support
        these attributes.
        """
        try:
            text = str(label.text) if label.text is not None else ""
            if not text:
                return
            NSMutableAttributedString = ObjCClass("NSMutableAttributedString")
            NSMutableParagraphStyle = ObjCClass("NSMutableParagraphStyle")
            attr = NSMutableAttributedString.alloc().initWithString_(text)
            full_range = (0, len(text))

            font = label.font
            if font is not None:
                attr.addAttribute_value_range_("NSFont", font, full_range)
            if props.get("letter_spacing") is not None:
                attr.addAttribute_value_range_(
                    "NSKern",
                    float(props["letter_spacing"]),
                    full_range,
                )
            line_h = props.get("line_height")
            if line_h is not None:
                style = NSMutableParagraphStyle.alloc().init()
                style.setMinimumLineHeight_(float(line_h))
                style.setMaximumLineHeight_(float(line_h))
                attr.addAttribute_value_range_(
                    "NSParagraphStyle",
                    style,
                    full_range,
                )
            decoration = props.get("text_decoration")
            if decoration == "underline":
                attr.addAttribute_value_range_("NSUnderline", 1, full_range)
            elif decoration == "line_through":
                attr.addAttribute_value_range_("NSStrikethrough", 1, full_range)
            label.setAttributedText_(attr)
        except Exception:
            pass


class ButtonHandler(IOSViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        # ``UIButtonTypeSystem`` (1) gives us a properly-sized button
        # with intrinsicContentSize derived from the title; the default
        # ``UIButtonTypeCustom`` returns CGSizeZero from sizeThatFits_,
        # which makes the button collapse to 0×0 under the layout engine.
        btn = ObjCClass("UIButton").buttonWithType_(1)
        btn.setTranslatesAutoresizingMaskIntoConstraints_(True)
        btn.retain()
        _pn_retained_views.append(btn)
        self._apply(btn, props)
        return btn

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def measure_intrinsic(
        self,
        native_view: Any,
        max_width: float,
        max_height: float,
    ) -> Tuple[float, float]:
        try:
            size = native_view.intrinsicContentSize()
            w = float(size.width) + 24.0
            h = float(size.height) + 12.0
            if math.isfinite(max_width):
                w = min(w, max_width)
            if math.isfinite(max_height):
                h = min(h, max_height)
            return (max(w, 44.0), max(h, 32.0))
        except Exception:
            return (44.0, 32.0)

    def _apply(self, btn: Any, props: Dict[str, Any]) -> None:
        if "title" in props:
            btn.setTitle_forState_(str(props["title"]) if props["title"] is not None else "", 0)
        if "font_size" in props and props["font_size"] is not None:
            btn.titleLabel.setFont_(UIFont.systemFontOfSize_(float(props["font_size"])))
        if "background_color" in props and props["background_color"] is not None:
            btn.setBackgroundColor_(_uicolor(props["background_color"]))
            if "color" not in props:
                _white = UIColor.colorWithRed_green_blue_alpha_(1.0, 1.0, 1.0, 1.0)
                btn.setTitleColor_forState_(_white, 0)
        if "color" in props and props["color"] is not None:
            btn.setTitleColor_forState_(_uicolor(props["color"]), 0)
        if "enabled" in props:
            btn.setEnabled_(bool(props["enabled"]))
        _apply_view_border(btn, props)
        _apply_shadow(btn, props)
        _apply_transform(btn, props)
        _apply_accessibility(btn, props)
        if "opacity" in props and props["opacity"] is not None:
            try:
                btn.setAlpha_(float(props["opacity"]))
            except Exception:
                pass
        if "on_click" in props:
            existing = _pn_btn_handler_map.get(id(btn))
            if existing is not None:
                _pn_btn_callback_map[id(existing)] = props["on_click"]
            else:
                handler = _PNButtonTarget.new()
                _pn_btn_handler_map[id(btn)] = handler
                _pn_btn_callback_map[id(handler)] = props["on_click"]
                btn.addTarget_action_forControlEvents_(handler, SEL("onTap:"), 1 << 6)


class ScrollViewHandler(IOSViewHandler):
    """Scroll container — wraps a single child whose height is unbounded.

    The child is positioned by the layout engine using its natural
    content height. The shared frame applier expands the parent
    `UIScrollView.contentSize` whenever a child frame extends beyond
    the visible bounds.

    When ``refresh_control`` is provided in props (a dict with
    ``refreshing`` + ``on_refresh``), a ``UIRefreshControl`` is
    attached to the scroll view.
    """

    def create(self, props: Dict[str, Any]) -> Any:
        sv = ObjCClass("UIScrollView").alloc().init()
        sv.setTranslatesAutoresizingMaskIntoConstraints_(True)
        _apply_common_visual(sv, props)
        self._apply_refresh(sv, props)
        return sv

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        _apply_common_visual(native_view, changed)
        if "refresh_control" in changed:
            self._apply_refresh(native_view, changed)

    def add_child(self, parent: Any, child: Any) -> None:
        try:
            child.setTranslatesAutoresizingMaskIntoConstraints_(True)
        except Exception:
            pass
        parent.addSubview_(child)

    def remove_child(self, parent: Any, child: Any) -> None:
        child.removeFromSuperview()

    def _apply_refresh(self, sv: Any, props: Dict[str, Any]) -> None:
        spec = props.get("refresh_control")
        if not spec:
            return
        try:
            existing = sv.refreshControl
            if existing is None:
                rc = ObjCClass("UIRefreshControl").alloc().init()
                rc.retain()
                _pn_retained_views.append(rc)
                sv.setRefreshControl_(rc)
                target = _PNButtonTarget.new()
                target.retain()
                _pn_retained_views.append(target)
                _pn_btn_handler_map[id(rc)] = target
                rc.addTarget_action_forControlEvents_(target, SEL("onTap:"), 1 << 12)  # ValueChanged
                existing = rc
            cb = spec.get("on_refresh") if isinstance(spec, dict) else None
            target = _pn_btn_handler_map.get(id(existing))
            if target is not None and cb is not None:
                _pn_btn_callback_map[id(target)] = cb
            refreshing = bool(spec.get("refreshing")) if isinstance(spec, dict) else False
            if refreshing:
                existing.beginRefreshing()
            else:
                existing.endRefreshing()
        except Exception:
            pass


class TextInputHandler(IOSViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        if props.get("multiline"):
            tv = ObjCClass("UITextView").alloc().init()
            tv.setTranslatesAutoresizingMaskIntoConstraints_(True)
            tv.setBackgroundColor_(_uicolor("#FFFFFF"))
            self._apply_textview(tv, props)
            return tv
        tf = ObjCClass("UITextField").alloc().init()
        tf.setBorderStyle_(2)  # RoundedRect
        tf.setTranslatesAutoresizingMaskIntoConstraints_(True)
        self._apply_textfield(tf, props)
        return tf

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        # Detect whether the underlying view is a UITextView (multiline).
        try:
            cls_name = str(native_view.objc_class.name)
        except Exception:
            cls_name = ""
        if "UITextView" in cls_name:
            self._apply_textview(native_view, changed)
        else:
            self._apply_textfield(native_view, changed)

    def _common_apply(self, view: Any, props: Dict[str, Any]) -> None:
        if "font_size" in props and props["font_size"] is not None:
            view.setFont_(UIFont.systemFontOfSize_(float(props["font_size"])))
        if "color" in props and props["color"] is not None:
            view.setTextColor_(_uicolor(props["color"]))
        if "background_color" in props and props["background_color"] is not None:
            view.setBackgroundColor_(_uicolor(props["background_color"]))
        if "secure" in props and props["secure"]:
            try:
                view.setSecureTextEntry_(True)
            except Exception:
                pass
        if "auto_capitalize" in props:
            mapping = {"none": 0, "words": 1, "sentences": 2, "characters": 3}
            try:
                view.setAutocapitalizationType_(mapping.get(props["auto_capitalize"], 2))
            except Exception:
                pass
        if "auto_correct" in props:
            try:
                view.setAutocorrectionType_(0 if not props["auto_correct"] else 1)
            except Exception:
                pass
        if "keyboard_type" in props:
            mapping = {
                "default": 0,
                "ascii": 1,
                "numbers_and_punctuation": 2,
                "url": 3,
                "number_pad": 4,
                "phone_pad": 5,
                "email_address": 7,
                "decimal_pad": 8,
            }
            try:
                view.setKeyboardType_(mapping.get(props["keyboard_type"], 0))
            except Exception:
                pass
        if "return_key_type" in props:
            mapping = {
                "default": 0,
                "go": 1,
                "google": 2,
                "join": 3,
                "next": 4,
                "route": 5,
                "search": 6,
                "send": 7,
                "yahoo": 8,
                "done": 9,
            }
            try:
                view.setReturnKeyType_(mapping.get(props["return_key_type"], 0))
            except Exception:
                pass
        _apply_view_border(view, props)
        _apply_shadow(view, props)
        _apply_transform(view, props)
        _apply_accessibility(view, props)
        if "opacity" in props and props["opacity"] is not None:
            try:
                view.setAlpha_(float(props["opacity"]))
            except Exception:
                pass

    def _apply_textfield(self, tf: Any, props: Dict[str, Any]) -> None:
        if "value" in props:
            tf.setText_(str(props["value"]) if props["value"] is not None else "")
        if "placeholder" in props:
            tf.setPlaceholder_(str(props["placeholder"]) if props["placeholder"] is not None else "")
        if "placeholder_color" in props and props["placeholder_color"] is not None:
            try:
                NSAttributedString = ObjCClass("NSAttributedString")
                p = str(props.get("placeholder", "") or "")
                attr = NSAttributedString.alloc().initWithString_attributes_(
                    p,
                    {"NSColor": _uicolor(props["placeholder_color"])},
                )
                tf.setAttributedPlaceholder_(attr)
            except Exception:
                pass
        if "auto_focus" in props and props["auto_focus"]:
            try:
                tf.becomeFirstResponder()
            except Exception:
                pass
        if "max_length" in props:
            try:
                tf.setMaxLength_(int(props["max_length"]))  # custom; UIKit has no native max
            except Exception:
                pass
        self._common_apply(tf, props)
        # Always wire the action target — even without ``on_change`` /
        # ``on_submit`` we want the textfield's delegate set so Return
        # dismisses the keyboard (textFieldShouldReturn:).
        _attach_textfield_raw_target(tf, props)

    def _apply_textview(self, tv: Any, props: Dict[str, Any]) -> None:
        if "value" in props:
            tv.setText_(str(props["value"]) if props["value"] is not None else "")
        if "auto_focus" in props and props["auto_focus"]:
            try:
                tv.becomeFirstResponder()
            except Exception:
                pass
        self._common_apply(tv, props)
        # NB: UITextView change events go through UITextViewDelegate; we
        # rely on KVO-style notification via UITextView.notificationName.
        # Skipping callback wiring here keeps the multiline path simple
        # (pure display + manual `value` round-trip) until we add a real
        # delegate implementation.


class ImageHandler(IOSViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        iv = ObjCClass("UIImageView").alloc().init()
        iv.setTranslatesAutoresizingMaskIntoConstraints_(True)
        self._apply(iv, props)
        return iv

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _apply(self, iv: Any, props: Dict[str, Any]) -> None:
        if "background_color" in props and props["background_color"] is not None:
            iv.setBackgroundColor_(_uicolor(props["background_color"]))
        if "tint_color" in props and props["tint_color"] is not None:
            try:
                iv.setTintColor_(_uicolor(props["tint_color"]))
            except Exception:
                pass
        if "source" in props and props["source"]:
            self._load_source(iv, props["source"])
        if "scale_type" in props and props["scale_type"]:
            mapping = {"cover": 2, "contain": 1, "stretch": 0, "center": 4}
            iv.setContentMode_(mapping.get(props["scale_type"], 1))
        _apply_view_border(iv, props)
        _apply_shadow(iv, props)
        _apply_transform(iv, props)
        _apply_accessibility(iv, props)
        if "opacity" in props and props["opacity"] is not None:
            try:
                iv.setAlpha_(float(props["opacity"]))
            except Exception:
                pass

    def _load_source(self, iv: Any, source: str) -> None:
        try:
            if source.startswith(("http://", "https://")):
                self._load_async(iv, source)
            else:
                UIImage = ObjCClass("UIImage")
                image = UIImage.imageNamed_(source)
                if image:
                    iv.setImage_(image)
        except Exception:
            pass

    def _load_async(self, iv: Any, source: str) -> None:
        """Asynchronously load a remote image off the main thread.

        Uses ``NSURLSession.sharedSession.dataTaskWithURL:completionHandler:``
        so the main thread is never blocked. The completion handler
        runs on a background queue; the image is set back on the main
        queue via ``dispatch_async`` so UIKit accepts it without
        threading warnings.
        """
        try:
            iv.retain()
            _pn_retained_views.append(iv)
            NSURL = ObjCClass("NSURL")
            NSURLSession = ObjCClass("NSURLSession")
            UIImage = ObjCClass("UIImage")
            url = NSURL.URLWithString_(source)
            session = NSURLSession.sharedSession

            def completion(data: Any, response: Any, error: Any) -> None:
                if error is not None or data is None:
                    return
                try:
                    image = UIImage.imageWithData_(data)
                    if image is None:
                        return

                    def apply() -> None:
                        try:
                            iv.setImage_(image)
                        except Exception:
                            pass

                    # Marshal back to main thread.
                    try:
                        from rubicon.objc import dispatch_async, dispatch_get_main_queue

                        dispatch_async(dispatch_get_main_queue(), apply)
                    except Exception:
                        try:
                            apply()
                        except Exception:
                            pass
                except Exception:
                    pass

            task = session.dataTaskWithURL_completionHandler_(url, completion)
            task.resume()
        except Exception:
            pass


class SwitchHandler(IOSViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        sw = ObjCClass("UISwitch").alloc().init()
        sw.setTranslatesAutoresizingMaskIntoConstraints_(True)
        self._apply(sw, props)
        return sw

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _apply(self, sw: Any, props: Dict[str, Any]) -> None:
        if "value" in props:
            sw.setOn_animated_(bool(props["value"]), False)
        _apply_accessibility(sw, props)
        if "on_change" in props:
            existing = _pn_switch_handler_map.get(id(sw))
            if existing is not None:
                existing._callback = props["on_change"]
            else:
                handler = _PNSwitchTarget.new()
                handler._callback = props["on_change"]
                _pn_switch_handler_map[id(sw)] = handler
                sw.addTarget_action_forControlEvents_(handler, SEL("onToggle:"), 1 << 12)


class ProgressBarHandler(IOSViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        pv = ObjCClass("UIProgressView").alloc().init()
        pv.setTranslatesAutoresizingMaskIntoConstraints_(True)
        if "value" in props:
            pv.setProgress_(float(props["value"]))
        return pv

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        if "value" in changed:
            native_view.setProgress_(float(changed["value"]))


class ActivityIndicatorHandler(IOSViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        ai = ObjCClass("UIActivityIndicatorView").alloc().init()
        ai.setTranslatesAutoresizingMaskIntoConstraints_(True)
        if props.get("animating", True):
            ai.startAnimating()
        return ai

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        if "animating" in changed:
            if changed["animating"]:
                native_view.startAnimating()
            else:
                native_view.stopAnimating()


class WebViewHandler(IOSViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        wv = ObjCClass("WKWebView").alloc().init()
        wv.setTranslatesAutoresizingMaskIntoConstraints_(True)
        if "url" in props and props["url"]:
            NSURL = ObjCClass("NSURL")
            NSURLRequest = ObjCClass("NSURLRequest")
            url_obj = NSURL.URLWithString_(str(props["url"]))
            wv.loadRequest_(NSURLRequest.requestWithURL_(url_obj))
        return wv

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        if "url" in changed and changed["url"]:
            NSURL = ObjCClass("NSURL")
            NSURLRequest = ObjCClass("NSURLRequest")
            url_obj = NSURL.URLWithString_(str(changed["url"]))
            native_view.loadRequest_(NSURLRequest.requestWithURL_(url_obj))


class SpacerHandler(IOSViewHandler):
    """Empty layout placeholder used as a flexible gap.

    All sizing semantics live in the layout engine; ``Spacer``
    behaves identically to a `View` with the same style props.
    """

    def create(self, props: Dict[str, Any]) -> Any:
        v = ObjCClass("UIView").alloc().init()
        v.setTranslatesAutoresizingMaskIntoConstraints_(True)
        return v

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        pass


class SafeAreaViewHandler(IOSViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        v = ObjCClass("UIView").alloc().init()
        v.setTranslatesAutoresizingMaskIntoConstraints_(True)
        _apply_common_visual(v, props)
        return v

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        _apply_common_visual(native_view, changed)

    def add_child(self, parent: Any, child: Any) -> None:
        try:
            child.setTranslatesAutoresizingMaskIntoConstraints_(True)
        except Exception:
            pass
        parent.addSubview_(child)

    def remove_child(self, parent: Any, child: Any) -> None:
        child.removeFromSuperview()


# ======================================================================
# Modal — actually presents a UIViewController
# ======================================================================


class ModalHandler(IOSViewHandler):
    """Real modal presentation backed by a presented `UIViewController`.

    The on-tree placeholder is a hidden ``UIView`` (so the layout
    engine can ignore it). When ``visible`` flips to ``True``, a
    fresh ``UIViewController`` is allocated, its view is configured
    as the container into which the modal's children mount, and the
    controller is presented from the topmost view controller.

    Children are added to the *content view* of the presented
    controller, not the on-tree placeholder, so the reconciler's
    ``add_child`` / ``insert_child`` calls are forwarded there.
    """

    def create(self, props: Dict[str, Any]) -> Any:
        v = ObjCClass("UIView").alloc().init()
        v.setHidden_(True)
        v._pn_modal_state = None
        self._apply(v, props, mounting=True)
        return v

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed, mounting=False)

    def add_child(self, parent: Any, child: Any) -> None:
        # Forward to the modal content view if present.
        state = _pn_modal_states.get(id(parent))
        if state and state.get("content_view") is not None:
            try:
                child.setTranslatesAutoresizingMaskIntoConstraints_(True)
            except Exception:
                pass
            state["content_view"].addSubview_(child)
        else:
            # Buffer for later, once the modal becomes visible.
            buf = _pn_modal_pending.setdefault(id(parent), [])
            buf.append(child)

    def remove_child(self, parent: Any, child: Any) -> None:
        try:
            child.removeFromSuperview()
        except Exception:
            pass
        buf = _pn_modal_pending.get(id(parent))
        if buf and child in buf:
            buf.remove(child)

    def insert_child(self, parent: Any, child: Any, index: int) -> None:
        state = _pn_modal_states.get(id(parent))
        if state and state.get("content_view") is not None:
            try:
                child.setTranslatesAutoresizingMaskIntoConstraints_(True)
            except Exception:
                pass
            state["content_view"].insertSubview_atIndex_(child, index)
        else:
            buf = _pn_modal_pending.setdefault(id(parent), [])
            buf.insert(index, child)

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        # Modal is a virtual placeholder — not rendered inline.
        return

    def _apply(self, placeholder: Any, props: Dict[str, Any], *, mounting: bool) -> None:
        visible = bool(props.get("visible", False))
        state = _pn_modal_states.get(id(placeholder))
        if visible and state is None:
            self._present(placeholder, props)
        elif not visible and state is not None:
            self._dismiss(placeholder)
        elif visible and state is not None:
            # Already presented; refresh the on_dismiss callback.
            state["on_dismiss"] = props.get("on_dismiss")

    def _present(self, placeholder: Any, props: Dict[str, Any]) -> None:
        try:
            UIViewController = ObjCClass("UIViewController")
            UIApplication = ObjCClass("UIApplication")
            controller = UIViewController.alloc().init()
            controller.retain()
            _pn_retained_views.append(controller)

            content = ObjCClass("UIView").alloc().init()
            content.setBackgroundColor_(_uicolor("#FFFFFF"))
            content.setTranslatesAutoresizingMaskIntoConstraints_(True)
            controller.view.addSubview_(content)
            controller.view.setBackgroundColor_(_uicolor("#FFFFFF"))
            # Stretch the content view to the controller's view.
            try:
                bounds = controller.view.bounds
                content.setFrame_(((0, 0), (bounds.size.width, bounds.size.height)))
                content.setAutoresizingMask_(2 | 16)  # FlexibleWidth | FlexibleHeight
            except Exception:
                pass

            _pn_modal_states[id(placeholder)] = {
                "controller": controller,
                "content_view": content,
                "on_dismiss": props.get("on_dismiss"),
            }
            # Drain any pending children.
            for child in _pn_modal_pending.pop(id(placeholder), []):
                try:
                    content.addSubview_(child)
                except Exception:
                    pass

            top = UIApplication.sharedApplication.keyWindow.rootViewController
            while top is not None and top.presentedViewController is not None:
                top = top.presentedViewController
            if top is not None:
                top.presentViewController_animated_completion_(controller, True, None)
        except Exception:
            pass

    def _dismiss(self, placeholder: Any) -> None:
        state = _pn_modal_states.pop(id(placeholder), None)
        if state is None:
            return
        controller = state.get("controller")
        on_dismiss = state.get("on_dismiss")
        if controller is not None:
            try:
                controller.dismissViewControllerAnimated_completion_(True, None)
            except Exception:
                pass
        if on_dismiss is not None:
            try:
                on_dismiss()
            except Exception:
                pass


_pn_modal_states: Dict[int, dict] = {}
_pn_modal_pending: Dict[int, List[Any]] = {}


class SliderHandler(IOSViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        sl = ObjCClass("UISlider").alloc().init()
        sl.setTranslatesAutoresizingMaskIntoConstraints_(True)
        self._apply(sl, props)
        return sl

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _apply(self, sl: Any, props: Dict[str, Any]) -> None:
        if "min_value" in props:
            sl.setMinimumValue_(float(props["min_value"]))
        if "max_value" in props:
            sl.setMaximumValue_(float(props["max_value"]))
        if "value" in props:
            sl.setValue_(float(props["value"]))
        _apply_accessibility(sl, props)
        if "on_change" in props:
            existing = _pn_slider_handler_map.get(id(sl))
            if existing is not None:
                existing._callback = props["on_change"]
            else:
                handler = _PNSliderTarget.new()
                handler._callback = props["on_change"]
                _pn_slider_handler_map[id(sl)] = handler
                sl.addTarget_action_forControlEvents_(handler, SEL("onSlide:"), 1 << 12)


# ======================================================================
# Pressable — visual touch feedback + tap/long-press callbacks
# ======================================================================


class PressableHandler(IOSViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        v = ObjCClass("UIView").alloc().init()
        v.setTranslatesAutoresizingMaskIntoConstraints_(True)
        v.setUserInteractionEnabled_(True)
        target = _PNPressableTarget.new()
        target.retain()
        _pn_retained_views.append(target)
        # UITapGestureRecognizer for press (single tap) — provides
        # touchDown/up via UIControl events on subclassed UIControl,
        # but since this is a UIView we register a tap gesture for
        # on_press and a long-press gesture for on_long_press.
        try:
            UITapGestureRecognizer = ObjCClass("UITapGestureRecognizer")
            tap = UITapGestureRecognizer.alloc().initWithTarget_action_(target, SEL("onTouchUp:"))
            v.addGestureRecognizer_(tap)
            UILongPressGestureRecognizer = ObjCClass("UILongPressGestureRecognizer")
            longp = UILongPressGestureRecognizer.alloc().initWithTarget_action_(target, SEL("onLongPress:"))
            v.addGestureRecognizer_(longp)
        except Exception:
            pass
        _pn_pressable_state[id(target)] = {
            "view": v,
            "on_press": props.get("on_press"),
            "on_long_press": props.get("on_long_press"),
            "pressed_opacity": float(props.get("pressed_opacity", 0.6)),
        }
        # Stash the target id so update() can reach it.
        v._pn_press_target_id = id(target)
        _apply_common_visual(v, props)
        return v

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        target_id = getattr(native_view, "_pn_press_target_id", None)
        if target_id is not None and target_id in _pn_pressable_state:
            info = _pn_pressable_state[target_id]
            if "on_press" in changed:
                info["on_press"] = changed["on_press"]
            if "on_long_press" in changed:
                info["on_long_press"] = changed["on_long_press"]
            if "pressed_opacity" in changed and changed["pressed_opacity"] is not None:
                info["pressed_opacity"] = float(changed["pressed_opacity"])
        _apply_common_visual(native_view, changed)

    def add_child(self, parent: Any, child: Any) -> None:
        try:
            child.setTranslatesAutoresizingMaskIntoConstraints_(True)
        except Exception:
            pass
        parent.addSubview_(child)

    def remove_child(self, parent: Any, child: Any) -> None:
        child.removeFromSuperview()


# ======================================================================
# StatusBar — global side effect, no view in the tree
# ======================================================================


class StatusBarHandler(IOSViewHandler):
    """Apply status-bar style/visibility to the key window.

    Status bar configuration on iOS is a per-view-controller value;
    we use the legacy UIApplication setters which still work on
    iOS 13+ (with ``UIViewControllerBasedStatusBarAppearance`` set
    to ``NO`` in Info.plist for full effect). The placeholder view
    is hidden and contributes nothing to the layout.
    """

    def create(self, props: Dict[str, Any]) -> Any:
        v = ObjCClass("UIView").alloc().init()
        v.setHidden_(True)
        self._apply(props)
        return v

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(changed)

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        return

    def _apply(self, props: Dict[str, Any]) -> None:
        try:
            UIApplication = ObjCClass("UIApplication")
            app = UIApplication.sharedApplication
            if "hidden" in props and props["hidden"] is not None:
                app.setStatusBarHidden_animated_(bool(props["hidden"]), True)
            if "bar_style" in props and props["bar_style"] is not None:
                # 0 = default (dark content on iOS 12-), 1 = lightContent,
                # 3 = darkContent (iOS 13+).
                mapping = {"default": 3, "light": 1, "dark": 3}
                app.setStatusBarStyle_animated_(mapping.get(props["bar_style"], 0), True)
        except Exception:
            pass


# ======================================================================
# KeyboardAvoidingView — wraps children and offsets them by the keyboard
# ======================================================================


_pn_keyboard_observer: Any = None


class _PNKeyboardObserver(NSObject):  # type: ignore[valid-type]
    @objc_method
    def keyboardWillShow_(self, notification: object) -> None:
        try:
            info = notification.userInfo
            kbd_frame = info.objectForKey_("UIKeyboardFrameEndUserInfoKey")
            # Frame is wrapped in NSValue; the Python side reads
            # CGRectValue() which returns a tuple of structs.
            rect = kbd_frame.CGRectValue
            height = float(rect.size.height)
        except Exception:
            height = 0.0
        from .. import platform_metrics

        platform_metrics.set_keyboard_height(height)

    @objc_method
    def keyboardWillHide_(self, notification: object) -> None:
        from .. import platform_metrics

        platform_metrics.set_keyboard_height(0.0)


def _ensure_keyboard_observer() -> None:
    global _pn_keyboard_observer
    if _pn_keyboard_observer is not None:
        return
    try:
        observer = _PNKeyboardObserver.new()
        observer.retain()
        _pn_keyboard_observer = observer
        NSNotificationCenter = ObjCClass("NSNotificationCenter")
        center = NSNotificationCenter.defaultCenter
        center.addObserver_selector_name_object_(
            observer,
            SEL("keyboardWillShow:"),
            "UIKeyboardWillShowNotification",
            None,
        )
        center.addObserver_selector_name_object_(
            observer,
            SEL("keyboardWillHide:"),
            "UIKeyboardWillHideNotification",
            None,
        )
    except Exception:
        pass


class KeyboardAvoidingViewHandler(IOSViewHandler):
    """Container that listens to the system keyboard and re-publishes its height.

    The actual layout shift is implemented in user-land by the
    [`KeyboardAvoidingView`][pythonnative.KeyboardAvoidingView]
    component, which subscribes to ``platform_metrics.subscribe`` via
    [`use_keyboard_height`][pythonnative.use_keyboard_height] and
    applies the offset as bottom padding. The native handler is just
    a vanilla UIView that ensures the observer is installed.
    """

    def create(self, props: Dict[str, Any]) -> Any:
        _ensure_keyboard_observer()
        v = ObjCClass("UIView").alloc().init()
        v.setTranslatesAutoresizingMaskIntoConstraints_(True)
        _apply_common_visual(v, props)
        return v

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        _apply_common_visual(native_view, changed)

    def add_child(self, parent: Any, child: Any) -> None:
        try:
            child.setTranslatesAutoresizingMaskIntoConstraints_(True)
        except Exception:
            pass
        parent.addSubview_(child)

    def remove_child(self, parent: Any, child: Any) -> None:
        child.removeFromSuperview()


# ======================================================================
# VirtualList — UITableView-backed virtualized list
# ======================================================================
#
# We register a raw libobjc class ``_PNTableSourceCTypes`` rather than
# using rubicon-objc's ``@objc_method`` because UIKit invokes
# ``tableView:cellForRowAtIndexPath:`` with a tagged-pointer
# NSIndexPath that crashes inside CPython's ``_ctypes.O_get`` when
# rubicon-objc's FFI closure tries to wrap it as a PyObject*.
#
# Each UITableView gets its own dataSource instance; per-instance
# state lives in ``_pn_table_state`` keyed by the dataSource's raw
# pointer (the integer value passed as ``self`` to every IMP).

_pn_table_state: Dict[int, dict] = {}


_PN_CELL_REUSE_ID = "PNCell"


_TABLE_NUM_SECTIONS_TYPE = _ct.CFUNCTYPE(_ct.c_long, _ct.c_void_p, _ct.c_void_p, _ct.c_void_p)
_TABLE_NUM_ROWS_TYPE = _ct.CFUNCTYPE(_ct.c_long, _ct.c_void_p, _ct.c_void_p, _ct.c_void_p, _ct.c_long)
_TABLE_HEIGHT_TYPE = _ct.CFUNCTYPE(_ct.c_double, _ct.c_void_p, _ct.c_void_p, _ct.c_void_p, _ct.c_void_p)
_TABLE_CELL_TYPE = _ct.CFUNCTYPE(_ct.c_void_p, _ct.c_void_p, _ct.c_void_p, _ct.c_void_p, _ct.c_void_p)
_TABLE_DID_SELECT_TYPE = _ct.CFUNCTYPE(None, _ct.c_void_p, _ct.c_void_p, _ct.c_void_p, _ct.c_void_p)


def _table_num_sections_imp(self_ptr: int, cmd_ptr: int, tv_ptr: int) -> int:
    return 1


def _table_num_rows_imp(self_ptr: int, cmd_ptr: int, tv_ptr: int, section: int) -> int:
    try:
        info = _pn_table_state.get(int(self_ptr))
        return int(info.get("count", 0)) if info else 0
    except Exception:
        import traceback as _tb

        print("[VirtualList][iOS] _table_num_rows_imp raised:")
        _tb.print_exc()
        return 0


def _table_height_imp(self_ptr: int, cmd_ptr: int, tv_ptr: int, ip_ptr: int) -> float:
    try:
        info = _pn_table_state.get(int(self_ptr))
        return float(info.get("row_height", 44.0)) if info else 44.0
    except Exception:
        import traceback as _tb

        print("[VirtualList][iOS] _table_height_imp raised:")
        _tb.print_exc()
        return 44.0


def _table_cell_imp(self_ptr: int, cmd_ptr: int, tv_ptr: int, ip_ptr: int) -> int:
    """Build (or reuse) a cell for ``tableView:cellForRowAtIndexPath:``.

    ``ip_ptr`` is read raw via ``[indexPath row]`` to avoid the
    rubicon-objc tagged-pointer crash. The table view itself is a
    real heap object so we can wrap it as an ObjCInstance for the
    convenience of dequeue / cell allocation. We retain the freshly
    allocated cell explicitly so it survives past the Python wrapper
    going out of scope at the end of this frame.
    """
    import traceback as _tb

    try:
        _objc_msgSend.restype = _ct.c_long
        _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p]
        row = int(_objc_msgSend(_ct.c_void_p(ip_ptr), _SEL_ROW))
    except Exception:
        print("[VirtualList][iOS] _table_cell_imp: indexPath.row read raised:")
        _tb.print_exc()
        row = 0

    try:
        from rubicon.objc import ObjCInstance

        UITableViewCell = ObjCClass("UITableViewCell")
        tv = ObjCInstance(_ct.c_void_p(tv_ptr))
        info = _pn_table_state.get(int(self_ptr))
        row_h = float(info.get("row_height", 44.0)) if info else 44.0

        try:
            tv_bounds = tv.bounds
            cell_w = float(tv_bounds.size.width)
        except Exception:
            cell_w = 0.0
        if cell_w <= 0:
            try:
                screen = ObjCClass("UIScreen").mainScreen()
                cell_w = float(screen.bounds.size.width)
            except Exception:
                cell_w = 320.0

        cell = tv.dequeueReusableCellWithIdentifier_(_PN_CELL_REUSE_ID)
        if cell is None or (hasattr(cell, "ptr") and cell.ptr.value == 0):
            cell = UITableViewCell.alloc().initWithStyle_reuseIdentifier_(0, _PN_CELL_REUSE_ID)
            transparent = _uicolor("#00000000")
            cell.setBackgroundColor_(transparent)
            cell.contentView.setBackgroundColor_(transparent)
            cell.retain()  # offset the Python wrapper's release on __del__

        try:
            cell.setFrame_(((0, 0), (cell_w, row_h)))
            cell.contentView.setFrame_(((0, 0), (cell_w, row_h)))
        except Exception:
            print("[VirtualList][iOS] _table_cell_imp: cell pre-size raised:")
            _tb.print_exc()

        try:
            existing_subs = cell.contentView.subviews
            if callable(existing_subs):
                existing_subs = existing_subs()
            for sub in list(existing_subs):
                sub.removeFromSuperview()
        except Exception:
            print("[VirtualList][iOS] _table_cell_imp: strip prior subviews raised:")
            _tb.print_exc()

        if info is not None:
            mount = info.get("mount_row")
            if mount is not None:
                try:
                    mount(row, cell.contentView, cell_w, row_h)
                except Exception:
                    print(f"[VirtualList][iOS] _table_cell_imp mount_row({row}) raised:")
                    _tb.print_exc()

        cell_ptr = cell.ptr.value
        return int(cell_ptr) if cell_ptr is not None else 0
    except Exception:
        print(f"[VirtualList][iOS] _table_cell_imp raised for row={row}:")
        _tb.print_exc()
        try:
            UITableViewCell = ObjCClass("UITableViewCell")
            cell = UITableViewCell.alloc().initWithStyle_reuseIdentifier_(0, _PN_CELL_REUSE_ID)
            cell.retain()
            return int(cell.ptr.value)
        except Exception:
            return 0


def _table_did_select_imp(self_ptr: int, cmd_ptr: int, tv_ptr: int, ip_ptr: int) -> None:
    try:
        _objc_msgSend.restype = _ct.c_long
        _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p]
        row = int(_objc_msgSend(_ct.c_void_p(ip_ptr), _SEL_ROW))
    except Exception:
        import traceback as _tb

        print("[VirtualList][iOS] _table_did_select_imp: indexPath.row read raised:")
        _tb.print_exc()
        return

    try:
        _objc_msgSend.restype = None
        _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p, _ct.c_void_p, _ct.c_bool]
        _objc_msgSend(_ct.c_void_p(tv_ptr), _SEL_DESELECT_ROW, _ct.c_void_p(ip_ptr), True)
    except Exception:
        import traceback as _tb

        print("[VirtualList][iOS] _table_did_select_imp: deselect raised:")
        _tb.print_exc()

    try:
        info = _pn_table_state.get(int(self_ptr))
        if info is None:
            return
        cb = info.get("on_row_press")
        if cb is not None:
            cb(row)
    except Exception:
        import traceback as _tb

        print("[VirtualList][iOS] _table_did_select_imp: on_row_press raised:")
        _tb.print_exc()


_table_num_sections_imp_ref = _TABLE_NUM_SECTIONS_TYPE(_table_num_sections_imp)
_table_num_rows_imp_ref = _TABLE_NUM_ROWS_TYPE(_table_num_rows_imp)
_table_height_imp_ref = _TABLE_HEIGHT_TYPE(_table_height_imp)
_table_cell_imp_ref = _TABLE_CELL_TYPE(_table_cell_imp)
_table_did_select_imp_ref = _TABLE_DID_SELECT_TYPE(_table_did_select_imp)


_PN_TABLE_SOURCE_CLS = _alloc_cls(_NS_OBJECT_CLS, b"_PNTableSourceCTypes", 0)
if _PN_TABLE_SOURCE_CLS:
    _add_method(
        _PN_TABLE_SOURCE_CLS,
        _sel_reg(b"numberOfSectionsInTableView:"),
        _ct.cast(_table_num_sections_imp_ref, _ct.c_void_p),
        b"q@:@",
    )
    _add_method(
        _PN_TABLE_SOURCE_CLS,
        _sel_reg(b"tableView:numberOfRowsInSection:"),
        _ct.cast(_table_num_rows_imp_ref, _ct.c_void_p),
        b"q@:@q",
    )
    _add_method(
        _PN_TABLE_SOURCE_CLS,
        _sel_reg(b"tableView:heightForRowAtIndexPath:"),
        _ct.cast(_table_height_imp_ref, _ct.c_void_p),
        b"d@:@@",
    )
    _add_method(
        _PN_TABLE_SOURCE_CLS,
        _sel_reg(b"tableView:cellForRowAtIndexPath:"),
        _ct.cast(_table_cell_imp_ref, _ct.c_void_p),
        b"@@:@@",
    )
    _add_method(
        _PN_TABLE_SOURCE_CLS,
        _sel_reg(b"tableView:didSelectRowAtIndexPath:"),
        _ct.cast(_table_did_select_imp_ref, _ct.c_void_p),
        b"v@:@@",
    )
    _reg_cls(_PN_TABLE_SOURCE_CLS)


def _alloc_table_source_instance() -> int:
    """Allocate and retain a fresh ``_PNTableSourceCTypes`` instance.

    Returns the raw pointer (integer) for the new dataSource. Callers
    must keep the pointer alive themselves — UITableView's dataSource
    relationship is non-retaining.
    """
    if not _PN_TABLE_SOURCE_CLS:
        raise RuntimeError("_PNTableSourceCTypes class registration failed")
    _objc_msgSend.restype = _ct.c_void_p
    _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p]
    raw = _objc_msgSend(_PN_TABLE_SOURCE_CLS, _SEL_ALLOC)
    raw = _objc_msgSend(raw, _SEL_INIT)
    raw = _objc_msgSend(raw, _SEL_RETAIN)
    return int(raw) if raw is not None else 0


class VirtualListHandler(IOSViewHandler):
    """Backed by ``UITableView``; rows are mounted on demand from Python.

    Expects props:

    - ``count``: total number of rows.
    - ``row_height``: fixed row height in points (variable heights
      would require a per-row measurement pass; out of scope for v1).
    - ``mount_row``: callable ``(row_index, content_view) -> None``
      that inserts the row's native view into ``content_view``. The
      Python side computes this by mounting a fresh sub-tree using
      its own reconciler, then calling ``add_child`` on the supplied
      content view.
    - ``on_row_press``: optional ``(row_index) -> None`` callback.
    """

    def create(self, props: Dict[str, Any]) -> Any:
        import traceback as _tb

        try:
            UITableView = ObjCClass("UITableView")
            tv = UITableView.alloc().initWithFrame_style_(((0, 0), (0, 0)), 0)
        except Exception:
            print("[VirtualList][iOS] UITableView alloc raised:")
            _tb.print_exc()
            raise
        try:
            tv.setTranslatesAutoresizingMaskIntoConstraints_(True)
            tv.setBackgroundColor_(_uicolor(props.get("background_color") or "#FFFFFF"))
        except Exception:
            print("[VirtualList][iOS] tv basic setup raised:")
            _tb.print_exc()
        try:
            tv.setSeparatorStyle_(0)  # None by default; users can opt in.
        except Exception:
            print("[VirtualList][iOS] setSeparatorStyle_ raised:")
            _tb.print_exc()

        try:
            source_ptr = _alloc_table_source_instance()
        except Exception:
            print("[VirtualList][iOS] raw dataSource allocation raised:")
            _tb.print_exc()
            raise
        if source_ptr == 0:
            raise RuntimeError("[VirtualList][iOS] dataSource alloc returned NULL")

        _pn_table_state[source_ptr] = {
            "count": int(props.get("count", 0)),
            "row_height": float(props.get("row_height", 44.0)),
            "mount_row": props.get("mount_row"),
            "on_row_press": props.get("on_row_press"),
        }

        try:
            _objc_msgSend.restype = None
            _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p, _ct.c_void_p]
            tv_ptr = tv.ptr if hasattr(tv, "ptr") else tv
            _objc_msgSend(tv_ptr, _SEL_SET_DATA_SOURCE, _ct.c_void_p(source_ptr))
            _objc_msgSend(tv_ptr, _SEL_SET_DELEGATE, _ct.c_void_p(source_ptr))
        except Exception:
            print("[VirtualList][iOS] raw setDataSource:/setDelegate: raised:")
            _tb.print_exc()
            raise

        try:
            tv._pn_source_id = source_ptr
        except Exception:
            print("[VirtualList][iOS] attaching _pn_source_id raised:")
            _tb.print_exc()
        return tv

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        sid = getattr(native_view, "_pn_source_id", None)
        if sid is None or sid not in _pn_table_state:
            return
        info = _pn_table_state[sid]
        if "count" in changed:
            info["count"] = int(changed["count"])
        if "row_height" in changed and changed["row_height"] is not None:
            info["row_height"] = float(changed["row_height"])
        if "mount_row" in changed:
            info["mount_row"] = changed["mount_row"]
        if "on_row_press" in changed:
            info["on_row_press"] = changed["on_row_press"]
        if "background_color" in changed and changed["background_color"] is not None:
            native_view.setBackgroundColor_(_uicolor(changed["background_color"]))
        try:
            native_view.reloadData()
        except Exception:
            pass


# ======================================================================
# UITabBar delegate via raw libobjc
# ======================================================================
#
# Uses the shared raw-libobjc helpers above. See the section comment
# there for why we sidestep rubicon-objc for delegate callbacks.

_pn_tabbar_state: dict = {"callback": None, "items": []}
_pn_tabbar_delegate_installed: bool = False
_pn_tabbar_delegate_ptr: Any = None

_DELEGATE_IMP_TYPE = _ct.CFUNCTYPE(None, _ct.c_void_p, _ct.c_void_p, _ct.c_void_p, _ct.c_void_p)


def _tabbar_did_select_imp(self_ptr: int, cmd_ptr: int, tabbar_ptr: int, item_ptr: int) -> None:
    """Raw C callback for ``tabBar:didSelectItem:``."""
    try:
        _objc_msgSend.restype = _ct.c_long
        _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p]
        tag: int = _objc_msgSend(item_ptr, _SEL_TAG)

        cb = _pn_tabbar_state["callback"]
        tab_items = _pn_tabbar_state["items"]
        if cb is not None and tab_items and 0 <= tag < len(tab_items):
            cb(tab_items[tag].get("name", ""))
    except Exception:
        pass


_tabbar_imp_ref = _DELEGATE_IMP_TYPE(_tabbar_did_select_imp)

_PN_DELEGATE_CLS = _alloc_cls(_NS_OBJECT_CLS, b"_PNTabBarDelegateCTypes", 0)
if _PN_DELEGATE_CLS:
    _add_method(
        _PN_DELEGATE_CLS,
        _sel_reg(b"tabBar:didSelectItem:"),
        _ct.cast(_tabbar_imp_ref, _ct.c_void_p),
        b"v@:@@",
    )
    _reg_cls(_PN_DELEGATE_CLS)


def _ensure_tabbar_delegate(tab_bar: Any) -> None:
    global _pn_tabbar_delegate_ptr
    if _pn_tabbar_delegate_ptr is None and _PN_DELEGATE_CLS:
        _objc_msgSend.restype = _ct.c_void_p
        _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p]
        raw = _objc_msgSend(_PN_DELEGATE_CLS, _SEL_ALLOC)
        raw = _objc_msgSend(raw, _SEL_INIT)
        raw = _objc_msgSend(raw, _SEL_RETAIN)
        _pn_tabbar_delegate_ptr = raw

    if _pn_tabbar_delegate_ptr is not None:
        _objc_msgSend.restype = None
        _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p, _ct.c_void_p]
        tab_bar_ptr = tab_bar.ptr if hasattr(tab_bar, "ptr") else tab_bar
        _objc_msgSend(tab_bar_ptr, _SEL_SET_DELEGATE, _pn_tabbar_delegate_ptr)


class TabBarHandler(IOSViewHandler):
    """Native tab bar using ``UITabBar``.

    Each tab is a ``UITabBarItem`` with a ``tag`` matching its index
    in the items list. A raw ctypes delegate forwards selection
    events back to the Python ``on_tab_select`` callback.
    """

    def create(self, props: Dict[str, Any]) -> Any:
        from .. import platform_metrics

        initial_h = platform_metrics.ios_tab_bar_height()
        tab_bar = ObjCClass("UITabBar").alloc().initWithFrame_(((0, 0), (0, initial_h)))
        tab_bar.setTranslatesAutoresizingMaskIntoConstraints_(True)
        tab_bar.retain()
        _pn_retained_views.append(tab_bar)
        self._apply_full(tab_bar, props)
        return tab_bar

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply_partial(native_view, changed)

    def measure_intrinsic(
        self,
        native_view: Any,
        max_width: float,
        max_height: float,
    ) -> Tuple[float, float]:
        from .. import platform_metrics

        w = max_width if math.isfinite(max_width) else 320.0
        h = platform_metrics.ios_tab_bar_height()
        return (w, h)

    def _apply_full(self, tab_bar: Any, props: Dict[str, Any]) -> None:
        items = props.get("items", [])
        self._set_bar_items(tab_bar, items)
        self._set_active(tab_bar, props.get("active_tab"), items)
        self._set_callback(tab_bar, props.get("on_tab_select"), items)

    def _apply_partial(self, tab_bar: Any, changed: Dict[str, Any]) -> None:
        prev_items = _pn_tabbar_state["items"]
        if "items" in changed:
            items = changed["items"]
            self._set_bar_items(tab_bar, items)
        else:
            items = prev_items
        if "active_tab" in changed:
            self._set_active(tab_bar, changed["active_tab"], items)
        if "on_tab_select" in changed:
            self._set_callback(tab_bar, changed["on_tab_select"], items)

    def _set_bar_items(self, tab_bar: Any, items: list) -> None:
        UITabBarItem = ObjCClass("UITabBarItem")
        UIImage = ObjCClass("UIImage")
        bar_items = []
        for i, item in enumerate(items):
            title = item.get("title", item.get("name", ""))
            image = self._resolve_icon(UIImage, item.get("icon"))
            bar_item = UITabBarItem.alloc().initWithTitle_image_tag_(str(title), image, i)
            bar_items.append(bar_item)
        tab_bar.setItems_animated_(bar_items, False)

    def _resolve_icon(self, UIImage: Any, icon: Any) -> Any:
        """Resolve a tab icon spec to a UIImage, or return None.

        Accepts a bare string (treated as an SF Symbol name) or a dict
        of the form ``{"ios": "house.fill", "android": "..."}``. SF
        Symbols are looked up via ``UIImage.systemImageNamed:``; names
        that don't resolve produce a text-only tab.
        """
        if icon is None:
            return None
        name: Any = None
        if isinstance(icon, str):
            name = icon
        elif isinstance(icon, dict):
            name = icon.get("ios")
        if not name:
            return None
        try:
            image = UIImage.systemImageNamed_(str(name))
            return image if image else None
        except Exception:
            return None

    def _set_active(self, tab_bar: Any, active: Any, items: list) -> None:
        if not active or not items:
            return
        for i, item in enumerate(items):
            if item.get("name") == active:
                try:
                    all_items = list(tab_bar.items or [])
                    if i < len(all_items):
                        tab_bar.setSelectedItem_(all_items[i])
                except Exception:
                    pass
                break

    def _set_callback(self, tab_bar: Any, cb: Any, items: list) -> None:
        _pn_tabbar_state["callback"] = cb
        _pn_tabbar_state["items"] = items
        _ensure_tabbar_delegate(tab_bar)


# ======================================================================
# Alert / Picker imperative helpers
# ======================================================================


def _window_is_key(window: Any) -> bool:
    try:
        value = getattr(window, "isKeyWindow", False)
        return bool(value() if callable(value) else value)
    except Exception:
        return False


def _top_view_controller_for_alert(app: Any) -> Any:
    """Find a presenter in scene-based and legacy iOS app templates."""
    window = None
    try:
        window = app.keyWindow
    except Exception:
        pass

    if window is None:
        try:
            windows = list(app.windows or [])
            for candidate in windows:
                if _window_is_key(candidate):
                    window = candidate
                    break
            if window is None and windows:
                window = windows[0]
        except Exception:
            pass

    if window is None:
        return None

    try:
        top = window.rootViewController
    except Exception:
        return None

    # If the root is a navigation controller, presenting from the visible
    # controller gives UIKit the most specific presentation context.
    try:
        visible = getattr(top, "visibleViewController", None)
        if visible is not None:
            top = visible
    except Exception:
        pass

    while top is not None:
        try:
            presented = top.presentedViewController
        except Exception:
            break
        if presented is None:
            break
        top = presented
    return top


def _present_alert(
    *,
    title: str,
    message: Optional[str],
    buttons: List[Dict[str, Any]],
    style: str = "alert",
    on_result: Callable[[int], None] = lambda _idx: None,
) -> None:
    """Present a UIAlertController of the given style.

    Safe to call from any thread — the UIKit work is automatically
    marshalled to the main thread via
    [`pythonnative.runtime.call_on_main_thread`][pythonnative.runtime.call_on_main_thread].
    Returns immediately; the alert appears on the next main-loop tick.

    ``buttons`` is a list of ``{"label": str, "style":
    "default"|"cancel"|"destructive"}`` dicts (no ``on_press``). When
    the user picks button ``i`` the helper invokes ``on_result(i)``
    exactly once. A dismiss (e.g. swipe-to-cancel on iPad) delivers
    ``-1``. ``on_result`` always runs on the main thread; if it needs
    to wake an asyncio.Future, use
    [`pythonnative.runtime.resolve_future`][pythonnative.runtime.resolve_future]
    to hop back onto the loop thread.
    """
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
            UIAlertController = ObjCClass("UIAlertController")
            UIAlertAction = ObjCClass("UIAlertAction")
            UIApplication = ObjCClass("UIApplication")
            ctrl = UIAlertController.alertControllerWithTitle_message_preferredStyle_(
                str(title or ""),
                str(message) if message is not None else None,
                0 if style == "alert" else 1,
            )
            button_specs = buttons or [{"label": "OK", "style": "default"}]

            for i, spec in enumerate(button_specs):
                label = str(spec.get("label", "OK"))
                kind = spec.get("style", "default")
                kind_int = {"default": 0, "cancel": 1, "destructive": 2}.get(kind, 0)

                def make_handler(button_index: int) -> Any:
                    def _on_action(action: _ct.c_void_p) -> None:  # noqa: ARG001
                        _deliver(button_index)

                    return _on_action

                action = UIAlertAction.actionWithTitle_style_handler_(
                    label,
                    kind_int,
                    make_handler(i),
                )
                ctrl.addAction_(action)
            top = _top_view_controller_for_alert(UIApplication.sharedApplication)
            if top is not None:
                top.presentViewController_animated_completion_(ctrl, True, None)
            else:
                _deliver(-1)
        except Exception:
            _deliver(-1)

    call_on_main_thread(_present_on_main)


# ======================================================================
# Picker — native dropdown / select widget
# ======================================================================
#
# The PythonNative `Picker` element renders as a `UIButton` whose tap
# presents a native action sheet (``UIAlertController``) listing the
# options. Selecting a row fires ``on_change(value)``. Action sheets
# are the standard iOS dropdown pattern for a small-to-medium set of
# choices; for very large lists, paginate or use a custom navigator.


_pn_picker_state: dict = {}
# Maps ``id(target)`` -> ``id(button)`` so the single shared
# ``_PNPickerTarget`` class can look up per-instance picker state on tap.
_pn_picker_target_to_button: dict = {}


def _picker_button_title(props: Dict[str, Any]) -> str:
    """Render the selected label, falling back to the placeholder."""
    items = props.get("items") or []
    selected = props.get("value")
    for item in items:
        if isinstance(item, dict) and item.get("value") == selected:
            return str(item.get("label", item.get("value", "")))
    return str(props.get("placeholder") or "Select…")


class _PNPickerTarget(NSObject):  # type: ignore[valid-type]
    """Shared ObjC target for every Picker button.

    Defined exactly once at module load. ``UIButton`` instances each
    retain their own ``_PNPickerTarget.new()`` instance, and the per-
    instance picker state is looked up in
    :data:`_pn_picker_target_to_button` / :data:`_pn_picker_state`.
    """

    @objc_method
    def onTap_(self, sender: object) -> None:  # noqa: ARG002
        bid = _pn_picker_target_to_button.get(id(self))
        if bid is None:
            return
        state = _pn_picker_state.get(bid)
        if not state:
            return
        items = list(state.get("items") or [])
        on_change = state.get("on_change")
        placeholder = state.get("placeholder") or "Select…"

        def _make_press(value: Any) -> Callable[[], None]:
            def _press() -> None:
                if on_change is not None:
                    try:
                        on_change(value)
                    except Exception:
                        pass

            return _press

        buttons: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", item.get("value", "")))
            buttons.append({"label": label, "on_press": _make_press(item.get("value"))})
        buttons.append({"label": "Cancel", "style": "cancel"})
        _present_alert(title=str(placeholder), message=None, buttons=buttons, style="action_sheet")


def _picker_make_target(button_id: int) -> Any:
    """Build a retained ObjC target wired to ``button_id``'s picker state."""
    target = _PNPickerTarget.new()
    target.retain()
    _pn_retained_views.append(target)
    _pn_picker_target_to_button[id(target)] = button_id
    return target


class PickerHandler(IOSViewHandler):
    """``Picker`` element handler — native action-sheet dropdown."""

    def create(self, props: Dict[str, Any]) -> Any:
        UIButton = ObjCClass("UIButton")
        btn = UIButton.buttonWithType_(1)  # UIButtonTypeSystem
        btn.setTranslatesAutoresizingMaskIntoConstraints_(True)
        bid = id(btn)
        _pn_picker_state[bid] = {
            "items": list(props.get("items") or []),
            "on_change": props.get("on_change"),
            "placeholder": props.get("placeholder") or "Select…",
            "value": props.get("value"),
        }
        target = _picker_make_target(bid)
        _pn_picker_state[bid]["target"] = target
        btn.addTarget_action_forControlEvents_(target, SEL("onTap:"), 1 << 6)  # touchUpInside
        btn.setTitle_forState_(_picker_button_title(props), 0)
        _apply_accessibility(btn, props)
        return btn

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        bid = id(native_view)
        state = _pn_picker_state.setdefault(bid, {})
        for key in ("items", "on_change", "placeholder", "value"):
            if key in changed:
                state[key] = changed[key]
        native_view.setTitle_forState_(_picker_button_title(state), 0)
        _apply_accessibility(native_view, changed)

    def measure_intrinsic(self, native_view: Any, max_width: float, max_height: float) -> Tuple[float, float]:
        try:
            mw = _safe_max(max_width, fallback=10000.0)
            mh = _safe_max(max_height, fallback=10000.0)
            size = native_view.sizeThatFits_((mw, mh))
            return (float(size.width) + 16.0, float(size.height) + 8.0)
        except Exception:
            return (120.0, 36.0)


# ======================================================================
# Registration
# ======================================================================


def register_handlers(registry: Any) -> None:
    """Register all iOS view handlers with the given registry."""
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
    "IOSViewHandler",
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


# Avoid an unused-import warning from threading; it's available for
# future delegate use (e.g., Camera/Location callbacks).
_ = threading
