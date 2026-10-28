# Bridge

The Python half of the [native bridge](../concepts/bridge.md): the
`ctypes` binding to the renderer core, JSON codec, per-platform
transports, protocol handshake, and the single callback the core and the
platform use to reach Python. App code never calls this module directly;
the
[`BridgeBackend`][pythonnative.native_views.bridge_backend.BridgeBackend],
[`BridgeModule`][pythonnative.native_modules.registry.BridgeModule], and
[`NativeScreenHost`][pythonnative.hosts.native.NativeScreenHost] do.

::: pythonnative.bridge
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Renderer core

The C ABI of the renderer core (`native/core/include/pn_core.h`), bound
with `ctypes`, plus Python decoders for its binary mount transactions and
animated writes. On iOS the symbols come from the app binary, on Android
from `libpncore.so` (named by `PN_CORE_LIBRARY`), and on the development
machine from the `pythonnative._core` extension.

::: pythonnative.bridge.core
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Codec

::: pythonnative.bridge.codec
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Fake transport (tests)

The host core with Python playing the platform's UI thread. See
[Testing what the platform mounts](../guides/testing.md#testing-what-the-platform-mounts).

::: pythonnative.bridge.fake
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Bootstrap

::: pythonnative.bootstrap
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- Wire format and native contracts: [The native bridge](../concepts/bridge.md).
- Bundling native plugins: [Configuration](../guides/configuration.md#plugins).
