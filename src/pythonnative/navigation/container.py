"""``NavigationContainer``: the root of a navigator tree.

The container renders the root navigator and wires it to the outside
world: deep links derived from the navigators' screen paths, a
caller-supplied initial state, ``on_state_change`` / ``on_ready``
callbacks, and a [`NavigationRef`][pythonnative.NavigationRef] for
navigating from outside the tree. Navigator chrome takes its colors
from the app [`Theme`][pythonnative.Theme]. Every app with navigation
renders exactly one container at the top.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Mapping, Optional, Sequence, Union

from ..component import component
from ..element import Element
from ..hooks import Context, create_context, use_effect, use_memo, use_ref
from .handle import provide
from .linking import LinkTable
from .ref import NavigationRef
from .state import NavigationState

if TYPE_CHECKING:
    from .navigators import Navigator

__all__ = ["ContainerContext", "NavigationContainer"]

StateLike = Union[NavigationState, Mapping[str, Any]]


class ContainerConfig:
    """What a root navigator reads from its enclosing container."""

    __slots__ = ("initial_state", "on_state_change", "on_ready", "ref", "_root", "_ready")

    def __init__(
        self,
        initial_state: Optional[NavigationState],
        on_state_change: Optional[Callable[[NavigationState], None]],
        on_ready: Optional[Callable[[], None]],
        ref: Optional[NavigationRef] = None,
    ) -> None:
        self.initial_state = initial_state
        self.on_state_change = on_state_change
        self.on_ready = on_ready
        self.ref = ref
        self._root: Any = None
        self._ready = False

    def attach_root(self, core: Any) -> Callable[[], None]:
        """Register the root navigator core and bind the ``NavigationRef``; returns a detach callable."""
        self._root = core
        if self.ref is not None:
            self.ref.current = core.container_handle()
        if not self._ready:
            self._ready = True
            if self.on_ready is not None:
                self.on_ready()

        def detach() -> None:
            if self._root is core:
                self._root = None
                if self.ref is not None:
                    self.ref.current = None

        return detach

    def dispatch_seed(self, seed: NavigationState) -> bool:
        """Route a deep-link state to the root navigator (``False`` if none is mounted)."""
        if self._root is None:
            return False
        target = seed.current
        self._root.navigate(target.name, target.params, target.state)
        return True


ContainerContext: Context[Optional[ContainerConfig]] = create_context(None, name="NavigationContainer")


def _coerce_state(value: Optional[StateLike]) -> Optional[NavigationState]:
    if value is None or isinstance(value, NavigationState):
        return value
    try:
        return NavigationState.from_dict(value)
    except (AttributeError, KeyError, TypeError, ValueError, IndexError):
        return None


@component
def NavigationContainer(
    navigator: "Navigator",
    *,
    link_prefixes: Sequence[str] = (),
    initial_state: Optional[StateLike] = None,
    on_state_change: Optional[Callable[[NavigationState], None]] = None,
    on_ready: Optional[Callable[[], None]] = None,
    ref: Optional[NavigationRef] = None,
) -> Element:
    """Render ``navigator`` as the root of the app's navigation.

    Args:
        navigator: The root [`StackNavigator`][pythonnative.StackNavigator],
            [`TabNavigator`][pythonnative.TabNavigator], or
            [`DrawerNavigator`][pythonnative.DrawerNavigator].
        link_prefixes: URL prefixes that open deep links (``"myapp://"``,
            ``"https://example.com"``). Paths come from each screen's
            ``path``. The URL the app was launched with seeds the
            initial state; URLs that arrive later navigate. Empty
            disables deep linking.
        initial_state: Explicit initial state for the root navigator
            (a ``NavigationState`` or its ``to_dict()`` form). Takes
            precedence over the launch URL. State restored by a native
            host (a pushed native screen re-entering Python) takes
            precedence over both.
        on_state_change: Called with the root navigator's state after
            every change. Persist ``state.to_dict()`` to restore later.
        on_ready: Called once the root navigator has mounted.
        ref: A [`NavigationRef`][pythonnative.NavigationRef]; bound to the
            root navigator while the container is mounted.

    Example:
        ```python
        Root = pn.StackNavigator(pn.Screen(HomeScreen, title="Home"), pn.Screen(ItemScreen, path="items/{id}"))
        nav_ref = pn.NavigationRef()


        @pn.component
        def App() -> pn.Node:
            return pn.NavigationContainer(Root, link_prefixes=["myapp://"], ref=nav_ref)
        ```
    """
    coerced = _coerce_state(initial_state)
    links: Optional[LinkTable] = use_memo(
        lambda: LinkTable(navigator, link_prefixes) if link_prefixes else None,
        [navigator, tuple(link_prefixes)],
    )

    def build() -> ContainerConfig:
        seed = coerced
        if seed is None and links is not None:
            from ..native_modules.linking import Linking

            url = Linking.get_initial_url()
            if url:
                seed = links.state_from_url(url)
        return ContainerConfig(seed, on_state_change, on_ready, ref)

    config = use_memo(
        build,
        [],  # pn: ignore[PN103] built once; later renders update the config in place
    )
    config.on_state_change = on_state_change
    config.on_ready = on_ready
    if config.ref is not ref:
        # The ref changed between renders: move the binding over.
        if config.ref is not None:
            config.ref.current = None
        config.ref = ref
        if ref is not None and config._root is not None:
            ref.current = config._root.container_handle()

    initial_url: Any = use_ref(None)

    def subscribe() -> Optional[Callable[[], None]]:
        if links is None:
            return None
        from ..native_modules.linking import Linking

        initial_url.current = Linking.get_initial_url()

        def on_url(url: str) -> None:
            # The initial URL already seeded the state; don't navigate twice.
            if url == initial_url.current:
                initial_url.current = None
                return
            seed = links.state_from_url(url)
            if seed is not None:
                config.dispatch_seed(seed)

        return Linking.add_listener(on_url)

    use_effect(subscribe, [links])

    return provide(ContainerContext, config, navigator())
