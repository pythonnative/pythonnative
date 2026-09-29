"""Unit tests for platform_metrics: dimensions, keyboard, subscribers."""

from __future__ import annotations

from typing import Generator

import pytest

from pythonnative import platform_metrics as pm


@pytest.fixture(autouse=True)
def _reset() -> Generator[None, None, None]:
    pm.reset_safe_area_insets()
    pm.reset_window_dimensions()
    pm.reset_screen_dimensions()
    pm.reset_keyboard_height()
    yield
    pm.reset_safe_area_insets()
    pm.reset_window_dimensions()
    pm.reset_screen_dimensions()
    pm.reset_keyboard_height()


# ======================================================================
# Window dimensions
# ======================================================================


def test_window_dimensions_default_zero() -> None:
    dims = pm.get_window_dimensions()
    assert dims.width == 0.0
    assert dims.height == 0.0


def test_set_window_dimensions_clamps_negative() -> None:
    pm.set_window_dimensions(-1.0, -2.0)
    dims = pm.get_window_dimensions()
    assert dims.width == 0.0
    assert dims.height == 0.0


def test_set_window_dimensions_updates() -> None:
    pm.set_window_dimensions(390.0, 844.0)
    dims = pm.get_window_dimensions()
    assert dims.width == 390.0
    assert dims.height == 844.0


def test_window_dimensions_default_density() -> None:
    dims = pm.get_window_dimensions()
    assert dims.scale == 1.0
    assert dims.font_scale == 1.0
    assert dims == pm.WindowDimensions(0.0, 0.0)


def test_set_window_dimensions_records_scale_and_font_scale() -> None:
    pm.set_window_dimensions(390.0, 844.0, scale=3.0, font_scale=1.3)
    dims = pm.get_window_dimensions()
    assert (dims.scale, dims.font_scale) == (3.0, 1.3)


def test_set_window_dimensions_keeps_density_when_omitted() -> None:
    pm.set_window_dimensions(390.0, 844.0, scale=2.0, font_scale=1.5)
    pm.set_window_dimensions(844.0, 390.0)
    dims = pm.get_window_dimensions()
    assert (dims.width, dims.height, dims.scale, dims.font_scale) == (844.0, 390.0, 2.0, 1.5)


def test_set_window_dimensions_treats_zero_density_as_one() -> None:
    pm.set_window_dimensions(390.0, 844.0, scale=0, font_scale=-1)
    dims = pm.get_window_dimensions()
    assert (dims.scale, dims.font_scale) == (1.0, 1.0)


def test_reset_window_dimensions_clears_density() -> None:
    pm.set_window_dimensions(390.0, 844.0, scale=3.0, font_scale=2.0)
    pm.reset_window_dimensions()
    assert pm.get_window_dimensions() == pm.WindowDimensions(0.0, 0.0, 1.0, 1.0)


# ======================================================================
# Screen dimensions
# ======================================================================


def test_screen_dimensions_fall_back_to_window_until_published() -> None:
    assert pm.get_screen_dimensions() == pm.WindowDimensions(0.0, 0.0)
    pm.set_window_dimensions(390.0, 700.0, scale=2.0)
    assert pm.get_screen_dimensions() == pm.get_window_dimensions()
    pm.set_screen_dimensions(390.0, 844.0, scale=2.0)
    assert pm.get_screen_dimensions().height == 844.0
    assert pm.get_window_dimensions().height == 700.0


def test_set_screen_dimensions_notifies_and_dedupes() -> None:
    received: list = []
    pm.subscribe(lambda: received.append("tick"))
    pm.set_screen_dimensions(390.0, 844.0)
    pm.set_screen_dimensions(390.0, 844.0)
    assert received == ["tick"]
    pm.set_screen_dimensions(390.0, 844.0, font_scale=1.2)
    assert received == ["tick", "tick"]
    pm.reset_screen_dimensions()
    assert pm.get_screen_dimensions() == pm.WindowDimensions(0.0, 0.0)


# ======================================================================
# Keyboard height
# ======================================================================


def test_keyboard_height_default_zero() -> None:
    assert pm.get_keyboard_height() == 0.0


def test_keyboard_height_clamps_negative() -> None:
    pm.set_keyboard_height(-50.0)
    assert pm.get_keyboard_height() == 0.0


def test_keyboard_height_updates() -> None:
    pm.set_keyboard_height(280.0)
    assert pm.get_keyboard_height() == 280.0


# ======================================================================
# Subscribers
# ======================================================================


def test_subscribe_fires_on_window_change() -> None:
    received: list = []
    pm.subscribe(lambda: received.append("tick"))
    pm.set_window_dimensions(100, 200)
    assert received == ["tick"]


def test_subscribe_fires_on_keyboard_change() -> None:
    received: list = []
    pm.subscribe(lambda: received.append("tick"))
    pm.set_keyboard_height(100)
    assert received == ["tick"]


def test_subscribe_fires_on_safe_area_change() -> None:
    received: list = []
    pm.subscribe(lambda: received.append("tick"))
    pm.set_safe_area_insets(top=44.0, left=0.0, bottom=34.0, right=0.0)
    assert received == ["tick"]


def test_subscribe_skips_no_op_updates() -> None:
    received: list = []
    pm.subscribe(lambda: received.append("tick"))
    pm.set_window_dimensions(100, 200)
    pm.set_window_dimensions(100, 200)  # same value
    assert received == ["tick"]


def test_unsubscribe_stops_notifications() -> None:
    received: list = []
    unsub = pm.subscribe(lambda: received.append("tick"))
    pm.set_keyboard_height(100)
    unsub()
    pm.set_keyboard_height(200)
    assert received == ["tick"]


def test_subscriber_exception_isolated() -> None:
    received: list = []

    def boom() -> None:
        raise RuntimeError("boom")

    pm.subscribe(boom)
    pm.subscribe(lambda: received.append("ok"))
    pm.set_window_dimensions(50, 60)
    assert received == ["ok"]
