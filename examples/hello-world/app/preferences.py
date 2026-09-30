"""The appearance setting: saved on the device and shared through context.

``App`` owns the setting (so it's loaded and applied at launch, before
anyone opens the Settings tab) and provides it through
``AppearanceContext``; the Settings tab reads and changes it with
``pn.use_context(AppearanceContext)``.
"""

from collections.abc import Callable
from typing import Literal, NamedTuple

import pythonnative as pn

Appearance = Literal["system", "light", "dark"]
APPEARANCES: tuple[Appearance, ...] = ("system", "light", "dark")


class AppearanceSetting(NamedTuple):
    value: Appearance
    set: Callable[[Appearance], None]


def _ignore(_: Appearance) -> None:
    """Default setter for components rendered outside ``App`` (tests, previews of one screen)."""


AppearanceContext = pn.create_context(AppearanceSetting("system", _ignore), name="Appearance")


def use_saved_appearance() -> AppearanceSetting:
    """Load the saved appearance and apply it as the app-wide color scheme.

    ``pn.ThemeProvider`` follows the effective color scheme, so the
    override switches every themed style and the navigation bars at once.
    """
    initial: Appearance = "system"
    appearance, set_appearance = pn.use_persisted_state("settings.appearance", initial)

    def apply() -> None:
        pn.appearance.set_color_scheme(None if appearance == "system" else appearance)

    pn.use_effect(apply, [appearance])
    return AppearanceSetting(appearance, set_appearance)
