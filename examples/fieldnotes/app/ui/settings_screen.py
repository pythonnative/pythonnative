"""The third tab: the sync server, background work, the lock, Pro, and diagnostics."""

from __future__ import annotations

import pythonnative as pn
from pythonnative import background

from ..journal import journal
from ..models import Appearance, Settings, SyncStatus, format_moment
from ..protocol import normalize_server_url
from ..services import TASK_NAME, apply_background_setting, sync_client
from .errors_screen import ErrorLogScreen
from .lock_screen import biometrics_available
from .pro_screen import ProScreen
from .theme import Styles
from .widgets import ActionButton, Banner, Field, ScreenHeader, Section

APPEARANCES: tuple[Appearance, ...] = ("system", "light", "dark")


def describe_sync(server_url: str, status: SyncStatus) -> str:
    """Say what the connection is doing, including why it isn't working.

    Args:
        server_url: The configured server, or empty for none.
        status: What the connection is doing.

    Returns:
        One or two sentences.
    """
    if not server_url:
        return "Offline. No sync server is set, so your journal stays on this device."
    if status.phase == "connected":
        last = f" Last synced {format_moment(status.last_synced)}." if status.last_synced else ""
        return f"Connected.{last}"
    if status.phase == "waiting":
        return f"{status.detail} Trying again in {status.retry_in:.0f} seconds (attempt {status.attempt})."
    return "Connecting..."


@pn.component
def SyncSection(settings: Settings) -> pn.Node:
    """Choose a server, and watch the connection to it."""
    styles = pn.use_styles(Styles)
    status = pn.use_store(journal.store, lambda state: state.sync)
    pending = pn.use_store(journal.store, lambda state: sum(1 for entry in state.entries if entry.dirty))
    transfer_error = pn.use_store(journal.store, lambda state: state.transfer_error)
    moving = pn.use_store(journal.store, lambda state: len(state.transfers))
    address, set_address = pn.use_state(settings.server_url)
    problem, set_problem = pn.use_state("")

    async def connect() -> None:
        try:
            url = normalize_server_url(address)
        except ValueError as error:
            set_problem(str(error))
            return
        set_problem("")
        set_address(url)
        await journal.update_settings(server_url=url)

    changed = address.strip() != settings.server_url
    return Section(
        "Sync server",
        Field(
            "Server address",
            address,
            set_address,
            placeholder="192.168.1.20:8770",
            keyboard_type="url",
            auto_capitalize="none",
        ),
        pn.Text(problem, style=styles.error_text) if problem else None,
        pn.Text(describe_sync(settings.server_url, status), style=styles.body),
        (
            pn.Text(
                f"{pending} waiting to sync." if pending else "Everything has been sent.",
                style=styles.caption,
            )
            if settings.server_url
            else None
        ),
        pn.Text(f"Moving {moving} attachments...", style=styles.caption) if moving else None,
        Banner(transfer_error, "warning") if transfer_error else None,
        pn.View(
            ActionButton("Save address", "cloud", connect, disabled=not changed),
            ActionButton("Retry now", "refresh-cw", sync_client.retry_now) if status.phase == "waiting" else None,
            style=styles.wrap,
        ),
    )


def background_summary() -> str:
    """Describe the periodic task as the platform reports it."""
    for task in background.status():
        if task.name != TASK_NAME:
            continue
        if not task.scheduled:
            return "Not scheduled."
        if task.last_run is None:
            return "Scheduled. It hasn't run yet: the system decides when."
        return f"Last ran {format_moment(task.last_run.timestamp())}: {task.last_result}."
    return "Not scheduled."


@pn.component
def BackgroundSection(settings: Settings) -> pn.Node:
    """Turn periodic sync on or off, and report what the system says about it."""
    styles = pn.use_styles(Styles)
    note = pn.use_store(journal.store, lambda state: state.background_note)

    async def toggle(enabled: bool) -> None:
        await journal.update_settings(background_sync=enabled)
        apply_background_setting(enabled)

    return Section(
        "Background sync",
        pn.View(
            pn.Text("Sync while the app is closed", style=[styles.body, styles.grow]),
            pn.Switch(
                value=settings.background_sync,
                on_change=toggle,
                on_tint_color=styles.colors.primary,
                accessibility_label="Sync while the app is closed",
            ),
            style=styles.spread,
        ),
        pn.Text(note or background_summary(), style=styles.caption) if settings.background_sync else None,
    )


@pn.component
def SecuritySection(settings: Settings) -> pn.Node:
    """Require biometrics to open the journal."""
    styles = pn.use_styles(Styles)
    available = pn.use_memo(biometrics_available, [])

    async def toggle(enabled: bool) -> None:
        await journal.update_settings(lock_enabled=enabled)

    return Section(
        "Security",
        pn.View(
            pn.Text("Lock with Face ID or fingerprint", style=[styles.body, styles.grow]),
            pn.Switch(
                value=settings.lock_enabled,
                on_change=toggle,
                disabled=not available and not settings.lock_enabled,
                on_tint_color=styles.colors.primary,
                accessibility_label="Lock with Face ID or fingerprint",
            ),
            style=styles.spread,
        ),
        pn.Text("This device has no biometrics set up.", style=styles.caption) if not available else None,
    )


@pn.component
def AppearanceSection(settings: Settings) -> pn.Node:
    """Follow the system, or force light or dark."""
    styles = pn.use_styles(Styles)

    async def choose(index: int) -> None:
        choice = APPEARANCES[index]
        await journal.update_settings(appearance=choice)
        pn.appearance.set_color_scheme(None if choice == "system" else choice)

    return Section(
        "Appearance",
        pn.SegmentedControl(
            segments=["System", "Light", "Dark"],
            selected_index=APPEARANCES.index(settings.appearance),
            on_change=choose,
            tint_color=styles.colors.primary,
            accessibility_label="Appearance",
        ),
    )


class TestError(Exception):
    """Raised on purpose by the diagnostics section, to check the error screen."""


@pn.component
def Tripwire(armed: bool) -> pn.Node:
    """Raise during render when armed. An error here is what a real bug looks like to the app."""
    if armed:
        raise TestError("This is a test of the error screen.")
    return None


@pn.component
def DiagnosticsSection() -> pn.Node:
    """The error log, and a way to see what a crash looks like."""
    navigation = pn.use_navigation()
    styles = pn.use_styles(Styles)
    count = pn.use_store(journal.store, lambda state: state.logged_errors)
    armed, set_armed = pn.use_state(False)

    def fail_in_handler() -> None:
        raise TestError("This is a test of the error log.")

    return Section(
        "Diagnostics",
        pn.Text(f"Errors logged: {count}", style=styles.label),
        pn.View(
            ActionButton("Error log", "file-text", lambda: navigation.push(ErrorLogScreen())),
            ActionButton("Log a test error", "circle-alert", fail_in_handler),
            ActionButton("Test the error screen", "circle-alert", lambda: set_armed(True)),
            style=pn.style(flex_direction="row", flex_wrap="wrap", gap=8),
        ),
        Tripwire(armed=armed),
    )


@pn.component
def SettingsScreen() -> pn.Node:
    """All of the app's options."""
    navigation = pn.use_navigation()
    styles = pn.use_styles(Styles)
    settings = pn.use_store(journal.store, lambda state: state.settings)
    is_pro = pn.use_store(journal.store, lambda state: state.is_pro)

    return pn.SafeAreaView(
        ScreenHeader("Settings"),
        pn.ScrollView(
            pn.Column(
                SyncSection(settings=settings),
                BackgroundSection(settings=settings),
                Section(
                    "Field Notes Pro",
                    pn.Text(
                        "Unlocked. Attachments are unlimited." if is_pro else "Unlimited attachments, one purchase.",
                        style=styles.body,
                    ),
                    ActionButton("See Pro", "crown", lambda: navigation.push(ProScreen())),
                ),
                SecuritySection(settings=settings),
                AppearanceSection(settings=settings),
                DiagnosticsSection(),
                style=styles.content,
            ),
            style=styles.grow,
        ),
        edges=("top",),
        style=styles.screen,
    )
