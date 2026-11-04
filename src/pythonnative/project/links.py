"""The files a website hosts so its ``https`` links open the app.

``[app].associated_domains`` wires the app's half of universal links and Android
app links. The site's half is two static JSON files, whose contents depend on the
app's identity. ``pn links`` prints them.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Dict, List, Optional

from .config import AppConfig

__all__ = ["apple_app_site_association", "asset_links", "keystore_fingerprint", "render"]

_PLACEHOLDER_TEAM = "YOUR_TEAM_ID"
_PLACEHOLDER_FINGERPRINT = "YOUR_SIGNING_CERTIFICATE_SHA256"


def apple_app_site_association(config: AppConfig) -> Dict[str, object]:
    """The contents of ``/.well-known/apple-app-site-association``."""
    team = config.ios.development_team or _PLACEHOLDER_TEAM
    return {"applinks": {"details": [{"appIDs": [f"{team}.{config.bundle_id}"], "components": [{"/": "/*"}]}]}}


def keystore_fingerprint(config: AppConfig) -> Optional[str]:
    """The release key's SHA-256 fingerprint, when ``keytool`` can read the keystore."""
    signing = config.android.signing
    if not signing.is_configured or not signing.keystore or not signing.key_alias:
        return None
    password = os.environ.get(signing.store_password_env)
    if not password:
        return None
    try:
        result = subprocess.run(
            [
                "keytool",
                "-list",
                "-v",
                "-keystore",
                str(config.resolve_path(signing.keystore)),
                "-alias",
                signing.key_alias,
                "-storepass:env",
                signing.store_password_env,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    match = re.search(r"SHA256:\s*([0-9A-F:]+)", result.stdout)
    return match.group(1) if match else None


def asset_links(config: AppConfig, *, fingerprint: Optional[str] = None) -> List[Dict[str, object]]:
    """The contents of ``/.well-known/assetlinks.json``."""
    return [
        {
            "relation": ["delegate_permission/common.handle_all_urls"],
            "target": {
                "namespace": "android_app",
                "package_name": config.application_id,
                "sha256_cert_fingerprints": [fingerprint or _PLACEHOLDER_FINGERPRINT],
            },
        }
    ]


def render(config: AppConfig) -> str:
    """The instructions ``pn links`` prints, with both files' exact contents."""
    if not config.associated_domains:
        return (
            "No associated domains are configured. Add them to pythonnative.toml:\n\n"
            '[app]\nassociated_domains = ["example.com"]\n'
        )
    fingerprint = keystore_fingerprint(config)
    domains = ", ".join(config.associated_domains)
    lines = [
        f"Host these files over HTTPS on {domains}, with no redirects and a JSON content type.",
        "",
        "/.well-known/apple-app-site-association",
        json.dumps(apple_app_site_association(config), indent=2),
        "",
        "/.well-known/assetlinks.json",
        json.dumps(asset_links(config, fingerprint=fingerprint), indent=2),
    ]
    if not config.ios.development_team:
        lines += ["", f"Replace {_PLACEHOLDER_TEAM}: set [ios].development_team, or use your Apple team ID."]
    if fingerprint is None:
        lines += [
            "",
            f"Replace {_PLACEHOLDER_FINGERPRINT}. With Play App Signing, copy it from the Play Console under "
            "Setup > App signing. Otherwise, set [android.signing] and its password variable, and run this again.",
        ]
    else:
        lines += ["", "If Google Play signs your releases, add its fingerprint from the Play Console too."]
    return "\n".join(lines) + "\n"
