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
        style=pn.style(spacing=12, padding=16),
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
    _all_extents_known,
    _dispatch_scroll_command,
    _native_lists_supported,
    _NativeList,
    _RowSpec,
    _VirtualizedList,
)
from .media import Image, ImageBackground, WebView
from .overlays import Modal, Portal
from .pressable import Pressable, TouchableOpacity, _StatefulPressable  # noqa: F401
from .structural import ErrorBoundary, Fragment, Suspense
from .text import Button, Text, TextInput

__all__ = [
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
]
