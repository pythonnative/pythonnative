"""Screen definitions and the typed options a screen accepts."""

from __future__ import annotations

import sys
from typing import Any, Callable, Dict, Literal, Mapping, Optional, TypedDict, Union

if sys.version_info >= (3, 11):
    from typing import Unpack
else:  # pragma: no cover
    from typing_extensions import Unpack

from ..element import Element

__all__ = ["HeaderSlot", "ScreenDef", "ScreenOptions", "Unpack"]

HeaderSlot = Union[Element, Callable[[], Optional[Element]], None]
"""An element (or zero-arg factory) rendered into a header slot."""


class ScreenOptions(TypedDict, total=False):
    """Per-screen options accepted by ``Screen(...)`` and ``nav.set_options(...)``.

    All keys are optional. Navigators ignore keys they don't use; the
    native host applies the header keys it can (see the platform notes
    on each key).

    Attributes:
        title: Screen title. Stack navigators show it in the native
            navigation bar; tab and drawer navigators use it as the item
            label.
        header_shown: Whether the native navigation bar is visible for
            this screen (default ``True``).
        header_large_title: iOS: use a large title that collapses on
            scroll. Ignored elsewhere.
        header_back_title: iOS: label of the back button shown on the
            *next* screen when it navigates back to this one. Ignored
            elsewhere.
        header_back_visible: Whether the back button is shown
            (default ``True``).
        header_left: Element (or factory) rendered at the leading edge
            of the navigation bar. Rendered by PythonNative into the bar
            on iOS; ignored on Android and desktop today.
        header_right: Element (or factory) rendered at the trailing edge
            of the navigation bar (same platform notes as
            ``header_left``).
        header_tint_color: Color of the bar's buttons and back chevron.
        header_style: Style dict for the bar itself; ``background_color``
            is honored on every platform that draws a bar.
        header_title_style: Style dict for the title label
            (``color``, ``font_size``, ``bold``).
        presentation: ``"card"`` (default) pushes; ``"modal"`` presents
            the screen as a sheet on iOS and as a full-screen push
            elsewhere.
        gesture_enabled: Whether the interactive back gesture (iOS
            swipe) can pop this screen (default ``True``).
        animation: Transition to use when the screen is pushed:
            ``"default"``, ``"none"``, ``"fade"``, ``"slide_from_right"``,
            ``"slide_from_bottom"``. Only ``"none"`` versus animated is
            distinguished on iOS and Android today.
        tab_bar_icon: Native system icon identifier for tab items. A
            string is used on every platform; a dict like
            ``{"ios": "house.fill", "android": "ic_menu_home"}`` selects
            per platform (SF Symbols on iOS, ``android.R.drawable.<name>``
            on Android).
        tab_bar_badge: Badge text or count shown on the tab item.
        tab_bar_label: Label used for the tab item when it should differ
            from ``title``.
        lazy: Tab and drawer navigators only: mount the screen the first
            time it's focused (default ``True``) instead of at
            navigator mount.
        unmount_on_blur: Tab and drawer navigators only: unmount the
            screen when it loses focus instead of keeping it alive
            hidden (default ``False``).
    """

    title: str
    header_shown: bool
    header_large_title: bool
    header_back_title: str
    header_back_visible: bool
    header_left: HeaderSlot
    header_right: HeaderSlot
    header_tint_color: str
    header_style: Dict[str, Any]
    header_title_style: Dict[str, Any]
    presentation: Literal["card", "modal"]
    gesture_enabled: bool
    animation: Literal["default", "none", "fade", "slide_from_right", "slide_from_bottom"]
    tab_bar_icon: Union[str, Dict[str, str]]
    tab_bar_badge: Union[str, int]
    tab_bar_label: str
    lazy: bool
    unmount_on_blur: bool


class ScreenDef:
    """Configuration for one screen inside a navigator.

    Created by ``Navigator.Screen(name, component, **options)``.

    Attributes:
        name: Route name used by ``nav.navigate(name)``.
        component: The ``@component`` rendered when this screen is
            active. Receives no props; read params with
            [`use_route`][pythonnative.use_route].
        options: Static [`ScreenOptions`][pythonnative.ScreenOptions]
            for the screen. May be a callable ``(route) -> options`` to
            derive options from the route's params.
        initial_params: Params merged under any params supplied by
            ``navigate`` when this screen is first shown.
    """

    __slots__ = ("name", "component", "options", "initial_params")

    def __init__(
        self,
        name: str,
        component: Callable[[], Any],
        *,
        options: Union[ScreenOptions, Callable[[Any], ScreenOptions], None] = None,
        initial_params: Optional[Mapping[str, Any]] = None,
        **option_kwargs: Unpack[ScreenOptions],
    ) -> None:
        if not name or not isinstance(name, str):
            raise TypeError("Screen name must be a non-empty string")
        if not callable(component):
            raise TypeError(f"Screen {name!r}: component must be a @component, got {component!r}")
        self.name = name
        self.component = component
        if callable(options):
            if option_kwargs:
                raise TypeError("Pass either a callable `options` or keyword options, not both")
            self.options: Union[ScreenOptions, Callable[[Any], ScreenOptions]] = options
        else:
            merged: Dict[str, Any] = dict(options or {})
            merged.update(option_kwargs)
            self.options = merged  # type: ignore[assignment]
        self.initial_params: Dict[str, Any] = dict(initial_params or {})

    def resolve_options(self, route: Any) -> Dict[str, Any]:
        """Return the static options, evaluating a callable ``options`` for ``route``."""
        opts = self.options
        if callable(opts):
            return dict(opts(route) or {})
        return dict(opts)

    def __repr__(self) -> str:
        return f"Screen({self.name!r})"
