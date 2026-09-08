# Async runtime

PythonNative starts one standard `asyncio` event loop on a dedicated application
thread. Component rendering, effects, event handlers, and async tasks run on
that thread. UIKit and Android retain their own UI threads; native bridge calls
marshal view operations there and queue events back to Python.

Ordinary asyncio networking, `TaskGroup`, timeouts, synchronization primitives,
and third-party async libraries run on this loop. A synchronous
Python callback can still delay other Python work, so use `asyncio.to_thread`
for blocking I/O and cooperative async work for long operations.

Component effects and async event handlers have component lifetimes. Unmounting
cancels their tasks. Use `runtime.run_application_task()` when work must survive
the initiating component, and `TaskScope` for explicitly owned services.
Native promises can register cancellation handlers; late results are ignored.

Headless tests can use `run_blocking()` and `drain()`. Don't call `run_blocking()`
from the running application loop; await the operation instead.

::: pythonnative.runtime
