# Package overview

PythonNative re-exports a small public surface from
`pythonnative/__init__.py`. Most user code only ever touches the names
in this overview. Opt-in device features live in
[capability](../guides/capabilities/index.md) subpackages, and deeper
internals (`reconciler`, `native_views`, `hosts`) are documented for
contributors and integrators.

## Entry point

Your app module defines a top-level component named `App`:

```python
import pythonnative as pn


@pn.component
def HomeScreen() -> pn.Node:
    return pn.Text("Hello from PythonNative")


Root = pn.StackNavigator(HomeScreen)


@pn.component
def App() -> pn.Node:
    return pn.NavigationContainer(Root)
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

## Top-level exports

These are all the names in `pythonnative.__all__`:

| Area | Page | Names |
|---|---|---|
| Component model | [Component](component.md), [Element](element.md) | [`component`][pythonnative.component.component], [`Component`][pythonnative.Component], [`memo`][pythonnative.memo], [`Element`][pythonnative.Element], [`Node`][pythonnative.element.Node] |
| Element factories | [Components](components.md), [Component properties](component-properties.md) | [`ActivityIndicator`][pythonnative.ActivityIndicator], [`BlurView`][pythonnative.BlurView], [`Button`][pythonnative.Button], [`Checkbox`][pythonnative.Checkbox], [`Column`][pythonnative.Column], [`DatePicker`][pythonnative.DatePicker], [`ErrorBoundary`][pythonnative.ErrorBoundary], [`FlatList`][pythonnative.FlatList], [`Fragment`][pythonnative.Fragment], `Icon`, `Image`, `ImageBackground`, [`KeyboardAvoidingView`][pythonnative.KeyboardAvoidingView], [`LinearGradient`][pythonnative.LinearGradient], [`Modal`][pythonnative.Modal], [`Picker`][pythonnative.Picker], [`Portal`][pythonnative.Portal], [`Pressable`][pythonnative.Pressable], [`ProgressBar`][pythonnative.ProgressBar], [`RefreshControl`][pythonnative.RefreshControl], [`Row`][pythonnative.Row], [`SafeAreaView`][pythonnative.SafeAreaView], [`ScrollView`][pythonnative.ScrollView], [`SectionList`][pythonnative.SectionList], [`SegmentedControl`][pythonnative.SegmentedControl], [`Slider`][pythonnative.Slider], [`Spacer`][pythonnative.Spacer], [`StatusBar`][pythonnative.StatusBar], [`Suspense`][pythonnative.Suspense], `Svg`, [`Switch`][pythonnative.Switch], [`Text`][pythonnative.Text], [`TextInput`][pythonnative.TextInput], [`View`][pythonnative.View], [`WebView`][pythonnative.WebView] |
| Component helpers | [Components](components.md) | `ImageSource`, [`ListController`][pythonnative.ListController], `ListData`, `Section`, `ViewableItem`, [`PressState`][pythonnative.PressState], [`Ripple`][pythonnative.Ripple], `IconName` |
| Shared props | [Components](components.md#shared-props) | [`AccessibilityProps`][pythonnative.AccessibilityProps], [`CommonProps`][pythonnative.CommonProps], [`MotionProps`][pythonnative.MotionProps], [`ViewProps`][pythonnative.ViewProps] |
| Typed event payloads | [Components](components.md#typed-event-payloads) | [`ContentSizeEvent`][pythonnative.ContentSizeEvent], [`ImageLoadEvent`][pythonnative.ImageLoadEvent], [`KeyPressEvent`][pythonnative.KeyPressEvent], [`LayoutEvent`][pythonnative.LayoutEvent], [`ScrollEvent`][pythonnative.ScrollEvent], [`SelectionEvent`][pythonnative.SelectionEvent], [`WebNavigationEvent`][pythonnative.WebNavigationEvent] |
| Imperative handles | [Handles](handles.md) | [`ScrollOffset`][pythonnative.ScrollOffset], [`ScrollViewHandle`][pythonnative.ScrollViewHandle], [`TextInputHandle`][pythonnative.TextInputHandle], [`ViewHandle`][pythonnative.ViewHandle], [`WebViewHandle`][pythonnative.WebViewHandle] |
| Hooks | [Hooks](hooks.md) | [`ColorScheme`][pythonnative.hooks.ColorScheme], [`Context`][pythonnative.Context], [`Deps`][pythonnative.Deps], [`MutationCall`][pythonnative.MutationCall], [`MutationState`][pythonnative.MutationState], [`QueryResult`][pythonnative.QueryResult], [`Ref`][pythonnative.Ref], [`batch_updates`][pythonnative.batch_updates], [`create_context`][pythonnative.create_context], [`use_back_handler`][pythonnative.use_back_handler], [`use_callback`][pythonnative.use_callback], [`use_color_scheme`][pythonnative.use_color_scheme], [`use_context`][pythonnative.use_context], [`use_deferred_value`][pythonnative.use_deferred_value], [`use_effect`][pythonnative.use_effect], [`use_imperative_handle`][pythonnative.use_imperative_handle], [`use_keyboard_height`][pythonnative.use_keyboard_height], [`use_layout_effect`][pythonnative.use_layout_effect], [`use_memo`][pythonnative.use_memo], [`use_mutation`][pythonnative.use_mutation], [`use_persisted_state`][pythonnative.use_persisted_state], [`use_query`][pythonnative.use_query], [`use_reducer`][pythonnative.use_reducer], [`use_ref`][pythonnative.use_ref], [`use_resource`][pythonnative.use_resource], [`use_safe_area_insets`][pythonnative.use_safe_area_insets], [`use_state`][pythonnative.use_state], [`use_subscription`][pythonnative.use_subscription], [`use_transition`][pythonnative.use_transition], [`use_window_dimensions`][pythonnative.use_window_dimensions] |
| Suspense | [Suspense](suspense.md) | [`Resource`][pythonnative.Resource], [`lazy`][pythonnative.lazy], [`start_resource`][pythonnative.start_resource] |
| Navigation | [Navigation](navigation.md) | [`DrawerNavigator`][pythonnative.DrawerNavigator], `Group`, [`Navigation`][pythonnative.Navigation], [`NavigationContainer`][pythonnative.NavigationContainer], [`NavigationRef`][pythonnative.NavigationRef], `NavigationState`, `Navigator`, `Route`, `Screen`, [`ScreenOptions`][pythonnative.ScreenOptions], [`StackNavigator`][pythonnative.StackNavigator], [`TabBarStyle`][pythonnative.TabBarStyle], [`TabNavigator`][pythonnative.TabNavigator], [`use_focus_effect`][pythonnative.use_focus_effect], [`use_is_focused`][pythonnative.use_is_focused], [`use_navigation`][pythonnative.use_navigation], [`use_route`][pythonnative.use_route], [`use_screen_options`][pythonnative.use_screen_options] |
| Styling | [Style](style.md) | [`ABSOLUTE_FILL`][pythonnative.style.ABSOLUTE_FILL], [`AccessibilityAction`][pythonnative.AccessibilityAction], [`AccessibilityState`][pythonnative.AccessibilityState], [`AccessibilityValue`][pythonnative.AccessibilityValue], [`Color`][pythonnative.Color], [`DynamicColor`][pythonnative.DynamicColor], [`EdgeInsets`][pythonnative.EdgeInsets], [`ShadowOffset`][pythonnative.ShadowOffset], [`Style`][pythonnative.style.Style], [`StyleProp`][pythonnative.style.StyleProp], [`StyleSheet`][pythonnative.StyleSheet], [`style`][pythonnative.style.style] |
| Theming | [Theme](theme.md) | [`Colors`][pythonnative.Colors], [`DARK_THEME`][pythonnative.DARK_THEME], [`LIGHT_THEME`][pythonnative.LIGHT_THEME], [`Radii`][pythonnative.Radii], [`Spacing`][pythonnative.Spacing], [`Theme`][pythonnative.Theme], [`ThemeProvider`][pythonnative.ThemeProvider], [`Typography`][pythonnative.Typography], [`use_styles`][pythonnative.use_styles], [`use_theme`][pythonnative.use_theme] |
| Appearance | [Appearance](appearance.md) | `appearance` |
| Assets and graphics | [Assets](assets.md), [Graphics](graphics.md) | `Asset`, `asset`, `icons`, `svg` |
| Motion | [Motion](motion.md) | [`worklet`][pythonnative.worklet], [`SharedValue`][pythonnative.SharedValue], [`AnimatedStyle`][pythonnative.AnimatedStyle], [`FrameInfo`][pythonnative.FrameInfo], [`use_shared_value`][pythonnative.use_shared_value], [`use_derived_value`][pythonnative.use_derived_value], [`use_animated_style`][pythonnative.use_animated_style], [`use_animated_reaction`][pythonnative.use_animated_reaction], [`use_frame_callback`][pythonnative.use_frame_callback], [`with_timing`][pythonnative.with_timing], [`with_spring`][pythonnative.with_spring], [`with_decay`][pythonnative.with_decay], [`with_delay`][pythonnative.with_delay], [`with_sequence`][pythonnative.with_sequence], [`with_repeat`][pythonnative.with_repeat], [`Easing`][pythonnative.Easing], [`Spring`][pythonnative.Spring], [`interpolate`][pythonnative.interpolate], [`interpolate_color`][pythonnative.interpolate_color], [`clamp`][pythonnative.clamp], [`snap_point`][pythonnative.snap_point], [`run_on_python`][pythonnative.run_on_python] |
| Components built on Motion | [Components](components.md#components-built-on-motion) | [`BottomSheet`][pythonnative.BottomSheet], [`BottomSheetHandle`][pythonnative.BottomSheetHandle], [`Swipeable`][pythonnative.Swipeable], [`SwipeableHandle`][pythonnative.SwipeableHandle] |
| Gestures | [Gestures](gestures.md) | `GestureSpec`, [`SwipeDirection`][pythonnative.SwipeDirection], `gestures` |
| System dialogs | [Alerts](alerts.md) | [`Alert`][pythonnative.Alert] |
| Device and environment | [Native modules](native_modules.md) | [`AccessibilityEvent`][pythonnative.AccessibilityEvent], [`AccessibilityInfo`][pythonnative.AccessibilityInfo], [`Device`][pythonnative.Device], [`DeviceInfo`][pythonnative.DeviceInfo], [`Dimensions`][pythonnative.Dimensions], [`DimensionsEvent`][pythonnative.DimensionsEvent], [`Keyboard`][pythonnative.Keyboard], [`KeyboardEvent`][pythonnative.KeyboardEvent], [`Locale`][pythonnative.Locale], [`Localization`][pythonnative.Localization], [`PixelRatio`][pythonnative.PixelRatio], [`WindowDimensions`][pythonnative.WindowDimensions], [`use_locales`][pythonnative.use_locales], [`use_reduce_motion`][pythonnative.use_reduce_motion], [`use_screen_reader_enabled`][pythonnative.use_screen_reader_enabled] |
| System services | [Native modules](native_modules.md), [Images](images.md) | [`AppState`][pythonnative.AppState], [`Battery`][pythonnative.Battery], [`Clipboard`][pythonnative.Clipboard], [`FileSystem`][pythonnative.FileSystem], [`Haptics`][pythonnative.Haptics], [`ImageSize`][pythonnative.ImageSize], [`Images`][pythonnative.Images], [`Linking`][pythonnative.Linking], [`NetInfo`][pythonnative.NetInfo], [`Permissions`][pythonnative.Permissions], [`SecureStore`][pythonnative.SecureStore], [`Share`][pythonnative.Share], [`use_app_state`][pythonnative.use_app_state], [`use_net_info`][pythonnative.use_net_info] |
| App state and persistence | [Store](store.md), [Storage](storage.md) | [`AsyncStorage`][pythonnative.AsyncStorage], [`Store`][pythonnative.Store], [`use_store`][pythonnative.use_store] |
| Networking | [Network](net.md) | [`HTTPError`][pythonnative.HTTPError], [`Response`][pythonnative.Response], [`WebSocket`][pythonnative.WebSocket], [`WebSocketClosed`][pythonnative.WebSocketClosed], [`WebSocketError`][pythonnative.WebSocketError], [`fetch`][pythonnative.fetch] |
| Async runtime | [Async runtime](runtime.md) | [`run_async`][pythonnative.run_async], [`run_blocking`][pythonnative.run_blocking] |
| Failure handling | [Diagnostics](diagnostics.md), [Error boundaries](../guides/error-boundaries.md) | [`HookOrderError`][pythonnative.HookOrderError], [`set_error_fallback`][pythonnative.set_error_fallback], [`set_error_handler`][pythonnative.set_error_handler] |
| Platform | [Platform](platform.md) | [`Platform`][pythonnative.Platform] |
| Native extension SDK | [SDK](sdk.md) | [`Props`][pythonnative.Props], [`define_component`][pythonnative.define_component], `sdk` |

## Everything else

These modules aren't re-exported at the top level, so import them by name.

### Capabilities

Opt-in device features, each a subpackage you enable with `[plugins].use`. See
[Capabilities](../guides/capabilities/index.md).

| Import | Page | Key symbols |
|---|---|---|
| `pythonnative.audio` | [Audio](audio.md) | `Sound`, `Recorder` |
| `pythonnative.background` | [Background](background.md) | `task`, `schedule` |
| `pythonnative.biometrics` | [Biometrics](biometrics.md) | `Biometrics` |
| `pythonnative.camera` | [Camera](camera.md) | `Camera`, `CameraView` |
| `pythonnative.location` | [Location](location.md) | `Location`, `Position` |
| `pythonnative.maps` | [Maps](maps.md) | `MapView`, `Marker`, `Polyline`, `Region` |
| `pythonnative.notifications` | [Notifications](notifications.md) | `Notifications` |
| `pythonnative.pickers` | [Pickers](pickers.md) | `pick_images`, `pick_videos`, `pick_documents` |
| `pythonnative.purchases` | [Purchases](purchases.md) | `Purchases` |
| `pythonnative.push` | [Push](push.md) | `Push` |
| `pythonnative.sensors` | [Sensors](sensors.md) | `Accelerometer`, `Barometer`, `Gyroscope`, `Magnetometer` |
| `pythonnative.video` | [Video](video.md) | `Video`, `VideoHandle` |

### Other modules

| Area | Page | Key symbols |
|---|---|---|
| Style helpers and aliases | [Style](style.md) | [`resolve_style`][pythonnative.style.resolve_style], [`Dimension`][pythonnative.style.Dimension], `FlexDirection`, `JustifyContent`, `AlignItems`, and the other aliases |
| Gesture descriptors | [Gestures](gestures.md) | [`Tap`][pythonnative.gestures.Tap], [`LongPress`][pythonnative.gestures.LongPress], [`Pan`][pythonnative.gestures.Pan], [`Swipe`][pythonnative.gestures.Swipe], [`Fling`][pythonnative.gestures.Fling], [`Pinch`][pythonnative.gestures.Pinch], [`Rotation`][pythonnative.gestures.Rotation], [`GestureEvent`][pythonnative.gestures.GestureEvent] |
| Layout animations, shared elements, and worklet errors | [Motion](motion.md) | [`FadeIn`][pythonnative.motion.FadeIn], [`FadeOut`][pythonnative.motion.FadeOut], [`SlideIn`][pythonnative.motion.SlideIn], [`SlideOut`][pythonnative.motion.SlideOut], [`ZoomIn`][pythonnative.motion.ZoomIn], [`ZoomOut`][pythonnative.motion.ZoomOut], [`LinearTransition`][pythonnative.motion.LinearTransition], [`FadingTransition`][pythonnative.motion.FadingTransition], [`Keyframes`][pythonnative.motion.Keyframes], [`LayoutAnimationConfig`][pythonnative.motion.LayoutAnimationConfig], [`SharedTransition`][pythonnative.motion.SharedTransition], [`WorkletError`][pythonnative.motion.WorkletError] (all in `pythonnative.motion`) |
| Extension SDK | [SDK](sdk.md) | [`element_factory`][pythonnative.sdk.element_factory], `UNSET`, `UnsetType`, `plugin_module`, `plugin_component` |
| Deep links | [Navigation](navigation.md) | [`LinkTable`][pythonnative.navigation.LinkTable] |
| Testing | [Testing](testing.md) | [`render`][pythonnative.testing.render], [`render_hook`][pythonnative.testing.render_hook], [`within`][pythonnative.testing.within], [`wait_for`][pythonnative.testing.wait_for], [`fake_clock`][pythonnative.testing.fake_clock], [`FakeBackend`][pythonnative.testing.FakeBackend], [`FakeHost`][pythonnative.testing.FakeHost] |
| Screen host | [Hosts](hosts.md) | [`ScreenHost`][pythonnative.hosts.base.ScreenHost] |
| Reconciler | [Reconciler](reconciler.md) | [`Reconciler`][pythonnative.reconciler.Reconciler] |
| Native views | [Native views](native_views.md) | [`get_backend`][pythonnative.native_views.get_backend], [`set_backend`][pythonnative.native_views.set_backend], [`BridgeBackend`][pythonnative.native_views.bridge_backend.BridgeBackend] |
| Mutation ops | [Mutation ops](mutations.md) | [`CreateOp`][pythonnative.mutations.CreateOp], [`UpdateOp`][pythonnative.mutations.UpdateOp], [`InsertOp`][pythonnative.mutations.InsertOp], [`DestroyOp`][pythonnative.mutations.DestroyOp] |
| Event routing | [Events](events.md) | [`EventRegistry`][pythonnative.events.EventRegistry], [`dispatch_event`][pythonnative.events.dispatch_event], [`extract_events`][pythonnative.events.extract_events] |
| Platform metrics | [Platform metrics](platform_metrics.md) | [`SafeAreaInsets`][pythonnative.platform_metrics.SafeAreaInsets], [`subscribe`][pythonnative.platform_metrics.subscribe] |
| Dev server | [Dev server](devserver.md) | [`DevServer`][pythonnative.devserver.DevServer], [`DevClient`][pythonnative.devclient.DevClient], [`WebTransport`][pythonnative.bridge.web.WebTransport] |
| Hot reload | [Hot reload](hot_reload.md) | [`apply_reload`][pythonnative.hot_reload.apply_reload], [`ModuleReloader`][pythonnative.hot_reload.ModuleReloader] |
| Diagnostics | [Diagnostics](diagnostics.md) | [`warn`][pythonnative.diagnostics.warn], [`is_dev`][pythonnative.diagnostics.is_dev], [`report_error`][pythonnative.diagnostics.report_error] |
| Utilities | [Utilities](utils.md) | `IS_ANDROID`, `IS_IOS`, `IS_WEB` |
| CLI | [CLI (`pn`)](cli.md) | `pn init`, `pn run`, `pn build`, `pn submit`, and more in the [CLI reference](cli.md) |

## Property reference

All visual and layout properties pass through the `style` dict (or a
list of dicts). The full per-component property catalogue lives in
[Component properties](component-properties.md).
