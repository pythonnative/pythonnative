# Hosts

A screen host owns a [`Reconciler`][pythonnative.reconciler.Reconciler],
schedules re-renders, and forwards platform lifecycle events (resume,
pause, back press, destroy) to navigators and effects. It's also the
[`HostNavigator`][pythonnative.navigation.HostNavigator] a root
[`Stack.Navigator`][pythonnative.create_stack_navigator] talks to when
it pushes real native screens.

The bundled Android (`PNScreenFragment`) and iOS (`PNViewController`)
templates create a host through the `Host` native module's `create`
event and never need to be edited by app code; one
[`NativeScreenHost`][pythonnative.hosts.native.NativeScreenHost] class
serves both platforms because every platform-specific step goes over
the [bridge](../concepts/bridge.md). The desktop preview uses
[`DesktopScreenHost`][pythonnative.hosts.desktop.DesktopScreenHost].

::: pythonnative.hosts
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Shared host logic

::: pythonnative.hosts.base
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Platform hosts

::: pythonnative.hosts.native
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

::: pythonnative.hosts.desktop
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members: ["DesktopScreenHost"]
      filters: ["!^_"]

## Next steps

- Understand the render queue in [Lifecycle](../concepts/lifecycle.md).
- See how a root stack drives native screens in the
  [Navigation guide](../guides/navigation.md#native-screens).
