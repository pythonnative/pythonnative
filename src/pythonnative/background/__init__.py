"""Run Python periodically while the app isn't open.

Enable it in ``pythonnative.toml``. iOS only launches for identifiers listed
in the app's ``Info.plist``, so every task's name also goes under ``tasks``:

```toml
[plugins]
use = ["background"]

[plugins.background]
tasks = ["sync"]
```

Declare tasks at module level, somewhere the app's entry module imports, so
they exist when the system starts the app with no screen:

Example:
    ```python
    from datetime import timedelta

    from pythonnative import background

    @background.task("sync", every=timedelta(minutes=30), requires_network=True)
    async def sync() -> background.Result:
        await upload_pending()
        return background.Result.SUCCESS

    background.schedule("sync")
    ```

The system decides when a task really runs: ``every`` is the shortest gap
between runs, not a timer.
"""

from __future__ import annotations

import asyncio
import inspect
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Literal, Mapping, Optional, Protocol, TypeVar, Union

from ..native_modules.registry import NativeModuleError, native_module, on_event
from ..runtime import run_application_task
from ..sdk.plugin import plugin_module

__all__ = ["MINIMUM_INTERVAL", "Result", "TaskStatus", "cancel", "run_now", "schedule", "status", "task"]

MINIMUM_INTERVAL = timedelta(minutes=15)
"""The shortest ``every``: WorkManager's floor for periodic work, applied on every platform."""

_IMPORT_WAIT = 30.0
_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


class Result(str, Enum):
    """What a task reports when it finishes.

    A task that returns ``None`` counts as ``SUCCESS``, and one that raises
    counts as ``FAILURE``.

    Attributes:
        SUCCESS: The work is done.
        FAILURE: The work failed. The next period still runs.
        RETRY: Run again soon. Android backs off and retries. iOS has no
            retry, so this counts as a failure until the next period.
    """

    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"


@dataclass(frozen=True)
class TaskStatus:
    """What the platform knows about one task.

    Attributes:
        name: The task's name.
        scheduled: Whether [`schedule`][pythonnative.background.schedule] is in effect.
        every: The shortest gap between runs.
        last_run: When the system last started the task from the background.
            [`run_now`][pythonnative.background.run_now] doesn't count.
        last_result: How that run ended: ``"success"``, ``"failure"``,
            ``"retry"``, or ``"expired"`` when the system stopped it first.
    """

    name: str
    scheduled: bool
    every: Optional[timedelta] = None
    last_run: Optional[datetime] = None
    last_result: Optional[str] = None


TaskFunction = Callable[[], Union[Awaitable[Optional[Result]], Optional[Result]]]
F = TypeVar("F", bound=TaskFunction)


@dataclass(frozen=True)
class _Task:
    name: str
    function: TaskFunction
    every: timedelta
    requires_network: bool
    requires_charging: bool
    processing: bool


class _BackgroundService(Protocol):
    def ready(self) -> None: ...

    def schedule(
        self,
        *,
        name: str,
        every: float,
        requires_network: bool = False,
        requires_charging: bool = False,
        processing: bool = False,
    ) -> None: ...

    def cancel(self, name: str) -> None: ...

    def status(self) -> List[Dict[str, Any]]: ...

    def complete(self, id: str, result: Literal["success", "failure", "retry"]) -> None: ...


class _Fallback:
    """No system scheduler off device: records what the facade asks for.

    Tests start a task the way the platform does, by emitting ``run``, and
    read ``completed`` for the answer.
    """

    def __init__(self) -> None:
        self.is_ready = False
        self.scheduled: Dict[str, float] = {}
        self.completed: Dict[str, str] = {}

    def ready(self) -> None:
        self.is_ready = True

    def schedule(
        self,
        *,
        name: str,
        every: float,
        requires_network: bool = False,
        requires_charging: bool = False,
        processing: bool = False,
    ) -> None:
        del requires_network, requires_charging, processing
        self.scheduled[name] = every

    def cancel(self, name: str) -> None:
        self.scheduled.pop(name, None)

    def status(self) -> List[Dict[str, Any]]:
        return [{"name": name, "scheduled": True, "every": every} for name, every in self.scheduled.items()]

    def complete(self, id: str, result: str) -> None:
        self.completed[id] = result


plugin_module(
    "Background",
    _BackgroundService,
    plugin="background",
    events={"run": Dict[str, Any], "expired": Dict[str, Any]},
    fallback=_Fallback,
)

_tasks: Dict[str, _Task] = {}
_running: Dict[str, Any] = {}


def task(
    name: str,
    *,
    every: timedelta,
    requires_network: bool = False,
    requires_charging: bool = False,
    processing: bool = False,
) -> Callable[[F], F]:
    """Declare a background task. Use it as a decorator at module level.

    The decorated function may be sync or async. It runs on the application
    thread, with no screen on the way when the system starts the app for it.
    Declaring a task doesn't start it; call
    [`schedule`][pythonnative.background.schedule] for that.

    Args:
        name: A stable name of letters, digits, ``.``, ``_``, and ``-``. On
            iOS it must also be listed in ``[plugins.background].tasks``.
        every: The shortest gap between runs, at least
            [`MINIMUM_INTERVAL`][pythonnative.background.MINIMUM_INTERVAL].
        requires_network: Wait for a network connection. iOS only enforces
            this with ``processing``, since `BGAppRefreshTask` has no such
            constraint.
        requires_charging: Wait for external power. On iOS this implies
            ``processing``.
        processing: On iOS, use `BGProcessingTask`, which allows minutes of
            work but usually waits until the device is idle, instead of
            `BGAppRefreshTask`, which gets about 30 seconds. Android ignores
            it, and always allows about 10 minutes.

    Raises:
        ValueError: If the name is malformed or ``every`` is below the floor.
    """
    if not _NAME.fullmatch(name):
        raise ValueError(f"Background task name {name!r} may only use letters, digits, '.', '_', and '-'")
    if every < MINIMUM_INTERVAL:
        raise ValueError(f"Background task {name!r}: every must be at least {MINIMUM_INTERVAL}, got {every}")

    def register(function: F) -> F:
        _tasks[name] = _Task(name, function, every, requires_network, requires_charging, processing)
        return function

    return register


def schedule(name: str) -> None:
    """Ask the system to run a declared task periodically, until it's canceled.

    Survives restarts of the app. Safe to call on every launch: an unchanged
    task keeps its place in the system's queue.

    Args:
        name: The task's name.

    Raises:
        NativeModuleError: With the code ``unknown_task`` if no ``@task`` has
            this name; ``unregistered_task`` on iOS if it isn't listed in
            ``[plugins.background].tasks``; ``unavailable`` on iOS if the
            system refuses, which it always does on a simulator and does when
            Background App Refresh is off; or ``plugin_not_enabled`` if
            ``background`` isn't in the build.
    """
    declared = _tasks.get(name)
    if declared is None:
        raise NativeModuleError("Background", "schedule", f"no @background.task named {name!r}", "unknown_task")
    native_module("Background").call(
        "schedule",
        name=name,
        every=declared.every.total_seconds(),
        requires_network=declared.requires_network,
        requires_charging=declared.requires_charging,
        processing=declared.processing or declared.requires_charging,
    )


def cancel(name: str) -> None:
    """Stop scheduling a task. A run already in progress isn't interrupted.

    Args:
        name: The task's name. An unscheduled name does nothing.

    Raises:
        NativeModuleError: With the code ``plugin_not_enabled`` if
            ``background`` isn't in the build.
    """
    native_module("Background").call("cancel", name=name)


def status() -> List[TaskStatus]:
    """Report every declared task, and any scheduled one no longer declared.

    Raises:
        NativeModuleError: With the code ``plugin_not_enabled`` if
            ``background`` isn't in the build.
    """
    rows = {row["name"]: row for row in native_module("Background").call("status")}
    names = [*_tasks, *(name for name in rows if name not in _tasks)]
    return [_status(name, rows.get(name, {})) for name in names]


def _status(name: str, row: Mapping[str, Any]) -> TaskStatus:
    declared = _tasks.get(name)
    every = timedelta(seconds=row["every"]) if row.get("every") else declared.every if declared else None
    last_run = datetime.fromtimestamp(row["last_run"], tz=timezone.utc) if row.get("last_run") else None
    return TaskStatus(name, bool(row.get("scheduled")), every, last_run, row.get("last_result"))


async def run_now(name: str) -> Result:
    """Run a declared task's Python function here and now, for development.

    This calls the function in-process and involves no system scheduler, so
    it proves your code works, not that the system will start it. Exceptions
    propagate, and ``status()`` doesn't change. To exercise the real path, see
    the capability guide.

    Args:
        name: The task's name.

    Returns:
        What the function returned.

    Raises:
        NativeModuleError: With the code ``unknown_task`` if no ``@task`` has
            this name.
    """
    declared = _tasks.get(name)
    if declared is None:
        raise NativeModuleError("Background", "run_now", f"no @background.task named {name!r}", "unknown_task")
    return await _call(declared)


async def _call(declared: _Task) -> Result:
    value = declared.function()
    if inspect.isawaitable(value):
        value = await value
    return Result.SUCCESS if value is None else Result(value)


async def _declared(name: str) -> Optional[_Task]:
    """Find a task, waiting out the app's import.

    Native releases ``run`` as soon as this module loads, which is before the
    entry module has reached the ``@task`` lines that follow its imports.
    """
    from ..bootstrap import status as bootstrap_status
    from ..bridge import has_transport

    deadline = time.monotonic() + _IMPORT_WAIT
    while name not in _tasks and has_transport() and not bootstrap_status() and time.monotonic() < deadline:
        await asyncio.sleep(0.02)
    return _tasks.get(name)


async def _invoke(invocation: str, name: str) -> None:
    result = Result.FAILURE
    try:
        declared = await _declared(name)
        if declared is None:
            print(
                f"[pn.background] The system started {name!r}, but no @background.task has that name. "
                "Declare it where the app's entry module imports it.",
                file=sys.stderr,
            )
        else:
            result = await _call(declared)
    except Exception as error:
        from ..diagnostics import report_error

        report_error(error, phase=f"background task {name}")
        print(f"[pn.background] {name!r} failed: {error!r}", file=sys.stderr)
    finally:
        _running.pop(invocation, None)
    native_module("Background").call("complete", id=invocation, result=result.value)


def _on_run(payload: Mapping[str, Any]) -> None:
    invocation = str(payload["id"])
    _running[invocation] = run_application_task(_invoke(invocation, str(payload["name"])))


def _on_expired(payload: Mapping[str, Any]) -> None:
    running = _running.pop(str(payload["id"]), None)
    if running is not None:
        running.cancel()


on_event("Background", "run", _on_run)
on_event("Background", "expired", _on_expired)

try:
    native_module("Background").call("ready")
except NativeModuleError:
    # Not in this build. Importing stays harmless; calling says what to do.
    pass
