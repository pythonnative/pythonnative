"""Video playback: a native player view with a typed handle.

Enable it in ``pythonnative.toml``:

```toml
[plugins]
use = ["video"]
```

Example:
    ```python
    import pythonnative as pn
    from pythonnative.video import Video

    @pn.component
    def Player(url: str) -> pn.Node:
        player = pn.use_ref()
        return pn.Column(
            Video(source=url, controls=True, ref=player, style=pn.style(aspect_ratio=16 / 9)),
            pn.Button("Restart", on_press=lambda: player.current.seek(0)),
        )
    ```
"""

from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, Literal, Optional, Union

from ..assets import Asset
from ..element import Element
from ..handles import HANDLE_TYPES, ViewHandle
from ..hooks import Ref
from ..sdk import Props
from ..sdk.plugin import plugin_component
from ..sdk.schema import COMPONENTS, register_schema
from ..style import StyleProp

__all__ = ["ResizeMode", "Video", "VideoHandle", "VideoInfo", "VideoSource"]

ResizeMode = Literal["contain", "cover", "stretch"]
"""How the picture fits its view: letterboxed, cropped to fill, or distorted to fill."""

VideoSource = Union[str, Asset, "os.PathLike[str]"]
"""An ``http(s)`` URL, a file path, a bundled [`Asset`][pythonnative.Asset], or a path under ``app/assets/``."""


@dataclass(frozen=True)
class VideoInfo:
    """What ``on_ready`` reports about a loaded video.

    Attributes:
        duration: Length in seconds, or ``0`` for a live stream.
        width: Picture width in pixels, or ``0`` when there's no video track.
        height: Picture height in pixels, or ``0`` when there's no video track.
    """

    duration: float
    width: float
    height: float


@dataclass(frozen=True)
class _VideoProps(Props):
    source: Optional[str] = None
    poster: Optional[str] = None
    controls: bool = False
    autoplay: bool = False
    loop: bool = False
    muted: bool = False
    volume: float = 1.0
    rate: float = 1.0
    resize_mode: ResizeMode = "contain"
    progress_interval: float = 0.25
    on_ready: Optional[Callable[[VideoInfo], Any]] = None
    on_progress: Optional[Callable[[float, float], Any]] = None
    on_end: Optional[Callable[[], Any]] = None
    on_error: Optional[Callable[[str], Any]] = None
    on_buffering: Optional[Callable[[bool], Any]] = None


_video = plugin_component("Video", _VideoProps, plugin="video", measurement="container")


def _command(*, result: Optional[Dict[str, Any]] = None, **arguments: Dict[str, Any]) -> Dict[str, Any]:
    return {"arguments": arguments, "required": list(arguments), "result": result or {"type": "null"}, "defaults": {}}


register_schema(
    dataclasses.replace(
        COMPONENTS["Video"],
        commands={
            "play": _command(),
            "pause": _command(),
            "seek": _command(seconds={"type": "number"}),
            "position": _command(result={"type": "number"}),
        },
    )
)


class VideoHandle(ViewHandle):
    """The handle a ``ref`` on [`Video`][pythonnative.video.Video] receives."""

    __slots__ = ()

    def play(self) -> None:
        """Start or resume playback. A video that has ended restarts from the beginning."""
        self.command("play")

    def pause(self) -> None:
        """Pause playback."""
        self.command("pause")

    def seek(self, seconds: float) -> None:
        """Jump to ``seconds`` from the start, clamped to the video's length."""
        self.command("seek", seconds=float(seconds))

    async def position(self) -> float:
        """Return the current playback position in seconds."""
        result = await self._ask("position")
        return 0.0 if result is None else float(result)


HANDLE_TYPES["Video"] = VideoHandle


def _uri(source: Optional[VideoSource]) -> Optional[str]:
    if source is None:
        return None
    if isinstance(source, Asset):
        return source.uri
    return os.fspath(source) or None


def Video(
    source: Optional[VideoSource] = None,
    *,
    controls: bool = False,
    autoplay: bool = False,
    loop: bool = False,
    muted: bool = False,
    volume: float = 1.0,
    rate: float = 1.0,
    resize_mode: ResizeMode = "contain",
    poster: Optional[VideoSource] = None,
    progress_interval: float = 0.25,
    on_ready: Optional[Callable[[VideoInfo], Any]] = None,
    on_progress: Optional[Callable[[float, float], Any]] = None,
    on_end: Optional[Callable[[], Any]] = None,
    on_error: Optional[Callable[[str], Any]] = None,
    on_buffering: Optional[Callable[[bool], Any]] = None,
    style: StyleProp = None,
    ref: Optional[Ref] = None,
    key: Optional[str] = None,
) -> Element:
    """Play a local or remote video in a native player view.

    The view has no intrinsic size, so give it one through ``style``: a
    ``width`` and ``height``, or a ``flex``, or an ``aspect_ratio`` inside a
    sized parent. Passing a ``ref`` publishes a
    [`VideoHandle`][pythonnative.video.VideoHandle] on ``ref.current``.

    The player releases its resources when the view unmounts. When the app
    goes to the background, playback pauses and resumes on return; Android
    also frees the decoder until then, since a device has few of them.

    Args:
        source: What to play: an ``http(s)`` URL, a file path, a bundled
            [`Asset`][pythonnative.Asset], or a path under ``app/assets/``.
        controls: Show the platform's playback controls
            (``AVPlayerViewController`` on iOS, ``PlayerView``'s controller
            on Android, the browser's own in the preview).
        autoplay: Start playing as soon as the video is ready.
        loop: Restart at the end. A looping video doesn't fire ``on_end``.
        muted: Silence the audio track without changing ``volume``.
        volume: Audio level from ``0.0`` to ``1.0``.
        rate: Playback speed, where ``1.0`` is normal.
        resize_mode: How the picture fits the view.
        poster: An image shown until playback starts, as a URL, a file path,
            or an asset.
        progress_interval: Seconds between ``on_progress`` calls.
        on_ready: Called with a [`VideoInfo`][pythonnative.video.VideoInfo]
            once the source has loaded and can play.
        on_progress: Called with ``(position, duration)`` in seconds while
            playing, every ``progress_interval``.
        on_end: Called when playback reaches the end.
        on_error: Called with a message when the source can't load or play.
        on_buffering: Called with ``True`` when playback stalls waiting for
            data and ``False`` when it can continue.
        style: Style dict (or list of dicts).
        ref: Optional [`Ref`][pythonnative.Ref] from ``use_ref()``.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"Video"``.

    Raises:
        PluginNotEnabledError: On a device whose build doesn't include
            ``video``.
    """
    element = _video(
        source=_uri(source),
        poster=_uri(poster),
        controls=controls,
        autoplay=autoplay,
        loop=loop,
        muted=muted,
        volume=volume,
        rate=rate,
        resize_mode=resize_mode,
        progress_interval=progress_interval,
        on_ready=on_ready,
        on_progress=on_progress,
        on_end=on_end,
        on_error=on_error,
        on_buffering=on_buffering,
        style=style,
        key=key,
    )
    if ref is None:
        return element
    return Element(element.type, {**element.props, "ref": ref}, list(element.children), key=key)
