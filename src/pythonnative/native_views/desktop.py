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
colors, fonts) and ignore everything in
[`LAYOUT_STYLE_KEYS`][pythonnative.layout.LAYOUT_STYLE_KEYS].

Event contract
--------------
Handlers never see Python callables. Each view stores its reconciler
tag (``widget._pn_tag``); Tk callbacks forward through
[`dispatch_event`][pythonnative.events.dispatch_event] with that tag,
and the Python-side [`EventRegistry`][pythonnative.events.EventRegistry]
routes to whatever closure the current render registered. Views with a
``gestures`` prop feed Tk pointer events into the shared pure-Python
[`GestureArbiter`][pythonnative.gestures.GestureArbiter].

Placement strategy
------------------
Tkinter fixes a widget's master at construction time, but the
reconciler creates views before parents (``CreateOp`` before
``InsertOp``). To bridge that, every widget is created under a single
shared *stage* frame (see
[`set_root_container`][pythonnative.native_views.desktop.set_root_container])
and positioned with ``place(in_=parent, ...)``. Tk's ``-in`` option
composes coordinates through nested parents, so the engine's
parent-relative frames render correctly without reparenting.
ScrollViews shift their children's placement by the current scroll
offset, which yields real wheel scrolling in the preview.

Scope
-----
This is a **preview** backend, not a production desktop target. It
favors fidelity of layout and behavior over pixel-perfect chrome:
rounded corners, shadows, per-widget opacity, and overflow clipping are
approximated or omitted (Tkinter can't express them cheaply). Native
animation is declined (``start_animation`` returns ``False``), so the
Python ticker drives previews of animations through
``set_animated_property``.

This module imports ``tkinter`` at import time, so it is only imported
when ``PN_PLATFORM=desktop``. Off-device unit tests inject a mock
registry via [`set_registry`][pythonnative.native_views.set_registry]
and never trigger this path.
"""

from __future__ import annotations

import math
import re
import time
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk
from typing import Any, Dict, List, Optional, Tuple

from ..events import dispatch_event, event_names
from ..gestures import make_arbiter
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

    Called by ``pythonnative.preview`` before the first screen is
    mounted. ``container`` must be a Tk widget (a ``Frame`` filling the
    preview window). Also installs the global mouse-wheel binding that
    powers ScrollView scrolling.
    """
    global _ROOT_CONTAINER
    _ROOT_CONTAINER = container
    _install_wheel_bindings(container)


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
# Event dispatch helpers
# ======================================================================


def _fire(widget: Any, name: str, *args: Any) -> None:
    """Dispatch event ``name`` for ``widget`` through the tag registry."""
    tag = getattr(widget, "_pn_tag", None)
    if tag is not None:
        dispatch_event(tag, name, *args)


def _has_event(widget: Any, name: str) -> bool:
    """Whether the element wired a callback named ``name`` this render."""
    merged = getattr(widget, "_pn_props", None) or {}
    return name in event_names(merged)


# ======================================================================
# Placement (ordering-independent, scroll-aware)
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
    and ``insert_child`` records the parent; whichever runs second
    triggers the actual ``place``. Coordinates compose through nested
    ``-in`` parents, so a child's parent-relative frame lands at the
    right absolute spot. A scrollable parent shifts every child by its
    current scroll offset.
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
    sx, sy = getattr(target, "_pn_scroll_offset", (0.0, 0.0)) if parent is not None else (0.0, 0.0)
    try:
        widget.place(in_=target, x=x + tx - sx, y=y + ty - sy, width=max(0.0, w), height=max(0.0, h))
        widget.lift()
    except Exception:
        pass


def _register_child(parent: Any, child: Any, index: int) -> None:
    """Track ``child`` in ``parent``'s ordered child list at ``index``."""
    children: List[Any] = getattr(parent, "_pn_children", None) or []
    if child in children:
        children.remove(child)
    children.insert(min(max(index, 0), len(children)), child)
    parent._pn_children = children


def _unregister_child(parent: Any, child: Any) -> None:
    children: List[Any] = getattr(parent, "_pn_children", None) or []
    try:
        children.remove(child)
    except ValueError:
        pass
    parent._pn_children = children


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
# Gesture wiring (pure-Python arbiter over Tk pointer events)
# ======================================================================


def _wire_gestures(widget: Any, specs: Any) -> None:
    """Feed Tk pointer events on ``widget`` into a `GestureArbiter`.

    The arbiter emits ``(gesture_index, payload)`` pairs which are
    forwarded as ``gesture:<i>`` events for this widget's tag. Long
    presses use Tk's ``after`` timer to poll the arbiter at its next
    deadline.
    """
    if not isinstance(specs, (list, tuple)) or not specs:
        widget._pn_arbiter = None
        return

    def _emit(index: int, payload: Dict[str, Any]) -> None:
        _fire(widget, f"gesture:{index}", payload)

    arbiter = make_arbiter([s for s in specs if isinstance(s, dict)], _emit)
    widget._pn_arbiter = arbiter
    if getattr(widget, "_pn_gestures_bound", False):
        return
    widget._pn_gestures_bound = True

    def _schedule_poll() -> None:
        current = getattr(widget, "_pn_arbiter", None)
        if current is None:
            return
        deadline = current.next_deadline()
        if deadline is None:
            return
        delay_ms = max(1, int((deadline - time.monotonic()) * 1000.0))

        def _poll() -> None:
            live = getattr(widget, "_pn_arbiter", None)
            if live is not None:
                live.poll(time.monotonic())
                _schedule_poll()

        try:
            widget.after(delay_ms, _poll)
        except Exception:
            pass

    def _on_down(event: Any) -> None:
        current = getattr(widget, "_pn_arbiter", None)
        if current is not None:
            current.pointer_down(0, float(event.x), float(event.y), time.monotonic())
            _schedule_poll()

    def _on_move(event: Any) -> None:
        current = getattr(widget, "_pn_arbiter", None)
        if current is not None:
            current.pointer_move(0, float(event.x), float(event.y), time.monotonic())

    def _on_up(event: Any) -> None:
        current = getattr(widget, "_pn_arbiter", None)
        if current is not None:
            current.pointer_up(0, float(event.x), float(event.y), time.monotonic())

    try:
        widget.bind("<ButtonPress-1>", _on_down, add="+")
        widget.bind("<B1-Motion>", _on_move, add="+")
        widget.bind("<ButtonRelease-1>", _on_up, add="+")
    except Exception:
        pass


# ======================================================================
# ScrollView wheel support
# ======================================================================

_WHEEL_BOUND = False


def _install_wheel_bindings(container: Any) -> None:
    """Install the global wheel handler that drives preview scrolling.

    Tk pointer events don't bubble, so a single ``bind_all`` on the
    toplevel hit-tests the widget under the cursor and walks the
    logical ``_pn_parent`` chain to the nearest scrollable ancestor.
    """
    global _WHEEL_BOUND
    if _WHEEL_BOUND:
        return
    try:
        top = container.winfo_toplevel()
    except Exception:
        return

    def _on_wheel(event: Any) -> None:
        delta = getattr(event, "delta", 0)
        if getattr(event, "num", None) == 4:
            delta = 120
        elif getattr(event, "num", None) == 5:
            delta = -120
        if not delta:
            return
        try:
            under = event.widget.winfo_containing(event.x_root, event.y_root)
        except Exception:
            under = None
        node = under
        while node is not None:
            if getattr(node, "_pn_scrollable", False):
                _scroll_by(node, delta)
                return
            node = getattr(node, "_pn_parent", None)

    try:
        top.bind_all("<MouseWheel>", _on_wheel, add="+")
        top.bind_all("<Button-4>", _on_wheel, add="+")
        top.bind_all("<Button-5>", _on_wheel, add="+")
        _WHEEL_BOUND = True
    except Exception:
        pass


def _content_extent(widget: Any) -> Tuple[float, float]:
    """Max (right, bottom) edge over the scroll container's children."""
    max_x = 0.0
    max_y = 0.0
    for child in getattr(widget, "_pn_children", []) or []:
        frame = getattr(child, "_pn_frame", None)
        if frame is None:
            continue
        x, y, w, h = frame
        max_x = max(max_x, x + w)
        max_y = max(max_y, y + h)
    return (max_x, max_y)


def _scroll_to(widget: Any, x: float, y: float, fire_event: bool = True) -> None:
    """Set a scroll container's offset, clamped to its content extent."""
    frame = getattr(widget, "_pn_frame", None)
    vw = frame[2] if frame else 0.0
    vh = frame[3] if frame else 0.0
    content_w, content_h = _content_extent(widget)
    max_x = max(0.0, content_w - vw)
    max_y = max(0.0, content_h - vh)
    new_offset = (min(max(0.0, x), max_x), min(max(0.0, y), max_y))
    if new_offset == getattr(widget, "_pn_scroll_offset", (0.0, 0.0)):
        return
    widget._pn_scroll_offset = new_offset
    for child in getattr(widget, "_pn_children", []) or []:
        _place(child)
    if fire_event:
        _fire(widget, "on_scroll", {"x": new_offset[0], "y": new_offset[1]})


def _scroll_by(widget: Any, wheel_delta: float) -> None:
    sx, sy = getattr(widget, "_pn_scroll_offset", (0.0, 0.0))
    step = -wheel_delta  # natural direction: wheel up scrolls content up
    horizontal = (getattr(widget, "_pn_props", {}) or {}).get("scroll_axis") == "horizontal"
    if horizontal:
        _scroll_to(widget, sx + step, sy)
    else:
        _scroll_to(widget, sx, sy + step)


# ======================================================================
# Base handler
# ======================================================================


class DesktopViewHandler(ViewHandler):
    """Shared create/update/frame/child behavior for Tk handlers.

    Concrete handlers implement
    [`build`][pythonnative.native_views.desktop.DesktopViewHandler.build]
    (construct the widget) and optionally
    [`apply`][pythonnative.native_views.desktop.DesktopViewHandler.apply]
    (apply visual props); creation bookkeeping (tag stamping, prop
    merging, gesture wiring) is inherited.
    """

    def build(self, props: Dict[str, Any]) -> Any:
        """Construct and return the bare Tk widget."""
        return tk.Frame(_master(), highlightthickness=0, bd=0)

    def apply(self, widget: Any, props: Dict[str, Any]) -> None:
        """Apply changed visual props (`_merge_props` has already run)."""
        _apply_common(widget, getattr(widget, "_pn_props", props))

    def create(self, tag: int, props: Dict[str, Any]) -> Any:
        widget = self.build(props)
        widget._pn_tag = tag
        _merge_props(widget, props)
        self.apply(widget, props)
        if "gestures" in props:
            _wire_gestures(widget, props.get("gestures"))
        return widget

    def update(self, native_view: Any, changed_props: Dict[str, Any]) -> None:
        _merge_props(native_view, changed_props)
        self.apply(native_view, changed_props)
        if "gestures" in changed_props:
            _wire_gestures(native_view, changed_props.get("gestures"))

    def insert_child(self, parent: Any, child: Any, index: int) -> None:
        child._pn_parent = parent
        _register_child(parent, child, index)
        _place(child)

    def remove_child(self, parent: Any, child: Any) -> None:
        _unregister_child(parent, child)
        try:
            child.place_forget()
        except Exception:
            pass
        child._pn_parent = None

    def destroy(self, native_view: Any) -> None:
        parent = getattr(native_view, "_pn_parent", None)
        if parent is not None:
            _unregister_child(parent, native_view)
        native_view._pn_arbiter = None
        try:
            native_view.destroy()
        except Exception:
            pass

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        if native_view is None:
            return
        native_view._pn_frame = (_finite(x), _finite(y), max(0.0, _finite(width)), max(0.0, _finite(height)))
        _place(native_view)

    def measure_intrinsic(self, native_view: Any, max_width: float, max_height: float) -> Tuple[float, float]:
        return (0.0, 0.0)

    def set_animated_property(self, native_view: Any, prop_name: str, value: Any) -> None:
        """Apply one frame of a Python-driven animation.

        Translation maps onto placement; background color maps onto
        ``configure``. Opacity, scale, and rotation have no cheap Tk
        analogue and are skipped (a documented preview limitation).
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
# Containers (View / SafeAreaView / KeyboardAvoidingView)
# ======================================================================


class FlexContainerHandler(DesktopViewHandler):
    """A bare positioning surface (``tk.Frame``).

    All flex semantics are computed by the layout engine and applied via
    ``set_frame``; the frame only carries visual chrome (background,
    border).
    """


class SafeAreaViewHandler(FlexContainerHandler):
    """Desktop has no notch/home-indicator insets, so this is a frame."""


class KeyboardAvoidingViewHandler(FlexContainerHandler):
    """No soft keyboard on desktop; behaves as a plain frame."""


# ======================================================================
# ScrollView
# ======================================================================


class ScrollViewHandler(FlexContainerHandler):
    """Preview ScrollView with real wheel scrolling.

    The layout engine lets the content grow past the viewport on the
    scroll axis; this handler offsets its children's placement by the
    current scroll offset (overflow outside the frame is *not* clipped
    — a documented preview limitation of the single-stage design).

    Commands:
        ``scroll_to_offset(x=…, y=…)``: jump to an offset.
        ``scroll_to_end()``: jump to the end of the content.
    """

    def build(self, props: Dict[str, Any]) -> Any:
        frame = tk.Frame(_master(), highlightthickness=0, bd=0)
        frame._pn_scrollable = True
        frame._pn_scroll_offset = (0.0, 0.0)
        return frame

    def command(self, native_view: Any, name: str, args: Dict[str, Any]) -> Any:
        if name == "scroll_to_offset":
            sx, sy = getattr(native_view, "_pn_scroll_offset", (0.0, 0.0))
            _scroll_to(native_view, _finite(args.get("x", sx)), _finite(args.get("y", sy)))
            return True
        if name == "scroll_to_end":
            content_w, content_h = _content_extent(native_view)
            _scroll_to(native_view, content_w, content_h)
            return True
        if name == "get_scroll_offset":
            sx, sy = getattr(native_view, "_pn_scroll_offset", (0.0, 0.0))
            return {"x": sx, "y": sy}
        return None

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        super().set_frame(native_view, x, y, width, height)
        # Keep the offset clamped when the viewport grows.
        sx, sy = getattr(native_view, "_pn_scroll_offset", (0.0, 0.0))
        _scroll_to(native_view, sx, sy, fire_event=False)


# ======================================================================
# Text
# ======================================================================


_ANCHOR_FOR_ALIGN = {"left": "w", "center": "center", "right": "e"}
_JUSTIFY_FOR_ALIGN = {"left": "left", "center": "center", "right": "right"}


class TextHandler(DesktopViewHandler):
    def build(self, props: Dict[str, Any]) -> Any:
        return tk.Label(_master(), highlightthickness=0, bd=0, padx=0, pady=0)

    def apply(self, label: Any, props: Dict[str, Any]) -> None:
        merged = getattr(label, "_pn_props", props)
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
    def build(self, props: Dict[str, Any]) -> Any:
        button = tk.Button(_master(), highlightthickness=0, takefocus=0)
        button.configure(command=lambda: _fire(button, "on_click"))
        return button

    def apply(self, button: Any, props: Dict[str, Any]) -> None:
        merged = getattr(button, "_pn_props", props)
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
    def build(self, props: Dict[str, Any]) -> Any:
        multiline = bool(props.get("multiline"))
        widget: Any
        if multiline:
            widget = tk.Text(_master(), highlightthickness=1, bd=0, wrap="word", height=1)
        else:
            widget = tk.Entry(_master(), highlightthickness=1, bd=0)
        widget._pn_multiline = multiline
        widget._pn_suppress = False
        self._bind(widget)
        return widget

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

    def _bind(self, widget: Any) -> None:
        def _on_key(_event: Any = None) -> None:
            if getattr(widget, "_pn_suppress", False):
                return
            _fire(widget, "on_change", self._current_text(widget))

        def _on_return(_event: Any = None) -> str:
            _fire(widget, "on_submit", self._current_text(widget))
            return "break"

        def _on_focus(_event: Any = None) -> None:
            _fire(widget, "on_focus")

        def _on_blur(_event: Any = None) -> None:
            _fire(widget, "on_blur")

        try:
            widget.bind("<KeyRelease>", _on_key)
            widget.bind("<FocusIn>", _on_focus)
            widget.bind("<FocusOut>", _on_blur)
            if not getattr(widget, "_pn_multiline", False):
                widget.bind("<Return>", _on_return)
        except Exception:
            pass

    def apply(self, widget: Any, props: Dict[str, Any]) -> None:
        merged = getattr(widget, "_pn_props", props)
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

    def command(self, native_view: Any, name: str, args: Dict[str, Any]) -> Any:
        if name == "focus":
            try:
                native_view.focus_set()
            except Exception:
                pass
            return True
        if name == "blur":
            try:
                native_view.winfo_toplevel().focus_set()
            except Exception:
                pass
            return True
        return None

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

    def build(self, props: Dict[str, Any]) -> Any:
        return tk.Label(_master(), highlightthickness=0, bd=0, background="#d1d1d6")

    def apply(self, label: Any, props: Dict[str, Any]) -> None:
        merged = getattr(label, "_pn_props", props)
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
    def build(self, props: Dict[str, Any]) -> Any:
        var = tk.IntVar(master=_master(), value=1 if props.get("value") else 0)
        check = tk.Checkbutton(_master(), variable=var, takefocus=0, highlightthickness=0, text="")
        check._pn_var = var
        check.configure(command=lambda: _fire(check, "on_change", bool(var.get())))
        return check

    def apply(self, check: Any, props: Dict[str, Any]) -> None:
        merged = getattr(check, "_pn_props", props)
        if "value" in props:
            try:
                check._pn_var.set(1 if props.get("value") else 0)
            except Exception:
                pass
        _apply_common(check, merged)

    def measure_intrinsic(self, native_view: Any, max_width: float, max_height: float) -> Tuple[float, float]:
        return (51.0, 31.0)


class CheckboxHandler(DesktopViewHandler):
    def build(self, props: Dict[str, Any]) -> Any:
        var = tk.IntVar(master=_master(), value=1 if props.get("value") else 0)
        check = tk.Checkbutton(_master(), variable=var, takefocus=0, highlightthickness=0, anchor="w")
        check._pn_var = var
        check.configure(command=lambda: _fire(check, "on_change", bool(var.get())))
        return check

    def apply(self, check: Any, props: Dict[str, Any]) -> None:
        merged = getattr(check, "_pn_props", props)
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
    def build(self, props: Dict[str, Any]) -> Any:
        scale = tk.Scale(
            _master(),
            orient="horizontal",
            showvalue=False,
            highlightthickness=0,
            bd=0,
            sliderlength=20,
        )

        def _command(_value: Any) -> None:
            if not getattr(scale, "_pn_suppress", False):
                try:
                    _fire(scale, "on_change", float(scale.get()))
                except Exception:
                    pass

        scale.configure(command=_command)
        return scale

    def apply(self, scale: Any, props: Dict[str, Any]) -> None:
        merged = getattr(scale, "_pn_props", props)
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
    def build(self, props: Dict[str, Any]) -> Any:
        return ttk.Progressbar(_master(), orient="horizontal", maximum=1.0)

    def apply(self, bar: Any, props: Dict[str, Any]) -> None:
        merged = getattr(bar, "_pn_props", props)
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
    def build(self, props: Dict[str, Any]) -> Any:
        return ttk.Progressbar(_master(), orient="horizontal", mode="indeterminate", length=40)

    def apply(self, bar: Any, props: Dict[str, Any]) -> None:
        merged = getattr(bar, "_pn_props", props)
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
    def apply(self, widget: Any, props: Dict[str, Any]) -> None:
        pass


class StatusBarHandler(DesktopViewHandler):
    """Desktop has no system status bar; render an inert zero-size frame."""

    def apply(self, widget: Any, props: Dict[str, Any]) -> None:
        pass


class WebViewHandler(DesktopViewHandler):
    """No embedded browser on desktop; show a labeled placeholder."""

    def build(self, props: Dict[str, Any]) -> Any:
        return tk.Label(
            _master(),
            background="#1c1c1e",
            foreground="#ffffff",
            highlightthickness=0,
            justify="center",
        )

    def apply(self, label: Any, props: Dict[str, Any]) -> None:
        merged = getattr(label, "_pn_props", props)
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
    """A frame that forwards press / long-press / gestures."""

    def build(self, props: Dict[str, Any]) -> Any:
        frame = tk.Frame(_master(), highlightthickness=0, bd=0, cursor="hand2")
        self._bind(frame)
        return frame

    def _bind(self, frame: Any) -> None:
        def _on_release(event: Any = None) -> None:
            fired_long = getattr(frame, "_pn_long_fired", False)
            frame._pn_long_fired = False
            self._cancel_long(frame)
            _fire(frame, "on_press_out")
            if not fired_long:
                _fire(frame, "on_press")

        def _on_press_down(_event: Any = None) -> None:
            frame._pn_long_fired = False
            _fire(frame, "on_press_in")
            if _has_event(frame, "on_long_press"):
                frame._pn_long_after = frame.after(500, _fire_long)

        def _fire_long() -> None:
            frame._pn_long_fired = True
            _fire(frame, "on_long_press")

        def _on_leave(_event: Any = None) -> None:
            self._cancel_long(frame)

        try:
            frame.bind("<ButtonRelease-1>", _on_release, add="+")
            frame.bind("<ButtonPress-1>", _on_press_down, add="+")
            frame.bind("<Leave>", _on_leave, add="+")
        except Exception:
            pass

    @staticmethod
    def _cancel_long(frame: Any) -> None:
        after_id = getattr(frame, "_pn_long_after", None)
        if after_id is not None:
            try:
                frame.after_cancel(after_id)
            except Exception:
                pass
            frame._pn_long_after = None


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

    def build(self, props: Dict[str, Any]) -> Any:
        return tk.Frame(_master(), highlightthickness=0, bd=0, background="#ffffff")

    def apply(self, frame: Any, props: Dict[str, Any]) -> None:
        merged = getattr(frame, "_pn_props", props)
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
        if visible != getattr(frame, "_pn_was_visible", None):
            frame._pn_was_visible = visible
            if visible:
                _fire(frame, "on_show")
            elif getattr(frame, "_pn_was_visible_once", False):
                _fire(frame, "on_dismiss")
            frame._pn_was_visible_once = True

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        # Modal placement is driven by visibility in ``apply``; the
        # engine never frames the placeholder itself.
        return


# ======================================================================
# TabBar
# ======================================================================


class TabBarHandler(DesktopViewHandler):
    """Bottom tab bar — a row of buttons laid out across its width."""

    def build(self, props: Dict[str, Any]) -> Any:
        frame = tk.Frame(_master(), highlightthickness=1, bd=0, background="#f2f2f7")
        try:
            frame.configure(highlightbackground="#c6c6c8", highlightcolor="#c6c6c8")
        except Exception:
            pass
        frame._pn_buttons = []
        return frame

    def apply(self, frame: Any, props: Dict[str, Any]) -> None:
        merged = getattr(frame, "_pn_props", props)
        items: List[Dict[str, Any]] = merged.get("items") or []
        active = merged.get("active_tab")
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
                return lambda: _fire(frame, "on_tab_select", tab_name)

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
    def build(self, props: Dict[str, Any]) -> Any:
        combo = ttk.Combobox(_master(), state="readonly")

        def _on_select(_event: Any = None) -> None:
            items = getattr(combo, "_pn_items", [])
            idx = combo.current()
            if 0 <= idx < len(items):
                _fire(combo, "on_change", items[idx].get("value"))

        try:
            combo.bind("<<ComboboxSelected>>", _on_select)
        except Exception:
            pass
        return combo

    def apply(self, combo: Any, props: Dict[str, Any]) -> None:
        merged = getattr(combo, "_pn_props", props)
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
    def build(self, props: Dict[str, Any]) -> Any:
        frame = tk.Frame(_master(), highlightthickness=0, bd=0)
        frame._pn_buttons = []
        return frame

    def apply(self, frame: Any, props: Dict[str, Any]) -> None:
        merged = getattr(frame, "_pn_props", props)
        segments: List[str] = merged.get("segments") or []
        selected = int(merged.get("selected_index", 0) or 0)
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
                return lambda: _fire(frame, "on_change", index)

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

    def build(self, props: Dict[str, Any]) -> Any:
        entry = tk.Entry(_master(), highlightthickness=1, bd=0)

        def _on_key(_event: Any = None) -> None:
            _fire(entry, "on_change", entry.get())

        try:
            entry.bind("<KeyRelease>", _on_key)
        except Exception:
            pass
        return entry

    def apply(self, entry: Any, props: Dict[str, Any]) -> None:
        merged = getattr(entry, "_pn_props", props)
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
# Registration
# ======================================================================


def register_handlers(registry: Any) -> None:
    """Register every built-in desktop handler on ``registry``.

    Mirrors ``register_handlers`` in the iOS / Android backends so the
    desktop registry services the same element types. Lists
    (``FlatList`` / ``SectionList``) need no handler: they are Python
    components that virtualize on top of ``ScrollView``.
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
    registry.register("Picker", PickerHandler())
    registry.register("Checkbox", CheckboxHandler())
    registry.register("SegmentedControl", SegmentedControlHandler())
    registry.register("DatePicker", DatePickerHandler())
