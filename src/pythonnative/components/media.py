"""Media factories: ``Image``, ``ImageBackground``, and ``WebView``."""

from typing import Any, Callable, Mapping, Optional, Union, Unpack, cast

from ..assets import Asset
from ..element import Element, Node
from ..hooks import Ref
from ..style import (
    Color,
    ScaleType,
    Style,
    StyleProp,
    resolve_style,
)
from ._base import _make_element
from .events import ImageLoadEvent, WebNavigationEvent
from .layout import View
from .props import AccessibilityProps

ImageSource = Union[str, Asset]
"""What ``Image.source`` accepts: a URL, ``data:`` URI, file path, or bundled [`Asset`][pythonnative.Asset]."""


def _source_uri(source: Optional[ImageSource]) -> Optional[str]:
    if source is None:
        return None
    if isinstance(source, Asset):
        return source.uri
    return str(source) or None


def Image(
    source: ImageSource = "",
    *,
    default_source: Optional[ImageSource] = None,
    scale_type: Optional[ScaleType] = None,
    tint_color: Optional[Color] = None,
    placeholder_color: Optional[Color] = None,
    blur_radius: Optional[float] = None,
    on_load_start: Optional[Callable[[], Any]] = None,
    on_load: Optional[Callable[[ImageLoadEvent], Any]] = None,
    on_load_end: Optional[Callable[[], Any]] = None,
    on_error: Optional[Callable[[str], Any]] = None,
    fade_duration: Optional[float] = None,
    headers: Optional[Mapping[str, str]] = None,
    style: StyleProp = None,
    ref: Optional[Ref] = None,
    key: Optional[str] = None,
    **props: Unpack[AccessibilityProps],
) -> Element:
    """Display a bundled, local, or remote image.

    Style properties: ``background_color``, ``border_*``, ``opacity``,
    ``transform``, plus the common layout props.

    Bundled images live under ``app/assets/`` and are referenced with
    [`pn.asset`][pythonnative.asset]; density variants (``logo@2x.png``,
    ``logo@3x.png``) are picked for the device automatically and the
    image measures at its logical (``1x``) size.

    Network images (``http://`` / ``https://``) go through the shared
    native image pipeline: downloads happen on a
    background thread, bytes are cached in memory and on disk keyed by
    URL, concurrent requests for the same URL share one download, and
    large bitmaps are downsampled to the view size when decoded.

    Args:
        source: A bundled [`Asset`][pythonnative.Asset], an ``http(s)``
            URL, a ``data:`` URI, or an absolute file path.
        default_source: A bundled or local image shown until ``source``
            has loaded (and left in place if it fails). Must not be a
            network URL.
        scale_type: Fit mode: ``"cover"``, ``"contain"``, ``"stretch"``,
            ``"center"``.
        tint_color: Color overlay applied to template images
            (monochrome icons).
        placeholder_color: Background color shown while a remote image
            is loading (and left in place if it fails).
        blur_radius: Gaussian blur radius in logical points applied to
            the decoded image.
        on_load_start: Callback invoked when loading begins (a network
            fetch or a decode).
        on_load: Callback invoked once the image has been decoded and
            displayed, with its logical width and height.
        on_load_end: Callback invoked when loading finishes, after
            ``on_load`` or ``on_error``.
        on_error: Callback invoked with an error message when a remote
            image fails to download or decode.
        fade_duration: Milliseconds to cross-fade the image in once it
            has loaded (Android and the browser; iOS shows it at once).
        headers: Extra HTTP headers sent with a network ``source``
            (authorization, cache control).
        style: Style dict (or list of dicts).
        ref: Optional [`Ref`][pythonnative.Ref] from ``use_ref()``.
        key: Stable identity for keyed reconciliation.
        **props: Shared accessibility and test keywords; see
            [`AccessibilityProps`][pythonnative.AccessibilityProps].

    Returns:
        An [`Element`][pythonnative.Element] of type ``"Image"``.
    """
    default_uri = _source_uri(default_source)
    if default_uri is not None and default_uri.startswith(("http://", "https://")):
        raise ValueError("Image(default_source=...) must be a bundled asset or local image, not a URL")
    return _make_element(
        "Image",
        style=style,
        ref=ref,
        key=key,
        source=_source_uri(source),
        default_source=default_uri,
        scale_type=scale_type,
        tint_color=tint_color,
        placeholder_color=placeholder_color,
        blur_radius=blur_radius,
        on_load_start=on_load_start,
        on_load=on_load,
        on_load_end=on_load_end,
        on_error=on_error,
        fade_duration=fade_duration,
        headers=dict(headers) if headers else None,
        _defaults={"accessibility_role": "image"},
        **props,
    )


def ImageBackground(
    *children: Node,
    source: ImageSource = "",
    scale_type: Optional[ScaleType] = None,
    style: StyleProp = None,
    key: Optional[str] = None,
    **props: Unpack[AccessibilityProps],
) -> Element:
    """Render ``children`` layered on top of a background image.

    Composed entirely from existing primitives: an absolutely-filled
    [`Image`][pythonnative.Image] sits behind a content
    [`View`][pythonnative.View] holding ``children``. The container's
    ``style`` controls sizing/padding; the image stretches to fill it
    via ``position: "absolute"`` and zeroed insets.

    Args:
        *children: Foreground content drawn over the image.
        source: A bundled [`Asset`][pythonnative.Asset], URL, ``data:``
            URI, or file path (see [`Image`][pythonnative.Image]).
        scale_type: Background fit mode (``"cover"`` is the most common
            for backgrounds).
        style: Style dict for the container (size, padding, alignment).
        key: Stable identity for keyed reconciliation.
        **props: Shared accessibility and test keywords; see
            [`AccessibilityProps`][pythonnative.AccessibilityProps].

    Returns:
        An [`Element`][pythonnative.Element] of type ``"View"`` wrapping
        the background image and foreground content.
    """
    fill: Style = {"position": "absolute", "top": 0, "left": 0, "right": 0, "bottom": 0}
    background = Image(
        source,
        scale_type=scale_type or "cover",
        style=fill,
    )
    content = View(*children, style={"flex": 1})
    return View(
        background,
        content,
        style=[{"overflow": "hidden"}, cast(Style, resolve_style(style))],
        key=key,
        **props,
    )


def WebView(
    *,
    url: str = "",
    html: Optional[str] = None,
    on_load: Optional[Callable[[str], Any]] = None,
    on_load_start: Optional[Callable[[str], Any]] = None,
    on_error: Optional[Callable[[str], Any]] = None,
    on_message: Optional[Callable[[str], Any]] = None,
    on_navigation_state_change: Optional[Callable[[WebNavigationEvent], Any]] = None,
    inject_javascript: Optional[str] = None,
    scroll_enabled: bool = True,
    style: StyleProp = None,
    ref: Optional[Ref] = None,
    key: Optional[str] = None,
) -> Element:
    """Embed web content from a URL or an inline HTML string.

    Args:
        url: HTTP(S) URL to load. Ignored when ``html`` is given.
        html: Inline HTML markup to render instead of loading a URL.
        on_load: Callback invoked with the final URL once a page
            finishes loading.
        on_load_start: Callback invoked with the URL when loading starts.
        on_error: Callback invoked with a top-level load error message.
        on_message: Callback invoked with the string payload whenever
            page JavaScript calls
            ``window.pythonnative.postMessage(...)``.
        on_navigation_state_change: Callback invoked with a typed navigation
            state when the top-level document starts or finishes loading.
        inject_javascript: JavaScript evaluated after each page load
            (useful for installing the ``postMessage`` bridge or
            tweaking the DOM).
        scroll_enabled: When ``False``, disables scrolling inside the
            web content.
        style: Style dict (or list of dicts).
        ref: Optional [`Ref`][pythonnative.Ref] from ``use_ref()``;
            receives a [`WebViewHandle`][pythonnative.WebViewHandle]
            with ``reload()``, ``go_back()``, ``eval_js()``, and friends.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"WebView"``.
    """
    return _make_element(
        "WebView",
        style=style,
        ref=ref,
        key=key,
        url=url or None,
        html=html,
        on_load=on_load,
        on_load_start=on_load_start,
        on_error=on_error,
        on_message=on_message,
        on_navigation_state_change=on_navigation_state_change,
        inject_javascript=inject_javascript,
        scroll_enabled=False if scroll_enabled is False else None,
    )
