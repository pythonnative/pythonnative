# Layout

The Python binding to Yoga's C++ flexbox engine. Headless tests use
[`LayoutNode`][pythonnative.layout.LayoutNode] and
[`calculate_layout`][pythonnative.layout.calculate_layout] to compute
frames `(x, y, width, height)` with stub intrinsic measurements.

Mobile renderers compile the same Yoga core into their native libraries and
measure content beside their widgets. The browser preview runs Yoga
WebAssembly. Those renderers return changed frames to the Python reconciler
through the bridge.

For a conceptual overview, see [Layout engine](../concepts/layout.md).

::: pythonnative.layout
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- Browse the supported style keys:
  [Component properties](component-properties.md).
- See how leaf widgets contribute their intrinsic size:
  [Native views](native_views.md).
- Read the conceptual walkthrough:
  [Layout engine](../concepts/layout.md).
