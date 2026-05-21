# Async runtime

PythonNative runs a single framework-wide ``asyncio`` event loop on a
dedicated daemon thread. Every awaitable surface in the framework —
[`use_async_effect`][pythonnative.hooks.use_async_effect],
[`use_query`][pythonnative.hooks.use_query],
[`use_mutation`][pythonnative.hooks.use_mutation],
[`fetch`][pythonnative.net.fetch],
[`AsyncStorage`][pythonnative.storage.AsyncStorage], the awaitable native
modules ([`Camera`][pythonnative.native_modules.camera.Camera] /
[`Location`][pythonnative.native_modules.location.Location] /
[`Notifications`][pythonnative.native_modules.notifications.Notifications]),
and [`Animated`][pythonnative.animated.Animated] composites — schedules
its work on this loop.

::: pythonnative.runtime
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Pattern: bridge a sync handler into async code

```python
import pythonnative as pn


@pn.component
def Toolbar():
    async def export():
        report = await build_report()
        await save_to_disk(report)

    return pn.Button("Export", on_click=lambda: pn.run_async(export()))
```

## Next steps

- Walk through the async surface end-to-end:
  [Async + data guide](../guides/async.md).
