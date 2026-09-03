# Preview

The desktop preview is the engine behind `pn preview`: it renders an
app in a real OS window through the Tkinter backend, with Fast
Refresh on every save. [`run_preview`][pythonnative.preview.run_preview]
opens the window and runs until it closes, and
[`DesktopApp`][pythonnative.preview.DesktopApp] owns the navigation
stack inside it.

::: pythonnative.preview
    options:
        show_root_heading: false
        show_root_toc_entry: false
        members_order: source
        filters: ["!^_"]

## Next steps

- See the workflow in the [Desktop preview guide](../guides/desktop-preview.md).