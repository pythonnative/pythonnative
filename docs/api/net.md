# Network

A small, dependency-free async HTTP client and WebSocket client. Use
[`fetch`][pythonnative.fetch] for the common "call a JSON API" path, including
multipart uploads and streamed responses, and
[`WebSocket`][pythonnative.WebSocket] for a live connection. Reach for
`httpx` or `aiohttp` if you need HTTP/2. See the
[Networking guide](../guides/networking.md).

::: pythonnative.net
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

[](){#pythonnative.websocket}

## WebSocket

::: pythonnative.websocket
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Patterns

- **Inside a component**: pair with
  [`use_query`][pythonnative.use_query] for loading/error state and
  automatic cancellation on unmount.
- **In an event handler**: wrap an `async def` in
  [`pn.run_async`][pythonnative.run_async] so a sync `on_press` can
  drive an awaitable request.
- **Mutations**: pair with [`use_mutation`][pythonnative.use_mutation]
  to track ``loading`` / ``error`` for POST/PUT/DELETE flows.
