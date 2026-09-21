"""Screen definitions, screen groups, and the typed options a screen accepts."""

from __future__ import annotations

from typing import Any, Callable, Dict, Literal, Mapping, Optional, Sequence, TypedDict, Union, Unpack

from ..assets import Asset
from ..element import Element
from ..icons import IconName

__all__ = [
    "PYTHON_ONLY_OPTIONS",
    "Animation",
    "HeaderSlot",
    "OptionsLike",
    "Presentation",
    "ScreenDef",
    "ScreenGroup",
    "ScreenOptions",
    "TabBarStyle",
    "Unpack",
    "flatten_screens",
    "resolve_options",
    "validate_screen_options",
]

HeaderSlot = Union[Element, Callable[[], Optional[Element]], None]
"""An element (or zero-arg factory) rendered into a header slot."""

Presentation = Literal["card", "modal", "full_screen_modal", "form_sheet", "transparent_modal"]
"""How a stack screen is presented (see ``ScreenOptions.presentation``)."""

Animation = Literal["default", "none", "fade", "slide_from_right", "slide_from_bottom"]
"""Transition used when a stack screen is pushed (see ``ScreenOptions.animation``)."""


class ScreenOptions(TypedDict, total=False):
    """Per-screen options accepted by ``Screen(...)``, ``Group(...)``, ``Navigator(...)``, and ``set_options(...)``.

    All keys are optional. Navigators ignore keys they don't use; the
    native host applies the header keys it can (see the platform notes
    on each key). Options layer in this order, later entries winning:
    ``Navigator(screen_options=...)``, ``Group(screen_options=...)``,
    the ``Screen`` itself, then ``nav.set_options(...)`` at runtime.

    The native ``Screen`` element also carries ``guarded``, an internal
    wire prop that isn't a user option: the stack navigator sets it
    while the route has a ``before_remove`` listener so iOS refuses the
    pop or dismiss synchronously and lets Python decide.

    Attributes:
        title: Screen title. Stack navigators show it in the native
            navigation bar; tab and drawer navigators use it as the item
            label.
        header_shown: Whether the navigation bar is visible for this
            screen (default ``True``).
        header_large_title: Use a large title that collapses on scroll.
            iOS renders the system large title; Android renders an
            expanded toolbar with a larger title.
        header_back_title: iOS only: label of the back button shown on
            the *next* screen when it navigates back to this one.
            Android shows a bare back arrow and ignores this key.
        header_back_visible: Whether the back button is shown
            (default ``True``).
        header_left: Element (or factory) rendered at the leading edge
            of the navigation bar.
        header_right: Element (or factory) rendered at the trailing edge
            of the navigation bar.
        header_tint_color: Color of the bar's buttons and back chevron.
            Defaults to the navigation theme's ``primary`` color.
        header_style: Style dict for the bar itself; ``background_color``
            is honored on every platform that draws a bar and defaults
            to the theme's ``card`` color.
        header_title_style: Style dict for the title label
            (``color``, ``font_size``, ``bold``). ``color`` defaults to
            the theme's ``text`` color.
        presentation: ``"card"`` (default) pushes onto the stack. The
            modal styles present the screen over the stack: on iOS
            ``"modal"`` is a page sheet, ``"full_screen_modal"`` covers
            the screen, ``"form_sheet"`` is a centered form sheet, and
            ``"transparent_modal"`` is presented over the current
            context with a transparent background. Android presents
            every modal style as a full-screen screen with a
            slide-from-bottom transition, which is what React
            Navigation's native stack does there.
        gesture_enabled: iOS only: whether the interactive swipe-back
            gesture can pop this screen (default ``True``). Android's
            system back is always available.
        animation: Transition used when the screen is pushed:
            ``"default"``, ``"none"``, ``"fade"``, ``"slide_from_right"``,
            or ``"slide_from_bottom"``. Honored on iOS and Android.
        tab_bar_icon: Icon for the tab item: a bundled icon name from
            ``pythonnative.icons`` (``"house"``,
            ``"settings"``) drawn as a vector on every platform, or a
            [`pn.asset`][pythonnative.asset] pointing at a PNG that's
            drawn as a template image.
        tab_bar_badge: Badge text or count shown on the tab item.
        tab_bar_label: Label used for the tab item when it should differ
            from ``title``.
        tab_bar_visible: Tab navigators only: whether the tab bar is
            shown while this tab is focused (default ``True``). Set it
            to ``False`` on a tab whose nested stack pushes detail
            screens, or toggle it at runtime with
            ``nav.get_parent().set_options(tab_bar_visible=False)``.
        lazy: Tab and drawer navigators only: mount the screen the first
            time it's focused (default ``True``) instead of at
            navigator mount.
        unmount_on_blur: Tab and drawer navigators only: unmount the
            screen when it loses focus instead of keeping it alive
            hidden (default ``False``).
        freeze_on_blur: Tab and drawer navigators only: while the
            screen is unfocused, reuse its last rendered element instead
            of re-rendering it when the navigator re-renders (default
            ``False``). The screen's own state updates still apply; it
            renders fresh again when it regains focus.
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
    presentation: Presentation
    gesture_enabled: bool
    animation: Animation
    tab_bar_icon: Union[IconName, Asset]
    tab_bar_badge: Union[str, int]
    tab_bar_label: str
    tab_bar_visible: bool
    lazy: bool
    unmount_on_blur: bool
    freeze_on_blur: bool


PYTHON_ONLY_OPTIONS = frozenset({"header_left", "header_right", "tab_bar_icon", "tab_bar_visible", "freeze_on_blur"})
"""Options consumed by Python that never travel to the native ``Screen`` element."""


class TabBarStyle(TypedDict, total=False):
    """Appearance of a tab navigator's bar, passed as ``Tab.Navigator(tab_bar_style=...)``.

    Every key is optional; unset keys fall back to the navigation
    theme (``active_tint_color`` to ``primary``, ``background_color``
    to ``card``) or to the platform default.

    Attributes:
        background_color: Bar background.
        active_tint_color: Tint of the selected item's icon and label.
        inactive_tint_color: Tint of unselected items.
        translucent: iOS: whether the bar blurs the content behind it.
            Ignored on Android.
        show_labels: Whether item labels are shown next to icons
            (default ``True``).
    """

    background_color: str
    active_tint_color: str
    inactive_tint_color: str
    translucent: bool
    show_labels: bool


OptionsLike = Union[ScreenOptions, Mapping[str, Any], Callable[[Any], Optional[Mapping[str, Any]]], None]
"""Static options, a ``(route) -> options`` callable, or ``None``."""

_ENUM_OPTIONS: Dict[str, frozenset] = {
    "presentation": frozenset(("card", "modal", "full_screen_modal", "form_sheet", "transparent_modal")),
    "animation": frozenset(("default", "none", "fade", "slide_from_right", "slide_from_bottom")),
}


def validate_screen_options(options: Mapping[str, Any]) -> None:
    """Reject unknown ``presentation`` and ``animation`` values.

    Raises:
        ValueError: If an enumerated option holds a value outside its ``Literal``.
    """
    for key, allowed in _ENUM_OPTIONS.items():
        value = options.get(key)
        if value is not None and value not in allowed:
            raise ValueError(f"ScreenOptions.{key} must be one of {sorted(allowed)}, got {value!r}")


def resolve_options(options: OptionsLike, route: Any) -> Dict[str, Any]:
    """Evaluate ``options`` for ``route``: call a callable, copy a mapping, or return ``{}`` for ``None``."""
    if options is None:
        return {}
    resolved = dict(options(route) or {}) if callable(options) else dict(options)
    validate_screen_options(resolved)
    return resolved


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
        options: OptionsLike = None,
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
            self.options: Union[ScreenOptions, Callable[[Any], ScreenOptions]] = options  # type: ignore[assignment]
        else:
            merged: Dict[str, Any] = dict(options or {})
            merged.update(option_kwargs)
            validate_screen_options(merged)
            self.options = merged  # type: ignore[assignment]
        self.initial_params: Dict[str, Any] = dict(initial_params or {})

    def resolve_options(self, route: Any) -> Dict[str, Any]:
        """Return the static options, evaluating a callable ``options`` for ``route``."""
        return resolve_options(self.options, route)

    def __repr__(self) -> str:
        return f"Screen({self.name!r})"


class ScreenGroup:
    """Screens that share a layer of options, created by ``Navigator.Group(*screens, screen_options=...)``.

    A group has no state of its own: the navigator flattens its screens
    into the route list and layers ``screen_options`` between the
    navigator's options and each screen's own.

    Attributes:
        screens: The grouped [`ScreenDef`][pythonnative.navigation.ScreenDef]s, in order.
        screen_options: Options applied to every screen in the group
            (a mapping or ``(route) -> options``).
    """

    __slots__ = ("screens", "screen_options")

    def __init__(self, screens: Sequence[ScreenDef], screen_options: OptionsLike = None) -> None:
        for screen in screens:
            if not isinstance(screen, ScreenDef):
                raise TypeError(f"Group accepts Screen(...) definitions, got {screen!r}")
        self.screens: tuple[ScreenDef, ...] = tuple(screens)
        if screen_options is not None and not callable(screen_options):
            validate_screen_options(screen_options)
        self.screen_options = screen_options

    def __repr__(self) -> str:
        return f"Group({[s.name for s in self.screens]!r})"


def flatten_screens(
    items: Sequence[Union[ScreenDef, ScreenGroup]],
) -> tuple[tuple[ScreenDef, ...], Dict[str, OptionsLike]]:
    """Expand groups into ``(screens, group_options_by_name)``; duplicate names raise ``ValueError``."""
    screens: list[ScreenDef] = []
    group_options: Dict[str, OptionsLike] = {}
    for item in items:
        if isinstance(item, ScreenGroup):
            for screen in item.screens:
                screens.append(screen)
                if item.screen_options is not None:
                    group_options[screen.name] = item.screen_options
        elif isinstance(item, ScreenDef):
            screens.append(item)
        else:
            raise TypeError(f"Navigator accepts Screen(...) and Group(...) definitions, got {item!r}")
    names = [screen.name for screen in screens]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"Duplicate screen names in navigator: {duplicates}")
    return tuple(screens), group_options
