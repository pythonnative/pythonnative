"""Asyncio runtime for PythonNative.

PythonNative runs a single, framework-wide ``asyncio`` event loop on
a dedicated daemon thread. Every awaitable surface in the framework
schedules its work on this loop via
[`run_async`][pythonnative.runtime.run_async]: the async hooks
([`use_async_effect`][pythonnative.hooks.use_async_effect],
[`use_query`][pythonnative.hooks.use_query],
[`use_mutation`][pythonnative.hooks.use_mutation]), the
[`fetch`][pythonnative.net.fetch] HTTP client,
[`AsyncStorage`][pythonnative.storage.AsyncStorage], the awaitable
native modules
([`Camera`][pythonnative.native_modules.camera.Camera] /
[`Location`][pythonnative.native_modules.location.Location] /
[`Notifications`][pythonnative.native_modules.notifications.Notifications]),
and awaited animations.

The reconciler is **not** asyncio-aware; it still runs synchronously on
the platform main thread. Coroutines that want to mutate component
state simply call the regular ``use_state`` setter, and the existing
deferred-render path inside the screen host marshals the re-render
onto the main thread. The runtime is therefore additive: it gives
coroutines somewhere to live without changing the rendering contract.

Example:
    ```python
    import asyncio

    import pythonnative as pn


    async def hello() -> str:
        await asyncio.sleep(0.1)
        return "hi"


    future = pn.runtime.run_async(hello())
    print(future.result(timeout=1.0))  # "hi"
    ```
"""

from __future__ import annotations

import asyncio
import ctypes
import ctypes.util
import inspect
import threading
from concurrent.futures import Future as _ThreadFuture
from typing import Any, Awaitable, Callable, Coroutine, Dict, Optional, TypeVar, Union

T = TypeVar("T")


# ======================================================================
# Module-level loop singleton
# ======================================================================

_loop: Optional[asyncio.AbstractEventLoop] = None
_thread: Optional[threading.Thread] = None
_lock = threading.Lock()


# ======================================================================
# Apple QoS bump (iOS / macOS)
# ======================================================================
#
# By default ``threading.Thread`` lands at a low QoS class on Apple
# platforms, which iOS subjects to wake-up coalescing; the asyncio
# loop only gets ~2 timeslices per second (~500ms granularity). Bumping
# the thread to ``QOS_CLASS_USER_INTERACTIVE`` is *necessary* for it to
# be treated as foreground work, but on the simulator it's not
# *sufficient* on its own. The companion fix is the PyDLL-based main
# thread dispatch further down in this file, which keeps the GIL held
# (and the thread off the kernel's coalescing grid) for the actual
# bg→main hop.

# qos_class_t value from <sys/qos.h>
_QOS_CLASS_USER_INTERACTIVE = 0x21


def _apply_apple_thread_qos() -> None:
    """Bump the calling thread to ``USER_INTERACTIVE`` on iOS.

    No-op on other platforms or if the symbol can't be loaded. Must be
    called from inside the target thread (the underlying syscall is
    ``pthread_set_qos_class_self_np``). Empirically ``USER_INTERACTIVE``
    is required on iOS; anything lower triggers wake-up coalescing on
    the background asyncio thread, which adds ~500ms latency to every
    cross-thread dispatch.
    """
    from .platform import Platform

    if not Platform.is_ios:
        return
    try:
        libc_path = ctypes.util.find_library("c")
        if libc_path is None:
            return
        libc = ctypes.CDLL(libc_path)
        set_fn = libc.pthread_set_qos_class_self_np
        set_fn.argtypes = [ctypes.c_int, ctypes.c_int]
        set_fn.restype = ctypes.c_int
        set_fn(_QOS_CLASS_USER_INTERACTIVE, 0)
    except Exception as exc:
        print(f"[pn.runtime] could not bump thread QoS: {exc!r}")


def _spawn_loop() -> asyncio.AbstractEventLoop:
    """Create a fresh event loop on a daemon thread and block until it's running."""
    loop = asyncio.new_event_loop()
    ready = threading.Event()

    def _run() -> None:
        _apply_apple_thread_qos()
        asyncio.set_event_loop(loop)
        ready.set()
        loop.run_forever()

    thread = threading.Thread(target=_run, daemon=True, name="pn-asyncio")
    thread.start()
    ready.wait()

    global _thread
    _thread = thread
    return loop


def get_loop() -> asyncio.AbstractEventLoop:
    """Return the framework-wide event loop, starting it on first use.

    The loop runs on a daemon thread (``"pn-asyncio"``) and lives for
    the duration of the process. It is safe to call this from any
    thread.

    Returns:
        The shared :class:`asyncio.AbstractEventLoop`.
    """
    global _loop
    if _loop is not None and not _loop.is_closed():
        return _loop
    with _lock:
        if _loop is None or _loop.is_closed():
            _loop = _spawn_loop()
        return _loop


def _shutdown_for_tests() -> None:
    """Stop the runtime loop, primarily for test isolation.

    Cancels every pending task, stops the loop, joins the thread, and
    clears the module-level state so the next call to
    [`get_loop`][pythonnative.runtime.get_loop] starts a fresh loop.
    Production code should not call this; the loop is a daemon and
    will be torn down with the process.
    """
    global _loop, _thread
    with _lock:
        loop = _loop
        thread = _thread
        _loop = None
        _thread = None
    if loop is None:
        return
    try:
        for task in asyncio.all_tasks(loop):
            loop.call_soon_threadsafe(task.cancel)
        loop.call_soon_threadsafe(loop.stop)
    except RuntimeError:
        pass
    if thread is not None:
        thread.join(timeout=2.0)
    try:
        loop.close()
    except RuntimeError:
        pass


# ======================================================================
# Scheduling helpers
# ======================================================================


Awaitlike = Union[Coroutine[Any, Any, T], Awaitable[T]]


def run_async(awaitable: Awaitlike[T]) -> "_ThreadFuture[T]":
    """Schedule ``awaitable`` on the framework loop and return a thread future.

    Use this when calling async code from synchronous code (e.g. an
    event handler, a hook setup function, or a test). The returned
    :class:`concurrent.futures.Future` is created by
    :func:`asyncio.run_coroutine_threadsafe` so it can be ``result()``-ed
    from the calling thread and ``cancel()``-ed from anywhere.

    Args:
        awaitable: Either a coroutine object (the typical case) or any
            awaitable. Awaitables that are not coroutines are wrapped
            with :func:`asyncio.ensure_future` on the loop.

    Returns:
        A thread-safe future that resolves with the coroutine's return
        value, or raises its exception.

    Example:
        ```python
        import pythonnative as pn

        async def work():
            return 42

        fut = pn.runtime.run_async(work())
        assert fut.result(timeout=1.0) == 42
        ```
    """
    loop = get_loop()
    if inspect.iscoroutine(awaitable):
        return asyncio.run_coroutine_threadsafe(awaitable, loop)

    async def _wrap() -> T:
        return await awaitable

    return asyncio.run_coroutine_threadsafe(_wrap(), loop)


def call_threadsafe(callback: Callable[..., Any], *args: Any) -> None:
    """Schedule ``callback(*args)`` on the loop thread.

    Thin wrapper around
    :meth:`asyncio.AbstractEventLoop.call_soon_threadsafe`. Useful from
    native delegates (which may fire on arbitrary threads) when you
    need to hop onto the runtime thread before touching asyncio
    primitives.
    """
    get_loop().call_soon_threadsafe(callback, *args)


def resolve_future(future: "asyncio.Future[T]", value: T) -> None:
    """Set ``future``'s result from any thread (no-op if already done).

    Convenience used by every native delegate that wraps a callback
    into an awaitable: the delegate doesn't have to know which thread
    it's on, only that it must not race with cancellation.

    Args:
        future: An :class:`asyncio.Future` bound to the runtime loop.
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
    """Create a future bound to the framework runtime loop.

    Safe to call from any thread. The returned future is **not**
    attached to whatever loop is current on the caller; instead it
    lives on the framework's shared loop so any thread can call
    [`resolve_future`][pythonnative.runtime.resolve_future] /
    [`reject_future`][pythonnative.runtime.reject_future] on it.
    """
    return get_loop().create_future()


# ======================================================================
# UI-thread bridge
# ======================================================================
#
# Every awaitable that touches the platform's UI APIs runs on the
# framework's background asyncio loop, but UIKit and the Android view
# system require all UI calls on the platform main thread. The helpers
# below marshal a synchronous Python callable onto the right thread per
# platform, so awaitable code (alerts, animations, etc.) can transparently
# bridge back when it needs to talk to native UI.


# Desktop (Tkinter) main-thread dispatcher, installed by
# ``pythonnative.preview`` while a ``pn preview`` session is live. Tk is
# not thread-safe, so UI work scheduled from the asyncio worker thread
# (animations, alerts) must hop onto the Tk main thread; the preview's
# poll loop drains whatever this dispatcher enqueues. When no preview is
# running (plain scripts / tests) the dispatcher stays ``None`` and work
# runs inline.
_desktop_main_dispatch: Optional[Callable[[Callable[[], None]], None]] = None


def set_desktop_main_dispatch(dispatch: Optional[Callable[[Callable[[], None]], None]]) -> None:
    """Install (or clear) the desktop main-thread dispatcher.

    Called by ``pythonnative.preview`` with a
    function that marshals ``fn`` onto the Tk main thread, and with
    ``None`` when the preview window closes.
    """
    global _desktop_main_dispatch
    _desktop_main_dispatch = dispatch


def call_on_main_thread(fn: Callable[[], None]) -> None:
    """Run ``fn()`` on the platform UI thread.

    - **iOS**: dispatches ``fn`` onto the main dispatch queue via
      ``libdispatch.dispatch_async_f`` (called through
      :class:`ctypes.PyDLL` to keep the GIL held; see the
      ``_ios_call_on_main`` comment block for why this matters).
    - **Android**: posts a ``Runnable`` to
      ``Handler(Looper.getMainLooper())``.
    - **Desktop**: enqueues ``fn`` for the ``pn preview`` poll loop to
      run on the Tk main thread (or runs inline if no preview is live).
    - **Tests**: runs ``fn()`` inline.

    Exceptions raised by ``fn`` are caught and printed; they must not
    propagate into UIKit / the Android Looper. If you need to surface
    a result back to the asyncio loop, do it via
    [`resolve_future`][pythonnative.runtime.resolve_future] from
    inside ``fn``.

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
# iOS main-thread dispatch (PyDLL-based, no GIL release)
# ----------------------------------------------------------------------
#
# rubicon-objc loads libobjc via ctypes.CDLL, which RELEASES THE GIL
# around every ObjC method call. On the iOS simulator (and to a lesser
# extent on-device), the asyncio thread is then parked by the kernel
# until the next wakeup-coalescing tick (~500ms), making each ObjC call
# absurdly slow when made from a background thread.
#
# To avoid this, we call libdispatch's ``dispatch_async_f`` directly
# via ``ctypes.PyDLL`` (which keeps the GIL held), and pass a
# ``CFUNCTYPE`` trampoline as the work function. The trampoline runs
# on the main thread, looks up the pending Python callable by an
# integer key, and invokes it.

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
        # asyncio thread from being parked after dispatch_async_f.
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


def _ios_call_on_main(fn: Callable[[], None]) -> None:
    """Dispatch ``fn`` to the iOS main thread without releasing the GIL.

    Uses libdispatch's ``dispatch_async_f`` via ``ctypes.PyDLL`` to
    avoid the rubicon-objc / CDLL GIL release that causes the asyncio
    thread to be parked by the kernel for ~500ms on each call.
    """
    global _main_next_id
    if _ios_is_main_thread():
        try:
            fn()
        except Exception as exc:
            print(f"[pn.runtime] main-inline callback raised: {exc!r}")
        return

    if not _ensure_libdispatch_loaded():
        # Last-resort fallback: run inline (UI calls may crash, but at
        # least we don't deadlock).
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


def _android_call_on_main(fn: Callable[[], None]) -> None:
    """Android-only: post ``fn`` to the main looper via Handler."""
    try:
        from java import dynamic_proxy, jclass

        Looper = jclass("android.os.Looper")
        if Looper.myLooper() == Looper.getMainLooper():
            fn()
            return

        Runnable = jclass("java.lang.Runnable")

        class _PNMainRunnable(dynamic_proxy(Runnable)):  # type: ignore[misc]
            def run(self) -> None:
                try:
                    fn()
                except Exception as exc:  # pragma: no cover - last resort
                    print(f"[pn.runtime] main-thread runnable raised: {exc!r}")

        Handler = jclass("android.os.Handler")
        Handler(Looper.getMainLooper()).post(_PNMainRunnable())
    except Exception as exc:
        print(f"[pn.runtime] _android_call_on_main failed, falling back inline: {exc!r}")
        fn()


__all__ = [
    "call_on_main_thread",
    "call_threadsafe",
    "create_future",
    "get_loop",
    "reject_future",
    "resolve_future",
    "run_async",
]
