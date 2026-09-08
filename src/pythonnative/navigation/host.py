"""Bridge between the native screen host and the navigation tree.

The host wraps the app's root element in
[`HostRoot`][pythonnative.navigation.host.HostRoot], which publishes:

- [`HostContext`][pythonnative.navigation.host.HostContext]: the
  [`HostNavigator`][pythonnative.navigation.HostNavigator] a root stack
  uses to push and pop real native screens, and
- [`FocusContext`][pythonnative.navigation.handle.FocusContext]: whether
  the host's screen is currently presented (``on_resume`` /
  ``on_pause``), so [`use_is_focused`][pythonnative.use_is_focused]
  and [`use_focus_effect`][pythonnative.use_focus_effect] follow the
  platform lifecycle even outside any declarative navigator.

Pushed screens receive their navigation history under the
``"pn_nav"`` key of the host's launch arguments; the root stack reads
it through ``HostNavigator.initial_navigation_state``.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..component import component
from ..element import Element, Node
from ..hooks import Context, create_context, use_effect, use_state
from .handle import FocusContext, HostNavigator

__all__ = ["HostContext", "HostRoot", "NAV_STATE_ARG"]

NAV_STATE_ARG = "pn_nav"
"""Launch-argument key under which a pushed screen receives its serialized navigation state."""

HostContext: Context[Optional[HostNavigator]] = create_context(None, name="Host")
"""The native host bridging this tree, or ``None`` when rendering without one (tests, rows)."""


@component
def HostRoot(*children: Node, host: HostNavigator) -> Element:
    """Publish the host bridge and its focus state to the tree below."""
    focused, set_focused = use_state(bool(getattr(host, "is_focused", True)))

    def subscribe() -> Any:
        set_focused(bool(getattr(host, "is_focused", True)))
        return host.add_focus_listener(lambda value: set_focused(bool(value)))

    use_effect(subscribe, [host])
    return HostContext.Provider(host, FocusContext.Provider(focused, *children))


def initial_state_from_args(args: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Extract a serialized navigation state from host launch arguments."""
    if not isinstance(args, dict):
        return None
    state = args.get(NAV_STATE_ARG)
    if isinstance(state, dict) and state.get("routes"):
        return state
    return None
