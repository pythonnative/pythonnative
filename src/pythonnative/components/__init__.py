"""Built-in element factories.

Each factory function (``Text``, ``Button``, …) is a fully-typed thin
wrapper that builds an [`Element`][pythonnative.Element] through the
shared ``_make_element`` helper, so style resolution, ``ref``
attachment, ``None``-default dropping, and forced overrides (e.g.
``Column``'s fixed ``flex_direction``) live in exactly one place. The
factory signatures themselves are the canonical prop schemas: editors
and type checkers validate calls directly against them.

The factories are grouped by concern into submodules (``text``,
``media``, ``controls``, ``layout``, ``pressable``, ``overlays``,
``structural``, ``lists``); everything public is re-exported here, so
``from pythonnative.components import Text`` keeps working.

Example:
    ```python
    import pythonnative as pn

    pn.Column(
        pn.Text("Hello", style=pn.style(font_size=18)),
        pn.Button("Tap", on_press=lambda: print("tapped")),
        style=pn.style(gap=12, padding=16),
    )
    ```
"""

from ._base import _SPAN_STYLE_KEYS, _flatten_text_spans, _make_element  # noqa: F401
from .controls import (
    ActivityIndicator,
    Checkbox,
    DatePicker,
    Picker,
    ProgressBar,
    RefreshControl,
    SegmentedControl,
    Slider,
    StatusBar,
    Switch,
)
from .events import (
    ContentSizeEvent,
    ImageLoadEvent,
    KeyPressEvent,
    LayoutEvent,
    ScrollEvent,
    SelectionEvent,
    WebNavigationEvent,
)
from .graphics import BlurType, BlurView, LinearGradient, PreserveAspectRatio, Svg
from .layout import (  # noqa: F401
    _SAFE_AREA_EDGES,
    Column,
    KeyboardAvoidingView,
    Row,
    SafeAreaView,
    ScrollView,
    Spacer,
    View,
    _KeyboardAvoidingContainer,
    _numeric_edge_padding,
    _SafeAreaContainer,
)
from .lists import (  # noqa: F401
    _DEFAULT_ROW_EXTENT,
    FlatList,
    ListController,
    SectionList,
    _NativeList,
    _RowSpec,
)
from .media import Image, ImageBackground, ImageSource, WebView
from .overlays import Modal, Portal
from .pressable import Pressable, PressState, Ripple, TouchableOpacity, _StatefulPressable  # noqa: F401
from .structural import ErrorBoundary, Fragment, Suspense
from .text import Button, EllipsizeMode, KeyboardAppearance, Text, TextInput

__all__ = [
    "ActivityIndicator",
    "BlurType",
    "BlurView",
    "Button",
    "Checkbox",
    "Column",
    "ContentSizeEvent",
    "DatePicker",
    "EllipsizeMode",
    "ErrorBoundary",
    "FlatList",
    "Fragment",
    "Image",
    "ImageBackground",
    "ImageLoadEvent",
    "ImageSource",
    "KeyPressEvent",
    "KeyboardAppearance",
    "KeyboardAvoidingView",
    "LayoutEvent",
    "LinearGradient",
    "ListController",
    "Modal",
    "Picker",
    "Portal",
    "PreserveAspectRatio",
    "PressState",
    "Pressable",
    "ProgressBar",
    "RefreshControl",
    "Ripple",
    "Row",
    "SafeAreaView",
    "ScrollEvent",
    "ScrollView",
    "SectionList",
    "SegmentedControl",
    "SelectionEvent",
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
    "WebNavigationEvent",
    "WebView",
]


def _install_contracts() -> None:
    """Register the built-in native contracts.

    Factories are the single source for Python signatures and native
    contracts. Code generation derives the contracts from them once
    (``sdk.builtins``, which release bundles omit); importing reads the
    generated document. A development checkout whose document predates a
    protocol change derives them instead.
    """
    from ..sdk import schema

    if not schema.load_builtin_contracts():
        from ..sdk.builtins import install

        install(globals())


_install_contracts()
del _install_contracts
