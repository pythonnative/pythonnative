"""The biometric lock: what covers the journal until its owner has proved who they are."""

from __future__ import annotations

from typing import Callable

import pythonnative as pn
from pythonnative.biometrics import Biometrics
from pythonnative.native_modules import NativeModuleError

from ..journal import journal
from .theme import Styles
from .widgets import PrimaryButton, slots


def biometrics_available() -> bool:
    """Return whether a prompt can be shown. A build without the capability has no prompt to show."""
    try:
        return Biometrics.is_available()
    except NativeModuleError:
        return False


async def authenticate() -> str:
    """Show the prompt, and open the journal if it succeeds.

    Returns:
        What to tell the person, or an empty string if it worked.
    """
    try:
        if await Biometrics.authenticate("Unlock your field journal"):
            journal.set_locked(False)
            return ""
    except NativeModuleError as error:
        return f"The prompt didn't open: {error.message}"
    return "That didn't work. Try again."


@pn.component
def LockScreen() -> pn.Node:
    """Ask for biometrics as soon as it appears, and again whenever someone presses the button."""
    styles = pn.use_styles(Styles)
    problem, set_problem = pn.use_state("")
    busy, set_busy = pn.use_state(False)
    available = pn.use_memo(biometrics_available, [])

    async def unlock() -> None:
        set_busy(True)
        set_problem(await authenticate())
        set_busy(False)

    async def prompt_once() -> None:
        if available:
            set_problem(await authenticate())

    pn.use_effect(prompt_once, [available])

    return pn.Column(
        *slots(
            icon=pn.Icon("lock", size=48, color=styles.colors.primary),
            title=pn.Text("Field Notes is locked", style=styles.heading),
            problem=pn.Text(problem, style=styles.error_text) if problem else None,
            action=(
                PrimaryButton("Unlock", unlock, disabled=busy)
                if available
                # Enrollment can vanish after the lock was turned on. Refusing to open
                # would strand the journal, and the device's own passcode still guards it.
                else pn.Column(
                    pn.Text("This device no longer has biometrics set up.", style=styles.center_text),
                    PrimaryButton("Open anyway", lambda: journal.set_locked(False)),
                    style=pn.style(gap=12),
                )
            ),
        ),
        style=[styles.screen, styles.center],
    )


def use_app_lock() -> bool:
    """Lock the journal each time the app leaves the foreground, if the setting is on.

    Returns:
        Whether the lock screen should cover the app right now.
    """
    lock_enabled = pn.use_store(journal.store, lambda state: state.settings.lock_enabled)
    locked = pn.use_store(journal.store, lambda state: state.locked)

    def watch() -> Callable[[], None]:
        def changed(state: str) -> None:
            if state == "background" and lock_enabled:
                journal.set_locked(True)

        return pn.AppState.add_listener(changed)

    pn.use_effect(watch, [lock_enabled])
    return bool(locked and lock_enabled)
