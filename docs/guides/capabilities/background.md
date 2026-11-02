# Background tasks

`pythonnative.background` runs your Python periodically while the app isn't open. On iOS it
uses `BGTaskScheduler`, with `BGAppRefreshTask` or `BGProcessingTask`. On Android it uses
WorkManager. The system decides when a task really runs, so `every` is the shortest gap
between runs, not a timer.

## Setup

```toml
[plugins]
use = ["background"]

[plugins.background]
tasks = ["sync"]
```

iOS launches an app only for identifiers listed in `Info.plist` under
`BGTaskSchedulerPermittedIdentifiers`, so every task's name goes in `tasks`. Setting the option
also adds `fetch` and `processing` to `UIBackgroundModes`. The identifier is the task's name
exactly as written, with no bundle ID prefix, so `tasks = ["sync"]` means `"sync"` both in the
plist and in code.

Android needs nothing from the option. WorkManager brings its own manifest entries.

## Declaring a task

```python
from datetime import timedelta

from pythonnative import background


@background.task("sync", every=timedelta(minutes=30), requires_network=True)
async def sync() -> background.Result:
    await upload_pending()
    return background.Result.SUCCESS


background.schedule("sync")
```

Declare tasks at module level, somewhere your entry module imports. When the system starts the
app for a task there's no screen, and the only code that has run is your import graph. A task
declared inside a screen's module that the entry module doesn't import won't be found, and the
run fails with a message saying so. A `run` that arrives while the entry module is still
importing waits for it, so it doesn't matter that `schedule` follows the decorator.

The function can be sync or async, and it runs on the application thread. It can return a
[`Result`][pythonnative.background.Result]:

| Result | Meaning | Android | iOS |
| --- | --- | --- | --- |
| `SUCCESS`, or `None` | The work is done | `Result.success()` | `setTaskCompleted(success: true)` |
| `FAILURE`, or an exception | The work failed | `Result.failure()`. The next period still runs | `setTaskCompleted(success: false)` |
| `RETRY` | Run again soon | `Result.retry()`, with WorkManager's backoff | Same as `FAILURE`. iOS has no retry |

An exception also goes to `pn.set_error_handler`, so a crash reporter sees it.

## Options

| Argument | Meaning |
| --- | --- |
| `every` | The shortest gap between runs, starting with the first. At least 15 minutes, WorkManager's floor, on every platform. Less raises `ValueError` |
| `requires_network` | Wait for a connection. Enforced on Android. On iOS, only with `processing` |
| `requires_charging` | Wait for external power. On iOS this implies `processing` |
| `processing` | On iOS, use `BGProcessingTask`. Android ignores it |

The two iOS task types differ a lot. `BGAppRefreshTask`, the default, gets about 30 seconds and
has no way to wait for a network. `BGProcessingTask` allows minutes of work but usually waits
until the device is idle, often overnight. Android allows about 10 minutes either way, and
this plugin ends a run at 9 so that Python hears about it.

## Being stopped

The system can take the time back. A run that's stopped is canceled in Python, so your function
sees `asyncio.CancelledError` at its next `await`. Clean up and let it propagate. There's no
need to report anything, since the platform already considers the run over.

```python
@background.task("sync", every=timedelta(minutes=30))
async def sync() -> None:
    try:
        await upload_pending()
    except asyncio.CancelledError:
        await save_progress()
        raise
```

On Android this happens when constraints lapse or at the 9-minute limit, and WorkManager retries.
On iOS it's the system's expiration handler.

## Scheduling and status

| Call | Does |
| --- | --- |
| `background.schedule(name)` | Asks the system to run it. Safe on every launch: an unchanged task keeps its place in the queue |
| `background.cancel(name)` | Stops scheduling it. A run in progress isn't interrupted |
| `background.status()` | Returns a [`TaskStatus`][pythonnative.background.TaskStatus] per task: `scheduled`, `every`, `last_run`, `last_result` |
| `await background.run_now(name)` | Runs the Python function right here, for development |

`schedule` raises `NativeModuleError` when it can't do what you asked:

| Code | When |
| --- | --- |
| `unknown_task` | No `@background.task` has that name |
| `unregistered_task` | iOS only: the name isn't in `[plugins.background].tasks` |
| `unavailable` | iOS only: `BGTaskScheduler` refused. Always on a simulator, and on a device with Background App Refresh off |

## Testing it

`run_now` proves your function works, not that the system starts it. To exercise the real path:

**Android.** Find the job and force it to run:

```sh
adb shell dumpsys jobscheduler | grep <package>       # the job's number follows "JOB #u0a123/"
adb shell cmd jobscheduler run -f <package> <job id>
```

WorkManager ignores a forced run before the period is due, logging "Delaying execution". After
`schedule`, or after a run, wait out `every` first. To check that it works with no activity, press
Home and then `adb shell am kill <package>`, which only works once nothing is keeping the process
busy. **Don't use `am force-stop`.** Android blocks every job of a force-stopped app until the user
opens it again.

**iOS.** `BGTaskScheduler` doesn't work on a simulator: `schedule` raises `unavailable`. On a device,
pause in the Xcode debugger after scheduling and run:

```
e -l objc -- (void)[[BGTaskScheduler sharedScheduler] _simulateLaunchForTaskWithIdentifier:@"sync"]
```

**Tests and the browser preview.** There's no scheduler, so nothing runs by itself. `schedule`,
`cancel`, and `status` work against a stand-in. Start a task the way the platform does:

```python
from pythonnative.native_modules.registry import emit, native_module

emit("Background", "run", {"id": "1", "name": "sync"})
# Once it finishes, native_module("Background").impl.completed == {"1": "success"}.
```

## What has been verified

- **Android (API 31 emulator):** WorkManager ran scheduled tasks on time. A task forced with
  `cmd jobscheduler run -f` ran in a process that had been killed, with no activity. A run went
  through `complete` to the right result, and a task over the time limit was canceled in Python
  and retried.
- **iOS simulator:** The plist keys, handler registration at launch, and `schedule` raising
  `unavailable`. The debugger command above does nothing on a simulator, since `submit` refuses
  every request. The native path from a launch to `run`, `complete`, and `expired` was driven with a
  stand-in `BGTask` handed to the plugin before Python started, not by the system.
- **Not verified:** a real `BGTaskScheduler` launch on an iOS device, `BGProcessingTask` scheduling,
  and how iOS rations tasks in practice. None of these can be seen from a simulator.
