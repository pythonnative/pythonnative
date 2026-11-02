"""Field Notes: a field journal that works offline and syncs when it can.

This module is the entry point, so it's also what the system imports when it starts
the app for a background task with no screen. It declares what has to exist either
way: the navigators, the error handler, and, by importing ``services``, the task.
"""

from __future__ import annotations

from typing import Callable, Mapping, Optional

import pythonnative as pn
from pythonnative.navigation import LinkTable, NavigationState
from pythonnative.notifications import NotificationResponse, Notifications

from .journal import journal
from .models import Snapshot
from .pro import pro
from .reminders import entry_id_from, entry_url
from .services import apply_background_setting, sync_client
from .ui.capture_screen import CaptureScreen
from .ui.editor_screen import EditorScreen
from .ui.entry_screen import EntryScreen
from .ui.errors_screen import ErrorLogScreen
from .ui.fallback import error_fallback
from .ui.journal_screen import JournalScreen
from .ui.lock_screen import LockScreen, use_app_lock
from .ui.map_screen import MapScreen
from .ui.media_screen import MediaScreen
from .ui.pro_screen import ProScreen
from .ui.settings_screen import SettingsScreen
from .ui.theme import DARK, LIGHT

LINK_PREFIXES = ["fieldnotes://"]

Tabs = pn.TabNavigator(
    pn.Screen(JournalScreen, title="Journal", tab_bar_icon="notebook-pen", path="journal"),
    pn.Screen(MapScreen, title="Map", tab_bar_icon="map", path="map"),
    pn.Screen(SettingsScreen, title="Settings", tab_bar_icon="settings", path="settings"),
    name="Main",
)

Root = pn.StackNavigator(
    pn.Screen(Tabs, header_shown=False),
    pn.Screen(EntryScreen, title="Entry", path="entries/{id}"),
    pn.Screen(EditorScreen, title="New entry", path="new"),
    pn.Screen(CaptureScreen, title="Capture"),
    pn.Screen(MediaScreen, title="Attachment"),
    pn.Screen(ProScreen, title="Field Notes Pro", path="pro"),
    pn.Screen(ErrorLogScreen, title="Error log"),
)

navigation = pn.NavigationRef()
"""Lets a notification tap, which arrives from outside the tree, open a screen."""

# The handler goes in at import time, so it hears about errors from the first render.
pn.set_error_handler(journal.errors.record)
pn.set_error_fallback(error_fallback)


def launch_state() -> Optional[NavigationState]:
    """Return the navigation state for the notification tap that launched the app, if one did.

    Seeding the first state means the entry is on screen from the first frame,
    with the journal beneath it for the back button. Navigating afterward would
    flash the journal first. ``last_response`` answers during a first render, and
    reading it claims the tap, so ``on_response`` won't deliver it a second time.

    Returns:
        The state, or ``None`` when the app started some other way.
    """
    launch = Notifications.last_response()
    entry_id = entry_id_from(launch) if launch is not None else None
    if entry_id is None:
        return None
    return LinkTable(Root, LINK_PREFIXES).state_from_url(entry_url(entry_id))


def open_notification(response: NotificationResponse) -> None:
    """Open the entry a tapped notification points at, while the app is running.

    Args:
        response: The tap.
    """
    entry_id = entry_id_from(response)
    if entry_id is not None and navigation.is_ready():
        navigation.navigate(EntryScreen(id=entry_id))


def use_sync(snapshot_url: str) -> None:
    """Keep the live connection and its triggers running while the app is mounted.

    Args:
        snapshot_url: The configured server. Changing it replaces the connection.
    """

    async def follow() -> None:
        await sync_client.run(snapshot_url)

    pn.use_effect(follow, [snapshot_url])

    def watch_conditions() -> Callable[[], None]:
        def network_changed(state: Mapping[str, object]) -> None:
            if state.get("is_connected"):
                sync_client.retry_now()

        def app_changed(state: str) -> None:
            if state == "active":
                sync_client.retry_now()

        stop_network = pn.NetInfo.add_listener(network_changed)
        stop_app = pn.AppState.add_listener(app_changed)

        def stop() -> None:
            stop_network()
            stop_app()

        return stop

    pn.use_effect(watch_conditions, [])


@pn.component
def Shell() -> pn.Node:
    """Everything that runs once the journal is on disk and its settings are known."""
    server_url = pn.use_store(journal.store, lambda state: state.settings.server_url)
    locked = use_app_lock()
    initial_state = pn.use_memo(launch_state, [])

    use_sync(server_url)

    def start() -> Callable[[], None]:
        apply_background_setting(journal.settings.background_sync)
        stop_notifications = Notifications.on_response(open_notification)
        stop_received = Notifications.on_received(
            lambda received: pn.run_async(journal.refresh()),
        )
        stop_purchases = pro.listen()

        def stop() -> None:
            stop_notifications()
            stop_received()
            stop_purchases()

        return stop

    pn.use_effect(start, [])

    return pn.View(
        pn.NavigationContainer(Root, link_prefixes=LINK_PREFIXES, initial_state=initial_state, ref=navigation),
        # Present it only while locked: a modal's children stay mounted while it's
        # hidden, and this one prompts for biometrics as soon as it mounts.
        (
            pn.Modal(
                LockScreen(),
                visible=True,
                animation_type="none",
                presentation_style="full_screen",
                dismiss_on_backdrop=False,
            )
            if locked
            else None
        ),
        style=pn.style(flex=1),
    )


@pn.component
def Startup(snapshot: Snapshot) -> pn.Node:
    """What shows before the journal opens, or instead of it if it can't."""
    return pn.Column(
        (
            pn.Text(snapshot.error, style=pn.style(padding=24, color="#B3261E"))
            if snapshot.error
            else pn.ActivityIndicator()
        ),
        style=pn.style(flex=1, align_items="center", justify_content="center"),
    )


@pn.component
def App() -> pn.Node:
    """The root: load the journal, then show it, in the chosen appearance."""
    snapshot = pn.use_store(journal.store)

    async def load() -> None:
        await journal.load()
        appearance = journal.settings.appearance
        pn.appearance.set_color_scheme(None if appearance == "system" else appearance)

    pn.use_effect(load, [])

    return pn.ThemeProvider(
        (
            Startup(snapshot=snapshot)
            if snapshot.loading or (snapshot.error and not snapshot.settings.device_id)
            else Shell()
        ),
        light=LIGHT,
        dark=DARK,
    )
