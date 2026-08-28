import sys
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

from pythonnative.project.config import (
    AppConfig,
    ConfigError,
    entrypoint_to_module,
    render_default_toml,
)


def _minimal(**app: object) -> dict:
    base: dict = {"id": "com.example.app", "name": "app"}
    base.update(app)
    return {"app": base}


def test_minimal_config_defaults() -> None:
    cfg = AppConfig.from_dict(_minimal())
    assert cfg.app_id == "com.example.app"
    assert cfg.display_name == "app"  # falls back to name
    assert cfg.version == "1.0.0"
    assert cfg.build == 1
    assert cfg.python_version == "3.11"
    assert cfg.orientation == "portrait"
    assert cfg.entry_point == "app/main.py"
    assert cfg.entry_module == "app.main"
    assert cfg.application_id == "com.example.app"
    assert cfg.bundle_id == "com.example.app"
    assert cfg.android_package_path == "com/example/app"
    assert cfg.url_schemes == []
    # 64-bit only by default; 32-bit ABIs are opt-in.
    assert cfg.android.abi_filters == ["arm64-v8a", "x86_64"]


def test_url_schemes_parsing_and_validation() -> None:
    cfg = AppConfig.from_dict(_minimal(url_schemes=["coolapp", "cool-beta"]))
    assert cfg.url_schemes == ["coolapp", "cool-beta"]

    with pytest.raises(ConfigError, match="url_schemes"):
        AppConfig.from_dict(_minimal(url_schemes=["9bad"]))
    with pytest.raises(ConfigError, match="url_schemes"):
        AppConfig.from_dict(_minimal(url_schemes=["has space"]))


def test_full_config_parsing() -> None:
    data = {
        "app": {
            "id": "com.acme.cool",
            "name": "cool",
            "display_name": "Cool App",
            "version": "2.5.0",
            "build": 9,
            "python_version": "3.12",
            "orientation": "landscape",
            "entry_point": "src/start.py",
        },
        "permissions": {"camera": "Reason", "notifications": True},
        "assets": {"icon": "a/icon.png", "splash": "a/splash.png"},
        "requirements": {"packages": ["httpx", "humanize"]},
        "ios": {
            "deployment_target": "15.0",
            "development_team": "TEAM12",
            "bundle_id": "com.acme.cool.ios",
            "signing": {"export_method": "app-store", "provisioning_profile": "Prof"},
        },
        "android": {
            "min_sdk": 26,
            "target_sdk": 33,
            "compile_sdk": 34,
            "application_id": "com.acme.cool.droid",
            "abi_filters": ["arm64-v8a"],
            "permissions": ["android.permission.FOO"],
            "signing": {"keystore": "r.keystore", "key_alias": "k"},
        },
    }
    cfg = AppConfig.from_dict(data)
    assert cfg.display_name == "Cool App"
    assert cfg.version == "2.5.0"
    assert cfg.python_version == "3.12"
    assert cfg.orientation == "landscape"
    assert cfg.entry_module == "src.start"
    assert cfg.bundle_id == "com.acme.cool.ios"
    assert cfg.application_id == "com.acme.cool.droid"
    assert cfg.requirements == ["httpx", "humanize"]
    assert cfg.icon == "a/icon.png"
    assert cfg.ios.signing.export_method == "app-store"
    assert cfg.ios.signing.provisioning_profile == "Prof"
    assert cfg.android.abi_filters == ["arm64-v8a"]
    assert cfg.android.signing.is_configured
    assert "android.permission.FOO" in cfg.resolved_permissions().android_permissions


@pytest.mark.parametrize(
    "app, message",
    [
        ({"id": "nodots", "name": "x"}, "reverse-DNS"),
        ({"id": "com.example.9bad", "name": "x"}, "segment"),
        ({"id": "com.class.app", "name": "x"}, "reserved word"),
        ({"id": "com.example.app", "name": ""}, "non-empty"),
        ({"id": "com.example.app", "name": "x", "version": "v1"}, "dotted number"),
        ({"id": "com.example.app", "name": "x", "build": 0}, "positive"),
        ({"id": "com.example.app", "name": "x", "python_version": "2.7"}, "unsupported"),
        ({"id": "com.example.app", "name": "x", "orientation": "sideways"}, "invalid"),
    ],
)
def test_app_validation_errors(app: dict, message: str) -> None:
    with pytest.raises(ConfigError) as exc:
        AppConfig.from_dict({"app": app})
    assert message in str(exc.value)


def test_unknown_permission_rejected() -> None:
    with pytest.raises(ConfigError) as exc:
        AppConfig.from_dict({"app": {"id": "com.example.app", "name": "x"}, "permissions": {"telepathy": True}})
    assert "Unknown permission" in str(exc.value)


def test_requirements_reject_pythonnative() -> None:
    with pytest.raises(ConfigError) as exc:
        AppConfig.from_dict(
            {"app": {"id": "com.example.app", "name": "x"}, "requirements": {"packages": ["pythonnative>=1"]}}
        )
    assert "pythonnative" in str(exc.value)


def test_android_sdk_validation() -> None:
    with pytest.raises(ConfigError):
        AppConfig.from_dict({"app": {"id": "com.example.app", "name": "x"}, "android": {"min_sdk": 18}})
    with pytest.raises(ConfigError):
        AppConfig.from_dict(
            {"app": {"id": "com.example.app", "name": "x"}, "android": {"min_sdk": 30, "target_sdk": 24}}
        )


def test_ios_export_method_validation() -> None:
    with pytest.raises(ConfigError):
        AppConfig.from_dict(
            {"app": {"id": "com.example.app", "name": "x"}, "ios": {"signing": {"export_method": "carrier-pigeon"}}}
        )


def test_missing_app_table() -> None:
    with pytest.raises(ConfigError) as exc:
        AppConfig.from_dict({})
    assert "[app]" in str(exc.value)


def test_wrong_types() -> None:
    with pytest.raises(ConfigError):
        AppConfig.from_dict({"app": {"id": "com.example.app", "name": "x", "build": "five"}})
    with pytest.raises(ConfigError):
        AppConfig.from_dict({"app": {"id": "com.example.app", "name": "x"}, "requirements": {"packages": "httpx"}})


def test_entrypoint_to_module() -> None:
    assert entrypoint_to_module("app/main.py") == "app.main"
    assert entrypoint_to_module("src/pkg/start.py") == "src.pkg.start"
    assert entrypoint_to_module("") == "app.main"
    assert entrypoint_to_module("app\\main.py") == "app.main"


def test_load_from_disk(tmp_path: Path) -> None:
    (tmp_path / "pythonnative.toml").write_text(
        render_default_toml(name="demo", app_id="com.example.demo"), encoding="utf-8"
    )
    cfg = AppConfig.load(tmp_path)
    assert cfg.app_id == "com.example.demo"
    assert cfg.project_root == tmp_path
    assert cfg.resolve_path("assets/icon.png") == (tmp_path / "assets/icon.png").resolve()


def test_load_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as exc:
        AppConfig.load(tmp_path)
    assert "No pythonnative.toml" in str(exc.value)


def test_rendered_default_toml_parses_and_loads() -> None:
    text = render_default_toml(name="my_app", app_id="com.example.my_app")
    data = tomllib.loads(text)
    cfg = AppConfig.from_dict(data)
    assert cfg.app_id == "com.example.my_app"
    assert cfg.display_name == "My App"
    assert cfg.requirements == []
