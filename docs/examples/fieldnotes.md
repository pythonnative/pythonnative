# Field Notes

Field Notes is a field journal: entries with photos, voice notes, and video, a map of
where they were written, reminders that open an entry, and live sync between devices.
It's in [`examples/fieldnotes`](https://github.com/pythonnative/pythonnative/tree/main/examples/fieldnotes),
and its README covers running it. This page is a tour of the parts worth stealing.

## How it's laid out

```text
app/
├── main.py          # Navigators, the error handler, deep links, and App
├── models.py        # Frozen dataclasses, including the store's Snapshot
├── database.py      # The SQLite file, its migrations, and its thread
├── repository.py    # All the SQL, in terms of models
├── journal.py       # The store, and every action that changes it
├── protocol.py      # What crosses the network, and who wins a conflict
├── syncing.py       # The live WebSocket, with reconnection
├── transfers.py     # Attachment uploads and downloads
├── services.py      # The sync client and the background task
├── pro.py           # The Pro unlock
├── reminders.py     # Notifications that link to an entry
├── geo.py           # Position fixes and map regions
├── errorlog.py      # The on-disk error log
└── ui/              # Screens, and the theme and widgets they share
```

Everything above `ui/` runs without a screen, which the background task needs and
the tests like. Nothing below `repository.py` writes SQL.

## A database on its own thread

`sqlite3` works on both device runtimes. A connection belongs to the thread that opened
it, and a slow disk shouldn't delay the thread that renders, so one connection lives on
one worker thread, and everything else sends it functions to call:

```python
async def run(self, work: Callable[[sqlite3.Connection], T]) -> T:
    def call() -> T:
        return work(self._connect())

    return await asyncio.get_running_loop().run_in_executor(self._executor, call)
```

A single worker also serializes every read and write with no locks. Migrations are a
tuple of SQL scripts, each moving `PRAGMA user_version` up by one, inside a transaction.
Only ever append to it, because those scripts have already run on devices.

The search registers a Python function with SQLite, because `LIKE` folds only ASCII:

```python
connection.create_function("folded", 1, _fold, deterministic=True)
```

That's the difference between finding "Blåbær" and not.

## One store, replaced whole

`Snapshot` is a frozen dataclass holding everything the screens read, in one
[`pn.Store`][pythonnative.Store]. Actions live on `Journal`. Each one writes through
the repository and then replaces the snapshot, so a screen can't show something that
wasn't saved:

```python
async def create_entry(self, draft: EntryDraft) -> Entry:
    entry = await self.repository.create(uuid.uuid4().hex, draft, now=time.time(), device=...)
    await self.refresh()
    self.announce_change()
    return entry
```

Screens select only what they need, and re-render only when that changes:

```python
entries = pn.use_store(journal.store, lambda state: state.entries)
```

Search runs in [`use_query`][pythonnative.use_query] keyed on the deferred text and the
entries, so a newer keystroke cancels a stale query, and a synced edit re-runs the
search that's on screen.

## Typed screens and deep links

A screen is a component, and its parameters are its route params. A deep link is one
`path=` on its `Screen`:

```python
Root = pn.StackNavigator(
    pn.Screen(Tabs, header_shown=False),
    pn.Screen(EntryScreen, title="Entry", path="entries/{id}"),
    pn.Screen(EditorScreen, title="New entry", path="new"),
    ...
)
```

A link can name an entry that was deleted, so `EntryScreen` has to make sense with
nothing to show.

## A reminder that opens an entry, even from cold

A tapped notification carries its entry's URL. A running app navigates through a
[`NavigationRef`][pythonnative.NavigationRef]. A tap that launched the app is better
served by seeding the first navigation state, so that the entry is there from the first
frame instead of the journal flashing first:

```python
def launch_state() -> Optional[NavigationState]:
    launch = Notifications.last_response()
    entry_id = entry_id_from(launch) if launch is not None else None
    if entry_id is None:
        return None
    return LinkTable(Root, LINK_PREFIXES).state_from_url(entry_url(entry_id))
```

Reading `last_response` claims the tap, so subscribing with `on_response` afterward
doesn't deliver it twice. On Android, any installed app can start an activity with such
data, so `entry_id_from` checks the URL as carefully as it would any deep link.

## Keeping a connection alive

The whole connection is one coroutine, run by an effect keyed on the server's URL.
Changing the URL cancels the old connection and starts a new one, and unmounting
closes the socket:

```python
async def follow() -> None:
    await sync_client.run(server_url)

pn.use_effect(follow, [server_url])
```

Reconnecting is a loop around `async with pn.WebSocket`, with a delay from `Backoff`:

```python
while True:
    self._publish(SyncStatus(phase="connecting", ...))
    try:
        async with pn.WebSocket(url, heartbeat=self.heartbeat, open_timeout=self.open_timeout) as socket:
            await self._session(socket, url)
        detail = "The server closed the connection."
    except _CONNECTION_ERRORS as error:
        detail = describe_failure(error)
    await self._wait_to_retry(detail)
```

Three small decisions make this behave. The backoff resets when the server says
`welcome`, not when the socket connects, so a server that accepts and then fails can't
keep the delay at its minimum. Jitter keeps a room of phones that lost the same server
from coming back in the same instant. And `_wait_to_retry` waits on an event, so a
network change or the **Retry now** button cuts the delay short.

## Merging without losing anything

Text fields are a last-writer-wins register: newer `updated_at` wins, and the device
ID breaks a tie, so two devices that saw the same two versions keep the same one.
Attachments merge by ID, so two people adding photos at once both keep them, and a
removal is final.

Whether an entry is synced is a count of local changes, not a flag. A push carries the
count, and the server echoes it back. An acknowledgment only clears the same count it
was sent with, so an edit made while a push was in flight still goes out:

```python
connection.execute("UPDATE entries SET dirty = 0 WHERE id = ? AND dirty = ?", (entry_id, change))
```

## Files don't go over the WebSocket

Messages carry an attachment's metadata. Files move with [`pn.fetch`][pythonnative.fetch]:
up with `files=` and `on_upload_progress`, and down with `stream=True`.

```python
response = await pn.fetch(
    f"{base}/attachments",
    method="POST",
    body={"id": attachment.id, "entry_id": attachment.entry_id, "kind": attachment.kind},
    files={"file": (attachment.name, path, attachment.mime_type)},
    on_upload_progress=progress,
)
```

Attachments store a path relative to the data directory, because an iOS app's container
path changes with each install. Cameras and pickers hand over files in the cache
directory, which the system can clear, so `Journal.add_attachment` moves them in first.

## Work that has to outlive a button

An event handler's coroutine belongs to the component that owns the view, and it's
canceled when that component unmounts. That's usually what you want, and sometimes a
disaster. Pressing **Unlock Pro** swaps the button for a thank-you, and if that canceled
the handler before `Purchases.finish`, the store would deliver the same purchase again on
every launch. So a purchase runs as an application task:

```python
PrimaryButton(label, lambda: run_application_task(pro.buy()), disabled=state.busy)
```

Deleting an entry works the same way, since its screen goes away as it does.

There's a subtler version of the same trap. `None` children are dropped before diffing,
not kept as holes, so a banner appearing above a row of buttons shifts those buttons
into new slots and remounts them. That loses their state and cancels whatever they're
running. `widgets.slots` gives each child a fixed key:

```python
pn.Column(
    *slots(
        problem=Banner(problem, "warning") if problem else None,
        shutter=PrimaryButton(shutter, take_picture),
    ),
)
```

## Failing in production

`main.py` installs both hooks at import time, so they hear about the very first render:

```python
pn.set_error_handler(journal.errors.record)
pn.set_error_fallback(error_fallback)
```

The log is one JSON object per line, so a crash halfway through a write costs at most
that line, and it trims itself so that a loop can't fill the disk. **Settings > Error
log** reads it. The fallback
replaces a whole screen above where `App` provides the theme, so it provides the theme
itself.

**Settings > Diagnostics** has a button that fails in an event handler and one that fails
during render. In a debug build you'll see the development error screen. In a release
build you'll see the fallback, with **Try again**.

## Saying what's true

Almost every capability has a state where it can't work: no store on an emulator, no
camera on a simulator, no Maps key, no background scheduling, no enrolled biometrics, a
refused permission. Each of those is a line on the screen rather than a silent no-op or
a crash, and each has a test. It's most of what separates this from a demo.

## Tests

`tests/test_fieldnotes.py` renders the real `App` with
[`pythonnative.testing`](../guides/testing.md), against a real SQLite file. The sync tests
start `server.py` on its own thread and event loop on localhost, then stop it and start
it again to watch the client reconnect. Only the hardware is fake, through each
capability's off-device fallback.

## Next steps

- Read the capability guides: [Capabilities](../guides/capabilities/index.md).
- Build it for a store: [Building for release](../guides/building-for-release.md).
