"""Demo screen for [`pythonnative.push`][pythonnative.push].

The suite has no Firebase project or APNs credentials, so this shows what an
unconfigured build does: on Android ``get_device_token`` raises with the code
``not_configured`` and the app keeps running, and a simulator's APNs answer, a
token or an error, is reported either way. Real delivery needs a device and a
server, as the guide explains.
"""

from __future__ import annotations

from typing import Callable

from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText

import pythonnative as pn
from pythonnative.native_modules.registry import NativeModuleError
from pythonnative.push import Push, PushMessage


@pn.component
def PushDemo() -> pn.Node:
    """Render the token request and message count."""
    token, set_token = pn.use_state("not requested")
    messages, set_messages = pn.use_state(0)

    def subscribe() -> Callable[[], None]:
        def on_message(_: PushMessage) -> None:
            set_messages(lambda count: count + 1)

        return Push.on_message(on_message)

    pn.use_effect(subscribe, [])

    async def request() -> None:
        try:
            value = await Push.get_device_token()
            set_token("received" if value else "none")
        except NativeModuleError as error:
            set_token(str(error.code))

    return DemoScreen(
        "Push",
        "Push.get_device_token and on_message, without credentials.",
        DemoSection(
            "Registration",
            pn.Button("Get device token", on_press=lambda: pn.run_async(request())),
            ResultText("Token", token),
            ResultText("Messages", messages),
            Hint("With no google-services.json, Android reports not_configured."),
        ),
    )
