# Reconciliation

Reconciliation is the process that turns a freshly produced
[`Element`][pythonnative.Element] tree into the smallest set of native
view mutations that bring the on-screen tree into agreement with it.
This page covers the rules that govern child identity, keyed diffing,
function components, transitions, strict mode, providers, and error
boundaries.

## Why we need a reconciler

Re-running a `@component` function returns a brand-new
[`Element`][pythonnative.Element] tree. Naively recreating native
widgets every render would be slow (Auto Layout passes, JNI roundtrips)
and would lose user state (text selections, scroll position, focus).

The reconciler instead asks: what is the *minimal* list of native
mutations that turns the previous tree into the new one? It maintains a
parallel virtual tree of [`VNode`][pythonnative.reconciler.VNode]s, each
of which holds an integer **tag** (the view's stable identity on the
native side) and the props last applied.

## The diff algorithm in one paragraph

For each pair of (previous, next) elements matched in a child list
(see [Child identity](#child-identity)):

- If their `type` matches, **update**: emit an
  [`UpdateOp`][pythonnative.mutations.UpdateOp] carrying only the
  props that changed (removed props arrive as `UNSET`; `None` is explicit null).
- If their `type` differs, **replace**: emit destroy ops for the old
  subtree, create ops for the new one, and recurse into its children.
- Mount new children, unmount children that no longer match, and move
  native views with [`InsertOp`][pythonnative.mutations.InsertOp] /
  [`DestroyOp`][pythonnative.mutations.DestroyOp] only when a native
  container's children were created, destroyed, moved, or replaced.

The committed tree is updated in place. Each node is recorded in an undo
journal before its first change in a pass, so a pass that fails, or a
transition that's preempted, rolls back to the committed tree. A child
list that keeps its shape (the same types and keys in the same slots)
is updated child by child without building any lookup tables, and a
native view whose props didn't change isn't touched at all.

The reconciler runs synchronous render functions on the application
thread. Async components capture their provider environment across
awaits. Changes to their inputs cancel obsolete work before it can
publish. Expensive Python work delays callbacks and commits, except
that a [transition](#transitions-and-preemption) yields to urgent input.
Native scrolling and [Motion](../guides/motion.md) (animations and
worklets on the UI thread) run independently; see
[Runtime limits](architecture.md#runtime-limits).

## Commits are transactions

Rendering records changes in an undo journal and stages native operations,
callbacks, refs, and effects. A render that fails restores the committed tree
without publishing those changes. At the end of the pass, staged mutations are
applied through a single `apply_mutations` call on the view backend (see
[Native views](../api/native_views.md)). The renderer core validates the
versioned transaction before applying it, lays it out with Yoga, and
acknowledges the committed revision with the changed frames of observed
views. Headless tests commit to the same core.

`flush_dirty` combines work from several dirty components into a batch, and
state setters schedule that flush rather than rendering inline, so every
setter call in one callback lands in one pass. Layout and passive effects
that raise are routed to the nearest error boundary, and a flush that
re-schedules itself more than fifty times raises
`RuntimeError("Too many re-renders")` through the same path. See
[Commits](bridge.md#commits) for validation and failure handling.

Callable props never enter the transaction at all. They stay on the
view's node, and the [`EventRegistry`][pythonnative.events.EventRegistry]
reads them from the node when native reports an event, so a render that
only changes callback identities emits **zero** ops.

## Child identity

A child list is the positional children of a native element, a
`Fragment`, a provider, or a boundary, or the value a component
returns. Each entry occupies one **slot**, numbered from zero, as in
React:

| Entry | Slot holds |
| --- | --- |
| An element | That element |
| `None`, `False`, `True` | Nothing, but the slot is kept |
| A list, tuple, or generator | A group: an implicit fragment whose items form their own child list |
| `pn.Fragment(...)`, keyed or not | A fragment node with its own child list |

Within one child list:

1. An element with a key matches the old child with the same key,
   wherever it was.
2. An element without a key matches the old unkeyed child in the same
   slot.
3. A match with a different type is replaced. A slot that was empty and
   now holds an element is a mount; the reverse is an unmount.

So conditional children never shift their siblings:

```python
@pn.component
def Inbox() -> pn.Node:
    query, set_query = pn.use_state("")
    messages = use_messages()
    return pn.Column(
        pn.Button("Clear", on_press=lambda: set_query("")) if query else None,
        SearchField(value=query, on_change=set_query),  # keeps its state
        [MessageRow(m).with_key(m.id) for m in messages],
        Footer(),                                       # never shifts
    )
```

When the `Clear` button appears, `SearchField` stays in slot 1 and
keeps its state. The list is one slot, a group, so `Footer` keeps its
identity however many messages there are.

`*items` unpacks into separate slots, so `pn.Column(*rows, Footer())`
still shifts `Footer` when `rows` grows, exactly as spreading an array
does in React. Pass the list itself instead. In development, a group of
two or more elements without keys is reported once per component.

## Keyed children

Within a group, children without keys are matched by **index**. That's
fine for static lists but breaks down when items are inserted or
reordered:

```python
@pn.component
def Inbox() -> pn.Node:
    msgs, set_msgs = pn.use_state([("a", "Hi"), ("b", "Hello")])
    return pn.Column(
        [pn.Text(text, key=mid) for mid, text in msgs],
    )
```

Without `key=mid`, inserting a new message at index `0` would update
each existing `Text` in place rather than push them down, briefly
showing the wrong text in each row. With keys, the reconciler matches
"a" and "b" by identity, mounts the new row at index `0`, and moves
the others without re-rendering them.

!!! tip "Choose keys from the data, not the position"
    `key=i` for `i in range(len(items))` is no better than no key at
    all. Use a stable identifier (database id, file path, etc.).

Built-in factories take `key=` directly. To key one of your own
components, call [`.with_key()`][pythonnative.element.Element.with_key]
on its element: `MessageRow(message).with_key(message.id)`. A user
component doesn't accept `key=`, because a key identifies the element
rather than being a prop.

## Function components

A `@pn.component` function is treated as an element type just like
`"Text"` or `"Button"`. When the reconciler encounters one:

1. It looks up the function's hook state (or creates a fresh slot).
2. It calls the function with the current props inside an active hook
   context.
3. It recursively reconciles whatever the function returned, a
   [`Node`][pythonnative.element.Node]: a single
   [`Element`][pythonnative.Element], a `list` or tuple of nodes (a
   child list whose entries mount as siblings at the component's
   position, with the slot rules above), or `None` (which mounts
   nothing).

Hook slots are matched by their position in the function body, which is
why hooks must be called at the top level (not inside `if`/`for`). In
dev mode the reconciler verifies the hook call sequence on every
render and raises
[`HookOrderError`][pythonnative.HookOrderError] on a mismatch.

## Skipping unchanged subtrees

A component re-renders when its own state changes, when its parent
re-renders it with new props, or when a context it reads changes. Two
checks let the reconciler skip work when a parent re-renders:

- **Identity bailout.** When a child element is the *identical* object
  the node rendered last time, and the node has no pending work of its
  own, the reconciler reuses the node and its whole subtree without
  calling any component functions. Element objects are immutable, so
  identity proves nothing changed. Descendants that do have pending
  state updates are already in the dirty queue and render in their own
  pass, and context consumers are marked through the provider's
  registry (below), so skipping a subtree never hides an update.
- **Memo.** A [`@pn.memo`][pythonnative.memo] component whose new props
  equal its previous props (shallowly, by default) is skipped even when
  the parent built a new element for it.

The identity bailout needs no API. It applies whenever a component
passes through elements it didn't build, which is the common case for
containers:

```python
@pn.component
def Card(*children: pn.Node, title: str) -> pn.Node:
    expanded, set_expanded = pn.use_state(True)
    return pn.Column(
        pn.Button(title, on_press=lambda: set_expanded(lambda e: not e)),
        pn.View(*children, style={"display": "flex" if expanded else "none"}),
    )
```

Toggling `expanded` re-renders `Card`, but `children` are the same
element objects its parent passed in, so the reconciler doesn't
re-render them. Navigators rely on the same rule: each route's screen
element is cached, so a navigator re-render (a title change, a focus
change) doesn't re-render the screens.

## Fragments and multi-child rendering

[`Fragment`][pythonnative.Fragment] groups siblings without a wrapping
native view: its children mount as native siblings at its position in
the parent's native child list. A fragment is a node of its own that
occupies one slot, keyed or not, and its children are matched among
themselves, like a list's. A keyed Fragment moves all of its children
together.

## Transitions and preemption

Every render pass is **urgent** or a **transition**. State updates made
inside [`start_transition`][pythonnative.start_transition], the
`start_transition` that [`use_transition`][pythonnative.use_transition]
returns, or a [`use_deferred_value`][pythonnative.use_deferred_value]
catch-up are transition updates. They wait in their component's state
queue, so urgent renders keep reading the old value, and they render in
a pass of their own after urgent work.

Only component state waits. A [`Store`][pythonnative.Store], or any
source read through [`use_subscription`][pythonnative.use_subscription],
holds its new value as soon as it's written, so its subscribers
re-render urgently even when the write happens inside a transition.
Otherwise one subscriber could show the new value while another still
showed the old one.

A transition pass checks for queued urgent input before each component
body. The bridge queues presses, text changes, keys, submits, back
presses, gesture ends, and navigation events as urgent input; scroll,
gesture updates, layout, window metrics, and selection changes are
coalesced and don't count. Neither does work from another thread, such
as a state setter a worker calls: it isn't input, and it runs once the
pass finishes. When input is waiting, and the pass hasn't
sent anything to native yet, PythonNative:

1. rolls the pass back, restoring every node and hook state it touched
   and dropping its staged mutations and effects;
2. runs the input's handler, renders its urgent updates, and commits
   them;
3. renders the transition again, replaying every queued update in its
   original order.

`is_pending` from `use_transition` stays `True` until the transition
commits, across any number of restarts. A transition that's been
preempted three times, or has been pending for 250 ms, renders without
checking, so a stream of taps can't starve it. A transition started by
the commit of another (from an effect, say) gets a fresh count and clock.

PythonNative doesn't slice renders the way React does on the web. Native
views scroll, animate, and paint on the UI thread while Python renders,
so a transition never needs to pause for the screen; it only needs to
get out of the way of input.

## Strict mode

A preempted transition renders again, so a component body must be
pure: a body that changes something outside itself would apply the
change twice. [`StrictMode`][pythonnative.StrictMode] finds those
bodies in development:

```python
pn.StrictMode(App())
```

For every component mounted beneath it, in development mode, the body
runs twice per render (the first result is discarded), `use_state`
initializers, updater functions, reducers, and `use_memo` factories
run twice, and on mount each `use_effect` and `use_layout_effect` runs,
cleans up, and runs again. Release builds ignore it. The `pn init`
template wraps its root in `StrictMode`, and `pn lint` rule `PN105`
flags the most common impurity it exposes: assigning to a module-level
name or mutating a module-level container in a component body.

## Portals

[`Portal`][pythonnative.Portal] elements contribute **zero** native
children to their parent. Their subtree mounts into a full-screen
overlay owned by the platform handler, and the layout pass positions
portal children against the viewport instead of the parent box. State,
context, and events still flow through the normal component tree; only
the native views live elsewhere.

## Context providers

[`Context.Provider`][pythonnative.hooks.Context.Provider] returns an element
whose type is the context itself. When the reconciler mounts one, it
pushes a value onto a per-context stack;
descendants reading via [`use_context`][pythonnative.use_context]
observe the topmost value.

Context is reactive, and propagation is targeted. `use_context` records
which provider node supplied the value, and each provider keeps a
registry of its consumer nodes, updated as consumers render and
unmount. When a re-render changes a provider's value, the reconciler
marks exactly the registered consumers dirty. It doesn't walk the
provider's subtree looking for them, so the cost is proportional to the
number of consumers. Consumers re-render even when a memoized ancestor
or an identity bailout skips the subtree between them and the provider.

```python
Accent = pn.create_context("#000000", name="Accent")


@pn.component
def Page() -> pn.Node:
    return Accent.Provider(Header(), value="#222222")


@pn.component
def Header() -> pn.Node:
    accent = pn.use_context(Accent)
    return pn.Text("Hi", style={"color": accent})
```

## Error boundaries

[`ErrorBoundary`][pythonnative.ErrorBoundary] is a special-cased
element. When the reconciler renders a subtree underneath one and an
exception escapes a child component or handler, the reconciler:

1. Catches the exception and invokes the boundary's `on_error`
   callback, if provided.
2. Tears down the partially-mounted subtree.
3. Renders the boundary's `fallback` (a static
   [`Element`][pythonnative.Element], `fallback(error)`, or
   `fallback(error, reset)` where `reset` remounts the children).
4. Continues reconciling the rest of the page.

This means a single misbehaving component can't bring down the whole
screen. See the [Error boundaries guide](../guides/error-boundaries.md)
for usage patterns.

## When to bypass the reconciler

For animation-driven values that change every frame (60+ Hz), going
through `set_state` is wasteful. Two ways to bypass:

- Use [Motion](../guides/motion.md): a
  [`SharedValue`][pythonnative.SharedValue] read by
  [`use_animated_style`][pythonnative.use_animated_style] drives the
  native property from the UI thread, and worklets handle scroll and
  gesture events there, so no Python code runs per frame at all.
- Use [`use_ref`][pythonnative.use_ref] to receive a typed
  [handle](../api/handles.md) for a mounted view and drive it
  imperatively (`scroll_to`, `focus`, a custom component's `command`)
  from inside an effect callback.

Reach for these only when profiling tells you that re-rendering is the
bottleneck.

## Next steps

- Browse the algorithm in code: [Reconciler API](../api/reconciler.md).
- Understand the backend underneath the diff: [Native views](native-views.md).
- See how mounting interacts with hooks: [Lifecycle](lifecycle.md).

## Elements and update priority

Elements are immutable: assigning an attribute raises, and
[`with_key`][pythonnative.element.Element.with_key] copies one. An element
keeps the props mapping its factory built rather than copying it, and its
children are a tuple. Values inside application props aren't copied;
replace mutable application data when its meaning changes. Component
construction follows the decorated function's Python signature, including
positional-only parameters, keyword-only parameters, variadic children,
and normal argument errors.

State setters and reducer dispatch functions retain their identity across
renders. Transition updates stay out of urgent renders. When the
transition renders, the state queue replays urgent updates in their
original order so an urgent edit isn't lost.

A native mount failure retires the surface and cancels its work. Validation
failure before native mutation preserves the previous revision and can be retried.
Property validation copies only changed records, so a one-property update doesn't
clone the rest of the live native tree.
