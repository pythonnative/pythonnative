# Query cache

[`use_query`][pythonnative.use_query] reads and writes a shared cache owned by a
`QueryClient`. Most apps never touch it: without a `client` argument, every query
uses the application's default client. Create your own when you want separate
limits, an isolated cache for one feature or test, or direct control over
invalidation and optimistic updates.

A client holds one entry per hashable key. Each entry has an immutable
`QuerySnapshot` that every subscriber to that key shares, so components that ask
for the same key share one request and one result. Cached results are fresh for
`stale_time` seconds. After that, the next subscriber triggers a refetch.

::: pythonnative.query.QueryClient
    options:
      show_root_toc_entry: true
      members:
        - snapshot
        - subscribe
        - invalidate
        - set_data
        - close
      members_order: source
      filters: ["!^_"]

::: pythonnative.query.QuerySnapshot
    options:
      show_root_toc_entry: true
      members_order: source
      filters: ["!^_"]

## Example

Create one client and keep it for as long as the data should stay cached. A module
level client works well. Don't create a new client on every render, because each
one starts with an empty cache and drops everything the previous render fetched.

```python
import pythonnative as pn
from pythonnative.query import QueryClient

client = QueryClient(capacity=64, stale_time=60)  # stale_time is in seconds


@pn.component
def UserCard(user_id: int) -> pn.Node:
    key = ("user", user_id)
    q = pn.use_query(
        lambda: api.get_user(user_id),
        [user_id],
        key=key,
        client=client,
    )

    if q.loading and q.data is None:
        return pn.Text("Loading…")
    if q.error:
        return pn.Text(f"Error: {q.error}")
    return pn.Column(
        pn.Text(q.data["name"]),
        pn.Button("Refresh", on_press=lambda: client.invalidate(key)),
    )
```

The key must include every input that identifies the result. Here `user_id` is in
the key, so each user gets its own cache entry. Calling `client.invalidate()`
with no argument invalidates every query in the client.

## Patterns

- **Refresh after a write**: call
  [`invalidate`][pythonnative.query.QueryClient.invalidate] once a mutation
  succeeds. Entries with active subscribers refetch right away. Others refetch the
  next time something subscribes.
- **Optimistic updates**: call
  [`set_data`][pythonnative.query.QueryClient.set_data] to publish a value
  immediately. It supersedes any request still in flight for that key and marks
  the value fresh for `stale_time`.
- **Bounded memory**: `capacity` limits how many entries the client keeps.
  When it's exceeded, the client drops the least recently used entries that have
  no subscribers and no request in flight.
- **Cleanup**: whoever creates a client owns it. Call
  [`close`][pythonnative.query.QueryClient.close] when you're finished with it to
  cancel shared tasks and release cached data.

## Next steps

- The hook is covered in the [Async + data guide](../guides/async.md) and listed
  under [async hooks](hooks.md#async-hooks).
- Run the tasks behind a query on the [async runtime](runtime.md).
