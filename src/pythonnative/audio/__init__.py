"""Audio playback and recording.

Enable it in ``pythonnative.toml``. Playback needs nothing else; recording also
needs a microphone usage string:

```toml
[plugins]
use = ["audio"]

[permissions]
microphone = "Record voice notes."
```

Example:
    ```python
    from pythonnative.audio import Audio, Recorder, Sound

    async def chime() -> None:
        Audio.set_mode(category="playback")
        sound = await Sound.load("https://example.com/chime.mp3")
        sound.on_end(sound.unload)
        sound.play()

    async def voice_note() -> None:
        recorder = await Recorder.start()
        await asyncio.sleep(3)
        recording = await recorder.stop()
        async with await Sound.load(recording.path) as sound:
            sound.play()
            await asyncio.sleep(recording.duration)
    ```
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Callable, Dict, List, Literal, Optional, Protocol, Type, Union

from ..assets import Asset
from ..native_modules.registry import NativeModuleError, native_module
from ..sdk.plugin import plugin_module

__all__ = ["Audio", "AudioCategory", "Recorder", "Recording", "RecordingQuality", "Sound", "SoundSource"]

AudioCategory = Literal["ambient", "solo_ambient", "playback", "record", "play_and_record", "multi_route"]
"""An ``AVAudioSession`` category, spelled in Python's style."""

RecordingQuality = Literal["low", "medium", "high"]
"""AAC in an MPEG-4 container at 16 kHz and 32 kbps, 22 kHz and 64 kbps, or 44.1 kHz and 128 kbps."""

SoundSource = Union[str, Asset, "os.PathLike[str]"]
"""An ``http(s)`` URL, a file path, a bundled [`Asset`][pythonnative.Asset], or a path under ``app/assets/``."""


@dataclass(frozen=True)
class Recording:
    """A finished recording.

    Attributes:
        path: Absolute path of the ``.m4a`` file.
        duration: Recorded length in seconds, not counting pauses.
    """

    path: str
    duration: float


class _AudioService(Protocol):
    async def load_sound(
        self, *, source: str, volume: float = 1.0, rate: float = 1.0, looping: bool = False
    ) -> int: ...

    def play_sound(self, *, id: int) -> None: ...

    def pause_sound(self, *, id: int) -> None: ...

    def stop_sound(self, *, id: int) -> None: ...

    def seek_sound(self, *, id: int, seconds: float) -> None: ...

    def set_sound_volume(self, *, id: int, volume: float) -> None: ...

    def set_sound_rate(self, *, id: int, rate: float) -> None: ...

    def set_sound_looping(self, *, id: int, looping: bool) -> None: ...

    def sound_position(self, *, id: int) -> float: ...

    def sound_duration(self, *, id: int) -> float: ...

    def unload_sound(self, *, id: int) -> None: ...

    async def start_recording(self, *, path: Optional[str] = None, quality: RecordingQuality = "high") -> int: ...

    def pause_recording(self, *, id: int) -> None: ...

    def resume_recording(self, *, id: int) -> None: ...

    async def stop_recording(self, *, id: int) -> Recording: ...

    def recording_metering(self, *, id: int) -> float: ...

    def set_mode(
        self,
        *,
        category: AudioCategory = "playback",
        mix_with_others: bool = False,
        duck_others: bool = False,
        default_to_speaker: bool = False,
        allow_bluetooth: bool = False,
    ) -> None: ...


class _Fallback:
    """No audio hardware off device: sounds keep their settings, and tests can ``emit`` a ``sound_ended``."""

    def __init__(self) -> None:
        self._next = 0
        self.sounds: Dict[int, Dict[str, Any]] = {}
        self.recordings: Dict[int, Optional[str]] = {}
        self.mode: Optional[Dict[str, Any]] = None

    def _id(self) -> int:
        self._next += 1
        return self._next

    def _sound(self, id: int) -> Dict[str, Any]:
        sound = self.sounds.get(id)
        if sound is None:
            raise NativeModuleError("Audio", "sound", f"no loaded sound {id}", "not_found")
        return sound

    def load_sound(self, *, source: str, volume: float = 1.0, rate: float = 1.0, looping: bool = False) -> int:
        id = self._id()
        self.sounds[id] = {"source": source, "position": 0.0, "playing": False}
        return id

    def play_sound(self, *, id: int) -> None:
        self._sound(id)["playing"] = True

    def pause_sound(self, *, id: int) -> None:
        self._sound(id)["playing"] = False

    def stop_sound(self, *, id: int) -> None:
        self._sound(id).update(playing=False, position=0.0)

    def seek_sound(self, *, id: int, seconds: float) -> None:
        self._sound(id)["position"] = seconds

    def set_sound_volume(self, *, id: int, volume: float) -> None:
        self._sound(id)["volume"] = volume

    def set_sound_rate(self, *, id: int, rate: float) -> None:
        self._sound(id)["rate"] = rate

    def set_sound_looping(self, *, id: int, looping: bool) -> None:
        self._sound(id)["looping"] = looping

    def sound_position(self, *, id: int) -> float:
        return float(self._sound(id)["position"])

    def sound_duration(self, *, id: int) -> float:
        self._sound(id)
        return 0.0

    def unload_sound(self, *, id: int) -> None:
        self.sounds.pop(id, None)

    def start_recording(self, *, path: Optional[str] = None, quality: str = "high") -> int:
        id = self._id()
        self.recordings[id] = path
        return id

    def pause_recording(self, *, id: int) -> None:
        del id

    def resume_recording(self, *, id: int) -> None:
        del id

    def stop_recording(self, *, id: int) -> Recording:
        return Recording(path=self.recordings.pop(id, None) or f"recording-{id}.m4a", duration=0.0)

    def recording_metering(self, *, id: int) -> float:
        del id
        return -160.0

    def set_mode(self, **mode: Any) -> None:
        self.mode = mode


plugin_module(
    "Audio",
    _AudioService,
    plugin="audio",
    events={"sound_ended": Dict[str, Any]},
    fallback=_Fallback,
    browser=True,
)


def _uri(source: SoundSource) -> str:
    uri = source.uri if isinstance(source, Asset) else os.fspath(source)
    if not uri:
        raise ValueError("Sound.load needs a source")
    return uri


class Sound:
    """One loaded sound. Create it with [`Sound.load`][pythonnative.audio.Sound.load].

    After a sound plays to its end, it rewinds to the start, so ``play()``
    plays it again. Playback pauses when the app goes to the background.

    Using it as an async context manager unloads it on exit:

    ```python
    async with await Sound.load(asset) as sound:
        sound.play()
    ```

    Raises:
        NativeModuleError: From any method once the sound is unloaded, with
            the code ``unloaded``.
    """

    def __init__(self, id: int, *, looping: bool = False) -> None:
        self._id: Optional[int] = id
        self._looping = looping
        self._end_callbacks: List[Callable[[], Any]] = []
        self._unsubscribe: Optional[Callable[[], None]] = None

    @classmethod
    async def load(
        cls, source: SoundSource, *, volume: float = 1.0, rate: float = 1.0, looping: bool = False
    ) -> "Sound":
        """Load ``source``, ready to play. Playback doesn't need any permission.

        Args:
            source: What to play: an ``http(s)`` URL, a file path, a bundled
                [`Asset`][pythonnative.Asset], or a path under ``app/assets/``.
            volume: Initial level from ``0.0`` to ``1.0``.
            rate: Initial speed, where ``1.0`` is normal.
            looping: Whether to restart at the end.

        Returns:
            The loaded sound.

        Raises:
            NativeModuleError: With the code ``load_failed`` when the source
                can't be read or decoded, or ``plugin_not_enabled`` when
                ``audio`` isn't in the build.
        """
        id = await native_module("Audio").call_async(
            "load_sound", source=_uri(source), volume=float(volume), rate=float(rate), looping=bool(looping)
        )
        return cls(int(id), looping=bool(looping))

    def _call(self, method: str, **args: Any) -> Any:
        if self._id is None:
            raise NativeModuleError("Audio", method, "this sound was unloaded", "unloaded")
        return native_module("Audio").call(method, id=self._id, **args)

    def play(self) -> None:
        """Start or resume playback."""
        self._call("play_sound")

    def pause(self) -> None:
        """Pause, keeping the position."""
        self._call("pause_sound")

    def stop(self) -> None:
        """Stop and rewind to the start. The sound stays loaded."""
        self._call("stop_sound")

    def seek(self, seconds: float) -> None:
        """Jump to ``seconds`` from the start."""
        self._call("seek_sound", seconds=float(seconds))

    def set_volume(self, volume: float) -> None:
        """Set the level from ``0.0`` to ``1.0``."""
        self._call("set_sound_volume", volume=float(volume))

    def set_rate(self, rate: float) -> None:
        """Set the speed, where ``1.0`` is normal. Pitch is preserved."""
        self._call("set_sound_rate", rate=float(rate))

    @property
    def looping(self) -> bool:
        """Whether the sound restarts at its end. A looping sound doesn't call ``on_end`` callbacks."""
        return self._looping

    @looping.setter
    def looping(self, value: bool) -> None:
        self._call("set_sound_looping", looping=bool(value))
        self._looping = bool(value)

    @property
    def position(self) -> float:
        """The current position in seconds."""
        return float(self._call("sound_position"))

    @property
    def duration(self) -> float:
        """The length in seconds, or ``0`` when it isn't known (a live stream)."""
        return float(self._call("sound_duration"))

    def _ended(self, payload: Any) -> None:
        if isinstance(payload, dict) and payload.get("id") == self._id:
            for callback in list(self._end_callbacks):
                callback()

    def on_end(self, callback: Callable[[], Any]) -> Callable[[], None]:
        """Call ``callback`` each time the sound plays to its end.

        Args:
            callback: Takes no arguments. It may call ``unload``.

        Returns:
            A function that removes the callback.
        """
        self._end_callbacks.append(callback)
        if self._unsubscribe is None:
            self._unsubscribe = native_module("Audio").add_listener("sound_ended", self._ended)

        def remove() -> None:
            if callback in self._end_callbacks:
                self._end_callbacks.remove(callback)

        return remove

    def unload(self) -> None:
        """Release the player. Calling it again does nothing."""
        if self._id is None:
            return
        id, self._id = self._id, None
        self._end_callbacks.clear()
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        native_module("Audio").call("unload_sound", id=id)

    async def __aenter__(self) -> "Sound":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        self.unload()

    def __repr__(self) -> str:
        return f"Sound({self._id})" if self._id is not None else "Sound(unloaded)"


class Recorder:
    """A recording in progress. Create it with [`Recorder.start`][pythonnative.audio.Recorder.start]."""

    def __init__(self, id: int) -> None:
        self._id: Optional[int] = id

    @classmethod
    async def start(cls, path: Optional[str] = None, quality: RecordingQuality = "high") -> "Recorder":
        """Prompt for the microphone if needed, and start recording.

        Needs ``microphone`` under ``[permissions]`` in ``pythonnative.toml``.
        It isn't a build requirement of the plugin, since playback alone
        doesn't use the microphone, so this is where a missing entry surfaces.

        Args:
            path: Where to write the ``.m4a`` file. A relative path is under
                the app's cache directory. When ``None``, a new file there.
            quality: The encoding settings.

        Returns:
            The running recorder.

        Raises:
            NativeModuleError: With the code ``missing_usage_string`` when the
                app doesn't declare ``microphone`` under ``[permissions]``,
                ``permission_denied`` when the user refuses, ``recording_failed``
                when the system can't start recording in time, or ``plugin_not_enabled``
                when ``audio`` isn't in the build.
        """
        id = await native_module("Audio").call_async("start_recording", path=path, quality=quality)
        return cls(int(id))

    def _call(self, method: str, **args: Any) -> Any:
        if self._id is None:
            raise NativeModuleError("Audio", method, "this recording has stopped", "stopped")
        return native_module("Audio").call(method, id=self._id, **args)

    def pause(self) -> None:
        """Pause recording. The paused time doesn't count toward the duration."""
        self._call("pause_recording")

    def resume(self) -> None:
        """Continue a paused recording in the same file."""
        self._call("resume_recording")

    def metering(self) -> float:
        """The current input level in decibels relative to full scale, from ``-160`` (silence) to ``0``."""
        return float(self._call("recording_metering"))

    async def stop(self) -> Recording:
        """Finish the file.

        Returns:
            The finished [`Recording`][pythonnative.audio.Recording].

        Raises:
            NativeModuleError: With the code ``recording_failed`` when no
                audio was captured, or ``stopped`` when it's already finished.
        """
        if self._id is None:
            raise NativeModuleError("Audio", "stop_recording", "this recording has stopped", "stopped")
        id, self._id = self._id, None
        result = await native_module("Audio").call_async("stop_recording", id=id)
        return result if isinstance(result, Recording) else Recording(str(result["path"]), float(result["duration"]))

    def __repr__(self) -> str:
        return f"Recorder({self._id})" if self._id is not None else "Recorder(stopped)"


class Audio:
    """App-wide audio behavior."""

    @staticmethod
    def set_mode(
        *,
        category: AudioCategory = "playback",
        mix_with_others: bool = False,
        duck_others: bool = False,
        default_to_speaker: bool = False,
        allow_bluetooth: bool = False,
    ) -> None:
        """Set how the app's audio relates to the device and to other apps.

        This is mainly iOS's ``AVAudioSession``. Each call replaces the whole
        mode. Without a call, iOS uses ``solo_ambient``, which the silent
        switch mutes; call this with ``category="playback"`` for sound the user
        asked to hear. A running ``Recorder`` switches to ``play_and_record``
        and restores this mode when it stops.

        Android has no categories, so ``category``, ``default_to_speaker``, and
        ``allow_bluetooth`` have no effect there. ``mix_with_others`` and
        ``duck_others`` control whether a ``Sound`` takes audio focus, which
        pauses or lowers other apps. In the browser preview this does nothing.

        Args:
            category: The ``AVAudioSession`` category.
            mix_with_others: Play alongside other apps' audio.
            duck_others: Play over other apps' audio, lowering it.
            default_to_speaker: With ``play_and_record``, use the speaker
                rather than the receiver.
            allow_bluetooth: With ``record`` or ``play_and_record``, offer
                Bluetooth headsets as inputs.

        Raises:
            NativeModuleError: With the code ``invalid_mode`` when iOS rejects
                the combination.
        """
        native_module("Audio").call(
            "set_mode",
            category=category,
            mix_with_others=mix_with_others,
            duck_others=duck_others,
            default_to_speaker=default_to_speaker,
            allow_bluetooth=allow_bluetooth,
        )
