"""Window and screen size, pixel density, and pixel rounding.

[`Dimensions`][pythonnative.Dimensions] and
[`PixelRatio`][pythonnative.PixelRatio] mirror React Native's modules of
the same names. Neither talks to a native module: the screen host
publishes ``width``, ``height``, ``scale``, ``font_scale``,
``screen_width``, and ``screen_height`` into
``platform_metrics`` on every layout
pass, and these classes read from there. That makes them usable
anywhere, including outside components; inside a component prefer
[`use_window_dimensions`][pythonnative.use_window_dimensions], which
re-renders on change.

Example:
    ```python
    import pythonnative as pn

    window = pn.Dimensions.get("window")
    columns = 3 if window.width >= 600 else 2
    hairline = pn.PixelRatio.round_to_nearest_pixel(0.5)
    ```
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from .. import platform_metrics
from ..platform_metrics import WindowDimensions

DimensionsScope = Literal["window", "screen"]


@dataclass(frozen=True)
class DimensionsEvent:
    """Both sizes after a change, as React Native's ``Dimensions`` listener receives them.

    Attributes:
        window: The area the app draws into.
        screen: The whole display.
    """

    window: WindowDimensions
    screen: WindowDimensions


class Dimensions:
    """Window and screen size in layout units (pt on iOS, dp on Android)."""

    @staticmethod
    def get(which: DimensionsScope = "window") -> WindowDimensions:
        """Return the current window or screen size.

        Args:
            which: ``"window"`` for the area the app occupies (excluding
                nothing the host hasn't subtracted; the keyboard is
                reported separately), ``"screen"`` for the whole display.
                Hosts that don't distinguish them report the window for
                both.

        Returns:
            A [`WindowDimensions`][pythonnative.platform_metrics.WindowDimensions]
            with ``width``, ``height``, ``scale``, and ``font_scale``. Width
            and height are ``0.0`` before the host's first layout pass.

        Raises:
            ValueError: For a value other than ``"window"`` or ``"screen"``.
        """
        if which == "window":
            return platform_metrics.get_window_dimensions()
        if which == "screen":
            return platform_metrics.get_screen_dimensions()
        raise ValueError(f"Dimensions.get expects 'window' or 'screen', not {which!r}")

    @staticmethod
    def add_listener(callback: Callable[[DimensionsEvent], None]) -> Callable[[], None]:
        """Subscribe to size changes; returns an unsubscribe function.

        The callback receives a
        [`DimensionsEvent`][pythonnative.native_modules.dimensions.DimensionsEvent]
        only when the window or screen size (or density) actually changed,
        not for keyboard or safe-area updates.
        """
        last = DimensionsEvent(platform_metrics.get_window_dimensions(), platform_metrics.get_screen_dimensions())

        def _changed() -> None:
            nonlocal last
            current = DimensionsEvent(
                platform_metrics.get_window_dimensions(), platform_metrics.get_screen_dimensions()
            )
            if current == last:
                return
            last = current
            callback(current)

        return platform_metrics.subscribe(_changed)


class PixelRatio:
    """Convert between layout units and physical pixels."""

    @staticmethod
    def get() -> float:
        """Return physical pixels per layout unit (``2.0`` on a 2x display)."""
        return platform_metrics.get_window_dimensions().scale

    @staticmethod
    def get_font_scale() -> float:
        """Return the user's text-size multiplier (``1.0`` at the default size)."""
        return platform_metrics.get_window_dimensions().font_scale

    @staticmethod
    def get_pixel_size_for_layout_size(size: float) -> int:
        """Return the whole number of physical pixels ``size`` layout units cover."""
        return int(round(float(size) * PixelRatio.get()))

    @staticmethod
    def round_to_nearest_pixel(size: float) -> float:
        """Round ``size`` (layout units) so it lands on a physical pixel boundary."""
        ratio = PixelRatio.get()
        return round(float(size) * ratio) / ratio
