"""Verify the package is importable and exports the public API."""

import pythonnative as pn
from pythonnative.element import Element


def test_package_version() -> None:
    assert pn.__version__


def test_element_class_exported() -> None:
    assert pn.Element is Element


def test_public_api_names() -> None:
    expected = {
        "ActivityIndicator",
        "Button",
        "Column",
        "Element",
        "ErrorBoundary",
        "FlatList",
        "Image",
        "Modal",
        "Pressable",
        "ProgressBar",
        "Row",
        "SafeAreaView",
        "ScrollView",
        "Slider",
        "Spacer",
        "Switch",
        "Text",
        "TextInput",
        "View",
        "WebView",
        # Core
        "Node",
        "create_screen",
        # Hooks
        "batch_updates",
        "component",
        "create_context",
        "use_callback",
        "use_context",
        "use_effect",
        "use_focus_effect",
        "use_memo",
        "use_navigation",
        "use_reducer",
        "use_ref",
        "use_route",
        "use_screen_options",
        "use_state",
        # Navigation
        "DrawerNavigator",
        "Group",
        "NavigationContainer",
        "NavigationRef",
        "Screen",
        "ScreenOptions",
        "StackNavigator",
        "TabNavigator",
        # Styling and theming
        "StyleSheet",
        "Theme",
        "ThemeProvider",
        "use_styles",
        "use_theme",
        # Stores
        "Store",
        "use_store",
    }
    assert expected.issubset(set(pn.__all__))


def test_removed_names_stay_removed() -> None:
    removed = {
        "create_drawer_navigator",
        "create_navigation_ref",
        "create_stack_navigator",
        "create_tab_navigator",
        "LinkingConfig",
        "ThemeContext",
    }
    assert removed.isdisjoint(pn.__all__)
    assert not any(hasattr(pn, name) for name in removed)
