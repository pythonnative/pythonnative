"""Shared private helpers behind the built-in element factories.

Every factory in this package routes through :func:`_make_element`, so
style resolution, ``ref`` attachment, ``None``-default dropping, and
forced overrides live in exactly one place. The rich-text span
flattening used by ``Text`` also lives here so it can be shared.
"""

from typing import Any, Dict, List, Optional, Tuple

from ..element import Element
from ..hooks import Ref
from ..style import StyleProp, resolve_style, validate_style_keys

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
       optional kwargs don't pollute the prop dict.
    4. ``ref`` is attached under the reserved ``"ref"`` key.
    5. ``_forced`` overrides everything (used by ``Column`` / ``Row`` to
       lock their flex direction regardless of user style).

    Args:
        name: Element type name (e.g. ``"Text"``).
        *children: Child elements.
        style: Style dict, list of dicts, or ``None``.
        ref: Optional [`Ref`][pythonnative.Ref] from ``use_ref()``; the
            reconciler populates ``ref.current`` with the underlying
            native view.
        key: Stable identity for keyed reconciliation.
        _defaults: Internal: fill-only-if-missing prop defaults.
        _forced: Internal: prop overrides applied last.
        **props: Per-component props. ``None`` values are dropped.

    Returns:
        A fresh [`Element`][pythonnative.Element].
    """
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


def _flatten_text_spans(
    parts: Tuple[Any, ...],
    inherited: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Flatten nested ``Text`` parts into a flat list of styled spans.

    Strings become spans carrying only the inherited style overrides;
    nested ``Text`` elements contribute their own span-style keys
    (merged over what they inherit) and recurse into their parts.
    """
    spans: List[Dict[str, Any]] = []
    for part in parts:
        if part is None:
            continue
        if isinstance(part, Element):
            props = part.props or {}
            child_style = dict(inherited)
            for k in _SPAN_STYLE_KEYS:
                if props.get(k) is not None:
                    child_style[k] = props[k]
            nested = props.get("spans")
            if nested:
                for span in nested:
                    merged = dict(child_style)
                    for k in _SPAN_STYLE_KEYS:
                        if span.get(k) is not None:
                            merged[k] = span[k]
                    spans.append({"text": span.get("text", ""), **merged})
            else:
                spans.append({"text": str(props.get("text", "")), **child_style})
        else:
            spans.append({"text": str(part), **inherited})
    return spans
