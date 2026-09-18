"""Typed event payloads delivered by the built-in components.

Every record here is a frozen, slotted dataclass, so callbacks read
``event.y`` instead of ``payload["y"]`` and a misspelled field is an
``AttributeError`` rather than a silent ``None``. The wire payload for
each event is a JSON object whose keys match the field names, which is
what lets ``Animated.event(on_scroll, y=scroll_y)`` keep binding by
name: the contract generator derives the native record from these
classes and the bridge reconstructs them before the callback runs.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LayoutEvent:
    """A view's committed frame, in the parent's coordinate space and logical units.

    Delivered to ``on_layout`` after the first layout and again whenever
    the frame changes.
    """

    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True, slots=True)
class ScrollEvent:
    """A scroll container's offset and geometry at the moment of the event.

    Delivered to ``on_scroll`` and the drag and momentum callbacks of
    [`ScrollView`][pythonnative.ScrollView], and to ``on_scroll`` on
    [`FlatList`][pythonnative.FlatList] and
    [`SectionList`][pythonnative.SectionList]. Geometry fields default
    to ``0.0`` when a renderer reports only the offset.
    """

    x: float
    y: float
    content_width: float = 0.0
    content_height: float = 0.0
    viewport_width: float = 0.0
    viewport_height: float = 0.0


@dataclass(frozen=True, slots=True)
class SelectionEvent:
    """A text field's selection as UTF-16 offsets (``start == end`` is a caret)."""

    start: int
    end: int


@dataclass(frozen=True, slots=True)
class KeyPressEvent:
    """One key press inside a text field.

    ``key`` is the typed character, or ``"Backspace"`` / ``"Enter"`` for
    those keys. Native platforms report only what their input pipeline
    exposes: iOS and Android see characters, backspace, and the return
    key; the browser reports every key.
    """

    key: str


@dataclass(frozen=True, slots=True)
class ContentSizeEvent:
    """The measured size of a text field's content, in logical units."""

    width: float
    height: float


@dataclass(frozen=True, slots=True)
class ImageLoadEvent:
    """Decoded image dimensions in the platform's logical display units."""

    width: float
    height: float


@dataclass(frozen=True, slots=True)
class WebNavigationEvent:
    """The top-level document's navigation state at a load transition."""

    url: str
    loading: bool
    can_go_back: bool
    can_go_forward: bool
    title: str = ""


__all__ = [
    "ContentSizeEvent",
    "ImageLoadEvent",
    "KeyPressEvent",
    "LayoutEvent",
    "ScrollEvent",
    "SelectionEvent",
    "WebNavigationEvent",
]
