"""Desktop native-view handlers (Tkinter).

The desktop backend renders a PythonNative app in a real OS window so
the inner development loop doesn't require a device build. It is driven
by ``pn preview`` (which sets ``PN_PLATFORM=desktop``) and powers the
in-process Fast Refresh loop in ``pythonnative.preview``.

Like the iOS and Android backends, **layout is owned by the pure-Python
flex engine** in [`pythonnative.layout`][pythonnative.layout]: the
reconciler computes each view's ``(x, y, width, height)`` in points and
[`set_frame`][pythonnative.native_views.desktop.DesktopViewHandler.set_frame]
applies it. Handlers therefore only deal with *visual* props (text,
colors, fonts, callbacks) and ignore everything in
[`LAYOUT_STYLE_KEYS`][pythonnative.layout.LAYOUT_STYLE_KEYS].

Placement strategy
------------------
Tkinter fixes a widget's master at construction time, but the
reconciler creates a view *before* it knows the parent (``create`` then
``add_child``). To bridge that, every widget is created under a single
shared *stage* frame (see
[`set_root_container`][pythonnative.native_views.desktop.set_root_container])
and positioned with ``place(in_=parent, ...)``. Tk's ``-in`` option
composes coordinates through nested parents, so the engine's
parent-relative frames render correctly without reparenting.

Scope
-----
This is a **preview** backend, not a production desktop target. It
favors fidelity of layout and behavior over pixel-perfect chrome:
rounded corners, shadows, per-widget opacity, and overflow clipping are
approximated or omitted (Tkinter can't express them cheaply). Every one
of the 25 built-in element types is handled so any app renders without
errors.

This module imports ``tkinter`` at import time, so it is only imported
when ``PN_PLATFORM=desktop``. Off-device unit tests inject a mock
registry via [`set_registry`][pythonnative.native_views.set_registry]
and never trigger this path.
"""

from __future__ import annotations

import math
import re
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk
from typing import Any, Dict, List, Optional, Tuple

from .base import ViewHandler

# ======================================================================
# Stage / root container
# ======================================================================
#
# Every Tk widget the backend creates is a child of this single frame.
# ``pn preview`` installs it before mounting the app; the placement
# logic (``_place``) positions widgets *inside* their logical parent via
# Tk's ``-in`` option, which only works when both windows share a
# top-level — guaranteed by the single-stage design.

_ROOT_CONTAINER: Any = None
_DEFAULT_FONT_SIZE = 15


def set_root_container(container: Any) -> None:
    """Install the stage frame that every desktop view is created under.

    Called by ``pythonnative.preview`` before the
    first screen is mounted. ``container`` must be a Tk widget (a
    ``Frame`` filling the preview window).
    """
    global _ROOT_CONTAINER
    _ROOT_CONTAINER = container


def get_root_container() -> Any:
    """Return the installed stage frame, or ``None`` if unset."""
    return _ROOT_CONTAINER


def clear_root_container() -> None:
    """Forget the stage frame (used when the preview window closes)."""
    global _ROOT_CONTAINER
    _ROOT_CONTAINER = None


def _master() -> Any:
    """Return the master widget new views should be constructed under."""
    if _ROOT_CONTAINER is not None:
        return _ROOT_CONTAINER
    # Fall back to Tk's default root so the handlers stay usable in a
    # bare REPL / test that created a Tk root but no explicit stage.
    return tk._get_default_root()


# ======================================================================
# Color + font helpers
# ======================================================================

_NAMED_PASSTHROUGH = re.compile(r"^[A-Za-z][A-Za-z0-9 ]*$")
_BOLD_WORDS = frozenset({"bold", "semibold", "black", "heavy", "extrabold", "extra_bold", "semi_bold"})


def _tk_color(value: Any) -> Optional[str]:
    """Convert a PythonNative color into a Tk color string.

    Accepts ``#rgb`` / ``#rrggbb`` / ``#aarrggbb`` hex (alpha is
    dropped — Tk has no per-color alpha), ``rgb()`` / ``rgba()``
    functional notation, ``(r, g, b)`` tuples, packed integers, and
    named colors (passed through for Tk to resolve). Returns ``None``
    for ``transparent`` / unparseable values so callers can leave the
    widget's default background untouched.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return "#%06x" % (value & 0xFFFFFF)
    if isinstance(value, (tuple, list)) and len(value) >= 3:
        try:
            r, g, b = (int(value[0]) & 255, int(value[1]) & 255, int(value[2]) & 255)
            return "#%02x%02x%02x" % (r, g, b)
        except (TypeError, ValueError):
            return None
    s = str(value).strip()
    if not s:
        return None
    low = s.lower()
    if low in ("transparent", "clear", "none"):
        return None
    if s.startswith("#"):
        hexd = s[1:]
        if len(hexd) == 3:
            return "#" + "".join(c * 2 for c in hexd)
        if len(hexd) == 4:  # #rgba -> drop alpha
            return "#" + "".join(c * 2 for c in hexd[:3])
        if len(hexd) == 6:
            return "#" + hexd
        if len(hexd) == 8:  # #aarrggbb -> drop leading alpha
            return "#" + hexd[2:]
        return None
    if low.startswith("rgb"):
        nums = re.findall(r"[\d.]+", s)
        if len(nums) >= 3:
            try:
                r, g, b = (int(float(nums[0])) & 255, int(float(nums[1])) & 255, int(float(nums[2])) & 255)
                return "#%02x%02x%02x" % (r, g, b)
            except ValueError:
                return None
        return None
    if _NAMED_PASSTHROUGH.match(s):
        return s
    return None


def _is_bold(props: Dict[str, Any]) -> bool:
    """Return whether the merged props imply a bold weight."""
    if props.get("bold"):
        return True
    weight = props.get("font_weight")
    if isinstance(weight, str):
        return weight.lower() in _BOLD_WORDS
    if isinstance(weight, (int, float)) and not isinstance(weight, bool):
        return float(weight) >= 600
    return False


def _make_font(props: Dict[str, Any]) -> Any:
    """Build a ``tkinter.font.Font`` from the merged style props.

    Sizes are passed as negative values (Tk's convention for *pixels*)
    so the rendered text and ``measure_intrinsic`` agree with the
    layout engine's pixel coordinate space.
    """
    size = props.get("font_size")
    try:
        px = int(round(float(size))) if size is not None else _DEFAULT_FONT_SIZE
    except (TypeError, ValueError):
        px = _DEFAULT_FONT_SIZE
    px = max(1, px)
    kwargs: Dict[str, Any] = {
        "size": -px,
        "weight": "bold" if _is_bold(props) else "normal",
        "slant": "italic" if props.get("italic") else "roman",
    }
    family = props.get("font_family")
    if family:
        kwargs["family"] = str(family)
    decoration = props.get("text_decoration")
    if decoration == "underline":
        kwargs["underline"] = 1
    elif decoration == "line_through":
        kwargs["overstrike"] = 1
    try:
        return tkfont.Font(**kwargs)
    except Exception:
        return tkfont.Font(size=-px)


def _measure_text(font: Any, text: str, max_width: float) -> Tuple[float, float]:
    """Return the ``(width, height)`` a string occupies in ``font``.

    Honors explicit newlines and greedily word-wraps paragraphs wider
    than ``max_width`` (``math.inf`` means no wrap) so multi-line
    ``Text`` measures the same height the engine will lay out.
    """
    try:
        line_h = float(font.metrics("linespace"))
    except Exception:
        line_h = float(_DEFAULT_FONT_SIZE + 4)
    if not text:
        return (0.0, line_h)
    bounded = math.isfinite(max_width) and max_width > 0
    longest = 0.0
    lines = 0
    for paragraph in text.split("\n"):
        if not paragraph:
            lines += 1
            continue
        para_w = float(font.measure(paragraph))
        if not bounded or para_w <= max_width:
            lines += 1
            longest = max(longest, para_w)
            continue
        current = ""
        for word in paragraph.split(" "):
            trial = word if not current else current + " " + word
            if not current or font.measure(trial) <= max_width:
                current = trial
            else:
                lines += 1
                longest = max(longest, float(font.measure(current)))
                current = word
        lines += 1
        longest = max(longest, float(font.measure(current)))
    width = min(longest, max_width) if bounded else longest
    return (math.ceil(width), math.ceil(lines * line_h))


def _finite(value: Any, default: float = 0.0) -> float:
    """Coerce ``value`` to a finite float, clamping NaN/inf to ``default``."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    return f if math.isfinite(f) else default


# ======================================================================
# Placement (ordering-independent)
# ======================================================================


def _merge_props(widget: Any, props: Dict[str, Any]) -> Dict[str, Any]:
    """Accumulate ``props`` onto the widget so partial updates stay coherent.

    The reconciler delivers only *changed* keys on update; Tk needs the
    full picture to rebuild a font or re-derive a layout, so each
    widget caches its merged props under ``_pn_props``.
    """
    merged: Dict[str, Any] = getattr(widget, "_pn_props", None) or {}
    merged.update(props)
    widget._pn_props = merged
    return merged


def _place(widget: Any) -> None:
    """Position ``widget`` inside its logical parent, if both are known.

    Idempotent and order-independent: ``set_frame`` records the frame
    and ``add_child`` records the parent; whichever runs second triggers
    the actual ``place``. Coordinates compose through nested ``-in``
    parents, so a child's parent-relative frame lands at the right
    absolute spot.
    """
    frame = getattr(widget, "_pn_frame", None)
    if frame is None:
        return
    parent = getattr(widget, "_pn_parent", None)
    target = parent if parent is not None else get_root_container()
    if target is None:
        return
    x, y, w, h = frame
    tx, ty = getattr(widget, "_pn_translate", (0.0, 0.0))
    try:
        widget.place(in_=target, x=x + tx, y=y + ty, width=max(0.0, w), height=max(0.0, h))
        widget.lift()
    except Exception:
        pass


def _set_translate_from_transform(widget: Any, spec: Any) -> None:
    """Extract a translate offset from a ``transform`` prop for placement.

    Tkinter can't scale or rotate widgets, but translation maps cleanly
    onto ``place`` coordinates, so animated/transformed views still move
    in the preview. Scale and rotate are ignored.
    """
    tx = 0.0
    ty = 0.0
    if spec is not None:
        entries = spec if isinstance(spec, list) else [spec]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if "translate_x" in entry:
                tx = _finite(entry["translate_x"])
            if "translate_y" in entry:
                ty = _finite(entry["translate_y"])
    widget._pn_translate = (tx, ty)


def _apply_common(widget: Any, props: Dict[str, Any]) -> None:
    """Apply visual props shared across most handlers (bg, border, transform)."""
    if "background_color" in props:
        color = _tk_color(props["background_color"])
        if color is not None:
            try:
                widget.configure(background=color)
            except Exception:
                pass
    if any(k in props for k in ("border_width", "border_color")):
        try:
            width = props.get("border_width")
            color = _tk_color(props.get("border_color")) or "#3c3c43"
            if width:
                widget.configure(
                    highlightthickness=int(round(_finite(width))),
                    highlightbackground=color,
                    highlightcolor=color,
                )
            else:
                widget.configure(highlightthickness=0)
        except Exception:
            pass
    if "transform" in props:
        _set_translate_from_transform(widget, props["transform"])
        _place(widget)


# ======================================================================
# Base handler
# ======================================================================


class DesktopViewHandler(ViewHandler):
    """Shared ``set_frame`` / child / measure behavior for Tk handlers.

    Concrete handlers implement ``create`` / ``update`` (and optionally
    ``measure_intrinsic``); child management and frame application are
    inherited and route through the order-independent
    [`_place`][pythonnative.native_views.desktop._place] helper.
    """

    def add_child(self, parent: Any, child: Any) -> None:
        child._pn_parent = parent
        _place(child)

    def insert_child(self, parent: Any, child: Any, index: int) -> None:
        child._pn_parent = parent
        _place(child)

    def remove_child(self, parent: Any, child: Any) -> None:
        try:
            child.place_forget()
        except Exception:
            pass
        child._pn_parent = None

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        if native_view is None:
            return
        native_view._pn_frame = (_finite(x), _finite(y), max(0.0, _finite(width)), max(0.0, _finite(height)))
        _place(native_view)

    def measure_intrinsic(self, native_view: Any, max_width: float, max_height: float) -> Tuple[float, float]:
        return (0.0, 0.0)

    def set_animated_property(
        self,
        native_view: Any,
        prop_name: str,
        value: Any,
        duration_ms: float = 0.0,
        easing: str = "linear",
    ) -> None:
        """Apply the final value of an animated property (no tween).

        The preview shows animation *end states* rather than smooth
        interpolation. Translation maps onto placement; opacity, scale,
        and rotation have no cheap Tk analogue and are skipped.
        """
        if native_view is None:
            return
        if prop_name == "translate_x":
            _, ty = getattr(native_view, "_pn_translate", (0.0, 0.0))
            native_view._pn_translate = (_finite(value), ty)
            _place(native_view)
        elif prop_name == "translate_y":
            tx, _ = getattr(native_view, "_pn_translate", (0.0, 0.0))
            native_view._pn_translate = (tx, _finite(value))
            _place(native_view)
        elif prop_name == "background_color":
            color = _tk_color(value)
            if color is not None:
                try:
                    native_view.configure(background=color)
                except Exception:
                    pass


# ======================================================================
# Containers (View / Column / Row / SafeAreaView / KeyboardAvoidingView)
# ======================================================================


class FlexContainerHandler(DesktopViewHandler):
    """A bare positioning surface (``tk.Frame``).

    All flex semantics are computed by the layout engine and applied via
    ``set_frame``; the frame only carries visual chrome (background,
    border).
    """

    def create(self, props: Dict[str, Any]) -> Any:
        frame = tk.Frame(_master(), highlightthickness=0, bd=0)
        _apply_common(frame, _merge_props(frame, props))
        return frame

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        _apply_common(native_view, _merge_props(native_view, changed))


class ScrollViewHandler(FlexContainerHandler):
    """Preview ScrollView — a plain frame.

    The layout engine still lets the content grow past the viewport on
    the scroll axis; the desktop preview renders that overflow without
    interactive scrolling or clipping (a documented preview limitation).
    """


class SafeAreaViewHandler(FlexContainerHandler):
    """Desktop has no notch/home-indicator insets, so this is a frame."""


class KeyboardAvoidingViewHandler(FlexContainerHandler):
    """No soft keyboard on desktop; behaves as a plain frame."""


# ======================================================================
# Text
# ======================================================================


_ANCHOR_FOR_ALIGN = {"left": "w", "center": "center", "right": "e"}
_JUSTIFY_FOR_ALIGN = {"left": "left", "center": "center", "right": "right"}


class TextHandler(DesktopViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        label = tk.Label(_master(), highlightthickness=0, bd=0, padx=0, pady=0)
        self._apply(label, props)
        return label

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _apply(self, label: Any, props: Dict[str, Any]) -> None:
        merged = _merge_props(label, props)
        text = merged.get("text")
        label._pn_text = "" if text is None else str(text)
        font = _make_font(merged)
        label._pn_font = font
        opts: Dict[str, Any] = {"text": label._pn_text, "font": font}
        color = _tk_color(merged.get("color"))
        if color is not None:
            opts["foreground"] = color
        align = merged.get("text_align")
        if align in _ANCHOR_FOR_ALIGN:
            opts["anchor"] = _ANCHOR_FOR_ALIGN[align]
            opts["justify"] = _JUSTIFY_FOR_ALIGN[align]
        else:
            opts["anchor"] = "w"
            opts["justify"] = "left"
        try:
            label.configure(**opts)
        except Exception:
            pass
        _apply_common(label, merged)

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        # Wrap to the laid-out width so multi-line text flows the way the
        # engine measured it.
        try:
            native_view.configure(wraplength=max(1, int(_finite(width))))
        except Exception:
            pass
        super().set_frame(native_view, x, y, width, height)

    def measure_intrinsic(self, native_view: Any, max_width: float, max_height: float) -> Tuple[float, float]:
        font = getattr(native_view, "_pn_font", None)
        if font is None:
            return (0.0, 0.0)
        text = getattr(native_view, "_pn_text", "")
        return _measure_text(font, text, max_width)


# ======================================================================
# Button
# ======================================================================


class ButtonHandler(DesktopViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        button = tk.Button(_master(), highlightthickness=0, takefocus=0)
        self._apply(button, props)
        return button

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _apply(self, button: Any, props: Dict[str, Any]) -> None:
        merged = _merge_props(button, props)
        title = merged.get("title")
        button._pn_text = "" if title is None else str(title)
        font = _make_font(merged)
        button._pn_font = font
        opts: Dict[str, Any] = {"text": button._pn_text, "font": font}
        color = _tk_color(merged.get("color"))
        if color is not None:
            opts["foreground"] = color
        bg = _tk_color(merged.get("background_color"))
        if bg is not None:
            opts["background"] = bg
            opts["activebackground"] = bg
        if "enabled" in merged:
            opts["state"] = "normal" if merged.get("enabled", True) else "disabled"
        try:
            button.configure(**opts)
        except Exception:
            pass
        if "on_click" in props:
            callback = props["on_click"]

            def _command() -> None:
                if callable(callback):
                    try:
                        callback()
                    except Exception:
                        pass

            try:
                button.configure(command=_command if callable(callback) else "")
            except Exception:
                pass
        _apply_common(button, merged)

    def measure_intrinsic(self, native_view: Any, max_width: float, max_height: float) -> Tuple[float, float]:
        font = getattr(native_view, "_pn_font", None)
        text = getattr(native_view, "_pn_text", "")
        if font is None:
            return (0.0, 0.0)
        w, h = _measure_text(font, text, math.inf)
        return (w + 28.0, h + 14.0)


# ======================================================================
# TextInput
# ======================================================================


class TextInputHandler(DesktopViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        multiline = bool(props.get("multiline"))
        widget: Any
        if multiline:
            widget = tk.Text(_master(), highlightthickness=1, bd=0, wrap="word", height=1)
        else:
            widget = tk.Entry(_master(), highlightthickness=1, bd=0)
        widget._pn_multiline = multiline
        widget._pn_suppress = False
        self._bind(widget, props)
        self._apply(widget, props)
        return widget

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _current_text(self, widget: Any) -> str:
        try:
            if getattr(widget, "_pn_multiline", False):
                return widget.get("1.0", "end-1c")
            return widget.get()
        except Exception:
            return ""

    def _set_text(self, widget: Any, value: str) -> None:
        widget._pn_suppress = True
        try:
            if getattr(widget, "_pn_multiline", False):
                widget.delete("1.0", "end")
                widget.insert("1.0", value)
            else:
                widget.delete(0, "end")
                widget.insert(0, value)
        except Exception:
            pass
        finally:
            widget._pn_suppress = False

    def _bind(self, widget: Any, props: Dict[str, Any]) -> None:
        def _on_key(_event: Any = None) -> None:
            if getattr(widget, "_pn_suppress", False):
                return
            callback = getattr(widget, "_pn_on_change", None)
            if callable(callback):
                try:
                    callback(self._current_text(widget))
                except Exception:
                    pass

        def _on_return(_event: Any = None) -> str:
            callback = getattr(widget, "_pn_on_submit", None)
            if callable(callback):
                try:
                    callback(self._current_text(widget))
                except Exception:
                    pass
            return "break"

        try:
            widget.bind("<KeyRelease>", _on_key)
            if not getattr(widget, "_pn_multiline", False):
                widget.bind("<Return>", _on_return)
        except Exception:
            pass

    def _apply(self, widget: Any, props: Dict[str, Any]) -> None:
        merged = _merge_props(widget, props)
        if "on_change" in props:
            widget._pn_on_change = props["on_change"]
        if "on_submit" in props:
            widget._pn_on_submit = props["on_submit"]
        opts: Dict[str, Any] = {"font": _make_font(merged)}
        color = _tk_color(merged.get("color"))
        if color is not None:
            opts["foreground"] = color
        bg = _tk_color(merged.get("background_color"))
        if bg is not None:
            opts["background"] = bg
        if not getattr(widget, "_pn_multiline", False) and merged.get("secure"):
            opts["show"] = "\u2022"
        if "editable" in merged:
            opts["state"] = "normal" if merged.get("editable", True) else "disabled"
        try:
            widget.configure(**opts)
        except Exception:
            pass
        if "value" in props:
            incoming = "" if props["value"] is None else str(props["value"])
            if self._current_text(widget) != incoming:
                self._set_text(widget, incoming)
        _apply_common(widget, merged)
        try:
            widget.configure(highlightbackground="#c7c7cc", highlightcolor="#007aff")
        except Exception:
            pass

    def measure_intrinsic(self, native_view: Any, max_width: float, max_height: float) -> Tuple[float, float]:
        merged = getattr(native_view, "_pn_props", {}) or {}
        font = _make_font(merged)
        try:
            line_h = float(font.metrics("linespace"))
        except Exception:
            line_h = float(_DEFAULT_FONT_SIZE + 4)
        return (160.0, line_h + 16.0)


# ======================================================================
# Image
# ======================================================================


class ImageHandler(DesktopViewHandler):
    """Best-effort image preview.

    Tk's ``PhotoImage`` loads PNG/GIF/PPM from local paths; network URLs
    and JPEG aren't supported without Pillow, so those fall back to a
    labeled placeholder. The handler keeps a reference to the
    ``PhotoImage`` (Tk garbage-collects images that aren't referenced).
    """

    def create(self, props: Dict[str, Any]) -> Any:
        label = tk.Label(_master(), highlightthickness=0, bd=0, background="#d1d1d6")
        self._apply(label, props)
        return label

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _apply(self, label: Any, props: Dict[str, Any]) -> None:
        merged = _merge_props(label, props)
        if "source" in props:
            source = props.get("source")
            photo = None
            if source and "://" not in str(source):
                try:
                    photo = tk.PhotoImage(file=str(source))
                except Exception:
                    photo = None
            label._pn_photo = photo  # keep a reference alive
            try:
                if photo is not None:
                    label.configure(image=photo, text="")
                else:
                    name = str(source).rsplit("/", 1)[-1] if source else "image"
                    label.configure(image="", text=f"\U0001f5bc\n{name}", compound="center")
            except Exception:
                pass
        _apply_common(label, merged)

    def measure_intrinsic(self, native_view: Any, max_width: float, max_height: float) -> Tuple[float, float]:
        photo = getattr(native_view, "_pn_photo", None)
        if photo is not None:
            try:
                return (float(photo.width()), float(photo.height()))
            except Exception:
                pass
        return (64.0, 64.0)


# ======================================================================
# Switch / Checkbox
# ======================================================================


class SwitchHandler(DesktopViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        var = tk.IntVar(master=_master(), value=1 if props.get("value") else 0)
        check = tk.Checkbutton(_master(), variable=var, takefocus=0, highlightthickness=0, text="")
        check._pn_var = var
        self._bind(check, props)
        self._apply(check, props)
        return check

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _bind(self, check: Any, props: Dict[str, Any]) -> None:
        def _command() -> None:
            callback = getattr(check, "_pn_on_change", None)
            if callable(callback):
                try:
                    callback(bool(check._pn_var.get()))
                except Exception:
                    pass

        try:
            check.configure(command=_command)
        except Exception:
            pass

    def _apply(self, check: Any, props: Dict[str, Any]) -> None:
        merged = _merge_props(check, props)
        if "on_change" in props:
            check._pn_on_change = props["on_change"]
        if "value" in props:
            try:
                check._pn_var.set(1 if props.get("value") else 0)
            except Exception:
                pass
        _apply_common(check, merged)

    def measure_intrinsic(self, native_view: Any, max_width: float, max_height: float) -> Tuple[float, float]:
        return (51.0, 31.0)


class CheckboxHandler(DesktopViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        var = tk.IntVar(master=_master(), value=1 if props.get("value") else 0)
        check = tk.Checkbutton(_master(), variable=var, takefocus=0, highlightthickness=0, anchor="w")
        check._pn_var = var
        self._bind(check, props)
        self._apply(check, props)
        return check

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _bind(self, check: Any, props: Dict[str, Any]) -> None:
        def _command() -> None:
            callback = getattr(check, "_pn_on_change", None)
            if callable(callback):
                try:
                    callback(bool(check._pn_var.get()))
                except Exception:
                    pass

        try:
            check.configure(command=_command)
        except Exception:
            pass

    def _apply(self, check: Any, props: Dict[str, Any]) -> None:
        merged = _merge_props(check, props)
        if "on_change" in props:
            check._pn_on_change = props["on_change"]
        opts: Dict[str, Any] = {}
        if "label" in merged:
            opts["text"] = "" if merged.get("label") is None else str(merged["label"])
        if "disabled" in merged:
            opts["state"] = "disabled" if merged.get("disabled") else "normal"
        color = _tk_color(merged.get("color"))
        if color is not None:
            opts["selectcolor"] = color
        if opts:
            try:
                check.configure(**opts)
            except Exception:
                pass
        if "value" in props:
            try:
                check._pn_var.set(1 if props.get("value") else 0)
            except Exception:
                pass
        _apply_common(check, merged)


# ======================================================================
# Slider / ProgressBar / ActivityIndicator
# ======================================================================


class SliderHandler(DesktopViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        scale = tk.Scale(
            _master(),
            orient="horizontal",
            showvalue=False,
            highlightthickness=0,
            bd=0,
            sliderlength=20,
        )
        self._bind(scale, props)
        self._apply(scale, props)
        return scale

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _bind(self, scale: Any, props: Dict[str, Any]) -> None:
        def _command(_value: Any) -> None:
            callback = getattr(scale, "_pn_on_change", None)
            if callable(callback):
                try:
                    callback(float(scale.get()))
                except Exception:
                    pass

        try:
            scale.configure(command=_command)
        except Exception:
            pass

    def _apply(self, scale: Any, props: Dict[str, Any]) -> None:
        merged = _merge_props(scale, props)
        if "on_change" in props:
            scale._pn_on_change = props["on_change"]
        opts: Dict[str, Any] = {
            "from_": _finite(merged.get("min_value", 0.0)),
            "to": _finite(merged.get("max_value", 1.0)),
        }
        rng = opts["to"] - opts["from_"]
        opts["resolution"] = rng / 100.0 if rng > 0 else 0.01
        try:
            scale.configure(**opts)
        except Exception:
            pass
        if "value" in merged:
            scale._pn_suppress = True
            try:
                scale.set(_finite(merged.get("value")))
            except Exception:
                pass
            finally:
                scale._pn_suppress = False
        _apply_common(scale, merged)

    def measure_intrinsic(self, native_view: Any, max_width: float, max_height: float) -> Tuple[float, float]:
        width = max_width if math.isfinite(max_width) else 200.0
        return (width, 28.0)


class ProgressBarHandler(DesktopViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        bar = ttk.Progressbar(_master(), orient="horizontal", maximum=1.0)
        self._apply(bar, props)
        return bar

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _apply(self, bar: Any, props: Dict[str, Any]) -> None:
        merged = _merge_props(bar, props)
        if merged.get("indeterminate"):
            try:
                bar.configure(mode="indeterminate")
                bar.start(60)
            except Exception:
                pass
        else:
            try:
                bar.configure(mode="determinate", value=max(0.0, min(1.0, _finite(merged.get("value", 0.0)))))
            except Exception:
                pass

    def measure_intrinsic(self, native_view: Any, max_width: float, max_height: float) -> Tuple[float, float]:
        width = max_width if math.isfinite(max_width) else 200.0
        return (width, 6.0)


class ActivityIndicatorHandler(DesktopViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        bar = ttk.Progressbar(_master(), orient="horizontal", mode="indeterminate", length=40)
        self._apply(bar, props)
        return bar

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _apply(self, bar: Any, props: Dict[str, Any]) -> None:
        merged = _merge_props(bar, props)
        try:
            if merged.get("animating", True):
                bar.start(50)
            else:
                bar.stop()
        except Exception:
            pass

    def measure_intrinsic(self, native_view: Any, max_width: float, max_height: float) -> Tuple[float, float]:
        merged = getattr(native_view, "_pn_props", {}) or {}
        size = 52.0 if merged.get("size") == "large" else 37.0
        return (size, 20.0)


# ======================================================================
# Spacer / StatusBar / WebView
# ======================================================================


class SpacerHandler(DesktopViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        return tk.Frame(_master(), highlightthickness=0, bd=0)

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        pass


class StatusBarHandler(DesktopViewHandler):
    """Desktop has no system status bar; render an inert zero-size frame."""

    def create(self, props: Dict[str, Any]) -> Any:
        return tk.Frame(_master(), highlightthickness=0, bd=0)

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        pass


class WebViewHandler(DesktopViewHandler):
    """No embedded browser on desktop; show a labeled placeholder."""

    def create(self, props: Dict[str, Any]) -> Any:
        label = tk.Label(
            _master(),
            background="#1c1c1e",
            foreground="#ffffff",
            highlightthickness=0,
            justify="center",
        )
        self._apply(label, props)
        return label

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _apply(self, label: Any, props: Dict[str, Any]) -> None:
        merged = _merge_props(label, props)
        target = merged.get("url") or ("inline HTML" if merged.get("html") else "")
        try:
            label.configure(text=f"\U0001f310 WebView\n{target}")
        except Exception:
            pass
        _apply_common(label, merged)


# ======================================================================
# Pressable
# ======================================================================


class PressableHandler(DesktopViewHandler):
    """A frame that forwards click / long-press to its callbacks."""

    def create(self, props: Dict[str, Any]) -> Any:
        frame = tk.Frame(_master(), highlightthickness=0, bd=0, cursor="hand2")
        self._bind(frame)
        self._apply(frame, props)
        return frame

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _bind(self, frame: Any) -> None:
        def _on_press(_event: Any = None) -> None:
            callback = getattr(frame, "_pn_on_press", None)
            if callable(callback):
                try:
                    callback()
                except Exception:
                    pass

        def _schedule_long(_event: Any = None) -> None:
            callback = getattr(frame, "_pn_on_long_press", None)
            if callable(callback):
                frame._pn_long_after = frame.after(500, _fire_long)

        def _fire_long() -> None:
            callback = getattr(frame, "_pn_on_long_press", None)
            if callable(callback):
                try:
                    callback()
                except Exception:
                    pass

        def _cancel_long(_event: Any = None) -> None:
            after_id = getattr(frame, "_pn_long_after", None)
            if after_id is not None:
                try:
                    frame.after_cancel(after_id)
                except Exception:
                    pass
                frame._pn_long_after = None

        try:
            frame.bind("<ButtonRelease-1>", _on_press)
            frame.bind("<ButtonPress-1>", _schedule_long)
            frame.bind("<Leave>", _cancel_long)
        except Exception:
            pass

    def _apply(self, frame: Any, props: Dict[str, Any]) -> None:
        merged = _merge_props(frame, props)
        if "on_press" in props:
            frame._pn_on_press = props["on_press"]
        if "on_long_press" in props:
            frame._pn_on_long_press = props["on_long_press"]
        _apply_common(frame, merged)


# ======================================================================
# Modal
# ======================================================================


class ModalHandler(DesktopViewHandler):
    """Overlay modal — a frame that fills the stage when ``visible``.

    The reconciler lays the modal's content out against the full
    viewport (see ``Reconciler._layout_visible_modals``) and applies
    frames to the children, so this handler only toggles its own
    visibility and stacking.
    """

    def create(self, props: Dict[str, Any]) -> Any:
        frame = tk.Frame(_master(), highlightthickness=0, bd=0, background="#ffffff")
        self._apply(frame, props)
        return frame

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _apply(self, frame: Any, props: Dict[str, Any]) -> None:
        merged = _merge_props(frame, props)
        if merged.get("transparent"):
            try:
                frame.configure(background="#33000000".replace("33", ""))  # solid fallback
            except Exception:
                pass
        visible = bool(merged.get("visible"))
        stage = get_root_container()
        try:
            if visible and stage is not None:
                frame.place(in_=stage, x=0, y=0, relwidth=1.0, relheight=1.0)
                frame.lift()
            else:
                frame.place_forget()
        except Exception:
            pass

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        # Modal placement is driven by visibility in ``_apply``; the
        # engine never frames the placeholder itself.
        return


# ======================================================================
# TabBar
# ======================================================================


class TabBarHandler(DesktopViewHandler):
    """Bottom tab bar — a row of buttons laid out across its width."""

    def create(self, props: Dict[str, Any]) -> Any:
        frame = tk.Frame(_master(), highlightthickness=1, bd=0, background="#f2f2f7")
        try:
            frame.configure(highlightbackground="#c6c6c8", highlightcolor="#c6c6c8")
        except Exception:
            pass
        frame._pn_buttons = []
        self._apply(frame, props)
        return frame

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _apply(self, frame: Any, props: Dict[str, Any]) -> None:
        merged = _merge_props(frame, props)
        items: List[Dict[str, Any]] = merged.get("items") or []
        active = merged.get("active_tab")
        on_select = merged.get("on_tab_select")
        for button in getattr(frame, "_pn_buttons", []):
            try:
                button.destroy()
            except Exception:
                pass
        buttons: List[Any] = []
        for item in items:
            name = item.get("name")
            title = item.get("title", name)
            is_active = name == active

            def _make_cmd(tab_name: Any) -> Any:
                def _cmd() -> None:
                    if callable(on_select):
                        try:
                            on_select(tab_name)
                        except Exception:
                            pass

                return _cmd

            button = tk.Button(
                frame,
                text=str(title),
                command=_make_cmd(name),
                relief="flat",
                takefocus=0,
                highlightthickness=0,
                foreground="#007aff" if is_active else "#8e8e93",
                background="#f2f2f7",
                activebackground="#e5e5ea",
                borderwidth=0,
            )
            buttons.append(button)
        frame._pn_buttons = buttons
        self._layout_buttons(frame)

    def _layout_buttons(self, frame: Any) -> None:
        buttons = getattr(frame, "_pn_buttons", [])
        count = len(buttons)
        if count == 0:
            return
        frame_w, frame_h = getattr(frame, "_pn_size", (0.0, 0.0))
        if frame_w <= 0:
            return
        each = frame_w / count
        for i, button in enumerate(buttons):
            try:
                button.place(x=i * each, y=0, width=each, height=frame_h)
            except Exception:
                pass

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        native_view._pn_size = (max(0.0, _finite(width)), max(0.0, _finite(height)))
        super().set_frame(native_view, x, y, width, height)
        self._layout_buttons(native_view)

    def measure_intrinsic(self, native_view: Any, max_width: float, max_height: float) -> Tuple[float, float]:
        width = max_width if math.isfinite(max_width) else 320.0
        return (width, 49.0)


# ======================================================================
# Picker / SegmentedControl / DatePicker
# ======================================================================


class PickerHandler(DesktopViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        combo = ttk.Combobox(_master(), state="readonly")
        self._bind(combo)
        self._apply(combo, props)
        return combo

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _bind(self, combo: Any) -> None:
        def _on_select(_event: Any = None) -> None:
            callback = getattr(combo, "_pn_on_change", None)
            items = getattr(combo, "_pn_items", [])
            idx = combo.current()
            if callable(callback) and 0 <= idx < len(items):
                try:
                    callback(items[idx].get("value"))
                except Exception:
                    pass

        try:
            combo.bind("<<ComboboxSelected>>", _on_select)
        except Exception:
            pass

    def _apply(self, combo: Any, props: Dict[str, Any]) -> None:
        merged = _merge_props(combo, props)
        if "on_change" in props:
            combo._pn_on_change = props["on_change"]
        items: List[Dict[str, Any]] = merged.get("items") or []
        combo._pn_items = items
        labels = [str(item.get("label", item.get("value", ""))) for item in items]
        try:
            combo.configure(values=labels)
        except Exception:
            pass
        if "value" in merged:
            target = merged.get("value")
            for i, item in enumerate(items):
                if item.get("value") == target:
                    try:
                        combo.current(i)
                    except Exception:
                        pass
                    break

    def measure_intrinsic(self, native_view: Any, max_width: float, max_height: float) -> Tuple[float, float]:
        return (180.0, 30.0)


class SegmentedControlHandler(DesktopViewHandler):
    def create(self, props: Dict[str, Any]) -> Any:
        frame = tk.Frame(_master(), highlightthickness=0, bd=0)
        frame._pn_buttons = []
        self._apply(frame, props)
        return frame

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _apply(self, frame: Any, props: Dict[str, Any]) -> None:
        merged = _merge_props(frame, props)
        segments: List[str] = merged.get("segments") or []
        selected = int(merged.get("selected_index", 0) or 0)
        on_change = merged.get("on_change")
        tint = _tk_color(merged.get("tint_color")) or "#007aff"
        for button in getattr(frame, "_pn_buttons", []):
            try:
                button.destroy()
            except Exception:
                pass
        buttons: List[Any] = []
        for i, label in enumerate(segments):
            is_active = i == selected

            def _make_cmd(index: int) -> Any:
                def _cmd() -> None:
                    if callable(on_change):
                        try:
                            on_change(index)
                        except Exception:
                            pass

                return _cmd

            button = tk.Button(
                frame,
                text=str(label),
                command=_make_cmd(i),
                relief="flat",
                takefocus=0,
                highlightthickness=1,
                borderwidth=1,
                foreground="#ffffff" if is_active else tint,
                background=tint if is_active else "#ffffff",
            )
            try:
                state = "normal" if merged.get("enabled", True) else "disabled"
                button.configure({"highlightbackground": tint, "state": state})
            except Exception:
                pass
            buttons.append(button)
        frame._pn_buttons = buttons
        self._layout_buttons(frame)

    def _layout_buttons(self, frame: Any) -> None:
        buttons = getattr(frame, "_pn_buttons", [])
        count = len(buttons)
        if count == 0:
            return
        frame_w, frame_h = getattr(frame, "_pn_size", (0.0, 0.0))
        if frame_w <= 0:
            return
        each = frame_w / count
        for i, button in enumerate(buttons):
            try:
                button.place(x=i * each, y=0, width=each, height=frame_h)
            except Exception:
                pass

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        native_view._pn_size = (max(0.0, _finite(width)), max(0.0, _finite(height)))
        super().set_frame(native_view, x, y, width, height)
        self._layout_buttons(native_view)


class DatePickerHandler(DesktopViewHandler):
    """Preview DatePicker — a text entry for the ISO date/time string."""

    def create(self, props: Dict[str, Any]) -> Any:
        entry = tk.Entry(_master(), highlightthickness=1, bd=0)
        self._bind(entry)
        self._apply(entry, props)
        return entry

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        self._apply(native_view, changed)

    def _bind(self, entry: Any) -> None:
        def _on_key(_event: Any = None) -> None:
            callback = getattr(entry, "_pn_on_change", None)
            if callable(callback):
                try:
                    callback(entry.get())
                except Exception:
                    pass

        try:
            entry.bind("<KeyRelease>", _on_key)
        except Exception:
            pass

    def _apply(self, entry: Any, props: Dict[str, Any]) -> None:
        merged = _merge_props(entry, props)
        if "on_change" in props:
            entry._pn_on_change = props["on_change"]
        if "enabled" in merged:
            try:
                entry.configure(state="normal" if merged.get("enabled", True) else "disabled")
            except Exception:
                pass
        if "value" in props:
            incoming = "" if props["value"] is None else str(props["value"])
            try:
                if entry.get() != incoming:
                    state = str(entry.cget("state"))
                    entry.configure(state="normal")
                    entry.delete(0, "end")
                    entry.insert(0, incoming)
                    entry.configure(state=state)
            except Exception:
                pass
        try:
            entry.configure(highlightbackground="#c7c7cc", highlightcolor="#007aff")
        except Exception:
            pass


# ======================================================================
# VirtualList (FlatList / SectionList)
# ======================================================================


class VirtualListHandler(DesktopViewHandler):
    """Preview list — eagerly mounts a bounded window of rows.

    The native iOS/Android backends recycle cells; the desktop preview
    mounts up to [`_MAX_ROWS`][pythonnative.native_views.desktop.VirtualListHandler]
    rows into per-row cells once its frame is known. Each cell is handed
    to the ``mount_row`` callback supplied by
    [`FlatList`][pythonnative.FlatList] / [`SectionList`][pythonnative.SectionList],
    which mounts the row's element subtree through a nested reconciler.
    """

    _MAX_ROWS = 200

    def create(self, props: Dict[str, Any]) -> Any:
        frame = tk.Frame(_master(), highlightthickness=0, bd=0)
        frame._pn_rows = []
        frame._pn_mounted = False
        self._apply(frame, props)
        return frame

    def update(self, native_view: Any, changed: Dict[str, Any]) -> None:
        was_count = (getattr(native_view, "_pn_props", {}) or {}).get("count")
        self._apply(native_view, changed)
        if "count" in changed and changed.get("count") != was_count:
            native_view._pn_mounted = False
            self._mount_rows(native_view)

    def _apply(self, frame: Any, props: Dict[str, Any]) -> Dict[str, Any]:
        merged = _merge_props(frame, props)
        _apply_common(frame, merged)
        return merged

    def _mount_rows(self, frame: Any) -> None:
        if getattr(frame, "_pn_mounted", False):
            return
        merged = getattr(frame, "_pn_props", {}) or {}
        count = int(merged.get("count", 0) or 0)
        row_height = _finite(merged.get("row_height", 0.0))
        mount_row = merged.get("mount_row")
        frame_w, _frame_h = getattr(frame, "_pn_size", (0.0, 0.0))
        if count <= 0 or row_height <= 0 or not callable(mount_row) or frame_w <= 0:
            return
        for cell in getattr(frame, "_pn_rows", []):
            try:
                cell.destroy()
            except Exception:
                pass
        rows: List[Any] = []
        for index in range(min(count, self._MAX_ROWS)):
            cell = tk.Frame(_master(), highlightthickness=0, bd=0)
            cell._pn_parent = frame
            cell._pn_frame = (0.0, index * row_height, frame_w, row_height)
            _place(cell)
            rows.append(cell)
            try:
                mount_row(index, cell, frame_w, row_height)
            except Exception:
                pass
        frame._pn_rows = rows
        frame._pn_mounted = True

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        native_view._pn_size = (max(0.0, _finite(width)), max(0.0, _finite(height)))
        super().set_frame(native_view, x, y, width, height)
        self._mount_rows(native_view)


# ======================================================================
# Registration
# ======================================================================


def register_handlers(registry: Any) -> None:
    """Register every built-in desktop handler on ``registry``.

    Mirrors ``register_handlers`` in the iOS / Android backends so the
    desktop registry services the same 25 element types.
    """
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
    registry.register("VirtualList", VirtualListHandler())
    registry.register("Picker", PickerHandler())
    registry.register("Checkbox", CheckboxHandler())
    registry.register("SegmentedControl", SegmentedControlHandler())
    registry.register("DatePicker", DatePickerHandler())
