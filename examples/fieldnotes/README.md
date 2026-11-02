# Field Notes

A field journal you could actually keep. Write what you saw, attach photos, voice
notes, and video, see it all on a map, come back to an entry when a reminder fires,
and share a journal live with your other devices. It works offline, and says so.

It's also the acceptance test for [RFC 0008](../../rfcs/0008-production-platform.md):
one real app that makes every first-party capability except `push` work together.
There's a guided tour of the code in
[`docs/examples/fieldnotes.md`](../../docs/examples/fieldnotes.md).

## Running it

From this directory:

```sh
pn run ios
pn run android
```

To run the release configuration, which has no dev server and shows the custom error
screen instead of the development one:

```sh
pn run ios --release --no-logs
pn run android --release --no-logs
```

`assets/icon.png` is checked in. `assets/generate_icon.py` draws it, using Pillow.

## Running the sync server

With no server configured, the journal stays on the device and tells you so. To see
two devices share a journal, run the development server, which uses only the standard
library:

```sh
python server.py                  # for simulators on this machine
python server.py --host 0.0.0.0   # for phones on your network
```

It listens on port 8770, because `pn start` already has 8765, and keeps its data in
`~/.fieldnotes-server` unless you pass `--data`. Then in the app, go to **Settings >
Sync server** and enter an address:

| Running on | Address |
| --- | --- |
| iOS simulator | `localhost:8770` |
| Android emulator | `10.0.2.2:8770` |
| A phone | Your computer's address, such as `192.168.1.20:8770` |

The server has no authentication and no TLS. Don't put it on the internet.
`GET /health` reports how many entries and clients it has.

## Tests

From the repository root:

```sh
uv run pytest tests/test_fieldnotes.py
```

These run the real screens against a real SQLite file and the real server on
localhost. Check types and the rules of hooks from this directory:

```sh
uv run mypy --strict app
uv run pn lint app
```

The Maestro flows need a build on a running simulator or emulator:

```sh
maestro test -e APP_ID=dev.pythonnative.fieldnotes ../../tests/e2e/flows/fieldnotes/smoke.yaml
maestro test -e APP_ID=dev.pythonnative.fieldnotes ../../tests/e2e/flows/fieldnotes/journal.yaml
```

`smoke.yaml` passes on a release build. On iOS, set a simulated location first
(`xcrun simctl location booted set 59.91,10.75`), or a new entry finds no position.

## What each capability does here

| Capability | In this app | Code |
| --- | --- | --- |
| `location` | Records where each entry was written. A fix that arrives after saving still lands on the entry | `app/geo.py`, `app/ui/editor_screen.py` |
| `maps` | The map tab has a marker per entry, and pressing one opens it | `app/ui/map_screen.py` |
| `camera` | `CameraView` on the capture screen takes photos and clips. `Camera.take_photo` is the way out when there's no preview | `app/ui/capture_screen.py` |
| `sensors` | A level on the capture screen, from the accelerometer | `app/ui/capture_screen.py` |
| `pickers` | Adds photos and videos from the library | `app/ui/attachments.py` |
| `audio` | `Recorder` records voice notes with a level meter, and `Sound` plays them back | `app/ui/attachments.py` |
| `video` | Plays a video attachment in a native player | `app/ui/media_screen.py` |
| `notifications` | Reminders, whose tap opens `fieldnotes://entries/{id}`, including from a cold start | `app/reminders.py`, `app/main.py` |
| `background` | A periodic task that exchanges entries and files while the app isn't open | `app/services.py` |
| `purchases` | A one-time Pro unlock, which lifts the limit of 3 attachments per entry | `app/pro.py`, `app/ui/pro_screen.py` |
| `biometrics` | An optional lock, which comes back when the app leaves the foreground | `app/ui/lock_screen.py` |

Three more parts of the framework carry weight without being capabilities.
`pn.WebSocket` is the live connection, with reconnection and backoff, in
`app/syncing.py`. `pn.fetch` uploads attachments with progress and downloads them
as streams, in `app/transfers.py`. `pn.set_error_handler` writes to the on-disk log
that **Settings > Error log** shows, and `pn.set_error_fallback` replaces the release
build's crash screen, in `app/errorlog.py` and `app/ui/fallback.py`.

`sqlite3` imports and works on both device runtimes, so the journal is a real database
under the app's data directory: `app/database.py` has its schema and migrations, and
`app/repository.py` holds all of its SQL.

Deep links are `fieldnotes://entries/{id}`, `fieldnotes://new`, `fieldnotes://pro`,
`fieldnotes://journal`, `fieldnotes://map`, and `fieldnotes://settings`.

## What a simulator can't show

- **Camera on iOS.** The simulator has no camera, so the capture screen says so and offers
  the system camera, which reports no photo. Live preview, pictures, and clips need a
  device. The Android emulator's virtual camera runs them.
- **Recording on iOS.** On a simulator, `AVAudioRecorder` may never start, and the
  recorder reports `recording_failed` after 20 seconds, which the app shows. Playback
  works there. Recording runs on the Android emulator.
- **The level on iOS.** The simulator has no sensors, so the badge doesn't appear. The
  Android emulator's virtual sensors drive it.
- **Background sync on iOS.** A simulator refuses to schedule background work, and the
  settings screen says so. A device needs the debugger command in
  [the guide](../../docs/guides/capabilities/background.md#testing-it).
- **Purchases.** Neither simulator can sell anything without store setup, so **Pro**
  shows that the store is unavailable. The purchase paths are covered by the fake store
  in `tests/test_fieldnotes.py`. A real purchase needs App Store Connect or a Play test
  track, and a product with the ID `dev.pythonnative.fieldnotes.pro`.
- **Maps on Android.** This project sets no `android_api_key`, so the map tab shows the
  SDK's documented message and lists your places instead. Set `GOOGLE_MAPS_API_KEY` to see
  the map, on an image with Play services. iOS maps need no key and work on a simulator.
- **Biometrics.** A simulator has no enrolled biometrics until you enroll them, so the
  lock's switch stays off.
