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
        "use_state",
        "Provider",
        # Navigation
        "NavigationContainer",
        "create_drawer_navigator",
        "create_stack_navigator",
        "create_tab_navigator",
        # Styling
        "StyleSheet",
        "ThemeContext",
    }
    assert expected.issubset(set(pn.__all__))
