"""What Pro is, and every state the store can be in when someone asks for it."""

from __future__ import annotations

import pythonnative as pn
from pythonnative.runtime import run_application_task

from ..journal import FREE_ATTACHMENTS, journal
from ..pro import pro
from .theme import Styles
from .widgets import ActionButton, Banner, PrimaryButton, Section, slots


@pn.component
def ProScreen() -> pn.Node:
    """Sell the unlock, or explain why it can't be sold here right now.

    A purchase runs as an application task, not in the button's scope. Unlocking
    swaps the button out, and that mustn't cancel the store's finish call, or the
    store would deliver the same purchase again on the next launch.
    """
    styles = pn.use_styles(Styles)
    owned = pn.use_store(journal.store, lambda state: state.is_pro)
    state = pn.use_store(journal.store, lambda state: state.pro)

    pn.use_screen_options(title="Field Notes Pro")
    pn.use_effect(pro.refresh, [])

    if owned:
        offer: pn.Node = Banner("Pro is unlocked. Thank you.", "success")
    elif state.phase == "checking":
        offer = pn.Row(pn.ActivityIndicator(), pn.Text("Asking the store...", style=styles.caption), style=styles.row)
    elif state.phase == "ready":
        offer = PrimaryButton(
            "Purchasing..." if state.busy else f"Unlock Pro for {state.display_price}",
            lambda: run_application_task(pro.buy()),
            disabled=state.busy,
        )
    else:
        offer = Banner(state.message or "The store isn't available right now.", "warning")

    return pn.ScrollView(
        pn.Column(
            *slots(
                heading=pn.Text("One purchase, no subscription.", style=styles.heading),
                pitch=pn.Text(
                    f"Free entries hold {FREE_ATTACHMENTS} attachments each, which covers most days in the field. "
                    "Pro removes the limit for every entry, on every device with your store account.",
                    style=styles.body,
                ),
                offer=offer,
                message=Banner(state.message, "info") if state.message and state.phase == "ready" else None,
                restore=(
                    Section(
                        "Already bought it?",
                        pn.Text("Restoring asks the store what your account owns.", style=styles.caption),
                        ActionButton(
                            "Restore purchase",
                            "refresh-cw",
                            lambda: run_application_task(pro.restore()),
                            disabled=state.busy or state.phase == "unavailable",
                        ),
                    )
                    if not owned
                    else None
                ),
            ),
            style=styles.content,
        ),
        style=styles.screen,
    )
