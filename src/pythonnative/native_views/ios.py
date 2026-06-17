"""iOS native-view handlers (rubicon-objc).

Each handler class maps a PythonNative element type to a UIKit view,
implementing view creation, property updates, child management, and
frame application. Handlers are registered with the
[`NativeViewRegistry`][pythonnative.native_views.NativeViewRegistry] by
[`register_handlers`][pythonnative.native_views.ios.register_handlers].

**Batched protocol**: the registry applies the reconciler's mutation
ops; handlers receive callable-free props. User callbacks never reach
this module; every interaction (taps, text edits, scrolls, gestures)
is forwarded through
[`dispatch_event`][pythonnative.events.dispatch_event] keyed by the
view's reconciler-assigned tag.

**Layout** is owned by the pure-Python flex engine in
`pythonnative.layout`: container handlers create plain `UIView`s, the
engine computes per-child frames in points, and
[`set_frame`][pythonnative.native_views.ios.IOSViewHandler.set_frame]
applies those frames via UIKit's classic ``frame`` property (with Auto
Layout disabled).

**Gestures** attach real ``UIGestureRecognizer`` instances (pan, pinch,
rotation, tap, long-press, swipe) configured from the serialized
gesture specs, so recognition runs fully natively.

**Animations**: ``timing`` and ``spring`` specs are driven by UIKit
block animations with completion callbacks reported back through
``pythonnative.animated.native_animation_completed``; ``decay`` falls
back to the Python ticker.

This module is only imported on iOS at runtime. Desktop tests inject a
mock registry via
[`set_registry`][pythonnative.native_views.set_registry] and never
trigger this import path.
"""

import ctypes as _ct
import math
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from rubicon.objc import SEL, ObjCClass, ObjCInstance, objc_method

from ..events import dispatch_event, event_names
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
# Tag table (ObjC pointer -> reconciler tag -> per-view state)
# ======================================================================

_view_tags: Dict[int, int] = {}
_view_state: Dict[int, Dict[str, Any]] = {}


def _remember(view: Any, tag: int) -> None:
    ptr = _objc_ptr(view)
    if ptr is not None:
        _view_tags[ptr] = tag
    _view_state[tag] = {"props": {}}


def _tag_of(view: Any) -> Optional[int]:
    ptr = _objc_ptr(view)
    if ptr is None:
        return None
    return _view_tags.get(ptr)


def _state_of(view: Any) -> Dict[str, Any]:
    tag = _tag_of(view)
    if tag is None:
        return {}
    return _view_state.setdefault(tag, {"props": {}})


def _forget(view: Any) -> None:
    ptr = _objc_ptr(view)
    if ptr is None:
        return
    tag = _view_tags.pop(ptr, None)
    if tag is not None:
        _view_state.pop(tag, None)


def _fire(view: Any, name: str, *args: Any) -> bool:
    """Dispatch event ``name`` for ``view`` through the tag registry."""
    tag = _tag_of(view)
    if tag is None:
        return False
    return dispatch_event(tag, name, *args)


def _fire_ptr(view_ptr: int, name: str, *args: Any) -> bool:
    """Dispatch event ``name`` for the raw ObjC pointer ``view_ptr``."""
    tag = _view_tags.get(int(view_ptr or 0))
    if tag is None:
        return False
    return dispatch_event(tag, name, *args)


def _has_event(view: Any, name: str) -> bool:
    """Whether the element wired a callback named ``name`` this render."""
    merged = _state_of(view).get("props") or {}
    return name in event_names(merged)


# ======================================================================
# Raw libobjc helpers
# ======================================================================
#
# rubicon-objc's ``@objc_method`` FFI bridge is unreliable on iOS arm64
# for some delegate callback shapes, in particular when UIKit passes
# tagged pointers (e.g. NSIndexPath) or invokes selectors that return
# objects, the FFI closure ends up in CPython's ``_ctypes.O_get`` and
# crashes on bogus PyObject* dereferences.
#
# These helpers let us bypass rubicon-objc entirely: allocate a brand
# new ObjC class via ``objc_allocateClassPair``, attach plain
# CFUNCTYPE-wrapped Python functions as ``IMP``s, and dispatch via
# ``objc_msgSend``. Every delegate that takes ObjC object arguments
# beyond plain integers should use this pattern (UITabBar's selection
# delegate and UIScrollView's scroll delegate both do).

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
_SEL_TAG = _sel_reg(b"tag")
_SEL_TEXT = _sel_reg(b"text")
_SEL_UTF8STRING = _sel_reg(b"UTF8String")
_SEL_ADD_TARGET_ACTION_EVENTS = _sel_reg(b"addTarget:action:forControlEvents:")
_SEL_ON_EDIT = _sel_reg(b"onEdit:")
_SEL_ON_SUBMIT = _sel_reg(b"onSubmit:")
_SEL_RESIGN_FIRST_RESPONDER = _sel_reg(b"resignFirstResponder")
_SEL_TEXT_FIELD_SHOULD_RETURN = _sel_reg(b"textFieldShouldReturn:")
_SEL_TEXT_FIELD_DID_BEGIN = _sel_reg(b"textFieldDidBeginEditing:")
_SEL_TEXT_FIELD_DID_END = _sel_reg(b"textFieldDidEndEditing:")
_SEL_TEXT_VIEW_DID_BEGIN = _sel_reg(b"textViewDidBeginEditing:")
_SEL_TEXT_VIEW_DID_END = _sel_reg(b"textViewDidEndEditing:")
_SEL_TEXT_VIEW_DID_CHANGE = _sel_reg(b"textViewDidChange:")

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
    ct = _ct

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
    coregraphics.CGAffineTransformRotate.restype = CGAffineTransform
    coregraphics.CGAffineTransformRotate.argtypes = [CGAffineTransform, ct.c_double]
    coregraphics.CGAffineTransformScale.restype = CGAffineTransform
    coregraphics.CGAffineTransformScale.argtypes = [CGAffineTransform, ct.c_double, ct.c_double]
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
                f"[set_transform:nan] spec={spec!r} -> (a={a!r}, b={b!r}, c={c!r}, d={d!r}, tx={tx!r}, ty={ty!r})",
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


# ======================================================================
# Retention + shared targets
# ======================================================================

_pn_retained_views: list = []


# ======================================================================
# Simultaneous-recognition gesture delegate (raw libobjc)
# ======================================================================
#
# All PythonNative recognizers on a view should recognize together
# (press feedback + pan + pinch...), matching the GestureArbiter's
# semantics on Android/desktop. UIKit defaults to exclusivity, so every
# recognizer we create gets this delegate, which answers YES to
# ``gestureRecognizer:shouldRecognizeSimultaneouslyWithGestureRecognizer:``.

_GESTURE_SIMUL_TYPE = _ct.CFUNCTYPE(_ct.c_bool, _ct.c_void_p, _ct.c_void_p, _ct.c_void_p, _ct.c_void_p)


def _gesture_simul_imp(self_ptr: int, cmd_ptr: int, g1_ptr: int, g2_ptr: int) -> bool:
    return True


_gesture_simul_imp_ref = _GESTURE_SIMUL_TYPE(_gesture_simul_imp)

_PN_GESTURE_DELEGATE_CLS = _alloc_cls(_NS_OBJECT_CLS, b"_PNGestureDelegateCTypes", 0)
if _PN_GESTURE_DELEGATE_CLS:
    _add_method(
        _PN_GESTURE_DELEGATE_CLS,
        _sel_reg(b"gestureRecognizer:shouldRecognizeSimultaneouslyWithGestureRecognizer:"),
        _ct.cast(_gesture_simul_imp_ref, _ct.c_void_p),
        b"c@:@@",
    )
    _reg_cls(_PN_GESTURE_DELEGATE_CLS)

_pn_gesture_delegate_ptr: Any = None


def _shared_gesture_delegate_ptr() -> Any:
    global _pn_gesture_delegate_ptr
    if _pn_gesture_delegate_ptr is None and _PN_GESTURE_DELEGATE_CLS:
        _objc_msgSend.restype = _ct.c_void_p
        _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p]
        raw = _objc_msgSend(_PN_GESTURE_DELEGATE_CLS, _SEL_ALLOC)
        raw = _objc_msgSend(raw, _SEL_INIT)
        raw = _objc_msgSend(raw, _SEL_RETAIN)
        _pn_gesture_delegate_ptr = raw
    return _pn_gesture_delegate_ptr


def _set_recognizer_delegate(recognizer: Any) -> None:
    delegate = _shared_gesture_delegate_ptr()
    if delegate is None:
        return
    try:
        _objc_msgSend.restype = None
        _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p, _ct.c_void_p]
        rec_ptr = recognizer.ptr if hasattr(recognizer, "ptr") else recognizer
        _objc_msgSend(rec_ptr, _SEL_SET_DELEGATE, delegate)
    except Exception:
        pass


# ======================================================================
# Native gesture wiring (UIGestureRecognizer -> dispatch_event)
# ======================================================================
#
# Recognizer *actions* must not go through rubicon's ``@objc_method``
# bridge: on iOS 18.x the action invocation dies inside UIKit/rubicon
# marshaling (``NSMapGet: map table argument is NULL``) and never
# reaches Python. Exactly like the scroll/tab-bar delegates, we route
# every action through one raw libobjc target class whose CFUNCTYPE IMP
# receives the recognizer *pointer* and looks up a Python closure keyed
# by that pointer. The closure then reads state/location off the
# retained rubicon recognizer object (outbound rubicon calls are fine).

# Maps recognizer ptr -> zero-arg Python handler closure.
_pn_action_handlers: Dict[int, Any] = {}

_ACTION_IMP_TYPE = _ct.CFUNCTYPE(None, _ct.c_void_p, _ct.c_void_p, _ct.c_void_p)


def _action_imp(_self_ptr: int, _cmd_ptr: int, sender_ptr: int) -> None:
    """Raw C callback for every PythonNative recognizer action."""
    handler = _pn_action_handlers.get(int(sender_ptr or 0))
    if handler is None:
        return
    try:
        handler()
    except Exception:
        pass


_action_imp_ref = _ACTION_IMP_TYPE(_action_imp)

_SEL_ON_ACTION = _sel_reg(b"onPNAction:")

_PN_ACTION_TARGET_CLS = _alloc_cls(_NS_OBJECT_CLS, b"_PNActionTargetCTypes", 0)
if _PN_ACTION_TARGET_CLS:
    _add_method(
        _PN_ACTION_TARGET_CLS,
        _SEL_ON_ACTION,
        _ct.cast(_action_imp_ref, _ct.c_void_p),
        b"v@:@",
    )
    _reg_cls(_PN_ACTION_TARGET_CLS)

_pn_action_target_ptr: Any = None


def _shared_action_target_ptr() -> Any:
    global _pn_action_target_ptr
    if _pn_action_target_ptr is None and _PN_ACTION_TARGET_CLS:
        _objc_msgSend.restype = _ct.c_void_p
        _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p]
        raw = _objc_msgSend(_PN_ACTION_TARGET_CLS, _SEL_ALLOC)
        raw = _objc_msgSend(raw, _SEL_INIT)
        raw = _objc_msgSend(raw, _SEL_RETAIN)
        _pn_action_target_ptr = raw
    return _pn_action_target_ptr


def _recognizer_ptr(rec: Any) -> int:
    ptr = rec.ptr if hasattr(rec, "ptr") else rec
    return int(getattr(ptr, "value", ptr) or 0)


def _register_action(rec: Any, handler: Any) -> None:
    """Bind ``handler`` to ``rec`` via the shared raw action target."""
    target_ptr = _shared_action_target_ptr()
    if target_ptr is None:
        return
    _objc_msgSend.restype = None
    _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p, _ct.c_void_p, _ct.c_void_p]
    rec_ptr = rec.ptr if hasattr(rec, "ptr") else rec
    _objc_msgSend(rec_ptr, _sel_reg(b"addTarget:action:"), target_ptr, _SEL_ON_ACTION)
    _pn_action_handlers[_recognizer_ptr(rec)] = handler


def _register_control_action(control: Any, events_mask: int, handler: Any) -> None:
    """Bind ``handler`` to a ``UIControl`` event via the shared raw target.

    The UIControl counterpart of ``_register_action``: control events
    (TouchUpInside, ValueChanged, ...) must not be delivered through
    rubicon's ``@objc_method`` bridge either; the trampoline's ``sender``
    marshaling is what crashed UISwitch toggles on iOS 18.x (the action
    fired, but touching the marshaled ``sender`` segfaulted). The raw IMP
    receives only the sender *pointer*; ``handler`` closures read any
    control state they need from the retained rubicon wrapper they
    captured at wiring time (outbound rubicon calls are fine).
    """
    target_ptr = _shared_action_target_ptr()
    if target_ptr is None:
        return
    _objc_msgSend.restype = None
    _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p, _ct.c_void_p, _ct.c_ulong]
    ctl_ptr = control.ptr if hasattr(control, "ptr") else control
    _objc_msgSend(ctl_ptr, _SEL_ADD_TARGET_ACTION_EVENTS, target_ptr, _SEL_ON_ACTION, events_mask)
    _pn_action_handlers[_recognizer_ptr(control)] = handler


# UIGestureRecognizerState -> GestureEvent.state
_GSTATE = {1: "began", 2: "changed", 3: "ended", 4: "cancelled", 5: "cancelled"}

_SWIPE_DIRECTIONS = {"right": 1, "left": 2, "up": 4, "down": 8}


def _make_gesture_handler(
    rec: Any,
    view: Any,
    kind: str,
    index: int,
    direction: Optional[str] = None,
) -> Any:
    """Build the action closure emitting one ``gesture:<i>`` payload."""

    def handler() -> None:
        try:
            raw_state = int(rec.state)
        except Exception:
            raw_state = 3
        state = _GSTATE.get(raw_state)
        if state is None:
            return

        payload: Dict[str, Any] = {"kind": kind, "state": state}
        try:
            location = rec.locationInView_(view)
            payload["x"] = float(location.x)
            payload["y"] = float(location.y)
        except Exception:
            pass
        try:
            payload["pointer_count"] = int(rec.numberOfTouches)
        except Exception:
            pass

        if kind == "pan":
            try:
                translation = rec.translationInView_(view)
                payload["translation_x"] = float(translation.x)
                payload["translation_y"] = float(translation.y)
                velocity = rec.velocityInView_(view)
                payload["velocity_x"] = float(velocity.x)
                payload["velocity_y"] = float(velocity.y)
            except Exception:
                pass
        elif kind == "pinch":
            try:
                payload["scale"] = float(rec.scale)
            except Exception:
                pass
        elif kind == "rotation":
            try:
                payload["rotation"] = float(rec.rotation)
            except Exception:
                pass
        elif kind == "swipe":
            # Discrete: UIKit only calls us on recognition, and only the
            # recognizer whose direction matched fires, so the bound
            # per-recognizer direction is the actual swipe direction.
            payload["state"] = "ended"
            payload["direction"] = direction
        elif kind == "tap":
            payload["state"] = "ended"

        _fire(view, f"gesture:{index}", payload)

    return handler


def _make_recognizer(kind: str, spec: Dict[str, Any]) -> List[Tuple[Any, Optional[str]]]:
    """Build the UIGestureRecognizer(s) for one serialized gesture spec.

    Swipe with ``direction="any"`` needs one recognizer per direction
    (UIKit constraint), so this returns ``(recognizer, direction)``
    pairs; ``direction`` is ``None`` for non-swipe kinds.
    """
    out: List[Tuple[Any, Optional[str]]] = []
    if kind == "tap":
        rec = ObjCClass("UITapGestureRecognizer").alloc().init()
        try:
            rec.setNumberOfTapsRequired_(max(1, int(spec.get("n_taps", 1))))
        except Exception:
            pass
        out.append((rec, None))
    elif kind == "long_press":
        rec = ObjCClass("UILongPressGestureRecognizer").alloc().init()
        try:
            rec.setMinimumPressDuration_(float(spec.get("min_duration_ms", 500.0)) / 1000.0)
            rec.setAllowableMovement_(float(spec.get("max_distance", 12.0)))
        except Exception:
            pass
        out.append((rec, None))
    elif kind == "pan":
        rec = ObjCClass("UIPanGestureRecognizer").alloc().init()
        try:
            rec.setMinimumNumberOfTouches_(max(1, int(spec.get("min_pointers", 1))))
        except Exception:
            pass
        out.append((rec, None))
    elif kind == "swipe":
        direction = str(spec.get("direction", "any"))
        directions = [direction] if direction in _SWIPE_DIRECTIONS else list(_SWIPE_DIRECTIONS)
        for d in directions:
            rec = ObjCClass("UISwipeGestureRecognizer").alloc().init()
            try:
                rec.setDirection_(_SWIPE_DIRECTIONS[d])
            except Exception:
                pass
            out.append((rec, d))
    elif kind == "pinch":
        out.append((ObjCClass("UIPinchGestureRecognizer").alloc().init(), None))
    elif kind == "rotation":
        out.append((ObjCClass("UIRotationGestureRecognizer").alloc().init(), None))
    return out


def _wire_gestures(view: Any, specs: Any) -> None:
    """Attach native recognizers for the serialized gesture specs.

    Re-wiring on update removes previously attached PythonNative
    recognizers first (configuration changes are rare; correctness
    beats incremental patching here).
    """
    state = _state_of(view)
    for rec in state.get("gesture_recognizers") or []:
        try:
            view.removeGestureRecognizer_(rec)
        except Exception:
            pass
        _pn_action_handlers.pop(_recognizer_ptr(rec), None)
    state["gesture_recognizers"] = []
    if not isinstance(specs, (list, tuple)) or not specs:
        return

    try:
        view.setUserInteractionEnabled_(True)
    except Exception:
        pass

    recognizers: List[Any] = []
    for i, spec in enumerate(specs):
        if not isinstance(spec, dict):
            continue
        kind = str(spec.get("kind", ""))
        if not kind:
            continue
        for rec, direction in _make_recognizer(kind, spec):
            try:
                rec.setCancelsTouchesInView_(False)
            except Exception:
                pass
            _set_recognizer_delegate(rec)
            try:
                view.addGestureRecognizer_(rec)
                rec.retain()
                recognizers.append(rec)
            except Exception:
                continue
            _register_action(rec, _make_gesture_handler(rec, view, kind, i, direction))

    state["gesture_recognizers"] = recognizers


# ======================================================================
# Native-driven animations (UIView block animations)
# ======================================================================

_native_anims: Dict[int, Dict[str, Any]] = {}


def _is_main_thread() -> bool:
    return threading.current_thread() is threading.main_thread()


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
        spec = {prop: value}

        def _apply(view: Any) -> None:
            _apply_transform(view, {"transform": [spec]})

        return _apply
    return None


def _spring_parameters(spec: Dict[str, Any]) -> Tuple[float, float, float]:
    """Translate physics params into UIKit's (duration, damping_ratio, velocity).

    UIKit's spring API takes a damping *ratio* (0..1) and a velocity
    normalized to the total travel distance. We derive both from the
    stiffness/damping/mass spec and approximate the settle duration
    from the envelope decay.
    """
    stiffness = max(1e-3, float(spec.get("stiffness", 100.0)))
    damping = max(1e-3, float(spec.get("damping", 10.0)))
    mass = max(1e-3, float(spec.get("mass", 1.0)))
    omega0 = math.sqrt(stiffness / mass)
    zeta = damping / (2.0 * math.sqrt(stiffness * mass))
    damping_ratio = max(0.05, min(1.0, zeta))
    if zeta < 1.0:
        duration = min(10.0, max(0.15, 4.0 / max(0.05, zeta * omega0)))
    else:
        duration = min(10.0, max(0.15, 4.0 / omega0))
    distance = abs(float(spec.get("to", 0.0)) - float(spec.get("from", 0.0)))
    v0 = float(spec.get("initial_velocity", 0.0))
    norm_velocity = (v0 / distance) if distance > 1e-9 else 0.0
    return duration, damping_ratio, norm_velocity


_EASING_OPTIONS = {
    "linear": 1 << 16,  # UIViewAnimationOptionCurveLinear
    "ease_in": 1 << 17,
    "ease_out": 1 << 18,
    "ease_in_out": 0,
    "ease": 0,
}


def _start_native_animation(view: Any, anim_id: int, prop_name: str, spec: Dict[str, Any]) -> bool:
    """Run a ``timing`` / ``spring`` spec as a UIView block animation."""
    applier_from = _animated_applier_for(prop_name, spec.get("from"))
    applier_to = _animated_applier_for(prop_name, spec.get("to"))
    if applier_to is None:
        return False
    UIView = ObjCClass("UIView")
    kind = str(spec.get("kind", "timing"))

    def _completion(finished: bool) -> None:
        _native_anims.pop(anim_id, None)
        try:
            from ..animated import native_animation_completed

            native_animation_completed(anim_id, bool(finished))
        except Exception:
            pass

    def _animations() -> None:
        try:
            applier_to(view)
        except Exception:
            pass

    try:
        # Snap to the starting value so the animation covers the full
        # declared range even if the view was somewhere else.
        if applier_from is not None:
            applier_from(view)
        _native_anims[anim_id] = {"view": view, "prop": prop_name}
        if kind == "spring":
            duration, damping_ratio, velocity = _spring_parameters(spec)
            UIView.animateWithDuration_delay_usingSpringWithDamping_initialSpringVelocity_options_animations_completion_(
                duration,
                0.0,
                damping_ratio,
                velocity,
                1 << 1,  # AllowUserInteraction
                _animations,
                _completion,
            )
        else:
            duration = max(0.0, float(spec.get("duration_ms", 300.0))) / 1000.0
            options = _EASING_OPTIONS.get(str(spec.get("easing", "ease_in_out")), 0) | (1 << 1)
            UIView.animateWithDuration_delay_options_animations_completion_(
                duration,
                float(spec.get("delay_ms", 0.0) or 0.0) / 1000.0,
                options,
                _animations,
                _completion,
            )
        return True
    except Exception:
        _native_anims.pop(anim_id, None)
        return False


# ======================================================================
# Base class with shared frame/measure/animation implementations
# ======================================================================


class IOSViewHandler(ViewHandler):
    """Base class providing the shared protocol implementation.

    Subclasses implement
    [`_build`][pythonnative.native_views.ios.IOSViewHandler._build]
    (construct the UIKit view) and
    [`_apply`][pythonnative.native_views.ios.IOSViewHandler._apply]
    (apply visual props); the base class owns tag registration,
    gesture wiring, frame application via classic ``CGRect``
    positioning (Auto Layout off), intrinsic measurement via
    ``sizeThatFits:``, and the animation hooks.
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
        state = _state_of(native_view)
        for rec in state.get("gesture_recognizers") or []:
            _pn_action_handlers.pop(_recognizer_ptr(rec), None)
        # Controls register their own pointer as the action-handler key
        # (see _register_control_action); drop it with the view.
        _pn_action_handlers.pop(_recognizer_ptr(native_view), None)
        try:
            native_view.removeFromSuperview()
        except Exception:
            pass
        _forget(native_view)

    def _build(self, props: Dict[str, Any]) -> Any:
        raise NotImplementedError

    def _apply(self, view: Any, props: Dict[str, Any], initial: bool) -> None:
        _apply_common_visual(view, props)

    def _teardown(self, native_view: Any) -> None:
        """Subclass hook for extra cleanup before the view is released."""

    def insert_child(self, parent: Any, child: Any, index: int) -> None:
        try:
            child.setTranslatesAutoresizingMaskIntoConstraints_(True)
        except Exception:
            pass
        try:
            count = len(list(parent.subviews or []))
        except Exception:
            count = index
        try:
            parent.insertSubview_atIndex_(child, max(0, min(index, count)))
        except Exception:
            try:
                parent.addSubview_(child)
            except Exception:
                pass

    def remove_child(self, parent: Any, child: Any) -> None:
        try:
            child.removeFromSuperview()
        except Exception:
            pass

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

    def set_animated_property(self, native_view: Any, prop_name: str, value: Any) -> None:
        """Apply one Python-driven animation frame immediately."""
        if native_view is None:
            return
        try:
            applier = _animated_applier_for(prop_name, value)
        except Exception:
            return
        if applier is None:
            return
        try:
            applier(native_view)
        except Exception:
            pass

    def start_animation(
        self,
        native_view: Any,
        anim_id: int,
        prop_name: str,
        spec: Dict[str, Any],
    ) -> bool:
        """Drive ``timing`` / ``spring`` specs with UIKit block animations.

        ``decay`` (and any unknown kind) returns ``False`` so the Python
        ticker integrates the exact physics. Off-main-thread starts also
        fall back; UIKit animation APIs are main-thread-only.
        """
        if native_view is None or not isinstance(spec, dict):
            return False
        if str(spec.get("kind", "")) not in ("timing", "spring"):
            return False
        if not _is_main_thread():
            return False
        return _start_native_animation(native_view, anim_id, prop_name, spec)

    def cancel_animation(self, native_view: Any, anim_id: int) -> Any:
        entry = _native_anims.pop(anim_id, None)
        if entry is None:
            return None
        view = entry.get("view")
        prop = str(entry.get("prop", ""))
        value: Any = None
        try:
            presentation = view.layer.presentationLayer()
            if presentation is not None and prop == "opacity":
                value = float(presentation.opacity)
        except Exception:
            value = None
        try:
            view.layer.removeAllAnimations()
        except Exception:
            pass
        return value


# ======================================================================
# Flex container handler (shared by Column, Row, View)
# ======================================================================


class FlexContainerHandler(IOSViewHandler):
    """Container for flex layout, a bare `UIView`.

    All flex semantics (direction, alignment, distribution, padding)
    are computed by the layout engine and applied via
    [`set_frame`][pythonnative.native_views.ios.IOSViewHandler.set_frame].
    """

    def _build(self, props: Dict[str, Any]) -> Any:
        v = ObjCClass("UIView").alloc().init()
        v.setTranslatesAutoresizingMaskIntoConstraints_(True)
        return v


# ======================================================================
# Leaf handlers
# ======================================================================


class TextHandler(IOSViewHandler):
    def _build(self, props: Dict[str, Any]) -> Any:
        label = ObjCClass("UILabel").alloc().init()
        label.setNumberOfLines_(0)
        label.setTranslatesAutoresizingMaskIntoConstraints_(True)
        return label

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

    def _apply(self, label: Any, props: Dict[str, Any], initial: bool) -> None:
        if "text" in props:
            label.setText_(str(props["text"]) if props["text"] is not None else "")
        # Font requires combining size + weight + family + italic + bold.
        font_keys_present = any(k in props for k in ("font_size", "font_weight", "font_family", "italic", "bold"))
        if font_keys_present:
            merged = _state_of(label).get("props") or props
            current = label.font
            try:
                current_size = float(current.pointSize) if current is not None else 17.0
            except Exception:
                current_size = 17.0
            size = float(merged.get("font_size", current_size)) if merged.get("font_size") is not None else current_size
            weight = merged.get("font_weight")
            if weight is None and merged.get("bold"):
                weight = "bold"
            family = merged.get("font_family")
            italic = bool(merged.get("italic"))
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
            merged = _state_of(label).get("props") or props
            self._apply_attributed(label, merged)
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
    def _build(self, props: Dict[str, Any]) -> Any:
        # ``UIButtonTypeSystem`` (1) gives us a properly-sized button
        # with intrinsicContentSize derived from the title; the default
        # ``UIButtonTypeCustom`` returns CGSizeZero from sizeThatFits_,
        # which makes the button collapse to 0×0 under the layout engine.
        btn = ObjCClass("UIButton").buttonWithType_(1)
        btn.setTranslatesAutoresizingMaskIntoConstraints_(True)
        btn.retain()
        _pn_retained_views.append(btn)
        _register_control_action(btn, 1 << 6, lambda: _fire(btn, "on_click"))  # TouchUpInside
        return btn

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

    def _apply(self, btn: Any, props: Dict[str, Any], initial: bool) -> None:
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


# ``scrollViewDidScroll:`` hands the delegate a ``UIScrollView*``. rubicon's
# ``@objc_method`` FFI bridge is unreliable for delegate callbacks that take
# ObjC object arguments on arm64 (see the module header note); on the arm64
# simulator the callback simply never reaches Python, so ``on_scroll`` would
# silently never fire. Exactly like the UITabBar delegate, we therefore build
# the delegate class with raw libobjc and dispatch through a CFUNCTYPE IMP.
#
# We read ``contentOffset`` off the *retained rubicon* scroll view we already
# hold (keyed by the delegate instance pointer) rather than off the raw
# callback argument: that sidesteps both the object-arg marshaling issue and
# the CGPoint struct-return ABI quirks of calling ``contentOffset`` via raw
# ``objc_msgSend``.
_pn_scroll_imp_map: Dict[int, Dict[str, Any]] = {}

_SCROLL_IMP_TYPE = _ct.CFUNCTYPE(None, _ct.c_void_p, _ct.c_void_p, _ct.c_void_p)


def _scroll_did_scroll_imp(self_ptr: int, _cmd_ptr: int, _scroll_view_ptr: int) -> None:
    """Raw C callback for ``scrollViewDidScroll:``."""
    info = _pn_scroll_imp_map.get(self_ptr)
    if not info:
        return
    sv = info.get("sv")
    if sv is None:
        return
    try:
        offset = sv.contentOffset
        x = float(offset.x)
        y = float(offset.y)
    except Exception:
        return
    _fire(sv, "on_scroll", {"x": x, "y": y})


_scroll_imp_ref = _SCROLL_IMP_TYPE(_scroll_did_scroll_imp)

_PN_SCROLL_DELEGATE_CLS = _alloc_cls(_NS_OBJECT_CLS, b"_PNScrollDelegateCTypes", 0)
if _PN_SCROLL_DELEGATE_CLS:
    _add_method(
        _PN_SCROLL_DELEGATE_CLS,
        _sel_reg(b"scrollViewDidScroll:"),
        _ct.cast(_scroll_imp_ref, _ct.c_void_p),
        b"v@:@",
    )
    _reg_cls(_PN_SCROLL_DELEGATE_CLS)


class ScrollViewHandler(IOSViewHandler):
    """Scroll container: wraps a single child whose height is unbounded.

    The child is positioned by the layout engine using its natural
    content height. The shared frame applier expands the parent
    `UIScrollView.contentSize` whenever a child frame extends beyond
    the visible bounds.

    Scroll offsets are reported as ``on_scroll`` events with a
    ``{"x": pts, "y": pts}`` payload. Imperative commands:
    ``scroll_to_offset`` / ``scroll_to_end`` / ``get_scroll_offset``.

    When ``refresh_control`` is provided in props, a
    ``UIRefreshControl`` is attached and pull-to-refresh fires the
    ``on_refresh`` event.
    """

    def _build(self, props: Dict[str, Any]) -> Any:
        sv = ObjCClass("UIScrollView").alloc().init()
        sv.setTranslatesAutoresizingMaskIntoConstraints_(True)
        self._wire_scroll(sv)
        return sv

    def _apply(self, sv: Any, props: Dict[str, Any], initial: bool) -> None:
        _apply_common_visual(sv, props)
        if "refresh_control" in props:
            self._apply_refresh(sv, props)
        # ``shows_scroll_indicator`` is present only when False; a removed
        # prop (None) restores both indicators.
        if "shows_scroll_indicator" in props:
            show = props["shows_scroll_indicator"]
            visible = True if show is None else bool(show)
            try:
                sv.setShowsVerticalScrollIndicator_(visible)
                sv.setShowsHorizontalScrollIndicator_(visible)
            except Exception:
                pass
        if "paging_enabled" in props:
            try:
                sv.setPagingEnabled_(bool(props["paging_enabled"]))
            except Exception:
                pass
        if "bounces" in props:
            b = props["bounces"]
            try:
                sv.setBounces_(True if b is None else bool(b))
            except Exception:
                pass
        if "keyboard_dismiss_mode" in props and props["keyboard_dismiss_mode"] is not None:
            mapping = {"none": 0, "on_drag": 1, "interactive": 2}
            try:
                sv.setKeyboardDismissMode_(mapping.get(props["keyboard_dismiss_mode"], 0))
            except Exception:
                pass

    def command(self, native_view: Any, name: str, args: Dict[str, Any]) -> Any:
        if name == "scroll_to_offset":
            x = float(args.get("x", 0.0) or 0.0)
            y = float(args.get("y", 0.0) or 0.0)
            animated = args.get("animated", True) is not False
            try:
                native_view.setContentOffset_animated_((x, y), animated)
            except Exception:
                pass
            return None
        if name == "scroll_to_end":
            animated = args.get("animated", True) is not False
            try:
                content = native_view.contentSize
                bounds = native_view.bounds
                target_y = max(0.0, float(content.height) - float(bounds.size.height))
                target_x = max(0.0, float(content.width) - float(bounds.size.width))
                horizontal = float(content.width) > float(bounds.size.width) and float(content.height) <= float(
                    bounds.size.height
                )
                offset = (target_x, 0.0) if horizontal else (0.0, target_y)
                native_view.setContentOffset_animated_(offset, animated)
            except Exception:
                pass
            return None
        if name == "get_scroll_offset":
            try:
                offset = native_view.contentOffset
                return {"x": float(offset.x), "y": float(offset.y)}
            except Exception:
                return {"x": 0.0, "y": 0.0}
        return None

    def _wire_scroll(self, sv: Any) -> None:
        if not _PN_SCROLL_DELEGATE_CLS:
            return
        _objc_msgSend.restype = _ct.c_void_p
        _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p]
        d = _objc_msgSend(_PN_SCROLL_DELEGATE_CLS, _SEL_ALLOC)
        d = _objc_msgSend(d, _SEL_INIT)
        d = _objc_msgSend(d, _SEL_RETAIN)
        delegate_ptr = int(d)
        _pn_scroll_imp_map[delegate_ptr] = {"sv": sv}
        _objc_msgSend.restype = None
        _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p, _ct.c_void_p]
        sv_ptr = sv.ptr if hasattr(sv, "ptr") else sv
        _objc_msgSend(sv_ptr, _SEL_SET_DELEGATE, _ct.c_void_p(delegate_ptr))

    def _apply_refresh(self, sv: Any, props: Dict[str, Any]) -> None:
        spec = props.get("refresh_control")
        if not spec:
            # Prop removed (screen reuse can recycle this scroll view
            # for a refresh-less screen): detach so no phantom pull
            # gesture survives.
            try:
                existing = sv.refreshControl
                if existing is not None:
                    existing.endRefreshing()
                    _pn_action_handlers.pop(_recognizer_ptr(existing), None)
                    sv.setRefreshControl_(None)
                    sv.setAlwaysBounceVertical_(False)
            except Exception:
                pass
            return
        try:
            existing = sv.refreshControl
            if existing is None:
                rc = ObjCClass("UIRefreshControl").alloc().init()
                rc.retain()
                _pn_retained_views.append(rc)
                sv.setRefreshControl_(rc)
                _register_control_action(rc, 1 << 12, lambda: _fire(sv, "on_refresh"))  # ValueChanged
                # Without this, a scroll view whose content fits its
                # bounds never engages the pan gesture, making the
                # refresh control unreachable by a pull (RN's ScrollView
                # bounces vertically by default for the same reason).
                try:
                    sv.setAlwaysBounceVertical_(True)
                except Exception:
                    pass
                existing = rc
            refreshing = bool(spec.get("refreshing")) if isinstance(spec, dict) else False
            if refreshing:
                existing.beginRefreshing()
            else:
                existing.endRefreshing()
        except Exception:
            pass


class ImageHandler(IOSViewHandler):
    """`UIImageView` with async URL loading via NSURLSession."""

    def _build(self, props: Dict[str, Any]) -> Any:
        iv = ObjCClass("UIImageView").alloc().init()
        iv.setTranslatesAutoresizingMaskIntoConstraints_(True)
        iv.setClipsToBounds_(True)
        iv.setContentMode_(1)  # ScaleAspectFit
        return iv

    def _apply(self, iv: Any, props: Dict[str, Any], initial: bool) -> None:
        if "tint_color" in props and props["tint_color"] is not None:
            try:
                iv.setTintColor_(_uicolor(props["tint_color"]))
            except Exception:
                pass
        if "source" in props and props["source"]:
            self._load_source(iv, str(props["source"]))
        if "scale_type" in props and props["scale_type"]:
            # UIViewContentMode: ScaleToFill=0, ScaleAspectFit=1,
            # ScaleAspectFill=2, Center=4.
            mapping = {"cover": 2, "contain": 1, "stretch": 0, "center": 4}
            iv.setContentMode_(mapping.get(props["scale_type"], 1))
        _apply_common_visual(iv, props)

    def measure_intrinsic(
        self,
        native_view: Any,
        max_width: float,
        max_height: float,
    ) -> Tuple[float, float]:
        try:
            img = native_view.image
            if img is not None:
                size = img.size
                w, h = float(size.width), float(size.height)
                if math.isfinite(max_width) and w > max_width > 0:
                    scale = max_width / w
                    w, h = max_width, h * scale
                return (w, h)
        except Exception:
            pass
        return (0.0, 0.0)

    def _load_source(self, iv: Any, source: str) -> None:
        try:
            if source.startswith(("http://", "https://")):
                self._load_async(iv, source)
            else:
                # Bundle resource or absolute file path.
                UIImage = ObjCClass("UIImage")
                image = UIImage.imageNamed_(source)
                if image is None:
                    image = UIImage.imageWithContentsOfFile_(source)
                if image:
                    iv.setImage_(image)
        except Exception:
            pass

    def _load_async(self, iv: Any, source: str) -> None:
        """Asynchronously load a remote image off the main thread.

        Uses ``NSURLSession.sharedSession.dataTaskWithURL:completionHandler:``
        so the main thread is never blocked. The completion handler
        runs on a background queue; the image is set back on the main
        queue so UIKit accepts it without threading warnings. The
        latest requested URI wins if several loads race.
        """
        state = _state_of(iv)
        state["pending_uri"] = source
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
                            if _state_of(iv).get("pending_uri") == source:
                                iv.setImage_(image)
                        except Exception:
                            pass

                    from ..runtime import call_on_main_thread

                    call_on_main_thread(apply)
                except Exception:
                    pass

            task = session.dataTaskWithURL_completionHandler_(url, completion)
            task.resume()
        except Exception:
            pass


# ----------------------------------------------------------------------
# TextInput: raw libobjc target/delegate
# ----------------------------------------------------------------------
#
# UITextField control events and UITextField/UITextView delegate
# callbacks all pass ObjC object arguments, which rubicon's
# ``@objc_method`` trampoline handles unreliably on arm64 (see the
# module header). The change/submit/focus/blur path is therefore built
# on a raw ``PNTextFieldActionTarget`` class registered with libobjc,
# exactly like the scroll and tab-bar delegates.
#
# One target instance is allocated per input view; ``_pn_tf_target_map``
# maps the target's raw pointer (the ``self`` of every IMP) back to the
# owning input view so the IMPs can consult per-view state (suppress
# flag, max_length) and fire through the tag-based event channel.

_pn_tf_target_map: Dict[int, Any] = {}
_PN_TEXTFIELD_TARGET_CLS: Optional[int] = None
_textfield_imp_refs: List[Any] = []


def _input_text(view_ptr: int) -> str:
    """Read ``text`` from a UITextField/UITextView via raw objc_msgSend."""
    if not view_ptr:
        return ""
    try:
        _objc_msgSend.restype = _ct.c_void_p
        _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p]
        nsstring_ptr = _objc_msgSend(_ct.c_void_p(view_ptr), _SEL_TEXT)
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


def _input_state_for_target(self_ptr: int) -> Tuple[Optional[Any], Dict[str, Any]]:
    view = _pn_tf_target_map.get(int(self_ptr))
    if view is None:
        return None, {}
    return view, _state_of(view)


def _tf_on_change_imp(self_ptr: int, _cmd: int, sender_ptr: int) -> None:
    view, state = _input_state_for_target(self_ptr)
    if view is None or state.get("suppress"):
        return
    text = _input_text(int(sender_ptr or 0))
    max_length = state.get("max_length")
    if isinstance(max_length, int) and max_length >= 0 and len(text) > max_length:
        text = text[:max_length]
        state["suppress"] = True
        try:
            view.setText_(text)
        except Exception:
            pass
        finally:
            state["suppress"] = False
    _fire(view, "on_change", text)


def _tf_on_submit_imp(self_ptr: int, _cmd: int, sender_ptr: int) -> None:
    view, state = _input_state_for_target(self_ptr)
    if view is None:
        return
    _fire(view, "on_submit", _input_text(int(sender_ptr or 0)))


def _tf_should_return_imp(self_ptr: int, _cmd: int, tf_ptr: int) -> bool:
    """Dismiss the keyboard on Return (``textFieldShouldReturn:``).

    iOS doesn't dismiss the keyboard on Return by default; the standard
    pattern is for the delegate to resign first responder and return
    YES, matching React Native's TextInput behavior.
    """
    try:
        _objc_msgSend.restype = None
        _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p]
        _objc_msgSend(_ct.c_void_p(int(tf_ptr or 0)), _SEL_RESIGN_FIRST_RESPONDER)
    except Exception:
        pass
    return True


def _tf_did_begin_imp(self_ptr: int, _cmd: int, sender_ptr: int) -> None:
    view, _state = _input_state_for_target(self_ptr)
    if view is not None:
        _fire(view, "on_focus")


def _tf_did_end_imp(self_ptr: int, _cmd: int, sender_ptr: int) -> None:
    view, _state = _input_state_for_target(self_ptr)
    if view is not None:
        _fire(view, "on_blur")


def _ensure_textfield_target_class() -> Optional[int]:
    global _PN_TEXTFIELD_TARGET_CLS
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
    change_imp = action_type(_tf_on_change_imp)
    submit_imp = action_type(_tf_on_submit_imp)
    should_return_imp = bool_type(_tf_should_return_imp)
    begin_imp = action_type(_tf_did_begin_imp)
    end_imp = action_type(_tf_did_end_imp)
    # CFUNCTYPE objects must outlive the registered class.
    _textfield_imp_refs.extend([change_imp, submit_imp, should_return_imp, begin_imp, end_imp])
    _add_method(cls, _SEL_ON_EDIT, _ct.cast(change_imp, _ct.c_void_p), b"v@:@")
    _add_method(cls, _SEL_ON_SUBMIT, _ct.cast(submit_imp, _ct.c_void_p), b"v@:@")
    _add_method(cls, _SEL_TEXT_FIELD_SHOULD_RETURN, _ct.cast(should_return_imp, _ct.c_void_p), b"c@:@")
    # ``textFieldDidBeginEditing:`` / ``textViewDidBeginEditing:`` share
    # the focus IMP; the end-editing pair shares the blur IMP, and
    # ``textViewDidChange:`` shares the change IMP. The same target is
    # wired as both UITextFieldDelegate and UITextViewDelegate so every
    # event works for single- and multi-line inputs alike.
    _add_method(cls, _SEL_TEXT_FIELD_DID_BEGIN, _ct.cast(begin_imp, _ct.c_void_p), b"v@:@")
    _add_method(cls, _SEL_TEXT_FIELD_DID_END, _ct.cast(end_imp, _ct.c_void_p), b"v@:@")
    _add_method(cls, _SEL_TEXT_VIEW_DID_BEGIN, _ct.cast(begin_imp, _ct.c_void_p), b"v@:@")
    _add_method(cls, _SEL_TEXT_VIEW_DID_END, _ct.cast(end_imp, _ct.c_void_p), b"v@:@")
    _add_method(cls, _SEL_TEXT_VIEW_DID_CHANGE, _ct.cast(change_imp, _ct.c_void_p), b"v@:@")
    _reg_cls(cls)
    _PN_TEXTFIELD_TARGET_CLS = int(cls)
    return _PN_TEXTFIELD_TARGET_CLS


def _attach_input_target(view: Any, *, is_field: bool) -> None:
    """Allocate the raw target and wire control events + delegate."""
    cls = _ensure_textfield_target_class()
    view_ptr = _objc_ptr(view)
    if not cls or not view_ptr:
        return
    _objc_msgSend.restype = _ct.c_void_p
    _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p]
    raw = _objc_msgSend(_ct.c_void_p(cls), _SEL_ALLOC)
    raw = _objc_msgSend(_ct.c_void_p(raw), _SEL_INIT)
    raw = _objc_msgSend(_ct.c_void_p(raw), _SEL_RETAIN)
    if not raw:
        return
    target_ptr = int(raw)
    _pn_tf_target_map[target_ptr] = view
    _pn_retained_views.append(target_ptr)
    _state_of(view)["tf_target_ptr"] = target_ptr
    if is_field:
        _objc_msgSend.restype = None
        _objc_msgSend.argtypes = [
            _ct.c_void_p,
            _ct.c_void_p,
            _ct.c_void_p,
            _ct.c_void_p,
            _ct.c_ulong,
        ]
        # UIControlEventEditingChanged / UIControlEventEditingDidEndOnExit.
        _objc_msgSend(
            _ct.c_void_p(view_ptr),
            _SEL_ADD_TARGET_ACTION_EVENTS,
            _ct.c_void_p(target_ptr),
            _SEL_ON_EDIT,
            1 << 17,
        )
        _objc_msgSend(
            _ct.c_void_p(view_ptr),
            _SEL_ADD_TARGET_ACTION_EVENTS,
            _ct.c_void_p(target_ptr),
            _SEL_ON_SUBMIT,
            1 << 19,
        )
    # The delegate carries shouldReturn / focus / blur for UITextField
    # and change / focus / blur for UITextView.
    _objc_msgSend.restype = None
    _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p, _ct.c_void_p]
    _objc_msgSend(_ct.c_void_p(view_ptr), _SEL_SET_DELEGATE, _ct.c_void_p(target_ptr))


class TextInputHandler(IOSViewHandler):
    """Single-line `UITextField` or multiline `UITextView`.

    The view class is chosen at creation time from the ``multiline``
    prop. Programmatic ``value`` updates set a suppress flag so the
    change events do not echo back into ``on_change``.
    """

    def _build(self, props: Dict[str, Any]) -> Any:
        if props.get("multiline"):
            tv = ObjCClass("UITextView").alloc().init()
            tv.setTranslatesAutoresizingMaskIntoConstraints_(True)
            tv.setFont_(UIFont.systemFontOfSize_(17.0))
            tv.setBackgroundColor_(_uicolor("#FFFFFF"))
            return tv
        tf = ObjCClass("UITextField").alloc().init()
        tf.setTranslatesAutoresizingMaskIntoConstraints_(True)
        tf.setBorderStyle_(3)  # UITextBorderStyleRoundedRect
        return tf

    def create(self, tag: int, props: Dict[str, Any]) -> Any:
        view = super().create(tag, props)
        view.retain()
        _pn_retained_views.append(view)
        _attach_input_target(view, is_field=not props.get("multiline"))
        return view

    def _teardown(self, native_view: Any) -> None:
        target_ptr = _state_of(native_view).get("tf_target_ptr")
        if target_ptr is not None:
            _pn_tf_target_map.pop(int(target_ptr), None)

    def _is_field(self, view: Any) -> bool:
        try:
            return bool(view.isKindOfClass_(ObjCClass("UITextField")))
        except Exception:
            return True

    def _apply(self, view: Any, props: Dict[str, Any], initial: bool) -> None:
        state = _state_of(view)
        is_field = self._is_field(view)
        if "max_length" in props:
            state["max_length"] = props["max_length"] if props["max_length"] is None else int(props["max_length"])
        if "value" in props and props["value"] is not None:
            current = str(view.text) if view.text is not None else ""
            new = str(props["value"])
            if current != new:
                state["suppress"] = True
                try:
                    view.setText_(new)
                finally:
                    state["suppress"] = False
        if "placeholder" in props and is_field:
            view.setPlaceholder_(str(props["placeholder"]) if props["placeholder"] is not None else "")
        if "placeholder_color" in props and props["placeholder_color"] is not None and is_field:
            try:
                NSAttributedString = ObjCClass("NSAttributedString")
                merged = state.get("props") or props
                p = str(merged.get("placeholder", "") or "")
                attr = NSAttributedString.alloc().initWithString_attributes_(
                    p,
                    {"NSColor": _uicolor(props["placeholder_color"])},
                )
                view.setAttributedPlaceholder_(attr)
            except Exception:
                pass
        if "font_size" in props and props["font_size"] is not None:
            view.setFont_(UIFont.systemFontOfSize_(float(props["font_size"])))
        if "color" in props and props["color"] is not None:
            view.setTextColor_(_uicolor(props["color"]))
        if "background_color" in props and props["background_color"] is not None:
            view.setBackgroundColor_(_uicolor(props["background_color"]))
        if "secure" in props:
            try:
                view.setSecureTextEntry_(bool(props["secure"]))
            except Exception:
                pass
        if "keyboard_type" in props and props["keyboard_type"] is not None:
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
        if "auto_capitalize" in props and props["auto_capitalize"] is not None:
            # UITextAutocapitalizationType: none=0, words=1, sentences=2, all=3.
            mapping = {"none": 0, "words": 1, "sentences": 2, "characters": 3}
            try:
                view.setAutocapitalizationType_(mapping.get(props["auto_capitalize"], 2))
            except Exception:
                pass
        if "auto_correct" in props:
            try:
                view.setAutocorrectionType_(1 if props["auto_correct"] else 0)
            except Exception:
                pass
        if "return_key_type" in props and props["return_key_type"] is not None:
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
        if "selection_color" in props and props["selection_color"] is not None:
            try:
                view.setTintColor_(_uicolor(props["selection_color"]))
            except Exception:
                pass
        if "text_content_type" in props:
            tct = props["text_content_type"]
            try:
                view.setTextContentType_(_ui_text_content_type(str(tct)) if tct is not None else None)
            except Exception:
                pass
        if "clear_button" in props and is_field:
            try:
                view.setClearButtonMode_(1 if props["clear_button"] else 0)  # 1 = WhileEditing
            except Exception:
                pass
        # ``editable`` is present only when False (read-only). A removed
        # prop arrives as None on update, which means "editable again".
        if "editable" in props:
            editable = props["editable"]
            resolved = True if editable is None else bool(editable)
            try:
                if is_field:
                    view.setEnabled_(resolved)
                else:
                    view.setEditable_(resolved)
            except Exception:
                pass
        if "auto_focus" in props and props["auto_focus"]:
            try:
                view.becomeFirstResponder()
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

    def measure_intrinsic(
        self,
        native_view: Any,
        max_width: float,
        max_height: float,
    ) -> Tuple[float, float]:
        w, h = super().measure_intrinsic(native_view, max_width, max_height)
        return (max(w, 100.0), max(h, 36.0))

    def command(self, native_view: Any, name: str, args: Dict[str, Any]) -> Any:
        if name == "focus":
            try:
                native_view.becomeFirstResponder()
            except Exception:
                pass
            return None
        if name == "blur":
            try:
                native_view.resignFirstResponder()
            except Exception:
                pass
            return None
        if name == "clear":
            state = _state_of(native_view)
            state["suppress"] = True
            try:
                native_view.setText_("")
            finally:
                state["suppress"] = False
            return None
        if name == "get_value":
            try:
                return str(native_view.text) if native_view.text is not None else ""
            except Exception:
                return ""
        return None


class SwitchHandler(IOSViewHandler):
    def _build(self, props: Dict[str, Any]) -> Any:
        sw = ObjCClass("UISwitch").alloc().init()
        sw.setTranslatesAutoresizingMaskIntoConstraints_(True)
        sw.retain()
        _pn_retained_views.append(sw)

        def _on_toggle() -> None:
            if _state_of(sw).get("suppress"):
                return
            try:
                value = bool(sw.isOn())
            except Exception:
                return
            _fire(sw, "on_change", value)

        _register_control_action(sw, 1 << 12, _on_toggle)  # ValueChanged
        return sw

    def _apply(self, sw: Any, props: Dict[str, Any], initial: bool) -> None:
        state = _state_of(sw)
        if "value" in props:
            new_val = bool(props["value"])
            if bool(sw.isOn()) != new_val:
                state["suppress"] = True
                try:
                    sw.setOn_animated_(new_val, not initial)
                finally:
                    state["suppress"] = False
        _apply_accessibility(sw, props)

    def measure_intrinsic(
        self,
        native_view: Any,
        max_width: float,
        max_height: float,
    ) -> Tuple[float, float]:
        return (51.0, 31.0)


class SliderHandler(IOSViewHandler):
    def _build(self, props: Dict[str, Any]) -> Any:
        sl = ObjCClass("UISlider").alloc().init()
        sl.setTranslatesAutoresizingMaskIntoConstraints_(True)
        sl.retain()
        _pn_retained_views.append(sl)

        def _on_slide() -> None:
            if _state_of(sl).get("suppress"):
                return
            try:
                value = float(sl.value)
            except Exception:
                return
            _fire(sl, "on_change", value)

        _register_control_action(sl, 1 << 12, _on_slide)  # ValueChanged
        return sl

    def _apply(self, sl: Any, props: Dict[str, Any], initial: bool) -> None:
        state = _state_of(sl)
        if "min_value" in props and props["min_value"] is not None:
            sl.setMinimumValue_(float(props["min_value"]))
        if "max_value" in props and props["max_value"] is not None:
            sl.setMaximumValue_(float(props["max_value"]))
        if "value" in props and props["value"] is not None:
            new_val = float(props["value"])
            if abs(float(sl.value) - new_val) > 1e-9:
                state["suppress"] = True
                try:
                    sl.setValue_animated_(new_val, not initial)
                finally:
                    state["suppress"] = False
        _apply_accessibility(sl, props)

    def measure_intrinsic(
        self,
        native_view: Any,
        max_width: float,
        max_height: float,
    ) -> Tuple[float, float]:
        w = max_width if math.isfinite(max_width) else 200.0
        return (max(w, 100.0), 34.0)


class ActivityIndicatorHandler(IOSViewHandler):
    def _build(self, props: Dict[str, Any]) -> Any:
        # Style: 100=medium, 101=large (iOS 13+).
        style = 101 if props.get("size") == "large" else 100
        ai = ObjCClass("UIActivityIndicatorView").alloc().initWithActivityIndicatorStyle_(style)
        ai.setTranslatesAutoresizingMaskIntoConstraints_(True)
        ai.setHidesWhenStopped_(True)
        return ai

    def _apply(self, ai: Any, props: Dict[str, Any], initial: bool) -> None:
        if "size" in props and props["size"] is not None and not initial:
            style = 101 if props["size"] == "large" else 100
            try:
                ai.setActivityIndicatorViewStyle_(style)
            except Exception:
                pass
        if "color" in props and props["color"] is not None:
            ai.setColor_(_uicolor(props["color"]))
        animating = props.get("animating")
        if "animating" in props or initial:
            should_animate = True if animating is None else bool(animating)
            if should_animate:
                ai.startAnimating()
            else:
                ai.stopAnimating()
        _apply_accessibility(ai, props)

    def measure_intrinsic(
        self,
        native_view: Any,
        max_width: float,
        max_height: float,
    ) -> Tuple[float, float]:
        try:
            size = native_view.intrinsicContentSize()
            return (float(size.width), float(size.height))
        except Exception:
            return (20.0, 20.0)


class PressableHandler(IOSViewHandler):
    """Touchable container with press feedback.

    A `UILongPressGestureRecognizer` with ``minimumPressDuration=0``
    tracks the raw touch for ``on_press_in`` / ``on_press_out`` and the
    pressed-opacity feedback; a tap recognizer fires ``on_press`` and a
    standard long-press recognizer fires ``on_long_press``. All three
    share the simultaneous-recognition delegate. Declarative
    ``gestures`` from props are attached on top by the base class.
    """

    def _build(self, props: Dict[str, Any]) -> Any:
        v = ObjCClass("UIView").alloc().init()
        v.setTranslatesAutoresizingMaskIntoConstraints_(True)
        v.setUserInteractionEnabled_(True)
        self._wire_press(v)
        return v

    def _wire_press(self, view: Any) -> None:
        UITap = ObjCClass("UITapGestureRecognizer")
        UILong = ObjCClass("UILongPressGestureRecognizer")

        tap = UITap.alloc().init()
        longp = UILong.alloc().init()
        # Zero-duration long press == raw touch-down / touch-up tracking.
        touch = UILong.alloc().init()
        touch.setMinimumPressDuration_(0.0)

        def on_tap() -> None:
            _fire(view, "on_press")

        def on_long() -> None:
            # UILongPressGestureRecognizer fires on every state
            # transition; only Began (1) counts as the trigger.
            try:
                state = int(longp.state)
            except Exception:
                state = 1
            if state == 1:
                _fire(view, "on_long_press")

        def on_touch() -> None:
            try:
                state = int(touch.state)
            except Exception:
                return
            if state == 1:  # began
                _press_feedback(view, True)
                _fire(view, "on_press_in")
            elif state in (3, 4, 5):  # ended / cancelled / failed
                _press_feedback(view, False)
                _fire(view, "on_press_out")

        for rec, handler in ((tap, on_tap), (longp, on_long), (touch, on_touch)):
            try:
                rec.setCancelsTouchesInView_(False)
            except Exception:
                pass
            _set_recognizer_delegate(rec)
            view.addGestureRecognizer_(rec)
            rec.retain()
            _register_action(rec, handler)

    def _apply(self, view: Any, props: Dict[str, Any], initial: bool) -> None:
        _apply_common_visual(view, props)
        if "enabled" in props:
            view.setUserInteractionEnabled_(props["enabled"] is not False)


# ----------------------------------------------------------------------
# UITextContentType constants
# ----------------------------------------------------------------------
#
# ``textContentType`` powers iOS AutoFill (passwords, OTP codes, etc.).
# The values are NSString *constants*, not literals, so we read the real
# constants out of UIKit via ``objc_const`` instead of hardcoding their
# string values.
_TEXT_CONTENT_TYPE_SYMBOLS = {
    "username": "UITextContentTypeUsername",
    "password": "UITextContentTypePassword",
    "new_password": "UITextContentTypeNewPassword",
    "one_time_code": "UITextContentTypeOneTimeCode",
    "email": "UITextContentTypeEmailAddress",
    "email_address": "UITextContentTypeEmailAddress",
    "name": "UITextContentTypeName",
    "url": "UITextContentTypeURL",
    "telephone": "UITextContentTypeTelephoneNumber",
    "telephone_number": "UITextContentTypeTelephoneNumber",
    "phone": "UITextContentTypeTelephoneNumber",
    "phone_number": "UITextContentTypeTelephoneNumber",
}
_pn_text_content_type_cache: Dict[str, Any] = {}


def _ui_text_content_type(name: str) -> Any:
    """Resolve a content-type name to its ``UITextContentType`` constant.

    Returns the NSString constant (an ``ObjCInstance``) for a known name,
    or ``None`` for an unknown name / lookup failure (in which case the
    caller should simply leave the content type unset).
    """
    symbol = _TEXT_CONTENT_TYPE_SYMBOLS.get(name.strip().lower())
    if not symbol:
        return None
    if symbol in _pn_text_content_type_cache:
        return _pn_text_content_type_cache[symbol]
    value = None
    try:
        from rubicon.objc.api import objc_const

        uikit = _ct.cdll.LoadLibrary("/System/Library/Frameworks/UIKit.framework/UIKit")
        value = objc_const(uikit, symbol)
    except Exception:
        value = None
    _pn_text_content_type_cache[symbol] = value
    return value


# ----------------------------------------------------------------------
# Pressable feedback
# ----------------------------------------------------------------------


def _press_feedback(view: Any, pressed: bool) -> None:
    """Animate the pressed-opacity visual feedback."""
    try:
        merged = _state_of(view).get("props") or {}
        if pressed:
            opacity = float(merged.get("pressed_opacity", 0.6))
            duration = 0.05
        else:
            raw = merged.get("opacity")
            opacity = float(raw) if raw is not None else 1.0
            duration = 0.1
        UIView = ObjCClass("UIView")
        UIView.animateWithDuration_animations_(duration, lambda: view.setAlpha_(opacity))
    except Exception:
        pass


# ======================================================================
# ProgressBar
# ======================================================================


class ProgressBarHandler(IOSViewHandler):
    """Determinate ``UIProgressView`` (or a spinning ``UIActivityIndicatorView``).

    ``UIProgressView`` has no indeterminate mode, so when
    ``indeterminate`` is set the handler instead creates an animating
    ``UIActivityIndicatorView``. The view type is chosen at create
    time; toggling ``indeterminate`` on an existing bar keeps the
    original view (a deliberate, safe limitation).
    """

    def _build(self, props: Dict[str, Any]) -> Any:
        if props.get("indeterminate"):
            ai = ObjCClass("UIActivityIndicatorView").alloc().init()
            ai.setTranslatesAutoresizingMaskIntoConstraints_(True)
            try:
                ai.startAnimating()
            except Exception:
                pass
            return ai
        pv = ObjCClass("UIProgressView").alloc().init()
        pv.setTranslatesAutoresizingMaskIntoConstraints_(True)
        return pv

    def _apply(self, view: Any, props: Dict[str, Any], initial: bool) -> None:
        try:
            cls_name = str(view.objc_class.name)
        except Exception:
            cls_name = ""
        if "UIActivityIndicatorView" in cls_name:
            if "color" in props and props["color"] is not None:
                try:
                    view.setColor_(_uicolor(props["color"]))
                except Exception:
                    pass
            try:
                view.startAnimating()
            except Exception:
                pass
        else:
            if "value" in props and props["value"] is not None:
                try:
                    view.setProgress_(float(props["value"]))
                except Exception:
                    pass
            if "color" in props and props["color"] is not None:
                try:
                    view.setProgressTintColor_(_uicolor(props["color"]))
                except Exception:
                    pass
            if "track_color" in props and props["track_color"] is not None:
                try:
                    view.setTrackTintColor_(_uicolor(props["track_color"]))
                except Exception:
                    pass
        _apply_accessibility(view, props)

    def measure_intrinsic(
        self,
        native_view: Any,
        max_width: float,
        max_height: float,
    ) -> Tuple[float, float]:
        try:
            cls_name = str(native_view.objc_class.name)
        except Exception:
            cls_name = ""
        if "UIActivityIndicatorView" in cls_name:
            return (20.0, 20.0)
        w = max_width if math.isfinite(max_width) else 200.0
        return (max(w, 40.0), 4.0)


# ======================================================================
# WebView: WKWebView with navigation + script-message delegates
# ======================================================================

# WKWebView.scrollView isn't auto-detected as a property by rubicon, so it
# must be declared once (lazily, to avoid forcing a WebKit load at import).
_pn_wkwebview_declared = False


def _webview_url(webview: Any) -> str:
    """Return the web view's current absolute URL string (or ``""``)."""
    try:
        url = webview.URL
        if url is None:
            return ""
        return str(url.absoluteString)
    except Exception:
        return ""


# WKNavigationDelegate + WKScriptMessageHandler bridge. WebKit passes
# object arguments (``WKNavigation*`` / ``WKScriptMessage*``) to these
# delegate callbacks, which rubicon's ``@objc_method`` FFI bridge
# mismarshals on iOS 18.x; the app dies with EXC_BAD_ACCESS inside
# ``objc_msgSend`` (see the module header note). Like the scroll and
# tab-bar delegates we therefore build the class with raw libobjc and
# CFUNCTYPE IMPs, keep per-delegate state keyed by the delegate
# *pointer*, and only touch the retained rubicon webview from Python.

# Maps delegate ptr -> {"view": rubicon WKWebView, "inject_js": str|None}.
_pn_webview_state: Dict[int, Dict[str, Any]] = {}

_WEBVIEW_IMP_TYPE = _ct.CFUNCTYPE(None, _ct.c_void_p, _ct.c_void_p, _ct.c_void_p, _ct.c_void_p)


def _webview_did_finish_imp(self_ptr: int, _cmd_ptr: int, _webview_ptr: int, _nav_ptr: int) -> None:
    """Raw C callback for ``webView:didFinishNavigation:``."""
    info = _pn_webview_state.get(int(self_ptr or 0))
    if not info:
        return
    wv = info.get("view")
    if wv is None:
        return
    js = info.get("inject_js")
    if js:
        try:
            wv.evaluateJavaScript_completionHandler_(str(js), None)
        except Exception:
            pass
    _fire(wv, "on_load", _webview_url(wv))


def _webview_did_start_imp(self_ptr: int, _cmd_ptr: int, _webview_ptr: int, _nav_ptr: int) -> None:
    """Raw C callback for ``webView:didStartProvisionalNavigation:``."""
    info = _pn_webview_state.get(int(self_ptr or 0))
    if not info:
        return
    wv = info.get("view")
    if wv is not None:
        _fire(wv, "on_navigation_state_change", _webview_url(wv))


def _webview_script_message_imp(self_ptr: int, _cmd_ptr: int, _controller_ptr: int, message_ptr: int) -> None:
    """Raw C callback for ``userContentController:didReceiveScriptMessage:``."""
    info = _pn_webview_state.get(int(self_ptr or 0))
    if not info:
        return
    wv = info.get("view")
    if wv is None:
        return
    body = ""
    try:
        # Wrapping the raw pointer ourselves (outbound rubicon call) is
        # safe; it's the @objc_method *callback* marshaling that breaks.
        message = ObjCInstance(_ct.c_void_p(message_ptr))
        raw = message.body
        body = str(raw) if raw is not None else ""
    except Exception:
        body = ""
    _fire(wv, "on_message", body)


_webview_did_finish_imp_ref = _WEBVIEW_IMP_TYPE(_webview_did_finish_imp)
_webview_did_start_imp_ref = _WEBVIEW_IMP_TYPE(_webview_did_start_imp)
_webview_script_message_imp_ref = _WEBVIEW_IMP_TYPE(_webview_script_message_imp)

_PN_WEBVIEW_DELEGATE_CLS = _alloc_cls(_NS_OBJECT_CLS, b"_PNWebViewDelegateCTypes", 0)
if _PN_WEBVIEW_DELEGATE_CLS:
    for sel_name, imp_ref in (
        (b"webView:didFinishNavigation:", _webview_did_finish_imp_ref),
        (b"webView:didStartProvisionalNavigation:", _webview_did_start_imp_ref),
        (b"userContentController:didReceiveScriptMessage:", _webview_script_message_imp_ref),
    ):
        _add_method(
            _PN_WEBVIEW_DELEGATE_CLS,
            _sel_reg(sel_name),
            _ct.cast(imp_ref, _ct.c_void_p),
            b"v@:@@",
        )
    _reg_cls(_PN_WEBVIEW_DELEGATE_CLS)


def _new_webview_delegate_ptr() -> Optional[int]:
    """Alloc/init/retain one raw ``_PNWebViewDelegateCTypes`` instance."""
    if not _PN_WEBVIEW_DELEGATE_CLS:
        return None
    _objc_msgSend.restype = _ct.c_void_p
    _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p]
    d = _objc_msgSend(_PN_WEBVIEW_DELEGATE_CLS, _SEL_ALLOC)
    d = _objc_msgSend(d, _SEL_INIT)
    d = _objc_msgSend(d, _SEL_RETAIN)
    return int(d) if d else None


class WebViewHandler(IOSViewHandler):
    def _build(self, props: Dict[str, Any]) -> Any:
        global _pn_wkwebview_declared
        WKWebView = ObjCClass("WKWebView")
        WKWebViewConfiguration = ObjCClass("WKWebViewConfiguration")
        if not _pn_wkwebview_declared:
            # Some WebKit @property declarations aren't auto-detected by
            # rubicon's runtime introspection (same class of issue as
            # UIView.superview above); declare the ones we read so
            # attribute access returns the object instead of a method.
            for cls, prop in (
                (WKWebView, "scrollView"),
                (WKWebView, "URL"),
                (WKWebViewConfiguration, "userContentController"),
            ):
                try:
                    cls.declare_property(prop)
                except Exception:
                    pass
            _pn_wkwebview_declared = True
        config = WKWebViewConfiguration.alloc().init()
        delegate_ptr = _new_webview_delegate_ptr()
        delegate = ObjCInstance(_ct.c_void_p(delegate_ptr)) if delegate_ptr else None
        # Register the message handler up front so page JS calling
        # ``window.webkit.messageHandlers.pythonnative.postMessage(x)``
        # can reach ``on_message`` even if it's wired in a later render.
        if delegate is not None:
            try:
                config.userContentController.addScriptMessageHandler_name_(delegate, "pythonnative")
            except Exception:
                pass
        wv = WKWebView.alloc().initWithFrame_configuration_(((0, 0), (0, 0)), config)
        wv.setTranslatesAutoresizingMaskIntoConstraints_(True)
        if delegate is not None:
            try:
                wv.setNavigationDelegate_(delegate)
            except Exception:
                pass
        if delegate_ptr:
            _pn_webview_state[delegate_ptr] = {"view": wv, "inject_js": None}
            self._delegate_ids[_objc_ptr(wv) or 0] = delegate_ptr
        return wv

    _delegate_ids: Dict[int, int] = {}

    def create(self, tag: int, props: Dict[str, Any]) -> Any:
        view = super().create(tag, props)
        delegate_id = self._delegate_ids.pop(_objc_ptr(view) or 0, None)
        if delegate_id is not None:
            _state_of(view)["webview_delegate_id"] = delegate_id
            if props.get("inject_javascript"):
                _pn_webview_state[delegate_id]["inject_js"] = props["inject_javascript"]
        return view

    def _teardown(self, native_view: Any) -> None:
        delegate_id = _state_of(native_view).get("webview_delegate_id")
        if delegate_id is not None:
            _pn_webview_state.pop(delegate_id, None)

    def _apply(self, wv: Any, props: Dict[str, Any], initial: bool) -> None:
        delegate_id = _state_of(wv).get("webview_delegate_id")
        if delegate_id is not None and "inject_javascript" in props:
            info = _pn_webview_state.get(delegate_id)
            if info is not None:
                info["inject_js"] = props["inject_javascript"]
        # ``html`` wins over ``url`` (matches the component contract).
        if "html" in props and props["html"]:
            try:
                wv.loadHTMLString_baseURL_(str(props["html"]), None)
            except Exception:
                pass
        elif "url" in props and props["url"]:
            try:
                NSURL = ObjCClass("NSURL")
                NSURLRequest = ObjCClass("NSURLRequest")
                url_obj = NSURL.URLWithString_(str(props["url"]))
                wv.loadRequest_(NSURLRequest.requestWithURL_(url_obj))
            except Exception:
                pass
        if "scroll_enabled" in props:
            enabled = props["scroll_enabled"]
            try:
                wv.scrollView.setScrollEnabled_(True if enabled is None else bool(enabled))
            except Exception:
                pass

    def command(self, native_view: Any, name: str, args: Dict[str, Any]) -> Any:
        if name == "eval_js":
            try:
                native_view.evaluateJavaScript_completionHandler_(str(args.get("source", "")), None)
            except Exception:
                pass
            return None
        if name == "reload":
            try:
                native_view.reload()
            except Exception:
                pass
            return None
        if name == "go_back":
            try:
                native_view.goBack()
            except Exception:
                pass
            return None
        if name == "go_forward":
            try:
                native_view.goForward()
            except Exception:
                pass
            return None
        return None


# ======================================================================
# Spacer / SafeAreaView
# ======================================================================


class SpacerHandler(IOSViewHandler):
    """Empty layout placeholder used as a flexible gap.

    All sizing semantics live in the layout engine; ``Spacer``
    behaves identically to a `View` with the same style props.
    """

    def _build(self, props: Dict[str, Any]) -> Any:
        v = ObjCClass("UIView").alloc().init()
        v.setTranslatesAutoresizingMaskIntoConstraints_(True)
        return v

    def _apply(self, view: Any, props: Dict[str, Any], initial: bool) -> None:
        pass


class SafeAreaViewHandler(IOSViewHandler):
    """Plain container; safe-area insets are applied by the layout engine."""

    def _build(self, props: Dict[str, Any]) -> Any:
        v = ObjCClass("UIView").alloc().init()
        v.setTranslatesAutoresizingMaskIntoConstraints_(True)
        return v


# ======================================================================
# Modal: actually presents a UIViewController
# ======================================================================


class ModalHandler(IOSViewHandler):
    """Real modal presentation backed by a presented `UIViewController`.

    The on-tree placeholder is a hidden ``UIView`` (so the layout
    engine can ignore it). When ``visible`` flips to ``True``, a fresh
    ``UIViewController`` is allocated, its view is configured as the
    container into which the modal's children mount, and the controller
    is presented from the topmost view controller.

    Children are added to the *content view* of the presented
    controller, not the on-tree placeholder, so the reconciler's
    ``insert_child`` / ``remove_child`` calls are forwarded there.
    """

    def _build(self, props: Dict[str, Any]) -> Any:
        v = ObjCClass("UIView").alloc().init()
        v.setHidden_(True)
        return v

    def _apply(self, placeholder: Any, props: Dict[str, Any], initial: bool) -> None:
        state = _state_of(placeholder)
        merged = state.get("props") or props
        visible = bool(merged.get("visible", False))
        presented = state.get("modal") is not None
        if visible and not presented:
            self._present(placeholder, merged)
        elif not visible and presented:
            self._dismiss(placeholder)

    def _teardown(self, native_view: Any) -> None:
        if _state_of(native_view).get("modal") is not None:
            self._dismiss(native_view)

    def insert_child(self, parent: Any, child: Any, index: int) -> None:
        state = _state_of(parent)
        modal = state.get("modal")
        if modal is not None:
            try:
                child.setTranslatesAutoresizingMaskIntoConstraints_(True)
            except Exception:
                pass
            try:
                content = modal["content_view"]
                count = len(list(content.subviews or []))
                content.insertSubview_atIndex_(child, max(0, min(index, count)))
            except Exception:
                pass
        else:
            buf = state.setdefault("pending_children", [])
            buf.insert(max(0, min(index, len(buf))), child)

    def remove_child(self, parent: Any, child: Any) -> None:
        try:
            child.removeFromSuperview()
        except Exception:
            pass
        buf = _state_of(parent).get("pending_children")
        if buf and child in buf:
            buf.remove(child)

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        # Modal is a virtual placeholder, not rendered inline.
        return

    def measure_intrinsic(
        self,
        native_view: Any,
        max_width: float,
        max_height: float,
    ) -> Tuple[float, float]:
        return (0.0, 0.0)

    def _present(self, placeholder: Any, props: Dict[str, Any]) -> None:
        state = _state_of(placeholder)
        try:
            UIViewController = ObjCClass("UIViewController")
            UIApplication = ObjCClass("UIApplication")
            controller = UIViewController.alloc().init()
            controller.retain()
            _pn_retained_views.append(controller)

            presentation_style = props.get("presentation_style", "page_sheet")
            is_overlay = presentation_style == "overlay" or bool(props.get("transparent"))

            content = ObjCClass("UIView").alloc().init()
            # An overlay dims the underlying context, so its content layer
            # is transparent and the controller view carries the scrim.
            content.setBackgroundColor_(_uicolor("#00000000" if is_overlay else "#FFFFFF"))
            content.setTranslatesAutoresizingMaskIntoConstraints_(True)
            controller.view.addSubview_(content)
            controller.view.setBackgroundColor_(_uicolor("#66000000" if is_overlay else "#FFFFFF"))
            try:
                bounds = controller.view.bounds
                content.setFrame_(((0, 0), (bounds.size.width, bounds.size.height)))
                content.setAutoresizingMask_(2 | 16)  # FlexibleWidth | FlexibleHeight
            except Exception:
                pass

            # UIModalPresentationStyle: fullScreen=0, pageSheet=1,
            # formSheet=2, overCurrentContext=6 (the dimmed overlay).
            style_map = {"full_screen": 0, "page_sheet": 1, "form_sheet": 2, "overlay": 6}
            style_int = 6 if is_overlay else style_map.get(presentation_style, 1)
            try:
                controller.setModalPresentationStyle_(style_int)
            except Exception:
                pass
            # For sheet styles, ``dismiss_on_backdrop=False`` locks
            # interactive (swipe / outside-tap) dismissal so the modal
            # stays put until ``visible`` is driven back to False.
            if not is_overlay and props.get("dismiss_on_backdrop") is False:
                try:
                    controller.setModalInPresentation_(True)
                except Exception:
                    pass

            def _on_present_complete() -> None:
                _fire(placeholder, "on_show")

            state["modal"] = {
                "controller": controller,
                "content_view": content,
                # Keep the completion block alive past this call.
                "on_show": _on_present_complete,
            }
            for child in state.pop("pending_children", []):
                try:
                    child.setTranslatesAutoresizingMaskIntoConstraints_(True)
                    content.addSubview_(child)
                except Exception:
                    pass

            top = _top_view_controller_for_alert(UIApplication.sharedApplication)
            if top is not None:
                top.presentViewController_animated_completion_(controller, True, _on_present_complete)
        except Exception:
            state.pop("modal", None)

    def _dismiss(self, placeholder: Any) -> None:
        state = _state_of(placeholder)
        modal = state.pop("modal", None)
        if modal is None:
            return
        controller = modal.get("controller")
        if controller is not None:
            try:
                controller.dismissViewControllerAnimated_completion_(True, None)
            except Exception:
                pass
        _fire(placeholder, "on_dismiss")


# ======================================================================
# StatusBar: global side effect, no view in the tree
# ======================================================================


class StatusBarHandler(IOSViewHandler):
    """Apply status-bar style/visibility to the key window.

    Status bar configuration on iOS is a per-view-controller value; we
    use the legacy UIApplication setters which still work on iOS 13+
    (with ``UIViewControllerBasedStatusBarAppearance`` set to ``NO`` in
    Info.plist for full effect). The placeholder view is hidden and
    contributes nothing to the layout.
    """

    def _build(self, props: Dict[str, Any]) -> Any:
        v = ObjCClass("UIView").alloc().init()
        v.setHidden_(True)
        return v

    def _apply(self, view: Any, props: Dict[str, Any], initial: bool) -> None:
        try:
            UIApplication = ObjCClass("UIApplication")
            app = UIApplication.sharedApplication
            if "hidden" in props and props["hidden"] is not None:
                app.setStatusBarHidden_animated_(bool(props["hidden"]), True)
            if "bar_style" in props and props["bar_style"] is not None:
                # 1 = lightContent, 3 = darkContent (iOS 13+).
                mapping = {"default": 3, "light": 1, "dark": 3}
                app.setStatusBarStyle_animated_(mapping.get(props["bar_style"], 0), True)
        except Exception:
            pass

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        return

    def measure_intrinsic(
        self,
        native_view: Any,
        max_width: float,
        max_height: float,
    ) -> Tuple[float, float]:
        return (0.0, 0.0)


# ======================================================================
# KeyboardAvoidingView: publishes the keyboard height to Python
# ======================================================================


_pn_keyboard_observer: Any = None


class _PNKeyboardObserver(NSObject):  # type: ignore[valid-type]
    @objc_method
    def keyboardWillShow_(self, notification: object) -> None:
        try:
            info = notification.userInfo
            kbd_frame = info.objectForKey_("UIKeyboardFrameEndUserInfoKey")
            # Frame is wrapped in NSValue; CGRectValue unwraps the rect.
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
        center = ObjCClass("NSNotificationCenter").defaultCenter
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
    component, which subscribes via
    [`use_keyboard_height`][pythonnative.use_keyboard_height] and
    applies the offset as bottom padding. The native handler is just a
    vanilla UIView that ensures the observer is installed.
    """

    def _build(self, props: Dict[str, Any]) -> Any:
        _ensure_keyboard_observer()
        v = ObjCClass("UIView").alloc().init()
        v.setTranslatesAutoresizingMaskIntoConstraints_(True)
        return v


# ======================================================================
# TabBar: UITabBar with a raw ctypes delegate
# ======================================================================
#
# ``tabBar:didSelectItem:`` passes the UITabBarItem as an ObjC object;
# see the module header for why we sidestep rubicon-objc here.

_DELEGATE_IMP_TYPE = _ct.CFUNCTYPE(None, _ct.c_void_p, _ct.c_void_p, _ct.c_void_p, _ct.c_void_p)


def _tabbar_did_select_imp(self_ptr: int, cmd_ptr: int, tabbar_ptr: int, item_ptr: int) -> None:
    """Raw C callback for ``tabBar:didSelectItem:``."""
    try:
        _objc_msgSend.restype = _ct.c_long
        _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p]
        index: int = _objc_msgSend(item_ptr, _SEL_TAG)

        tag = _view_tags.get(int(tabbar_ptr or 0))
        state = _view_state.get(tag) if tag is not None else None
        items = (state or {}).get("props", {}).get("items") or []
        if 0 <= index < len(items):
            _fire_ptr(int(tabbar_ptr), "on_tab_select", items[index].get("name", ""))
    except Exception:
        pass


_tabbar_imp_ref = _DELEGATE_IMP_TYPE(_tabbar_did_select_imp)

_PN_TABBAR_DELEGATE_CLS = _alloc_cls(_NS_OBJECT_CLS, b"_PNTabBarDelegateCTypes", 0)
if _PN_TABBAR_DELEGATE_CLS:
    _add_method(
        _PN_TABBAR_DELEGATE_CLS,
        _sel_reg(b"tabBar:didSelectItem:"),
        _ct.cast(_tabbar_imp_ref, _ct.c_void_p),
        b"v@:@@",
    )
    _reg_cls(_PN_TABBAR_DELEGATE_CLS)

_pn_tabbar_delegate_ptr: Any = None


def _ensure_tabbar_delegate(tab_bar: Any) -> None:
    global _pn_tabbar_delegate_ptr
    if _pn_tabbar_delegate_ptr is None and _PN_TABBAR_DELEGATE_CLS:
        _objc_msgSend.restype = _ct.c_void_p
        _objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p]
        raw = _objc_msgSend(_PN_TABBAR_DELEGATE_CLS, _SEL_ALLOC)
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

    Each tab is a ``UITabBarItem`` with a ``tag`` matching its index in
    the items list. A raw ctypes delegate forwards selection events
    into the ``on_tab_select`` channel.
    """

    def _build(self, props: Dict[str, Any]) -> Any:
        from .. import platform_metrics

        initial_h = platform_metrics.ios_tab_bar_height()
        tab_bar = ObjCClass("UITabBar").alloc().initWithFrame_(((0, 0), (0, initial_h)))
        tab_bar.setTranslatesAutoresizingMaskIntoConstraints_(True)
        tab_bar.retain()
        _pn_retained_views.append(tab_bar)
        _ensure_tabbar_delegate(tab_bar)
        return tab_bar

    def measure_intrinsic(
        self,
        native_view: Any,
        max_width: float,
        max_height: float,
    ) -> Tuple[float, float]:
        from .. import platform_metrics

        w = max_width if math.isfinite(max_width) else 320.0
        return (w, platform_metrics.ios_tab_bar_height())

    def _apply(self, tab_bar: Any, props: Dict[str, Any], initial: bool) -> None:
        merged = _state_of(tab_bar).get("props") or props
        items = merged.get("items") or []
        if "items" in props:
            self._set_bar_items(tab_bar, items)
        if "active_tab" in props or "items" in props:
            self._set_active(tab_bar, merged.get("active_tab"), items)
        _apply_accessibility(tab_bar, props)

    def _set_bar_items(self, tab_bar: Any, items: list) -> None:
        UITabBarItem = ObjCClass("UITabBarItem")
        UIImage = ObjCClass("UIImage")
        bar_items = []
        for i, item in enumerate(items):
            title = item.get("title", item.get("name", ""))
            image = self._resolve_icon(UIImage, item.get("icon"))
            bar_item = UITabBarItem.alloc().initWithTitle_image_tag_(str(title), image, i)
            bar_items.append(bar_item)
        try:
            tab_bar.setItems_animated_(bar_items, False)
        except Exception:
            pass

    def _resolve_icon(self, UIImage: Any, icon: Any) -> Any:
        """Resolve a tab icon spec to a UIImage, or return None.

        Accepts a bare string (treated as an SF Symbol name) or a dict
        of the form ``{"ios": "house.fill", "android": "..."}``. Names
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

    # If the root is a navigation controller, presenting from the
    # visible controller gives UIKit the most specific context.
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

    Safe to call from any thread; the UIKit work is automatically
    marshalled to the main thread via
    [`pythonnative.runtime.call_on_main_thread`][pythonnative.runtime.call_on_main_thread].
    Returns immediately; the alert appears on the next main-loop tick.

    ``buttons`` is a list of ``{"label": str, "style":
    "default"|"cancel"|"destructive"}`` dicts. When the user picks
    button ``i`` the helper invokes ``on_result(i)`` exactly once. A
    dismiss (e.g. swipe-to-cancel on iPad) delivers ``-1``.
    ``on_result`` always runs on the main thread; if it needs to wake
    an asyncio.Future, use
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
# Picker: action-sheet dropdown
# ======================================================================
#
# The PythonNative `Picker` renders as a `UIButton` whose tap presents
# a native action sheet (``UIAlertController``) listing the options.
# Selecting a row fires ``on_change(value)``. Action sheets are the
# standard iOS dropdown pattern for a small-to-medium set of choices.


# Maps ``id(target)`` -> owning Picker button.
def _picker_button_title(props: Dict[str, Any]) -> str:
    """Render the selected label, falling back to the placeholder."""
    items = props.get("items") or []
    selected = props.get("value")
    for item in items:
        if isinstance(item, dict) and item.get("value") == selected:
            return str(item.get("label", item.get("value", "")))
    return str(props.get("placeholder") or "Select…")


def _present_picker_sheet(btn: Any) -> None:
    """Present the option action-sheet for a Picker button."""
    merged = _state_of(btn).get("props") or {}
    items = [item for item in (merged.get("items") or []) if isinstance(item, dict)]
    placeholder = merged.get("placeholder") or "Select…"

    buttons: List[Dict[str, Any]] = [{"label": str(item.get("label", item.get("value", "")))} for item in items]
    buttons.append({"label": "Cancel", "style": "cancel"})

    def _on_result(index: int) -> None:
        if 0 <= index < len(items):
            _fire(btn, "on_change", items[index].get("value"))

    _present_alert(
        title=str(placeholder),
        message=None,
        buttons=buttons,
        style="action_sheet",
        on_result=_on_result,
    )


class PickerHandler(IOSViewHandler):
    """``Picker`` element handler, native action-sheet dropdown."""

    def _build(self, props: Dict[str, Any]) -> Any:
        btn = ObjCClass("UIButton").buttonWithType_(1)  # UIButtonTypeSystem
        btn.setTranslatesAutoresizingMaskIntoConstraints_(True)
        btn.retain()
        _pn_retained_views.append(btn)
        _register_control_action(btn, 1 << 6, lambda: _present_picker_sheet(btn))  # TouchUpInside
        return btn

    def _apply(self, btn: Any, props: Dict[str, Any], initial: bool) -> None:
        merged = _state_of(btn).get("props") or props
        try:
            btn.setTitle_forState_(_picker_button_title(merged), 0)
        except Exception:
            pass
        _apply_accessibility(btn, props)

    def measure_intrinsic(self, native_view: Any, max_width: float, max_height: float) -> Tuple[float, float]:
        try:
            mw = _safe_max(max_width, fallback=10000.0)
            mh = _safe_max(max_height, fallback=10000.0)
            size = native_view.sizeThatFits_((mw, mh))
            return (float(size.width) + 16.0, float(size.height) + 8.0)
        except Exception:
            return (120.0, 36.0)


# ======================================================================
# Checkbox: SF Symbol UIButton toggling checked / unchecked
# ======================================================================


def _checkbox_set_image(btn: Any) -> None:
    """Set the box image from the current checked state (tinted when checked)."""
    state = _state_of(btn)
    merged = state.get("props") or {}
    checked = bool(state.get("value"))
    try:
        UIImage = ObjCClass("UIImage")
        name = "checkmark.square.fill" if checked else "square"
        image = UIImage.systemImageNamed_(name)
        if image is None:
            return
        color = merged.get("color")
        if checked and color is not None:
            try:
                tinted = image.imageWithTintColor_(_uicolor(color))
                if tinted is not None:
                    image = tinted
            except Exception:
                pass
        btn.setImage_forState_(image, 0)
    except Exception:
        pass


def _checkbox_toggle(btn: Any) -> None:
    """Flip a Checkbox button's checked state and fire ``on_change``."""
    state = _state_of(btn)
    merged = state.get("props") or {}
    if merged.get("disabled"):
        return
    new_value = not bool(state.get("value"))
    # Optimistic local flip so the box feels instant even if the
    # app's re-render is a frame behind; the authoritative ``value``
    # prop re-syncs it on the next update.
    state["value"] = new_value
    _checkbox_set_image(btn)
    _fire(btn, "on_change", new_value)


class CheckboxHandler(IOSViewHandler):
    def _build(self, props: Dict[str, Any]) -> Any:
        btn = ObjCClass("UIButton").buttonWithType_(0)  # UIButtonTypeCustom
        btn.setTranslatesAutoresizingMaskIntoConstraints_(True)
        btn.retain()
        _pn_retained_views.append(btn)
        _register_control_action(btn, 1 << 6, lambda: _checkbox_toggle(btn))  # TouchUpInside
        return btn

    def _apply(self, btn: Any, props: Dict[str, Any], initial: bool) -> None:
        state = _state_of(btn)
        if initial:
            # UIButtonTypeCustom defaults to a white title and inherits
            # no useful tint, so both the label and the SF Symbol box
            # are invisible on light backgrounds without an explicit
            # color.
            try:
                btn.setTitleColor_forState_(_uicolor("#111111"), 0)
                btn.setTintColor_(_uicolor("#111111"))
            except Exception:
                pass
        if "value" in props:
            state["value"] = bool(props["value"])
        if "label" in props:
            label = props["label"]
            try:
                btn.setTitle_forState_(str(label) if label is not None else "", 0)
            except Exception:
                pass
            # An image-bearing custom button is not exposed to the
            # accessibility tree by title alone; mirror the label
            # explicitly (an accessibility_label prop still wins below).
            try:
                btn.setAccessibilityLabel_(str(label) if label is not None else "")
            except Exception:
                pass
        if "disabled" in props:
            # ``disabled`` is present only when True; a removed prop
            # (None) re-enables the control.
            disabled = bool(props["disabled"]) if props["disabled"] is not None else False
            try:
                btn.setEnabled_(not disabled)
            except Exception:
                pass
        _checkbox_set_image(btn)
        _apply_accessibility(btn, props)

    def measure_intrinsic(self, native_view: Any, max_width: float, max_height: float) -> Tuple[float, float]:
        try:
            mw = _safe_max(max_width, fallback=10000.0)
            mh = _safe_max(max_height, fallback=10000.0)
            size = native_view.sizeThatFits_((mw, mh))
            w = max(float(size.width) + 8.0, 28.0)
            h = max(float(size.height), 28.0)
            if math.isfinite(max_width):
                w = min(w, max_width)
            return (w, h)
        except Exception:
            return (28.0, 28.0)


# ======================================================================
# SegmentedControl: native UISegmentedControl
# ======================================================================


class SegmentedControlHandler(IOSViewHandler):
    def _build(self, props: Dict[str, Any]) -> Any:
        UISegmentedControl = ObjCClass("UISegmentedControl")
        segments = [str(s) for s in (props.get("segments") or [])]
        control = UISegmentedControl.alloc().initWithItems_(segments)
        control.setTranslatesAutoresizingMaskIntoConstraints_(True)
        control.retain()
        _pn_retained_views.append(control)

        def _on_change() -> None:
            if _state_of(control).get("suppress"):
                return
            try:
                index = int(control.selectedSegmentIndex)
            except Exception:
                return
            _fire(control, "on_change", index)

        _register_control_action(control, 1 << 12, _on_change)  # ValueChanged
        return control

    def _apply(self, control: Any, props: Dict[str, Any], initial: bool) -> None:
        state = _state_of(control)
        merged = state.get("props") or props
        rebuilt = False
        if "segments" in props and props["segments"] is not None and not initial:
            new_segments = [str(s) for s in props["segments"]]
            if new_segments != state.get("segments"):
                state["suppress"] = True
                try:
                    control.removeAllSegments()
                    for i, title in enumerate(new_segments):
                        control.insertSegmentWithTitle_atIndex_animated_(title, i, False)
                except Exception:
                    pass
                finally:
                    state["suppress"] = False
                rebuilt = True
        if "segments" in props and props["segments"] is not None:
            state["segments"] = [str(s) for s in props["segments"]]
        # Apply the selection when it changed or after a segment rebuild
        # (rebuilding resets the control to "no segment selected").
        if rebuilt or ("selected_index" in props and props["selected_index"] is not None) or initial:
            state["suppress"] = True
            try:
                control.setSelectedSegmentIndex_(int(merged.get("selected_index", 0) or 0))
            except Exception:
                pass
            finally:
                state["suppress"] = False
        if "tint_color" in props and props["tint_color"] is not None:
            color = _uicolor(props["tint_color"])
            try:
                control.setSelectedSegmentTintColor_(color)  # iOS 13+
            except Exception:
                pass
            try:
                control.setTintColor_(color)
            except Exception:
                pass
        if "enabled" in props:
            # ``enabled`` is present only when False; a removed prop
            # (None) re-enables the control.
            enabled = props["enabled"]
            try:
                control.setEnabled_(True if enabled is None else bool(enabled))
            except Exception:
                pass
        _apply_accessibility(control, props)

    def measure_intrinsic(self, native_view: Any, max_width: float, max_height: float) -> Tuple[float, float]:
        try:
            mw = _safe_max(max_width, fallback=10000.0)
            mh = _safe_max(max_height, fallback=10000.0)
            size = native_view.sizeThatFits_((mw, mh))
            w = float(size.width)
            if math.isfinite(max_width):
                w = min(w, max_width)
            return (max(w, 0.0), max(float(size.height), 0.0))
        except Exception:
            return (0.0, 0.0)


# ======================================================================
# DatePicker: native UIDatePicker (compact style on iOS 13.4+)
# ======================================================================


_DATE_PICKER_FORMATS = {"date": "yyyy-MM-dd", "time": "HH:mm", "datetime": "yyyy-MM-dd'T'HH:mm"}
_pn_date_formatters: Dict[str, Any] = {}


def _date_formatter(mode: str) -> Any:
    """Return a cached ``NSDateFormatter`` for the given picker mode."""
    fmt = _DATE_PICKER_FORMATS.get(mode, _DATE_PICKER_FORMATS["date"])
    cached = _pn_date_formatters.get(fmt)
    if cached is not None:
        return cached
    formatter = ObjCClass("NSDateFormatter").alloc().init()
    formatter.setDateFormat_(fmt)
    # A fixed POSIX locale keeps fixed-format parsing deterministic
    # (24-hour clock, no calendar/locale surprises) per Apple guidance.
    try:
        NSLocale = ObjCClass("NSLocale")
        formatter.setLocale_(NSLocale.alloc().initWithLocaleIdentifier_("en_US_POSIX"))
    except Exception:
        pass
    formatter.retain()
    _pn_date_formatters[fmt] = formatter
    return formatter


class DatePickerHandler(IOSViewHandler):
    def _build(self, props: Dict[str, Any]) -> Any:
        picker = ObjCClass("UIDatePicker").alloc().init()
        picker.setTranslatesAutoresizingMaskIntoConstraints_(True)
        picker.retain()
        _pn_retained_views.append(picker)
        # iOS 13.4+ compact style keeps the picker a small, leaf-sized
        # control instead of a full-width wheel.
        try:
            picker.setPreferredDatePickerStyle_(2)  # UIDatePickerStyleCompact
        except Exception:
            pass

        def _on_change() -> None:
            state = _state_of(picker)
            if state.get("suppress"):
                return
            mode = (state.get("props") or {}).get("mode", "date")
            try:
                iso = str(_date_formatter(mode).stringFromDate_(picker.date))
            except Exception:
                return
            _fire(picker, "on_change", iso)

        _register_control_action(picker, 1 << 12, _on_change)  # ValueChanged
        return picker

    def _apply(self, picker: Any, props: Dict[str, Any], initial: bool) -> None:
        state = _state_of(picker)
        merged = state.get("props") or props
        mode = str(merged.get("mode", "date") or "date")
        if "mode" in props and props["mode"] is not None:
            mode_map = {"time": 0, "date": 1, "datetime": 2}
            try:
                picker.setDatePickerMode_(mode_map.get(mode, 1))
            except Exception:
                pass
        if "minimum" in props:
            self._set_bound(picker, "setMinimumDate_", props["minimum"], mode)
        if "maximum" in props:
            self._set_bound(picker, "setMaximumDate_", props["maximum"], mode)
        if "value" in props and props["value"]:
            try:
                date = _date_formatter(mode).dateFromString_(str(props["value"]))
            except Exception:
                date = None
            if date is not None:
                state["suppress"] = True
                try:
                    picker.setDate_animated_(date, False)
                except Exception:
                    pass
                finally:
                    state["suppress"] = False
        if "enabled" in props:
            # ``enabled`` is present only when False; a removed prop
            # (None) re-enables the picker.
            enabled = props["enabled"]
            try:
                picker.setEnabled_(True if enabled is None else bool(enabled))
            except Exception:
                pass
        _apply_accessibility(picker, props)

    def _set_bound(self, picker: Any, selector: str, value: Any, mode: str) -> None:
        try:
            if not value:
                getattr(picker, selector)(None)
                return
            date = _date_formatter(mode).dateFromString_(str(value))
            getattr(picker, selector)(date)
        except Exception:
            pass

    def measure_intrinsic(self, native_view: Any, max_width: float, max_height: float) -> Tuple[float, float]:
        try:
            mw = _safe_max(max_width, fallback=10000.0)
            mh = _safe_max(max_height, fallback=10000.0)
            size = native_view.sizeThatFits_((mw, mh))
            w = float(size.width)
            if math.isfinite(max_width):
                w = min(w, max_width)
            return (max(w, 0.0), max(float(size.height), 0.0))
        except Exception:
            return (0.0, 0.0)


# ======================================================================
# Registration
# ======================================================================


def register_handlers(registry: Any) -> None:
    """Register all iOS view handlers with the given registry."""
    flex = FlexContainerHandler()
    registry.register("View", flex)
    registry.register("Column", flex)
    registry.register("Row", flex)
    registry.register("Text", TextHandler())
    registry.register("Button", ButtonHandler())
    registry.register("TextInput", TextInputHandler())
    registry.register("Image", ImageHandler())
    registry.register("Switch", SwitchHandler())
    registry.register("ProgressBar", ProgressBarHandler())
    registry.register("ActivityIndicator", ActivityIndicatorHandler())
    registry.register("WebView", WebViewHandler())
    registry.register("Spacer", SpacerHandler())
    registry.register("ScrollView", ScrollViewHandler())
    registry.register("SafeAreaView", SafeAreaViewHandler())
    registry.register("Modal", ModalHandler())
    registry.register("Slider", SliderHandler())
    registry.register("TabBar", TabBarHandler())
    registry.register("Pressable", PressableHandler())
    registry.register("StatusBar", StatusBarHandler())
    registry.register("KeyboardAvoidingView", KeyboardAvoidingViewHandler())
    registry.register("Picker", PickerHandler())
    registry.register("Checkbox", CheckboxHandler())
    registry.register("SegmentedControl", SegmentedControlHandler())
    registry.register("DatePicker", DatePickerHandler())


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
    "PickerHandler",
    "CheckboxHandler",
    "SegmentedControlHandler",
    "DatePickerHandler",
    "register_handlers",
]
