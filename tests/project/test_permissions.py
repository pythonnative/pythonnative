import pytest

from pythonnative.project.permissions import (
    BASE_ANDROID_PERMISSIONS,
    CAPABILITIES,
    describe_catalog,
    resolve_permissions,
    unknown_capabilities,
)


def test_base_permissions_always_present() -> None:
    resolved = resolve_permissions({})
    for perm in BASE_ANDROID_PERMISSIONS:
        assert perm in resolved.android_permissions
    assert resolved.ios_usage_descriptions == {}


def test_camera_maps_both_platforms() -> None:
    resolved = resolve_permissions({"camera": "Scan things"})
    assert resolved.ios_usage_descriptions["NSCameraUsageDescription"] == "Scan things"
    assert "android.permission.CAMERA" in resolved.android_permissions


def test_true_uses_default_reason() -> None:
    resolved = resolve_permissions({"camera": True})
    cap = CAPABILITIES["camera"]
    assert resolved.ios_usage_descriptions["NSCameraUsageDescription"] == cap.default_reason


def test_false_disables_capability() -> None:
    resolved = resolve_permissions({"camera": False})
    assert "android.permission.CAMERA" not in resolved.android_permissions
    assert "NSCameraUsageDescription" not in resolved.ios_usage_descriptions


def test_notifications_no_reason_needed() -> None:
    resolved = resolve_permissions({"notifications": True})
    assert "android.permission.POST_NOTIFICATIONS" in resolved.android_permissions
    assert resolved.ios_usage_descriptions == {}


def test_location_always_adds_background_mode_and_perms() -> None:
    resolved = resolve_permissions({"location_always": "Track route"})
    assert "android.permission.ACCESS_BACKGROUND_LOCATION" in resolved.android_permissions
    assert "android.permission.ACCESS_FINE_LOCATION" in resolved.android_permissions
    assert "location" in resolved.ios_background_modes
    assert resolved.ios_usage_descriptions["NSLocationAlwaysAndWhenInUseUsageDescription"] == "Track route"
    assert "NSLocationWhenInUseUsageDescription" in resolved.ios_usage_descriptions


def test_extra_android_permissions_appended_and_deduped() -> None:
    resolved = resolve_permissions(
        {"camera": True},
        extra_android_permissions=["android.permission.CAMERA", "android.permission.FOO"],
    )
    assert resolved.android_permissions.count("android.permission.CAMERA") == 1
    assert "android.permission.FOO" in resolved.android_permissions


def test_android_permissions_have_no_duplicates() -> None:
    resolved = resolve_permissions({"location_when_in_use": True, "location_always": True})
    assert len(resolved.android_permissions) == len(set(resolved.android_permissions))


def test_unknown_capabilities_helper() -> None:
    assert unknown_capabilities(["camera", "telepathy", "x-ray"]) == ["telepathy", "x-ray"]
    assert unknown_capabilities(["camera", "notifications"]) == []


def test_resolve_raises_on_unknown() -> None:
    with pytest.raises(ValueError):
        resolve_permissions({"telepathy": True})


def test_describe_catalog_lists_all() -> None:
    text = describe_catalog()
    for key in CAPABILITIES:
        assert key in text
