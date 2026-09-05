# Reconciliation

Reconciliation is the process that turns a freshly produced
[`Element`][pythonnative.Element] tree into the smallest set of native
view mutations that bring the on-screen tree into agreement with it.
PythonNative's reconciler is small (a few hundred lines) and intentional;
this page covers how to think about it and the rules that govern keyed
diffing, function components, providers, and error boundaries.

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

For each pair of (previous, next) elements at the same position in the
tree:

- If their `type` matches, **update**: emit an
  [`UpdateOp`][pythonnative.mutations.UpdateOp] carrying only the
  props that changed (removed props arrive as `None`).
- If their `type` differs, **replace**: emit destroy ops for the old
  subtree, create ops for the new one, and recurse into its children.
- For container elements, match children by `key` first and by
  position only if no key was provided. Reorder, mount, and unmount
  as needed using [`InsertOp`][pythonnative.mutations.InsertOp] /
  [`DestroyOp`][pythonnative.mutations.DestroyOp].

That's it. There's no "fiber tree", no time slicing, and no priority
lanes. The reconciler runs synchronously to completion; if a render is
heavy, you'll feel it as a frame drop, not a deferred update.

## Commits are transactions

The diff phase is pure: it only accumulates ops. At the end of the
pass the whole list (including the `SetFrameOp`s produced by the
layout pass) is applied through a single
[`apply_mutations`][pythonnative.native_views.NativeViewRegistry.apply_mutations]
call. The native side sees one coherent transaction per commit
(mirroring React Native's Fabric mounting layer), which is also what
makes `flush_dirty` batches cheap: several dirty components re-render,
and their combined mutations land as one batch.

Callable props never enter the transaction at all. They're registered
in the [`EventRegistry`][pythonnative.events.EventRegistry] keyed by
`(tag, event name)`, so a render that only changes callback identities
emits **zero** ops.

## Keyed children

Without keys, children are matched by **index**. That's fine for static
lists but breaks down when items are inserted or reordered:

```python
@pn.component
def Inbox():
    msgs, set_msgs = pn.use_state([("a", "Hi"), ("b", "Hello")])
    return pn.Column(
        *[pn.Text(text, key=mid) for mid, text in msgs],
    )
```

Without `key=mid`, inserting a new message at index `0` would update
each existing `Text` in place rather than push them down, briefly
showing the wrong text in each row. With keys, the reconciler matches
"a" and "b" by identity, mounts the new row at index `0`, and shifts
the others without re-rendering them.

!!! tip "Choose keys from the data, not the position"
    `key=i` for `i in range(len(items))` is no better than no key at
    all. Use a stable identifier (database id, file path, etc.).

## Function components

A `@pn.component` function is treated as an element type just like
`"Text"` or `"Button"`. When the reconciler encounters one:

1. It looks up the function's hook state (or creates a fresh slot).
2. It calls the function with the current props inside an active hook
   context.
3. It recursively reconciles whatever the function returned: a single
   [`Element`][pythonnative.Element], a `list` of elements (which
   mount as siblings at the component's position), or `None` (which
   mounts nothing).

Hook slots are matched by their position in the function body, which is
why hooks must be called at the top level (not inside `if`/`for`). In
dev mode the reconciler verifies the hook call sequence on every
render and raises
[`HookOrderError`][pythonnative.HookOrderError] on a mismatch.

## Fragments and multi-child rendering

[`Fragment`][pythonnative.Fragment] groups siblings without a wrapping
native view: its children splice directly into the parent's native
child list. `None` and `False` children are dropped everywhere, so
conditional rendering with `cond and pn.Text(...)` needs no special
casing. A keyed Fragment participates in keyed diffing as one unit,
moving all of its children together.

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
observe the topmost value. Context is reactive: when a re-render
changes a Provider's value, the reconciler marks every recorded
consumer of that context dirty, so consumers re-render even when a
memoized ancestor in between skips its subtree.

```python
ThemeContext = pn.create_context({"primary": "#000"})

@pn.component
def Screen():
    return ThemeContext.Provider({"primary": "#222"}, Header())

@pn.component
def Header():
    theme = pn.use_context(ThemeContext)
    return pn.Text("Hi", style={"color": theme["primary"]})
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

- Use the [`Animated`][pythonnative.Animated] API: an
  [`AnimatedValue`][pythonnative.AnimatedValue] bound into an
  `Animated.View` style drives the native property directly, and
  when the platform can run the animation natively, no Python code
  runs per frame at all. See the
  [Animations guide](../guides/animations.md).
- Use [`use_ref`][pythonnative.use_ref] to hold a reference to a
  native view and mutate it directly from inside an effect callback.

Reach for these only when profiling tells you that re-rendering is the
bottleneck.

## Next steps

- Browse the algorithm in code: [Reconciler API](../api/reconciler.md).
- Understand handlers underneath the diff: [Native views](native-views.md).
- See how mounting interacts with hooks: [Lifecycle](lifecycle.md).
