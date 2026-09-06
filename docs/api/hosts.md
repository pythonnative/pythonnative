# Hosts

An application surface host owns a
[`Reconciler`][pythonnative.reconciler.Reconciler], schedules Python work,
and forwards lifecycle, viewport, and back events. Its logical tree includes
screens, overlays, and mounted list rows. Native containers present those
children without creating a separate Python host for every screen or row.

The host also publishes cached navigation restoration state through the
`Host` module. It implements the
[`HostNavigator`][pythonnative.navigation.HostNavigator] interface used by
navigation and headless tests.

The bundled Android (`PNScreenFragment`) and iOS (`PNViewController`)
templates create a host through the `Host` native module's `create`
event and never need to be edited by app code; one
[`NativeScreenHost`][pythonnative.hosts.native.NativeScreenHost] class
serves both platforms because every platform-specific step goes over
the [bridge](../concepts/bridge.md). The browser preview uses the same
class: its page is a bridge peer that speaks the `Host` module protocol
over a WebSocket (see
[`WebTransport`][pythonnative.bridge.web.WebTransport]).

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

## Next steps

- Understand the render queue in [Lifecycle](../concepts/lifecycle.md).
- See how a root stack drives native screens in the
  [Navigation guide](../guides/navigation.md#native-screens).
