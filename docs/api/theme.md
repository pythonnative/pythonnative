# Theme

One [`Theme`][pythonnative.Theme] holds the app's design tokens:
[`Colors`][pythonnative.Colors], [`Typography`][pythonnative.Typography],
a [`Spacing`][pythonnative.Spacing] scale, and [`Radii`][pythonnative.Radii].
Components read it with [`use_theme`][pythonnative.use_theme] and
derive styles from it once per theme with
[`use_styles`][pythonnative.use_styles]. The built-in navigators draw
their headers, tab bars, and drawers from the same tokens.
[`ThemeProvider`][pythonnative.ThemeProvider] supplies a light and a
dark theme and picks one from the effective color scheme; without it,
[`LIGHT_THEME`][pythonnative.LIGHT_THEME] and
[`DARK_THEME`][pythonnative.DARK_THEME] apply.

::: pythonnative.theme
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- Define themes, add tokens, and support dark mode in the
  [Styling guide](../guides/styling.md#themes).
- Build static styles with [`StyleSheet`][pythonnative.StyleSheet]; see
  [Style](style.md).
