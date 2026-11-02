"""Demo screen for [`pythonnative.audio`][pythonnative.audio].

A one-second tone, embedded here so the simulator needs no network, exercises
``Sound``. Recording captures about a second from the microphone, checks the file,
and plays it back. A simulator's input may be silent, but the file is still real.
"""

from __future__ import annotations

import asyncio
import base64
import os
import tempfile
from typing import Any, Optional

from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText

import pythonnative as pn
from pythonnative.audio import Audio, Recorder, Sound
from pythonnative.native_modules.registry import NativeModuleError

# 660 Hz AAC, generated with ffmpeg's sine source.
_TONE = base64.b64decode(
    "AAAAHGZ0eXBNNEEgAAACAE00QSBpc29taXNvMgAAAAhmcmVlAAAJUG1kYXTcAExhdmM2My4xLjEwMgACNKFSbFQ0mqp9ryVX5+tX"
    "zbrdcKkIkkHwXqv333vo3WfRus9W6r1bqvwXovwXqqoyqUto2SjWzVs1jp2tWWtWWxYmnrJ3VvmFXp8Pkv8fyfofHeYaRjn1s+sn"
    "1s+qlKrSwMDaG0NoYGBgb9W+TfJgYGBjZs2DAwMDAwMDAxuWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW"
    "WWWWWWWWWWWXgAESltmiUVRiFrMQtZaFn9f2/frzxq9cc/t/4/f9U1eta/v/4/n9U1fGuP+P+37/qvV8aEZgpfDYp48ePHl7GyLq"
    "vq1Fs/Gu+s8KRyysVdpBNFo4omBxjTSmBxiflp1/J6j5PUfLi8KKPlxeFFHy+XyeA10Uduz8DWvKXyV0hw/o9XyuTCk7igbTVxHS"
    "XDBefSRni554np4np54onnp54ovo9PPPFFF9Po9e3oE/iXq2DsloooooooooNwD08KyMSysIpJlf9q47rv8/48yZqaSSXJJJIIDz"
    "D9x/okQA/8fmcutzP317+l+u+/fNZqAHd3cQbHrxxxYELDGLtjHEeNWncv3xS/bcXU06jxrC0tLSlOibY4zTMBO/vCPj4bGf30D4"
    "+Gx7+8I+Phse/vCMnwYe/vCPj4bHv7wj4+DD394Rk+Gx7+5D4+DD399A8fi1Oj3hHx8IGf3hGT4Mn30cAOAwmPZJDAkOKFIzh+kv"
    "WeP/63/f/343uari+fHW1qaqCZ0dBTu2VUe3ZLRwQUFBg55clW1h1uhxuiHzAtrC/ZRkiTKJV/gSGvtLeJPiW9pPmR4nyxsMDJpp"
    "jznpqmEluHLcF4JJjasyLNTCwlIAUb3BkVXTdgguCxxHYORfiXAHEUKEgeUGuADsMKE2OBIg1vN6/iJuv/6f/v/tKmTOrfOsmsNV"
    "AsQRItM7yNKjttrstj3QRBEESIgpItIyqNJGVJunKxFa8ZTsImAK322UaYaGxurmlJpUaSKSKQN9GBtSA1C8DXr17OzN9qv2VyVc"
    "levW3iwoqgSE0k1lFVBV4hOJnh5lnectMbQwyqd/uz4A5DCYSEoliYRFNy/XXzqXnP/+j/7f565i7567rjm7yXffQJnZ2HRKqXqc"
    "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"
    "HGRhdGEAAAABAAAAAExhdmY2My4xLjEwMg=="
)


def _write_tone() -> str:
    path = os.path.join(tempfile.mkdtemp(prefix="pn-audio-demo"), "tone.m4a")
    with open(path, "wb") as handle:
        handle.write(_TONE)
    return path


@pn.component
def AudioDemo() -> pn.Node:
    """Render buttons that play a sound and record a clip, with readouts for each."""
    tone = pn.use_memo(_write_tone, [])
    sound_ref = pn.use_ref()
    duration, set_duration = pn.use_state("not loaded")
    ends, set_ends = pn.use_state(0)
    position, set_position = pn.use_state("none")
    level, set_level = pn.use_state("none")
    recorded, set_recorded = pn.use_state("none")
    replayed, set_replayed = pn.use_state("no")
    failure, set_failure = pn.use_state("none")

    def unload_on_exit() -> Any:
        def cleanup() -> None:
            sound: Optional[Sound] = sound_ref.current
            if sound is not None:
                sound.unload()

        return cleanup

    pn.use_effect(unload_on_exit, [])

    async def play() -> None:
        try:
            Audio.set_mode(category="playback")
            sound: Optional[Sound] = sound_ref.current
            if sound is None:
                sound = await Sound.load(tone)
                sound.on_end(lambda: set_ends(lambda total: total + 1))
                sound_ref.current = sound
            set_duration("about 1s" if 0.9 < sound.duration < 1.2 else f"{sound.duration:.2f}")
            sound.play()
            await asyncio.sleep(0.5)
            set_position("moving" if sound.position > 0 else "stuck")
        except NativeModuleError as error:
            set_failure(error.code or "unknown")

    async def record() -> None:
        try:
            recorder = await Recorder.start(quality="low")
            await asyncio.sleep(0.5)
            set_level("in range" if -160 <= recorder.metering() <= 0 else "out of range")
            await asyncio.sleep(0.5)
            recording = await recorder.stop()
            nonempty = os.path.getsize(recording.path) > 0
            set_recorded("nonempty" if nonempty and recording.duration > 0.5 else "empty")
            async with await Sound.load(recording.path) as replay:
                finished = asyncio.Event()
                replay.on_end(finished.set)
                replay.play()
                await asyncio.wait_for(finished.wait(), 10)
            set_replayed("yes")
        except NativeModuleError as error:
            set_failure(error.code or "unknown")

    return DemoScreen(
        "Audio",
        "Sound plays, and Recorder records.",
        DemoSection(
            "Sound",
            pn.Button("Play tone", on_press=lambda: asyncio.ensure_future(play())),
            ResultText("Duration", duration),
            ResultText("Position", position),
            ResultText("Ends", ends),
        ),
        DemoSection(
            "Recorder",
            pn.Button("Record a second", on_press=lambda: asyncio.ensure_future(record())),
            ResultText("Level", level),
            ResultText("Recording", recorded),
            ResultText("Replayed", replayed),
            ResultText("Audio error", failure),
            Hint("Recording needs microphone under [permissions] in pythonnative.toml."),
        ),
    )
