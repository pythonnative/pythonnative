# Generated native contracts

Declare an extension's interface in Python, generate its native adapters, and
implement the platform behavior in Swift and Kotlin. The complete working
example is `examples/inbox`: its badge uses generated props, and its module
has synchronous and asynchronous methods.

## Define the interface

```python
from dataclasses import dataclass
from typing import Annotated, Protocol

from pythonnative.sdk import element_factory, register_component
from pythonnative.sdk.schema import ModuleSchema, NativeField, register_schema


@dataclass(frozen=True)
class BadgeProps:
    count: Annotated[int, NativeField(invalidates_layout=True)] = 0


class ToolsProtocol(Protocol):
    def format_count(self, count: int) -> str: ...

    async def ready(self) -> str: ...


register_component(name="Badge", props=BadgeProps)
register_schema(ModuleSchema.from_protocol("Tools", ToolsProtocol))
Badge = element_factory("Badge")
```

From an environment where that module is importable, run:

```sh
pn codegen --module my_package.contracts --output generated
```

Generation produces the schema, Swift and Kotlin props and module adapters,
Python facades, browser metadata, and Markdown reference material. Generated
contracts are deterministic. Built-in generated files are checked against the
Python definitions in the test suite.

A component field can describe layout invalidation, recreation, animation
support, and supported platforms with `NativeField`. A recreation field changes
the native widget while preserving its owning component's Python state. Typed
props reject invalid values before native mutation. Treat the generated schema
as an interface, and keep it in source control.

## Package the native implementation

Set `contracts` in the plugin's `pn_plugin.json` to its schema file:

```json
{
  "contracts": "schema.json",
  "ios": {
    "entry": "BadgePlugin",
    "resources": ["ios/resources/**"]
  },
  "android": {
    "entry": "com.example.badge.BadgePlugin",
    "resources": ["android/res/**", "android/assets/**"]
  }
}
```

The schema should contain the extension's own components and modules. The inbox
example's `generate_contracts.py` demonstrates extracting those definitions.
Builders merge plugin contracts with the built-ins, regenerate native bindings,
and bundle the matching schema into embedded Python. Startup rejects a client
whose protocol, Yoga version, or schema fingerprint doesn't match.

Swift implementations use the generated service protocol and module adapter;
Kotlin implementations use the generated service interface and adapter.
Register those adapters and component managers through the plugin registry.
Use the generated props type in each widget manager instead of repeating prop
names and defaults by hand. The generated adapter handles argument decoding,
method dispatch, and result delivery.

For a hand-written asynchronous module, register a cancellation callback with
Swift `PNPromise.onCancel` or Kotlin `Promise.onCancel`. Python task cancellation
notifies the native promise; the implementation releases any underlying request
or subscription. Late results are ignored after cancellation.

Plugin sources and resources must stay inside the plugin directory. Android
resources preserve their `res` or `assets` layout. iOS resources become SwiftPM
processed resources. Removing a plugin removes its staged sources and resources
on the next preparation. Target wheel discovery reads archives without importing
mobile binary extensions into the desktop build process.

Rebuild after changing a contract or native implementation. Fast Refresh applies
to Python application behavior; it can't change a compiled native interface.
