"""Declare the Python side of a native plugin.

A plugin's facade calls these at import. The same declarations serve three
places:

- On a device with the plugin in the build, the contract is already compiled
  in, so nothing is evaluated at startup.
- On a device without the plugin, calling a method or rendering a component
  raises an error naming the ``[plugins].use`` entry to add.
- Off device (tests, the browser preview), the declaration registers the
  contract and the Python ``fallback``, so the same code keeps running.

``scripts/generate-native-contracts.py`` imports a first-party facade to write
its ``native/schema.json``; third-party plugins do the same with their own
script (see ``examples/inbox-extension/generate_contracts.py``).
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional, Sequence

from ..element import Element
from ..native_modules.registry import declare_plugin_module, register_python_module
from . import schema
from ._components import define_component

__all__ = ["PluginNotEnabledError", "plugin_component", "plugin_module"]


class PluginNotEnabledError(RuntimeError):
    """A component's plugin isn't compiled into this build."""


def plugin_module(
    name: str,
    protocol: type,
    *,
    plugin: str,
    events: Optional[Mapping[str, Any]] = None,
    fallback: Any = None,
    platforms: Optional[Mapping[str, Sequence[str]]] = None,
    browser: bool = False,
) -> None:
    """Declare native module ``name``, implemented by ``plugin``.

    Args:
        name: The module name native code registers.
        protocol: A class whose annotated methods are the contract.
        plugin: The plugin's name, for the error when it isn't in the build.
        events: Event names and their payload types.
        fallback: The off-device implementation: a class or an instance.
        platforms: Methods limited to some platforms, for example
            ``{"get_device_token": ["ios"]}``. Calling one elsewhere raises
            ``NativeModuleError`` with the code ``unsupported``.
        browser: The plugin's ``web`` entry implements this module in the
            preview page, so calls go there instead of to ``fallback``.
    """
    declare_plugin_module(name, plugin, browser=browser)
    if name not in schema.MODULES:
        contract = schema.ModuleSchema.from_protocol(name, protocol, events=events)
        for method, names in (platforms or {}).items():
            contract.methods[method]["platforms"] = list(names)
        schema.register_schema(contract)
    if fallback is not None:
        register_python_module(name, fallback)


def plugin_component(
    name: str,
    props: type,
    *,
    plugin: str,
    measurement: str = "container",
    platforms: Sequence[str] = ("ios", "android", "web"),
) -> Callable[..., Element]:
    """Declare native component ``name``, implemented by ``plugin``, and return its factory.

    Args:
        name: The element type native code registers a manager for.
        props: The dataclass of its props.
        plugin: The plugin's name, for the error when it isn't in the build.
        measurement: How the renderer core sizes it; see
            [`define_component`][pythonnative.sdk.define_component].
        platforms: Where a manager exists.

    Returns:
        The element factory. On a device whose build doesn't include
        ``plugin``, calling it raises
        [`PluginNotEnabledError`][pythonnative.sdk.plugin.PluginNotEnabledError].
    """
    factory = define_component(name, props, measurement=measurement, platforms=tuple(platforms))

    def checked(*children: Any, **kwargs: Any) -> Element:
        if not schema.in_build(component=name):
            raise PluginNotEnabledError(
                f"{name} is part of the {plugin!r} capability, which isn't in this build. "
                f"Add {plugin!r} to [plugins].use in pythonnative.toml and rebuild."
            )
        return factory(*children, **kwargs)

    checked.__name__ = name
    checked.__qualname__ = name
    checked.__doc__ = props.__doc__
    checked.__signature__ = getattr(factory, "__signature__", None)  # type: ignore[attr-defined]
    return checked
