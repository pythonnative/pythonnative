# Screen

The screen host owns a [`Reconciler`][pythonnative.reconciler.Reconciler],
schedules re-renders, and forwards platform lifecycle hooks (resume,
pause, destroy) to navigators and effects. The bundled
Android (`MainActivity`) and iOS (`ViewController`) templates create a
host via [`create_screen`][pythonnative.create_screen] and never need to
be edited by app code.

::: pythonnative.screen
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- Understand the render queue in [Lifecycle](../concepts/lifecycle.md).
- See how navigation hosts each screen in
  [`NavigationContainer`][pythonnative.NavigationContainer].
