"""Asyncio runtime: one event loop, hosted on the platform main thread.

PythonNative is **async-first**: the whole framework (rendering,
effects, native modules, animations, timers) shares a single
``asyncio`` event loop that lives on the platform's main thread. There
is no background runtime thread; coroutines interleave with rendering
on the same thread, so async code can touch component state and (via
the commit) native views without any cross-thread marshaling.

Because UIKit and the Android view system own the main thread's run
loop, the framework loop cannot call ``run_forever`` and block.
Instead it runs as a **guest**: whenever work is scheduled
(``call_soon`` / ``call_soon_threadsafe`` / timers), the runtime asks
the platform to *pump* the loop on the next main-queue turn
(``dispatch_async`` on iOS, ``Handler.post`` on Android, the Tk poll
loop in ``pn preview``). One pump runs every ready callback and due
timer, then returns control to the platform.

Key entry points:

- [`get_loop`][pythonnative.runtime.get_loop]: the framework loop. If
  a loop is already running on the calling thread (an ``async`` test,
  ``asyncio.run``), that loop is adopted instead.
- [`run_async`][pythonnative.runtime.run_async]: schedule a coroutine
  from synchronous code (an event handler, an effect). Returns an
  ``asyncio.Task`` when called on the loop's thread, or a
  ``concurrent.futures.Future`` when called from another thread.
- [`run_blocking`][pythonnative.runtime.run_blocking] /
  [`drain`][pythonnative.runtime.drain]: drive the guest loop from
  synchronous code. Used by tests and plain scripts, where no platform
  pump exists.

Example:
    ```python
    import pythonnative as pn


    @pn.component
    def SaveButton():
        async def save():
            await pn.AsyncStorage.set_item("draft", "…")

        return pn.Button("Save", on_press=lambda: pn.run_async(save()))
    ```
"""

from __future__ import annotations

import asyncio
import ctypes
import ctypes.util
import inspect
import threading
import time as _time
from typing import Any, Awaitable, Callable, Coroutine, Dict, Optional, TypeVar, Union

T = TypeVar("T")


# ======================================================================
# The guest loop
# ======================================================================


class _GuestLoop(asyncio.SelectorEventLoop):
    """A selector event loop that asks the platform to pump it.

    Overrides every scheduling entry point so that queuing work also
    requests a pump on the platform main queue. The pump itself
    (:func:`_pump`) runs one ``run_forever`` iteration bounded by an
    immediate ``stop``, which executes all ready callbacks and due
    timers, then reschedules itself while work remains.
    """

    def __init__(self) -> None:
        super().__init__()
        self._pn_owner_thread = threading.current_thread()
        self._pn_pumping = False
        self._pn_pump_queued = False
        self._pn_timer: Optional[threading.Timer] = None
        self._pn_timer_when: float = float("inf")
        self._pn_lock = threading.Lock()

    # -- scheduling overrides ------------------------------------------
    #
    # ``type: ignore[override]``: the typeshed stubs type these with a
    # ``TypeVarTuple`` linking ``callback`` to ``*args``; the plain
    # ``Callable[..., Any]`` form used here accepts the same calls.

    def call_soon(self, callback: Callable[..., Any], *args: Any, context: Any = None) -> Any:  # type: ignore[override]
        handle = super().call_soon(callback, *args, context=context)
        self._pn_request_pump(0.0)
        return handle

    def call_soon_threadsafe(  # type: ignore[override]
        self, callback: Callable[..., Any], *args: Any, context: Any = None
    ) -> Any:
        handle = super().call_soon_threadsafe(callback, *args, context=context)
        self._pn_request_pump(0.0)
        return handle

    def call_at(  # type: ignore[override]
        self, when: float, callback: Callable[..., Any], *args: Any, context: Any = None
    ) -> Any:
        handle = super().call_at(when, callback, *args, context=context)
        self._pn_request_pump(max(0.0, when - self.time()))
        return handle

    # -- pumping --------------------------------------------------------

    def _pn_request_pump(self, delay: float) -> None:
        """Ask the platform to pump this loop after ``delay`` seconds.

        No-op while a pump is executing (the post-pump check
        reschedules if work remains) and when no platform dispatcher
        exists (headless tests drive the loop with
        [`drain`][pythonnative.runtime.drain] /
        [`run_blocking`][pythonnative.runtime.run_blocking] instead).
        """
        if self._pn_pumping or self.is_running() or self.is_closed():
            return
        if delay <= 0.0:
            with self._pn_lock:
                if self._pn_pump_queued:
                    return
                if not _has_pump_dispatcher():
                    return
                self._pn_pump_queued = True
            _dispatch_to_main_queue(self._pn_pump)
            return
        # Delayed work: keep a single earliest-deadline timer that
        # forwards onto the main queue when it fires.
        now = _time.monotonic()
        when = now + delay
        with self._pn_lock:
            if not _has_pump_dispatcher():
                return
            if self._pn_timer is not None and self._pn_timer_when <= when:
                return
            if self._pn_timer is not None:
                self._pn_timer.cancel()
            timer = threading.Timer(delay, self._pn_timer_fired)
            timer.daemon = True
            self._pn_timer = timer
            self._pn_timer_when = when
        timer.start()

    def _pn_timer_fired(self) -> None:
        with self._pn_lock:
            self._pn_timer = None
            self._pn_timer_when = float("inf")
        self._pn_request_pump(0.0)

    def _pn_pump(self) -> None:
        """Run one loop iteration on the main thread, then reschedule."""
        with self._pn_lock:
            self._pn_pump_queued = False
        if self.is_closed() or self.is_running() or self._pn_pumping:
            return
        if threading.current_thread() is not self._pn_owner_thread:
            # A dispatcher delivered the pump on the wrong thread
            # (shouldn't happen on device); drop it rather than run the
            # loop off its owner thread.
            return
        self._pn_pumping = True
        try:
            super().call_soon(self.stop)
            self.run_forever()
        except Exception as exc:  # pragma: no cover - platform-level guard
            print(f"[pn.runtime] loop pump raised: {exc!r}")
        finally:
            self._pn_pumping = False
        # Reschedule while work remains: immediately for ready
        # callbacks, at the earliest deadline for timers.
        ready = getattr(self, "_ready", None)
        if ready:
            self._pn_request_pump(0.0)
            return
        scheduled = getattr(self, "_scheduled", None)
        if scheduled:
            next_when = scheduled[0].when()
            self._pn_request_pump(max(0.0, next_when - self.time()))


_loop: Optional[_GuestLoop] = None
_loop_lock = threading.Lock()


def get_loop() -> asyncio.AbstractEventLoop:
    """Return the framework event loop.

    If a loop is already running on the calling thread (an ``async``
    test, or app code inside ``asyncio.run``), that loop is adopted so
    every framework awaitable lives on the caller's loop. Otherwise
    the shared guest loop is returned, created on first use and owned
    by the creating thread (the platform main thread on device).

    Returns:
        The :class:`asyncio.AbstractEventLoop` all framework work
        should be scheduled on.
    """
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        pass
    global _loop
    if _loop is not None and not _loop.is_closed():
        return _loop
    with _loop_lock:
        if _loop is None or _loop.is_closed():
            _loop = _GuestLoop()
        return _loop


def _on_loop_thread(loop: asyncio.AbstractEventLoop) -> bool:
    """Whether the current thread may schedule non-threadsafe work on ``loop``."""
    owner = getattr(loop, "_pn_owner_thread", None)
    if owner is not None:
        return threading.current_thread() is owner
    try:
        return asyncio.get_running_loop() is loop
    except RuntimeError:
        return False


def _shutdown_for_tests() -> None:
    """Close the guest loop and reset module state (test isolation).

    Cancels every pending task, lets cancellations propagate, and
    closes the loop so the next [`get_loop`][pythonnative.runtime.get_loop]
    starts fresh. Production code never calls this; the loop lives for
    the process.
    """
    global _loop
    with _loop_lock:
        loop = _loop
        _loop = None
    if loop is None or loop.is_closed():
        return
    timer = loop._pn_timer
    if timer is not None:
        timer.cancel()
    if loop.is_running():  # pragma: no cover - misuse guard
        return
    try:
        tasks = [t for t in asyncio.all_tasks(loop) if not t.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        loop.run_until_complete(loop.shutdown_asyncgens())
    except Exception:
        pass
    finally:
        loop.close()


# ======================================================================
# Scheduling helpers
# ======================================================================


Awaitlike = Union[Coroutine[Any, Any, T], Awaitable[T]]


def run_async(awaitable: Awaitlike[T]) -> Any:
    """Schedule ``awaitable`` on the framework loop.

    The standard bridge from synchronous code (event handlers, effect
    setups) into async code. On the loop's own thread this returns an
    :class:`asyncio.Task`; from another thread it returns the
    :class:`concurrent.futures.Future` produced by
    :func:`asyncio.run_coroutine_threadsafe`. Both support
    ``cancel()`` and ``add_done_callback()``.

    Args:
        awaitable: A coroutine object (the typical case) or any
            awaitable.

    Returns:
        A future-like handle for the scheduled work.

    Example:
        ```python
        import pythonnative as pn

        async def work():
            return 42

        task = pn.run_async(work())
        ```
    """
    loop = get_loop()
    if _on_loop_thread(loop):
        return asyncio.ensure_future(awaitable, loop=loop)
    if inspect.iscoroutine(awaitable):
        return asyncio.run_coroutine_threadsafe(awaitable, loop)

    async def _wrap() -> T:
        return await awaitable

    return asyncio.run_coroutine_threadsafe(_wrap(), loop)


def run_blocking(awaitable: Awaitlike[T], timeout: Optional[float] = None) -> T:
    """Run ``awaitable`` to completion on the framework loop, blocking.

    For synchronous scripts and tests. Must not be called while the
    loop is already running (i.e., from inside a coroutine); ``await``
    directly there instead.

    Args:
        awaitable: The coroutine or awaitable to drive.
        timeout: Optional seconds before :class:`TimeoutError`.

    Returns:
        The awaitable's result.
    """
    loop = get_loop()
    if loop.is_running():
        raise RuntimeError("run_blocking() cannot be used while the event loop is running; use `await` instead")

    async def _driver() -> T:
        if timeout is not None:
            try:
                return await asyncio.wait_for(_ensure_coro(awaitable), timeout)
            except asyncio.TimeoutError:
                # On Python 3.10, asyncio.TimeoutError is not the builtin
                # TimeoutError (they were unified in 3.11); normalize so
                # callers can always catch the builtin.
                raise TimeoutError(f"run_blocking() timed out after {timeout}s") from None
        return await _ensure_coro(awaitable)

    return loop.run_until_complete(_driver())


async def _ensure_coro(awaitable: Awaitlike[T]) -> T:
    return await awaitable


def drain(timeout: float = 1.0, *, until: Optional[Callable[[], bool]] = None) -> bool:
    """Pump the framework loop until it goes idle (or ``until`` holds).

    Runs ready callbacks, due timers, and task steps repeatedly. Used
    by synchronous tests to settle async effects, resources, and
    transition flushes deterministically; on-device the platform pump
    makes this unnecessary.

    Args:
        timeout: Maximum seconds to keep pumping.
        until: Optional predicate; draining stops early once it
            returns truthy.

    Returns:
        ``True`` if the loop went idle (or ``until`` matched) before
        the timeout, ``False`` otherwise.
    """
    loop = get_loop()
    if loop.is_running():
        raise RuntimeError("drain() cannot be used while the event loop is running; use `await` instead")
    deadline = _time.monotonic() + timeout
    while _time.monotonic() < deadline:
        loop.run_until_complete(asyncio.sleep(0))
        if until is not None and until():
            return True
        pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
        ready = bool(getattr(loop, "_ready", ()))
        scheduled = bool(getattr(loop, "_scheduled", ()))
        if until is None and not pending and not ready and not scheduled:
            return True
        if pending or scheduled:
            loop.run_until_complete(asyncio.sleep(0.002))
    return False


def call_threadsafe(callback: Callable[..., Any], *args: Any) -> None:
    """Schedule ``callback(*args)`` on the framework loop from any thread.

    Thin wrapper around
    :meth:`asyncio.AbstractEventLoop.call_soon_threadsafe`. Useful from
    native delegates (which may fire on arbitrary OS threads) to hop
    onto the main-thread loop before touching asyncio primitives.
    """
    get_loop().call_soon_threadsafe(callback, *args)


def resolve_future(future: "asyncio.Future[T]", value: T) -> None:
    """Set ``future``'s result from any thread (no-op if already done).

    Convenience used by every native delegate that wraps a callback
    into an awaitable: the delegate doesn't have to know which thread
    it's on, only that it must not race with cancellation.

    Args:
        future: An :class:`asyncio.Future` bound to the framework loop.
        value: The value to deliver as the future's result.
    """
    loop = future.get_loop()
    loop.call_soon_threadsafe(_set_future_result, future, value)


def reject_future(future: "asyncio.Future[Any]", error: BaseException) -> None:
    """Set ``future``'s exception from any thread (no-op if already done)."""
    loop = future.get_loop()
    loop.call_soon_threadsafe(_set_future_exception, future, error)


def _set_future_result(future: "asyncio.Future[Any]", value: Any) -> None:
    if not future.done():
        future.set_result(value)


def _set_future_exception(future: "asyncio.Future[Any]", error: BaseException) -> None:
    if not future.done():
        future.set_exception(error)


def create_future() -> "asyncio.Future[Any]":
    """Create a future bound to the framework loop.

    Safe to call from any thread. Native delegates deliver into it via
    [`resolve_future`][pythonnative.runtime.resolve_future] /
    [`reject_future`][pythonnative.runtime.reject_future].
    """
    return get_loop().create_future()


# ======================================================================
# Main-queue dispatch
# ======================================================================
#
# The guest loop is pumped by enqueueing a callable on the platform's
# main queue. Unlike ``call_on_main_thread`` (which runs inline when
# already on the main thread), pump dispatch is ALWAYS queued: pumping
# inline from arbitrary call sites (say, a ``call_soon`` issued in the
# middle of a reconciler commit) would re-enter the renderer.


# Desktop (Tkinter) main-thread dispatcher, installed by
# ``pythonnative.preview`` while a ``pn preview`` session is live; the
# preview's poll loop drains whatever this dispatcher enqueues.
_desktop_main_dispatch: Optional[Callable[[Callable[[], None]], None]] = None


def set_desktop_main_dispatch(dispatch: Optional[Callable[[Callable[[], None]], None]]) -> None:
    """Install (or clear) the desktop main-thread dispatcher.

    Called by ``pythonnative.preview`` with a function that marshals
    work onto the Tk main thread, and with ``None`` when the preview
    window closes.
    """
    global _desktop_main_dispatch
    _desktop_main_dispatch = dispatch


def _has_pump_dispatcher() -> bool:
    """Whether a queued main-thread dispatcher exists on this platform."""
    from .platform import Platform

    if Platform.is_ios or Platform.is_android:
        return True
    return _desktop_main_dispatch is not None


def _dispatch_to_main_queue(fn: Callable[[], None]) -> None:
    """Enqueue ``fn`` on the platform main queue (never runs inline)."""
    from .platform import Platform

    if Platform.is_ios:
        _ios_dispatch_async(fn)
    elif Platform.is_android:
        _android_post_to_main(fn)
    elif _desktop_main_dispatch is not None:
        _desktop_main_dispatch(fn)
    # Headless: nothing to dispatch to; drain()/run_blocking() pump.


def call_on_main_thread(fn: Callable[[], None]) -> None:
    """Run ``fn()`` on the platform UI thread.

    - **iOS**: dispatches ``fn`` onto the main dispatch queue via
      ``libdispatch.dispatch_async_f`` (called through
      :class:`ctypes.PyDLL` to keep the GIL held), or runs inline when
      already on the main thread.
    - **Android**: posts a ``Runnable`` to
      ``Handler(Looper.getMainLooper())``, or runs inline on the main
      looper thread.
    - **Desktop**: enqueues ``fn`` for the ``pn preview`` poll loop
      (or runs inline if no preview is live).
    - **Tests**: runs ``fn()`` inline.

    Exceptions raised by ``fn`` are caught and printed; they must not
    propagate into UIKit / the Android Looper.

    Args:
        fn: A zero-arg callable. Runs on the main thread when the
            platform's UI runtime is available, otherwise inline.
    """
    from .platform import Platform

    if Platform.is_ios:
        _ios_call_on_main(fn)
    elif Platform.is_android:
        _android_call_on_main(fn)
    elif Platform.is_desktop and _desktop_main_dispatch is not None:
        _desktop_main_dispatch(fn)
    else:
        fn()


# ----------------------------------------------------------------------
# iOS main-queue dispatch (PyDLL-based, no GIL release)
# ----------------------------------------------------------------------
#
# rubicon-objc loads libobjc via ctypes.CDLL, which RELEASES THE GIL
# around every ObjC method call. On the iOS simulator (and to a lesser
# extent on-device), a thread is then parked by the kernel until the
# next wakeup-coalescing tick (~500ms), making cross-thread ObjC calls
# absurdly slow. To avoid this, we call libdispatch's
# ``dispatch_async_f`` directly via ``ctypes.PyDLL`` (which keeps the
# GIL held), and pass a ``CFUNCTYPE`` trampoline as the work function.
# The trampoline runs on the main thread, looks up the pending Python
# callable by an integer key, and invokes it.

_dispatch_lib: Optional[Any] = None
_dispatch_async_f_c: Optional[Any] = None
_dispatch_main_q_ptr: int = 0
_DISPATCH_FN_TYPE = ctypes.CFUNCTYPE(None, ctypes.c_void_p)
_main_pending: Dict[int, Callable[[], None]] = {}
_main_pending_lock = threading.Lock()
_main_next_id: int = 0


def _main_trampoline_py(ctx: int) -> None:
    """Run on the main thread; pop the queued callable and call it."""
    with _main_pending_lock:
        fn = _main_pending.pop(ctx, None)
    if fn is None:
        return
    try:
        fn()
    except Exception as exc:
        print(f"[pn.runtime] main-thread trampoline raised: {exc!r}")


# Keep a strong reference to the C-callable trampoline forever; if it
# gets GC'd while libdispatch holds the function pointer, we crash.
_main_trampoline_c = _DISPATCH_FN_TYPE(_main_trampoline_py)


def _ensure_libdispatch_loaded() -> bool:
    """Locate libdispatch + the main queue. Returns True on success."""
    global _dispatch_lib, _dispatch_async_f_c, _dispatch_main_q_ptr
    if _dispatch_lib is not None:
        return True
    try:
        # PyDLL keeps the GIL held during C calls, preventing the
        # calling thread from being parked after dispatch_async_f.
        lib = ctypes.PyDLL("/usr/lib/system/libdispatch.dylib")
    except OSError:
        try:
            lib = ctypes.PyDLL(None)  # main program (libdispatch is in libSystem)
        except OSError as exc:
            print(f"[pn.runtime] could not load libdispatch via PyDLL: {exc!r}")
            return False
    try:
        fn = lib.dispatch_async_f
        fn.restype = None
        fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        # The main queue is a struct global named ``_dispatch_main_q``
        # in libdispatch. dispatch_async_f wants a pointer to it.
        sym = ctypes.c_void_p.in_dll(lib, "_dispatch_main_q")
        main_q_ptr = ctypes.addressof(sym)
    except (AttributeError, ValueError) as exc:
        print(f"[pn.runtime] libdispatch missing expected symbol: {exc!r}")
        return False
    _dispatch_lib = lib
    _dispatch_async_f_c = fn
    _dispatch_main_q_ptr = main_q_ptr
    return True


_pthread_main_np_c: Optional[Any] = None


def _ios_is_main_thread() -> bool:
    """Cheap main-thread check using pthread_main_np (no GIL release)."""
    try:
        # pthread_main_np is in libc; calling via PyDLL keeps the GIL.
        global _pthread_main_np_c
        if _pthread_main_np_c is None:
            libc = ctypes.PyDLL(ctypes.util.find_library("c") or "/usr/lib/libc.dylib")
            f = libc.pthread_main_np
            f.restype = ctypes.c_int
            f.argtypes = []
            _pthread_main_np_c = f
        return bool(_pthread_main_np_c())
    except Exception:
        # Fall back to threading module (Python-side check).
        return threading.current_thread().name == "MainThread"


def _ios_dispatch_async(fn: Callable[[], None]) -> None:
    """Enqueue ``fn`` on the iOS main dispatch queue (always queued)."""
    global _main_next_id
    if not _ensure_libdispatch_loaded():
        print("[pn.runtime] libdispatch unavailable; running callback inline")
        try:
            fn()
        except Exception as exc:
            print(f"[pn.runtime] inline fallback raised: {exc!r}")
        return
    with _main_pending_lock:
        _main_next_id += 1
        key = _main_next_id
        _main_pending[key] = fn
    # dispatch_async_f(queue, context, work): non-blocking; just
    # enqueues the work onto the main queue and returns.
    assert _dispatch_async_f_c is not None
    _dispatch_async_f_c(_dispatch_main_q_ptr, key, _main_trampoline_c)


def _ios_call_on_main(fn: Callable[[], None]) -> None:
    """Run ``fn`` on the iOS main thread (inline when already there)."""
    if _ios_is_main_thread():
        try:
            fn()
        except Exception as exc:
            print(f"[pn.runtime] main-inline callback raised: {exc!r}")
        return
    _ios_dispatch_async(fn)


# Cached Android main-queue plumbing. Posting a pump is a hot path (it
# runs for every batch of scheduled loop work), so the Runnable proxy
# class and the main-looper Handler are created once and reused;
# defining a ``dynamic_proxy`` class per call would register a new JNI
# class every time.
_android_runnable_cls: Optional[Any] = None
_android_main_handler: Optional[Any] = None


def _ensure_android_main_handler() -> Any:
    global _android_runnable_cls, _android_main_handler
    if _android_main_handler is not None:
        return _android_main_handler
    from java import dynamic_proxy, jclass

    Runnable = jclass("java.lang.Runnable")

    class _PNMainRunnable(dynamic_proxy(Runnable)):  # type: ignore[misc]
        def __init__(self, fn: Callable[[], None]) -> None:
            super().__init__()
            self._fn = fn

        def run(self) -> None:
            try:
                self._fn()
            except Exception as exc:  # pragma: no cover - last resort
                print(f"[pn.runtime] main-thread runnable raised: {exc!r}")

    Looper = jclass("android.os.Looper")
    Handler = jclass("android.os.Handler")
    _android_runnable_cls = _PNMainRunnable
    _android_main_handler = Handler(Looper.getMainLooper())
    return _android_main_handler


def _android_post_to_main(fn: Callable[[], None]) -> None:
    """Enqueue ``fn`` on the Android main looper (always queued)."""
    try:
        handler = _ensure_android_main_handler()
        assert _android_runnable_cls is not None
        handler.post(_android_runnable_cls(fn))
    except Exception as exc:
        print(f"[pn.runtime] _android_post_to_main failed, falling back inline: {exc!r}")
        fn()


def _android_call_on_main(fn: Callable[[], None]) -> None:
    """Run ``fn`` on the Android main thread (inline when already there)."""
    try:
        from java import jclass

        Looper = jclass("android.os.Looper")
        if Looper.myLooper() == Looper.getMainLooper():
            fn()
            return
    except Exception:
        pass
    _android_post_to_main(fn)


__all__ = [
    "call_on_main_thread",
    "call_threadsafe",
    "create_future",
    "drain",
    "get_loop",
    "reject_future",
    "resolve_future",
    "run_async",
    "run_blocking",
]
