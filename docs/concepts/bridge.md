# The native bridge

Python reaches the native side through two channels. Commits, layout
reads, view commands, and animation requests go to the **renderer core**,
a C++20 library with a C ABI (`native/core/include/pn_core.h`) that every
target links: the iOS app binary, Android's `libpncore.so`, the
`pythonnative._core` extension that tests and tooling load on the
development machine, and the browser preview's WebAssembly build. Native
module calls go to the platform runtime: Swift in
`src/pythonnative/native/ios` and Kotlin in
`src/pythonnative/native/android`. App templates stage and embed both.

Python owns component state, reconciliation, and logical relationships.
The core owns validation, the shadow tree, layout, view flattening, list
datasets, animation graphs, and (on Android, in the browser, and in tests)
gesture recognition. The platform's mounting layer owns widgets, text
drawing, input, scrolling, navigation containers, accessibility, and the
frame clock. Python binds the core with `ctypes`
([`pythonnative.bridge.core`](../api/bridge.md#renderer-core)); the
protocol version is 7.

## Threads and the deadlock rule

| Thread | Calls into the core | May wait on |
| --- | --- | --- |
| Python application loop | `pn_core_measure`, `pn_core_command`, `pn_core_animate` (short, under the core lock) | the core lock |
| Commit worker (the loop's executor) | `pn_core_commit`, with the GIL released by `ctypes` | the core lock; the UI thread, only to measure an `intrinsic` leaf |
| Core work (a non-UI thread the platform schedules) | `pn_core_work`, which relayouts after container and intrinsic size reports | the core lock; the UI thread, as above |
| Platform UI thread | `pn_core_mount_next`, `pn_core_mount_finished`, `pn_core_animation_frame`, `pn_core_take_writes`, `pn_core_event`, `pn_core_pointer`, `pn_core_report_*`, list reads | nothing |

The rule that keeps this deadlock-free: **the UI thread never waits on
another thread and never takes the core's commit lock.** It takes mount
transactions from a queue, owns the mount-side state (list data sources,
animated values, gesture recognizers), and posts everything else
(container sizes, loaded image sizes, re-measure requests) to the core
without blocking. The core asks the platform to run that deferred work
through its `schedule_work` callback, on any thread but the UI thread.
Any other thread may therefore wait on the UI thread.

A commit follows these steps:

1. The reconciler builds wire operations and the backend serializes one
   envelope.
2. The commit worker calls `pn_core_commit`. The core parses the envelope,
   validates every operation against the compiled contracts and the
   current tree, applies it, lays out with Yoga, flattens layout-only
   views, diffs against the mounted tree, queues a binary mount
   transaction, asks the platform to drain the queue (`schedule_mount`),
   and returns the acknowledgement. It never waits for the mount.
3. Python publishes refs and frames, then runs layout and passive effects.
4. On its next turn, the UI thread takes each queued transaction with
   `pn_core_mount_next`, applies it, and reports `pn_core_mount_finished`.
   One transaction mounts at a time.

Effects therefore run after the core accepts and lays out a commit, not
after widgets exist. Commands and animation requests those effects issue
queue behind the commit's mount, so they always reach the widgets it
creates.

Native never waits for Python, and Python never answers a callback:
every message (`event`, `host`, `module`, `animation`, `layout`, and
`command`) is queued and delivered in order to the application loop.
Navigation back requests and recycled-row requests are asynchronous.
Messages sent before Python has started, such as a screen's `create`
while the interpreter is still booting, wait in the queue until Python
registers its callback. Platforms cache restoration state as Python
publishes it (`Host.set_state`) and hand it back in the next `create`
payload as `restored_state`. Viewport metrics (size, insets, keyboard
height, color scheme, scale, and font scale) travel on the `layout` and
`resume` host events. Adjacent continuous scroll and gesture samples can
be coalesced; discrete input preserves order. Animated event bindings
evaluate in the core before the event is queued to Python.

## Commits

A surface commit has this shape:

```json
{
  "version": 7,
  "application": "3f2a9c41-6c1e-4b8a-9d55-0d1f7e2b8c10",
  "surface": 1,
  "revision": 42,
  "ops": [
    ["c", 7, "Text", {"text": "Hi", "_pn_layout": true}],
    ["u", 3, {"background_color": "#fff"}, ["opacity"]],
    ["i", 3, 7, 0],
    ["d", 5]
  ],
  "layout": {"roots": [1], "width": 390, "height": 844, "selective": true}
}
```

| Operation | Fields |
| --- | --- |
| `c` | tag, component type, props |
| `u` | tag, changed props, removed property names; `null` remains a value |
| `i` | parent tag, child tag, insertion index (move-aware) |
| `d` | tag; children must already be destroyed |

Geometry never travels from Python: the core lays out every commit. The
optional `layout` object names the screen roots and the surface's
viewport, which Python's host learns from the platform's `layout` host
events. With `selective: true`, the acknowledgement carries frames only
for tags marked `_pn_layout` (views with a ref or an `on_layout`
callback); diagnostics and tests pass `false` to collect every changed
frame. `pn_core_layout` lays out against a new viewport without a commit.

Python builds the wire operations once and serializes the envelope once
per commit. The core validates the entire envelope before mutating
anything, in every build: the protocol version, the application identity,
the exact next revision (`1` for a new application), operation arity,
live tags, known components, every prop and removal against the compiled
contract tables, insertion bounds, cycles, destruction order, one dataset
patch per list per commit, and the layout request. It stages the checks
over the entries the commit touches, so validation costs time
proportional to the commit rather than to the mounted tree.

An accepted commit returns:

```json
{
  "ok": true, "application": "3f2a9c41-...", "surface": 1, "revision": 42,
  "metrics": {"validate_ns": 41000, "commit_ns": 230000, "operations": 6},
  "layout": {
    "application": "3f2a9c41-...", "surface": 1, "revision": 42,
    "frames": [[7, 16.0, 120.0, 60.0, 16.0]],
    "metrics": {"layout_ns": 95000, "visited": 4, "views": 12}
  }
}
```

`layout` is present when the envelope carried a layout request. Each frame
is `[tag, x, y, width, height]`, relative to the view's logical parent.
Python advances its bookkeeping only after the acknowledgement. A rejection
is `{"ok": false, "failed": false, "application", "surface", "revision",
"error", "op"}`, where `error` names the reason (for a prop, the component
and the property) and `op` is the index of the offending operation. It
leaves the core's tree as it was, so the previous revision stays current.

A mount that fails on the UI thread (a manager throws, or a decode fails)
marks the surface failed and sends a `host` message named
`surface_failed` with `{"surface", "error"}`. A failed surface rejects
further incremental commits. A new application identity and a complete
remount establish a clean surface; replaying a partial commit isn't a
recovery strategy. The current app host uses one surface.

The application loop keeps running while an acknowledgement is pending.
A reconciler queues state writes instead of rendering against an
uncommitted tree. Shared backend transactions serialize; preparation uses
the acknowledged revision when a transaction reaches the front. Refs,
effects, and native events wait for publication. Cancelling a caller's
wait doesn't cancel the commit.

### Incremental list packets

`VirtualList.dataset` contains `base`, `revision`, and `changes`. Each revision
advances by one. There may be one dataset patch per list per commit.

| Change | Payload |
| --- | --- |
| `reset` | array of `[key, item_revision, extent, sticky]` records |
| `i` | insertion index, row record |
| `u` | replacement row record with the same key |
| `d` | key to remove |
| `m` | key, final index |

A reset must be first. Keys are unique nonempty strings; extents are finite and
positive. The core keeps two copies of each dataset. The commit side
validates a patch against its base revision during `pn_core_commit`. The
mount side publishes it when the UI thread applies the `VirtualList`
create or update that carries it (`pn_core_list_apply`), and then answers
the native data source (`pn_core_list_count`, `pn_core_list_key`,
`pn_core_list_extent`, `pn_core_list_sticky`, `pn_core_list_row_revision`)
without the commit lock. Native window events include the active sticky
header. Application scroll events keep the `ScrollEvent` shape and are
emitted only when subscribed.

## Mount transactions

The core hands the UI thread a little-endian binary buffer:

| Part | Encoding |
| --- | --- |
| Header | `u32` magic `PNMT`, `u16` format (`1`), `u16` reserved, `i64` surface, `i64` revision, `i64` transaction id, `u32` op count |
| `0` reset | (destroy every view of the surface) |
| `1` create | `i64` tag, `str` component, `value` props |
| `2` update | `i64` tag, `u8` flags (`1`: recreate the widget), `value` changed props, `u32` count, `str` removed keys |
| `3` insert | `i64` parent, `i64` child, `u32` mounted index (move-aware) |
| `5` delete | `i64` tag (also detaches the view from its parent) |
| `6` frame | `i64` tag, `f64` x, y, width, height |
| `7` command | `i64` tag, `str` name, `value` arguments, `i64` call id |

A `str` is a `u32` byte length followed by UTF-8. A `value` is a `u8`
kind followed by its payload: `0` null, `1` false, `2` true, `3` an `i64`,
`4` an `f64`, `5` a `str`, `6` an array (`u32` count, then values), or
`7` an object (`u32` count, then `str` key and value pairs). The
bytes stay valid until `pn_core_mount_finished` for the same transaction.

Mount operations address mounted views only, so they differ from the
commit when the core flattens layout-only views (see
[Layout engine](layout.md#view-flattening)): children of a flattened view
are inserted into its nearest mounted ancestor, and frames are relative
to that ancestor. A commit that replaces the application identity starts
with a reset. Relayouts that native changes cause (a container resizes,
an image loads) produce frame-only transactions, and Python receives
the observed frames as a `layout` message.

Animation requests don't occupy ops: the core attaches them to a
transaction and runs them when the platform reports that transaction
mounted.
[`pythonnative.bridge.core.decode_transaction`][pythonnative.bridge.core.decode_transaction]
is the reference decoder, and the Swift, Kotlin, and JavaScript mounting
layers each implement the same format.

## Events and controlled input

The platform passes each view event through `pn_core_event(surface, tag,
name, arguments, edit_revision)`. The core stamps the mounted
application, surface, revision, and a sequence number, feeds any
animated event bindings, and queues an `event` message whose payload is
`{"application", "surface", "revision", "sequence", "args",
"edit_revision"}`. The backend rejects callbacks from earlier
applications, destroyed tags, future revisions, and replayed sequences.
Event payloads for `on_layout`, `on_scroll`, `on_selection_change`,
`on_key_press`, and `on_content_size_change` are reconstructed into the
frozen dataclasses in `pythonnative.components.events` before the
callback runs. Gesture callbacks arrive as `gesture:N` events, where `N`
indexes the view's `gestures` list.

Text changes also carry an edit revision. Python echoes the latest revision it
has processed with controlled `value` updates. A native input ignores older
echoes, preserves the selection where possible, and avoids replacing an active
IME composition. Typing therefore doesn't wait for Python rendering.

## Commands, animations, and layout reads

`pn_core_command(surface, tag, name, arguments, call_id)` validates the
arguments against the component's contract and queues the command behind
pending mounts. It returns `{"ok": true, "queued": true}` or an error: a
stale tag, invalid arguments, or "view #N isn't mounted (it only affects
layout)" for a flattened view, which no built-in command can address. The
UI thread runs the command and answers with a `command` message,
`{"call_id", "ok", "value"}`, which resolves the future the handle method
awaits. A ref's handle addresses a live tag; commands against a destroyed
tag raise an error.

`pn_core_animate(surface, tag, request)` validates an animation request
(`graph`, `start`, `cancel`, or `set`) and queues it the same way. The
core reports each driver's end as an `animation` message, `{"id",
"finished", "value"}`, and a driver started with `report: true` (a value
with Python listeners or no bound view) also sends `{"id", "value"}` every
frame.

`pn_core_measure(surface, tag)` reads the shadow tree, flattened views
included, and returns `{"frame": [x, y, w, h], "window": [x, y, w, h]}`.
`ViewHandle.measure_in_window` uses it.

## Native containers and lists

A native screen, portal, modal, or recycled row can be physically attached to a
platform container while remaining a child in the same Python component tree.
Context, error boundaries, suspense boundaries, and task ownership follow that
logical tree. In the core, those subtrees are detached roots that lay out
against the size their container reports through
`pn_core_report_container` (see [Layout engine](layout.md)).

Lists use stable keys and data revisions to validate row requests.
UIKit collection views and Android recycler views own physical cells; a bounded
window of ordinary keyed Python row components supplies their contents. Headless
tests simulate the same viewport and row requests. Dataset revisions change when
data or rendering inputs change; per-item revisions avoid reloading unchanged
cells. Dataset indexing is memoized separately from viewport changes. Stable
sequence identity, callbacks, and `data_revision` reuse that index even when a
parent rerenders. Replace an edited sequence or increment `data_revision` after
in-place edits. Native prefetch requests warm the bounded row window. Native
containers preserve the first visible key and its offset across dataset changes;
iOS also preserves it as measured row heights replace estimates. Global and
section headers don't change public item indices. Row instances can unmount
outside the window, so persistent item state belongs in app data.

## Modules, contracts, and animations

Module calls carry a call ID and arguments. A module can settle inline or return
`pending` and settle later. Cancellation removes the Python waiter and notifies
the native promise. Swift `PNPromise.onCancel` and Kotlin `Promise.onCancel`
allow implementations to release underlying work. The core validates module
arguments against the same contracts (`pn_core_validate_module`).

The SDK derives component and module contracts from Python dataclasses,
annotations, and protocols. `pn codegen` produces typed Swift and Kotlin
props, values, and module adapters, Python facades, and reference
documentation. The built-in contracts are derived once, at code
generation, into `pythonnative/sdk/_builtin_contracts.json`, which `import
pythonnative` reads instead of evaluating annotations. Plugin manifests can
name a generated contract file; builders merge it with the built-ins.
Before the first commit, Python passes the merged contract document to
`pn_core_load_contracts`, which compiles it into indexed tables; the core
rejects commits until contracts are loaded. Startup checks the protocol
version and the contract fingerprint compiled into the native library, and
a mismatch fails with "Native component contracts changed. Rebuild the app
with 'pn run'."

Animation graphs describe values, arithmetic, interpolation, colors, and
clamping. The core runs timing, spring, and decay drivers and evaluates
connected bindings. The platform's frame clock calls
`pn_core_animation_frame(timestamp_ms)`, which returns whether more frames
are needed, and then `pn_core_take_writes`, which returns the frame's
animated prop writes:

| Part | Encoding |
| --- | --- |
| Header | `u32` write count |
| Each write | `i64` tag, `str` prop, `value` |

The platform applies each write to the view's animated property. The core
asks for frames through the `request_frames` callback. Scroll and gesture
mappings feed graph values directly, so visual updates continue while the
Python application thread is busy.

## The browser preview

Under `pn preview` the renderer core runs in the page, compiled to
WebAssembly (`devserver/static/core/pn_core.wasm`), and
[`WebTransport`][pythonnative.bridge.web.WebTransport] forwards each call
Python makes into the core over the dev server's WebSocket.
`load_contracts`, `commit`, `layout`, `command`, `animate`, and `measure`
become requests that the page answers with the core's own JSON reply.
Envelopes travel as the text Python serialized, so the core parses each one
once. Everything the core emits, and every command result, comes back as a
callback, as on device. Python waits for each reply on the calling thread
(the commit worker for commits, the application loop for the rest); the
page never waits for Python.

The page is single-threaded, so the core's callbacks run where the
platforms use threads:

- `measure` and `baseline` run synchronously inside the commit or layout
  that asks. The page builds a prototype element from the props and
  measures it with the fonts and styles it renders with, which backs the
  `text` and `intrinsic` modes. A `native` leaf (a plugin's view) has no
  browser widget, so it measures as the labeled placeholder the page
  draws for it.
- `schedule_mount` drains the queue in a microtask, `schedule_work` runs
  `pn_core_work` on a timer, and `request_frames` starts a
  `requestAnimationFrame` loop that calls `pn_core_animation_frame`.
- Module calls drain pending mounts first, as on iOS and Android, so
  `Host.attach_root` always finds the root view Python committed.

Stack screens, presented modal sheets, and the portal layer report their
sizes with `pn_core_report_container`; a loaded image reports its size
with `pn_core_report_intrinsic`; and a text input asks to be measured
again with `pn_core_invalidate` as the user types. DOM pointer events go
to `pn_core_pointer`, and gesture deadlines poll on timers. A page that
reconnects starts with a fresh core, so Python compiles the contracts
into it again before its next commit.

## Profiling the boundary

`PN_PROFILE` traces rendering, serialization, and the core's work for each
commit. The acknowledgement's `validate_ns`, `commit_ns`, and `layout_ns`
appear as native samples on a separate trace track, placed at host receipt
without assuming synchronized clocks, beside the commit worker's
`commit_wait`. Work counters report commits, operations, bytes, layout
requests, queued commits, and views in the core's shadow tree. These
counters and host timings aren't device frame-rate claims.
