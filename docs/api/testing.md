# Testing

`pythonnative.testing` renders components without a device or
simulator. [`render`][pythonnative.testing.render] mounts an element
into an in-memory [`FakeBackend`][pythonnative.testing.FakeBackend]
and returns a [`RenderResult`][pythonnative.testing.RenderResult] with
Testing Library-style queries and event helpers;
[`render_hook`][pythonnative.testing.render_hook] does the same for a
bare hook. [`within`][pythonnative.testing.within] scopes the queries
to one subtree, [`wait_for`][pythonnative.testing.wait_for] polls a
predicate while draining the framework loop, and
[`fake_clock`][pythonnative.testing.fake_clock] puts `asyncio` timers
on virtual time.

::: pythonnative.testing
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Queries

Every query comes in four flavors: `get_by_*` (exactly one match or
`LookupError`), `query_by_*` (the match or `None`), `get_all_by_*`
(every match), and `find_by_*` (`get_by_*` wrapped in `wait_for`).
`RenderResult` and the scope returned by `within` share this class.

::: pythonnative.testing.queries.Queries
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## pytest plugin

Installing `pythonnative` registers this plugin under the `pytest11`
entry point, so every pytest session gets the runtime-reset fixture and
`pn_clock` without a `conftest.py`. Disable it with
`-p no:pythonnative`.

::: pythonnative.testing.pytest_plugin
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- Read the [Testing guide](../guides/testing.md) for patterns.
- Test navigation flows against a
  [`FakeHost`][pythonnative.testing.FakeHost].
