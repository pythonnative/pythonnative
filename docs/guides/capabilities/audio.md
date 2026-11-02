# Audio

`pythonnative.audio` plays sounds and records from the microphone. On iOS it uses
`AVAudioPlayer` for files, `AVPlayer` for network URLs, and `AVAudioRecorder`. On
Android it uses Media3 ExoPlayer and `MediaRecorder`. The browser preview uses
`HTMLAudioElement` and `MediaRecorder`.

## Setup

```toml
[plugins]
use = ["audio"]

# Only if the app records.
[permissions]
microphone = "Record voice notes."
```

Playback needs no permission, so the plugin doesn't require `microphone` at build
time. An app that records without declaring it gets a `NativeModuleError` with the
code `missing_usage_string` from `Recorder.start`, on both platforms, rather than a
crash at the system prompt.

## Playing a sound

```python
from pythonnative.audio import Sound

sound = await Sound.load(pn.asset("chime.m4a"))
sound.on_end(sound.unload)
sound.play()
```

`Sound.load` takes an `http(s)` URL, a file path, a `file://` URL, a bundled
[`Asset`][pythonnative.Asset], or a path under `app/assets/`. It raises
`NativeModuleError` with the code `load_failed` if the source can't be read.

| Member | Meaning |
| --- | --- |
| `play()`, `pause()` | Start or resume, and pause |
| `stop()` | Pause and rewind. The sound stays loaded |
| `seek(seconds)` | Jump to a position |
| `set_volume(v)` | Level from `0.0` to `1.0` |
| `set_rate(r)` | Speed, where `1.0` is normal. Pitch is preserved |
| `looping` | Read or assign whether it restarts at the end |
| `position`, `duration` | Seconds. `duration` is `0` when unknown |
| `on_end(callback)` | Called at each natural end. Returns a function that removes it |
| `unload()` | Release the player |

A sound that plays to its end rewinds, so `play()` plays it again. A looping sound
doesn't call `on_end` callbacks. To unload on exit, use it as a context manager:

```python
async with await Sound.load(url) as sound:
    sound.play()
    await asyncio.sleep(sound.duration)
```

## Recording

```python
from pythonnative.audio import Recorder

recorder = await Recorder.start(quality="high")
await asyncio.sleep(3)
level = recorder.metering()
recording = await recorder.stop()
print(recording.path, recording.duration)
```

`Recorder.start` prompts for the microphone when needed and raises
`NativeModuleError` with the code `permission_denied` when the user refuses, or
`recording_failed` when iOS's audio input doesn't start within 20 seconds. Only one
recording runs at a time.

The file is AAC in an MPEG-4 container. With no `path`, it goes in a new file under
the cache directory, which the system may clear, so move anything worth keeping. A
relative `path` is under the cache directory too.

`pause()` and `resume()` continue in the same file, and paused time doesn't count
toward `duration`. `metering()` returns the input level in decibels relative to full
scale, from `-160` to `0`. iOS reports the average power and Android the peak since
the last call.

## Audio mode

[`Audio.set_mode`][pythonnative.audio.Audio.set_mode] is mainly iOS's
`AVAudioSession`:

```python
from pythonnative.audio import Audio

Audio.set_mode(category="playback", mix_with_others=True)
```

Without a call, iOS uses `solo_ambient`, which the silent switch mutes. Call it with
`category="playback"` for sound the user asked to hear. A running `Recorder`
switches to `play_and_record` and restores the previous category when it stops.

Android has no categories, so `category`, `default_to_speaker`, and `allow_bluetooth`
have no effect there. `mix_with_others` stops a `Sound` from taking audio focus, and
`duck_others` makes it take focus in a way that lowers other apps instead of pausing
them. In the browser preview, the call does nothing.

## Lifecycle and background audio

Playback pauses when the app goes to the background. It doesn't resume by itself.
This plugin doesn't set up background playback or recording. On iOS, an app that
adds `audio` to `UIBackgroundModes` through `[ios].extra_info_plist` keeps playing.
Android has no equivalent here, since that would need a foreground service.

## Platform differences

- **Metering.** See above: average on iOS, peak on Android, computed from the signal
  in the preview.
- **Preview.** `Recording.path` is a `blob:` URL, which `Sound.load` accepts but
  `os.path` doesn't. Error codes aren't reported from the page, so a failure there
  is a `NativeModuleError` with only a message.

## App Store review

Apple's automated checks look at which APIs a binary references. Since this plugin
references `AVAudioRecorder`, a playback-only app might be flagged for a missing
microphone purpose string. This hasn't been tested against App Store Connect. If it
happens, declare `microphone` under `[permissions]`, even if the app never records.

## What wasn't verified on a simulator

These ran on the iOS simulator and an Android API 31 emulator, with local files:
load, play, pause, seek, stop, rate, volume, position, duration, `on_end`, looping,
`set_mode`, unload, and the `missing_usage_string` error.

On the Android emulator, recording also ran for real: start, pause, resume, metering,
stop, a nonempty file, and playing it back. An emulator under load produced recordings
shorter than the wall-clock time (about 1.2 seconds out of 2.3), which looks like its
virtual microphone delivering too few samples, so check the duration on a device.

**Recording has not run on iOS.** On the simulator used for verification,
`AVAudioRecorder.record()` never returned: it blocks inside Core Audio, waiting for
the host Mac's audio server to accept the input stream
(`HALC_ProxyIOContext::_TellServerAboutStreamUsage`). The same thing happens with the
`record` category instead of `play_and_record`, and with no earlier playback, so it
isn't specific to the session setup. `Recorder.start` reports `recording_failed` after
20 seconds there, and the rest of the app stays responsive, though `AVPlayer` playback
in the same process stalls while the start is pending. Everything past that call is
unproven on iOS: pause, resume, metering, stop, and the duration. Try it on a device.

The rest remains unproven on both platforms:

- Whether the sound came out right: positions and durations were observed, not audio.
- Captured audio's content. Only the file and its timing were checked.
- Network sources, and with them the iOS `AVPlayer` path, since the verification
  deliberately ran with no network dependency.
- Android's audio focus behavior with other apps playing.
- The permission prompt's denied path, and `Permissions.request("microphone")`.
- The browser preview's module: its script passes a syntax check and the dev server
  serves it, but it hasn't played or recorded anything in a browser.
