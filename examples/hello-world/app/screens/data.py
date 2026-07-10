"""Data screen: ``use_query``, ``use_mutation``, persisted state, awaitable alerts.

Pushed onto the navigation stack from the Showcase screen. Showcases
PythonNative's async surface end-to-end without needing a network
connection: the "fetch" is simulated with ``asyncio.sleep``, taps are
counted in [`AsyncStorage`][pythonnative.AsyncStorage] via
[`use_persisted_state`][pythonnative.use_persisted_state], and the
reset button awaits a [`pn.Alert.confirm`][pythonnative.Alert.confirm]
before wiping the saved value.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

import pythonnative as pn
from app.theme import styles

local_styles = pn.StyleSheet.create(
    quote_card=pn.style(
        padding=20,
        background_color="#FEF3C7",
        border_radius=12,
        spacing=8,
    ),
    counter_card=pn.style(
        padding=16,
        background_color="#F0F9FF",
        border_radius=12,
        spacing=10,
        align_items="center",
    ),
)


async def _fake_load_quote() -> str:
    """Pretend to call an API: 600ms delay, then a random quote."""
    await asyncio.sleep(0.6)
    return random.choice(
        [
            "Simple is better than complex.",
            "Errors should never pass silently.",
            "Now is better than never.",
            "Readability counts.",
            "Beautiful is better than ugly.",
        ]
    )


@pn.component
def QuoteCard() -> pn.Element:
    """Loads a quote on mount and lets the user refetch."""
    q = pn.use_query(_fake_load_quote, [])

    if q.loading and q.data is None:
        body: pn.Element = pn.Text("Loading…", style=styles["hint"])
    elif q.error is not None:
        body = pn.Text(f"Error: {q.error}", style=styles["hint"])
    else:
        body = pn.Text(q.data or "", style=pn.style(font_size=18, font_weight="600"))

    return pn.View(
        pn.Text("From an async source", style=styles["section_title"]),
        body,
        pn.Button(
            "Refresh" if not q.loading else "Refreshing…",
            on_press=q.refetch,
        ),
        style=local_styles["quote_card"],
    )


async def _save_tap_count(count: int) -> int:
    """Pretend to call an API that confirms the save and returns the new total."""
    await asyncio.sleep(0.3)
    return count


@pn.component
def TapCounter() -> pn.Element:
    """A persisted counter with an awaitable confirm-clear flow."""
    count, set_count = pn.use_persisted_state("data_demo.taps", 0)
    mutation, save = pn.use_mutation(_save_tap_count)

    def tap() -> None:
        new = count + 1
        set_count(new)
        save(new)

    async def clear() -> None:
        if await pn.Alert.confirm(
            "Reset counter?",
            message="This will clear the saved tap total.",
            confirm_label="Reset",
            cancel_label="Keep",
        ):
            set_count(0)
            save(0)

    def on_clear() -> None:
        # Alert.confirm is awaitable; fire it on the runtime loop so
        # we can use it from a sync ``on_press`` handler.
        pn.run_async(clear())

    return pn.View(
        pn.Text("Persisted counter", style=styles["section_title"]),
        pn.Text(f"Taps so far: {count}", style=pn.style(font_size=20, font_weight="600")),
        pn.Text(
            "Confirmed save…" if mutation.loading else "Saved.",
            style=styles["hint"],
        ),
        pn.Row(
            pn.Button("Tap me", on_press=tap),
            pn.Button("Reset", on_press=on_clear),
            style=pn.style(spacing=8, align_items="center"),
        ),
        style=local_styles["counter_card"],
    )


@pn.component
def DataScreen() -> pn.Element:
    """The full data-demo screen."""
    nav = pn.use_navigation()

    return pn.ScrollView(
        pn.Column(
            pn.Text("Async hooks demo", style=styles["title"]),
            pn.Text(
                "Demonstrates use_query, use_mutation, use_persisted_state, " "and awaitable pn.Alert.confirm.",
                style=styles["hint"],
            ),
            QuoteCard(),
            TapCounter(),
            pn.Button("Back", on_press=nav.go_back),
            style=styles["section"],
        )
    )


# Suppress unused-import lint when treating this file as a script.
_ = Any
