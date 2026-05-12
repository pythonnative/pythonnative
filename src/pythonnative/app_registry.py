"""App component registration for the `pn.run(App)` entry point.

The ``pn.run`` convention mirrors ``AppRegistry.registerComponent`` in
React Native: the user's app module declares a top-level component
function and registers it once at import time. Native templates then
load the app via a single dotted module path (e.g. ``"app.main_page"``)
without needing to know the App component's exact name.

Example:
    ```python
    import pythonnative as pn

    @pn.component
    def App():
        return pn.NavigationContainer(...)

    pn.run(App)
    ```

The Android (``PageFragment.kt``) and iOS (``ViewController.swift``)
templates pass the module path to
[`create_page`][pythonnative.create_page], which imports the module
(triggering this registration) and looks up the registered component.
"""

from typing import Any, Callable, Optional

_registered_app: Optional[Callable[..., Any]] = None
"""Module-level holder for the most recently registered App component.

A single registration slot is intentional: real apps have exactly one
root component. Re-calling :func:`register` simply overwrites the
previous value — useful for tests and hot reloading.
"""


def register(component: Callable[..., Any]) -> None:
    """Register the App component for this Python process.

    Args:
        component: A zero-argument ``@component`` function that returns
            an [`Element`][pythonnative.Element]. Typically wraps a
            [`NavigationContainer`][pythonnative.NavigationContainer]
            at the root.

    Raises:
        TypeError: If ``component`` is not callable.
    """
    global _registered_app
    if not callable(component):
        raise TypeError(f"pn.run expects a callable component, got {type(component).__name__}")
    _registered_app = component


def get_registered_app() -> Optional[Callable[..., Any]]:
    """Return the registered App component, or ``None`` if not set."""
    return _registered_app


def clear() -> None:
    """Reset the registered App. Used by tests and full-host resets."""
    global _registered_app
    _registered_app = None
