"""Fallback behavior of asset generation when Pillow isn't installed.

Unlike ``test_icons.py``, these tests don't import Pillow and don't skip
when it's present: ``pillow_available`` is patched to report it missing.
"""

from pathlib import Path
from typing import Any, Callable

import pytest

from pythonnative.project import icons


@pytest.fixture(autouse=True)
def no_pillow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(icons, "pillow_available", lambda: False)

    def fail_open(source: Path) -> Any:
        raise AssertionError(f"_open_rgba must not be called without Pillow: {source}")

    monkeypatch.setattr(icons, "_open_rgba", fail_open)


def test_generate_ios_icons_returns_false_and_leaves_output_absent(tmp_path: Path) -> None:
    appiconset = tmp_path / "AppIcon.appiconset"
    assert icons.generate_ios_icons(tmp_path / "missing.png", appiconset) is False
    assert not appiconset.exists()


def test_generate_ios_icons_keeps_existing_assets(tmp_path: Path) -> None:
    appiconset = tmp_path / "AppIcon.appiconset"
    appiconset.mkdir()
    sentinel = appiconset / "icon-1024.png"
    sentinel.write_bytes(b"template-icon")

    assert icons.generate_ios_icons(tmp_path / "missing.png", appiconset) is False
    assert sentinel.read_bytes() == b"template-icon"
    assert [p.name for p in appiconset.iterdir()] == ["icon-1024.png"]


def test_generate_android_icons_returns_false_and_leaves_output_absent(tmp_path: Path) -> None:
    res = tmp_path / "res"
    assert icons.generate_android_icons(tmp_path / "missing.png", res) is False
    assert not res.exists()


def test_generate_android_icons_keeps_adaptive_icon_and_mipmaps(tmp_path: Path) -> None:
    res = tmp_path / "res"
    anydpi = res / "mipmap-anydpi-v26"
    anydpi.mkdir(parents=True)
    adaptive = anydpi / "ic_launcher.xml"
    adaptive.write_bytes(b"<adaptive/>")
    mipmap = res / "mipmap-mdpi"
    mipmap.mkdir()
    launcher = mipmap / "ic_launcher.png"
    launcher.write_bytes(b"template-launcher")

    assert icons.generate_android_icons(tmp_path / "missing.png", res) is False
    assert adaptive.read_bytes() == b"<adaptive/>"
    assert launcher.read_bytes() == b"template-launcher"
    assert not (mipmap / "ic_launcher_round.png").exists()
    assert not (res / "mipmap-hdpi").exists()


def test_generate_ios_splash_returns_false_and_leaves_output_absent(tmp_path: Path) -> None:
    imageset = tmp_path / "Splash.imageset"
    assert icons.generate_ios_splash(tmp_path / "missing.png", imageset) is False
    assert not imageset.exists()


def test_generate_ios_splash_keeps_existing_assets(tmp_path: Path) -> None:
    imageset = tmp_path / "Splash.imageset"
    imageset.mkdir()
    sentinel = imageset / "splash.png"
    sentinel.write_bytes(b"template-splash")

    assert icons.generate_ios_splash(tmp_path / "missing.png", imageset) is False
    assert sentinel.read_bytes() == b"template-splash"
    assert [p.name for p in imageset.iterdir()] == ["splash.png"]


def test_generate_android_splash_icon_returns_false_and_leaves_output_absent(tmp_path: Path) -> None:
    dest = tmp_path / "drawable" / "splash_icon.png"
    assert icons.generate_android_splash_icon(tmp_path / "missing.png", dest) is False
    assert not dest.parent.exists()


def test_generate_android_splash_icon_keeps_existing_file(tmp_path: Path) -> None:
    dest = tmp_path / "splash_icon.png"
    dest.write_bytes(b"template-splash-icon")

    assert icons.generate_android_splash_icon(tmp_path / "missing.png", dest, size=64) is False
    assert dest.read_bytes() == b"template-splash-icon"


def test_dominant_background_color_returns_none(tmp_path: Path) -> None:
    assert icons.dominant_background_color(tmp_path / "missing.png") is None


@pytest.mark.parametrize(
    "generate",
    [
        icons.generate_ios_icons,
        icons.generate_android_icons,
        icons.generate_ios_splash,
        icons.generate_android_splash_icon,
    ],
)
def test_generators_never_open_the_source(generate: Callable[[Path, Path], bool], tmp_path: Path) -> None:
    # The autouse fixture makes _open_rgba raise if the fallback reaches it.
    assert generate(tmp_path / "missing.png", tmp_path / "out") is False
