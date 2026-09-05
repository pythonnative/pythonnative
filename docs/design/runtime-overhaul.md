# Runtime overhaul

PythonNative now uses one logical application tree and a standard asyncio loop
on a dedicated application thread. Native runtimes own widgets, measurement,
input, scrolling, and animation frames. This is a breaking pre-1.0 change:
rebuild application clients together with the Python package.

## Implemented architecture

| Area | Result |
| --- | --- |
| Async runtime | Standard asyncio tasks, sockets, task groups, timeouts, component task scopes, async event handlers, and native cancellation. |
| State and data | Immutable snapshot comparison, reliable resubscription, bounded shared query caching with explicit keys, and cancellation of abandoned requests. Implicit queries belong to their hook instance. |
| Logical ownership | Screens, overlays, and bounded keyed list rows share providers, boundaries, and component task ownership. Native containers own presentation. |
| Bridge | Protocol 2 validates a complete revisioned commit before mutation. Acknowledgements, event sequences, text edit revisions, and live refs prevent stale updates. |
| Layout | Pinned Yoga 3.2.1 runs in the host binding and native libraries. Native leaf measurement produces batched changed frames. The browser uses Yoga WebAssembly. |
| Native lists | UIKit collection views and Android recycler views own keyed cells, variable row measurements, both scroll axes, and scrolling. Python mounts a bounded window of ordinary row components. |
| Animation | Serialized expression graphs, timing, spring, decay, derived values, color interpolation, and native scroll and gesture bindings. Binding replacement preserves running graph ownership. |
| SDK | Dataclass and protocol contracts generate typed props, module adapters, validators, Python facades, and schema documentation. Builds merge plugin contracts and verify the startup fingerprint. |
| Builds | Extracted native libraries, target wheel locks with hashes, archive-based plugin discovery, managed native resources, and clean source and wheel distributions. |
| Development | Conservative hook-signature refresh, component remounts for incompatible changes, service-change remounts, phase tracing, and updated architecture documentation. |
| Reference app | An offline inbox with 2,000 variable-height records, deferred search, shared state, editing, optimistic persistence and rollback, native navigation, and a custom native extension. |

The former guest event loop, coroutine stepper, hand-written Python flex layout,
row-host pool, and imperative per-screen host navigation have been removed.
There are no compatibility adapters for those paths.

## Working with the new runtime

Read [the architecture](../concepts/architecture.md),
[bridge contract](../concepts/bridge.md), and
[generated native contracts guide](../guides/native-contracts.md).
`examples/inbox/README.md` describes running the reference app and its mobile
acceptance flow.

For application-thread timings, set `PN_PROFILE` to a writable trace path before
starting the process. Collection is bounded to the latest 10,000 events and
exports at normal process exit. For explicit capture, use
`pythonnative.profiling.Profiler` as a context manager and call `export(path)`.
Traces include component rendering, layout and commit phases, rendered-component
counts, and bridge operation and byte counts. Native frame profiling still uses
Instruments or Android's platform tools.

## Validation and practical limits

Validation covers the Python suite, generated-file drift, static typing,
formatting, strict documentation builds, native unit tests and compilation,
installed-wheel layout, and real simulator and emulator flows. The reference
flow exercises search, native text editing, save, navigation, and process restart
with persisted data. A separate embedded-runtime flow exercises sockets,
`TaskGroup`, timeout, and cancellation on both platforms.

The application host currently uses one surface. A failed commit requires a
complete surface reset and remount. Reconciliation reduces work at dirty
component roots but doesn't time-slice arbitrary Python render functions.
Native frame drivers continue independently; CPU-heavy Python work should yield
cooperatively or run outside the application thread.

Wheel locks guarantee the selected artifacts and their hashes. Cross-platform
dependency markers and unavailable mobile system APIs still require validation
on each embedded runtime. Simulator builds don't validate device signing or
store submission. Native transition polish, exhaustive accessibility audits,
and performance budgets on physical devices remain release work.


## Local validation results

The implementation was checked with Python 3.13, an iOS 18.6 simulator, and an
Android API 31 emulator:

- Python: 1,222 tests passed; 14 opt-in package-matrix tests were skipped.
- Native libraries: 40 iOS tests and 34 Android tests passed.
- Mobile flows: standard asyncio, animations, stack and other navigation,
  vertical and horizontal list recycling, and the inbox acceptance workflow.
- Browser: inbox search, navigation, text editing, save, and reload persistence.
- Builds: Android release library, APK, and app bundle; iOS simulator Release
  configuration; source distribution and wheel, including isolated installation.
- Tooling: Ruff, Black, MyPy, strict MkDocs, generated-contract drift checks,
  E2E export coverage, and installation of locked iOS Simulator wheels.

The complete 85-flow mobile suite wasn't run in this local pass. The CI workflow
retains the full suite; the local flows focus on the changed runtime boundaries.
