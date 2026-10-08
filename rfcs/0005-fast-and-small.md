# RFC 0005: Fast and small

- Status: Implemented
- Author(s): Owen Carey, with Claude (Claude Code)
- Created: 2026-10-07
- Implemented in: this pull request
- Supersedes / Superseded by: none

## Summary

PythonNative has React Native's feature surface, but a new app launches
slowly, ships large, and re-renders with avoidable overhead. A freshly
scaffolded app takes four seconds to show its first screen on a fast Mac's
simulator and ships a 92 MB bundle, a third of which is CPython's own test
suite. This RFC makes the runtime fast and small by default: bytecode
everywhere, a trimmed embedded standard library, startup that doesn't
rebuild contracts or parse source, Python started off the main thread,
render bookkeeping proportional to what changed, one validation per
commit, and native commits that don't copy the whole tree. It sets budgets,
records benchmarks, enforces deterministic proxies for them in CI, fixes
correctness bugs found on the same paths, and deletes the dead code those
paths carried.

## Motivation

The first thing a skeptic says about Python on a phone is that it's slow
and heavy. Today a hello world confirms it. Measured on 2026-10-07 with the
`pn init` template (`HomeScreen`, `DetailScreen`, one stack navigator) on
an iPhone 17 Pro simulator, Xcode 26.3, Python 3.13.15:

| Measurement | Result |
| --- | --- |
| First `pn run ios` (cold) | 6.7 minutes |
| Debug `.app` size | 92 MB: 49 MB `python/`, 34 MB of it `lib/python3.13/test/` |
| CPython test extension frameworks in the bundle | 15 (`_testcapi`, `xxlimited`, and so on), each signed |
| Cold launch to first content | 4.1 to 4.5 s |
| Process start to "Embedded Python initialized" | 2.35 s, before any application code |
| `import pythonnative` on the host, warm bytecode | 0.6 s |
| Re-render of 300 small components (headless) | 132 ms |

The causes are specific:

- **No bytecode on iOS.** The embedded standard library ships without
  `.pyc` files, debug bundles don't compile `pythonnative` or the app, and
  `PythonRuntime.swift` sets `write_bytecode = 0`. Every launch compiles
  every imported module from source. Release builds compile the app and
  packages only when the host interpreter matches `app.python_version`,
  and they silently skip it otherwise.
- **No standard library trimming.** BeeWare's `install_python` copies the
  whole `lib/python3.13`, including `test/`, `idlelib`, `tkinter`,
  `ensurepip`, `turtledemo`, and `pydoc_data`, plus CPython's test-only
  extension modules, which `install_dylib` turns into signed frameworks.
- **Contracts rebuilt at import.** `components/__init__.py` calls
  `sdk.builtins.install()`, which derives every native component schema
  from `typing.get_type_hints` and dataclasses. Under a profiler, this is
  1.2 s of a 2.5 s import. `bootstrap.start()` then loads the same
  contracts again from `_native_contracts.json` and compares each one by
  serializing it, and the handshake hashes the whole manifest.
- **Source parsing at import.** Every `Component` computes its Fast Refresh
  hook signature with `inspect.getsource` and `ast.parse` when it's
  defined, including the framework's own built-in components: 0.5 s
  under a profiler.
- **Python on the main thread.** iOS initializes the interpreter and runs
  the bootstrap synchronously in `viewDidLoad`. Android does the same,
  plus the entry module import, in `MainActivity.onCreate`, which risks an
  "application not responding" error on slower devices.
- **Render bookkeeping.** The rollback journal records every one of
  `HookState`'s 30 slots for every rendered component, copying their
  lists and dictionaries, and records `VNode` attribute writes one field at
  a time through a context variable lookup. Together that's about 40 percent
  of re-render time. `diagnostics.is_dev()` reads `os.environ` on each call
  (7 percent). `Component.__call__` runs `inspect.Signature.bind` and
  `apply_defaults` for every element, and `Component.render` builds
  `BoundArguments` again.
- **Double validation.** Python validates every commit's structure and
  every prop against the schema, in release builds too, and the native
  runtime validates the same commit again with generated validators.
- **Native commits copy the tree.** `PNCommit.apply` and Kotlin's
  `CommitState` copy the live tag set and the parent, type, and child-count
  maps for each commit, so a one-prop update costs time proportional to
  the number of mounted views. `pn_bridge_apply` decodes the commit's
  JSON reply and encodes it again to attach metrics.

Some first-run costs compound this. The iOS runtime download (31 MB) is
cached per project under `build/`, so every new project and every
`pn clean` downloads it again, with no timeout or progress output.

## Reference behavior

React Native ships precompiled Hermes bytecode in release builds, lazily
initializes modules ("inline requires"), keeps prop validation and other
checks in development only, and keeps the native splash screen up until
the first frame is ready. Its new renderer commits a shadow tree that's
cloned only along changed paths.

Python has equivalents for most of these. `compileall` with
`--invalidation-mode unchecked-hash` produces bytecode that's valid
without checking source timestamps, which suits an immutable signed
bundle. Sourceless `.pyc` files placed where the `.py` file was load
without sources. PEP 562's module `__getattr__` defers imports without
changing the public API. BeeWare's Briefcase and Chaquopy both strip the
standard library's tests from app bundles, and Chaquopy already compiles
the Android standard library.

PythonNative follows these practices. It deliberately differs in one
place: development builds also ship bytecode for the standard library and
the framework, because the dev loop is where launch time is felt most
often, and Python, unlike JavaScript, has a compiler that can run at build
time without changing semantics.

## Design

### Budgets

The implementation was held to these targets, measured as in the
Motivation. Results are recorded in
[`rfcs/benchmarks/0005-fast-and-small.json`](benchmarks/0005-fast-and-small.json)
and discussed under "Recorded validation."

| Measurement | Before | Target | Result |
| --- | --- | --- | --- |
| `import pythonnative` (host, warm bytecode) | 0.6 s | 0.25 s or less | 0.20 to 0.33 s (met in quiet conditions) |
| Debug `.app` size, `pn init` template | 92 MB | 55 MB or less | 62 MB (not met; see below) |
| Cold launch to first content, iOS simulator, debug | 4.1 to 4.5 s | 1.5 s or less | 2.0 to 3.4 s under heavy host load (not met as measured) |
| Python work on the platform main thread at launch | All of it | None | None |
| Re-render of 300 small components (headless) | 132 ms | 66 ms or less | 1.3 to 1.7 times faster than `main`, interleaved (not met) |
| Native commit validation, one-prop update | O(mounted views) | O(changed ops) | O(changed ops) |

CI doesn't enforce wall-clock thresholds, which vary with hardware (RFC
0003 made the same call). Instead, tests enforce deterministic proxies:

- Importing `pythonnative` calls none of `inspect.getsource`,
  `typing.get_type_hints`, and `ast.parse`, doesn't import
  `sdk.builtins` or `refresh`, leaves the lazy subsystems unloaded, and
  loads at most 90 `pythonnative` modules (73 today).
- A render pass captures each object at most once.
- Element construction and rendering never call `inspect.Signature.bind`.
- Release-mode commits skip Python prop validation.
- A prepared iOS runtime contains none of the pruned paths, and staged
  code carries bytecode.
- A release build fails when bytecode can't be produced.

These live in `tests/test_performance_budgets.py`, `tests/project/`, and
the codegen drift tests.

`scripts/benchmark-runtime.py` reports the timing measurements as JSON so
they can be compared across changes.

### Startup

**Generated built-in contracts.** `scripts/generate-native-contracts.py`
derives the built-in manifest (`sdk.builtins.write_builtin_contracts`) and
writes it to `src/pythonnative/sdk/_builtin_contracts.json`, alongside the
Swift and Kotlin sources it already generates, with the manifest's
fingerprint inside. Identical field schemas are stored once and referenced
by index, which shrinks the document from 1.3 MB to 163 KB and makes the
loaded components share their field dictionaries.
`schema.load_builtin_contracts()` registers it at import instead of
deriving schemas from type hints. The derivation in `sdk/builtins.py`
remains the source of truth for code generation and joins
`DEV_ONLY_PATHS`; a development checkout whose generated document predates
a protocol change derives the contracts instead. `validate_props` moves to
`sdk/schema.py`. Drift tests compare the document with a fresh derivation.

**Plugin contracts load once.** The builder writes only plugin contracts,
plus the fingerprint of everything the native library was generated
from, to `_native_contracts.json`. `load_manifest` skips a contract
that's already registered. `schema.fingerprint()` is cached until the set
of registered contracts changes, and both loaders seed the cache, so the
startup handshake never hashes the manifest.

**Cheaper Fast Refresh signatures.** Components defined inside the
`pythonnative` package never compute a hook signature (and no longer
import `pythonnative.refresh`). Application components still compute one
when they're defined, because the preview's editor may already have
replaced the source by the time a reload runs, but `pythonnative.refresh`
now parses each source file once with the C parser and caches the tree,
instead of tokenizing every function with `inspect.getsource`. Release
bundles still omit `refresh.py`.

**Lazy subsystems.** `import pythonnative` no longer imports animation,
gestures, icons, navigation, or HTTP (`fetch`, `Response`, `HTTPError`)
until their first use, through a module `__getattr__` (PEP 562). Names,
`__all__`, and documentation don't change, and `if TYPE_CHECKING:` imports
keep the static types exact. SVG, the store, and the device modules stay
eager: the built-in components and the screen host import them anyway.

**Bytecode everywhere on iOS.** The builder prepares each runtime once, in
the shared cache (below): it removes the pruned paths and compiles the
standard library with `compileall` in `unchecked-hash` mode. The builder
also compiles `pythonnative`, the installed packages, and the app in
every build (`project/bytecode.py`). Debug builds keep the `.py` sources
beside the bytecode for tracebacks and Fast Refresh. Release builds
replace each module with sourceless bytecode, which the template's
`PNFinalizePython.sh` also applies to the standard library after
`install_python`. Compiled code records bundle-relative file names
(`app/main.py`), never paths on the build machine. The compiling
interpreter must match `app.python_version`'s minor version (the one
running `pn`, or `pythonX.Y` on `PATH`): its absence is a warning in debug
builds and a `BuildError` in release builds, replacing the silent skip.
Debug builds set `write_bytecode = 1`, so the dev client's overlay of
changed sources is cached between launches. Release builds keep it at 0.

**Python off the main thread.**

- `pythonnative.bootstrap.start(dev, strict, entry)` imports the entry
  module last, so the first screen only renders.
- iOS: `AppDelegate` starts the interpreter and the bootstrap on a
  background queue at launch. `PythonRuntime.whenReady(_:)` runs a
  completion on the main queue. `PNViewController.prepareRuntime` takes a
  completion: until Python is ready the controller shows the app's launch
  storyboard as a placeholder, then sends `create` and replays the
  lifecycle events UIKit already delivered. Nothing on the main thread
  waits for Python, so the bridge's main-thread hops can't deadlock. A
  debug build logs `[PN] First screen attached N ms after process start`.
- Android: `MainActivity` sets its content view immediately (so fragment
  restoration works as before), holds the system splash screen with an
  `OnPreDrawListener` until Python is ready, and runs `Python.start`, the
  bootstrap, and the entry import on a background thread before
  installing the `PythonHost`. No new dependency is needed.
- Both bridges queue native-to-Python messages until Python registers its
  callback, instead of dropping them. A screen's `create`, sent while the
  interpreter is still booting, simply waits, and so do early events such
  as `AppState` changes.

### Rendering

**Journal snapshots per object.** A render pass stamps each `VNode` and
`HookState` with its journal's identity the first time it changes and
records a single undo entry that restores all of its journaled fields at
once (`Journal.snapshot`, which reads the fields with one compiled
reader). Later writes in the same pass compare one integer. Objects
created during the pass are stamped at construction and never captured,
and accepting a journal gives it a new identity so accepted state can be
captured again. `HookState._JOURNALED` omits the hook cursors, the
dev-mode hook log, and the effect-queue marks, which `begin_render`
resets. The context variable lookup on every `VNode.__setattr__` goes
away.

**Element construction without `Signature.bind`.** `Component` compiles a
call plan from its signature once: positional parameter names, the
`*children` parameter, keyword-only names, required names, and defaults.
`__call__` binds positional arguments and keywords against the plan and
raises the same `TypeError` messages as `Signature.bind`. Signatures with
positional-only parameters or `**kwargs` keep the general path.
`Component.render` calls the function directly from stored props and
children.

**Development checks cost nothing in release.** `diagnostics.is_dev()`
reads a module-level flag that `set_dev_mode` and the environment set at
import (`reset_dev_mode` rereads the environment). `@profiled` phases
skip their context manager entirely when no profiler is active. `CommitState` keeps validating commit structure (revisions, tags,
parents, and list datasets), which list publication needs, but validates
props against schemas only in development. The native validators stay
authoritative in every build.

**Native commits proportional to the change.** `PNCommit.apply` (Swift)
and `CommitState` (Kotlin) apply each validated operation to the live
maps immediately and record its inverse in an undo log. A rejected commit
replays the log in reverse. `PNCommit.apply` returns its reply as a
dictionary, and Kotlin's as a `JSONObject`, so the bridges add metrics and
encode once. The browser preview's validator already copied only the
records a commit touched and stays as it is.

**Lists.** iOS's list layout invalidates on bounds changes only when the
list pins section headers.

### Bundle size

The builder removes these from the staged iOS runtime: `test/`, `idlelib/`,
`tkinter/`, `turtledemo/`, `turtle.py`, `ensurepip/`, `venv/`,
`__phello__/`, `__hello__.py`, `antigravity.py`, `this.py`, and the test
extension modules (`_testcapi`,
`_testinternalcapi`, `_testlimitedcapi`, `_testbuffer`, `_testclinic`,
`_testclinic_limited`, `_testexternalinspection`, `_testimportmultiple`,
`_testmultiphase`, `_testsinglephase`, `_xxtestfuzz`, `_ctypes_test`,
`xxlimited`, `xxlimited_35`, `xxsubtype`). `pydoc`, `pydoc_data`,
`_pyrepl`, and `unittest` stay, because applications, libraries, `pydoc`,
and `site` import them at runtime.

The app templates drop the IDE's stub test targets (`ios_templateTests`,
`ios_templateUITests`, `ExampleUnitTest.kt`, `ExampleInstrumentedTest.kt`,
and their test dependencies), which only add build time. `pn build` prints
each artifact's size and the Python runtime's share of it
(`project.artifacts.size_report`).

### Build speed

Runtime downloads move to a shared cache: `~/Library/Caches/pythonnative`
on macOS, `$XDG_CACHE_HOME/pythonnative` (or `~/.cache/pythonnative`)
elsewhere, and `PN_CACHE_DIR` when it's set. Each runtime is downloaded
once per machine with a timeout and progress output, then verified,
extracted, pruned, and compiled once. A marker file records the
preparation version. `pn clean` no longer forces a new download.

The Android builder passes Gradle the SDK that `pn doctor` detects
(`ANDROID_HOME`, `ANDROID_SDK_ROOT`, or the platform's default location,
shared as `project.android.sdk_dir`). Previously `pn doctor` reported the
SDK as found while `pn run android` failed with "SDK location not found"
unless `ANDROID_HOME` was exported.

### Correctness fixes on these paths

- **Duplicate keys.** `_reconcile_child_list` matches each old keyed
  child at most once. A later duplicate is created fresh, and every
  unmatched old child is destroyed, in development and release alike.
  Development mode still warns.
- **`use_layout_effect`'s contract.** Layout effects run after native
  mounts the commit and before passive effects. State they set commits
  in a following transaction. The docstring and the hooks guide say this,
  instead of promising that they run before the user sees the frame.
- **`use_query` with an explicit `key=`.** The subscription calls the
  latest fetcher through a ref, so a fetcher that reads changed props
  under an unchanged key isn't stale.
- **Event coalescing.** `bridge._continuous` is guarded by a lock, since
  native callback threads and the application loop both change it.
- **Android permissions.** The runtime library and template manifests no
  longer request `POST_NOTIFICATIONS` for every app; it comes from
  `[permissions]` (`notifications` or `remote_notifications`).
  `VIBRATE` stays: it's an install-time permission the built-in `Haptics`
  module needs, and dropping it would crash apps that use haptics.
- **Android state restoration.** `PNScreenFragment` sent saved state in a
  `restore_state` event that Python ignored, so restoration never worked
  on Android. It now travels in `create` as `restored_state`, as on iOS.
- **iOS push entitlement.** `aps-environment` follows
  `[ios.signing].export_method`: `production` for `app-store`, `ad-hoc`,
  and `enterprise` exports, and `development` otherwise.

### Wire contract

`PROTOCOL_VERSION` becomes 5, defined once in `bridge/commits.py` and
carried by the generated `PNContracts.protocolVersion` and `yogaVersion`,
which Swift, Kotlin, and the browser preview read instead of their own
literals. Native and browser transports no longer accept the `f` (frame)
operation or answer `measure`: every native transport runs layout beside
its widgets, so Python never sent either to them. The headless fake
transport keeps both, and Python's Yoga binding remains for headless
layout in tests.

Native-to-Python callbacks return nothing: the C callback type is `void`,
`PythonHost.callback` returns `Unit`, `native_callback` returns `None`,
and the browser preview's page sends `create` and `back_pressed` as
ordinary callbacks (the root arrives through `Host.attach_root`, and
`Host.finish` pops the screen, as on device). Rebuilt apps and dev clients
are required, as with every protocol change.

## Removals

- `sdk.builtins.install()` at import, and the second load of built-in
  contracts at bootstrap.
- Fast Refresh signatures (and the `refresh` import) for framework
  components, and per-function `inspect.getsource` tokenizing.
- Per-slot journaling of `HookState` and per-field journaling of `VNode`.
- Python prop validation of commits in release builds.
- The native and browser `f` operation, `pn_bridge_measure`,
  `PNBridge.measure` (Kotlin), and the browser preview's `measure` request.
- The dead event-result path: `_on_event` encoding a handler's return value
  for native, the C callback's return buffer, Kotlin's `fireForResult`,
  return values from Swift's `callPython`, `emitEvent`, `PNEvents.emit`,
  and the generated event helpers, and docs that describe synchronous
  event results. Native has delivered events asynchronously since
  protocol 4.
- The browser preview's page-to-Python request channel (`Bridge.request`,
  `["req", ...]` messages, and `WebTransport._deliver_request`), whose only
  users were the `create` reply and `back_pressed`.
- No-op `save_state` and `restore_state` host events, and iOS's second
  `restore_state` after `create` already carried the state.
- `PNBridge.assertMain` (Kotlin), `PNBridge.ensureMainThread` (Swift, only
  ever called inside `PNBridge.onUI`), the documented but nonexistent
  `"pump"` callback kind, and the hard-coded protocol and Yoga versions in
  Swift, Kotlin, and the browser preview.
- Dropping native-to-Python messages sent before Python registered its
  callback.
- The per-project runtime download under `build/ios_runtime`.
- The silent "Skipping bytecode compilation" path for release builds.
- The blanket `POST_NOTIFICATIONS` permission on Android.
- Stub test targets and their test dependencies in both app templates.

## Alternatives considered

- **A zipped standard library.** CPython can import from `python313.zip`,
  which shrinks the file count. Rejected for now: extension modules can't
  load from a zip, iOS still needs them unpacked as frameworks, and
  sourceless bytecode already removes most of the size.
- **A frozen or snapshotted interpreter.** Freezing `pythonnative` into the
  binary, or restoring a heap snapshot, would be faster still, but needs a
  custom CPython build per release. Bytecode and lazy imports get most of
  the benefit with the stock runtime.
- **Removing Python-side commit validation entirely.** It provides the
  best error messages in development and catches framework bugs before
  they reach native code. Keeping it in development only gives both.
- **A different journal design (work-in-progress hook state).** Rendering
  into a copy and swapping it in on commit would remove the journal for
  hooks, but every hook implementation would have to read from one copy
  and write to the other. Per-object snapshots reach the same cost with
  far less churn.
- **Wall-clock thresholds in CI.** Shared runners vary too much to gate on
  milliseconds. Deterministic proxies catch the regressions that matter
  (reintroduced source parsing, schema derivation, or journal growth), and
  recorded benchmarks track the rest.

## Non-goals

- A prebuilt dev client, one-command dev loop, dev menu, inspector, or
  debugger (the next RFC).
- Raising the iOS deployment target or removing `PNCompat.swift`.
- Android App Bundle ABI splitting, R8, or shrinking Chaquopy's runtime.
- Interruptible rendering or rendering on more than one thread.
- View flattening and a binary bridge encoding.
- Generating component managers from contracts, except for the parts this
  RFC touches.
- Image caching, list prefetch windows, and other per-component
  performance work.

## Testing and rollout

- Python unit tests for the call plan (including error messages), journal
  rollback with per-object snapshots and acceptance, duplicate keys, the
  `use_query` fetcher, lazy attributes, cached development mode, protocol
  5 transports, asynchronous callbacks, and release-mode commit
  validation. All 2,220 collected tests pass (the package-matrix tests skip
  without `PN_PACKAGE_MATRIX=1`), as do ruff, black, and mypy (257 files).
- Deterministic budget tests in `tests/test_performance_budgets.py`.
- Builder tests for runtime pruning, the shared cache, bytecode
  compilation (debug and release layouts, bundle-relative file names, and
  failures), bundled plugin contracts, artifact size reports, and push
  entitlements.
- Generated-contract drift tests, including the new JSON document.
- Swift XCTest (108 tests) and Kotlin unit tests, including undo-log
  rejection and the retired frame operation.
- Browser renderer acceptance tests in headless Chrome, and the live
  preview: mounting through `Host.attach_root`, state updates, and push
  and back navigation.
- The `pn init` template on the iPhone 17 Pro simulator and on an API 31
  Android emulator (built with `ANDROID_HOME` unset): launch, state
  updates, push, and back navigation.

## Recorded validation

Measured on an Intel Mac (x86_64) with Xcode 26.3, an iPhone 17 Pro
simulator, and an API 31 x86_64 Android emulator. Unrelated builds kept the
host busy throughout (load averages between 6 and 64), so each comparison
interleaves `main` (444637a) and this change under the same conditions;
absolute numbers vary between sessions.

- **Host runtime** (`scripts/benchmark-runtime.py`, two interleaved
  sessions): `import pythonnative` 604 to 941 ms before, 294 to 326 ms
  after (202 ms in an earlier, quieter session against 659 ms); element
  construction 8.1 to 9.5 µs before, 4.1 to 5.8 µs after; a 300-component
  re-render 96 to 121 ms before, 72 to 73 ms after; preparing a
  300-view commit 5.4 to 6.6 ms before, 2.7 to 2.9 ms after.
- **iOS startup.** From the process's first log line to "Embedded Python
  initialized" (interpreter start plus importing `pythonnative`): 3.6 to
  5.7 s before, 0.8 to 1.4 s after. The first screen attached 2.0 to 3.4
  s after process start. Screenshot polling from `simctl launch` to
  visible content measured 5.3 to 6.1 s before and 3.4 to 3.6 s after.
- **iOS size.** The debug `.app` went from 92 MB to 62 MB: the standard
  library from 49 MB to 22 MB with bytecode for all 526 modules, and the
  15 test-only extension frameworks are gone. `app_packages` grew from
  5.7 MB to 8.4 MB because debug builds now carry bytecode beside the
  sources.
- **Build.** A first `pn run ios` took 116 s with the shared runtime
  already prepared, against 401 s before.
- **Android.** `am start -W` waited 10.6 to 11.0 s after the change
  against 17 to 51 s before, all reported as timeouts by a
  software-emulated device. Treat this as indicative only.

Three targets aren't met as measured:

- **App size.** 62 MB against 55 MB. Debug builds deliberately keep
  sources beside bytecode for tracebacks and Fast Refresh; release builds
  ship sourceless bytecode for the standard library, the framework, and
  the app, which removes most of the duplicated 22 MB. Release `.ipa`
  sizes weren't measured here because they require signing.
- **Launch.** The 1.5 s target assumed a quiet host. The interpreter's
  share fell four- to fivefold; what remains is process and UIKit launch
  in a loaded simulator, the dev client's connection attempt, and the
  first render.
- **Re-rendering.** The journal now costs about a tenth of a re-render,
  down from about 40 percent; the rest is spread across reconciliation
  itself, which this RFC didn't restructure.
