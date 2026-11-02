"""Demo screen for [`pythonnative.notifications`][pythonnative.notifications].

Scheduling right away, while this screen is in the foreground, reaches
``on_received``. A delayed notification can be canceled before it fires. Tapping a
notification reaches ``on_response``, though the flow doesn't tap one: the system's
shade isn't something it can reach the same way on both platforms.
"""

from __future__ import annotations

from typing import Callable, List

from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText

import pythonnative as pn
from pythonnative.native_modules.registry import NativeModuleError
from pythonnative.notifications import NotificationResponse, Notifications, ReceivedNotification


@pn.component
def NotificationsDemo() -> pn.Node:
    """Render permission, scheduling, cancellation, and event readouts."""
    permission, set_permission = pn.use_state("unknown")
    scheduled, set_scheduled = pn.use_state("none")
    received, set_received = pn.use_state(0)
    last_data, set_last_data = pn.use_state("none")
    responses, set_responses = pn.use_state(0)
    badge, set_badge = pn.use_state("not set")
    launch = pn.use_memo(Notifications.last_response, [])

    def subscribe() -> Callable[[], None]:
        def on_received(notification: ReceivedNotification) -> None:
            set_received(lambda count: count + 1)
            set_last_data(str(notification.data.get("source", "none")))

        def on_response(response: NotificationResponse) -> None:
            set_responses(lambda count: count + 1)
            set_last_data(str(response.data.get("source", "none")))

        removers: List[Callable[[], None]] = [
            Notifications.on_received(on_received),
            Notifications.on_response(on_response),
        ]

        def remove() -> None:
            for remover in removers:
                remover()

        return remove

    pn.use_effect(subscribe, [])

    async def request() -> None:
        set_permission("granted" if await Notifications.request_permission() else "denied")

    async def schedule_now() -> None:
        shown = await Notifications.schedule(
            "Demo", "Right now", identifier="demo_now", data={"source": "now"}, badge=1
        )
        set_scheduled("now" if shown else "refused")

    async def schedule_later() -> None:
        shown = await Notifications.schedule("Demo", "Later", delay_seconds=600, identifier="demo_later")
        set_scheduled("later" if shown else "refused")

    async def cancel_all() -> None:
        await Notifications.cancel_all()
        set_scheduled("canceled")

    async def apply_badge() -> None:
        try:
            await Notifications.set_badge(3)
            set_badge("set")
        except NativeModuleError as error:
            set_badge(str(error.code))

    return DemoScreen(
        "Notifications",
        "Notifications.schedule, cancel_all, set_badge, on_received, and last_response.",
        DemoSection(
            "Scheduling",
            pn.Button("Request permission", on_press=lambda: pn.run_async(request())),
            ResultText("Permission", permission),
            pn.Button("Schedule now", on_press=lambda: pn.run_async(schedule_now())),
            pn.Button("Schedule in ten minutes", on_press=lambda: pn.run_async(schedule_later())),
            pn.Button("Cancel all", on_press=lambda: pn.run_async(cancel_all())),
            ResultText("Scheduled", scheduled),
        ),
        DemoSection(
            "Events",
            ResultText("Received", received),
            ResultText("Responses", responses),
            ResultText("Last data", last_data),
            ResultText("Launched by a tap", "yes" if launch else "no"),
            pn.Button("Set badge", on_press=lambda: pn.run_async(apply_badge())),
            ResultText("Badge", badge),
            Hint("Android has no badge API, so it reports unsupported."),
        ),
    )
