"""Typed media events shared by Python, iOS, Android, and preview."""

from dataclasses import dataclass


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
