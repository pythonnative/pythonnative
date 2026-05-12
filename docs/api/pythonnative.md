# Package overview

PythonNative re-exports a small public surface from
`pythonnative/__init__.py`. Most user code only ever touches the names
in this overview; deeper internals (`reconciler`, `native_views`,
`page`) are documented for contributors and integrators.

## Entry point

Your app module defines a top-level component named `App`:

```python
import pythonnative as pn

@pn.component
def App():
    return pn.NavigationContainer(...)
```

The bundled Android `ScreenFragment` and iOS `ViewController` load
your app by **module path** (`"app.main"`) and look up the
module's top-level `App` attribute. There is no registration step
or imperative bootstrap call. If you need to expose a
differently-named root component, configure the templates to load
an explicit dotted path like `"app.main.RootScreen"` instead.

::: pythonnative
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members: false

## Where to look next

The reference is split per module so each page stays scannable:

| Area | Page | Key symbols |
|---|---|---|
| Element factories | [Components](components.md) | [`Text`][pythonnative.Text], [`Button`][pythonnative.Button], [`Column`][pythonnative.Column], [`Row`][pythonnative.Row], [`ScrollView`][pythonnative.ScrollView], [`FlatList`][pythonnative.FlatList], [`SectionList`][pythonnative.SectionList], [`Modal`][pythonnative.Modal], [`Pressable`][pythonnative.Pressable], [`StatusBar`][pythonnative.StatusBar], [`KeyboardAvoidingView`][pythonnative.KeyboardAvoidingView], [`RefreshControl`][pythonnative.RefreshControl], [`Picker`][pythonnative.Picker], [`ErrorBoundary`][pythonnative.ErrorBoundary] |
| Hooks | [Hooks](hooks.md) | [`use_state`][pythonnative.use_state], [`use_reducer`][pythonnative.use_reducer], [`use_effect`][pythonnative.use_effect], [`use_memo`][pythonnative.use_memo], [`use_ref`][pythonnative.use_ref], [`use_context`][pythonnative.use_context], [`use_window_dimensions`][pythonnative.use_window_dimensions], [`use_safe_area_insets`][pythonnative.use_safe_area_insets], [`use_keyboard_height`][pythonnative.use_keyboard_height] |
| Animations | [Animated](animated.md) | `Animated`, [`AnimatedValue`][pythonnative.AnimatedValue] |
| System dialogs | [Alerts](alerts.md) | [`Alert`][pythonnative.Alert] |
| Platform | [Platform](platform.md) | [`Platform`][pythonnative.Platform] |
| Navigation | [Navigation](navigation.md) | [`NavigationContainer`][pythonnative.NavigationContainer], [`create_stack_navigator`][pythonnative.create_stack_navigator], [`create_tab_navigator`][pythonnative.create_tab_navigator], [`create_drawer_navigator`][pythonnative.create_drawer_navigator], [`use_navigation`][pythonnative.use_navigation] |
| Styling | [Style](style.md) | [`StyleSheet`][pythonnative.StyleSheet], [`ThemeContext`][pythonnative.style.ThemeContext] |
| Element descriptor | [Element](element.md) | [`Element`][pythonnative.Element] |
| Screen host | [Screen](screen.md) | [`create_screen`][pythonnative.create_screen] |
| Reconciler | [Reconciler](reconciler.md) | [`Reconciler`][pythonnative.reconciler.Reconciler] |
| Native modules | [Native modules](native_modules.md) | `Camera`, `Location`, `FileSystem`, `Notifications` |
| Native views | [Native views](native_views.md) | [`NativeViewRegistry`][pythonnative.native_views.NativeViewRegistry], [`ViewHandler`][pythonnative.native_views.base.ViewHandler] |
| Hot reload | [Hot reload](hot_reload.md) | [`FileWatcher`][pythonnative.hot_reload.FileWatcher], [`ModuleReloader`][pythonnative.hot_reload.ModuleReloader] |
| Utilities | [Utilities](utils.md) | `IS_ANDROID`, `IS_IOS`, [`get_android_context`][pythonnative.utils.get_android_context] |
| CLI | [CLI (`pn`)](cli.md) | `pn init`, `pn run`, `pn clean` |

## Property reference

All visual and layout properties pass through the `style` dict (or a
list of dicts). The full per-component property catalogue lives in
[Component properties](component-properties.md).
