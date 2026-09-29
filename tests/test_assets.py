"""Unit tests for the assets pipeline: paths, variants, manifests, fonts, and runtime lookup."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import pytest

import pythonnative as pn
from pythonnative import assets
from pythonnative.assets import (
    Asset,
    AssetManifest,
    FontParseError,
    choose_variant,
    font_faces,
    normalize_path,
    read_font_face,
    scan,
    split_variant,
    weight_from_name,
    write_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
PACIFICO = ROOT / "examples/e2e-suite/app/assets/fonts/Pacifico-Regular.ttf"


# ----------------------------------------------------------------------
# Paths and variants
# ----------------------------------------------------------------------


def test_normalize_path_accepts_relative_forms_and_rejects_escapes() -> None:
    assert normalize_path("images/logo.png") == "images/logo.png"
    assert normalize_path("./images//logo.png") == "images/logo.png"
    assert normalize_path("asset://images/logo.png") == "images/logo.png"
    assert normalize_path("images\\logo.png") == "images/logo.png"
    for bad in ("", "   ", "/etc/passwd", "../secret.txt", "images/../../x"):
        with pytest.raises(ValueError):
            normalize_path(bad)
    with pytest.raises(ValueError):
        normalize_path(3)  # type: ignore[arg-type]


def test_split_variant_and_choose_variant() -> None:
    assert split_variant("images/logo@2x.png") == ("images/logo.png", 2.0)
    assert split_variant("images/logo@1.5x.png") == ("images/logo.png", 1.5)
    assert split_variant("logo.png") == ("logo.png", 1.0)
    assert split_variant("email@work.png") == ("email@work.png", 1.0)

    variants = {1.0: "a.png", 2.0: "a@2x.png", 3.0: "a@3x.png"}
    assert choose_variant(variants, 2.0) == "a@2x.png"
    # No exact match: prefer the next denser file so it's downsampled.
    assert choose_variant(variants, 2.5) == "a@3x.png"
    assert choose_variant(variants, 1.5) == "a@2x.png"
    # Above the densest: take the densest.
    assert choose_variant(variants, 4.0) == "a@3x.png"
    assert choose_variant({}, 2.0) is None


def test_asset_value_semantics_and_wire_form() -> None:
    logo = pn.asset("./images/logo.png")
    assert logo == Asset("images/logo.png")
    assert hash(logo) == hash(Asset("images/logo.png"))
    assert logo.uri == "asset://images/logo.png"
    assert str(logo) == "asset://images/logo.png"
    assert logo.name == "logo.png"
    assert logo.suffix == ".png"
    assert logo.__native_value__() == "asset://images/logo.png"
    assert Asset.__native_schema__() == {"type": "string"}
    assert assets.is_asset_uri(logo.uri)
    assert not assets.is_asset_uri("https://example.com/x.png")


# ----------------------------------------------------------------------
# Manifest scanning
# ----------------------------------------------------------------------


def _make_assets(root: Path) -> Path:
    (root / "images").mkdir(parents=True)
    for name in ("logo.png", "logo@2x.png", "logo@3x.png", "photo.jpg"):
        (root / "images" / name).write_bytes(b"x")
    (root / "data").mkdir()
    (root / "data" / "config.json").write_text('{"a": 1}')
    (root / "data" / ".hidden").write_text("skip")
    (root / "data" / "notes.txt~").write_text("skip")
    (root / "fonts").mkdir()
    (root / "fonts" / "Pacifico-Regular.ttf").write_bytes(PACIFICO.read_bytes())
    (root / "fonts" / "broken.otf").write_bytes(b"not a font")
    return root


def test_scan_groups_variants_lists_files_and_parses_fonts(tmp_path: Path) -> None:
    root = _make_assets(tmp_path / "assets")
    warnings: list[str] = []
    manifest = scan(root, log=warnings.append)

    assert manifest.files == (
        "data/config.json",
        "fonts/Pacifico-Regular.ttf",
        "fonts/broken.otf",
        "images/logo.png",
        "images/logo@2x.png",
        "images/logo@3x.png",
        "images/photo.jpg",
    )
    assert manifest.variants["images/logo.png"] == {
        "1": "images/logo.png",
        "2": "images/logo@2x.png",
        "3": "images/logo@3x.png",
    }
    # Images without variants still get a one-entry group so lookup is one dict hit.
    assert manifest.variants["images/photo.jpg"] == {"1": "images/photo.jpg"}
    assert "data/config.json" not in manifest.variants

    assert manifest.resolve("images/logo.png", 2.0) == "images/logo@2x.png"
    assert manifest.resolve("asset://images/logo@2x.png", 3.0) == "images/logo@3x.png"
    assert manifest.resolve("data/config.json") == "data/config.json"
    assert manifest.resolve("missing.png") is None

    assert [face.family for face in manifest.fonts] == ["Pacifico"]
    assert manifest.faces("pacifico")[0].path == "fonts/Pacifico-Regular.ttf"
    assert warnings and "broken.otf" in warnings[0]


def test_write_manifest_round_trips_and_is_not_listed_as_an_asset(tmp_path: Path) -> None:
    root = _make_assets(tmp_path / "assets")
    written = write_manifest(root)
    data = json.loads((root / assets.MANIFEST_NAME).read_text())
    assert data["version"] == 1
    restored = AssetManifest.from_dict(data)
    assert restored == written
    # A second scan doesn't pick the manifest up as an asset.
    assert assets.MANIFEST_NAME not in scan(root).files


def test_scan_of_missing_directory_is_empty(tmp_path: Path) -> None:
    manifest = scan(tmp_path / "nope")
    assert manifest == AssetManifest()
    # write_manifest creates the directory so a bundle always carries one.
    write_manifest(tmp_path / "nope")
    assert (tmp_path / "nope" / assets.MANIFEST_NAME).is_file()


# ----------------------------------------------------------------------
# Fonts
# ----------------------------------------------------------------------


def test_read_font_face_reads_family_weight_and_style() -> None:
    face = read_font_face(PACIFICO, path="fonts/Pacifico-Regular.ttf")
    assert face.family == "Pacifico"
    assert face.weight == 400
    assert face.italic is False
    assert face.postscript_name == "Pacifico-Regular"
    assert face.path == "fonts/Pacifico-Regular.ttf"
    # Bytes work too, and the path defaults to the file name for paths.
    assert read_font_face(PACIFICO.read_bytes()).family == "Pacifico"
    assert read_font_face(PACIFICO).path == "Pacifico-Regular.ttf"


def test_read_font_face_rejects_non_fonts() -> None:
    with pytest.raises(FontParseError):
        read_font_face(b"definitely not a font file")


def test_weight_from_name_prefers_longer_words() -> None:
    assert weight_from_name("Semi Bold Italic") == 600
    assert weight_from_name("ExtraBold") == 800
    assert weight_from_name("Bold") == 700
    assert weight_from_name("Light") == 300
    assert weight_from_name("Regular") == 400
    assert weight_from_name("Italic") is None


# ----------------------------------------------------------------------
# Runtime roots and reads
# ----------------------------------------------------------------------


def test_assets_read_from_an_override_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _make_assets(tmp_path / "assets")
    monkeypatch.setenv("PN_ASSETS_ROOT", str(root))
    assert root in assets.assets_roots()
    assert pn.asset("data/config.json").exists()
    assert pn.asset("data/config.json").read_text() == '{"a": 1}'
    assert json.loads(pn.asset("data/config.json").read_bytes()) == {"a": 1}
    assert not pn.asset("data/missing.json").exists()
    with pytest.raises(FileNotFoundError):
        pn.asset("data/missing.json").read_bytes()
    assert [face.family for face in font_faces()] == ["Pacifico"]


class _FakeAssetsModule:
    """Stands in for the native ``Assets`` module (what Android answers with)."""

    def __init__(self, manifest: AssetManifest, files: dict[str, bytes]) -> None:
        self.files = dict(files)
        self.files[assets.MANIFEST_NAME] = manifest.dumps().encode()
        self.calls: list[tuple[str, Any]] = []

    def call(self, method: str, **args: Any) -> Any:
        self.calls.append((method, args))
        path = args["path"]
        if method == "exists":
            return path in self.files
        if method == "read":
            from pythonnative.native_modules.registry import NativeModuleError

            if path not in self.files:
                raise NativeModuleError("Assets", "read", f"asset not found: {path}", "not_found")
            return base64.b64encode(self.files[path]).decode()
        raise AssertionError(method)


def test_font_faces_and_reads_fall_back_to_the_native_manifest(monkeypatch: pytest.MonkeyPatch) -> None:
    """On Android the bundle isn't a directory, so fonts come from the manifest via the bridge."""
    manifest = scan(PACIFICO.parents[1])
    fake = _FakeAssetsModule(manifest, {"data/config.json": b'{"native": true}'})

    monkeypatch.setattr("pythonnative.bridge.has_transport", lambda: True)
    monkeypatch.setattr("pythonnative.native_modules.registry.native_module", lambda name: fake)
    monkeypatch.setattr(assets, "_bundled_roots", lambda *, exclude: [])
    monkeypatch.delenv("PN_ASSETS_ROOT", raising=False)

    faces = font_faces()
    assert [face.family for face in faces] == ["Pacifico"]
    assert faces[0].postscript_name == "Pacifico-Regular"
    assert ("read", {"path": assets.MANIFEST_NAME}) in fake.calls

    assert pn.asset("data/config.json").exists()
    assert pn.asset("data/config.json").read_text() == '{"native": true}'
    assert not pn.asset("nope.json").exists()
    with pytest.raises(FileNotFoundError):
        pn.asset("nope.json").read_bytes()


def test_font_faces_is_empty_without_roots_or_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pythonnative.bridge.has_transport", lambda: False)
    monkeypatch.setattr(assets, "_bundled_roots", lambda *, exclude: [])
    monkeypatch.delenv("PN_ASSETS_ROOT", raising=False)
    assert font_faces() == ()
