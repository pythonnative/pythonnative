"""Upload a built app to App Store Connect or Google Play (``pn submit``).

Both paths use store credentials from the environment, so they run the same on
a laptop and in CI:

- **iOS:** ``PN_ASC_KEY_PATH``, ``PN_ASC_KEY_ID``, and ``PN_ASC_ISSUER_ID`` name
  an App Store Connect API key, which ``xcrun altool`` uploads the ``.ipa`` with.
- **Android:** ``PN_PLAY_SERVICE_ACCOUNT`` names a Google service account's JSON
  key file. The Google Play Developer API takes the ``.aab`` through a single
  edit: insert it, upload the bundle, assign the track, and commit. The access
  token's JWT is signed with ``openssl``, so this adds no dependency.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence

__all__ = [
    "PlayStore",
    "SubmitError",
    "find_android_bundle",
    "find_ios_package",
    "submit_android",
    "submit_ios",
]

_TOKEN_SCOPE = "https://www.googleapis.com/auth/androidpublisher"
_PLAY_TRACKS = ("internal", "alpha", "beta", "production")

Logger = Callable[[str], None]


class SubmitError(RuntimeError):
    """An upload couldn't start or a store rejected it. The message says why."""


def find_ios_package(build_root: Path) -> Path:
    """The newest exported ``.ipa`` under ``build_root``.

    Raises:
        SubmitError: If nothing has been exported yet.
    """
    packages = sorted((Path(build_root) / "ios" / "export").rglob("*.ipa"), key=lambda path: path.stat().st_mtime)
    if not packages:
        raise SubmitError("No .ipa found. Run 'pn build ios' with [ios.signing] export_method = \"app-store\" first.")
    return packages[-1]


def find_android_bundle(build_root: Path) -> Path:
    """The newest release ``.aab`` under ``build_root``.

    Raises:
        SubmitError: If nothing has been built yet.
    """
    bundles = sorted(
        (Path(build_root) / "android").rglob("*-release.aab"),
        key=lambda path: path.stat().st_mtime,
    )
    if not bundles:
        raise SubmitError("No release .aab found. Run 'pn build android' first.")
    return bundles[-1]


def submit_ios(package: Path, *, environ: Optional[Mapping[str, str]] = None, log: Optional[Logger] = None) -> None:
    """Upload ``package`` to App Store Connect.

    Raises:
        SubmitError: If credentials are missing or ``altool`` fails.
    """
    env = dict(os.environ if environ is None else environ)
    emit: Logger = log or print
    path, key_id, issuer = (env.get(name) for name in ("PN_ASC_KEY_PATH", "PN_ASC_KEY_ID", "PN_ASC_ISSUER_ID"))
    if not (path and key_id and issuer):
        raise SubmitError(
            "Set PN_ASC_KEY_PATH, PN_ASC_KEY_ID, and PN_ASC_ISSUER_ID to an App Store Connect API key. "
            "Create one under Users and Access > Integrations in App Store Connect."
        )
    if not Path(path).is_file():
        raise SubmitError(f"PN_ASC_KEY_PATH doesn't exist: {path}")
    # altool looks the key up by file name in API_PRIVATE_KEYS_DIR.
    with tempfile.TemporaryDirectory(prefix="pn-asc-") as keys:
        shutil.copy2(path, Path(keys) / f"AuthKey_{key_id}.p8")
        env["API_PRIVATE_KEYS_DIR"] = keys
        emit(f"Uploading {package.name} to App Store Connect...")
        result = subprocess.run(
            [
                "xcrun",
                "altool",
                "--upload-app",
                "-f",
                str(package),
                "-t",
                "ios",
                "--apiKey",
                key_id,
                "--apiIssuer",
                issuer,
            ],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    if result.returncode != 0:
        raise SubmitError(f"altool failed:\n{result.stdout}\n{result.stderr}".strip())
    emit("Uploaded. App Store Connect processes the build before it appears in TestFlight.")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _sign_rs256(message: bytes, private_key: str) -> bytes:
    with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as handle:
        handle.write(private_key)
        key_path = handle.name
    try:
        os.chmod(key_path, 0o600)
        result = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", key_path],
            input=message,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise SubmitError("Signing Google's token needs openssl on PATH.") from exc
    finally:
        os.unlink(key_path)
    if result.returncode != 0:
        raise SubmitError(
            f"openssl couldn't sign with the service account key: {result.stderr.decode(errors='replace')}"
        )
    return result.stdout


@dataclass
class PlayStore:
    """A minimal Google Play Developer API client.

    Attributes:
        package: The Android application id.
        account: The parsed service account key.
        api_root: The API's origin; tests point it at a fake server.
    """

    package: str
    account: Dict[str, Any]
    api_root: str = "https://androidpublisher.googleapis.com"
    _token: Optional[str] = None

    def _request(
        self,
        method: str,
        url: str,
        *,
        body: Optional[bytes] = None,
        content_type: str = "application/json",
        auth: bool = True,
    ) -> Dict[str, Any]:
        request = urllib.request.Request(url, data=body, method=method, headers={"Content-Type": content_type})
        if auth:
            request.add_header("Authorization", f"Bearer {self.token()}")
        try:
            with urllib.request.urlopen(request, timeout=600) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            raise SubmitError(f"Google Play returned HTTP {exc.code} for {method} {url}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise SubmitError(f"Couldn't reach Google Play: {exc.reason}") from exc
        parsed: Dict[str, Any] = json.loads(raw) if raw else {}
        return parsed

    def token(self) -> str:
        """An OAuth access token for the service account, requested once."""
        if self._token is None:
            token_uri = str(self.account.get("token_uri") or "https://oauth2.googleapis.com/token")
            now = int(time.time())
            header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
            claims = _b64url(
                json.dumps(
                    {
                        "iss": self.account["client_email"],
                        "scope": _TOKEN_SCOPE,
                        "aud": token_uri,
                        "iat": now,
                        "exp": now + 3600,
                    }
                ).encode()
            )
            signing_input = f"{header}.{claims}".encode()
            signature = _b64url(_sign_rs256(signing_input, self.account["private_key"]))
            form = urllib.parse.urlencode(
                {
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": f"{header}.{claims}.{signature}",
                }
            ).encode()
            reply = self._request(
                "POST", token_uri, body=form, content_type="application/x-www-form-urlencoded", auth=False
            )
            self._token = str(reply["access_token"])
        return self._token

    def _edits(self) -> str:
        return f"{self.api_root}/androidpublisher/v3/applications/{self.package}/edits"

    def upload(self, bundle: Path, *, track: str, status: str = "completed", log: Optional[Logger] = None) -> int:
        """Upload ``bundle`` to ``track`` in one edit and return its version code."""
        emit: Logger = log or print
        edit = self._request("POST", self._edits(), body=b"{}")["id"]
        emit(f"Uploading {bundle.name} to Google Play...")
        upload_url = (
            f"{self.api_root}/upload/androidpublisher/v3/applications/{self.package}/edits/{edit}/bundles"
            "?uploadType=media"
        )
        reply = self._request("POST", upload_url, body=bundle.read_bytes(), content_type="application/octet-stream")
        version = int(reply["versionCode"])
        emit(f"Assigning version {version} to the {track} track...")
        release = {"track": track, "releases": [{"status": status, "versionCodes": [str(version)]}]}
        self._request("PUT", f"{self._edits()}/{edit}/tracks/{track}", body=json.dumps(release).encode())
        self._request("POST", f"{self._edits()}/{edit}:commit", body=b"")
        return version


def submit_android(
    bundle: Path,
    *,
    package: str,
    track: str = "internal",
    draft: bool = False,
    environ: Optional[Mapping[str, str]] = None,
    api_root: Optional[str] = None,
    log: Optional[Logger] = None,
) -> int:
    """Upload ``bundle`` to Google Play and return the version code it was given.

    Args:
        bundle: The signed ``.aab``.
        package: The Android application id.
        track: One of ``internal``, ``alpha``, ``beta``, or ``production``.
        draft: Leave the release as a draft. A new app must use this until its
            first release has gone through the Play Console.
        environ: The environment; defaults to ``os.environ``.
        api_root: The API's origin, for tests.
        log: Progress logger.

    Raises:
        SubmitError: If credentials are missing, or Google Play rejects a step.
    """
    env = os.environ if environ is None else environ
    if track not in _PLAY_TRACKS:
        raise SubmitError(f"Unknown track {track!r}. Use one of {', '.join(_PLAY_TRACKS)}.")
    path = env.get("PN_PLAY_SERVICE_ACCOUNT")
    if not path:
        raise SubmitError(
            "Set PN_PLAY_SERVICE_ACCOUNT to a Google service account's JSON key file, with access granted "
            "in the Play Console under Users and permissions."
        )
    try:
        account = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SubmitError(f"Couldn't read the service account key at {path}: {exc}") from exc
    missing: Sequence[str] = [key for key in ("client_email", "private_key") if key not in account]
    if missing:
        raise SubmitError(f"{path} isn't a service account key; it's missing {', '.join(missing)}.")
    store = PlayStore(package, account, api_root or PlayStore.api_root)
    return store.upload(bundle, track=track, status="draft" if draft else "completed", log=log)
