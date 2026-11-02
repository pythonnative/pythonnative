"""PythonNative: declarative native UI for Android and iOS.

PythonNative is a cross-platform toolkit that turns Python ``@component``
functions into real, native Android and iOS views. The component model
is React-like (function components plus hooks). Python owns the logical
component tree and reconciliation on a dedicated asyncio application thread.
Versioned commits go to a shared C++ renderer core, which every target links.
The core validates each commit against the native contracts, lays it out with
Yoga off the UI thread, flattens layout-only views, and runs animation graphs.
Swift ``PythonNativeKit`` on iOS and the Kotlin ``pythonnative`` module on
Android mount the result: they own widgets, text drawing, input, and the frame
clock on the platform UI thread. The browser preview runs the same core as
WebAssembly and mounts DOM widgets.

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
- **Capabilities** are opt-in device features, one subpackage each:
  ``pythonnative.audio``, ``background``, ``biometrics``, ``camera``,
  ``location``, ``maps``, ``notifications``, ``pickers``, ``purchases``,
  ``push``, ``sensors``, and ``video``. They aren't re-exported here. List
  one in ``[plugins].use`` in ``pythonnative.toml`` to compile it into the
  app, then import it by name: ``from pythonnative.camera import CameraView``.
  Calling one that isn't in the build raises ``NativeModuleError`` with the
  code ``plugin_not_enabled``.
- **Failures** in a release build reach
  [`set_error_handler`][pythonnative.set_error_handler], and a render error
  no boundary catches shows the screen set with
  [`set_error_fallback`][pythonnative.set_error_fallback].

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

__version__ = "0.52.2"

import importlib
from typing import TYPE_CHECKING, Any

from . import appearance, diagnostics, runtime, sdk, svg
from .alerts import Alert
from .assets import Asset, asset
from .component import Component, component, memo
from .components import (
    set_error_fallback,
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
    View,
    WebNavigationEvent,
    WebView,
)
from .components.props import AccessibilityProps, ViewProps
from .diagnostics import HookOrderError
from .element import Element, Node
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
from .native_modules import (
    AccessibilityEvent,
    AccessibilityInfo,
    AppState,
    Battery,
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
    NetInfo,
    Permissions,
    PixelRatio,
    SecureStore,
    Share,
    use_app_state,
    use_locales,
    use_net_info,
    use_reduce_motion,
    use_screen_reader_enabled,
)
from .diagnostics import set_error_handler
from .platform import Platform
from .platform_metrics import WindowDimensions
from .runtime import run_async, run_blocking
from .scheduler import batch_updates
from .sdk import Props, define_component
from .storage import AsyncStorage, use_persisted_state
from .store import Store, use_store
from .style import (
    ABSOLUTE_FILL,
    AccessibilityAction,
    AccessibilityState,
    AccessibilityValue,
    Color,
    DynamicColor,
    EdgeInsets,
    ShadowOffset,
    Style,
    StyleProp,
    StyleSheet,
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
    # Errors
    "set_error_fallback",
    "set_error_handler",
    # Networking
    "WebSocket",
    "WebSocketClosed",
    "WebSocketError",
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
    "Color",
    "DynamicColor",
    "EdgeInsets",
    "ShadowOffset",
    "Style",
    "StyleProp",
    "StyleSheet",
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
    "style",
    "use_theme",
    # Appearance
    "appearance",
    # Animation
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
    "Clipboard",
    "FileSystem",
    "Haptics",
    "ImageSize",
    "Images",
    "Linking",
    "NetInfo",
    "Permissions",
    "SecureStore",
    "Share",
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
    # Diagnostics
    "HookOrderError",
    # Platform
    "Platform",
    # Custom-component SDK
    "Props",
    "define_component",
    "sdk",
]

from .list_data import ListData, Section, ViewableItem

# Subsystems an app may never touch load on first use (PEP 562), so
# ``import pythonnative`` stays fast on a phone. Names, ``__all__``, and
# documentation are unchanged, and type checkers see ordinary imports.
_LAZY_GROUPS: dict[str, tuple[str, ...]] = {
    "animated": (
        "Animated",
        "AnimatedValue",
        "AnimationResult",
        "Easing",
        "EasingSpec",
        "use_animated_value",
    ),
    "gestures": ("GestureSpec", "SwipeDirection"),
    "icons": ("Icon", "IconName"),
    "navigation": (
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
    ),
    "net": ("HTTPError", "Response", "fetch"),
    "websocket": ("WebSocket", "WebSocketClosed", "WebSocketError"),
}
_LAZY = {name: module for module, names in _LAZY_GROUPS.items() for name in names}
_LAZY_MODULES = frozenset({"gestures", "icons"})

if TYPE_CHECKING:
    from . import gestures, icons
    from .animated import (
        Animated,
        AnimatedValue,
        AnimationResult,
        Easing,
        EasingSpec,
        use_animated_value,
    )
    from .gestures import GestureSpec, SwipeDirection
    from .icons import Icon, IconName
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
    from .websocket import WebSocket, WebSocketClosed, WebSocketError


def __getattr__(name: str) -> Any:
    module = _LAZY.get(name)
    if module is None and name not in _LAZY_MODULES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    imported = importlib.import_module(f".{module or name}", __name__)
    value = imported if module is None else getattr(imported, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | _LAZY.keys() | _LAZY_MODULES)
