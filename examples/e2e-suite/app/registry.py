"""Registry of every demo screen in the E2E suite.

The registry is the single source of truth that maps a stable demo
``id`` to:

- the navigation title shown in the platform nav bar,
- the category bucket (used to group demos on the home screen),
- the ``feature`` string, the PythonNative public symbol the demo
  exercises (used by ``scripts/check-e2e-coverage.py``),
- the component function that renders the demo.

Adding a new demo is a three-step process:

1. Implement the screen in ``app/screens/<category>/<id>.py``.
2. Append a ``DemoEntry`` to :data:`DEMOS` below.
3. Author a Maestro flow at ``tests/e2e/flows/<category>/<id>.yaml``.

``app/main.py`` consumes this list to wire every screen into the root
[`Stack.Navigator`][pythonnative.create_stack_navigator]. The
home screen ([`app.screens.home.HomeScreen`][]) also consumes it to
render a categorized list of buttons.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List

import pythonnative as pn
from app.screens.alerts.confirm_alert import ConfirmAlertDemo
from app.screens.alerts.simple_alert import SimpleAlertDemo
from app.screens.animations.parallel_animation import ParallelAnimationDemo
from app.screens.animations.sequence_animation import SequenceAnimationDemo
from app.screens.animations.spring_animation import SpringAnimationDemo
from app.screens.animations.timing_animation import TimingAnimationDemo
from app.screens.components.activity_indicator import ActivityIndicatorDemo
from app.screens.components.button import ButtonDemo
from app.screens.components.checkbox import CheckboxDemo
from app.screens.components.date_picker import DatePickerDemo
from app.screens.components.error_boundary import ErrorBoundaryDemo
from app.screens.components.flat_list import FlatListDemo
from app.screens.components.fragment import FragmentDemo
from app.screens.components.image import ImageDemo
from app.screens.components.image_background import ImageBackgroundDemo
from app.screens.components.keyboard_avoiding_view import KeyboardAvoidingViewDemo
from app.screens.components.modal import ModalDemo
from app.screens.components.picker import PickerDemo
from app.screens.components.pressable import PressableDemo
from app.screens.components.progress_bar import ProgressBarDemo
from app.screens.components.refresh_control import RefreshControlDemo
from app.screens.components.safe_area_view import SafeAreaViewDemo
from app.screens.components.scroll_view import ScrollViewDemo
from app.screens.components.section_list import SectionListDemo
from app.screens.components.segmented_control import SegmentedControlDemo
from app.screens.components.slider import SliderDemo
from app.screens.components.spacer import SpacerDemo
from app.screens.components.status_bar import StatusBarDemo
from app.screens.components.switch import SwitchDemo
from app.screens.components.text import TextDemo
from app.screens.components.text_input import TextInputDemo
from app.screens.components.touchable_opacity import TouchableOpacityDemo
from app.screens.components.view_column_row import ViewColumnRowDemo
from app.screens.components.web_view import WebViewDemo
from app.screens.gestures.gestures import GesturesDemo
from app.screens.hooks.batch_updates_demo import BatchUpdatesDemo
from app.screens.hooks.memo_demo import MemoDemo
from app.screens.hooks.use_async_effect import UseAsyncEffectDemo
from app.screens.hooks.use_callback import UseCallbackDemo
from app.screens.hooks.use_context import UseContextDemo
from app.screens.hooks.use_effect import UseEffectDemo
from app.screens.hooks.use_memo import UseMemoDemo
from app.screens.hooks.use_mutation import UseMutationDemo
from app.screens.hooks.use_persisted_state import UsePersistedStateDemo
from app.screens.hooks.use_query import UseQueryDemo
from app.screens.hooks.use_reducer import UseReducerDemo
from app.screens.hooks.use_ref import UseRefDemo
from app.screens.hooks.use_state import UseStateDemo
from app.screens.hooks.use_window_dimensions import UseWindowDimensionsDemo
from app.screens.layout.absolute_position import AbsolutePositionDemo
from app.screens.layout.alignment import AlignmentDemo
from app.screens.layout.aspect_ratio import AspectRatioDemo
from app.screens.layout.flex_layout import FlexLayoutDemo
from app.screens.layout.padding_margin import PaddingMarginDemo
from app.screens.navigation.drawer_navigator import DrawerNavigatorDemo
from app.screens.navigation.focus_effect import FocusEffectDemo
from app.screens.navigation.params_passing import ParamsPassingDemo
from app.screens.navigation.tab_navigator import TabNavigatorDemo
from app.screens.platform.platform_info import PlatformInfoDemo
from app.screens.runtime.run_async_demo import RunAsyncDemo
from app.screens.sdk.custom_component import CustomComponentDemo
from app.screens.storage.async_storage_demo import AsyncStorageDemo
from app.screens.styling.borders_shadows import BordersShadowsDemo
from app.screens.styling.stylesheet_demo import StyleSheetDemo
from app.screens.styling.transform import TransformDemo
from app.screens.styling.typography import TypographyDemo


@dataclass(frozen=True)
class DemoEntry:
    """One demo screen in the registry.

    Attributes:
        id: Unique, URL-safe identifier used as the Stack route name,
            as the home-screen button label suffix, and as the Maestro
            flow file name. ``snake_case``.
        category: Bucket used to group demos on the home screen.
            Mirrors the directory under ``app/screens/`` and
            ``tests/e2e/flows/``.
        title: Display title shown in the platform nav bar and in the
            home-screen list entry.
        feature: The ``pythonnative.__all__`` symbol the demo exercises
            (e.g. ``"use_state"``). Used by the coverage checker. Use
            ``"category::feature"`` form for sub-features that aren't
            themselves listed in ``__all__`` (e.g.
            ``"styling::transform"``).
        component: The ``@pn.component`` function rendering the demo.
    """

    id: str
    category: str
    title: str
    feature: str
    component: Callable[[], pn.Element]


DEMOS: List[DemoEntry] = [
    # ------------------------------------------------------------------
    # Components
    # ------------------------------------------------------------------
    DemoEntry("text", "Components", "Text", "Text", TextDemo),
    DemoEntry("button", "Components", "Button", "Button", ButtonDemo),
    DemoEntry("text_input", "Components", "TextInput", "TextInput", TextInputDemo),
    DemoEntry("image", "Components", "Image", "Image", ImageDemo),
    DemoEntry("switch", "Components", "Switch", "Switch", SwitchDemo),
    DemoEntry("slider", "Components", "Slider", "Slider", SliderDemo),
    DemoEntry("progress_bar", "Components", "ProgressBar", "ProgressBar", ProgressBarDemo),
    DemoEntry(
        "activity_indicator",
        "Components",
        "ActivityIndicator",
        "ActivityIndicator",
        ActivityIndicatorDemo,
    ),
    DemoEntry(
        "view_column_row",
        "Components",
        "View / Column / Row",
        "View",
        ViewColumnRowDemo,
    ),
    DemoEntry("scroll_view", "Components", "ScrollView", "ScrollView", ScrollViewDemo),
    DemoEntry("safe_area_view", "Components", "SafeAreaView", "SafeAreaView", SafeAreaViewDemo),
    DemoEntry("modal", "Components", "Modal", "Modal", ModalDemo),
    DemoEntry("pressable", "Components", "Pressable", "Pressable", PressableDemo),
    DemoEntry("picker", "Components", "Picker", "Picker", PickerDemo),
    DemoEntry(
        "refresh_control",
        "Components",
        "RefreshControl",
        "RefreshControl",
        RefreshControlDemo,
    ),
    DemoEntry("fragment", "Components", "Fragment", "Fragment", FragmentDemo),
    DemoEntry(
        "error_boundary",
        "Components",
        "ErrorBoundary",
        "ErrorBoundary",
        ErrorBoundaryDemo,
    ),
    DemoEntry("spacer", "Components", "Spacer", "Spacer", SpacerDemo),
    DemoEntry("status_bar", "Components", "StatusBar", "StatusBar", StatusBarDemo),
    DemoEntry(
        "keyboard_avoiding_view",
        "Components",
        "KeyboardAvoidingView",
        "KeyboardAvoidingView",
        KeyboardAvoidingViewDemo,
    ),
    DemoEntry("flat_list", "Components", "FlatList", "FlatList", FlatListDemo),
    DemoEntry("section_list", "Components", "SectionList", "SectionList", SectionListDemo),
    DemoEntry("web_view", "Components", "WebView", "WebView", WebViewDemo),
    DemoEntry("touchable_opacity", "Components", "TouchableOpacity", "TouchableOpacity", TouchableOpacityDemo),
    DemoEntry("image_background", "Components", "ImageBackground", "ImageBackground", ImageBackgroundDemo),
    DemoEntry("checkbox", "Components", "Checkbox", "Checkbox", CheckboxDemo),
    DemoEntry("segmented_control", "Components", "SegmentedControl", "SegmentedControl", SegmentedControlDemo),
    DemoEntry("date_picker", "Components", "DatePicker", "DatePicker", DatePickerDemo),
    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------
    DemoEntry("use_state", "Hooks", "use_state", "use_state", UseStateDemo),
    DemoEntry("use_effect", "Hooks", "use_effect", "use_effect", UseEffectDemo),
    DemoEntry("use_reducer", "Hooks", "use_reducer", "use_reducer", UseReducerDemo),
    DemoEntry("use_ref", "Hooks", "use_ref", "use_ref", UseRefDemo),
    DemoEntry("use_memo", "Hooks", "use_memo", "use_memo", UseMemoDemo),
    DemoEntry("use_callback", "Hooks", "use_callback", "use_callback", UseCallbackDemo),
    DemoEntry("use_context", "Hooks", "use_context", "use_context", UseContextDemo),
    DemoEntry(
        "use_async_effect",
        "Hooks",
        "use_async_effect",
        "use_async_effect",
        UseAsyncEffectDemo,
    ),
    DemoEntry("use_query", "Hooks", "use_query", "use_query", UseQueryDemo),
    DemoEntry("use_mutation", "Hooks", "use_mutation", "use_mutation", UseMutationDemo),
    DemoEntry(
        "use_persisted_state",
        "Hooks",
        "use_persisted_state",
        "use_persisted_state",
        UsePersistedStateDemo,
    ),
    DemoEntry(
        "use_window_dimensions",
        "Hooks",
        "use_window_dimensions",
        "use_window_dimensions",
        UseWindowDimensionsDemo,
    ),
    DemoEntry("memo", "Hooks", "memo", "memo", MemoDemo),
    DemoEntry("batch_updates", "Hooks", "batch_updates", "batch_updates", BatchUpdatesDemo),
    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    DemoEntry(
        "tab_navigator",
        "Navigation",
        "Tab Navigator",
        "create_tab_navigator",
        TabNavigatorDemo,
    ),
    DemoEntry(
        "drawer_navigator",
        "Navigation",
        "Drawer Navigator",
        "create_drawer_navigator",
        DrawerNavigatorDemo,
    ),
    DemoEntry(
        "params_passing",
        "Navigation",
        "Route Params",
        "use_route",
        ParamsPassingDemo,
    ),
    DemoEntry(
        "focus_effect",
        "Navigation",
        "use_focus_effect",
        "use_focus_effect",
        FocusEffectDemo,
    ),
    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    DemoEntry("flex_layout", "Layout", "Flex layout", "layout::flex", FlexLayoutDemo),
    DemoEntry(
        "aspect_ratio",
        "Layout",
        "Aspect ratio",
        "layout::aspect_ratio",
        AspectRatioDemo,
    ),
    DemoEntry(
        "absolute_position",
        "Layout",
        "Absolute positioning",
        "layout::absolute",
        AbsolutePositionDemo,
    ),
    DemoEntry(
        "padding_margin",
        "Layout",
        "Padding & margin",
        "layout::spacing",
        PaddingMarginDemo,
    ),
    DemoEntry("alignment", "Layout", "Alignment", "layout::alignment", AlignmentDemo),
    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------
    DemoEntry("typography", "Styling", "Typography", "styling::typography", TypographyDemo),
    DemoEntry(
        "borders_shadows",
        "Styling",
        "Borders & shadows",
        "styling::borders",
        BordersShadowsDemo,
    ),
    DemoEntry("transform", "Styling", "Transforms", "styling::transform", TransformDemo),
    DemoEntry("stylesheet", "Styling", "StyleSheet", "StyleSheet", StyleSheetDemo),
    # ------------------------------------------------------------------
    # Animations
    # ------------------------------------------------------------------
    DemoEntry("timing_animation", "Animations", "Animated.timing", "Animated", TimingAnimationDemo),
    DemoEntry(
        "spring_animation",
        "Animations",
        "Animated.spring",
        "animated::spring",
        SpringAnimationDemo,
    ),
    DemoEntry(
        "parallel_animation",
        "Animations",
        "Animated.parallel",
        "animated::parallel",
        ParallelAnimationDemo,
    ),
    DemoEntry(
        "sequence_animation",
        "Animations",
        "Animated.sequence",
        "animated::sequence",
        SequenceAnimationDemo,
    ),
    # ------------------------------------------------------------------
    # Gestures
    # ------------------------------------------------------------------
    DemoEntry("gestures", "Gestures", "gestures", "gestures", GesturesDemo),
    # ------------------------------------------------------------------
    # Alerts, storage, runtime, platform, SDK
    # ------------------------------------------------------------------
    DemoEntry("simple_alert", "Alerts", "Alert.show", "Alert", SimpleAlertDemo),
    DemoEntry(
        "confirm_alert",
        "Alerts",
        "Alert.confirm",
        "alerts::confirm",
        ConfirmAlertDemo,
    ),
    DemoEntry(
        "async_storage",
        "Storage",
        "AsyncStorage",
        "AsyncStorage",
        AsyncStorageDemo,
    ),
    DemoEntry("run_async", "Runtime", "run_async", "run_async", RunAsyncDemo),
    DemoEntry("platform_info", "Platform", "Platform info", "Platform", PlatformInfoDemo),
    DemoEntry(
        "custom_component",
        "SDK",
        "Custom component",
        "native_component",
        CustomComponentDemo,
    ),
]

CATEGORIES: List[str] = []
for _demo in DEMOS:
    if _demo.category not in CATEGORIES:
        CATEGORIES.append(_demo.category)


def demos_for_category(category: str) -> List[DemoEntry]:
    """Return all demos that belong to ``category``, preserving order."""
    return [d for d in DEMOS if d.category == category]


def feature_to_demo_id() -> dict:
    """Map every covered feature string to its demo ``id``.

    Used by ``scripts/check-e2e-coverage.py`` to confirm that every
    public symbol in ``pythonnative.__all__`` is touched by at least
    one demo. Multiple demos covering the same feature is fine; the
    coverage checker only cares about whether ``feature`` is in this
    map.
    """
    return {d.feature: d.id for d in DEMOS}
