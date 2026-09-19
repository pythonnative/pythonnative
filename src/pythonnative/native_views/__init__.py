"""The view backend the reconciler commits to.

The reconciler talks to exactly one object, obtained from
[`get_backend`][pythonnative.native_views.get_backend], through a small
protocol: ``apply_mutations`` (one ordered batch of
create/update/insert/destroy/frame ops per commit, see
`pythonnative.mutations`), ``resolve_view``, ``measure_intrinsic``,
``command``, and the animation hooks (``set_animated_property``,
``start_animation``, ``cancel_animation``). Two implementations exist:

- [`BridgeBackend`][pythonnative.native_views.bridge_backend.BridgeBackend]
  (iOS, Android, and the browser preview): serializes each commit and
  hands it to the native runtime through the bridge; the Swift and
  Kotlin component managers, or the preview page's DOM applier, own
  every platform view. Python holds no native objects. ``resolve_view``
  answers with a [`NativeViewRef`][pythonnative.native_views.NativeViewRef].
- [`FakeBackend`][pythonnative.testing.FakeBackend] (headless tests):
  keeps an inspectable tree of fake views. Tests install one with
  [`set_backend`][pythonnative.native_views.set_backend].

Platform selection happens lazily on first use, so this package imports
on any platform. Off device, with no backend installed, ``get_backend``
raises instead of guessing.
"""

from typing import Any, Union

from .bridge_backend import BridgeBackend, NativeViewRef

__all__ = ["BridgeBackend", "NativeViewRef", "get_backend", "parse_color_int", "set_backend"]

_backend: Any = None


def _create_backend() -> Any:
    """Build the backend for the active platform.

    iOS, Android, and the browser preview (``PN_PLATFORM=web``) get the
    bridge backend, after importing any ``pythonnative.handlers`` entry
    points so plugin component schemas are registered before the first
    commit is validated. Anywhere else there is no renderer at all.
    """
    from ..utils import IS_NATIVE

    if not IS_NATIVE:
        raise RuntimeError(
            "No view backend is available off device. Run the app with `pn preview`, or install "
            "pythonnative.testing.FakeBackend with pythonnative.native_views.set_backend() in tests."
        )
    from ..sdk._components import discover_components

    discover_components()
    return BridgeBackend()


def get_backend() -> Any:
    """Return the process-wide view backend, creating the bridge backend on first use.

    Raises:
        RuntimeError: Off device when no backend was installed with
            [`set_backend`][pythonnative.native_views.set_backend].
    """
    global _backend
    if _backend is None:
        _backend = _create_backend()
    return _backend


def set_backend(backend: Any) -> None:
    """Install a backend explicitly (tests), or pass ``None`` to reset the singleton.

    Args:
        backend: The replacement backend, or ``None`` to clear so the
            next ``get_backend`` call rebuilds the platform backend.
    """
    global _backend
    _backend = backend


def parse_color_int(color: Union[str, int]) -> int:
    """Parse a color value into a signed 32-bit ARGB int.

    Accepts ``"#RRGGBB"``, ``"#AARRGGBB"``, or a raw integer. Java APIs
    such as ``setBackgroundColor`` expect a signed 32-bit int, so values
    with a high alpha byte (``0xFF......``) become their negative
    two's-complement equivalent. Kept for extension authors writing
    Python-side color plumbing; the renderers parse colors natively.

    Args:
        color: Hex string (with or without leading ``#``) or an int.

    Returns:
        Signed 32-bit ARGB int suitable for Android's color APIs.
    """
    if isinstance(color, int):
        val = color
    else:
        c = color.strip().lstrip("#")
        if len(c) == 6:
            c = "FF" + c
        val = int(c, 16)
    if val > 0x7FFFFFFF:
        val -= 0x100000000
    return val
