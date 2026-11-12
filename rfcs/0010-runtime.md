# RFC 0010: Runtime

- Status: Draft
- Author(s): Owen Carey, with Claude (Claude Code)
- Created: 2026-11-11
- Implemented in: (the `feat/runtime` branch, once shipped)
- Supersedes / Superseded by: replaces the child matching rule and the
  one-turn transition deferral from RFC 0002, and the per-attribute render
  journal from RFC 0005. Everything else in those RFCs remains implemented.

## Summary

PythonNative's renderer core, native hosts, and motion system now match
React Native's New Architecture, but the layer every app spends its Python
time in hasn't been restructured since it was written: the reconciler,
hooks, and element factories. It's slow (a 300-component re-render makes
about 175,000 function calls), it can't be preempted, and it gives children
a different identity rule than React does, so `cond and pn.Text(...)`
makes the siblings after it lose their state.

This RFC rebuilds that layer, in Python, with no change to the wire
contract or to any native code:

- **React's child identity.** `None` and `False` children keep their
  position, and a list passed as a child is its own group. A conditional
  child no longer remounts its siblings.
- **A lean reconciler.** One pass over the props of each view, in-place
  updates when a child list keeps its shape, and bookkeeping only for
  what changed. The target is a re-render at least three times faster.
- **Preemptible transitions.** A render started by `start_transition` or
  `use_deferred_value` is abandoned when the user taps or types, the
  urgent update commits first, and the transition restarts.
- **Strict mode.** `pn.StrictMode` double-renders components and
  double-runs effects in development, which finds the impure renders that
  preemption would otherwise turn into bugs.
- **Faster startup, measured.** Every launch logs a startup timeline, and
  the framework stops doing work at import that the first frame doesn't
  need.
- **Performance gates that don't depend on the clock.** Tests bound the
  number of function calls a render makes, so a regression fails CI.

## Motivation

Measurements are from an Intel Core i9-9980HK Mac (Python 3.13.15, load
average about 6) on 2026-11-11, at `851b0080`. They're host and simulator
timings, like every number in earlier RFCs.

### Conditional children remount their siblings

`normalize_children` (`reconciler/vnode.py`) drops `None`, `True`, and
`False` before the diff, and `_reconcile_child_list` matches unkeyed
children by position among what's left:

```python
pn.Column(
    show_banner and Banner(),
    SearchField(),   # has state: the text being typed
    Results(),
)
```

When `show_banner` turns true, `SearchField` is compared with `Banner` in
position 0. The types differ, so `SearchField` is destroyed and recreated.
Its text, its focus, and any running async handler are gone. React keeps a
hole where the falsy child was, so `SearchField` stays in position 1.

The same rule flattens lists into their parent. In
`pn.Column(Header(), [Row(i) for i in items], Footer())`, growing `items`
shifts `Footer` unless every child is keyed. React treats the array as one
child whose items are matched among themselves.

RFC 0008 recorded this as a known rough edge, and Field Notes works around
it with keys. It's the most common idiom in React code, and it fails
silently.

### The reconciler is slower than it needs to be

`scripts/benchmark-runtime.py` re-renders 300 keyed components (1,201
nodes) whose props all change. It takes 100 to 110 ms:

| Part | Time | Share |
| --- | --- | --- |
| Component bodies (functions, hooks, element factories) | 25 ms | 23% |
| Reconciler (diffing, bookkeeping) | 66 ms | 60% |
| Commit (encode, core, headless decode) | 20 ms | 17% |

The reconciler spends about 55 microseconds per node. A profile shows no
single hot spot. The cost is spread over work done for every node whether
or not anything changed:

- `_split_props` copies the props, checks seven motion props, looks up
  the motion target, defines a closure, and calls `extract_events`, which
  builds two more dicts (`reconciler/core.py`, `events.py`).
- `_reconcile_native` computes the flattened native child tags before and
  after reconciling the children, recursively, even when no child was
  added, removed, or moved.
- `_reconcile_child_list` builds a key dict, an unkeyed list, a set, and
  an iterator for every child list.
- Every attribute write to a `VNode` goes through a Python `__setattr__`
  that consults the render journal (5,700 calls per pass), and the journal
  snapshots every field of each node on its first write.
- Each native node appends a `functools.partial` publication for its
  events on every pass, changed or not.
- Node kinds are properties that call `isinstance` (4,500 property reads
  and 19,500 `isinstance` calls per pass).

A spike measured how much of that is inherent to Python. A lean update
path (real elements, real component bodies, real hooks, one pass over
each node's props, in-place child updates, one undo record per node)
diffed the same tree in 6.8 ms instead of 66 ms. The spike left out the
general keyed path, boundaries, and the special props, so the shipped
number will be higher, but the headroom is about tenfold on the
reconciler's share.

Component bodies have slack as well. `pn.Text("a")` takes 6.5
microseconds, of which constructing the `Element` is 1.7 (a plain slotted
class takes 0.3). The frozen dataclass assigns four fields through
`object.__setattr__`, copies the props dict, and wraps it in a
`MappingProxyType`.

Recorded results for this benchmark have ranged from 47 ms (RFC 0007) to
70 ms (RFC 0009) to more than 100 ms today on the same machine. Load
explains some of that, but nothing in the repository can tell load from a
regression, because RFC 0005 chose not to gate on wall-clock time.

### A render can't be preempted

`use_transition` defers a render by one turn of the event loop
(`scheduler.py`). Once it starts, it runs to completion.
`docs/concepts/reconciliation.md` says so: "a long synchronous function
cannot be preempted by a later urgent update." If filtering a list takes
200 ms, a keystroke that arrives 10 ms in waits 190 ms, which is the
problem transitions exist to solve.

React solves it by slicing the render and yielding to the browser.
PythonNative doesn't need slices: native views scroll, animate, and
paint on the UI thread while Python renders. What Python needs is to
notice that an urgent event is waiting and get out of its way.

### Nothing checks that renders are pure

A preempted render is discarded and run again, so a component body that
mutates something outside itself would apply that change twice. React's
`StrictMode` exists to surface this in development. PythonNative has no
equivalent.

### Startup is import-bound and unmeasured

Field Notes in the release configuration on the iOS 26.2 simulator
attached its first screen 1,981, 2,207, and 2,398 ms after process start.
The interpreter was initialized about 0.7 s in, so 1.26 to 1.38 s is
Python work: importing the framework, importing the app, rendering, and
committing. The app logs only those two timestamps, so the split between
them is unknown on device.

On the host, `import pythonnative` takes 420 to 450 ms for 67 framework
modules and 240 modules in total. Known contributors:

- 53 `@dataclass` definitions cost 70 ms, because `dataclasses` generates
  each class's methods with `exec`.
- `asyncio` and what it imports (`ssl`, `socket`, `subprocess`) cost about
  85 ms.
- `svg`, `components.lists`, and `sdk.plugin` are imported eagerly and
  cost 24, 29, and 28 ms.

In development, `@pn.component` also parses each component's source for
its Fast Refresh signature at import (`refresh.py`), which cost 70 ms of
Field Notes's 745 ms app import.

## Reference behavior

| Concern | React and React Native | This RFC |
| --- | --- | --- |
| Falsy children | `null`, `false`, and `true` hold their position; siblings keep their identity | The same |
| Array children | One child; items matched by key, or by index within the array | The same, for lists, tuples, and generators |
| Fragments | A node of its own | The same; unkeyed fragments are no longer flattened into the parent |
| Reconciler | Fibers: a second tree built per render, in an interruptible work loop | The committed tree updated in place, with an undo journal for rollback |
| Priorities | Lanes: many priority levels, time-sliced on one thread | Two levels, urgent and transition. A transition is preempted, not sliced |
| Starvation | Transition lanes expire and render synchronously | A transition preempted three times, or pending for 250 ms, renders without checking |
| Strict mode | `<StrictMode>`: double render and double effects in development | `pn.StrictMode(...)`, the same checks |
| Standalone transition | `startTransition(fn)` | `pn.start_transition(fn)` |

Deliberate differences:

- **No fibers.** React builds a work-in-progress tree so it can pause a
  render and resume it later, because the JavaScript thread must yield
  for the browser to paint. PythonNative paints on another thread, so it
  never needs to pause, only to abandon. An in-place update with an undo
  journal, which the reconciler already has, abandons a render at a
  fraction of the allocation cost that a second tree would have in Python.
- **Preemption instead of slicing.** A transition runs in one piece
  unless an urgent input arrives. That means no generator frames or
  explicit work stack on the hot path, and no partially rendered tree for
  other code to observe.
- **Still Python.** React's reconciler is JavaScript running on a fast
  engine. Moving PythonNative's into C++ would buy more speed, but see
  "Alternatives considered" for what it would cost.

## Design

### Overview

Nothing changes on the wire. `PROTOCOL_VERSION` stays 8, and there are
no changes to Swift, Kotlin, C++, or the preview's JavaScript. PythonNative
Go, the browser preview, and headless tests get every part of this RFC
from the Python package alone.

For application code:

```python
@pn.component
def Inbox() -> pn.Node:
    query, set_query = pn.use_state("")
    shown = pn.use_deferred_value(query)
    return pn.Column(
        ClearButton(on_press=lambda: set_query("")) if query else None,
        SearchField(value=query, on_change=set_query),  # keeps its state
        [MessageRow(m).with_key(m.id) for m in search(shown)],
        Footer(),                                       # never shifts
    )
```

`SearchField` keeps its identity when `ClearButton` appears. (`query and
ClearButton(...)` would render the same way, but an empty string isn't a
`pn.Node`, so the conditional expression is the typed spelling.) `Footer`
keeps its identity as the list grows. Rendering the rows for a new
`shown` is a transition: if the user types again while it renders, the
render is dropped, the keystroke commits, and the rows render for the
newer value.

### Child identity

A child list is the positional children of a native element, a
`Fragment`, a provider, or a boundary, or the value a component returns.
Each entry occupies one **slot**, numbered from zero:

| Entry | Slot holds |
| --- | --- |
| An element | That element |
| `None`, `False`, `True` | Nothing, but the slot is kept |
| A list, tuple, or generator | A group: an implicit fragment whose items form their own child list |
| `pn.Fragment(...)`, keyed or not | A fragment node with its own child list |

Matching within one child list:

1. An element with a key matches the old child with the same key,
   wherever it was.
2. An element without a key matches the old unkeyed child in the same
   slot.
3. A match with a different type is replaced. A slot that was empty and
   now holds an element is a mount; the reverse is an unmount.

A component that returns a list returns a child list, as it does today,
and one that returns `None` renders nothing.

`*items` unpacks into separate slots, so `pn.Column(*rows, Footer())`
still shifts `Footer` when `rows` grows, exactly as spreading does in
React. Passing the list itself is now the recommended form, and the
development warning for "a nested list among positional children" is
removed. The warning for a group of two or more elements without keys
stays.

`VNode.children` stays dense: holes aren't stored as nodes. Each child
records its `slot`, and matching reads it. Code that walks the tree
(layout, DevTools, the testing queries, Fast Refresh) needs no changes
for holes. Groups and unkeyed fragments are real nodes of the existing
wrapper kind, transparent to native child order, as keyed fragments
already are.

### The reconciler

`reconciler/core.py`, `children.py`, `vnode.py`, and `journal.py` are
restructured. The public surface (`Reconciler.mount`, `reconcile`,
`flush_dirty`, `unmount`, `walk`, and the `VNode` attributes tools read)
is unchanged.

- **Node kinds.** `VNode.kind` is an integer set at creation (native,
  component, provider, error boundary, suspense, wrapper). The `is_*`
  properties remain for tools and read it.
- **Explicit journaling.** `VNode.__setattr__` is removed. The reconciler
  calls `touch(node)` (`reconciler/vnode.py`) once, where it first
  changes a node in a pass, which records the fields that pass can change
  through `Journal.record`. Nodes created in the pass are never recorded.
  Hook states are recorded the same way, copying only the lists a render
  replaces entries of. `Ref` keeps its journaled writes, since
  application code assigns `ref.current` directly.
- **One pass over props.** A native update walks the new props once.
  A value identical to the old one is skipped. An `on_*` callable updates
  the node's handler table. Anything else is compared with `equal` and
  added to the update op if it differs. Removed keys are found only when
  the counts disagree. The current split-then-diff path remains as the
  slow path for the props that need it: `ref`, `on_layout`, `gestures`,
  `refresh_control`, the motion props, and animated styles.
- **Handlers on the node.** Event callbacks live in `VNode.events`, which
  the journal covers, and the event registry resolves a tag to its node's
  table at dispatch: `EventRegistry.register(tag, node, scope)` runs once,
  when the view is committed. The per-node, per-pass `set_events`
  publication is removed. Handlers from an uncommitted or rolled-back
  pass are never visible, as now.
- **Child lists.** If the new list has the same length and each slot has
  the same key and type, children update in place with no dicts built.
  Otherwise the keyed path runs, as now, with the slot rule above.
- **Native order only when it changed.** Creating, destroying, moving, or
  replacing a child marks the nearest native ancestor's order as stale.
  Only stale containers recompute their flattened child tags and emit
  inserts, right before the ops are flushed.
- **Untouched when unchanged.** A native view, fragment, group, or
  provider whose props and child list didn't change isn't recorded or
  written at all; it keeps its previous element, which compares equal.
- **Refs and layout.** Ref publications are queued only when a ref
  changed or its view was created.
- **Bailouts.** An identical element, a memoized component with equal
  props, and identical props objects all skip work, as the first two do
  now.

Boundaries, Suspense hydration, async components, effect ordering, the
render-storm guard, asynchronous commits, and rollback on failure keep
their behavior. Their code moves onto the new node layout.

### Elements and factories

- `Element` becomes a slotted class instead of a frozen dataclass. It's
  still immutable to application code: assignment raises, `props` is
  typed `Mapping`, and equality is unchanged. Factories hand it a dict
  they just built, so construction stops copying.
- `_make_element` gets fast paths for the common calls: no style or one
  style dict, no `ref`, and no accessibility values.
- `Element.with_key` copies the element without rebuilding its props.
- Hooks stop recording to the hook log and checking the signature
  outside development mode, which they nearly do today, and read their
  cursor without the intermediate helper calls.

### Preemptible transitions

Every render pass is **urgent** or a **transition**.

- A pass is a transition when all of its work came from
  `start_transition` or `use_deferred_value`. Any urgent state change
  makes the pass urgent. Mounts and `reconcile` calls from hosts are
  urgent.
- An urgent pass runs to completion, as now.
- A transition update doesn't change the state that urgent renders read.
  It waits in its hook state's queue (the queue `use_transition` already
  had), and its component is recorded in the reconciler's
  `TransitionQueue`. The transition pass applies every queue in order,
  inside its journal, so a rollback restores the queues too. Clearing
  `is_pending` is itself a transition update, so it commits with the
  transition.
- A transition pass checks for urgent input before each component body.
  Input reaches the application loop through `scheduler.queue_urgent`,
  which counts what's queued and not yet run; the bridge queues
  **discrete** native messages this way (every `event` and `host`
  message the bridge doesn't coalesce: presses, text changes, keys,
  submits, back presses, gesture ends, navigation events). Continuous
  events (`on_scroll`, `on_window`, `on_selection_change`, and
  `on_gesture_update`), which the bridge already coalesces, aren't
  urgent. Work queued from another thread with
  `call_on_application_thread`, such as a state setter, is urgent too.
- When the flag is set, the pass raises an internal `Preempted` signal.
  The journal rolls back every node and hook state the pass touched, the
  staged ops and publications are dropped, and the transition's updates
  go back in the queue. Nothing reached native, because preemption is
  only checked before the first op is flushed.
- The loop then runs the event's handler. Its updates render and commit
  as an urgent pass, and the transition is scheduled again after it.
  State updates replay in their original order, which the state queues
  already guarantee.
- A transition that has been preempted three times, or has been pending
  for 250 ms, renders without checking, so a stream of taps can't starve
  it.
- `is_pending` from `use_transition` stays true until the transition
  commits, across any number of restarts.

`pn.start_transition(fn)` is exported for code outside a component, such
as a store action. It marks the updates in `fn` as a transition and has
no pending flag.

`TransitionQueue` now records the hook states with queued transition
updates, the preemption count, and when the transition was queued; its
one-turn `defer`, `on_complete`, and `flush` are gone. Flushes and urgent
input are scheduled in a fresh `contextvars.Context`, so a handler never
inherits the transition flag of the code that scheduled it.
`docs/concepts/reconciliation.md` and the `use_transition` and
`use_deferred_value` docstrings are rewritten to describe preemption.

### Strict mode

```python
pn.StrictMode(App())
```

`StrictMode` is a structural element, like `Fragment`. In development
mode, for components beneath it:

- Each component body runs twice per render. The first result is
  discarded, and hooks see the same state both times.
- On mount, each effect runs, its cleanup runs, and it runs again, for
  both `use_effect` and `use_layout_effect`.
- `use_memo` factories, `use_state` initializers, and updater functions
  (which includes reducers) run twice.

In a release build, and without the wrapper, nothing changes. The
`pn init` template wraps its root in `StrictMode`. `pythonnative.testing`
doesn't enable it unless a test renders the wrapper.

### Startup

**A timeline on every launch.** `bootstrap.start` and the first host
render record monotonic marks: framework imported, contracts loaded,
bridge connected, app imported, first render finished, first commit
acknowledged. One line is logged per launch, in release builds too:

```text
[PN] startup: framework 182 ms, contracts 9 ms, app 310 ms, render 41 ms, commit 28 ms
```

`pn.diagnostics.startup_timeline()` returns the same marks as a mapping,
and they're reported through the existing profiling counters.

**Less work at import.**

- Framework classes that are dataclasses only for convenience, and are
  defined on the import path of `import pythonnative`, become slotted
  classes or named tuples. Dataclasses that are public API with documented
  dataclass behavior (`Theme`, event records, `Props` subclasses) stay.
- `svg`, the list components, `sdk.plugin`, and the native module facades
  join the lazy groups in `pythonnative/__init__.py`. Their names resolve
  on first use, as navigation and networking do today.
- `@pn.component` no longer parses source at definition. It records the
  function, and `refresh.hook_signature` reads the module's source, kept
  from the last load, when Fast Refresh first compares two versions.
- `MODULE_BUDGET` in `tests/test_performance_budgets.py` is lowered to
  the new count, and a new budget bounds the dataclass definitions
  executed by `import pythonnative`.

### Targets and gates

Targets, on the reference machine with the same scripts:

| Measure | Today | Target |
| --- | --- | --- |
| Re-render of 300 components (`rerender_300_ms`) | 100 to 110 ms | 35 ms or less |
| Mount of 300 components (new `mount_300_ms`) | 142 to 148 ms | 75 ms or less |
| Function calls per re-rendered component, Python and built-in | About 585 | 200 or fewer |
| `import pythonnative` | 420 to 450 ms | 250 ms or less |
| Field Notes, interpreter ready to first screen, iOS simulator, release | 1.26 to 1.38 s | 1.0 s or less |

Gates in `tests/test_performance_budgets.py`, none of which read a clock:

- Function calls (Python and built-in) for one re-render and one mount of
  the benchmark tree, counted with `sys.setprofile`, with a budget set 15%
  above the shipped count.
- A pass in which nothing changed creates no ops, no publications, and no
  journal records beyond the component that rendered.
- A child list that keeps its shape allocates no matching dicts.

`scripts/benchmark-runtime.py` gains `mount_300_ms` and
`transition_preempt_ms` (the time from a queued press to its commit while
a 300-component transition is rendering), and results are recorded in
`rfcs/benchmarks/0010-runtime.json`.

### Tooling, docs, and examples

- `pn lint` gains a rule for the most common impurity strict mode
  exposes: assigning to a module-level name or mutating a module-level
  container inside a component body.
- `docs/concepts/reconciliation.md`, `docs/concepts/hooks.md`,
  `docs/concepts/architecture.md`, `docs/guides/state.md`, and
  `docs/api/hooks.md` are updated for the identity rule, preemption,
  strict mode, and the startup timeline.
- Field Notes drops the keys it added to work around shifting siblings.
- `examples/e2e-suite` gains demos, with Maestro flows, for a conditional
  sibling keeping its state, a list group beside a stateful footer, and a
  preempted transition.

### Rollout order

The work lands in one pull request, in this order, with the full suite
passing after each step:

1. Call-count gates and the new benchmarks, recorded against today's
   code.
2. Child identity: slots and groups.
3. The lean reconciler, elements, and factories.
4. Preemptible transitions.
5. Strict mode.
6. Startup timeline and import work.
7. Docs, examples, E2E demos, and recorded results.

## Removals

- **Dropping falsy children and flattening lists.** `normalize_children`
  is gone, replaced by `child_slots`, along with the nested-list
  development warning. The old matching rule isn't kept behind a flag:
  it's a bug relative to React, and code that depended on siblings
  remounting was depending on state loss.
- **Inline expansion of unkeyed fragments.** `Fragment` no longer drops
  `None` and `False` children either.
- **`VNode.__setattr__`, `STRUCTURAL_FIELDS`, and the field-by-field
  snapshots.** Replaced by `touch` and `Journal.record`. The
  `_local_update` wrapper that compared native roots before and after a
  local update is gone; stale containers replace it.
- **Per-node `set_events` publications**, and `EventRegistry.set_events`
  and `EventRegistry.set_scope` with them (replaced by `register`).
- **`Element` as a frozen dataclass**, including `dataclasses.replace`,
  `dataclasses.fields`, `FrozenInstanceError`, and the copied,
  `MappingProxyType`-wrapped props. `with_key` is the supported way to
  copy one.
- **`CreateOp`, `UpdateOp`, `InsertOp`, and `DestroyOp` as frozen
  dataclasses.** They're slotted classes with the same fields and value
  equality.
- **`TransitionQueue.defer`, `on_complete`, and `flush`**, and the
  one-turn deferral as the whole of what a transition means, along with
  the statement that rendering can't be preempted.
- **Field Notes's `widgets.slots` helper**, which keyed children only to
  stop siblings from remounting.
- **Source parsing in `@pn.component`.**
- **Eager imports** of `svg`, the list components, `sdk.plugin`, and the
  native module facades from `pythonnative/__init__.py`. The names stay
  importable from `pythonnative`.

## Alternatives considered

- **A native reconciler in the C++ core.** It would be perhaps twice as
  fast again as the lean Python one. It needs the CPython C API inside
  `libpncore`, which on Android means linking against the `libpython`
  that Chaquopy owns and loads, with headers Chaquopy doesn't publish to
  app builds. RFC 0007 rejected a CPython extension for that reason. It
  would also put hook, boundary, and Fast Refresh semantics in C++ with
  manual reference counting, for a single maintainer. The spike shows
  most of the available time is recoverable without it. Revisit when
  device traces show the remaining Python cost mattering.
- **Replacing Chaquopy.** It would make a native reconciler practical and
  move Android to PyPI's own wheels, but it's a runtime swap that has to
  be proven on Android hardware, and nothing in this RFC needs it.
  Chaquopy 17 already installs PyPI's Android wheels.
- **Compiling the reconciler with mypyc.** The source would stay Python,
  but PythonNative would have to build and publish its own iOS and
  Android binary wheels and install them into apps, instead of bundling
  the host's copy. That's a packaging project. It stays available later,
  and it would compile the lean reconciler just as well.
- **Fibers and time slicing.** See "Reference behavior". A second tree
  per render costs allocations Python is slow at, and slicing solves a
  problem (yielding to paint) that PythonNative doesn't have.
- **Generator-based rendering.** Making every reconcile step a generator
  would allow pausing, but `yield from` chains tax every node on every
  render to serve the rare preemption.
- **Rendering on a second thread or interpreter.** Free-threaded builds
  aren't what BeeWare or Chaquopy ship, and subinterpreters can't share
  the application's objects.
- **Signals instead of re-rendering.** Fine-grained reactivity would
  avoid most reconciliation, but it replaces the component model that
  RFC 0004 settled and that React developers recognize.
- **Wall-clock performance tests.** They flake on shared CI runners.
  Call counts are deterministic and move with the same changes.
- **Holding the mount until layout effects have run.** That would make
  `use_layout_effect` run before paint, as in React. It needs a commit
  flag in the core, a protocol bump, and buffering of view commands on
  every host. It's worth doing, separately.

## Non-goals

- Any change to the wire contract, the renderer core, the native hosts,
  or the preview's JavaScript.
- A native or compiled reconciler, and replacing Chaquopy.
- `use_layout_effect` before paint.
- Pausing and resuming a render, more than two priority levels, and
  rendering content offscreen ahead of time.
- Free-threaded CPython and subinterpreters.
- New hooks from React 19 (`use_optimistic`, `use_action_state`) and
  `use_id`.
- The `State` object and typed `use_mutation` that earlier RFCs
  deferred. They're API design, not runtime, and deserve their own
  discussion.
- Measurements on physical devices. The targets are host and simulator
  numbers; the startup timeline is what will make device numbers easy to
  collect.
- Shrinking the app's own import time. The timeline reports it;
  `pn.lazy` screens are the existing tool for it.

## Testing and rollout

- **Existing suites.** The reconciler, hooks, suspense, boundaries,
  navigation, lists, motion, Fast Refresh, and testing-library tests run
  unchanged except where they assert the old identity rule. Each such
  test is rewritten to assert the new one, and the change is listed in
  the pull request.
- **Identity.** New tests cover a falsy child toggling beside stateful
  siblings, groups growing and shrinking beside stateful siblings, keyed
  items moving between slots, nested groups, fragments, components
  returning lists and `None`, and native child order after each.
- **Reconciler equivalence.** A property-style test renders random trees
  and random updates, then compares the native tree the ops produce with
  a fresh mount of the same element.
- **Preemption.** Tests drive a transition with the virtual clock, queue
  a discrete event mid-render, and assert the urgent commit lands first,
  hook state is restored, effects don't run for the abandoned pass,
  `is_pending` stays true, and the starvation limits hold.
- **Strict mode.** Tests assert the double calls in development and
  their absence in release mode.
- **Gates.** The call-count and allocation budgets above.
- **Hosts.** Field Notes and the E2E suite run on the iOS simulator and
  an Android emulator, with the new Maestro flows, and the browser tests
  run against the preview. No native code changes, so these are
  regression runs.
- **Migration.** Apps may delete keys they added only to stop siblings
  from remounting. A child list that mixes `*spread` items with later
  unkeyed stateful siblings behaves as before; passing the list itself
  fixes it.

## Open questions

- **Which events are discrete.** The list above follows the bridge's
  existing split between coalesced and uncoalesced events. Text
  selection changes are coalesced today but arguably urgent.
- **The starvation limits.** Three preemptions and 250 ms are starting
  values. The preemption benchmark may move them.
- **Strict mode in the template.** Wrapping the `pn init` root in
  `StrictMode` matches React's project templates, but doubles
  development render cost for new users.
- **How much import time is left to remove.** The 250 ms target assumes
  the dataclass and lazy-loading changes land as estimated; `asyncio`
  alone is a third of it.
