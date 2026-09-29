# Reconciler

Diffs successive element trees and applies the smallest set of native
mutations that bring the on-screen view tree in line with the new
description. The reconciler is platform-agnostic; it talks to native
widgets exclusively through a backend such as the
[`BridgeBackend`][pythonnative.native_views.bridge_backend.BridgeBackend]
or the in-memory [`FakeBackend`][pythonnative.testing.FakeBackend].
Renders are batched automatically (one flush per callback, effect, or
task step), and a flush that re-schedules itself more than fifty times
raises `RuntimeError("Too many re-renders")` through the nearest
[`ErrorBoundary`][pythonnative.ErrorBoundary].

::: pythonnative.reconciler
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members: false

## Core

::: pythonnative.reconciler.core
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      inherited_members: true
      filters: ["!^_"]

## Mounted nodes

::: pythonnative.reconciler.vnode
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Keyed children

::: pythonnative.reconciler.children
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- Read the high-level walkthrough in
  [Reconciliation](../concepts/reconciliation.md).
- See the backend the reconciler commits to in [Native views](native_views.md).
