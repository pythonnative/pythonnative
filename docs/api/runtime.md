# Async runtime

PythonNative runs a single framework-wide ``asyncio`` event loop **on
the platform's main thread**, pumped as a guest of the native run loop
(``dispatch_async`` on iOS, ``Handler.post`` on Android, the Tk poll
loop in ``pn preview``). Every awaitable surface in the framework
schedules its work on this loop: ``async def`` components,
coroutine [`use_effect`][pythonnative.use_effect] callbacks,
[`use_resource`][pythonnative.use_resource],
[`use_query`][pythonnative.hooks.use_query],
[`use_mutation`][pythonnative.hooks.use_mutation],
[`fetch`][pythonnative.net.fetch],
[`AsyncStorage`][pythonnative.storage.AsyncStorage], the awaitable native
modules ([`Camera`][pythonnative.native_modules.camera.Camera] /
[`Location`][pythonnative.native_modules.location.Location] /
[`Notifications`][pythonnative.native_modules.notifications.Notifications]),
and [`Animated`][pythonnative.animated.Animated] composites.

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

    return pn.Button("Export", on_press=lambda: pn.run_async(export()))
```

## Next steps

- Walk through the async surface end-to-end:
  [Async + data guide](../guides/async.md).
