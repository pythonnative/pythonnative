"""Hooks that connect components to the motion runtime (RFC 0009)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeVar

from ..hooks import _require_hook_state, use_effect, use_ref
from ..style import AnimatedStyle, Style
from .runtime import runtime
from .shared import SharedValue
from .worklets import require_worklet

__all__ = [
    "AnimatedStyle",
    "FrameInfo",
    "use_animated_reaction",
    "use_animated_style",
    "use_derived_value",
    "use_frame_callback",
    "use_shared_value",
]

T = TypeVar("T")


@dataclass(frozen=True)
class FrameInfo:
    """What a [`use_frame_callback`][pythonnative.use_frame_callback] worklet receives each frame.

    Attributes:
        timestamp_ms: The display frame's time, in milliseconds.
        delta_ms: Milliseconds since the previous frame.
    """

    timestamp_ms: float
    delta_ms: float


def _backend(hook: str) -> Any:
    state = _require_hook_state(hook)
    return getattr(state.owner, "backend", None)


def use_shared_value(initial: T) -> SharedValue[T]:
    """A [`SharedValue`][pythonnative.SharedValue] that lives as long as the component.

    Its identity is stable across renders, like ``use_ref``; the core
    releases it when the component unmounts.

    Example:
        ```python
        offset = pn.use_shared_value(0.0)
        ```
    """
    backend = _backend("use_shared_value")
    ref = use_ref(None)
    if ref.current is None:
        ref.current = SharedValue(initial)
    shared: SharedValue[T] = ref.current
    runtime.adopt(shared, backend)

    def mount() -> Callable[[], None]:
        return lambda: runtime.release_shared(shared)

    use_effect(mount, [])  # pn: ignore[PN103] releases on unmount; the ref and backend are stable
    return shared


def _seed(fn: Callable[[], Any]) -> Any:
    """Run a worklet once as Python, so Python reads a sensible value before the UI thread reports."""
    try:
        return fn()
    except Exception:
        return None


def use_derived_value(worklet: Callable[[], T]) -> SharedValue[T]:
    """A read-only shared value the UI thread recomputes whenever a shared value it reads changes.

    Example:
        ```python
        progress = pn.use_derived_value(lambda: offset.value / width)
        ```
    """
    fn = require_worklet(worklet, "use_derived_value")
    backend = _backend("use_derived_value")
    ref = use_ref(None)
    if ref.current is None:
        ref.current = (SharedValue(_seed(fn), readonly=True), runtime.new_binding())
    shared, binding = ref.current
    runtime.adopt(shared, backend)
    runtime.bind(backend, binding, "derived", fn, output=shared)

    def mount() -> Callable[[], None]:
        def release() -> None:
            runtime.release_binding(backend, binding)
            runtime.release_shared(shared)

        return release

    use_effect(mount, [])  # pn: ignore[PN103] releases on unmount; the ref and backend are stable
    return shared


def use_animated_style(worklet: Callable[[], Style]) -> AnimatedStyle:
    """A style the UI thread recomputes whenever a shared value it reads changes.

    Put it in any built-in component's ``style`` list, after the static
    styles it overrides. The worklet runs once when the view mounts, before
    its first frame is drawn.

    Example:
        ```python
        moved = pn.use_animated_style(lambda: {"transform": [{"translate_x": offset.value}]})
        return pn.View(child, style=[styles.card, moved])
        ```
    """
    fn = require_worklet(worklet, "use_animated_style")
    backend = _backend("use_animated_style")
    ref = use_ref(None)
    if ref.current is None:
        ref.current = AnimatedStyle(runtime.new_binding())
    style: AnimatedStyle = ref.current
    runtime.bind(backend, style.binding, "style", fn)

    def mount() -> Callable[[], None]:
        return lambda: runtime.release_binding(backend, style.binding)

    use_effect(mount, [])  # pn: ignore[PN103] releases on unmount; the ref and backend are stable
    return style


def use_animated_reaction(prepare: Callable[[], T], react: Callable[[T, Optional[T]], None]) -> None:
    """Run ``react(current, previous)`` on the UI thread whenever ``prepare()``'s result changes.

    ``prepare`` tracks the shared values it reads. ``react`` typically
    writes another shared value or calls back with ``run_on_python``.

    Example:
        ```python
        pn.use_animated_reaction(
            lambda: offset.value > threshold,
            lambda past, _: pn.run_on_python(set_past, past),
        )
        ```
    """
    prepare_fn = require_worklet(prepare, "use_animated_reaction")
    react_fn = require_worklet(react, "use_animated_reaction")
    backend = _backend("use_animated_reaction")
    ref = use_ref(None)
    if ref.current is None:
        ref.current = runtime.new_binding()
    binding: int = ref.current
    runtime.bind(backend, binding, "reaction", prepare_fn, react=react_fn)

    def mount() -> Callable[[], None]:
        return lambda: runtime.release_binding(backend, binding)

    use_effect(mount, [])  # pn: ignore[PN103] releases on unmount; the ref and backend are stable


def use_frame_callback(worklet: Callable[[FrameInfo], None], *, active: bool = True) -> None:
    """Run a worklet on the UI thread every display frame while ``active``.

    Example:
        ```python
        def spin(frame: pn.FrameInfo) -> None:
            angle.value = (angle.value + frame.delta_ms * 0.18) % 360

        pn.use_frame_callback(pn.worklet(spin), active=playing)
        ```
    """
    fn = require_worklet(worklet, "use_frame_callback")
    backend = _backend("use_frame_callback")
    ref = use_ref(None)
    if ref.current is None:
        ref.current = runtime.new_binding()
    binding: int = ref.current
    runtime.bind(backend, binding, "frame", fn, active=active)

    def mount() -> Callable[[], None]:
        return lambda: runtime.release_binding(backend, binding)

    use_effect(mount, [])  # pn: ignore[PN103] releases on unmount; the ref and backend are stable
