"""PythonNative: declarative native UI for Android and iOS.

PythonNative is a cross-platform toolkit that turns Python ``@component``
functions into real, native Android and iOS views. The component model
is React-like (function components plus hooks). Python owns the logical
component tree and reconciliation on a dedicated asyncio application thread.
Versioned commits cross into Swift ``PythonNativeKit`` on iOS and the Kotlin
``pythonnative`` module on Android. Those renderers own widgets, Yoga layout,
measurement, gestures, and animation frames on the platform UI thread.
The browser preview uses DOM widgets and Yoga WebAssembly.

Key building blocks:

- **Element factories** ([`Text`][pythonnative.Text],
  [`Button`][pythonnative.Button], [`Column`][pythonnative.Column], etc.)
  return immutable [`Element`][pythonnative.Element] descriptors.
- **Hooks** ([`use_state`][pythonnative.use_state],
  [`use_effect`][pythonnative.use_effect],
  [`use_reducer`][pythonnative.use_reducer], etc.) manage state, side
  effects, and context inside `@component` functions.
- **Navigation**: screens are components whose parameters are their
  route params, listed in module-level
  [`StackNavigator`][pythonnative.StackNavigator],
  [`TabNavigator`][pythonnative.TabNavigator], or
  [`DrawerNavigator`][pythonnative.DrawerNavigator] values and rendered
  by [`NavigationContainer`][pythonnative.NavigationContainer].
  ``nav.push(ItemScreen(id=42))`` is checked by the type checker.
- **Styling** uses a ``style`` dict per element (or a list of dicts),
  typed by the [`Style`][pythonnative.style.Style] ``TypedDict``.
  [`StyleSheet`][pythonnative.StyleSheet] namespaces group named
  styles, and one [`Theme`][pythonnative.Theme] styles the app and
  its navigators.
- **State** lives in hooks for a component and in a typed
  [`Store`][pythonnative.Store] for the app.
- **Animations** use the ``Animated`` namespace. Serialized graphs
  connect values, arithmetic, interpolation, and style bindings.
  Native timing, spring, decay, scroll, and gesture drivers update
  supported bindings without Python work on every frame.
- **Gestures** attach to any view via the ``gestures=`` prop using
  descriptors from ``pythonnative.gestures``
  ([`Tap`][pythonnative.gestures.Tap],
  [`LongPress`][pythonnative.gestures.LongPress],
  [`Pan`][pythonnative.gestures.Pan],
  [`Swipe`][pythonnative.gestures.Swipe],
  [`Pinch`][pythonnative.gestures.Pinch],
  [`Rotation`][pythonnative.gestures.Rotation]).
- **Custom native components** can be authored with the
  ``pythonnative.sdk`` package: define a typed
  [`Props`][pythonnative.sdk.Props] dataclass and declare the component
  with [`define_component`][pythonnative.sdk.define_component], which
  returns its element factory (or expose it from a PyPI package via the
  ``pythonnative.handlers`` entry-point group).

Example:
    ```python
    import pythonnative as pn

    @pn.component
    def App() -> pn.Node:
        count, set_count = pn.use_state(0)
        return pn.Column(
            pn.Text(f"Count: {count}", style=pn.style(font_size=24)),
            pn.Button("+", on_press=lambda: set_count(count + 1)),
            style=pn.style(gap=12),
        )
    ```
"""

__version__ = "0.47.0"

from . import appearance, diagnostics, gestures, icons, runtime, sdk, svg
from .alerts import Alert
from .animated import ANIMATABLE_PROPS, Animated, AnimatedValue, AnimationResult, Easing, EasingSpec, use_animated_value
from .assets import Asset, asset
from .component import Component, component, memo
from .components import (
    ActivityIndicator,
    BlurView,
    Button,
    Checkbox,
    Column,
    ContentSizeEvent,
    DatePicker,
    ErrorBoundary,
    FlatList,
    Fragment,
    Image,
    ImageBackground,
    ImageLoadEvent,
    ImageSource,
    KeyboardAvoidingView,
    KeyPressEvent,
    LayoutEvent,
    LinearGradient,
    ListController,
    Modal,
    Picker,
    Portal,
    Pressable,
    PressState,
    ProgressBar,
    RefreshControl,
    Ripple,
    Row,
    SafeAreaView,
    ScrollEvent,
    ScrollView,
    SectionList,
    SegmentedControl,
    SelectionEvent,
    Slider,
    Spacer,
    StatusBar,
    Suspense,
    Svg,
    Switch,
    Text,
    TextInput,
    TouchableOpacity,
    View,
    WebNavigationEvent,
    WebView,
)
from .components.props import AccessibilityProps, ViewProps
from .diagnostics import HookOrderError
from .element import Element, Node
from .gestures import GestureSpec, SwipeDirection
from .handles import ScrollOffset, ScrollViewHandle, TextInputHandle, ViewHandle, WebViewHandle
from .hooks import (
    ColorScheme,
    Context,
    Deps,
    MutationCall,
    MutationState,
    QueryResult,
    Ref,
    create_context,
    use_back_handler,
    use_callback,
    use_color_scheme,
    use_context,
    use_deferred_value,
    use_effect,
    use_imperative_handle,
    use_keyboard_height,
    use_layout_effect,
    use_memo,
    use_mutation,
    use_query,
    use_reducer,
    use_ref,
    use_resource,
    use_safe_area_insets,
    use_state,
    use_subscription,
    use_transition,
    use_window_dimensions,
)
from .hosts import create_screen
from .icons import Icon, IconName
from .mutations import UNSET, UnsetType
from .native_modules import (
    AccessibilityEvent,
    AccessibilityInfo,
    AppState,
    Battery,
    Biometrics,
    Camera,
    Clipboard,
    Device,
    DeviceInfo,
    Dimensions,
    DimensionsEvent,
    FileSystem,
    Haptics,
    Images,
    ImageSize,
    Keyboard,
    KeyboardEvent,
    Linking,
    Locale,
    Localization,
    Location,
    NetInfo,
    Notifications,
    Permissions,
    PixelRatio,
    SecureStore,
    Share,
    Vibration,
    use_app_state,
    use_locales,
    use_net_info,
    use_reduce_motion,
    use_screen_reader_enabled,
)
from .navigation import (
    DrawerNavigator,
    Group,
    Navigation,
    NavigationContainer,
    NavigationRef,
    NavigationState,
    Navigator,
    Route,
    Screen,
    ScreenOptions,
    StackNavigator,
    TabBarStyle,
    TabNavigator,
    use_focus_effect,
    use_is_focused,
    use_navigation,
    use_route,
    use_screen_options,
)
from .net import HTTPError, Response, fetch
from .platform import Platform, get_platform
from .platform_metrics import WindowDimensions
from .runtime import run_async, run_blocking
from .scheduler import batch_updates
from .sdk import Props, define_component, element_factory
from .storage import AsyncStorage, use_persisted_state
from .store import Store, use_store
from .style import (
    ABSOLUTE_FILL,
    AccessibilityAction,
    AccessibilityState,
    AccessibilityValue,
    AlignContent,
    AlignItems,
    AlignSelf,
    AutoCapitalize,
    BorderStyle,
    Color,
    Dimension,
    Display,
    DynamicColor,
    EdgeInsets,
    FlexDirection,
    FlexWrap,
    FontWeight,
    JustifyContent,
    KeyboardType,
    LayoutDirection,
    Overflow,
    PointerEvents,
    Position,
    ReturnKeyType,
    ScaleType,
    ShadowOffset,
    Style,
    StyleProp,
    StyleSheet,
    TextAlign,
    TextDecoration,
    TextTransform,
    TransformSpec,
    resolve_style,
    style,
)
from .suspense import Resource, lazy, start_resource
from .theme import (
    DARK_THEME,
    LIGHT_THEME,
    Colors,
    Radii,
    Spacing,
    Theme,
    ThemeProvider,
    Typography,
    use_styles,
    use_theme,
)

__all__ = [
    "UNSET",
    "UnsetType",
    # Components
    "ActivityIndicator",
    "BlurView",
    "Button",
    "Checkbox",
    "Column",
    "DatePicker",
    "ErrorBoundary",
    "FlatList",
    "ListData",
    "Section",
    "ViewableItem",
    "Fragment",
    "Icon",
    "IconName",
    "Image",
    "ImageBackground",
    "ImageLoadEvent",
    "ImageSource",
    "WebNavigationEvent",
    "KeyboardAvoidingView",
    "LinearGradient",
    "ListController",
    "Modal",
    "Picker",
    "Portal",
    "Pressable",
    "PressState",
    "ProgressBar",
    "RefreshControl",
    "Ripple",
    "Row",
    "SafeAreaView",
    "ScrollView",
    "SectionList",
    "SegmentedControl",
    "Slider",
    "Spacer",
    "StatusBar",
    "Suspense",
    "Svg",
    "Switch",
    "Text",
    "TextInput",
    "TouchableOpacity",
    "View",
    "WebView",
    # Shared props
    "AccessibilityProps",
    "ViewProps",
    # Typed events
    "ContentSizeEvent",
    "KeyPressEvent",
    "LayoutEvent",
    "ScrollEvent",
    "SelectionEvent",
    # Imperative handles
    "ScrollOffset",
    "ScrollViewHandle",
    "TextInputHandle",
    "ViewHandle",
    "WebViewHandle",
    # Assets and graphics
    "Asset",
    "asset",
    "icons",
    "svg",
    # Core
    "Component",
    "Element",
    "Node",
    "component",
    "create_screen",
    "memo",
    # Hooks
    "ColorScheme",
    "Deps",
    "Context",
    "MutationCall",
    "MutationState",
    "QueryResult",
    "Ref",
    "batch_updates",
    "create_context",
    "use_back_handler",
    "use_callback",
    "use_color_scheme",
    "use_context",
    "use_deferred_value",
    "use_effect",
    "use_imperative_handle",
    "use_keyboard_height",
    "use_layout_effect",
    "use_memo",
    "use_mutation",
    "use_persisted_state",
    "use_query",
    "use_reducer",
    "use_ref",
    "use_resource",
    "use_safe_area_insets",
    "use_state",
    "use_subscription",
    "use_transition",
    "use_window_dimensions",
    # Suspense and async rendering
    "Resource",
    "lazy",
    "start_resource",
    # Navigation
    "DrawerNavigator",
    "Group",
    "Navigation",
    "NavigationContainer",
    "NavigationRef",
    "NavigationState",
    "Navigator",
    "Route",
    "Screen",
    "ScreenOptions",
    "StackNavigator",
    "TabBarStyle",
    "TabNavigator",
    "use_focus_effect",
    "use_is_focused",
    "use_navigation",
    "use_route",
    "use_screen_options",
    # Styling - typed primitives
    "AccessibilityAction",
    "AccessibilityState",
    "AccessibilityValue",
    "AlignContent",
    "AlignItems",
    "AlignSelf",
    "AutoCapitalize",
    "BorderStyle",
    "Color",
    "Dimension",
    "Display",
    "DynamicColor",
    "EdgeInsets",
    "FlexDirection",
    "FlexWrap",
    "FontWeight",
    "JustifyContent",
    "KeyboardType",
    "LayoutDirection",
    "Overflow",
    "PointerEvents",
    "Position",
    "ReturnKeyType",
    "ScaleType",
    "ShadowOffset",
    "Style",
    "StyleProp",
    "StyleSheet",
    "TextAlign",
    "TextDecoration",
    "TextTransform",
    "Theme",
    "ThemeProvider",
    "Colors",
    "Typography",
    "Spacing",
    "Radii",
    "LIGHT_THEME",
    "DARK_THEME",
    "ABSOLUTE_FILL",
    "use_styles",
    "TransformSpec",
    "resolve_style",
    "style",
    "use_theme",
    # Appearance
    "appearance",
    # Animation
    "ANIMATABLE_PROPS",
    "Animated",
    "AnimatedValue",
    "AnimationResult",
    "Easing",
    "EasingSpec",
    "use_animated_value",
    # Gestures
    "GestureSpec",
    "SwipeDirection",
    "gestures",
    # Imperative
    "Alert",
    # Native modules
    "AccessibilityEvent",
    "AccessibilityInfo",
    "Device",
    "DeviceInfo",
    "Dimensions",
    "DimensionsEvent",
    "Keyboard",
    "KeyboardEvent",
    "Locale",
    "Localization",
    "PixelRatio",
    "WindowDimensions",
    "use_locales",
    "use_reduce_motion",
    "use_screen_reader_enabled",
    "AppState",
    "Battery",
    "Biometrics",
    "Camera",
    "Clipboard",
    "FileSystem",
    "Haptics",
    "ImageSize",
    "Images",
    "Linking",
    "Location",
    "NetInfo",
    "Notifications",
    "Permissions",
    "SecureStore",
    "Share",
    "Vibration",
    "use_app_state",
    "use_net_info",
    # Stores
    "Store",
    "use_store",
    # Networking + persistence
    "AsyncStorage",
    "fetch",
    "HTTPError",
    "Response",
    # Runtime
    "run_async",
    "run_blocking",
    "runtime",
    # Diagnostics
    "HookOrderError",
    "diagnostics",
    # Platform
    "Platform",
    "get_platform",
    # Custom-component SDK
    "Props",
    "define_component",
    "element_factory",
    "sdk",
]

from .list_data import ListData, Section, ViewableItem
