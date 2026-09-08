"""``NavigationContainer``: the root of a navigator tree.

The container wires the root navigator to the outside world: deep links
(via [`LinkingConfig`][pythonnative.LinkingConfig]), a caller-supplied
initial state, and ``on_state_change`` / ``on_ready`` callbacks. Every
app with navigation renders exactly one container at the top.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional, Union

from ..component import component
from ..element import Element, Node
from ..hooks import Context, create_context, use_effect, use_memo, use_ref
from .linking import LinkingConfig
from .state import NavigationState

__all__ = ["ContainerContext", "NavigationContainer"]

StateLike = Union[NavigationState, Mapping[str, Any]]


class ContainerConfig:
    """What a root navigator reads from its enclosing container."""

    __slots__ = ("initial_state", "on_state_change", "on_ready", "_root", "_ready")

    def __init__(
        self,
        initial_state: Optional[NavigationState],
        on_state_change: Optional[Callable[[NavigationState], None]],
        on_ready: Optional[Callable[[], None]],
    ) -> None:
        self.initial_state = initial_state
        self.on_state_change = on_state_change
        self.on_ready = on_ready
        self._root: Any = None
        self._ready = False

    def attach_root(self, core: Any) -> Callable[[], None]:
        """Register the root navigator core; returns a detach callable."""
        self._root = core
        if not self._ready:
            self._ready = True
            if self.on_ready is not None:
                self.on_ready()

        def detach() -> None:
            if self._root is core:
                self._root = None

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
    except Exception:
        return None


@component
def NavigationContainer(
    *children: Node,
    linking: Optional[LinkingConfig] = None,
    initial_state: Optional[StateLike] = None,
    on_state_change: Optional[Callable[[NavigationState], None]] = None,
    on_ready: Optional[Callable[[], None]] = None,
) -> Element:
    """Root of a navigator tree.

    Args:
        *children: The root navigator (a ``Stack.Navigator``, ``Tab.Navigator``,
            or ``Drawer.Navigator``) and anything rendered alongside it.
        linking: Deep-link configuration. The URL the app was launched
            with seeds the initial state; URLs that arrive later are
            dispatched as ``navigate`` calls.
        initial_state: Explicit initial state for the root navigator
            (a ``NavigationState`` or its ``to_dict()`` form). Takes
            precedence over the launch URL. State restored by a native
            host (a pushed native screen re-entering Python) takes
            precedence over both.
        on_state_change: Called with the root navigator's state after
            every change. Persist ``state.to_dict()`` to restore later.
        on_ready: Called once the root navigator has mounted.

    Example:
        ```python
        Stack = pn.create_stack_navigator()

        @pn.component
        def App():
            return pn.NavigationContainer(
                Stack.Navigator(
                    Stack.Screen("Home", HomeScreen),
                    Stack.Screen("Detail", DetailScreen, options={"title": "Detail"}),
                ),
                linking=linking,
            )
        ```
    """
    coerced = _coerce_state(initial_state)

    def build() -> ContainerConfig:
        seed = coerced
        if seed is None and linking is not None:
            from ..native_modules.linking import Linking

            url = Linking.get_initial_url()
            if url:
                seed = linking.state_from_url(url)
        return ContainerConfig(seed, on_state_change, on_ready)

    config = use_memo(build, [])
    config.on_state_change = on_state_change
    config.on_ready = on_ready

    initial_url: Any = use_ref(None)

    def subscribe() -> Optional[Callable[[], None]]:
        if linking is None:
            return None
        from ..native_modules.linking import Linking

        initial_url.current = Linking.get_initial_url()

        def on_url(url: str) -> None:
            # The initial URL already seeded the state; don't navigate twice.
            if url == initial_url.current:
                initial_url.current = None
                return
            seed = linking.state_from_url(url)
            if seed is not None:
                config.dispatch_seed(seed)

        return Linking.add_listener(on_url)

    use_effect(subscribe, [linking])

    return ContainerContext.Provider(config, *children)
