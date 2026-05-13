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
  Native's animation API.
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
            pn.Button("+", on_click=lambda: set_count(count + 1)),
            style=pn.style(spacing=12),
        )
    ```
"""

__version__ = "0.14.0"

from . import sdk
from .alerts import Alert
from .animated import Animated, AnimatedValue
from .components import (
    ActivityIndicator,
    Button,
    Column,
    ErrorBoundary,
    FlatList,
    Image,
    KeyboardAvoidingView,
    Modal,
    Picker,
    Pressable,
    ProgressBar,
    RefreshControl,
    Row,
    SafeAreaView,
    ScrollView,
    SectionList,
    Slider,
    Spacer,
    StatusBar,
    Switch,
    Text,
    TextInput,
    View,
    WebView,
)
from .element import Element
from .hooks import (
    Provider,
    batch_updates,
    component,
    create_context,
    use_callback,
    use_context,
    use_effect,
    use_keyboard_height,
    use_memo,
    use_navigation,
    use_reducer,
    use_ref,
    use_safe_area_insets,
    use_state,
    use_window_dimensions,
)
from .native_modules import Camera, FileSystem, Location, Notifications
from .navigation import (
    NavigationContainer,
    create_drawer_navigator,
    create_stack_navigator,
    create_tab_navigator,
    use_focus_effect,
    use_route,
)
from .platform import Platform
from .screen import create_screen
from .sdk import (
    Props,
    ViewHandler,
    element_factory,
    native_component,
    register_component,
)
from .style import (
    AlignItems,
    AlignSelf,
    AutoCapitalize,
    Color,
    Dimension,
    EdgeInsets,
    FlexDirection,
    FontWeight,
    JustifyContent,
    KeyboardType,
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
    resolve_style,
    style,
)

__all__ = [
    # Components
    "ActivityIndicator",
    "Button",
    "Column",
    "ErrorBoundary",
    "FlatList",
    "Image",
    "KeyboardAvoidingView",
    "Modal",
    "Picker",
    "Pressable",
    "ProgressBar",
    "RefreshControl",
    "Row",
    "SafeAreaView",
    "ScrollView",
    "SectionList",
    "Slider",
    "Spacer",
    "StatusBar",
    "Switch",
    "Text",
    "TextInput",
    "View",
    "WebView",
    # Core
    "Element",
    "create_screen",
    # Hooks
    "batch_updates",
    "component",
    "create_context",
    "use_callback",
    "use_context",
    "use_effect",
    "use_focus_effect",
    "use_keyboard_height",
    "use_memo",
    "use_navigation",
    "use_reducer",
    "use_ref",
    "use_route",
    "use_safe_area_insets",
    "use_state",
    "use_window_dimensions",
    "Provider",
    # Navigation
    "NavigationContainer",
    "create_drawer_navigator",
    "create_stack_navigator",
    "create_tab_navigator",
    # Styling - typed primitives
    "AlignItems",
    "AlignSelf",
    "AutoCapitalize",
    "Color",
    "Dimension",
    "EdgeInsets",
    "FlexDirection",
    "FontWeight",
    "JustifyContent",
    "KeyboardType",
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
    "resolve_style",
    "style",
    # Animation
    "Animated",
    "AnimatedValue",
    # Imperative
    "Alert",
    # Native modules
    "Camera",
    "FileSystem",
    "Location",
    "Notifications",
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
