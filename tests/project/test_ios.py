import plistlib
from pathlib import Path

from pythonnative.project import ios
from pythonnative.project.config import AppConfig

_BASE_PLIST = {
    "UIApplicationSceneManifest": {"UIApplicationSupportsMultipleScenes": False},
}


def _config(tmp_path: Path, **overrides: object) -> AppConfig:
    data: dict = {"app": {"id": "com.acme.cool", "name": "cool", "display_name": "Cool App"}}
    data.update(overrides)
    return AppConfig.from_dict(data, project_root=tmp_path)


def _write_plist(tmp_path: Path) -> Path:
    path = tmp_path / "Info.plist"
    with open(path, "wb") as handle:
        plistlib.dump(dict(_BASE_PLIST), handle)
    return path


def test_info_plist_identity_and_orientation(tmp_path: Path) -> None:
    plist_path = _write_plist(tmp_path)
    cfg = _config(
        tmp_path, app={"id": "com.acme.cool", "name": "cool", "display_name": "Cool App", "orientation": "all"}
    )
    ios.configure_info_plist(plist_path, cfg)
    plist = plistlib.loads(plist_path.read_bytes())
    assert plist["CFBundleDisplayName"] == "Cool App"
    assert plist["CFBundleName"] == "cool"
    assert "UIInterfaceOrientationPortrait" in plist["UISupportedInterfaceOrientations"]
    assert "UIInterfaceOrientationLandscapeLeft" in plist["UISupportedInterfaceOrientations"]
    # Base scene manifest is preserved.
    assert "UIApplicationSceneManifest" in plist


def test_info_plist_permissions(tmp_path: Path) -> None:
    plist_path = _write_plist(tmp_path)
    cfg = _config(tmp_path, permissions={"camera": "Scan", "location_always": "Track", "notifications": True})
    ios.configure_info_plist(plist_path, cfg)
    plist = plistlib.loads(plist_path.read_bytes())
    assert plist["NSCameraUsageDescription"] == "Scan"
    assert plist["NSLocationAlwaysAndWhenInUseUsageDescription"] == "Track"
    assert "location" in plist["UIBackgroundModes"]
    # notifications need no usage string on iOS
    assert "NSNotifications" not in plist


def test_info_plist_extra_keys(tmp_path: Path) -> None:
    plist_path = _write_plist(tmp_path)
    cfg = _config(tmp_path, ios={"extra_info_plist": {"ITSAppUsesNonExemptEncryption": False}})
    ios.configure_info_plist(plist_path, cfg)
    plist = plistlib.loads(plist_path.read_bytes())
    assert plist["ITSAppUsesNonExemptEncryption"] is False


def test_build_settings(tmp_path: Path) -> None:
    cfg = _config(
        tmp_path,
        app={"id": "com.acme.cool", "name": "cool", "version": "4.2.0", "build": 11, "orientation": "portrait"},
        ios={"deployment_target": "16.0", "development_team": "TEAM99", "bundle_id": "com.acme.cool.app"},
    )
    settings = ios.build_settings(cfg)
    assert "PRODUCT_BUNDLE_IDENTIFIER=com.acme.cool.app" in settings
    assert "MARKETING_VERSION=4.2.0" in settings
    assert "CURRENT_PROJECT_VERSION=11" in settings
    assert "IPHONEOS_DEPLOYMENT_TARGET=16.0" in settings
    assert "DEVELOPMENT_TEAM=TEAM99" in settings
    assert any("UISupportedInterfaceOrientations_iPhone=UIInterfaceOrientationPortrait" in s for s in settings)


def test_build_settings_no_team_omits_it(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    assert not any(s.startswith("DEVELOPMENT_TEAM=") for s in ios.build_settings(cfg))


def test_export_options_app_store(tmp_path: Path) -> None:
    cfg = _config(
        tmp_path,
        ios={"development_team": "TEAM99", "signing": {"export_method": "app-store"}},
    )
    dest = ios.write_export_options(cfg, tmp_path / "export.plist")
    options = plistlib.loads(dest.read_bytes())
    assert options["method"] == "app-store"
    assert options["teamID"] == "TEAM99"
    assert options["signingStyle"] == "automatic"


def test_export_options_manual_with_profile(tmp_path: Path) -> None:
    cfg = _config(
        tmp_path,
        ios={"signing": {"export_method": "ad-hoc", "provisioning_profile": "My Profile"}},
    )
    dest = ios.write_export_options(cfg, tmp_path / "export.plist")
    options = plistlib.loads(dest.read_bytes())
    assert options["method"] == "ad-hoc"
    assert options["signingStyle"] == "manual"
    assert options["provisioningProfiles"] == {"com.acme.cool": "My Profile"}


def test_export_options_upload_destination(tmp_path: Path) -> None:
    cfg = _config(tmp_path, ios={"signing": {"export_method": "app-store"}})
    dest = ios.write_export_options(cfg, tmp_path / "export.plist", upload=True)
    options = plistlib.loads(dest.read_bytes())
    assert options["destination"] == "upload"
    # A plain export has no destination key at all.
    dest = ios.write_export_options(cfg, tmp_path / "export2.plist")
    assert "destination" not in plistlib.loads(dest.read_bytes())


def test_info_plist_url_schemes(tmp_path: Path) -> None:
    plist_path = _write_plist(tmp_path)
    cfg = _config(
        tmp_path,
        app={"id": "com.acme.cool", "name": "cool", "url_schemes": ["coolapp", "cool-beta"]},
    )
    ios.configure_info_plist(plist_path, cfg)
    plist = plistlib.loads(plist_path.read_bytes())
    (url_type,) = plist["CFBundleURLTypes"]
    assert url_type["CFBundleURLSchemes"] == ["coolapp", "cool-beta"]
    assert url_type["CFBundleURLName"] == "com.acme.cool"


def test_write_entitlements_for_remote_notifications(tmp_path: Path) -> None:
    (tmp_path / "ios_template").mkdir()
    cfg = _config(tmp_path, permissions={"remote_notifications": True})
    dest = ios.write_entitlements(tmp_path, cfg)
    assert dest is not None
    entitlements = plistlib.loads(dest.read_bytes())
    assert entitlements["aps-environment"] == "development"
    # The build settings point code signing at the generated file.
    assert f"CODE_SIGN_ENTITLEMENTS={ios.ENTITLEMENTS_FILE}" in ios.build_settings(cfg)


def test_no_entitlements_without_capabilities(tmp_path: Path) -> None:
    cfg = _config(tmp_path, permissions={"camera": "Scan"})
    assert ios.write_entitlements(tmp_path, cfg) is None
    assert not any(s.startswith("CODE_SIGN_ENTITLEMENTS=") for s in ios.build_settings(cfg))
