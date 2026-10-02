# Store

A [`Store`][pythonnative.Store] holds one immutable application value
outside the component tree. Actions replace the value with
`store.set(...)` or `store.update(...)`, and components read it with
[`use_store`][pythonnative.use_store], re-rendering only when the
selected slice changes.

```python
from dataclasses import dataclass, replace

import pythonnative as pn


@dataclass(frozen=True)
class Session:
    user: str | None = None
    unread: int = 0


session = pn.Store(Session())


def sign_in(user: str) -> None:
    session.update(lambda state: replace(state, user=user))


@pn.component
def UnreadBadge() -> pn.Node:
    unread = pn.use_store(session, lambda state: state.unread)
    return pn.Text(str(unread)) if unread else None
```

::: pythonnative.store
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- Choose between hooks, context, stores, and persistence in
  [Managing state](../guides/state.md).
- Persist values across launches with
  [`use_persisted_state`][pythonnative.use_persisted_state]; see
  [Storage](storage.md).
