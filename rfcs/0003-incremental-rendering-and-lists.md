# RFC 0003: Incremental rendering and lists

- Status: Implemented
- Author(s): Owen Carey, with Codex
- Created: 2026-09-22
- Implemented in: this change
- Supersedes / Superseded by: replaces the list transport and Python sticky headers in RFC 0002

## Summary

Make work proportional to the change, keep native mounting from blocking the
application loop, and make renderer failures diagnosable without rendering
another component tree. This change spans generated contracts, commit
ownership, Yoga updates, virtualized lists, diagnostics, and performance
conformance tests. Function components, hooks, native widgets, and standard
asyncio remain the application model.

## Motivation

A one-item edit currently sends every item revision, native props are validated
and decoded repeatedly, Yoga updates reconstruct complete styles, and native
commits synchronously hold the Python application thread. Sticky section
headers depend on Python scroll callbacks. The development error screen depends
on the renderer that may have failed. These costs and failure modes grow with
real applications even when only a small visible window is mounted.

## Reference behavior

React Native separates render, commit, and mount, prepares work away from the
UI thread where possible, and gives native scrolling ownership of sticky
headers. PythonNative follows that division while retaining ordinary Python
functions and asyncio tasks. It does not pretend that arbitrary synchronous
Python code can be interrupted or moved between threads safely.

Reference: https://reactnative.dev/architecture/render-pipeline

## Design

### Commit ownership and contracts

Protocol version 4 requires rebuilt clients and regenerated extension contracts.
A bridge backend has at most one native commit in flight, including when
multiple screen reconcilers share it. Acknowledgement publishes the committed tag
index and enables refs and effects. State updates during a commit accumulate
for a subsequent render. Rejected or unknown outcomes retain the existing
explicit rejection and poisoned-surface distinction. Events that arrive before
their commit acknowledgement are delivered after publication in order.

Generate executable native validation and metadata instead of interpreting the
component schema JSON at runtime. Generated prop wrappers decode fields once.
Keep schema JSON for tooling, browser conformance, and extension generation.
Instrument preparation, queueing, mutation, layout, acknowledgement, and
component rendering separately. Avoid copying the whole type registry to
encode a small transaction.

### Layout

Apply changed Yoga properties directly, including defaults for removed props.
Keep paint-only changes out of layout invalidation. Preserve native measurement
thread requirements. Return geometry only when Python needs it, and batch row
measurement invalidation within a native layout pass.

### Lists

Replace the whole-array update protocol with a revisioned dataset containing
keyed rows and insert, remove, move, and update patches. Initial mount carries
the initial rows; subsequent commits carry only changes. Native and browser
renderers validate base revisions and keys before changing their data stores.

Expose a generic `ListData[T]` with explicit batched mutations and subscriptions.
It retains stable keys and a bounded mutation journal. `FlatList` accepts either
this source or an ordinary `Sequence[T]`. Sequence replacement requires a scan;
an incremental source provides changed keys directly. Both feed the same list
protocol and renderer. Render only the requested window. Offscreen rows unmount,
so persistent item state belongs in the application data model.

Expose frozen `Section[T]` and `ViewableItem[T]` records. Section keys are
explicit, independent of their position. Native layouts own pinned section
headers, and Python keeps the active header in its mounted window. Native
window events fire when the required range changes. App scroll callbacks are
wired only when subscribed.

```python
messages = pn.ListData(initial_messages, key=lambda message: message.id)
with messages.batch():
    messages.insert(0, new_message)
    messages.update(existing_message.id, replacement)

pn.FlatList(data=messages, render_item=lambda message, index: Message(message))
pn.SectionList(sections=[pn.Section(key="recent", title="Recent", data=recent)])
```

### Diagnostics and tooling

Show development errors through a host-owned native overlay, independent of the
surface and reconciler. Include the traceback and reload/dismiss actions. The
browser uses an independent DOM overlay. Extend profiling with bounded phase
and work counters. Add a repeatable benchmark command with JSON output and
deterministic work assertions; keep hardware-dependent timing out of ordinary
CI pass/fail thresholds. Extend the reference app and conformance tests to
exercise live list edits, scrolling, pending commits, failure, and recovery.

## Removals

- Whole-array list update props and their native snapshot replacement path.
- Python-rendered sticky section header overlays and position-based section keys.
- Interpreted native component schema validation and repeated prop decoding.
- Full Yoga style reconstruction for incremental prop changes.
- The renderer-dependent development error tree.
- The preceding wire version and obsolete tests and documentation.

No compatibility shims or dual implementations are retained. Ordinary sequences
remain supported as an intentional, convenient public API.

## Alternatives considered

- A binary bridge first: reduces encoding overhead without fixing oversized
  transactions or repeated work. Retain JSON and measure the resulting pipeline.
- A signals rewrite: changes application semantics without addressing native
  mounting and list transport. Keep hooks and explicit dependencies.
- Python UI-thread worklets: arbitrary Python execution cannot guarantee a
  bounded frame budget. Keep native animation expressions and scrolling.
- Rendering ahead of unacknowledged commits: complicates refs, effects, and
  recovery. Start with one commit per surface and coalesce pending state.

## Non-goals

Layout-only view flattening, a full visual inspector, build configuration
plugins, a package ecosystem overhaul, additional device APIs, and desktop
production targets are subsequent projects. They aren't dependencies of this
rendering change.

## Testing and rollout

Use Python lifecycle and failure tests, shared protocol traces, randomized list
operations, Swift XCTest, Android JUnit/Robolectric, and the browser renderer
suite. Exercise available local simulators and emulators with the list and
reference app flows. Record deterministic work counts and comparative local
benchmarks; identify simulator measurements separately from physical hardware.
Update examples, docs, generated artifacts, and E2E coverage together.

## Implementation decisions and limits

- Native transports run their blocking crossing on an executor. Python tree
  preparation and publication stay on the application thread; native structural
  preflight, widget mutation, and measurement stay on the UI thread. This isn't
  interruptible rendering or automatic parallel execution of Python components.
- `ListData` has a 1,024-change journal by default. A one-item update avoids
  copying order or scanning metadata. Structural edits still shift indexed
  arrays. Expired history, changed render inputs or decorations, and switching
  data adapters require a reset. Grids and custom height functions use the
  sequence adapter. Source identity participates in row memoization, and events
  from a superseded source revision can't read its new order through old indices.
- Native metadata applies one validated dataset patch per list per commit.
  Android issues individual insertion, removal, and move notifications. iOS
  uses `reloadData()` for structural patches to avoid UIKit's differing pre- and
  post-update index rules; logical keyed row roots and their hook state survive.
  Item-revision-only updates don't invalidate the entire collection layout.
- The browser maintains prefix sums for indexed offset lookup. UIKit and
  RecyclerView own mobile geometry and recycling. Sticky headers move natively;
  Python retains the active header alongside the bounded visible window.
- The Inbox reference app uses `ListData` for its unfiltered collection.
  Filtering and persistence still create application-level snapshots. This RFC
  doesn't make those operations constant-time.
- The Swift value encoder writes Codable values directly into bridge values.
  This also avoids an iOS 17 JSONEncoder issue that truncated strings containing
  NUL. Shared native fixtures verify the preserved string and its round trip.

## Recorded validation

The work benchmark runs with:

```bash
python scripts/benchmark-rendering.py --rows 100000 --edits 10
```

[Recorded JSON](benchmarks/0003-list-work.json) contains the environment, counters,
and phase summaries. On the local Intel Mac, the ordinary sequence adapter's
median edit took 943.8 ms; `ListData` took 12.9 ms. Across ten edits, the sequence
adapter scanned 1,000,000 metadata rows; `ListData` scanned none and validated ten
changed records. The largest incremental dataset packet was 63 bytes, and both
paths retained 71 mounted views.

These compare two supported APIs in this implementation, not historical versions.
They include profiling overhead and concurrent development-machine load. They
aren't device frame-rate measurements. Tests enforce deterministic work bounds,
not timing thresholds.

The iOS simulator exercised the 10,000-row live-edit demo, FlatList's vertical,
horizontal, and inverted modes, SectionList, and Inbox search, editing, saving,
and persistence after relaunch. Swift XCTest passed 106 tests. Android assembled
successfully and passed 104 JUnit/Robolectric tests. The local Android emulator
crashed before connecting to adb, including a clean boot attempt, so Android
interactive acceptance remains unverified on this machine. Browser conformance,
1,857 passing Python tests (14 skipped), generated-code drift, typing, lint, package
builds, and the strict documentation build supplement the native checks.
