"""PythonNative: declarative native UI for Android and iOS.

PythonNative is a cross-platform toolkit that turns Python ``@component``
functions into real, native Android and iOS views. The component model
is React-like (function components plus hooks), but rendering happens
through direct platform bindings: Chaquopy on Android (Java) and
rubicon-objc on iOS (Objective-C). There is no JavaScript bridge.

Key building blocks:

- **Element factories** ([`Text`][pythonnative.Text],
  [`Button`][pythonnative.Button], [`Column`][pythonnative.Column], etc.)
  return immutable [`Element`][pythonnative.Element] descriptors.
- **Hooks** ([`use_state`][pythonnative.use_state],
  [`use_effect`][pythonnative.use_effect],
  [`use_reducer`][pythonnative.use_reducer], etc.) manage state, side
  effects, and context inside `@component` functions.
- **Navigation** is built from
  [`NavigationContainer`][pythonnative.NavigationContainer] plus one of
  the [`create_stack_navigator`][pythonnative.create_stack_navigator],
  [`create_tab_navigator`][pythonnative.create_tab_navigator], or
  [`create_drawer_navigator`][pythonnative.create_drawer_navigator]
  factories.
- **Styling** uses a single ``style`` dict per element (or a list of
  dicts), composable via [`StyleSheet`][pythonnative.StyleSheet].
  PythonNative ships a fully-typed [`Style`][pythonnative.style.Style]
  TypedDict so editors and ``mypy`` validate every key as you type.
- **Animations** use the ``Animated`` namespace, modeled on React
  Native's animation API. Animations are driven natively (Core
  Animation / ``ViewPropertyAnimator``) whenever possible.
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
  [`Props`][pythonnative.sdk.Props] dataclass, implement a
  [`ViewHandler`][pythonnative.native_views.base.ViewHandler] for each
  platform, and register it via
  [`@native_component`][pythonnative.sdk.native_component] (or expose
  it from a PyPI package via the ``pythonnative.handlers`` entry-point
  group).

Example:
    ```python
    import pythonnative as pn

    @pn.component
    def App():
        count, set_count = pn.use_state(0)
        return pn.Column(
            pn.Text(f"Count: {count}", style=pn.style(font_size=24)),
            pn.Button("+", on_press=lambda: set_count(count + 1)),
            style=pn.style(spacing=12),
        )
    ```
"""

__version__ = "0.24.0"

from . import appearance, diagnostics, gestures, images, runtime, sdk
from .alerts import Alert
from .animated import Animated, AnimatedValue, use_animated_value
from .components import (
    ActivityIndicator,
    Button,
    Checkbox,
    Column,
    DatePicker,
    ErrorBoundary,
    FlatList,
    Fragment,
    Image,
    ImageBackground,
    KeyboardAvoidingView,
    ListController,
    Modal,
    Picker,
    Portal,
    Pressable,
    ProgressBar,
    RefreshControl,
    Row,
    SafeAreaView,
    ScrollView,
    SectionList,
    SegmentedControl,
    Slider,
    Spacer,
    StatusBar,
    Suspense,
    Switch,
    Text,
    TextInput,
    TouchableOpacity,
    View,
    WebView,
)
from .diagnostics import HookOrderError
from .element import Element
from .hooks import (
    MutationCall,
    MutationState,
    Provider,
    QueryResult,
    Ref,
    batch_updates,
    component,
    create_context,
    memo,
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
    use_navigation,
    use_query,
    use_reducer,
    use_ref,
    use_resource,
    use_safe_area_insets,
    use_state,
    use_transition,
    use_window_dimensions,
)
from .native_modules import (
    AppState,
    Battery,
    Biometrics,
    Camera,
    Clipboard,
    FileSystem,
    Haptics,
    Linking,
    Location,
    NetInfo,
    Notifications,
    Permissions,
    SecureStore,
    Share,
    Vibration,
    use_app_state,
    use_net_info,
)
from .navigation import (
    NavigationContainer,
    ScreenOptions,
    create_drawer_navigator,
    create_stack_navigator,
    create_tab_navigator,
    use_focus_effect,
    use_route,
)
from .net import HTTPError, Response, fetch
from .platform import Platform
from .runtime import run_async, run_blocking
from .screen import create_screen
from .sdk import (
    Props,
    ViewHandler,
    element_factory,
    native_component,
    register_component,
)
from .storage import AsyncStorage, use_persisted_state
from .style import (
    DEFAULT_DARK_THEME,
    DEFAULT_LIGHT_THEME,
    AccessibilityState,
    AlignContent,
    AlignItems,
    AlignSelf,
    AutoCapitalize,
    Color,
    Dimension,
    EdgeInsets,
    FlexDirection,
    FlexWrap,
    FontWeight,
    JustifyContent,
    KeyboardType,
    LayoutDirection,
    Overflow,
    Position,
    ReturnKeyType,
    ScaleType,
    ShadowOffset,
    Style,
    StyleProp,
    StyleSheet,
    TextAlign,
    TextDecoration,
    ThemeContext,
    TransformSpec,
    default_theme,
    resolve_style,
    style,
    use_theme,
)
from .suspense import Resource, lazy, start_resource

__all__ = [
    # Components
    "ActivityIndicator",
    "Button",
    "Checkbox",
    "Column",
    "DatePicker",
    "ErrorBoundary",
    "FlatList",
    "Fragment",
    "Image",
    "ImageBackground",
    "KeyboardAvoidingView",
    "ListController",
    "Modal",
    "Picker",
    "Portal",
    "Pressable",
    "ProgressBar",
    "RefreshControl",
    "Row",
    "SafeAreaView",
    "ScrollView",
    "SectionList",
    "SegmentedControl",
    "Slider",
    "Spacer",
    "StatusBar",
    "Suspense",
    "Switch",
    "Text",
    "TextInput",
    "TouchableOpacity",
    "View",
    "WebView",
    # Core
    "Element",
    "create_screen",
    # Hooks
    "batch_updates",
    "component",
    "create_context",
    "memo",
    "MutationCall",
    "MutationState",
    "QueryResult",
    "Ref",
    "use_back_handler",
    "use_callback",
    "use_color_scheme",
    "use_context",
    "use_deferred_value",
    "use_effect",
    "use_focus_effect",
    "use_imperative_handle",
    "use_keyboard_height",
    "use_layout_effect",
    "use_memo",
    "use_mutation",
    "use_navigation",
    "use_persisted_state",
    "use_query",
    "use_reducer",
    "use_ref",
    "use_resource",
    "use_route",
    "use_safe_area_insets",
    "use_state",
    "use_transition",
    "use_window_dimensions",
    "Provider",
    # Suspense and async rendering
    "Resource",
    "lazy",
    "start_resource",
    # Navigation
    "NavigationContainer",
    "ScreenOptions",
    "create_drawer_navigator",
    "create_stack_navigator",
    "create_tab_navigator",
    # Styling - typed primitives
    "AccessibilityState",
    "AlignContent",
    "AlignItems",
    "AlignSelf",
    "AutoCapitalize",
    "Color",
    "DEFAULT_DARK_THEME",
    "DEFAULT_LIGHT_THEME",
    "Dimension",
    "EdgeInsets",
    "FlexDirection",
    "FlexWrap",
    "FontWeight",
    "JustifyContent",
    "KeyboardType",
    "LayoutDirection",
    "Overflow",
    "Position",
    "ReturnKeyType",
    "ScaleType",
    "ShadowOffset",
    "Style",
    "StyleProp",
    "StyleSheet",
    "TextAlign",
    "TextDecoration",
    "ThemeContext",
    "TransformSpec",
    "default_theme",
    "resolve_style",
    "style",
    "use_theme",
    # Appearance
    "appearance",
    # Image pipeline
    "images",
    # Animation
    "Animated",
    "AnimatedValue",
    "use_animated_value",
    # Gestures
    "gestures",
    # Imperative
    "Alert",
    # Native modules
    "AppState",
    "Battery",
    "Biometrics",
    "Camera",
    "Clipboard",
    "FileSystem",
    "Haptics",
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
    # Custom-component SDK
    "Props",
    "ViewHandler",
    "element_factory",
    "native_component",
    "register_component",
    "sdk",
]
