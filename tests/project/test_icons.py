import json
from pathlib import Path

import pytest

from pythonnative.project import icons

pytestmark = pytest.mark.skipif(not icons.pillow_available(), reason="Pillow not installed")


@pytest.fixture
def source_icon(tmp_path: Path) -> Path:
    from PIL import Image

    path = tmp_path / "icon.png"
    Image.new("RGBA", (512, 512), (12, 34, 56, 255)).save(path)
    return path


def test_generate_ios_icons(source_icon: Path, tmp_path: Path) -> None:
    appiconset = tmp_path / "AppIcon.appiconset"
    assert icons.generate_ios_icons(source_icon, appiconset) is True
    icon = appiconset / "icon-1024.png"
    assert icon.is_file()
    contents = json.loads((appiconset / "Contents.json").read_text())
    assert contents["images"][0]["filename"] == "icon-1024.png"

    from PIL import Image

    rendered = Image.open(icon)
    assert rendered.size == (1024, 1024)
    assert rendered.mode == "RGB"  # alpha flattened for App Store


def test_generate_android_icons(source_icon: Path, tmp_path: Path) -> None:
    res = tmp_path / "res"
    (res / "mipmap-anydpi-v26").mkdir(parents=True)
    (res / "mipmap-anydpi-v26" / "ic_launcher.xml").write_text("<adaptive/>", encoding="utf-8")

    assert icons.generate_android_icons(source_icon, res) is True
    from PIL import Image

    for density, size in icons.ANDROID_LAUNCHER_DENSITIES.items():
        launcher = res / f"mipmap-{density}" / "ic_launcher.png"
        assert launcher.is_file()
        assert Image.open(launcher).size == (size, size)
        assert (res / f"mipmap-{density}" / "ic_launcher_round.png").is_file()
    # Adaptive XML removed so raster icons are authoritative.
    assert not (res / "mipmap-anydpi-v26").exists()


def test_generate_ios_splash(source_icon: Path, tmp_path: Path) -> None:
    imageset = tmp_path / "Splash.imageset"
    assert icons.generate_ios_splash(source_icon, imageset) is True
    assert (imageset / "splash.png").is_file()
    contents = json.loads((imageset / "Contents.json").read_text())
    assert contents["images"][0]["filename"] == "splash.png"


def test_dominant_background_color(tmp_path: Path) -> None:
    from PIL import Image

    path = tmp_path / "solid.png"
    Image.new("RGBA", (64, 64), (255, 0, 0, 255)).save(path)
    assert icons.dominant_background_color(path) == "#FF0000"


def test_has_source(tmp_path: Path) -> None:
    assert icons.has_source(None) is False
    assert icons.has_source(tmp_path / "missing.png") is False
    real = tmp_path / "real.png"
    real.write_bytes(b"x")
    assert icons.has_source(real) is True
