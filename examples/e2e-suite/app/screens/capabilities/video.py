"""Demo screen for [`pythonnative.video`][pythonnative.video].

A two-second clip, embedded here so the simulator needs no network, plays through
the ``Video`` view. The readouts mirror every event, and the buttons drive the
typed handle published on the ``ref``.
"""

from __future__ import annotations

import asyncio
import base64
import os
import tempfile
from typing import Optional

from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText

import pythonnative as pn
from pythonnative.video import Video, VideoHandle, VideoInfo

# 96x54, 5 frames per second, generated with ffmpeg's testsrc.
_CLIP = base64.b64decode(
    "AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAANMbW9vdgAAAGxtdmhkAAAAAAAAAAAAAAAAAAAD6AAAB9AAAQAAAQAA"
    "AAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAA"
    "And0cmFrAAAAXHRraGQAAAADAAAAAAAAAAAAAAABAAAAAAAAB9AAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAA"
    "AAAAAAAAAAAAAABAAAAAAGAAAAA2AAAAAAAkZWR0cwAAABxlbHN0AAAAAAAAAAEAAAfQAAAAAAABAAAAAAHvbWRpYQAAACBtZGhk"
    "AAAAAAAAAAAAAAAAAAAoAAAAUABVxAAAAAAALWhkbHIAAAAAAAAAAHZpZGUAAAAAAAAAAAAAAABWaWRlb0hhbmRsZXIAAAABmm1p"
    "bmYAAAAUdm1oZAAAAAEAAAAAAAAAAAAAACRkaW5mAAAAHGRyZWYAAAAAAAAAAQAAAAx1cmwgAAAAAQAAAVpzdGJsAAAAunN0c2QA"
    "AAAAAAAAAQAAAKphdmMxAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAGAANgBIAAAASAAAAAAAAAABFExhdmM2My4xLjEwMiBsaWJ4"
    "MjY0AAAAAAAAAAAAAAAAGP//AAAAMGF2Y0MBQsAK/+EAGGdCwArZBifmwEQAAAMABAAAAwAoPEiZIAEABWjLgOSyAAAAEHBhc3AA"
    "AAABAAAAAQAAABRidHJ0AAAAAAAAGoAAAAAAAAAAGHN0dHMAAAAAAAAAAQAAAAoAAAgAAAAAFHN0c3MAAAAAAAAAAQAAAAEAAAAc"
    "c3RzYwAAAAAAAAABAAAAAQAAAAoAAAABAAAAPHN0c3oAAAAAAAAAAAAAAAoAAAS9AAAAJgAAADMAAAA2AAAAPwAAAFsAAAA2AAAA"
    "LgAAAC4AAAAoAAAAFHN0Y28AAAAAAAAAAQAAA3wAAABhdWR0YQAAAFltZXRhAAAAAAAAACFoZGxyAAAAAAAAAABtZGlyYXBwbAAA"
    "AAAAAAAAAAAAACxpbHN0AAAAJKl0b28AAAAcZGF0YQAAAAEAAAAATGF2ZjYzLjEuMTAyAAAACGZyZWUAAAaobWRhdAAAAm8GBf//"
    "a9xF6b3m2Ui3lizYINkj7u94MjY0IC0gY29yZSAxNjUgcjMyMjIgYjM1NjA1YSAtIEguMjY0L01QRUctNCBBVkMgY29kZWMgLSBD"
    "b3B5bGVmdCAyMDAzLTIwMjUgLSBodHRwOi8vd3d3LnZpZGVvbGFuLm9yZy94MjY0Lmh0bWwgLSBvcHRpb25zOiBjYWJhYz0wIHJl"
    "Zj0zIGRlYmxvY2s9MTowOjAgYW5hbHlzZT0weDE6MHgxMTEgbWU9aGV4IHN1Ym1lPTcgcHN5PTEgcHN5X3JkPTEuMDA6MC4wMCBt"
    "aXhlZF9yZWY9MSBtZV9yYW5nZT0xNiBjaHJvbWFfbWU9MSB0cmVsbGlzPTEgOHg4ZGN0PTAgY3FtPTAgZGVhZHpvbmU9MjEsMTEg"
    "ZmFzdF9wc2tpcD0xIGNocm9tYV9xcF9vZmZzZXQ9LTIgdGhyZWFkcz0yIGxvb2thaGVhZF90aHJlYWRzPTEgc2xpY2VkX3RocmVh"
    "ZHM9MCBucj0wIGRlY2ltYXRlPTEgaW50ZXJsYWNlZD0wIGJsdXJheV9jb21wYXQ9MCBjb25zdHJhaW5lZF9pbnRyYT0wIGJmcmFt"
    "ZXM9MCB3ZWlnaHRwPTAga2V5aW50PTEwIGtleWludF9taW49MSBzY2VuZWN1dD00MCBpbnRyYV9yZWZyZXNoPTAgcmNfbG9va2Fo"
    "ZWFkPTEwIHJjPWNyZiBtYnRyZWU9MSBjcmY9NDAuMCBxY29tcD0wLjYwIHFwbWluPTAgcXBtYXg9NjkgcXBzdGVwPTQgaXBfcmF0"
    "aW89MS40MCBhcT0xOjEuMDAAgAAAAkZliIQv/w/46KAA/FD6wcVwJsJQZIvBN4PQeBsQBaQldPnu3CUfw1gQLYW9HbyeA+EkBgGC"
    "ACOGphIJk8f8DmMZgynj/jIgByRADTBEKIAQCxXFcHQmMHQmIzAcmQAAgOJgiAAIG8QA7FcVwdCYg6Ex/A/hw4cOgPHh+uEoGQIC"
    "UAcOglUcevgBBOysgYTb9/h9KfhvFA/KzAwAMYIQABAIcc/h6u4kDYwCVEzvL13/tL4cFmtxFQKAJ5biuOX8gVlLQJhPT0/+i+Hh"
    "w2ADO83Tl//CfVJy3dfz/GeZ+PTA/jV78KxoFZHFXxIEzwQP/8FZYEvr7Lz0QAoQmJi3FctBMQdBMf9I/wgTqKYua1DIXV1C8JAk"
    "HDAAeCZeNKqWAPU5iaYNaNkf/CsAvDpFXea4SiYSAkHytyyty+FqjbqP+IYBwWlrCtqD0Big0K42+gb+gHQmJFLtjd/4AkA4d3Le"
    "KxWF1kc4DgAEwVgmorGCugYK6IOhMAb+hqP4vAAxAcOQCV+vt/BG8fXDJ6CWAwSkUFSyipcflhpoxr2LxGABw7xryXLe4ZRwpjj5"
    "U8CxIQr2FGlioscF1IiAKIAATPz7ETY8HgNiDwNiY0+H5A2Tn8ijA0GCBOAcFpoace4SARLvFa4Jv6gyIYa5iiQ+ApgZQUQpqaad"
    "TSQ7BUbw7BUbxTKKYkAAQF4gAQmWsK1iR0TEjomPgTfDw4SVLmX4YAK+FBsPmIjMlg8A057hAl5pCgAVwVj5gD2MGAAJsz7GfYiQ"
    "NjHgbGAAAAAiQZo4X9EveMYW4JBSrmP9aMV6iMvYe4JLvwFR6o2vUS0ngAAAAC9BmlQ+NeGOCQQtfA+73D0Ed3d8AC/BJvcRSa8E"
    "FWEv/Vgo1qtYtQHZfBJrUTrB4AAAADJBmmHxrwQdCEWnwR3fBlIDf+GKr3uB2QqM2tfXh6L8t5b/PFMBv5tX4c1qH3MLy6XfPAAA"
    "ADtBmoHxvhgy1u+URLX5dDuj2GL31qZFX6tXmfgoq+7ufDIA9c4Wgk1W5+CMy1g9oy+HCqqqMUAg/qTDwAAAAFdBmqPFm8NP+HOK"
    "DAGaT3952I9Af7J46BWGwVkcVfEgEzrwSGu7oHz+eG6n58a/2Cje7u7jaMq8JJWye/wQcoaKP+fd4NMzFLGlZkLss2fwSEVVHPFR"
    "UeAAAAAyQZrBcb4JCPlsyEtfURSY/Aqy6G0BwfBXeDoTEJT7PfwR9V4il9RLU34egjqLqoApUeAAAAAqQZrhcb4bJe4BwBf0htb8"
    "KVAay/4rrTL4JK1lQil9RLWK8OI9Kv3GldckAAAAKkGbANxrwQc8A5VqX/fhqiWHwRnd3czEUq8E38OYvUEKMOXUvrwxREUzwAAA"
    "ACRBmyBXG+pl76DlQGvoFBXvrUwiKX0YqvwSVWonQp/BHWa+lR4="
)


def _write_clip() -> str:
    path = os.path.join(tempfile.mkdtemp(prefix="pn-video-demo"), "clip.mp4")
    with open(path, "wb") as handle:
        handle.write(_CLIP)
    return path


@pn.component
def VideoDemo() -> pn.Node:
    """Render a player, its event readouts, and buttons for the handle's commands."""
    clip = pn.use_memo(_write_clip, [])
    player = pn.use_ref()
    source, set_source = pn.use_state(clip)
    controls, set_controls = pn.use_state(False)
    ready, set_ready = pn.use_state("no")
    ticks, set_ticks = pn.use_state(0)
    position, set_position = pn.use_state(0.0)
    ended, set_ended = pn.use_state(0)
    buffering, set_buffering = pn.use_state("no")
    error, set_error = pn.use_state("none")
    asked, set_asked = pn.use_state("not asked")

    def handle() -> Optional[VideoHandle]:
        current = player.current
        return current if isinstance(current, VideoHandle) else None

    def play() -> None:
        current = handle()
        if current is not None:
            current.play()

    def pause() -> None:
        current = handle()
        if current is not None:
            current.pause()

    def on_ready(info: VideoInfo) -> None:
        set_ready(f"{info.width:.0f}x{info.height:.0f}")

    def on_progress(seconds: float, duration: float) -> None:
        del duration
        set_position(seconds)
        set_ticks(lambda total: total + 1)

    async def ask() -> None:
        current = handle()
        if current is not None:
            current.seek(1.0)
            await asyncio.sleep(0.5)
            set_asked(f"{await current.position():.1f}")

    def seek_and_ask() -> None:
        asyncio.ensure_future(ask())

    return DemoScreen(
        "Video",
        "A native player, its events, and a typed handle.",
        DemoSection(
            "Player",
            Video(
                source=source,
                controls=controls,
                muted=True,
                resize_mode="contain",
                on_ready=on_ready,
                on_progress=on_progress,
                on_end=lambda: set_ended(lambda total: total + 1),
                on_error=lambda message: set_error("some" if message else "none"),
                on_buffering=lambda value: set_buffering("yes" if value else "no"),
                ref=player,
                style=pn.style(height=160, background_color="#000000"),
            ),
            ButtonsRow(
                pn.Button("Play", on_press=play),
                pn.Button("Pause", on_press=pause),
            ),
            ButtonsRow(
                pn.Button("Seek and ask", on_press=seek_and_ask),
                pn.Button("Native controls", on_press=lambda: set_controls(not controls)),
            ),
            pn.Button("Load a missing file", on_press=lambda: set_source(f"{clip}.missing")),
        ),
        DemoSection(
            "Events",
            ResultText("Ready", ready),
            ResultText("Progressing", "yes" if ticks > 0 else "no"),
            ResultText("Position", f"{position:.1f}"),
            ResultText("Ended", ended),
            ResultText("Buffering", buffering),
            ResultText("Asked position", asked),
            ResultText("Video error", error),
            Hint("The clip is embedded in this screen, so nothing here needs the network."),
        ),
    )
