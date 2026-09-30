"""Screen definitions, screen groups, and the typed options a screen accepts."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Dict, Iterable, Literal, Mapping, Optional, Sequence, TypedDict, Union, Unpack

from ..assets import Asset
from ..component import Component
from ..element import Element
from ..icons import IconName

if TYPE_CHECKING:
    from .navigators import Navigator

__all__ = [
    "PYTHON_ONLY_OPTIONS",
    "Animation",
    "Group",
    "Presentation",
    "Screen",
    "ScreenLike",
    "ScreenOptions",
    "ScreenTarget",
    "TabBarStyle",
    "find_screen",
    "flatten_screens",
    "validate_screen_options",
]

Presentation = Literal["card", "modal", "full_screen_modal", "form_sheet", "transparent_modal"]
"""How a stack screen is presented (see ``ScreenOptions.presentation``)."""

Animation = Literal["default", "none", "fade", "slide_from_right", "slide_from_bottom"]
"""Transition used when a stack screen is pushed (see ``ScreenOptions.animation``)."""


class ScreenOptions(TypedDict, total=False):
    """Per-screen options accepted by ``Screen(...)``, ``Group(...)``, ``screen_options=``, and ``set_options(...)``.

    All keys are optional. Navigators ignore keys they don't use; the
    native host applies the header keys it can (see the platform notes
    on each key). Options layer in this order, later entries winning:
    the navigator's ``screen_options``, each enclosing ``Group``, the
    ``Screen`` itself, then options set at runtime with
    [`use_screen_options`][pythonnative.use_screen_options] or
    ``nav.set_options(...)``.

    Attributes:
        title: Screen title. Stack navigators show it in the native
            navigation bar; tab and drawer navigators use it as the item
            label. Defaults to the route name.
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
        header_left: Element rendered at the leading edge of the
            navigation bar.
        header_right: Element rendered at the trailing edge of the
            navigation bar.
        header_tint_color: Color of the bar's buttons and back chevron.
            Defaults to the theme's ``colors.primary``.
        header_style: Style dict for the bar itself; ``background_color``
            is honored on every platform that draws a bar and defaults
            to the theme's ``colors.surface``.
        header_title_style: Style dict for the title label
            (``color``, ``font_size``, ``bold``). ``color`` defaults to
            the theme's ``colors.text``.
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
            ``pythonnative.icons`` (``"house"``, ``"settings"``) drawn as
            a vector on every platform, or a
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
            screen is unfocused, hold back new params (from
            ``set_params`` or a ``jump_to`` element) until it's focused
            again (default ``False``). Navigators already skip unfocused
            screens whose params didn't change, and the screen's own
            state updates still apply.
    """

    title: str
    header_shown: bool
    header_large_title: bool
    header_back_title: str
    header_back_visible: bool
    header_left: Optional[Element]
    header_right: Optional[Element]
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
    """Appearance of a tab navigator's bar, passed as ``TabNavigator(..., tab_bar_style=...)``.

    Every key is optional; unset keys fall back to the theme
    (``active_tint_color`` to ``colors.primary``, ``background_color``
    to ``colors.surface``) or to the platform default.

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


_ENUM_OPTIONS: Dict[str, frozenset[str]] = {
    "presentation": frozenset(("card", "modal", "full_screen_modal", "form_sheet", "transparent_modal")),
    "animation": frozenset(("default", "none", "fade", "slide_from_right", "slide_from_bottom")),
}

_KNOWN_OPTIONS = frozenset(ScreenOptions.__annotations__)


def validate_screen_options(options: Mapping[str, Any]) -> None:
    """Reject unknown option keys and ``presentation`` / ``animation`` values outside their ``Literal``.

    Raises:
        TypeError: If ``options`` names a key that isn't a ``ScreenOptions`` field.
        ValueError: If an enumerated option holds a value outside its ``Literal``.
    """
    unknown = sorted(set(options) - _KNOWN_OPTIONS)
    if unknown:
        raise TypeError(f"Unknown screen option(s) {unknown}; see pn.ScreenOptions for the supported keys")
    for key, allowed in _ENUM_OPTIONS.items():
        value = options.get(key)
        if value is not None and value not in allowed:
            raise ValueError(f"ScreenOptions.{key} must be one of {sorted(allowed)}, got {value!r}")


ScreenComponent = Union[Component[...], "Navigator"]
"""What a screen renders: a ``@component`` whose parameters are the route params, or a nested navigator."""


def _required_params(component: Any) -> list[str]:
    """Names of ``component``'s parameters that have no default (navigators have none)."""
    if not isinstance(component, Component):
        return []
    return [
        name
        for name, parameter in inspect.signature(component.fn).parameters.items()
        if parameter.default is inspect.Parameter.empty
        and parameter.kind not in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD)
    ]


class Screen:
    """One screen in a navigator: the component it renders, its route name, deep-link path, and options.

    A screen's component receives its route params as ordinary
    arguments, so the component's signature *is* the screen's params
    type:

    ```python
    @pn.component
    def ItemScreen(id: int, tab: str = "details") -> pn.Node: ...

    Root = pn.StackNavigator(pn.Screen(ItemScreen, title="Item", path="items/{id}"))
    nav.push(ItemScreen(id=42))
    ```

    A bare component or navigator listed in a navigator is shorthand
    for ``Screen(component)``.

    Args:
        component: The ``@component`` to render, or a nested
            [`Navigator`][pythonnative.navigation.Navigator].
        name: Route name, used in serialized state and diagnostics.
            Defaults to the component's name or the navigator's
            ``name``.
        path: Deep-link path relative to the enclosing navigator's
            path, with Python format placeholders for params
            (``"items/{id}"``). Params are converted with the
            component's annotations. Nested navigators use ``path`` as
            a prefix for their screens.
        **options: Static [`ScreenOptions`][pythonnative.ScreenOptions].

    Raises:
        TypeError: If ``component`` isn't a component or navigator, or
            an option key is unknown.
        ValueError: If no route name can be derived.
    """

    __slots__ = ("component", "name", "path", "options")

    def __init__(
        self,
        component: ScreenComponent,
        *,
        name: Optional[str] = None,
        path: Optional[str] = None,
        **options: Unpack[ScreenOptions],
    ) -> None:
        from .navigators import Navigator

        if not isinstance(component, (Component, Navigator)):
            raise TypeError(f"Screen expects a @component or a navigator, got {component!r}")
        resolved = name or (component.name if isinstance(component, Navigator) else component.display_name)
        if not resolved:
            raise ValueError(f"{component!r} needs a route name: pass Screen(..., name=...) or name the navigator")
        validate_screen_options(options)
        self.component = component
        self.name: str = resolved
        self.path = path.strip("/") if path is not None else None
        self.options: Dict[str, Any] = dict(options)

    @property
    def navigator(self) -> Optional["Navigator"]:
        """The nested navigator this screen renders, or ``None`` for a component screen."""
        from .navigators import Navigator

        return self.component if isinstance(self.component, Navigator) else None

    def required_params(self) -> list[str]:
        """Parameters the screen's component needs a value for."""
        return _required_params(self.component)

    def render(self, params: Mapping[str, Any]) -> Element:
        """Build the screen's element for a route carrying ``params``."""
        if isinstance(self.component, Component):
            return self.component(**params)
        return self.component()

    def matches(self, target: Any, *, exact: bool = False) -> bool:
        """Whether ``target`` (a component or navigator) is what this screen renders.

        Identity decides; unless ``exact``, a component replaced by Fast
        Refresh also matches its predecessor by module, qualified name,
        and display name. Components made by one factory share a qualified name, so
        callers try an identity match across every screen first (see
        ``find_screen``).
        """
        if target is self.component:
            return True
        if exact:
            return False
        if isinstance(target, Component) and isinstance(self.component, Component):
            return (target.__module__, getattr(target, "__qualname__", None), target.display_name) == (
                self.component.__module__,
                getattr(self.component, "__qualname__", None),
                self.component.display_name,
            )
        return False

    def __repr__(self) -> str:
        return f"Screen({self.name!r})"


class Group:
    """Screens that share a layer of options.

    ```python
    pn.StackNavigator(
        Home,
        pn.Group(pn.Screen(Compose), pn.Screen(Filters), presentation="modal"),
    )
    ```

    Args:
        *screens: The grouped screens (``Screen`` objects, bare
            components or navigators, or nested groups).
        **options: [`ScreenOptions`][pythonnative.ScreenOptions] layered
            between the navigator's ``screen_options`` and each
            screen's own options.
    """

    __slots__ = ("screens", "options")

    def __init__(self, *screens: "ScreenLike", **options: Unpack[ScreenOptions]) -> None:
        validate_screen_options(options)
        self.screens: tuple[ScreenLike, ...] = screens
        self.options: Dict[str, Any] = dict(options)

    def __repr__(self) -> str:
        return f"Group({list(self.screens)!r})"


def find_screen(screens: Iterable[Screen], target: Any) -> Optional[Screen]:
    """The screen rendering ``target``: an identity match wins over a Fast Refresh name match."""
    candidates = tuple(screens)
    for exact in (True, False):
        found = next((screen for screen in candidates if screen.matches(target, exact=exact)), None)
        if found is not None:
            return found
    return None


ScreenLike = Union[Screen, Group, Component[...], "Navigator"]
"""An entry in a navigator's screen list."""

ScreenTarget = Union[Element, Component[...], "Navigator"]
"""A navigation destination: an element carrying params, or a component or navigator with none."""


def flatten_screens(items: Sequence[ScreenLike]) -> tuple[tuple[Screen, ...], Dict[str, Dict[str, Any]]]:
    """Expand groups into ``(screens, group_options_by_name)``.

    Raises:
        TypeError: For an entry that isn't a screen, group, component, or navigator.
        ValueError: For duplicate route names.
    """
    from .navigators import Navigator

    screens: list[Screen] = []
    group_options: Dict[str, Dict[str, Any]] = {}

    def visit(entry: Any, inherited: Dict[str, Any]) -> None:
        if isinstance(entry, Group):
            merged = {**inherited, **entry.options}
            for child in entry.screens:
                visit(child, merged)
            return
        if isinstance(entry, (Component, Navigator)):
            entry = Screen(entry)
        if not isinstance(entry, Screen):
            raise TypeError(f"Navigators accept Screen(...), Group(...), components, and navigators, got {entry!r}")
        screens.append(entry)
        if inherited:
            group_options[entry.name] = inherited

    for item in items:
        visit(item, {})
    names = [screen.name for screen in screens]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"Duplicate screen names in navigator: {duplicates}; give one of them Screen(..., name=...)")
    return tuple(screens), group_options
