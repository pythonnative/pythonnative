# Mental model

PythonNative is a *thin* layer over native UIKit and Android view
hierarchies, with a React-style component model on top. If you have
worked with React Native, the surface API will feel familiar; the
runtime, however, is meaningfully different.

## TL;DR

- `@pn.component` functions return immutable
  [`Element`][pythonnative.Element] descriptors. Nothing is mounted
  until the [`Reconciler`][pythonnative.reconciler.Reconciler] commits
  the tree.
- Hooks ([`use_state`][pythonnative.use_state],
  [`use_effect`][pythonnative.use_effect], etc.) drive re-renders.
  State updates are batched per render pass.
- Re-rendering produces a new tree; the reconciler diffs it against
  the previous one and applies the smallest set of native mutations.
- Native widgets are created and updated by Swift and Kotlin
  component managers that receive one serialized transaction per
  commit over the [native bridge](bridge.md). There is no JavaScript
  and no V8 / Hermes runtime.

## The runtime in one diagram

```text
@pn.component fn   --->   Element tree   --->   Reconciler   --->   Native views
        ^                                            |
        |                                            v
   set_state()   <---------   schedule re-render   batched   --->   diff + patch
                                                                          |
                                                                          v
                                                                     flush effects
```

Each render pass has three phases:

1. **Render**: component functions run; hooks record state reads,
   queue effects, register memos. No native widgets change yet.
2. **Commit**: the reconciler applies the diff to native views,
   creating, updating, and removing widgets through the registered
   [`ViewHandler`][pythonnative.native_views.base.ViewHandler]
   implementations.
3. **Effect**: pending [`use_effect`][pythonnative.use_effect]
   callbacks fire in depth-first order; cleanups from the previous
   render run before the new callbacks.

If an effect sets state, the loop kicks off again (with a safety cap
that prevents render storms).

## How PythonNative differs from React Native

| Concept | React Native | PythonNative |
|---|---|---|
| Component language | JavaScript / TypeScript | Python |
| Bridge | Fabric: one C++ shadow tree commit per render; TurboModules for device APIs | One JSON transaction per commit applied by Swift / Kotlin component managers; named native modules for device APIs |
| Threading | UI runs on the main thread; JS on a separate thread | UI and reconciler both on the platform's main thread |
| Distribution | Metro bundler ships a JS bundle | The `pn` CLI bundles your `app/` and the `pythonnative` package into the native project |
| Hot reload | Metro fast refresh of the JS bundle | `FileWatcher` plus `ModuleReloader` reloads `.py` modules in place |
| Native widgets | Wrapped by Fabric component managers | Wrapped by `PNComponentManager` (Swift) / `ComponentManager` (Kotlin) classes |

The single most important consequence: there is **no async boundary**
between Python and the native widget. Reading a label's text in Python
is a synchronous JNI / Objective-C method call. That keeps the model
small (no message-passing protocol, no serialization) and lets native
APIs that expect synchronous, on-thread access just work.

## How PythonNative differs from Toga, BeeWare, Kivy

- Toga and Kivy are imperative widget toolkits. PythonNative is
  declarative: you describe the tree per render, and the reconciler
  figures out the diff.
- Kivy renders its own widgets via OpenGL. PythonNative renders
  *real* native widgets, so your buttons look like UIKit buttons on
  iOS and Material buttons on Android, and accessibility just works.
- BeeWare's Briefcase is a packaging story; PythonNative ships its
  own `pn` CLI for the same purpose, plus a UI runtime.

## Mental shortcuts

When something feels surprising, fall back on these rules:

!!! tip "It's just Python"
    There is no compiler, no transpiler, and no JS runtime.
    `print(x)` reaches the device console; `import foo` runs the
    bundled module. If a stack trace mentions `pythonnative.*`, you
    can open that file in your editor and read the source.

!!! tip "Components are functions"
    Each call to a `@component` function should produce the same
    output for the same input plus current hook state. Side effects
    belong in [`use_effect`][pythonnative.use_effect].

!!! tip "Native widgets are real"
    A `pn.Text` becomes a `UILabel` or a `TextView`. Anything you can
    do to those in their respective SDKs, you can usually do via a
    custom [`ViewHandler`][pythonnative.native_views.base.ViewHandler].

## Next steps

- See the runtime in detail: [Architecture](architecture.md).
- Walk through a render: [Lifecycle](lifecycle.md).
- Learn how trees are diffed: [Reconciliation](reconciliation.md).
