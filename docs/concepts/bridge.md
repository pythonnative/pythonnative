# The native bridge

PythonNative uses a versioned JSON protocol between a Python application thread
and native renderers. Python owns component state and logical relationships.
Native code owns widgets, measurement, input, scrolling, and animation frames.
The Swift runtime lives in `src/pythonnative/native/ios`; the Kotlin runtime lives
in `src/pythonnative/native/android`. App templates stage and embed those libraries.

## Application and UI threads

The application has an ordinary asyncio loop on its own thread. A commit's
blocking transport call runs on a worker. Native JSON decoding
happens there before operations are queued to the platform UI thread. Structural
preflight, widget mutation, and native measurement retain UI-thread ownership.
On iOS, the ctypes transport releases the GIL during this crossing. Native input
is queued back to Python rather than waiting for a Python handler on the UI thread.

A callback must never depend on a synchronous Python answer. Navigation back
requests and recycled-row requests are asynchronous. Platforms cache restoration
state as Python publishes it, so the `save_state` and `restore_state` lifecycle
callbacks are acknowledged without calling into Python. Viewport metrics
(size, insets, keyboard height, color scheme, scale, and font scale) travel on
the `layout` and `resume` host events.
Adjacent continuous scroll and gesture samples can be coalesced. Discrete input
preserves order. Animation input bindings evaluate before the sample is queued.

## Commits

A surface commit has this shape:

```json
{
  "version": 4,
  "application": "unique-application-id",
  "surface": 1,
  "revision": 1,
  "ops": [
    ["c", 1, "View", {"flex": 1}],
    ["c", 2, "Text", {"text": "Hello"}],
    ["i", 1, 2, 0]
  ]
}
```

| Operation | Fields |
| --- | --- |
| `c` | tag, component type, props |
| `u` | tag, changed props, removed property names; `null` remains a value |
| `i` | parent tag, child tag, insertion index |
| `d` | tag; children must already be destroyed |
| `f` | tag, x, y, width, height |

Python builds the wire operations once, validates them once against the
generated contract, and serializes the envelope once per commit; there is no
encode-decode-patch round trip. The renderer then validates the entire
operation sequence before mutation: operation arity, live tags, insertion
bounds, cycles, typed values, and finite geometry.
An accepted commit returns `ok`, `application`, `surface`, and the exact
`revision`, plus optional native timing metrics. Python advances its bookkeeping
only after that acknowledgment. A rejection with `failed: false` reports
validation failure before mutation and preserves the previous revision.
A failed surface rejects further incremental updates. A new application identity
and a complete remount establish a clean surface; replaying a partial commit
isn't a recovery strategy. The current app host uses one surface.

The application loop keeps running while acknowledgement is pending. A reconciler
queues state writes instead of rendering against an uncommitted tree. Shared
backend transactions serialize; preparation uses the acknowledged revision when
a transaction reaches the front. Refs, effects, and native events wait for
publication. Cancelling a caller's wait doesn't cancel native mounting.

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
positive. Validation stages edits before publishing them. Updating metadata
preserves the order index; structural edits rebuild indexes as needed. Native
window events include the active sticky header. Application scroll events keep
the `ScrollEvent` shape and are emitted only when subscribed.

## Events and controlled input

Events carry `application`, `surface`, `revision`, `sequence`, and an `args` list.
The backend rejects callbacks from earlier applications, destroyed tags, future
revisions, and replayed sequences. Event payloads for `on_layout`, `on_scroll`,
`on_selection_change`, `on_key_press`, and `on_content_size_change` are
reconstructed into the frozen dataclasses in `pythonnative.components.events`
before the callback runs. A ref's handle addresses a live native tag; commands
against a destroyed tag raise an error.

Text changes also carry an edit revision. Python echoes the latest revision it
has processed with controlled `value` updates. A native input ignores older
echoes, preserves the selection where possible, and avoids replacing an active
IME composition. Typing therefore doesn't wait for Python rendering.

## Layout and native containers

Every renderer uses Yoga 3.2.1. The C++ source is vendored with its license and
provenance. Python tests build a host binding, iOS and Android compile the same
core, and the browser preview uses the corresponding Yoga WebAssembly package.

The application sends styles as props. Native leaf managers measure text,
controls, and images next to their widgets. When the viewport is known, a commit
includes a `layout` object with `roots`, `width`, `height`, and `selective: true`.
Its acknowledgment includes changed frames for `_pn_layout` observers (refs or
`on_layout`), so mutation and required layout share one bridge
crossing. `Layout.compute` remains available for viewport changes without
mutations. Both return frames with `application`, `surface`, and `revision`.
Geometry from another surface or revision is ignored. Drawing-only prop updates
skip a separate request. Changed styles update existing Yoga nodes; removal
restores the property default or surviving shorthand. Diagnostic raw layout
requests may omit `selective` to collect all changed frames. Yoga calculations
reuse unchanged constraints, and
frame collection visits only subtrees with new layout. Python doesn't make one
measurement RPC per leaf.

Commit and required layout acknowledgments precede ref and effect publication.
Native navigation animations and later platform layout changes may continue after
that boundary; their geometry returns through the same identified layout channel.

A native screen, portal, modal, or recycled row can be physically attached to a
platform container while remaining a child in the same Python component tree.
Context, error boundaries, suspense boundaries, and task ownership follow that
logical tree. Lists use stable keys and data revisions to validate row requests.
UIKit collection views and Android recycler views own physical cells; a bounded
window of ordinary keyed Python row components supplies their contents. Headless
tests simulate the same viewport and row requests. Dataset revisions change when
data or rendering inputs change; per-item revisions avoid reloading unchanged
cells. Dataset indexing is memoized separately from viewport changes. Stable
sequence identity, callbacks, and `data_revision` reuse that index even when a
parent rerenders. Replace an edited sequence or increment `data_revision` after
in-place edits. Native prefetch requests warm the bounded row window. Native
containers preserve the first visible key and its offset across dataset changes;
iOS also preserves it as measured row heights replace estimates. Global and section headers don't change public item indices. Row instances
can unmount outside the window, so persistent item state belongs in app data.

## Modules, contracts, and animations

Module calls carry a call ID and arguments. A module can settle inline or return
`pending` and settle later. Cancellation removes the Python waiter and notifies
the native promise. Swift `PNPromise.onCancel` and Kotlin `Promise.onCancel`
allow implementations to release underlying work.

The SDK derives component and module contracts from Python dataclasses,
annotations, and protocols. `pn codegen` produces Swift, Kotlin, Python, browser
metadata, and reference documentation. Plugin manifests can name a generated
contract file; builders merge it into both the native library and embedded Python.
Startup checks the protocol, Yoga version, and contract fingerprint.

Animation graphs describe values, arithmetic, interpolation, colors, and
clamping. Native timing, spring, and decay drivers evaluate connected bindings
on the UI thread. Scroll and gesture mappings feed graph values directly, so
visual updates can continue while the Python application thread is busy.

## Profiling the boundary

`PN_PROFILE` traces separate rendering, validation, transport, native mutation,
and layout. Native duration samples appear on a separate trace track, placed at
host receipt without assuming synchronized clocks. Work counters report copied
validation records, operations, native views visited, and changed frames. A
one-property regression test uses 10,000 records to check work growth directly.
These counters and host timings aren't device frame-rate claims.
