"""Imperative, awaitable system alerts.

Inspired by React Native's ``Alert.alert()`` but designed around
``async`` / ``await`` instead of per-button callbacks. There are three
entry points:

- [`Alert.show`][pythonnative.alerts.Alert.show]: fire-and-forget
  one-button notice (no return value).
- [`Alert.confirm`][pythonnative.alerts.Alert.confirm]: awaitable
  two-button yes/no, resolves to a ``bool``.
- [`Alert.choose`][pythonnative.alerts.Alert.choose]: awaitable
  multi-button picker / action sheet, resolves to the selected
  label (or ``None`` if dismissed).

Example:
    ```python
    import pythonnative as pn


    async def maybe_delete():
        if await pn.Alert.confirm(
            title="Delete item?",
            message="This action cannot be undone.",
            confirm_label="Delete",
            cancel_label="Keep",
        ):
            await delete_item()
    ```
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Sequence

from .platform import Platform
from .runtime import resolve_future

# ======================================================================
# Internal dispatch helpers
# ======================================================================


def _dispatch_alert(
    *,
    title: str,
    message: Optional[str],
    buttons: List[Dict[str, Any]],
    style: str,
    on_result: Any,
) -> None:
    """Route an alert request to the active platform presenter.

    ``buttons`` is a list of ``{"label": str, "style":
    "default"|"cancel"|"destructive"}`` dicts. The presenter must
    invoke ``on_result(index)`` exactly once when the user picks a
    button, or ``on_result(-1)`` if the dialog is dismissed without a
    selection. ``on_result`` may run on any thread.
    """
    if Platform.is_ios:
        try:
            from .native_views.ios import _present_alert as _ios_present_alert

            _ios_present_alert(
                title=title,
                message=message,
                buttons=buttons,
                style=style,
                on_result=on_result,
            )
            return
        except Exception:
            on_result(-1)
            return

    if Platform.is_android:
        try:
            from .native_views.android import _present_alert as _android_present_alert

            _android_present_alert(
                title=title,
                message=message,
                buttons=buttons,
                style=style,
                on_result=on_result,
            )
            return
        except Exception:
            on_result(-1)
            return

    # Test backend: record the call so unit tests can assert on it,
    # then deliver the configured response.
    Alert._test_log.append(
        {
            "title": title,
            "message": message,
            "buttons": list(buttons),
            "style": style,
        }
    )
    response = Alert._next_test_response()
    on_result(response)


# ======================================================================
# Public Alert API
# ======================================================================


class Alert:
    """Imperative alert / action-sheet helper.

    All methods are static. Use [`show`][pythonnative.alerts.Alert.show]
    for a fire-and-forget single-button notice,
    [`confirm`][pythonnative.alerts.Alert.confirm] for an awaitable
    yes/no dialog, and
    [`choose`][pythonnative.alerts.Alert.choose] for a multi-option
    picker.
    """

    #: Records every alert call when running off-device. Tests reset
    #: this between cases via ``Alert._test_log.clear()``. Each entry
    #: contains ``title``, ``message``, ``buttons``, and ``style``.
    _test_log: List[Dict[str, Any]] = []

    #: Queue of indices to deliver to upcoming alerts in tests. Set via
    #: [`Alert.set_test_response`][pythonnative.alerts.Alert.set_test_response].
    #: A negative value (or empty queue) simulates a dismiss.
    _test_responses: List[int] = []

    @staticmethod
    def set_test_response(*indices: int) -> None:
        """Queue indices to return from upcoming test alerts.

        Use in async tests to script the user's choices: each pending
        call to [`confirm`][pythonnative.alerts.Alert.confirm] or
        [`choose`][pythonnative.alerts.Alert.choose] pops the next
        queued index. Pass ``-1`` to simulate a dismiss.

        Args:
            *indices: Sequence of button indices to deliver, oldest
                first. Calls beyond the queue length resolve to ``-1``.
        """
        Alert._test_responses[:] = list(indices)

    @staticmethod
    def _next_test_response() -> int:
        if Alert._test_responses:
            return Alert._test_responses.pop(0)
        return -1

    @staticmethod
    def show(
        title: str,
        message: Optional[str] = None,
        *,
        button: str = "OK",
    ) -> None:
        """Display a simple, one-button alert and return immediately.

        Args:
            title: Dialog title.
            message: Optional body text.
            button: Label for the single dismiss button (default
                ``"OK"``).

        This is fire-and-forget. To know what the user did, use
        [`confirm`][pythonnative.alerts.Alert.confirm] or
        [`choose`][pythonnative.alerts.Alert.choose] and ``await``
        the result.
        """
        _dispatch_alert(
            title=title,
            message=message,
            buttons=[{"label": button, "style": "default"}],
            style="alert",
            on_result=lambda _idx: None,
        )

    @staticmethod
    async def confirm(
        title: str,
        message: Optional[str] = None,
        *,
        confirm_label: str = "OK",
        cancel_label: str = "Cancel",
    ) -> bool:
        """Present a two-button yes/no dialog and wait for the choice.

        Args:
            title: Dialog title.
            message: Optional body text.
            confirm_label: Label for the "yes" button (default
                ``"OK"``).
            cancel_label: Label for the "no" button (default
                ``"Cancel"``).

        Returns:
            ``True`` if the user pressed the confirm button, ``False``
            for the cancel button or a dismiss.

        Example:
            ```python
            if await pn.Alert.confirm("Save changes?"):
                await save()
            ```
        """
        loop = asyncio.get_running_loop()
        future: asyncio.Future[bool] = loop.create_future()

        def _on_result(index: int) -> None:
            resolve_future(future, index == 1)

        _dispatch_alert(
            title=title,
            message=message,
            buttons=[
                {"label": cancel_label, "style": "cancel"},
                {"label": confirm_label, "style": "default"},
            ],
            style="alert",
            on_result=_on_result,
        )
        return await future

    @staticmethod
    async def choose(
        title: str,
        options: Sequence[str],
        *,
        message: Optional[str] = None,
        cancel_label: Optional[str] = None,
        style: str = "action_sheet",
        destructive_labels: Sequence[str] = (),
    ) -> Optional[str]:
        """Present a multi-option picker and wait for the user's choice.

        Args:
            title: Dialog title.
            options: Sequence of option labels (in display order).
            message: Optional body text.
            cancel_label: If provided, adds a "cancel" button with
                this label. Selecting it resolves to ``None``.
            style: ``"action_sheet"`` (default) for an iOS-style
                sheet, or ``"alert"`` for a stacked alert dialog.
            destructive_labels: Labels in ``options`` that should be
                styled destructively (red on iOS).

        Returns:
            The selected label, or ``None`` if the user dismissed or
            tapped the cancel button.

        Example:
            ```python
            choice = await pn.Alert.choose(
                "Photo source",
                options=["Camera", "Gallery"],
                cancel_label="Cancel",
            )
            if choice == "Camera":
                ...
            ```
        """
        if not options:
            raise ValueError("Alert.choose requires at least one option")

        loop = asyncio.get_running_loop()
        future: asyncio.Future[Optional[str]] = loop.create_future()

        destructive = set(destructive_labels)
        buttons: List[Dict[str, Any]] = [
            {
                "label": opt,
                "style": "destructive" if opt in destructive else "default",
            }
            for opt in options
        ]
        if cancel_label is not None:
            buttons.append({"label": cancel_label, "style": "cancel"})

        def _on_result(index: int) -> None:
            if 0 <= index < len(options):
                resolve_future(future, options[index])
            else:
                resolve_future(future, None)

        _dispatch_alert(
            title=title,
            message=message,
            buttons=buttons,
            style=style,
            on_result=_on_result,
        )
        return await future


__all__ = ["Alert"]
