"""Data screen: async components, Suspense, queries, mutations, persisted state.

Pushed onto the navigation stack from the Showcase screen. Showcases
PythonNative's async surface end-to-end without needing a network
connection: an ``async def`` component awaits its data behind a
[`Suspense`][pythonnative.Suspense] fallback, the "fetch" is simulated
with ``asyncio.sleep``, taps are counted in
[`AsyncStorage`][pythonnative.AsyncStorage] via
[`use_persisted_state`][pythonnative.use_persisted_state], and the
reset button awaits a [`pn.Alert.confirm`][pythonnative.Alert.confirm]
before wiping the saved value.
"""

import asyncio
import random
from dataclasses import dataclass

import pythonnative as pn
from app.theme import AppStyles

NAMES = ["Ada Lovelace", "Grace Hopper", "Alan Turing", "Guido van Rossum"]
QUOTES = [
    "Simple is better than complex.",
    "Errors should never pass silently.",
    "Now is better than never.",
    "Readability counts.",
    "Beautiful is better than ugly.",
]


class Styles(pn.StyleSheet):
    emphasis = pn.style(font_size=18, font_weight="600")
    count = pn.style(font_size=20, font_weight="600")
    profile = pn.style(gap=4)
    buttons = pn.style(gap=8, align_items="center")


@dataclass(frozen=True)
class Profile:
    id: int
    name: str


async def load_quote() -> str:
    """Pretend to call an API: 600ms delay, then a random quote."""
    await asyncio.sleep(0.6)
    return random.choice(QUOTES)


async def load_profile(seed: int) -> Profile:
    """Pretend to call an API that returns a tiny profile."""
    await asyncio.sleep(0.5)
    return Profile(id=seed, name=NAMES[seed % len(NAMES)])


async def save_tap_count(count: int) -> int:
    """Pretend to call an API that confirms the save and returns the new total."""
    await asyncio.sleep(0.3)
    return count


@pn.component
def QuoteCard() -> pn.Node:
    """Loads a quote on mount and lets the user refetch."""
    styles = pn.use_styles(AppStyles)
    quote = pn.use_query(load_quote, [])

    if quote.loading and quote.data is None:
        body = pn.Text("Loading…", style=styles.hint)
    elif quote.error is not None:
        body = pn.Text(f"Error: {quote.error}", style=styles.hint)
    else:
        body = pn.Text(quote.data or "", style=[styles.body, Styles.emphasis])

    return pn.View(
        pn.Text("From an async source", style=styles.section_title),
        body,
        pn.Button("Refreshing…" if quote.loading else "Refresh", on_press=quote.refetch),
        style=styles.warm_card,
    )


@pn.component
async def ProfileCard(seed: int = 0) -> pn.Node:
    """An ``async def`` component: it awaits its data, then returns its tree.

    While the await is pending the nearest [`Suspense`][pythonnative.Suspense]
    ancestor shows its fallback; no loading-state bookkeeping needed here.
    """
    styles = pn.use_styles(AppStyles)
    profile: Profile = await pn.use_resource(lambda: load_profile(seed), [seed])
    return pn.View(
        pn.Text(profile.name, style=[styles.body, Styles.emphasis]),
        pn.Text(f"Profile #{profile.id}", style=styles.hint),
        style=Styles.profile,
    )


@pn.component
def SuspenseCard() -> pn.Node:
    """Wraps the async ProfileCard in a Suspense boundary with a fallback."""
    styles = pn.use_styles(AppStyles)
    seed, set_seed = pn.use_state(0)

    return pn.View(
        pn.Text("Async component + Suspense", style=styles.section_title),
        pn.Suspense(
            ProfileCard(seed=seed),
            fallback=pn.Text("Loading profile…", style=styles.hint),
        ),
        pn.Button("Next profile", on_press=lambda: set_seed(seed + 1)),
        style=styles.warm_card,
    )


@pn.component
def TapCounter() -> pn.Node:
    """A persisted counter with an awaitable confirm-clear flow."""
    styles = pn.use_styles(AppStyles)
    count, set_count = pn.use_persisted_state("data_demo.taps", 0)
    mutation, save = pn.use_mutation(save_tap_count)

    def tap() -> None:
        set_count(count + 1)
        save(count + 1)

    # Handlers may be ``async``: the framework runs the coroutine and
    # cancels it if this component unmounts first.
    async def reset() -> None:
        if await pn.Alert.confirm(
            "Reset counter?",
            message="This will clear the saved tap total.",
            confirm_label="Reset",
            cancel_label="Keep",
        ):
            set_count(0)
            save(0)

    return pn.View(
        pn.Text("Persisted counter", style=styles.section_title),
        pn.Text(f"Taps so far: {count}", style=[styles.body, Styles.count]),
        pn.Text("Confirming save…" if mutation.loading else "Saved.", style=styles.hint),
        pn.Row(
            pn.Button("Tap me", on_press=tap),
            pn.Button("Reset", on_press=reset),
            style=Styles.buttons,
        ),
        style=[styles.card, {"align_items": "center"}],
    )


@pn.component
def DataScreen() -> pn.Node:
    """The full data-demo screen."""
    nav = pn.use_navigation()
    styles = pn.use_styles(AppStyles)

    return pn.ScrollView(
        pn.Column(
            pn.Text("Async demo", style=styles.title),
            pn.Text(
                "Demonstrates async components with Suspense, use_query, "
                "use_mutation, use_persisted_state, and awaitable pn.Alert.confirm.",
                style=styles.hint,
            ),
            SuspenseCard(),
            QuoteCard(),
            TapCounter(),
            pn.Button("Back", on_press=nav.go_back),
            style=styles.section,
        )
    )
