# Platform metrics

Platform-level metrics shared between screen hosts and native view handlers.
The screen host writes window metrics, safe-area insets, and keyboard heights,
which view handlers query on demand in layout units (`pt` on iOS, `dp` on Android)
to size bars and insets correctly without manual threading through measurement signatures.

::: pythonnative.platform_metrics
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- See how platform detection works in [Platform](platform.md).
- Learn how screens host root views in [Screen](screen.md).
- Read about platform and accessibility integration in the [Platform & Accessibility guide](../guides/platform-accessibility.md).
