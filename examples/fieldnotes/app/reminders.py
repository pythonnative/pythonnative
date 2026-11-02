"""Reminders to come back to an entry, as local notifications that deep-link to it."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional

from pythonnative.notifications import NotificationResponse, Notifications

from .journal import Journal
from .models import Entry

_ENTRY_URL = re.compile(r"^fieldnotes://entries/([0-9A-Za-z_-]{1,64})$")


@dataclass(frozen=True)
class Preset:
    """A reminder time someone can choose without a date picker.

    Attributes:
        label: The button's title.
        delay: Returns how many seconds away the time is, given the current moment.
    """

    label: str
    delay: Callable[[datetime], float]


def _tomorrow_morning(now: datetime) -> float:
    morning = (now + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
    return (morning - now).total_seconds()


PRESETS: tuple[Preset, ...] = (
    Preset("In 1 minute", lambda now: 60.0),
    Preset("In 1 hour", lambda now: 3600.0),
    Preset("Tomorrow morning", _tomorrow_morning),
    Preset("Next week", lambda now: 7 * 86400.0),
)


def notification_id(entry_id: str) -> str:
    """Return the identifier an entry's reminder is scheduled under, one per entry."""
    return f"entry-{entry_id}"


def entry_url(entry_id: str) -> str:
    """Return an entry's deep link."""
    return f"fieldnotes://entries/{entry_id}"


def entry_id_from(response: NotificationResponse) -> Optional[str]:
    """Find the entry a tapped notification points at.

    The data of a tap arrives through the launching intent on Android, and any
    installed app can start an activity with such an intent, so it's checked as
    carefully as any other deep link.

    Args:
        response: The tap.

    Returns:
        The entry's ID, or ``None`` if the data doesn't name an entry.
    """
    url = response.data.get("url")
    match = _ENTRY_URL.match(url) if isinstance(url, str) else None
    return match.group(1) if match else None


async def schedule_reminder(journal: Journal, entry: Entry, delay_seconds: float) -> bool:
    """Ask for permission if needed, schedule the notification, and remember it.

    Args:
        journal: Where the reminder is remembered.
        entry: The entry to come back to.
        delay_seconds: Seconds from now.

    Returns:
        ``False`` if notifications aren't allowed, so nothing was scheduled.
    """
    if not await Notifications.request_permission():
        return False
    scheduled = await Notifications.schedule(
        entry.display_title,
        "Time to come back to this entry.",
        delay_seconds=delay_seconds,
        identifier=notification_id(entry.id),
        data={"url": entry_url(entry.id)},
    )
    if scheduled:
        await journal.set_reminder(entry.id, time.time() + delay_seconds)
    return scheduled


async def cancel_reminder(journal: Journal, entry_id: str) -> None:
    """Remove an entry's pending reminder."""
    await Notifications.cancel(notification_id(entry_id))
    await journal.clear_reminder(entry_id)
