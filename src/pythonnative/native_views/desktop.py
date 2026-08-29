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

Interaction and stacking props
------------------------------
``z_index`` is honored among logical siblings: whenever a sibling set
contains an explicit ``z_index``, the parent's children are re-lifted
in ascending ``z_index`` order (missing values count as 0, ties keep
insertion order), so higher values render above their siblings.
``pointer_events`` is approximated by suspending a widget's Tk binding
tags: ``"none"`` mutes the view and its descendants, ``"box_none"``
mutes only the view itself, and ``"box_only"`` mutes only the
descendants. Suspension is reversible (the original tags are restored
when the prop returns to ``"auto"``), but it is coarser than the real
platforms: all bindings go quiet (keyboard included), and muted
widgets drop events rather than passing them through to whatever sits
underneath. ``hit_slop`` can't grow the initial press target (Tk
hit-tests presses strictly by widget bounds), but it does expand press
*tracking*: once a press starts, Tk's implicit grab keeps streaming
motion and release events to the pressed widget, and ``Pressable``
treats positions within the slop insets of its frame as still inside
when deciding whether a release fires ``on_press`` or a pending long
press survives pointer drift.

Scope
-----
This is a **preview** backend, not a production desktop target. It
favors fidelity of layout and behavior over pixel-perfect chrome:
shadows, per-widget opacity, and overflow clipping are approximated or
omitted (Tkinter can't express them cheaply). Rounded corners
(``border_radius`` plus the per-corner ``border_*_radius`` keys, which
fall back to it) are approximated on Frame-based views by painting the
background and a uniform border onto a covering ``Canvas``; the corner
cutouts are filled with the parent's solid background rather than
being truly transparent, and content leaves (Text, Button, Image)
ignore radius entirely. Native animation is declined
(``start_animation`` returns ``False``), so the Python ticker drives
previews of animations through ``set_animated_property``: translation
maps onto placement, animated ``background_color`` and ``color``
(including interpolated ``"#AARRGGBB"`` strings) map onto ``configure``
(or the rounded-corner canvas when one is active), and rotate, scale,
and opacity frames are silently ignored.

This module imports ``tkinter`` at import time, so it is only imported
when ``PN_PLATFORM=desktop``. Off-device unit tests inject a mock
registry via [`set_registry`][pythonnative.native_views.set_registry]
and never trigger this path.
"""

from __future__ import annotations

import bisect
import math
import re
import time
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk
from typing import Any, Dict, List, Optional, Tuple

from .. import diagnostics
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
# top-level, guaranteed by the single-stage design.

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
    dropped; Tk has no per-color alpha), ``rgb()`` / ``rgba()``
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
        diagnostics.swallowed("desktop._place")
        return
    # The unconditional lift above would put a low ``z_index`` sibling
    # on top, so restack whenever this sibling set uses ``z_index``.
    if parent is not None and getattr(parent, "_pn_has_z", False):
        _restack(parent)
    # Frames are the only reliable resize signal for unmapped widgets,
    # so keep the rounded background in sync here (cheap when the
    # paint signature is unchanged).
    if getattr(widget, "_pn_radius_canvas", None) is not None:
        _redraw_rounded_background(widget)


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


def _z_index(widget: Any) -> float:
    """Return the widget's ``z_index`` (missing or unparseable is 0)."""
    merged = getattr(widget, "_pn_props", None) or {}
    z = merged.get("z_index")
    if z is None:
        return 0.0
    try:
        return float(z)
    except (TypeError, ValueError):
        return 0.0


def _lift_subtree(widget: Any) -> None:
    """Lift ``widget``, then its logical descendants in ``z_index`` order.

    Every desktop widget is a Tk child of the shared stage, so
    stacking is one global order: lifting a container doesn't carry
    its subtree along. Pre-order lifting keeps each subtree above its
    root and applies nested ``z_index`` ordering along the way.
    """
    try:
        widget.lift()
    except Exception:
        diagnostics.swallowed("desktop._lift_subtree")
    for child in sorted(getattr(widget, "_pn_children", None) or [], key=_z_index):
        _lift_subtree(child)


def _restack(parent: Any) -> None:
    """Re-lift ``parent``'s children (and their subtrees) by ``z_index``.

    ``sorted`` is stable, so siblings with equal ``z_index`` keep their
    insertion order. Called whenever a sibling set contains an explicit
    ``z_index`` (see ``_place`` and ``_apply_common``).
    """
    for child in sorted(getattr(parent, "_pn_children", None) or [], key=_z_index):
        _lift_subtree(child)


# ----------------------------------------------------------------------
# ``pointer_events`` (best-effort via Tk binding tags)
# ----------------------------------------------------------------------
#
# A muted widget gets a single dummy binding tag with no bindings, so
# no event scripts (its own, its class's, or the global "all" tag's)
# run while the mode is active; the original tags are saved and
# restored when the prop returns to "auto". This is coarser than the
# real platforms: keyboard bindings go quiet too, and Tk still routes
# the event to the widget under the cursor, so muted widgets drop
# events instead of letting them fall through to lower widgets.

_PE_MUTED_TAG = "pn_pointer_events_off"


def _pointer_mode(widget: Any) -> str:
    """Return the widget's own ``pointer_events`` mode (default ``"auto"``)."""
    merged = getattr(widget, "_pn_props", None) or {}
    mode = merged.get("pointer_events")
    return mode if mode in ("none", "box_none", "box_only") else "auto"


def _pointer_muted(widget: Any) -> bool:
    """Whether the widget should ignore pointer events right now.

    True when its own mode mutes the view (``"none"`` / ``"box_none"``)
    or when any logical ancestor mutes its subtree (``"none"`` /
    ``"box_only"``).
    """
    if _pointer_mode(widget) in ("none", "box_none"):
        return True
    node = getattr(widget, "_pn_parent", None)
    while node is not None:
        if _pointer_mode(node) in ("none", "box_only"):
            return True
        node = getattr(node, "_pn_parent", None)
    return False


def _set_pointer_muted(widget: Any, muted: bool) -> None:
    """Suspend or restore the widget's Tk binding tags (idempotent)."""
    try:
        current = tuple(widget.bindtags())
        if muted:
            if current != (_PE_MUTED_TAG,):
                widget._pn_saved_bindtags = current
                widget.bindtags((_PE_MUTED_TAG,))
        elif current == (_PE_MUTED_TAG,):
            saved = getattr(widget, "_pn_saved_bindtags", None)
            if saved:
                widget.bindtags(saved)
    except Exception:
        diagnostics.swallowed("desktop._set_pointer_muted")


def _refresh_pointer_events(widget: Any) -> None:
    """Recompute pointer muting for ``widget`` and its logical subtree."""
    muted = _pointer_muted(widget)
    _set_pointer_muted(widget, muted)
    canvas = getattr(widget, "_pn_radius_canvas", None)
    if canvas is not None:
        # The rounded-corner canvas covers the widget and forwards
        # events to it (see ``_set_rounded_background``), so it mutes
        # exactly when its host does.
        _set_pointer_muted(canvas, muted)
    for child in getattr(widget, "_pn_children", None) or []:
        _refresh_pointer_events(child)


# ----------------------------------------------------------------------
# ``hit_slop`` (press-tracking expansion)
# ----------------------------------------------------------------------
#
# Tk delivers the initial press only to the widget under the cursor,
# so the slop insets can't grow the press target the way they do on
# device. They do expand the *tracking* rect: Tk's implicit grab keeps
# streaming motion and release events to the pressed widget even past
# its edges, and ``_within_hit_rect`` treats positions within the slop
# insets of the widget's frame as inside.


def _parse_hit_slop(value: Any) -> Tuple[float, float, float, float]:
    """Normalize a ``hit_slop`` prop into ``(top, left, bottom, right)`` insets.

    Accepts a uniform number or a dict with any of ``top`` / ``left``
    / ``bottom`` / ``right``; missing or unparseable entries are 0.
    """
    if isinstance(value, dict):
        return (
            max(0.0, _finite(value.get("top"))),
            max(0.0, _finite(value.get("left"))),
            max(0.0, _finite(value.get("bottom"))),
            max(0.0, _finite(value.get("right"))),
        )
    uniform = max(0.0, _finite(value))
    return (uniform, uniform, uniform, uniform)


def _within_hit_rect(widget: Any, x: float, y: float) -> bool:
    """Whether a widget-relative point is inside the frame plus ``hit_slop``.

    Falls back to the live Tk size when the layout frame isn't known
    yet, and to "inside" when neither is available (never drop a press
    for lack of geometry).
    """
    frame = getattr(widget, "_pn_frame", None)
    if frame is not None:
        w, h = frame[2], frame[3]
    else:
        try:
            w, h = float(widget.winfo_width()), float(widget.winfo_height())
        except Exception:
            return True
    top, left, bottom, right = getattr(widget, "_pn_hit_slop", (0.0, 0.0, 0.0, 0.0))
    return (-left <= x <= w + right) and (-top <= y <= h + bottom)


# ----------------------------------------------------------------------
# Rounded corners (Canvas approximation)
# ----------------------------------------------------------------------
#
# Tk widgets are rectangles and can't be clipped, so Frame-based views
# with a border radius get a full-size Canvas child that paints the
# background (and a uniform border outline) as a rounded polygon. The
# corner cutouts can't be transparent; they're filled with the logical
# parent's background color, which reads correctly whenever the parent
# paints a solid color behind the view. Content leaves (Text, Button,
# Image) skip the approximation entirely: a covering canvas would hide
# what they draw.

_RADIUS_ARC_STEPS = 8

_SIDE_BORDER_WIDTH_KEYS = (
    "border_left_width",
    "border_top_width",
    "border_right_width",
    "border_bottom_width",
)


def _corner_radii(props: Dict[str, Any]) -> Tuple[float, float, float, float]:
    """Resolve ``(top-left, top-right, bottom-right, bottom-left)`` radii.

    Per-corner keys fall back to ``border_radius``; missing values are
    0. Negative or unparseable values clamp to 0.
    """
    base = max(0.0, _finite(props.get("border_radius")))

    def _one(key: str) -> float:
        value = props.get(key)
        if value is None:
            return base
        return max(0.0, _finite(value, base))

    return (
        _one("border_top_left_radius"),
        _one("border_top_right_radius"),
        _one("border_bottom_right_radius"),
        _one("border_bottom_left_radius"),
    )


def _resolve_border(props: Dict[str, Any]) -> Tuple[float, str]:
    """Resolve the uniform ``(width, color)`` border approximation.

    Tk borders are uniform, so per-side borders collapse to the widest
    side's width and the first nonzero side's color.
    """
    width = props.get("border_width")
    color = _tk_color(props.get("border_color")) or "#3c3c43"
    side_widths = [props.get(k) for k in _SIDE_BORDER_WIDTH_KEYS]
    if any(w is not None for w in side_widths):
        width = max(float(w) for w in side_widths if w is not None)
        for side, w in zip(("left", "top", "right", "bottom"), side_widths):
            if w is not None and float(w) > 0:
                side_color = _tk_color(props.get(f"border_{side}_color"))
                if side_color is not None:
                    color = side_color
                break
    return (max(0.0, _finite(width)), color)


def _underlay_color(widget: Any) -> str:
    """Best-effort color of whatever paints behind ``widget``.

    Used to fill the corner cutouts of a rounded view: the logical
    parent's rounded fill when it has one, else its plain Tk
    background. A solid guess is the documented limitation; gradients
    or images behind a rounded view can't be matched.
    """
    parent = getattr(widget, "_pn_parent", None)
    target = parent if parent is not None else get_root_container()
    if target is not None:
        state = getattr(target, "_pn_radius_state", None)
        if state is not None and state.get("fill"):
            return str(state["fill"])
        try:
            return str(target.cget("background"))
        except Exception:
            pass
    return "#ffffff"


def _rounded_rect_points(w: float, h: float, radii: Tuple[float, float, float, float]) -> List[float]:
    """Vertices of a rounded rectangle, corner arcs sampled clockwise.

    Radii are clamped proportionally so adjacent corners never
    overlap. A zero radius degenerates to the plain corner point.
    """
    tl, tr, br, bl = radii
    scale = min(
        1.0,
        w / max(1e-6, tl + tr),
        w / max(1e-6, bl + br),
        h / max(1e-6, tl + bl),
        h / max(1e-6, tr + br),
    )
    tl, tr, br, bl = (r * scale for r in (tl, tr, br, bl))
    points: List[float] = []

    def _arc(cx: float, cy: float, r: float, start_deg: float) -> None:
        if r <= 0:
            points.extend((cx, cy))
            return
        for step in range(_RADIUS_ARC_STEPS + 1):
            a = math.radians(start_deg - 90.0 * step / _RADIUS_ARC_STEPS)
            points.extend((cx + r * math.cos(a), cy - r * math.sin(a)))

    _arc(tl, tl, tl, 180.0)
    _arc(w - tr, tr, tr, 90.0)
    _arc(w - br, h - br, br, 0.0)
    _arc(bl, h - bl, bl, -90.0)
    return points


def _redraw_rounded_background(widget: Any) -> None:
    """Repaint the rounded background canvas if its inputs changed.

    Sizes prefer the layout frame (kept current by ``_place``) over
    ``winfo_*`` so the polygon is right even before Tk maps the
    window. Redraws are skipped when the (size, colors, radii,
    underlay) signature matches the last paint.
    """
    canvas = getattr(widget, "_pn_radius_canvas", None)
    state = getattr(widget, "_pn_radius_state", None)
    if canvas is None or state is None:
        return
    frame = getattr(widget, "_pn_frame", None)
    if frame is not None and frame[2] > 0 and frame[3] > 0:
        w, h = frame[2], frame[3]
    else:
        try:
            w, h = float(canvas.winfo_width()), float(canvas.winfo_height())
        except Exception:
            return
    if w <= 1 or h <= 1:
        return
    under = _underlay_color(widget)
    signature = (w, h, state["radii"], state["fill"], state["outline"], state["outline_width"], under)
    if state.get("drawn") == signature:
        return
    state["drawn"] = signature
    try:
        canvas.configure(background=under)
        canvas.delete("all")
        if state["fill"] or state["outline"]:
            canvas.create_polygon(
                _rounded_rect_points(w, h, state["radii"]),
                fill=state["fill"] or "",
                outline=state["outline"],
                width=max(1.0, state["outline_width"]),
            )
    except Exception:
        diagnostics.swallowed("desktop._redraw_rounded_background")


def _set_rounded_background(widget: Any, radii: Tuple[float, float, float, float], props: Dict[str, Any]) -> None:
    """Install (or refresh) the rounded background canvas on ``widget``."""
    border_width, border_color = _resolve_border(props)
    widget._pn_radius_state = {
        "radii": radii,
        "fill": _tk_color(props.get("background_color")),
        "outline": border_color if border_width else "",
        "outline_width": border_width,
    }
    canvas = getattr(widget, "_pn_radius_canvas", None)
    if canvas is None:
        try:
            canvas = tk.Canvas(widget, highlightthickness=0, bd=0)
            canvas.place(x=0, y=0, relwidth=1.0, relheight=1.0)
            # Below any direct Tk children the handler owns (TabBar /
            # SegmentedControl buttons); PythonNative children live on
            # the stage and are lifted above the whole frame anyway.
            # ``Canvas.lower`` is the canvas-item method, so reach for
            # the widget-stacking ``Misc.lower`` explicitly.
            tk.Misc.lower(canvas)
            # Clicks over the frame now land on the covering canvas,
            # so append the frame's bindtag: its gesture and press
            # bindings keep firing, with matching coordinates (the
            # canvas fills the frame exactly).
            canvas.bindtags(tuple(canvas.bindtags()) + (str(widget),))
            canvas.bind("<Configure>", lambda _e: _redraw_rounded_background(widget), add="+")
        except Exception:
            diagnostics.swallowed("desktop._set_rounded_background")
            return
        canvas._pn_parent = widget  # wheel hit-testing walks through
        widget._pn_radius_canvas = canvas
        _set_pointer_muted(canvas, _pointer_muted(widget))
    _redraw_rounded_background(widget)


def _clear_rounded_background(widget: Any) -> None:
    """Drop the rounded background canvas when radii return to zero."""
    canvas = getattr(widget, "_pn_radius_canvas", None)
    if canvas is None:
        return
    widget._pn_radius_canvas = None
    widget._pn_radius_state = None
    try:
        canvas.destroy()
    except Exception:
        diagnostics.swallowed("desktop._clear_rounded_background")


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
    radii = _corner_radii(props) if isinstance(widget, tk.Frame) else (0.0, 0.0, 0.0, 0.0)
    rounded = any(r > 0 for r in radii)
    if "background_color" in props and not rounded:
        color = _tk_color(props["background_color"])
        if color is not None:
            try:
                widget.configure(background=color)
            except Exception:
                diagnostics.swallowed("desktop._apply_common")
    if rounded:
        # Background and border move onto the rounded canvas; the
        # square highlight border would poke out of the corners.
        try:
            widget.configure(highlightthickness=0)
        except Exception:
            diagnostics.swallowed("desktop._apply_common")
        _set_rounded_background(widget, radii, props)
    else:
        _clear_rounded_background(widget)
        if any(k in props for k in ("border_width", "border_color", *_SIDE_BORDER_WIDTH_KEYS)):
            try:
                width, color = _resolve_border(props)
                if width:
                    widget.configure(
                        highlightthickness=int(round(width)),
                        highlightbackground=color,
                        highlightcolor=color,
                    )
                else:
                    widget.configure(highlightthickness=0)
            except Exception:
                diagnostics.swallowed("desktop._apply_common")
    if "hit_slop" in props:
        widget._pn_hit_slop = _parse_hit_slop(props.get("hit_slop"))
    if "test_id" in props and props["test_id"] is not None:
        # Stamped for introspection so preview-level tooling and tests
        # can locate widgets the same way Maestro does on device.
        widget._pn_test_id = str(props["test_id"])
    if "transform" in props:
        _set_translate_from_transform(widget, props["transform"])
        _place(widget)
    if "z_index" in props:
        parent = getattr(widget, "_pn_parent", None)
        if parent is not None:
            parent._pn_has_z = True
            _restack(parent)
    if "pointer_events" in props:
        _refresh_pointer_events(widget)


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
            diagnostics.swallowed("desktop._wire_gestures._schedule_poll")

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
        diagnostics.swallowed("desktop._wire_gestures")


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
        diagnostics.swallowed("desktop._install_wheel_bindings")


def _content_extent(widget: Any) -> Tuple[float, float]:
    """Max (right, bottom) edge over the scroll container's children.

    Containers that window their children (``VirtualList``) publish
    the full logical extent via ``_pn_content_extent`` so clamping
    covers rows that aren't currently mounted.
    """
    override = getattr(widget, "_pn_content_extent", None)
    if override is not None:
        return override
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
    hook = getattr(widget, "_pn_scroll_hook", None)
    if hook is not None:
        # ``VirtualList`` re-windows its rows and reports the richer
        # native-list scroll payload instead of the default event.
        hook(new_offset, fire_event)
    elif fire_event:
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
        # ``z_index`` applies before insertion (create-time props run
        # first), so stacking and pointer muting settle here, once the
        # parent chain is known.
        merged = getattr(child, "_pn_props", None) or {}
        if merged.get("z_index") is not None:
            parent._pn_has_z = True
        if getattr(parent, "_pn_has_z", False):
            _restack(parent)
        _refresh_pointer_events(child)

    def remove_child(self, parent: Any, child: Any) -> None:
        _unregister_child(parent, child)
        try:
            child.place_forget()
        except Exception:
            diagnostics.swallowed("desktop.DesktopViewHandler.remove_child")
        child._pn_parent = None

    def destroy(self, native_view: Any) -> None:
        parent = getattr(native_view, "_pn_parent", None)
        if parent is not None:
            _unregister_child(parent, native_view)
        native_view._pn_arbiter = None
        try:
            native_view.destroy()
        except Exception:
            diagnostics.swallowed("desktop.DesktopViewHandler.destroy")

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        if native_view is None:
            return
        native_view._pn_frame = (_finite(x), _finite(y), max(0.0, _finite(width)), max(0.0, _finite(height)))
        _place(native_view)

    def measure_intrinsic(self, native_view: Any, max_width: float, max_height: float) -> Tuple[float, float]:
        return (0.0, 0.0)

    def set_animated_property(self, native_view: Any, prop_name: str, value: Any) -> None:
        """Apply one frame of a Python-driven animation.

        Translation maps onto placement; ``background_color`` and
        ``color`` map onto ``configure`` and accept every color form
        ``_tk_color`` understands, including the ``"#AARRGGBB"``
        strings that color interpolations emit (alpha is dropped).
        Opacity, scale, and rotation (numeric degrees) have no cheap
        Tk analogue, and other animated style keys have no desktop
        mapping; those frames are silently skipped (a documented
        preview limitation).
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
                state = getattr(native_view, "_pn_radius_state", None)
                if state is not None:
                    # A rounded view paints its background on the
                    # radius canvas, not the frame itself.
                    state["fill"] = color
                    _redraw_rounded_background(native_view)
                    return
                try:
                    native_view.configure(background=color)
                except Exception:
                    diagnostics.swallowed("desktop.DesktopViewHandler.set_animated_property")
        elif prop_name == "color":
            color = _tk_color(value)
            if color is not None:
                try:
                    native_view.configure(foreground=color)
                except Exception:
                    diagnostics.swallowed("desktop.DesktopViewHandler.set_animated_property")


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
    current scroll offset (overflow outside the frame is *not* clipped,
    a documented preview limitation of the single-stage design).

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
# VirtualList (natively virtualized list preview)
# ======================================================================


class VirtualListHandler(ScrollViewHandler):
    """Preview twin of the native ``VirtualList`` handlers.

    Android backs ``VirtualList`` with a ``RecyclerView`` and iOS with
    a ``UITableView``; the desktop preview reuses the ScrollView
    machinery and does its own row windowing so trees that target the
    native-list contract behave the same way here. Rows within one
    viewport of the scroll window host a live subtree driven by a
    nested reconciler (see ``pythonnative.virtual_rows``); rows that
    leave the window are unmounted.

    Expects props:

    - ``count``: total number of rows.
    - ``row_height``: uniform row extent in points, or
    - ``row_heights``: per-row extents.
    - ``render_row``: ``render_row(index) -> Element`` producing one
      row's subtree. Called lazily as rows enter the window.
    - ``shows_scroll_indicator``: accepted and ignored (the preview
      draws no scroll bar).

    Events (dispatched by tag): ``on_scroll`` with
    ``{"x", "y", "extent", "range"}`` in points, matching the device
    handlers. ``on_row_press`` is not synthesized: preview rows are
    live widgets, so presses land on the row's own Pressable / Button
    children.

    Commands: ``scroll_to_offset`` / ``scroll_to_index`` /
    ``scroll_to_end`` / ``get_scroll_offset``. The ``animated`` flag
    is accepted and ignored (the preview jumps, like ScrollView).
    """

    def build(self, props: Dict[str, Any]) -> Any:
        from ..virtual_rows import RowHostPool

        frame = super().build(props)
        frame._pn_vl = {
            "count": 0,
            "row_height": 44.0,
            "row_heights": None,
            "render_row": None,
            "starts": [0.0],
            "pool": RowHostPool(),
            "cells": {},
            "cell_width": 0.0,
        }
        frame._pn_content_extent = (0.0, 0.0)

        def _hook(offset: Tuple[float, float], fire_event: bool) -> None:
            self._rewindow(frame)
            if fire_event:
                viewport = getattr(frame, "_pn_frame", None)
                _fire(
                    frame,
                    "on_scroll",
                    {
                        "x": 0.0,
                        "y": offset[1],
                        "extent": viewport[3] if viewport else 0.0,
                        "range": frame._pn_vl["starts"][-1],
                    },
                )

        frame._pn_scroll_hook = _hook
        return frame

    def apply(self, frame: Any, props: Dict[str, Any]) -> None:
        super().apply(frame, props)
        layout_changed, content_changed = self._read_data_props(frame, props)
        if layout_changed:
            # Geometry changed under the mounted window; rebuild it.
            self._release_rows(frame)
            self._rewindow(frame)
        elif content_changed:
            # Only ``render_row`` changed (a fresh closure every
            # render); reconcile the live rows in place, mirroring
            # the device handlers' reload-on-render behavior.
            self._rebind_rows(frame)

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        super().set_frame(native_view, x, y, width, height)
        self._rewindow(native_view)

    def measure_intrinsic(self, native_view: Any, max_width: float, max_height: float) -> Tuple[float, float]:
        # Fill the available space, like a ScrollView clamped to its
        # parent; collapse to 0 on unbounded axes (nested lists don't
        # scroll, matching the device handlers).
        w = max_width if math.isfinite(max_width) else 0.0
        h = max_height if math.isfinite(max_height) else 0.0
        return (max(0.0, w), max(0.0, h))

    def command(self, native_view: Any, name: str, args: Dict[str, Any]) -> Any:
        info = getattr(native_view, "_pn_vl", None)
        if info is None:
            return None
        if name == "scroll_to_offset":
            _scroll_to(native_view, 0.0, _finite(args.get("y", 0.0)))
            return True
        if name == "scroll_to_index":
            count = info["count"]
            index = max(0, min(int(_finite(args.get("index", 0))), max(0, count - 1)))
            _scroll_to(native_view, 0.0, info["starts"][index] if count else 0.0)
            return True
        if name == "scroll_to_end":
            _scroll_to(native_view, 0.0, info["starts"][-1])
            return True
        if name == "get_scroll_offset":
            sx, sy = getattr(native_view, "_pn_scroll_offset", (0.0, 0.0))
            return {"x": sx, "y": sy}
        return None

    def destroy(self, native_view: Any) -> None:
        info = getattr(native_view, "_pn_vl", None)
        if info is not None:
            self._release_rows(native_view)
            try:
                info["pool"].release_all()
            except Exception:
                diagnostics.swallowed("desktop.VirtualListHandler.destroy")
        super().destroy(native_view)

    # -- data + windowing ----------------------------------------------

    def _read_data_props(self, frame: Any, props: Dict[str, Any]) -> Tuple[bool, bool]:
        """Fold changed data props into ``_pn_vl``.

        Returns ``(layout_changed, content_changed)``: the first is
        true when row geometry changed (count or extents) and the
        window must be rebuilt; the second when ``render_row`` changed
        and live rows only need a rebind.
        """
        info = frame._pn_vl
        layout_changed = False
        if "count" in props:
            info["count"] = int(props.get("count") or 0)
            layout_changed = True
        if "row_height" in props and props.get("row_height") is not None:
            info["row_height"] = max(0.0, _finite(props["row_height"], 44.0))
            layout_changed = True
        if "row_heights" in props:
            heights = props.get("row_heights")
            info["row_heights"] = [max(0.0, _finite(h)) for h in heights] if heights else None
            layout_changed = True
        content_changed = False
        if "render_row" in props:
            info["render_row"] = props.get("render_row")
            content_changed = True
        if layout_changed:
            n = info["count"]
            heights = info["row_heights"]
            starts = [0.0] * (n + 1)
            acc = 0.0
            for i in range(n):
                starts[i] = acc
                extent = heights[i] if heights is not None and i < len(heights) else info["row_height"]
                acc += max(0.0, extent)
            starts[n] = acc
            info["starts"] = starts
            # Publish the full content extent so ``_scroll_to`` clamps
            # against every row, not just the mounted window.
            frame._pn_content_extent = (0.0, acc)
        return (layout_changed, content_changed)

    def _rewindow(self, frame: Any) -> None:
        """Mount rows within one viewport of the window, unmount the rest."""
        info = getattr(frame, "_pn_vl", None)
        if info is None or info["render_row"] is None:
            return
        viewport = getattr(frame, "_pn_frame", None)
        if viewport is None:
            return
        n = info["count"]
        width = max(0.0, viewport[2])
        height = max(0.0, viewport[3])
        if n <= 0 or width <= 0 or height <= 0:
            self._release_rows(frame)
            return
        if width != info["cell_width"]:
            # Mounted rows were laid out against a different width.
            self._release_rows(frame)
            info["cell_width"] = width
        starts = info["starts"]
        offset = getattr(frame, "_pn_scroll_offset", (0.0, 0.0))[1]
        lo = max(0.0, offset - height)
        hi = offset + 2.0 * height
        first = max(0, bisect.bisect_right(starts, lo, 0, n) - 1)
        last = min(n - 1, bisect.bisect_left(starts, hi, 0, n))
        cells: Dict[int, Any] = info["cells"]
        for index in [i for i in cells if i < first or i > last]:
            self._release_row(frame, index)
        for index in range(first, last + 1):
            if index in cells:
                continue
            cell = tk.Frame(_master(), highlightthickness=0, bd=0)
            cell._pn_parent = frame
            cells[index] = cell
            _register_child(frame, cell, len(getattr(frame, "_pn_children", None) or []))
            cell._pn_frame = (0.0, starts[index], width, starts[index + 1] - starts[index])
            _place(cell)
            self._attach_row(frame, cell, index)

    def _attach_row(self, frame: Any, cell: Any, index: int) -> None:
        """Mount (or rebind) row ``index`` into ``cell`` and place its root."""
        info = frame._pn_vl
        render_row = info["render_row"]
        cell_frame = getattr(cell, "_pn_frame", (0.0, 0.0, 0.0, 0.0))
        try:
            root = info["pool"].bind(index, lambda: render_row(index), cell_frame[2], cell_frame[3])
        except Exception:
            diagnostics.swallowed("desktop.VirtualListHandler._attach_row")
            return
        if root is None:
            return
        # A rebind can replace the subtree's root, so reset the cell's
        # child list instead of accumulating stale widgets.
        root._pn_parent = cell
        cell._pn_children = [root]
        _place(root)

    def _rebind_rows(self, frame: Any) -> None:
        info = frame._pn_vl
        for index, cell in list(info["cells"].items()):
            self._attach_row(frame, cell, index)

    def _release_row(self, frame: Any, index: int) -> None:
        info = frame._pn_vl
        cell = info["cells"].pop(index, None)
        try:
            info["pool"].release(index)
        except Exception:
            diagnostics.swallowed("desktop.VirtualListHandler._release_row")
        if cell is not None:
            _unregister_child(frame, cell)
            try:
                cell.destroy()
            except Exception:
                diagnostics.swallowed("desktop.VirtualListHandler._release_row")

    def _release_rows(self, frame: Any) -> None:
        info = getattr(frame, "_pn_vl", None)
        if info is None:
            return
        for index in list(info["cells"]):
            self._release_row(frame, index)


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
            diagnostics.swallowed("desktop.TextHandler.apply")
        _apply_common(label, merged)

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        # Wrap to the laid-out width so multi-line text flows the way the
        # engine measured it.
        try:
            native_view.configure(wraplength=max(1, int(_finite(width))))
        except Exception:
            diagnostics.swallowed("desktop.TextHandler.set_frame")
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
        button.configure(command=lambda: _fire(button, "on_press"))
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
            diagnostics.swallowed("desktop.ButtonHandler.apply")
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
            diagnostics.swallowed("desktop.TextInputHandler._set_text")
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
            diagnostics.swallowed("desktop.TextInputHandler._bind")

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
            diagnostics.swallowed("desktop.TextInputHandler.apply")
        if "value" in props:
            incoming = "" if props["value"] is None else str(props["value"])
            if self._current_text(widget) != incoming:
                self._set_text(widget, incoming)
        _apply_common(widget, merged)
        try:
            widget.configure(highlightbackground="#c7c7cc", highlightcolor="#007aff")
        except Exception:
            diagnostics.swallowed("desktop.TextInputHandler.apply")

    def command(self, native_view: Any, name: str, args: Dict[str, Any]) -> Any:
        if name == "focus":
            try:
                native_view.focus_set()
            except Exception:
                diagnostics.swallowed("desktop.TextInputHandler.command")
            return True
        if name == "blur":
            try:
                native_view.winfo_toplevel().focus_set()
            except Exception:
                diagnostics.swallowed("desktop.TextInputHandler.command")
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

    Tk's ``PhotoImage`` loads PNG/GIF/PPM from local paths; JPEG isn't
    supported without Pillow, so undecodable formats fall back to a
    labeled placeholder. Network URLs are fetched through the shared
    image pipeline (`pythonnative.images`), so caching and ``on_load``
    / ``on_error`` behave like the mobile backends. The handler keeps
    a reference to the ``PhotoImage`` (Tk garbage-collects images that
    aren't referenced).
    """

    def build(self, props: Dict[str, Any]) -> Any:
        return tk.Label(_master(), highlightthickness=0, bd=0, background="#d1d1d6")

    def apply(self, label: Any, props: Dict[str, Any]) -> None:
        merged = getattr(label, "_pn_props", props)
        if "placeholder_color" in props:
            color = _tk_color(props.get("placeholder_color"))
            if color is not None:
                try:
                    label.configure(background=color)
                except Exception:
                    diagnostics.swallowed("desktop.ImageHandler.apply")
        if "source" in props:
            source = props.get("source")
            label._pn_pending_source = source
            if source and "://" in str(source):
                from ..images import fetch

                def _on_ready(path: str, src: Any = source) -> None:
                    if getattr(label, "_pn_pending_source", None) == src:
                        self._show_file(label, path, src)

                def _on_error(message: str, src: Any = source) -> None:
                    if getattr(label, "_pn_pending_source", None) == src:
                        self._show_fallback(label, src)
                        _fire(label, "on_error", message)

                self._show_fallback(label, source)
                fetch(str(source), _on_ready, _on_error)
            else:
                self._show_file(label, str(source) if source else None, source)
        _apply_common(label, merged)

    def _show_file(self, label: Any, path: Optional[str], source: Any) -> None:
        photo = None
        if path:
            try:
                photo = tk.PhotoImage(file=path)
            except Exception:
                photo = None
        label._pn_photo = photo  # keep a reference alive
        try:
            if photo is not None:
                label.configure(image=photo, text="")
                _fire(label, "on_load")
            else:
                self._show_fallback(label, source)
                if path:
                    _fire(label, "on_error", "decode failed")
        except Exception:
            diagnostics.swallowed("desktop.ImageHandler._show_file")

    def _show_fallback(self, label: Any, source: Any) -> None:
        name = str(source).rsplit("/", 1)[-1] if source else "image"
        try:
            label.configure(image="", text=f"\U0001f5bc\n{name}", compound="center")
        except Exception:
            diagnostics.swallowed("desktop.ImageHandler._show_fallback")

    def measure_intrinsic(self, native_view: Any, max_width: float, max_height: float) -> Tuple[float, float]:
        photo = getattr(native_view, "_pn_photo", None)
        if photo is not None:
            try:
                return (float(photo.width()), float(photo.height()))
            except Exception:
                diagnostics.swallowed("desktop.ImageHandler.measure_intrinsic")
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
                diagnostics.swallowed("desktop.SwitchHandler.apply")
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
                diagnostics.swallowed("desktop.CheckboxHandler.apply")
        if "value" in props:
            try:
                check._pn_var.set(1 if props.get("value") else 0)
            except Exception:
                diagnostics.swallowed("desktop.CheckboxHandler.apply")
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
                    diagnostics.swallowed("desktop.SliderHandler.build._command")

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
            diagnostics.swallowed("desktop.SliderHandler.apply")
        if "value" in merged:
            scale._pn_suppress = True
            try:
                scale.set(_finite(merged.get("value")))
            except Exception:
                diagnostics.swallowed("desktop.SliderHandler.apply")
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
                diagnostics.swallowed("desktop.ProgressBarHandler.apply")
        else:
            try:
                bar.configure(mode="determinate", value=max(0.0, min(1.0, _finite(merged.get("value", 0.0)))))
            except Exception:
                diagnostics.swallowed("desktop.ProgressBarHandler.apply")

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
            diagnostics.swallowed("desktop.ActivityIndicatorHandler.apply")

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
            diagnostics.swallowed("desktop.WebViewHandler.apply")
        _apply_common(label, merged)


# ======================================================================
# Pressable
# ======================================================================


class PressableHandler(DesktopViewHandler):
    """A frame that forwards press / long-press / gestures.

    ``hit_slop`` support is partial (see ``_within_hit_rect``): the
    slop insets can't grow the initial press target, but they expand
    the tracking rect, so a release (or pointer drift during a pending
    long press) within the slop of the frame's edges still counts as
    inside. A release outside the expanded rect fires ``on_press_out``
    without ``on_press``, matching the device backends' cancel-on-exit
    behavior.
    """

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
            inside = event is None or _within_hit_rect(frame, float(event.x), float(event.y))
            if not fired_long and inside:
                _fire(frame, "on_press")

        def _on_press_down(_event: Any = None) -> None:
            frame._pn_long_fired = False
            _fire(frame, "on_press_in")
            if _has_event(frame, "on_long_press"):
                frame._pn_long_after = frame.after(500, _fire_long)

        def _fire_long() -> None:
            frame._pn_long_fired = True
            _fire(frame, "on_long_press")

        def _on_drift(event: Any = None) -> None:
            # A pending long press survives pointer drift inside the
            # hit rect (frame plus hit_slop). <Leave> fires once at
            # the edge crossing, so <B1-Motion> covers travel beyond
            # it; Tk's implicit grab keeps reporting positions.
            if event is None or not _within_hit_rect(frame, float(event.x), float(event.y)):
                self._cancel_long(frame)

        try:
            frame.bind("<ButtonRelease-1>", _on_release, add="+")
            frame.bind("<ButtonPress-1>", _on_press_down, add="+")
            frame.bind("<B1-Motion>", _on_drift, add="+")
            frame.bind("<Leave>", _on_drift, add="+")
        except Exception:
            diagnostics.swallowed("desktop.PressableHandler._bind")

    @staticmethod
    def _cancel_long(frame: Any) -> None:
        after_id = getattr(frame, "_pn_long_after", None)
        if after_id is not None:
            try:
                frame.after_cancel(after_id)
            except Exception:
                diagnostics.swallowed("desktop.PressableHandler._cancel_long")
            frame._pn_long_after = None


# ======================================================================
# Modal
# ======================================================================


class ModalHandler(DesktopViewHandler):
    """Overlay modal, a frame that fills the stage when ``visible``.

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
            diagnostics.swallowed("desktop.ModalHandler.apply")
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
# Portal
# ======================================================================


class PortalHandler(DesktopViewHandler):
    """Portal host that floats children over the whole stage.

    Tkinter has no view that can cover the stage without also
    swallowing clicks, so the portal keeps its own frame unmapped and
    instead places each child directly against the stage (``_place``
    with no logical parent targets the root container). The detached
    layout pass produces viewport coordinates, which is exactly the
    stage coordinate space, and ``_place`` lifts children above the
    main content. Empty portal area has no widget at all, so clicks
    there reach whatever sits underneath.
    """

    def insert_child(self, parent: Any, child: Any, index: int) -> None:
        # No ``_pn_parent``: placement composes against the stage.
        child._pn_parent = None
        _register_child(parent, child, index)
        _place(child)

    def remove_child(self, parent: Any, child: Any) -> None:
        _unregister_child(parent, child)
        try:
            child.place_forget()
        except Exception:
            diagnostics.swallowed("desktop.PortalHandler.remove_child")

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        # The portal frame itself stays unmapped; only children render.
        return


# ======================================================================
# TabBar
# ======================================================================


class TabBarHandler(DesktopViewHandler):
    """Bottom tab bar, a row of buttons laid out across its width."""

    def build(self, props: Dict[str, Any]) -> Any:
        frame = tk.Frame(_master(), highlightthickness=1, bd=0, background="#f2f2f7")
        try:
            frame.configure(highlightbackground="#c6c6c8", highlightcolor="#c6c6c8")
        except Exception:
            diagnostics.swallowed("desktop.TabBarHandler.build")
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
                diagnostics.swallowed("desktop.TabBarHandler.apply")
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
                diagnostics.swallowed("desktop.TabBarHandler._layout_buttons")

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
            diagnostics.swallowed("desktop.PickerHandler.build")
        return combo

    def apply(self, combo: Any, props: Dict[str, Any]) -> None:
        merged = getattr(combo, "_pn_props", props)
        items: List[Dict[str, Any]] = merged.get("items") or []
        combo._pn_items = items
        labels = [str(item.get("label", item.get("value", ""))) for item in items]
        try:
            combo.configure(values=labels)
        except Exception:
            diagnostics.swallowed("desktop.PickerHandler.apply")
        if "value" in merged:
            target = merged.get("value")
            for i, item in enumerate(items):
                if item.get("value") == target:
                    try:
                        combo.current(i)
                    except Exception:
                        diagnostics.swallowed("desktop.PickerHandler.apply")
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
                diagnostics.swallowed("desktop.SegmentedControlHandler.apply")
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
                diagnostics.swallowed("desktop.SegmentedControlHandler.apply")
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
                diagnostics.swallowed("desktop.SegmentedControlHandler._layout_buttons")

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        native_view._pn_size = (max(0.0, _finite(width)), max(0.0, _finite(height)))
        super().set_frame(native_view, x, y, width, height)
        self._layout_buttons(native_view)


class DatePickerHandler(DesktopViewHandler):
    """Preview DatePicker, a text entry for the ISO date/time string."""

    def build(self, props: Dict[str, Any]) -> Any:
        entry = tk.Entry(_master(), highlightthickness=1, bd=0)

        def _on_key(_event: Any = None) -> None:
            _fire(entry, "on_change", entry.get())

        try:
            entry.bind("<KeyRelease>", _on_key)
        except Exception:
            diagnostics.swallowed("desktop.DatePickerHandler.build")
        return entry

    def apply(self, entry: Any, props: Dict[str, Any]) -> None:
        merged = getattr(entry, "_pn_props", props)
        if "enabled" in merged:
            try:
                entry.configure(state="normal" if merged.get("enabled", True) else "disabled")
            except Exception:
                diagnostics.swallowed("desktop.DatePickerHandler.apply")
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
                diagnostics.swallowed("desktop.DatePickerHandler.apply")
        try:
            entry.configure(highlightbackground="#c7c7cc", highlightcolor="#007aff")
        except Exception:
            diagnostics.swallowed("desktop.DatePickerHandler.apply")


# ======================================================================
# Registration
# ======================================================================


def register_handlers(registry: Any) -> None:
    """Register every built-in desktop handler on ``registry``.

    Mirrors ``register_handlers`` in the iOS / Android backends so the
    desktop registry services the same element types, including
    ``VirtualList``. ``FlatList`` and ``SectionList`` still pick the
    Python-windowed engine on desktop (``_native_lists_supported`` is
    false here), but trees that emit ``VirtualList`` directly, and
    tests that exercise the native-list routing, get the same command
    and prop contract in the preview.
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
