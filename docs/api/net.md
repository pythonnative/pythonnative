# Network

A small, dependency-free async HTTP client. Use [`fetch`][pythonnative.fetch]
for the common "call a JSON API" path; reach for `httpx` / `aiohttp`
if you need multipart, streaming, or HTTP/2.

::: pythonnative.net
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
  [`pn.run_async`][pythonnative.run_async] so a sync `on_click` can
  drive an awaitable request.
- **Mutations**: pair with [`use_mutation`][pythonnative.use_mutation]
  to track ``loading`` / ``error`` for POST/PUT/DELETE flows.
