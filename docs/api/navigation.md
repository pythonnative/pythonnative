# Navigation

Typed stack, tab, and drawer navigators. Screens are components whose
parameters are their route params, listed in module-level
[`StackNavigator`][pythonnative.StackNavigator],
[`TabNavigator`][pythonnative.TabNavigator], and
[`DrawerNavigator`][pythonnative.DrawerNavigator] values with
[`Screen`][pythonnative.Screen] and [`Group`][pythonnative.Group]. A
[`NavigationContainer`][pythonnative.NavigationContainer] renders the
root navigator and derives deep links from each screen's `path`.
Screens navigate through the [`Navigation`][pythonnative.Navigation]
handle from [`use_navigation`][pythonnative.use_navigation]
(`nav.push(ItemScreen(id=42))`) and set their options with
[`use_screen_options`][pythonnative.use_screen_options]. Code outside
the tree navigates through a
[`NavigationRef`][pythonnative.NavigationRef]. Navigator chrome takes
its colors from the app [`Theme`][pythonnative.Theme].

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
      members: ["LinkTable"]

## Navigation ref

::: pythonnative.navigation.ref
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

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
