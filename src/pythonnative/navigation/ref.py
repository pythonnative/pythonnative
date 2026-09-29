"""``NavigationRef``: navigate from outside the component tree.

```python
nav_ref = pn.create_navigation_ref()

@pn.component
def App():
    return pn.NavigationContainer(Stack.Navigator(...), ref=nav_ref)

def on_push_notification(payload):
    if nav_ref.is_ready():
        nav_ref.navigate("Thread", id=payload["thread"])
```

The container binds the root navigator's handle to ``ref.current``
when it mounts and clears it on unmount. Every proxied method raises
``RuntimeError`` while no container is mounted, so call
``is_ready()`` first from code that may run before the UI is up.
"""

from __future__ import annotations

from typing import Any, Optional, Union

from .handle import Navigation
from .state import NavigationState, Route

__all__ = ["NavigationRef", "create_navigation_ref"]

_NOT_MOUNTED = "Navigation container is not mounted"


class NavigationRef:
    """Handle to the root navigator, usable outside components.

    Created by [`create_navigation_ref`][pythonnative.create_navigation_ref]
    and bound with ``NavigationContainer(ref=...)``. The proxied methods
    mirror [`Navigation`][pythonnative.Navigation] and act on the root
    navigator; reach a nested navigator's screen with
    ``ref.navigate("Tabs", screen="Profile", user="ada")``.

    Attributes:
        current: The root navigator's
            [`Navigation`][pythonnative.Navigation] handle, or ``None``
            while no container is mounted.
    """

    __slots__ = ("current",)

    def __init__(self) -> None:
        self.current: Optional[Navigation] = None

    def is_ready(self) -> bool:
        """Whether a ``NavigationContainer`` has bound this ref."""
        return self.current is not None

    def _require(self) -> Navigation:
        if self.current is None:
            raise RuntimeError(_NOT_MOUNTED)
        return self.current

    def navigate(self, route: str, /, *, screen: Optional[str] = None, **params: Any) -> None:
        """Go to ``route`` on the root navigator (see ``Navigation.navigate``)."""
        self._require().navigate(route, screen=screen, **params)

    def push(self, route: str, /, *, screen: Optional[str] = None, **params: Any) -> None:
        """Push ``route`` onto the root stack (see ``Navigation.push``)."""
        self._require().push(route, screen=screen, **params)

    def replace(self, route: str, /, *, screen: Optional[str] = None, **params: Any) -> None:
        """Replace the active screen with ``route`` (see ``Navigation.replace``)."""
        self._require().replace(route, screen=screen, **params)

    def pop(self, count: int = 1) -> bool:
        """Pop ``count`` screens; returns whether anything happened."""
        return self._require().pop(count)

    def go_back(self) -> bool:
        """Alias for ``pop()``."""
        return self._require().go_back()

    def pop_to(self, route: str, /, *, screen: Optional[str] = None, **params: Any) -> None:
        """Pop back to ``route`` (see ``Navigation.pop_to``)."""
        self._require().pop_to(route, screen=screen, **params)

    def pop_to_top(self) -> None:
        """Pop every screen above the first one."""
        self._require().pop_to_top()

    def reset(self, *routes: Union[str, Route], index: Optional[int] = None, **params: Any) -> None:
        """Replace the whole history (see ``Navigation.reset``)."""
        self._require().reset(*routes, index=index, **params)

    def get_state(self) -> NavigationState:
        """The root navigator's current state."""
        return self._require().get_state()

    def __repr__(self) -> str:
        return f"<NavigationRef {'ready' if self.is_ready() else 'unbound'}>"


def create_navigation_ref() -> NavigationRef:
    """Create a [`NavigationRef`][pythonnative.NavigationRef] to bind with ``NavigationContainer(ref=...)``.

    Create it at module level so push-notification handlers, deep-link
    code, and services can navigate without a component in scope.

    Example:
        ```python
        nav_ref = pn.create_navigation_ref()

        @pn.component
        def App():
            return pn.NavigationContainer(Stack.Navigator(...), ref=nav_ref)

        def open_thread(thread_id: int) -> None:
            if nav_ref.is_ready():
                nav_ref.navigate("Thread", id=thread_id)
        ```
    """
    return NavigationRef()
