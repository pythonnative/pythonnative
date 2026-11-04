"""The long-lived objects the app wires together, and the background sync task.

A task has to be declared at import time, somewhere the entry module imports,
because when the system starts the app for one, there's no screen and importing is
all that has happened. So the sync client and the task live here, apart from the UI.
"""

from __future__ import annotations

from datetime import timedelta

import pythonnative as pn
from pythonnative import background
from pythonnative.native_modules import NativeModuleError

from .journal import journal
from .syncing import SyncClient
from .transfers import TransferQueue

TASK_NAME = "sync"
"""Must match ``[plugins.background].tasks`` in ``pythonnative.toml``."""

transfers = TransferQueue(journal)
sync_client = SyncClient(journal, after_connect=transfers.run)


@background.task(TASK_NAME, every=timedelta(minutes=30), requires_network=True)
async def background_sync() -> background.Result:
    """Exchange entries and attachments with the server while the app isn't open.

    Returns:
        ``SUCCESS`` when there's nothing left to do, and ``RETRY`` when the server
        couldn't be reached.
    """
    await journal.load()
    url = journal.settings.server_url
    if not url:
        return background.Result.SUCCESS
    try:
        await sync_client.sync_once(url)
        await transfers.run(url)
    except (OSError, TimeoutError, pn.WebSocketError):
        return background.Result.RETRY
    return background.Result.SUCCESS


def apply_background_setting(enabled: bool) -> None:
    """Schedule or cancel the task to match the setting, and publish any reason it can't run.

    An iOS simulator always refuses to schedule background work, and so does a
    device with Background App Refresh off. Neither is an error worth more than a
    line in the settings screen.

    Args:
        enabled: The ``background_sync`` setting.
    """
    if not enabled:
        background.cancel(TASK_NAME)
        journal.publish(background_note="")
        return
    try:
        background.schedule(TASK_NAME)
    except NativeModuleError as error:
        journal.publish(
            background_note=(
                "This device won't run background work, so sync happens while the app is open."
                if error.code == "unavailable"
                else str(error)
            )
        )
    else:
        journal.publish(background_note="")
