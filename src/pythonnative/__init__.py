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
- **Animations** use the ``Animated`` namespace, modeled on React
  Native's animation API.

Example:
    ```python
    import pythonnative as pn

    @pn.component
    def App():
        count, set_count = pn.use_state(0)
        return pn.Column(
            pn.Text(f"Count: {count}", style={"font_size": 24}),
            pn.Button("+", on_click=lambda: set_count(count + 1)),
            style={"spacing": 12},
        )
    ```
"""

__version__ = "0.12.0"

from typing import Any, Callable

from . import app_registry as _app_registry
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
from .page import create_page
from .platform import Platform
from .style import StyleSheet, ThemeContext


def run(component: Callable[..., Any]) -> Callable[..., Any]:
    """Register the App component as the root of the application.

    Mirrors React Native's
    [`AppRegistry.registerComponent`](https://reactnative.dev/docs/appregistry):
    the user's module declares an ``App`` function once and registers
    it at import time. Native templates then load the app by importing
    its module — they do not need to know the App component's name.

    Args:
        component: A zero-argument ``@component`` function. Typically
            returns a [`Stack.Navigator`][pythonnative.create_stack_navigator]
            wrapped in a
            [`NavigationContainer`][pythonnative.NavigationContainer].

    Returns:
        The same ``component`` (so ``run`` can be used as a decorator
        in a pinch, though calling it directly is the conventional
        form).

    Example:
        ```python
        import pythonnative as pn

        Stack = pn.create_stack_navigator()

        @pn.component
        def App():
            return pn.NavigationContainer(
                Stack.Navigator(
                    Stack.Screen("Home", component=HomeScreen),
                )
            )

        pn.run(App)
        ```
    """
    _app_registry.register(component)
    return component


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
    "create_page",
    "run",
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
    # Styling
    "StyleSheet",
    "ThemeContext",
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
]
