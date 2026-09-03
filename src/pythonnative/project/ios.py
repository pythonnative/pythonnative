"""Config-driven iOS project configurator.

Adapts the bundled ``ios_template`` Xcode project to a specific
[`AppConfig`][pythonnative.project.config.AppConfig]. Unlike Android, the
iOS bundle identifier, version, team, and deployment target are *not*
baked into files; they're passed to ``xcodebuild`` as build-setting
overrides (see [`build_settings`][pythonnative.project.ios.build_settings]),
which avoids fragile ``project.pbxproj`` edits. This module owns the
parts that must live on disk:

- **Info.plist.** Display name, supported orientations, permission usage
  descriptions (from ``[permissions]``), background modes, URL schemes
  (from ``[app].url_schemes``), and any ``[ios].extra_info_plist`` keys.
- **Entitlements.** A ``.entitlements`` file generated when a declared
  capability needs one (e.g., ``remote_notifications``).
- **Branding.** The ``AppIcon`` asset and an optional ``Splash`` image
  set plus a generated ``LaunchScreen`` storyboard.
- **Export options.** A plist for ``xcodebuild -exportArchive`` derived
  from ``[ios.signing]``.

The embedded CPython runtime is *not* handled here: the bundled Xcode
template links ``Python.xcframework`` directly and installs the standard
library, app sources, and packages during the Xcode build (see the
"Install Python runtime" build phase). The
[`builder`][pythonnative.project.builder] stages the framework and the
Python sources into the project before invoking ``xcodebuild``.
"""

from __future__ import annotations

import plistlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from . import icons
from .config import AppConfig

PROJECT_NAME = "ios_template"
"""The fixed Xcode project/scheme/target name (kept stable on purpose)."""

PROJECT_FILE = "ios_template.xcodeproj"
"""The ``.xcodeproj`` directory name within the staged template."""

APP_BUNDLE_NAME = "ios_template.app"
"""The built ``.app`` bundle name (product name is left as the target name)."""

ENTITLEMENTS_FILE = "ios_template/ios_template.entitlements"
"""Project-relative path of the generated entitlements file (when needed)."""

_ORIENTATIONS: Dict[str, List[str]] = {
    "portrait": ["UIInterfaceOrientationPortrait"],
    "landscape": [
        "UIInterfaceOrientationLandscapeLeft",
        "UIInterfaceOrientationLandscapeRight",
    ],
    "all": [
        "UIInterfaceOrientationPortrait",
        "UIInterfaceOrientationLandscapeLeft",
        "UIInterfaceOrientationLandscapeRight",
    ],
}

_EXPORT_METHODS = {
    "development": "development",
    "ad-hoc": "ad-hoc",
    "app-store": "app-store",
    "enterprise": "enterprise",
}

Logger = Callable[[str], None]


@dataclass
class IOSLayout:
    """Resolved paths within a configured iOS project.

    Attributes:
        project_dir: The staged ``ios_template`` directory.
        info_plist: Path to the app ``Info.plist``.
        bundle_id: The resolved iOS bundle identifier.
    """

    project_dir: Path
    info_plist: Path
    bundle_id: str


def configure(project_dir: Path, config: AppConfig, *, log: Optional[Logger] = None) -> IOSLayout:
    """Configure a staged iOS template for ``config``.

    Args:
        project_dir: The staged ``ios_template`` directory.
        config: The validated app configuration.
        log: Optional progress logger.

    Returns:
        An [`IOSLayout`][pythonnative.project.ios.IOSLayout].
    """
    emit: Logger = log or (lambda _message: None)
    project_dir = Path(project_dir)
    info_plist = project_dir / "ios_template" / "Info.plist"

    configure_info_plist(info_plist, config)
    write_entitlements(project_dir, config)
    _apply_branding(project_dir, config, emit)

    emit(f"Configured iOS project ({config.bundle_id}).")
    return IOSLayout(project_dir=project_dir, info_plist=info_plist, bundle_id=config.bundle_id)


# ======================================================================
# Info.plist
# ======================================================================


def configure_info_plist(info_plist: Path, config: AppConfig) -> None:
    """Write display name, orientation, permissions, and extras to the plist.

    Args:
        info_plist: Path to the app ``Info.plist``.
        config: The validated app configuration.
    """
    with open(info_plist, "rb") as handle:
        plist = plistlib.load(handle)

    plist["CFBundleDisplayName"] = config.display_name
    plist["CFBundleName"] = config.name
    plist["PNEntryModule"] = config.entry_module

    orientations = _ORIENTATIONS.get(config.orientation, _ORIENTATIONS["portrait"])
    plist["UISupportedInterfaceOrientations"] = list(orientations)
    plist["UISupportedInterfaceOrientations~ipad"] = list(orientations)

    resolved = config.resolved_permissions()
    for key, reason in resolved.ios_usage_descriptions.items():
        plist[key] = reason
    if resolved.ios_background_modes:
        plist["UIBackgroundModes"] = list(resolved.ios_background_modes)

    if config.url_schemes:
        plist["CFBundleURLTypes"] = [
            {
                "CFBundleURLName": config.bundle_id,
                "CFBundleURLSchemes": list(config.url_schemes),
            }
        ]

    if config.splash:
        plist["UILaunchStoryboardName"] = "LaunchScreen"

    for key, value in config.ios.extra_info_plist.items():
        plist[key] = value

    with open(info_plist, "wb") as handle:
        plistlib.dump(plist, handle)


def write_entitlements(project_dir: Path, config: AppConfig) -> Optional[Path]:
    """Generate the app entitlements file when a capability needs one.

    Args:
        project_dir: The staged ``ios_template`` directory.
        config: The validated app configuration.

    Returns:
        The written entitlements path, or ``None`` when no declared
        capability requires entitlements.
    """
    entitlements = config.resolved_permissions().ios_entitlements
    if not entitlements:
        return None
    dest = project_dir / ENTITLEMENTS_FILE
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as handle:
        plistlib.dump(dict(entitlements), handle)
    return dest


# ======================================================================
# Build settings / export options
# ======================================================================


def build_settings(config: AppConfig, *, for_archive: bool = False) -> List[str]:
    """Return ``KEY=VALUE`` ``xcodebuild`` overrides for this config.

    Args:
        config: The validated app configuration.
        for_archive: When ``True``, include signing settings appropriate
            for a device archive.

    Returns:
        A list of ``"SETTING=value"`` strings to append to an
        ``xcodebuild`` invocation.
    """
    orientations = _ORIENTATIONS.get(config.orientation, _ORIENTATIONS["portrait"])
    orientation_value = " ".join(orientations)
    settings = [
        f"PRODUCT_BUNDLE_IDENTIFIER={config.bundle_id}",
        f"MARKETING_VERSION={config.version}",
        f"CURRENT_PROJECT_VERSION={config.build}",
        f"IPHONEOS_DEPLOYMENT_TARGET={config.ios.deployment_target}",
        f"INFOPLIST_KEY_UISupportedInterfaceOrientations_iPhone={orientation_value}",
        f"INFOPLIST_KEY_UISupportedInterfaceOrientations_iPad={orientation_value}",
    ]
    if config.ios.development_team:
        settings.append(f"DEVELOPMENT_TEAM={config.ios.development_team}")
    if config.resolved_permissions().ios_entitlements:
        settings.append(f"CODE_SIGN_ENTITLEMENTS={ENTITLEMENTS_FILE}")
    if for_archive and not config.ios.signing.provisioning_profile:
        settings.append("CODE_SIGN_STYLE=Automatic")
    return settings


def write_export_options(config: AppConfig, dest: Path, *, upload: bool = False) -> Path:
    """Write an ``exportOptions.plist`` for ``xcodebuild -exportArchive``.

    Args:
        config: The validated app configuration.
        dest: Destination plist path.
        upload: When ``True``, ask ``xcodebuild`` to upload the build to
            App Store Connect instead of exporting a local ``.ipa``
            (requires ``export_method = "app-store"``).

    Returns:
        ``dest``.
    """
    signing = config.ios.signing
    options: Dict[str, object] = {
        "method": _EXPORT_METHODS.get(signing.export_method, "development"),
        "compileBitcode": False,
        "stripSwiftSymbols": True,
    }
    if upload:
        options["destination"] = "upload"
    if config.ios.development_team:
        options["teamID"] = config.ios.development_team
    if signing.provisioning_profile:
        options["signingStyle"] = "manual"
        options["provisioningProfiles"] = {config.bundle_id: signing.provisioning_profile}
    else:
        options["signingStyle"] = "automatic"

    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as handle:
        plistlib.dump(options, handle)
    return dest


# ======================================================================
# Branding
# ======================================================================


def _apply_branding(project_dir: Path, config: AppConfig, emit: Logger) -> None:
    assets_dir = project_dir / "ios_template" / "Assets.xcassets"
    icon_path = config.resolve_path(config.icon) if config.icon else None
    splash_path = config.resolve_path(config.splash) if config.splash else None

    if icon_path and icons.has_source(icon_path):
        if icons.generate_ios_icons(icon_path, assets_dir / "AppIcon.appiconset"):
            emit("Generated iOS app icon.")
        else:
            emit("Skipping iOS icon: Pillow not installed (pip install 'pythonnative[build]').")

    if splash_path and icons.has_source(splash_path):
        if icons.generate_ios_splash(splash_path, assets_dir / "Splash.imageset"):
            _write_launch_storyboard(project_dir)
            emit("Configured iOS splash screen.")
        else:
            emit("Skipping iOS splash: Pillow not installed (pip install 'pythonnative[build]').")


def _write_launch_storyboard(project_dir: Path) -> None:
    """Overwrite ``LaunchScreen.storyboard`` with a centered splash image."""
    storyboard = project_dir / "ios_template" / "Base.lproj" / "LaunchScreen.storyboard"
    storyboard.write_text(_LAUNCH_STORYBOARD, encoding="utf-8")


# An edge-pinned image view (aspect-fit) over a white background. The
# image references the generated "Splash" asset set.
_LAUNCH_STORYBOARD = """<?xml version="1.0" encoding="UTF-8"?>
<document type="com.apple.InterfaceBuilder3.CocoaTouch.Storyboard.XIB" version="3.0" toolsVersion="22155" targetRuntime="iOS.CocoaTouch" propertyAccessControl="none" useAutolayout="YES" launchScreen="YES" useTraitCollections="YES" useSafeAreas="YES" colorMatched="YES" initialViewController="01J-lp-oVM">
    <dependencies>
        <plugIn identifier="com.apple.InterfaceBuilder.IBCocoaTouchPlugin" version="22131"/>
        <capability name="Safe area layout guides" minToolsVersion="9.0"/>
        <capability name="documents saved in the Xcode 8 format" minToolsVersion="8.0"/>
    </dependencies>
    <scenes>
        <scene sceneID="EHf-IW-A2E">
            <objects>
                <viewController id="01J-lp-oVM" sceneMemberID="viewController">
                    <view key="view" contentMode="scaleToFill" id="Ze5-6b-2t3">
                        <rect key="frame" x="0.0" y="0.0" width="393" height="852"/>
                        <autoresizingMask key="autoresizingMask" widthSizable="YES" heightSizable="YES"/>
                        <subviews>
                            <imageView clipsSubviews="YES" userInteractionEnabled="NO" contentMode="scaleAspectFit" image="Splash" translatesAutoresizingMaskIntoConstraints="NO" id="Spl-aS-h00"/>
                        </subviews>
                        <viewLayoutGuide key="safeArea" id="6Tk-OE-BBY"/>
                        <color key="backgroundColor" systemColor="systemBackgroundColor"/>
                        <constraints>
                            <constraint firstItem="Spl-aS-h00" firstAttribute="leading" secondItem="Ze5-6b-2t3" secondAttribute="leading" id="lea-Sp-001"/>
                            <constraint firstItem="Spl-aS-h00" firstAttribute="trailing" secondItem="Ze5-6b-2t3" secondAttribute="trailing" id="tra-Sp-002"/>
                            <constraint firstItem="Spl-aS-h00" firstAttribute="top" secondItem="Ze5-6b-2t3" secondAttribute="top" id="top-Sp-003"/>
                            <constraint firstItem="Spl-aS-h00" firstAttribute="bottom" secondItem="Ze5-6b-2t3" secondAttribute="bottom" id="bot-Sp-004"/>
                        </constraints>
                    </view>
                </viewController>
                <placeholder placeholderIdentifier="IBFirstResponder" id="iYj-Kq-Ea1" userLabel="First Responder" sceneMemberID="firstResponder"/>
            </objects>
            <point key="canvasLocation" x="53" y="375"/>
        </scene>
    </scenes>
    <resources>
        <image name="Splash" width="393" height="393"/>
    </resources>
</document>
"""
