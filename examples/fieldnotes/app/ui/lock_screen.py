"""The biometric lock: what covers the journal until its owner has proved who they are."""

from __future__ import annotations

import time
from typing import Callable

import pythonnative as pn
from pythonnative.biometrics import Biometrics
from pythonnative.native_modules import NativeModuleError

from ..journal import journal
from .theme import Styles
from .widgets import PrimaryButton

GRACE_SECONDS = 30.0
"""How long the app can be away before it asks again."""


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
            journal.publish(locked=False)
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
        pn.Icon("lock", size=48, color=styles.colors.primary),
        pn.Text("Field Notes is locked", style=styles.heading),
        pn.Text(problem, style=styles.error_text) if problem else None,
        (
            PrimaryButton("Unlock", unlock, disabled=busy)
            if available
            # Enrollment can vanish after the lock was turned on. Refusing to open
            # would strand the journal, and the device's own passcode still guards it.
            else pn.Column(
                pn.Text("This device no longer has biometrics set up.", style=styles.center_text),
                PrimaryButton("Open anyway", lambda: journal.publish(locked=False)),
                style=pn.style(gap=12),
            )
        ),
        style=[styles.screen, styles.center],
    )


def use_app_lock() -> bool:
    """Lock the journal when the app comes back from the background, if the setting is on.

    A short trip doesn't count. On Android, a photo picker or the system camera is
    another activity, so this app goes to the background whenever someone attaches a
    photo, and a prompt on every return would be its own kind of broken.

    Returns:
        Whether the lock screen should cover the app right now.
    """
    lock_enabled = pn.use_store(journal.store, lambda state: state.settings.lock_enabled)
    locked = pn.use_store(journal.store, lambda state: state.locked)
    left_at = pn.use_ref(0.0)

    def watch() -> Callable[[], None]:
        def changed(state: str) -> None:
            if state == "background":
                left_at.current = time.monotonic()
            elif state == "active" and lock_enabled and left_at.current:
                if time.monotonic() - left_at.current >= GRACE_SECONDS:
                    journal.publish(locked=True)
                left_at.current = 0.0

        return pn.AppState.add_listener(changed)

    pn.use_effect(watch, [lock_enabled])
    return bool(locked and lock_enabled)
