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

import importlib
from typing import TYPE_CHECKING, Any

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
from .graphics import BlurType, BlurView, LinearGradient
from .layout import (
    Column,
    KeyboardAvoidingView,
    Row,
    SafeAreaView,
    ScrollView,
    Spacer,
    View,
)
from .media import Image, ImageBackground, ImageSource, WebView
from .overlays import Modal, Portal
from .pressable import Pressable, PressState, Ripple
from .structural import ErrorBoundary, Fragment, StrictMode, Suspense, set_error_fallback
from .text import Button, EllipsizeMode, KeyboardAppearance, Text, TextInput

if TYPE_CHECKING:
    from .lists import FlatList, ListController, SectionList
    from .vector import PreserveAspectRatio, Svg

# The list components and ``Svg`` (with ``pythonnative.svg``) load on first
# use (PEP 562), so ``import pythonnative`` doesn't pay for them.
_LAZY = {
    "FlatList": "lists",
    "ListController": "lists",
    "SectionList": "lists",
    "PreserveAspectRatio": "vector",
    "Svg": "vector",
}

__all__ = [
    "set_error_fallback",
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
    "StrictMode",
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

        install(_factories())


def __getattr__(name: str) -> Any:
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(f".{module}", __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | _LAZY.keys())


def _factories() -> dict[str, Any]:
    """Every public name in this package, loading the lazy ones (contract derivation reads them all)."""
    return {name: globals()[name] if name in globals() else __getattr__(name) for name in __all__}


_install_contracts()
del _install_contracts
