# Navigation

A React Navigation-style API: a
[`NavigationContainer`][pythonnative.NavigationContainer] holds one or
more navigators (stack, tab, or drawer), and any descendant component
can navigate through the [`Navigation`][pythonnative.Navigation] handle
from [`use_navigation`][pythonnative.use_navigation] or read its
current [`Route`][pythonnative.navigation.Route] with
[`use_route`][pythonnative.use_route].

::: pythonnative.navigation
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members: false

## Navigators

::: pythonnative.navigation.navigators
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Container and deep linking

::: pythonnative.navigation.container
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members: ["NavigationContainer"]

::: pythonnative.navigation.linking
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members: ["LinkingConfig"]

## Hooks

::: pythonnative.navigation.hooks
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## The `Navigation` handle

::: pythonnative.navigation.handle
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Screens and options

::: pythonnative.navigation.screen
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## State

::: pythonnative.navigation.state
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Host bridge

::: pythonnative.navigation.host
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- See worked examples in the [Navigation guide](../guides/navigation.md).
- Test flows without a device using
  [`FakeHost`][pythonnative.testing.FakeHost].
