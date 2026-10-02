"""``NavigationRef``: navigate from outside the component tree.

```python
nav_ref = pn.NavigationRef()


@pn.component
def App() -> pn.Node:
    return pn.NavigationContainer(Root, ref=nav_ref)


def on_push_notification(payload: dict[str, str]) -> None:
    if nav_ref.is_ready():
        nav_ref.navigate(ThreadScreen(id=payload["thread"]))
```

The container binds the root navigator's handle to ``ref.current``
when it mounts and clears it on unmount. Every proxied method raises
``RuntimeError`` while no container is mounted, so call
``is_ready()`` first from code that may run before the UI is up.
"""

from __future__ import annotations

from typing import Optional

from ..element import Element
from .handle import Navigation
from .screen import ScreenTarget
from .state import NavigationState

__all__ = ["NavigationRef"]

_NOT_MOUNTED = "Navigation container is not mounted"


class NavigationRef:
    """Handle to the root navigator, usable outside components.

    Create one at module level and bind it with
    ``NavigationContainer(ref=...)``, so push-notification handlers,
    deep-link code, and services can navigate without a component in
    scope. The proxied methods mirror [`Navigation`][pythonnative.Navigation]
    and act from the root navigator, which reaches every statically
    nested screen.

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

    def navigate(self, target: Element, /) -> None:
        """Go to ``target`` (see ``Navigation.navigate``)."""
        self._require().navigate(target)

    def push(self, target: Element, /) -> None:
        """Push ``target`` (see ``Navigation.push``)."""
        self._require().push(target)

    def replace(self, target: Element, /) -> None:
        """Replace the active screen with ``target`` (see ``Navigation.replace``)."""
        self._require().replace(target)

    def pop(self, count: int = 1) -> bool:
        """Pop ``count`` screens; returns whether anything happened."""
        return self._require().pop(count)

    def go_back(self) -> bool:
        """Pop one screen; returns whether anything happened."""
        return self._require().go_back()

    def pop_to(self, target: ScreenTarget, /) -> None:
        """Pop back to ``target`` (see ``Navigation.pop_to``)."""
        self._require().pop_to(target)

    def pop_to_top(self) -> None:
        """Pop every screen above the first one."""
        self._require().pop_to_top()

    def reset(self, *targets: Element, index: Optional[int] = None) -> None:
        """Replace the root navigator's history (see ``Navigation.reset``)."""
        self._require().reset(*targets, index=index)

    def get_state(self) -> NavigationState:
        """The root navigator's current state."""
        return self._require().get_state()

    def __repr__(self) -> str:
        return f"<NavigationRef {'ready' if self.is_ready() else 'unbound'}>"
