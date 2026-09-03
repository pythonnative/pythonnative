# Package overview

PythonNative re-exports a small public surface from
`pythonnative/__init__.py`. Most user code only ever touches the names
in this overview; deeper internals (`reconciler`, `native_views`,
`hosts`) are documented for contributors and integrators.

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
| Component model | [Component](component.md) | [`component`][pythonnative.component.component], [`Component`][pythonnative.Component], [`memo`][pythonnative.memo] |
| Element factories | [Components](components.md) | [`Text`][pythonnative.Text], [`Button`][pythonnative.Button], [`Column`][pythonnative.Column], [`Row`][pythonnative.Row], [`ScrollView`][pythonnative.ScrollView], [`FlatList`][pythonnative.FlatList], [`SectionList`][pythonnative.SectionList], [`Modal`][pythonnative.Modal], [`Pressable`][pythonnative.Pressable], [`StatusBar`][pythonnative.StatusBar], [`KeyboardAvoidingView`][pythonnative.KeyboardAvoidingView], [`RefreshControl`][pythonnative.RefreshControl], [`Picker`][pythonnative.Picker], [`Fragment`][pythonnative.Fragment], [`Portal`][pythonnative.Portal], [`ErrorBoundary`][pythonnative.ErrorBoundary] |
| Hooks | [Hooks](hooks.md) | [`use_state`][pythonnative.use_state], [`use_reducer`][pythonnative.use_reducer], [`use_effect`][pythonnative.use_effect], [`use_layout_effect`][pythonnative.use_layout_effect], [`use_memo`][pythonnative.use_memo], [`use_ref`][pythonnative.use_ref], [`use_imperative_handle`][pythonnative.use_imperative_handle], [`use_context`][pythonnative.use_context], [`use_back_handler`][pythonnative.use_back_handler], [`use_window_dimensions`][pythonnative.use_window_dimensions], [`use_safe_area_insets`][pythonnative.use_safe_area_insets], [`use_keyboard_height`][pythonnative.use_keyboard_height], [`use_color_scheme`][pythonnative.use_color_scheme], [`use_resource`][pythonnative.use_resource], [`use_transition`][pythonnative.use_transition], [`use_deferred_value`][pythonnative.use_deferred_value], [`create_context`][pythonnative.create_context] |
| Suspense | [Suspense](suspense.md) | [`Suspense`][pythonnative.Suspense], [`Resource`][pythonnative.Resource], [`start_resource`][pythonnative.start_resource], [`lazy`][pythonnative.lazy] |
| Animations | [Animated](animated.md) | `Animated`, [`AnimatedValue`][pythonnative.AnimatedValue], [`use_animated_value`][pythonnative.use_animated_value] |
| System dialogs | [Alerts](alerts.md) | [`Alert`][pythonnative.Alert] |
| Platform | [Platform](platform.md) | [`Platform`][pythonnative.Platform] |
| Navigation | [Navigation](navigation.md) | [`NavigationContainer`][pythonnative.NavigationContainer], [`create_stack_navigator`][pythonnative.create_stack_navigator], [`create_tab_navigator`][pythonnative.create_tab_navigator], [`create_drawer_navigator`][pythonnative.create_drawer_navigator], [`Navigation`][pythonnative.Navigation], [`use_navigation`][pythonnative.use_navigation], [`use_route`][pythonnative.use_route], [`use_is_focused`][pythonnative.use_is_focused], [`LinkingConfig`][pythonnative.LinkingConfig] |
| Testing | [Testing](testing.md) | [`render`][pythonnative.testing.render], [`render_hook`][pythonnative.testing.render_hook], [`FakeBackend`][pythonnative.testing.FakeBackend], [`FakeHost`][pythonnative.testing.FakeHost] |
| Styling | [Style](style.md) | [`StyleSheet`][pythonnative.StyleSheet], [`Style`][pythonnative.style.Style], [`StyleProp`][pythonnative.style.StyleProp], [`style`][pythonnative.style.style], [`ThemeContext`][pythonnative.style.ThemeContext], [`use_theme`][pythonnative.use_theme] |
| Appearance | [Appearance](appearance.md) | [`use_color_scheme`][pythonnative.use_color_scheme], `appearance.set_color_scheme`, `appearance.get_color_scheme` |
| Images | [Images](images.md) | `images.fetch`, `images.clear_cache` |
| Element descriptor | [Element](element.md) | [`Element`][pythonnative.Element] |
| Screen host | [Hosts](hosts.md) | [`create_screen`][pythonnative.create_screen], [`ScreenHost`][pythonnative.hosts.base.ScreenHost] |
| Reconciler | [Reconciler](reconciler.md) | [`Reconciler`][pythonnative.reconciler.Reconciler] |
| Native modules | [Native modules](native_modules.md) | `Camera`, `Location`, `FileSystem`, `Notifications` |
| Native views | [Native views](native_views.md) | [`NativeViewRegistry`][pythonnative.native_views.NativeViewRegistry], [`ViewHandler`][pythonnative.native_views.base.ViewHandler] |
| Mutation ops | [Mutation ops](mutations.md) | [`CreateOp`][pythonnative.mutations.CreateOp], [`UpdateOp`][pythonnative.mutations.UpdateOp], [`InsertOp`][pythonnative.mutations.InsertOp], [`DestroyOp`][pythonnative.mutations.DestroyOp], [`SetFrameOp`][pythonnative.mutations.SetFrameOp] |
| Event routing | [Events](events.md) | [`EventRegistry`][pythonnative.events.EventRegistry], [`dispatch_event`][pythonnative.events.dispatch_event], [`extract_events`][pythonnative.events.extract_events] |
| Platform metrics | [Platform metrics](platform_metrics.md) | [`SafeAreaInsets`][pythonnative.platform_metrics.SafeAreaInsets], [`WindowDimensions`][pythonnative.platform_metrics.WindowDimensions], [`subscribe`][pythonnative.platform_metrics.subscribe] |
| Hot reload | [Hot reload](hot_reload.md) | [`FileWatcher`][pythonnative.hot_reload.FileWatcher], [`ModuleReloader`][pythonnative.hot_reload.ModuleReloader] |
| Diagnostics | [Diagnostics](diagnostics.md) | [`HookOrderError`][pythonnative.HookOrderError], [`warn`][pythonnative.diagnostics.warn], [`is_dev`][pythonnative.diagnostics.is_dev], [`report_error`][pythonnative.diagnostics.report_error] |
| Custom components SDK | [SDK](sdk.md) | [`Props`][pythonnative.sdk._components.Props], [`ViewHandler`][pythonnative.native_views.base.ViewHandler], [`native_component`][pythonnative.sdk._components.native_component], [`register_component`][pythonnative.sdk._components.register_component], [`element_factory`][pythonnative.sdk._components.element_factory] |
| Utilities | [Utilities](utils.md) | `IS_ANDROID`, `IS_IOS`, `IS_DESKTOP` |
| CLI | [CLI (`pn`)](cli.md) | `pn init`, `pn run`, `pn clean` |

## Property reference

All visual and layout properties pass through the `style` dict (or a
list of dicts). The full per-component property catalogue lives in
[Component properties](component-properties.md).
