# Generated native contracts

Python declarations define the native interface. The same compiler generates
Swift and Kotlin props, records, event emitters, and service adapters for
built-ins and extensions. The separately packaged `examples/inbox-extension`
contains a complete implementation; `examples/inbox` consumes its wheel.

## Declare Python values

Use ordinary dataclasses, enums, `TypedDict`, `Literal`, optional values, and
nested collections. Record defaults survive decoding, and results and events
arrive as the original Python record classes. Unsupported annotations fail
during declaration. Explicit `Any` means a portable JSON value, not an arbitrary
Python object.

```python
from dataclasses import dataclass
from typing import Annotated, Callable, Protocol

from pythonnative.sdk import element_factory, register_component
from pythonnative.sdk.schema import ModuleSchema, NativeField, register_schema


@dataclass(frozen=True)
class Record:
    identifier: str
    title: str
    labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class BadgeProps:
    count: Annotated[int, NativeField(invalidates_layout=True)] = 0
    on_press: Callable[[int], None] | None = None


class ToolsProtocol(Protocol):
    async def prepare(self, records: list[Record], *, limit: int = 10) -> list[Record]: ...


register_component(name="Badge", props=BadgeProps)
register_schema(ModuleSchema.from_protocol("Tools", ToolsProtocol, events={"prepared": list[Record]}))
Badge = element_factory("Badge")
```

Generate from an importable declaration module:

```sh
pn codegen --module my_package.contracts --output generated
```

Generation writes the schema, `NativeValues`, `NativeProps`, `NativeModules`,
Python facades, browser metadata, and a property reference. Generated Python
methods preserve defaults and keyword arguments. Generated `on_prepared`
subscriptions accept typed callbacks and return an unsubscribe function.

Native mappings require string keys. Integers must fit JavaScript's exact
integer range, numbers must be finite, and booleans don't count as numbers.
Record field names must be Python identifiers; use a mapping for other JSON
keys. Records reject missing required fields and unknown fields. Recursive type
cycles aren't supported. Values marked `NativeField(python_only=True)` remain
in Python; other unserializable values raise an error.

Custom components accept `style=` through `element_factory`, even when the
props dataclass doesn't declare a style field. Shared style fields are included
in the generated native contract. Declare `platforms=("ios",)` on
`register_component` or `native_component` for an iOS-only renderer; custom
components default to iOS and Android support. A browser placeholder doesn't
make `Platform.supports` return true.

## Implement the native side

Use `PNTypedComponentManager<BadgeProps>` on iOS and
`TypedComponentManager<BadgeProps>` on Android. The `applyTyped` method receives
checked props. `has_count` distinguishes a changed property from one absent in
a partial update. Common view props live in `PNViewProps`; they aren't repeated
in every generated component. Use `PNComponentEvents.Badge.on_press` to emit
the declared payload.

For iOS controls, attach `PNActionTarget` in `createView` after calling
`super.createView`. The view's state then retains the target for its lifetime.
`makeView` runs before that state exists.

Nullable record fields encode explicit null. A nonrequired nullable `TypedDict`
field uses `PNPresence<T?>` in Swift and Kotlin so absence stays distinct from
a present null; use `.present(nil)` in Swift or `PNPresence.Present(null)` in
Kotlin for the latter.

Implement `ToolsImplementation`, then register a `ToolsModuleAdapter` in the
plugin. Swift's asynchronous implementation receives a completion callback;
Kotlin receives a `Result` callback. Both return an optional cancellation
function. The generated adapter registers it with the native promise. Cancelling
the Python task releases the native work, removes its waiter, and discards late
settlements. Emit module events through the generated `ToolsEvents` helper.

The Inbox extension demonstrates nested records, tuple defaults, a cancellable
delayed operation, typed module and component events, packaged resources,
and a real SwiftPM and Maven dependency. Its generation script filters the
manifest to its own components and services. Build discovery merges those
contracts with the built-ins without importing target binaries on the host.

## Package sources, resources, and dependencies

Include `pn_plugin.json` and its referenced files in the wheel:

```json
{
  "name": "BadgeExtension",
  "contracts": "schema.json",
  "ios": {
    "entry": "BadgePlugin",
    "resources": ["ios/resources/*.json"],
    "dependencies": [
      {
        "url": "https://github.com/apple/swift-collections.git",
        "version": "1.1.4",
        "products": ["DequeModule"]
      }
    ]
  },
  "android": {
    "entry": "com.example.badge.BadgePlugin",
    "resources": ["android/res/**/*.xml"],
    "assets": ["android/assets/*.json"],
    "dependencies": ["androidx.collection:collection-ktx:1.4.5"]
  }
}
```

Swift dependencies require HTTPS URLs, exact versions, and product names.
Maven coordinates require an exact version; ranges, dynamic versions, and
snapshots are rejected. Conflicting declarations fail preparation. These pins
cover direct native dependencies; Python's `pn.lock` records Python wheels.

Android resources retain their `res` structure. Assets are namespaced by plugin
name, such as `InboxExtension/inbox_labels.json`. Resource paths must stay
inside the plugin.

Swift plugin resources retain their manifest-relative paths inside
`Bundle.module`, under `PluginResources/<plugin name>/`. This keeps two plugins
with the same resource filename separate. For example, the Inbox extension
loads `PluginResources/InboxExtension/ios/resources/inbox_labels.json`.
Android assets similarly live under the plugin name in the app assets.
Removing a plugin removes its staged files and dependency declarations.
Resolved wheel hashes invalidate cached metadata even when the wheel's filename
hasn't changed.

## Missing values, nulls, and resets

Protocol 3 separates setting a value from removing a property:

```python
import pythonnative as pn

# Explicit null is a value when the declared type permits it.
nullable = pn.Element("Picker", {"value": None})

# Omission or UNSET removes a previously supplied property.
reset = pn.Element("Text", {"text": "Default size", "font_size": pn.UNSET})
```

Generated component facades use `UNSET` for omitted arguments. Built-in
convenience factories continue to omit optional keyword arguments whose value
is `None`; their omission still produces an explicit removal in the next
transaction. Native state retains the distinction between a null and a missing
property. Physical setters restore a declared default or the platform default.
A reset doesn't recreate the logical tag. Only fields marked `recreate`, such
as `TextInput.multiline` and `ProgressBar.indeterminate`, replace the physical
widget, retaining logical ownership and supported focus/selection state.

`NativeField` also declares layout invalidation, animation, and platform support.
`Platform.supports("Image", "source")` or
`Platform.supports("Notifications", "get_device_token")` inspects the compiled
contract. This checks declared support; a permission grant or attached piece of
hardware is a separate runtime condition. Android remote push needs a provider
extension and reports an unsupported operation instead of a successful empty
token.

`Permissions.check()` is now a coroutine, matching asynchronous platform
settings APIs: use `await pn.Permissions.check("camera")`. Android camera
editing (`allow_editing=True`) raises an unsupported-operation error; use
a provider plugin if your application needs an Android image editor.

Protocol 2 clients aren't supported. Rebuild the app after changing declarations,
native sources, or native dependencies. Startup checks the exact contract
fingerprint and Yoga version before mounting. Fast Refresh handles Python
application changes within that compiled interface.

## Verify contracts

```sh
uv run python scripts/generate-native-contracts.py
uv run pytest tests/test_codegen.py tests/test_native_values.py
uv run python scripts/run-browser-tests.py
```

Native tests exercise generated adapters alongside actual UIKit and Android
controls. The Inbox Maestro flows build the extension wheel, drive native
navigation and input, verify native cancellation without a late event, save
data, restart the process, and verify persistence.
