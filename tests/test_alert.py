"""Unit tests for the awaitable Alert API."""

from __future__ import annotations

import asyncio
from typing import Generator

import pytest

from pythonnative.alerts import Alert
from pythonnative.platform import _set_platform_for_test


@pytest.fixture(autouse=True)
def _reset() -> Generator[None, None, None]:
    Alert._test_log.clear()
    Alert._test_responses.clear()
    yield
    Alert._test_log.clear()
    Alert._test_responses.clear()
    _set_platform_for_test(None)


def test_show_is_fire_and_forget_with_default_button() -> None:
    Alert.show("Hello", "World")
    assert len(Alert._test_log) == 1
    entry = Alert._test_log[0]
    assert entry["title"] == "Hello"
    assert entry["message"] == "World"
    assert entry["style"] == "alert"
    assert entry["buttons"] == [{"label": "OK", "style": "default"}]


def test_show_with_custom_button_label() -> None:
    Alert.show("Saved!", button="Sweet")
    assert Alert._test_log[0]["buttons"] == [{"label": "Sweet", "style": "default"}]


def test_confirm_returns_true_when_confirm_pressed() -> None:
    Alert.set_test_response(1)
    result = asyncio.run(Alert.confirm("Save?"))
    assert result is True
    entry = Alert._test_log[0]
    assert entry["title"] == "Save?"
    assert entry["buttons"] == [
        {"label": "Cancel", "style": "cancel"},
        {"label": "OK", "style": "default"},
    ]


def test_confirm_returns_false_on_cancel() -> None:
    Alert.set_test_response(0)
    result = asyncio.run(Alert.confirm("Save?"))
    assert result is False


def test_confirm_returns_false_on_dismiss() -> None:
    result = asyncio.run(Alert.confirm("Save?"))
    assert result is False


def test_confirm_custom_labels() -> None:
    Alert.set_test_response(1)
    asyncio.run(
        Alert.confirm(
            "Quit?",
            message="Unsaved changes will be lost.",
            confirm_label="Quit",
            cancel_label="Stay",
        )
    )
    entry = Alert._test_log[0]
    assert entry["title"] == "Quit?"
    assert entry["message"] == "Unsaved changes will be lost."
    assert entry["buttons"][0]["label"] == "Stay"
    assert entry["buttons"][1]["label"] == "Quit"


def test_choose_returns_selected_option() -> None:
    Alert.set_test_response(1)
    result = asyncio.run(Alert.choose("Pick", options=["A", "B", "C"]))
    assert result == "B"


def test_choose_with_cancel_label_returns_none_when_cancelled() -> None:
    # Buttons are [A, B, cancel]; selecting index 2 means cancel.
    Alert.set_test_response(2)
    result = asyncio.run(Alert.choose("Pick", options=["A", "B"], cancel_label="Nope"))
    assert result is None
    entry = Alert._test_log[0]
    assert entry["buttons"][-1] == {"label": "Nope", "style": "cancel"}


def test_choose_returns_none_on_dismiss() -> None:
    result = asyncio.run(Alert.choose("Pick", options=["A", "B"]))
    assert result is None


def test_choose_marks_destructive_options() -> None:
    Alert.set_test_response(1)
    asyncio.run(
        Alert.choose(
            "Pick",
            options=["Keep", "Delete"],
            destructive_labels=["Delete"],
        )
    )
    buttons = Alert._test_log[0]["buttons"]
    assert buttons[0] == {"label": "Keep", "style": "default"}
    assert buttons[1] == {"label": "Delete", "style": "destructive"}


def test_choose_raises_on_empty_options() -> None:
    with pytest.raises(ValueError):
        asyncio.run(Alert.choose("Pick", options=[]))
