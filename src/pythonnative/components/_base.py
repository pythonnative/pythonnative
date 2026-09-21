"""Shared private helpers behind the built-in element factories.

Every factory in this package routes through :func:`_make_element`, so
style resolution, ``ref`` attachment, ``None``-default dropping, typed
``on_layout`` delivery, and forced overrides live in exactly one place.
The rich-text span flattening used by ``Text`` and the accessibility
prop normalizers shared by every view also live here.
"""

from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from ..element import Element
from ..hooks import Ref
from ..style import AccessibilityAction, AccessibilityValue, StyleProp, resolve_style, validate_style_keys
from .events import LayoutEvent

# ======================================================================
# Typed on_layout delivery
# ======================================================================


class _LayoutCallback:
    """Deliver ``on_layout`` as a [`LayoutEvent`][pythonnative.LayoutEvent].

    The layout pass reports frames as ``{"x", "y", "width", "height"}``
    dicts; this wrapper turns them into the typed record before the
    user's callback runs. A payload that already is a ``LayoutEvent``
    passes through untouched. ``Animated.event`` handlers aren't
    wrapped (the reconciler recognizes them by type to install native
    bindings) and read the same field names either way.
    """

    __slots__ = ("callback",)

    def __init__(self, callback: Callable[[LayoutEvent], Any]) -> None:
        self.callback = callback

    def __call__(self, payload: Any) -> Any:
        if isinstance(payload, Mapping):
            payload = LayoutEvent(
                x=float(payload.get("x", 0.0)),
                y=float(payload.get("y", 0.0)),
                width=float(payload.get("width", 0.0)),
                height=float(payload.get("height", 0.0)),
            )
        return self.callback(payload)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, _LayoutCallback) and other.callback == self.callback

    def __hash__(self) -> int:
        return hash(self.callback)


def _layout_callback(callback: Any) -> Any:
    """Wrap a plain ``on_layout`` callable so it receives a ``LayoutEvent``."""
    if callback is None or isinstance(callback, _LayoutCallback):
        return callback
    from ..animated import AnimatedEvent

    if isinstance(callback, AnimatedEvent):
        return callback
    return _LayoutCallback(callback)


# ======================================================================
# Canonical element builder
# ======================================================================


def _make_element(
    name: str,
    *children: Element,
    style: StyleProp = None,
    ref: Optional[Ref] = None,
    key: Optional[str] = None,
    _defaults: Optional[Dict[str, Any]] = None,
    _forced: Optional[Dict[str, Any]] = None,
    **props: Any,
) -> Element:
    """Build an [`Element`][pythonnative.Element] of type ``name``.

    This is the single helper every built-in factory routes through, so
    the cross-cutting concerns that used to be duplicated per component
    live in one place:

    1. ``style`` is flattened via
       [`resolve_style`][pythonnative.style.resolve_style] (list-of-dicts
       and ``None`` both handled).
    2. ``_defaults`` are filled in for keys not already present (used for
       things like ``View``'s default ``flex_direction: "column"`` that
       a user style may legitimately override).
    3. ``**props`` are merged on top, with ``None`` values *dropped* so
       optional kwargs don't pollute the prop dict. ``on_layout`` is
       wrapped so it receives a [`LayoutEvent`][pythonnative.LayoutEvent].
    4. ``ref`` is attached under the reserved ``"ref"`` key.
    5. ``_forced`` overrides everything (used by ``Column`` / ``Row`` to
       lock their flex direction regardless of user style).

    Args:
        name: Element type name (e.g. ``"Text"``).
        *children: Child elements.
        style: Style dict, list of dicts, or ``None``.
        ref: Optional [`Ref`][pythonnative.Ref] from ``use_ref()``; the
            reconciler publishes a typed handle on ``ref.current``.
        key: Stable identity for keyed reconciliation.
        _defaults: Internal: fill-only-if-missing prop defaults.
        _forced: Internal: prop overrides applied last.
        **props: Per-component props. ``None`` values are dropped.

    Returns:
        A fresh [`Element`][pythonnative.Element].
    """
    from ..sdk.builtins import validate_props

    if props.get("on_layout") is not None:
        props["on_layout"] = _layout_callback(props["on_layout"])
    validate_props(name, props)
    out: Dict[str, Any] = dict(resolve_style(style))
    if out:
        validate_style_keys(out, owner=name)
    if _defaults:
        for k, v in _defaults.items():
            out.setdefault(k, v)
    for k, v in props.items():
        if v is not None:
            out[k] = v
    if ref is not None:
        out["ref"] = ref
    if _forced:
        out.update(_forced)
    return Element(name, out, list(children), key=key)


# ======================================================================
# Accessibility prop normalizers
# ======================================================================


def _accessibility_value(value: Optional[Union[str, AccessibilityValue]]) -> Optional[Union[str, Dict[str, Any]]]:
    """Return the wire form of ``accessibility_value``: a string or a plain dict."""
    if value is None or isinstance(value, str):
        return value
    return dict(value)


def _accessibility_actions(actions: Optional[Sequence[AccessibilityAction]]) -> Optional[List[Dict[str, Any]]]:
    """Return the wire form of ``accessibility_actions``: a list of plain dicts, or ``None`` when empty."""
    if not actions:
        return None
    return [dict(action) for action in actions]


# ======================================================================
# RefreshControl attachment
# ======================================================================

REFRESH_CONTROL_TYPE = "RefreshControl"
"""Element type produced by [`RefreshControl`][pythonnative.RefreshControl]."""


def _refresh_control_props(control: Optional[Element], *, owner: str) -> Optional[Dict[str, Any]]:
    """Turn a ``RefreshControl`` element into the ``refresh_control`` wire prop.

    Scroll containers hold their refresh control as a prop rather than
    a child (the native side attaches a ``UIRefreshControl`` /
    ``SwipeRefreshLayout`` to the scroll view itself), so the element
    is unwrapped here into the flat dict the bridge and the event
    extractor expect. Keeping it an element on the Python side means
    users build it like every other piece of UI and get a clear error
    if they pass the wrong thing.

    Raises:
        TypeError: If ``control`` is not a ``RefreshControl`` element.
    """
    if control is None:
        return None
    if not isinstance(control, Element) or control.type != REFRESH_CONTROL_TYPE:
        raise TypeError(
            f"{owner}(refresh_control=...) expects pn.RefreshControl(...), got {type(control).__name__}: {control!r}"
        )
    return dict(control.props)


# ======================================================================
# Rich text spans
# ======================================================================


# Style keys that can vary per span inside a rich-text run. Layout
# keys are excluded: spans are inline fragments of one paragraph and
# have no boxes of their own.
_SPAN_STYLE_KEYS = (
    "color",
    "background_color",
    "font_size",
    "font_family",
    "font_weight",
    "bold",
    "italic",
    "text_decoration",
    "letter_spacing",
)


class _SpanPressDispatcher:
    """Route the native ``on_span_press(index)`` event to the span's Python callback.

    ``Text`` keeps one callback per flattened span (``None`` for spans
    that aren't pressable) and sends only a ``pressable`` flag on the
    wire. The dispatcher is the element's ``on_span_press`` event
    handler, so the reconciler hoists it into the event registry like
    any other ``on_*`` callable, and nested ``Text`` elements read the
    callbacks back through it when they're flattened into an outer run.
    """

    __slots__ = ("callbacks",)

    def __init__(self, callbacks: List[Optional[Callable[[], Any]]]) -> None:
        self.callbacks = callbacks

    def __call__(self, index: int) -> Any:
        if 0 <= index < len(self.callbacks):
            callback = self.callbacks[index]
            if callback is not None:
                return callback()
        return None


def _flatten_text_spans(
    parts: Tuple[Any, ...],
    inherited: Dict[str, Any],
    on_press: Optional[Callable[[], Any]] = None,
) -> Tuple[List[Dict[str, Any]], List[Optional[Callable[[], Any]]]]:
    """Flatten nested ``Text`` parts into a flat list of styled spans.

    Strings become spans carrying only the inherited style overrides;
    nested ``Text`` elements contribute their own span-style keys
    (merged over what they inherit) and recurse into their parts. A
    span whose nearest enclosing ``Text`` has an ``on_press`` is marked
    ``pressable``; the matching callbacks are returned alongside, one
    entry per span (``None`` when the span isn't pressable).

    Args:
        parts: The positional parts of a ``Text`` call.
        inherited: Span-style keys inherited from the enclosing run.
        on_press: The enclosing ``Text``'s own ``on_press``, inherited
            by every span that doesn't carry a closer one.

    Returns:
        ``(spans, callbacks)`` of equal length.
    """
    spans: List[Dict[str, Any]] = []
    callbacks: List[Optional[Callable[[], Any]]] = []

    def emit(text: str, style: Dict[str, Any], callback: Optional[Callable[[], Any]]) -> None:
        span = {"text": text, **style}
        if callback is not None:
            span["pressable"] = True
        spans.append(span)
        callbacks.append(callback)

    for part in parts:
        if part is None:
            continue
        if isinstance(part, Element):
            props = part.props or {}
            child_style = dict(inherited)
            for k in _SPAN_STYLE_KEYS:
                if props.get(k) is not None:
                    child_style[k] = props[k]
            child_press = props.get("on_press") or on_press
            nested = props.get("spans")
            if nested:
                dispatcher = props.get("on_span_press")
                nested_callbacks = dispatcher.callbacks if isinstance(dispatcher, _SpanPressDispatcher) else []
                for index, span in enumerate(nested):
                    merged = dict(child_style)
                    for k in _SPAN_STYLE_KEYS:
                        if span.get(k) is not None:
                            merged[k] = span[k]
                    span_press = nested_callbacks[index] if index < len(nested_callbacks) else None
                    emit(span.get("text", ""), merged, span_press or child_press)
            else:
                emit(str(props.get("text", "")), child_style, child_press)
        else:
            emit(str(part), inherited, on_press)
    return spans, callbacks
