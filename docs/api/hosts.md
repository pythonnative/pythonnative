# Hosts

A screen host owns a [`Reconciler`][pythonnative.reconciler.Reconciler],
schedules re-renders, and forwards platform lifecycle events (resume,
pause, back press, destroy) to navigators and effects. It's also the
[`HostNavigator`][pythonnative.navigation.HostNavigator] a root
[`Stack.Navigator`][pythonnative.create_stack_navigator] talks to when
it pushes real native screens.

The bundled Android (`ScreenFragment`) and iOS (`ViewController`)
templates create a host via [`create_screen`][pythonnative.create_screen]
and never need to be edited by app code. The desktop preview uses
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

::: pythonnative.hosts.android
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members: ["AndroidScreenHost"]
      filters: ["!^_"]

::: pythonnative.hosts.ios
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members: ["IOSScreenHost"]
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
