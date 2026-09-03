# Bridge

The Python half of the [native bridge](../concepts/bridge.md): JSON
codec, per-platform transports, protocol handshake, main-queue posting,
and the single callback native uses to reach Python. App code never
calls this module directly; the
[`BridgeBackend`][pythonnative.native_views.bridge_backend.BridgeBackend],
[`BridgeModule`][pythonnative.native_modules.registry.BridgeModule], and
[`NativeScreenHost`][pythonnative.hosts.native.NativeScreenHost] do.

::: pythonnative.bridge
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
