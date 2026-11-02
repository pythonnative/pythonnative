# Video

`pythonnative.video` plays local and remote video in a native player view:
`AVPlayer` on iOS, Media3 ExoPlayer on Android, and an HTML5 `<video>` in the
browser preview.

## Setup

```toml
[plugins]
use = ["video"]
```

Video needs no permission. On Android, the plugin adds
`androidx.media3:media3-exoplayer` and `androidx.media3:media3-ui` to the build.
Only an app that enables the plugin pays for them.

## The view

```python
import pythonnative as pn
from pythonnative.video import Video


@pn.component
def Player() -> pn.Node:
    player = pn.use_ref()
    return pn.Column(
        Video(
            source=pn.asset("intro.mp4"),
            controls=True,
            ref=player,
            style=pn.style(aspect_ratio=16 / 9),
        ),
        pn.Button("Restart", on_press=lambda: player.current.seek(0)),
    )
```

The view has no intrinsic size, so `style` must give it one: a `width` and
`height`, a `flex`, or an `aspect_ratio` inside a sized parent. Without one it
collapses to nothing.

`source` takes an `http(s)` URL, a file path, a `file://` URL, a bundled
[`Asset`][pythonnative.Asset], or a path under `app/assets/`. Changing it replaces
what's playing.

| Prop | Default | Meaning |
| --- | --- | --- |
| `controls` | `False` | Show the platform's playback controls |
| `autoplay` | `False` | Start as soon as the video is ready |
| `loop` | `False` | Restart at the end |
| `muted` | `False` | Silence the audio without changing `volume` |
| `volume` | `1.0` | Audio level from `0.0` to `1.0` |
| `rate` | `1.0` | Playback speed |
| `resize_mode` | `"contain"` | `"contain"`, `"cover"`, or `"stretch"` |
| `poster` | `None` | An image shown until playback starts |
| `progress_interval` | `0.25` | Seconds between `on_progress` calls |

## Events

| Event | Arguments | When |
| --- | --- | --- |
| `on_ready` | [`VideoInfo`][pythonnative.video.VideoInfo] | The source loaded and can play |
| `on_progress` | `position`, `duration` | While playing, and after a seek, every `progress_interval` |
| `on_end` | | Playback reached the end. A looping video doesn't fire it |
| `on_error` | `message` | The source can't load or play |
| `on_buffering` | `bool` | Playback stalled waiting for data, or can continue |

## The handle

A `ref` receives a [`VideoHandle`][pythonnative.video.VideoHandle]: `play()`,
`pause()`, `seek(seconds)`, and `await position()`. `play()` restarts a video that
has ended.

## Lifecycle

The player is released when the view unmounts. When the app goes to the
background, playback pauses, and it resumes when the app returns if it was playing.
Android also releases the player while the activity is stopped, since a device has
few hardware decoders, and rebuilds it at the same position.

## Platform differences

- **Controls.** iOS shows `AVPlayerViewController`, Android shows `PlayerView`'s
  controller, and the preview shows the browser's own.
- **Silent switch.** On iOS, a video with sound changes the app's audio session
  from the default `solo_ambient` to `playback`, so the silent switch doesn't mute
  it. A category the app chose with
  [`Audio.set_mode`][pythonnative.audio.Audio.set_mode] stays as it is.
- **Autoplay in the preview.** A browser may refuse to start a video with sound
  until the user has interacted with the page. Native platforms don't.
- **Ready in the preview.** `on_ready` fires at `loadedmetadata`, a little earlier
  than on device.

## What wasn't verified on a simulator

These ran on the iOS simulator and an Android API 31 emulator with local clips:
`on_ready`, `on_progress`, `on_end`, `on_buffering`, `on_error`, `play`, `pause`,
`seek`, `position`, replay after the end, native controls, and unmounting. Android
also showed the poster, and released the player in the background and rebuilt it on
return. The rest remains unproven:

- Sound output itself: the clips ran muted, and only positions were observed.
- Playback from a network URL, including stalls that fire `on_buffering` mid-stream,
  since the verification deliberately ran with no network dependency.
- The poster and the pause and resume around backgrounding on iOS.
- The hardware decoder limit that Android's release on stop guards against. An
  emulator decodes in software.
- The browser preview's manager: its script passes a syntax check and the dev server
  serves it, but it hasn't played anything in a browser.
