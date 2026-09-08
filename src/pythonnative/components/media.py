"""Media factories: ``Image``, ``ImageBackground``, and ``WebView``."""

from typing import Any, Callable, Literal, Optional

from ..element import Element
from ..hooks import Ref
from ..style import AccessibilityState, Color, ScaleType, StyleProp, resolve_style
from ._base import _make_element
from .layout import View


def Image(
    source: str = "",
    *,
    scale_type: Optional[ScaleType] = None,
    tint_color: Optional[Color] = None,
    placeholder_color: Optional[Color] = None,
    on_load: Optional[Callable[[], Any]] = None,
    on_error: Optional[Callable[[str], Any]] = None,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessibility_role: Optional[str] = None,
    accessible: Optional[bool] = None,
    accessibility_state: Optional[AccessibilityState] = None,
    accessibility_live_region: Optional[Literal["none", "polite", "assertive"]] = None,
    test_id: Optional[str] = None,
    ref: Optional[Ref] = None,
    key: Optional[str] = None,
) -> Element:
    """Display an image from a resource path or URL.

    Style properties: ``background_color``, ``border_*``, ``opacity``,
    ``transform``, plus the common layout props.

    Network images (``http://`` / ``https://``) go through the shared
    image pipeline (`pythonnative.images`): downloads happen on a
    background thread, bytes are cached in memory and on disk keyed by
    URL, concurrent requests for the same URL share one download, and
    large bitmaps are downsampled to the view size when decoded.

    Args:
        source: Image resource name or URL.
        scale_type: Fit mode: ``"cover"``, ``"contain"``, ``"stretch"``,
            ``"center"``.
        tint_color: Color overlay applied to template images
            (monochrome icons).
        placeholder_color: Background color shown while a remote image
            is loading (and left in place if it fails).
        on_load: Callback invoked once the image has been decoded and
            displayed.
        on_error: Callback invoked with an error message when a remote
            image fails to download or decode.
        style: Style dict (or list of dicts).
        accessibility_label: Spoken description for screen readers.
        accessibility_role: Override the default ``"image"`` role.
        accessible: Override whether the element is exposed to AT.
        accessibility_state: Current widget state for assistive tech,
            e.g. ``{"disabled": True, "selected": False}``. Recognized
            keys: ``disabled``, ``selected``, ``checked``, ``busy``,
            ``expanded``.
        accessibility_live_region: How AT announces dynamic changes to
            this view: ``"none"``, ``"polite"``, or ``"assertive"``
            (Android only).
        test_id: Stable identifier for UI tests; exposed as
            ``resource-id`` on Android and ``accessibilityIdentifier``
            on iOS.
        ref: Optional [`Ref`][pythonnative.Ref] from ``use_ref()``.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"Image"``.
    """
    return _make_element(
        "Image",
        style=style,
        ref=ref,
        key=key,
        source=source or None,
        scale_type=scale_type,
        tint_color=tint_color,
        placeholder_color=placeholder_color,
        on_load=on_load,
        on_error=on_error,
        accessibility_label=accessibility_label,
        accessibility_role=accessibility_role,
        accessible=accessible,
        accessibility_state=accessibility_state,
        accessibility_live_region=accessibility_live_region,
        test_id=test_id,
        _defaults={"accessibility_role": "image"},
    )


def ImageBackground(
    *children: Element,
    source: str = "",
    scale_type: Optional[ScaleType] = None,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessible: Optional[bool] = None,
    accessibility_state: Optional[AccessibilityState] = None,
    accessibility_live_region: Optional[Literal["none", "polite", "assertive"]] = None,
    test_id: Optional[str] = None,
    key: Optional[str] = None,
) -> Element:
    """Render ``children`` layered on top of a background image.

    Composed entirely from existing primitives: an absolutely-filled
    [`Image`][pythonnative.Image] sits behind a content
    [`View`][pythonnative.View] holding ``children``. The container's
    ``style`` controls sizing/padding; the image stretches to fill it
    via ``position: "absolute"`` and zeroed insets.

    Args:
        *children: Foreground content drawn over the image.
        source: Image resource name or URL.
        scale_type: Background fit mode (``"cover"`` is the most common
            for backgrounds).
        style: Style dict for the container (size, padding, alignment).
        accessibility_label: Spoken description of the background image.
        accessible: Override whether the image is exposed to AT.
        accessibility_state: Current widget state for assistive tech,
            e.g. ``{"disabled": True, "selected": False}``. Recognized
            keys: ``disabled``, ``selected``, ``checked``, ``busy``,
            ``expanded``.
        accessibility_live_region: How AT announces dynamic changes to
            this view: ``"none"``, ``"polite"``, or ``"assertive"``
            (Android only).
        test_id: Stable identifier for UI tests; exposed as
            ``resource-id`` on Android and ``accessibilityIdentifier``
            on iOS.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"View"`` wrapping
        the background image and foreground content.
    """
    fill = {"position": "absolute", "top": 0, "left": 0, "right": 0, "bottom": 0}
    background = Image(
        source,
        scale_type=scale_type or "cover",
        style=fill,
        accessibility_label=accessibility_label,
        accessible=accessible,
        accessibility_state=accessibility_state,
        accessibility_live_region=accessibility_live_region,
        test_id=test_id,
    )
    content = View(*children, style={"flex": 1})
    return View(
        background,
        content,
        style=[{"overflow": "hidden"}, resolve_style(style)],
        key=key,
    )


def WebView(
    *,
    url: str = "",
    html: Optional[str] = None,
    on_load: Optional[Callable[[str], Any]] = None,
    on_message: Optional[Callable[[str], Any]] = None,
    on_navigation_state_change: Optional[Callable[[str], Any]] = None,
    inject_javascript: Optional[str] = None,
    scroll_enabled: bool = True,
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """Embed web content from a URL or an inline HTML string.

    Args:
        url: HTTP(S) URL to load. Ignored when ``html`` is given.
        html: Inline HTML markup to render instead of loading a URL.
        on_load: Callback invoked with the final URL once a page
            finishes loading.
        on_message: Callback invoked with the string payload whenever
            page JavaScript calls
            ``window.pythonnative.postMessage(...)``.
        on_navigation_state_change: Callback invoked with the URL each
            time the top-level document begins navigating.
        inject_javascript: JavaScript evaluated after each page load
            (useful for installing the ``postMessage`` bridge or
            tweaking the DOM).
        scroll_enabled: When ``False``, disables scrolling inside the
            web content.
        style: Style dict (or list of dicts).
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"WebView"``.
    """
    return _make_element(
        "WebView",
        style=style,
        key=key,
        url=url or None,
        html=html,
        on_load=on_load,
        on_message=on_message,
        on_navigation_state_change=on_navigation_state_change,
        inject_javascript=inject_javascript,
        scroll_enabled=False if scroll_enabled is False else None,
    )
