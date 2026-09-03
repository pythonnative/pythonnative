"""Target-aware resolution of ``[requirements].packages``.

A PythonNative app runs on an embedded CPython, so its third-party
packages have to be resolved for the *device*, not for the machine
running ``pn``. Pure-Python wheels (``py3-none-any``) work everywhere,
but anything with a compiled extension needs a wheel built for the
exact platform triple the app will run on:

- iOS (PEP 730): ``ios_13_0_arm64_iphoneos`` for devices and
  ``ios_13_0_arm64_iphonesimulator`` / ``ios_13_0_x86_64_iphonesimulator``
  for the Simulator, published on PyPI and on BeeWare's index.
- Android (PEP 738): ``android_24_arm64_v8a`` / ``android_24_x86_64``,
  published on PyPI and on Chaquopy's index.

This module models those targets ([`Target`][pythonnative.project.deps.Target]),
asks pip to resolve the project's requirements against each of them
without installing anything ([`resolve`][pythonnative.project.deps.resolve]),
and installs the resolved set into a per-target directory for the
iOS build ([`install`][pythonnative.project.deps.install]). ``pip``
does the actual work through its ``--platform`` / ``--python-version``
/ ``--only-binary=:all:`` cross-resolution mode, so the host
interpreter's version and platform never leak into the app.

On Android the authoritative install is done by Chaquopy inside the
Gradle build (with the same ``--only-binary`` rule); resolving here is
a fast preview that catches missing wheels before a multi-minute build.

All pip invocations go through the builder's
[`CommandRunner`][pythonnative.project.builder.CommandRunner] so the
logic is unit testable with a recording fake.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

from .config import AppConfig

if TYPE_CHECKING:
    from .builder import CommandRunner

BEEWARE_INDEX_URL = "https://pypi.anaconda.org/beeware/simple"
"""BeeWare's wheel index: iOS binary wheels for the CPython versions Python-Apple-support ships."""

CHAQUOPY_INDEX_URL = "https://chaquo.com/pypi-13.1/"
"""Chaquopy's wheel index: Android binary wheels built for its embedded CPython."""

MIN_IOS_WHEEL_VERSION = (12, 0)
"""Oldest iOS version a PEP 730 wheel can be tagged with (CPython's own floor)."""

MIN_ANDROID_WHEEL_API = 16
"""Oldest Android API level a PEP 738 wheel can be tagged with."""

IOS_SDKS = ("iphoneos", "iphonesimulator")
"""The two iOS SDKs a build can target; each gets its own ``app_packages`` slice."""

ANDROID_ABI_TAGS: Dict[str, str] = {"arm64-v8a": "arm64_v8a", "x86_64": "x86_64"}
"""Gradle ABI name -> wheel platform tag component."""


# ======================================================================
# Targets
# ======================================================================


@dataclass(frozen=True)
class Target:
    """One device platform to resolve packages for.

    Attributes:
        platform: ``"ios"`` or ``"android"``.
        python_version: CPython ``major.minor`` the app embeds.
        arch: CPU architecture (``"arm64"`` or ``"x86_64"``).
        sdk: iOS SDK (``"iphoneos"`` / ``"iphonesimulator"``); empty on
            Android.
        os_version: Minimum OS version the app declares: the iOS
            deployment target (``"13.0"``) or the Android API level as a
            string (``"24"``).
    """

    platform: str
    python_version: str
    arch: str
    sdk: str = ""
    os_version: str = "13.0"

    @property
    def label(self) -> str:
        """Short human-readable name, e.g. ``"iOS Simulator (arm64)"``."""
        if self.platform == "ios":
            kind = "iOS device" if self.sdk == "iphoneos" else "iOS Simulator"
            return f"{kind} ({self.arch}, iOS {self.os_version}+)"
        return f"Android {self.abi} (API {self.os_version}+)"

    @property
    def abi(self) -> str:
        """The Gradle ABI name for an Android target (``"arm64-v8a"``)."""
        for abi, tag in ANDROID_ABI_TAGS.items():
            if tag == self.arch or abi == self.arch:
                return abi
        return self.arch

    @property
    def slice_name(self) -> str:
        """The staged packages folder name for an iOS target (``app_packages.iphoneos``)."""
        return f"app_packages.{self.sdk}"

    @property
    def platform_tags(self) -> List[str]:
        """Every wheel platform tag this target accepts, newest first.

        A wheel is tagged with the *minimum* OS version it supports, so
        a target on iOS 13.0 also accepts wheels tagged for 12.x.
        Mirrors ``packaging.tags.ios_platforms`` /
        ``android_platforms`` so the list stays in step with what pip
        itself would compute on the device.
        """
        if self.platform == "ios":
            return list(_ios_platform_tags(self.os_version, f"{self.arch}_{self.sdk}"))
        return list(_android_platform_tags(int(self.os_version), ANDROID_ABI_TAGS.get(self.arch, self.arch)))

    @property
    def index_urls(self) -> List[str]:
        """Extra indexes searched after PyPI: the platform's binary wheel repository."""
        return [BEEWARE_INDEX_URL] if self.platform == "ios" else [CHAQUOPY_INDEX_URL]

    @property
    def abi_tag(self) -> str:
        """The CPython ABI tag (``cp313``)."""
        return "cp" + self.python_version.replace(".", "")


def _ios_platform_tags(version: str, multiarch: str) -> Iterable[str]:
    major, minor = _parse_version(version)
    for maj in range(major, MIN_IOS_WHEEL_VERSION[0] - 1, -1):
        top = minor if maj == major else 9
        bottom = MIN_IOS_WHEEL_VERSION[1] if maj == MIN_IOS_WHEEL_VERSION[0] else 0
        for mnr in range(top, bottom - 1, -1):
            yield f"ios_{maj}_{mnr}_{multiarch}"


def _android_platform_tags(api_level: int, abi: str) -> Iterable[str]:
    for level in range(api_level, MIN_ANDROID_WHEEL_API - 1, -1):
        yield f"android_{level}_{abi}"


def _parse_version(version: str) -> Tuple[int, int]:
    parts = version.split(".")
    major = int(parts[0])
    minor = int(parts[1]) if len(parts) > 1 else 0
    return major, minor


def host_simulator_arch() -> str:
    """The iOS Simulator architecture matching this Mac (``arm64`` or ``x86_64``)."""
    import platform as platform_module

    return "arm64" if platform_module.machine() == "arm64" else "x86_64"


def ios_targets(
    config: AppConfig, *, sdks: Sequence[str] = IOS_SDKS, simulator_arch: Optional[str] = None
) -> List[Target]:
    """Build the iOS targets for ``config``.

    Args:
        config: The validated app configuration.
        sdks: Which SDKs to include (default both).
        simulator_arch: Architecture for the Simulator target; defaults
            to the host Mac's, which is also what the builder pins
            ``ARCHS`` to.

    Returns:
        One [`Target`][pythonnative.project.deps.Target] per SDK.
    """
    targets: List[Target] = []
    for sdk in sdks:
        if sdk not in IOS_SDKS:
            raise ValueError(f"Unknown iOS SDK {sdk!r} (expected one of {IOS_SDKS}).")
        arch = "arm64" if sdk == "iphoneos" else (simulator_arch or host_simulator_arch())
        targets.append(
            Target(
                platform="ios",
                python_version=config.python_version,
                arch=arch,
                sdk=sdk,
                os_version=config.ios.deployment_target,
            )
        )
    return targets


def android_targets(config: AppConfig) -> List[Target]:
    """Build one Android target per ``[android].abi_filters`` entry."""
    return [
        Target(
            platform="android",
            python_version=config.python_version,
            arch=ANDROID_ABI_TAGS.get(abi, abi),
            os_version=str(config.android.min_sdk),
        )
        for abi in config.android.abi_filters
    ]


def targets_for(config: AppConfig, platform: Optional[str] = None) -> List[Target]:
    """All targets for ``platform`` (``"ios"``, ``"android"``, or ``None`` for both)."""
    targets: List[Target] = []
    if platform in (None, "ios"):
        targets.extend(ios_targets(config))
    if platform in (None, "android"):
        targets.extend(android_targets(config))
    return targets


# ======================================================================
# pip invocations
# ======================================================================


def pip_base_args(config: AppConfig, target: Target, *, python: Optional[str] = None) -> List[str]:
    """The pip arguments that select ``target`` for cross-platform resolution.

    Args:
        config: The app configuration (for ``extra_index_urls``).
        target: The device target.
        python: Interpreter to run pip with; defaults to the current one.

    Returns:
        ``[python, "-m", "pip", "install", <selection flags...>]`` with
        no requirements appended.
    """
    args = [
        python or sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        # Cross-resolution: pip refuses to build from source for a foreign
        # platform, which is also exactly what an app store build needs.
        "--only-binary=:all:",
        "--implementation",
        "cp",
        "--python-version",
        target.python_version,
        "--abi",
        target.abi_tag,
    ]
    for tag in target.platform_tags:
        args.extend(["--platform", tag])
    for url in [*target.index_urls, *config.extra_index_urls]:
        args.extend(["--extra-index-url", url])
    return args


def report_args(config: AppConfig, target: Target, *, python: Optional[str] = None) -> List[str]:
    """Pip arguments that resolve ``config.requirements`` for ``target`` without installing.

    The JSON report (``--report -``) lists every wheel pip *would*
    install, which is what [`resolve`][pythonnative.project.deps.resolve]
    parses.
    """
    return [
        *pip_base_args(config, target, python=python),
        "--dry-run",
        "--ignore-installed",
        "--quiet",
        "--report",
        "-",
        *config.requirements,
    ]


def install_args(config: AppConfig, target: Target, dest: Path, *, python: Optional[str] = None) -> List[str]:
    """Pip arguments that install ``config.requirements`` for ``target`` into ``dest``."""
    return [
        *pip_base_args(config, target, python=python),
        "--target",
        str(dest),
        "--upgrade",
        *config.requirements,
    ]


# ======================================================================
# Results
# ======================================================================


@dataclass
class ResolvedPackage:
    """One wheel pip selected for a target.

    Attributes:
        name: Distribution name as reported by pip.
        version: Selected version.
        filename: The wheel filename (its tags say what it is built for).
        url: Where the wheel comes from.
    """

    name: str
    version: str
    filename: str
    url: str = ""
    latest: str = ""
    """The version an unconstrained desktop resolution picks, when it is newer than ``version``.

    Set by [`mark_downgrades`][pythonnative.project.deps.mark_downgrades].
    A non-empty value means pip walked back to an older release because
    the newer ones have no wheel for this target.
    """

    @property
    def downgraded(self) -> bool:
        """Whether this target got an older release than the desktop would."""
        return bool(self.latest)

    @property
    def is_pure(self) -> bool:
        """Whether this is a platform-independent (``none-any``) wheel."""
        return self.filename.endswith("-none-any.whl")

    @property
    def platform_tag(self) -> str:
        """The wheel's platform tag (``"any"`` for pure-Python wheels)."""
        stem = self.filename[:-4] if self.filename.endswith(".whl") else self.filename
        return stem.rsplit("-", 1)[-1]

    @property
    def index_host(self) -> str:
        """Host name of the index the wheel is served from (``"files.pythonhosted.org"`` for PyPI)."""
        return urlparse(self.url).netloc if self.url else ""

    @property
    def source_label(self) -> str:
        """Friendly source name: ``PyPI``, ``BeeWare``, ``Chaquopy``, or the index host."""
        host = self.index_host
        if host.endswith("pythonhosted.org") or host.endswith("pypi.org"):
            return "PyPI"
        if host == "pypi.anaconda.org" and "/beeware/" in self.url:
            return "BeeWare"
        if host == "chaquo.com":
            return "Chaquopy"
        return host or "local"


@dataclass
class Resolution:
    """The outcome of resolving the requirements for one target.

    Attributes:
        target: The target that was resolved.
        packages: Wheels pip selected (empty when ``error`` is set or
            there are no requirements).
        error: pip's failure explanation when resolution failed, else
            ``None``.
        missing: Requirement names pip could not satisfy, parsed from
            ``error`` (best effort).
    """

    target: Target
    packages: List[ResolvedPackage] = field(default_factory=list)
    error: Optional[str] = None
    missing: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Whether every requirement resolved to a wheel."""
        return self.error is None

    @property
    def binary_packages(self) -> List[ResolvedPackage]:
        """The platform-specific wheels in ``packages``."""
        return [pkg for pkg in self.packages if not pkg.is_pure]

    @property
    def downgraded_packages(self) -> List[ResolvedPackage]:
        """Packages that resolved to an older release than the desktop would get."""
        return [pkg for pkg in self.packages if pkg.downgraded]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for ``pn deps --json`` and the compatibility matrix job."""
        return {
            "platform": self.target.platform,
            "label": self.target.label,
            "python_version": self.target.python_version,
            "arch": self.target.arch,
            "sdk": self.target.sdk,
            "ok": self.ok,
            "error": self.error,
            "missing": list(self.missing),
            "packages": [
                {
                    "name": pkg.name,
                    "version": pkg.version,
                    "filename": pkg.filename,
                    "pure": pkg.is_pure,
                    "platform_tag": pkg.platform_tag,
                    "source": pkg.source_label,
                    "url": pkg.url,
                    "latest": pkg.latest or None,
                }
                for pkg in self.packages
            ],
        }


class DependencyError(Exception):
    """Raised when requirements can't be resolved or installed for a target.

    The message is user-facing: it names the target, the unsatisfiable
    requirement(s), and what to do about it.
    """


# ======================================================================
# Resolving
# ======================================================================

_NO_MATCH_RE = re.compile(r"No matching distribution found for (?P<req>[^\s]+)")
_NO_VERSION_RE = re.compile(r"Could not find a version that satisfies the requirement (?P<req>[^\s]+)")


def parse_report(report_json: str, target: Target) -> Resolution:
    """Turn a pip ``--report`` JSON document into a [`Resolution`][pythonnative.project.deps.Resolution]."""
    data = json.loads(report_json or "{}")
    packages: List[ResolvedPackage] = []
    for item in data.get("install", []):
        metadata = item.get("metadata", {})
        download = item.get("download_info", {}) or {}
        url = str(download.get("url", ""))
        filename = url.rsplit("/", 1)[-1] if url else ""
        packages.append(
            ResolvedPackage(
                name=str(metadata.get("name", "?")),
                version=str(metadata.get("version", "?")),
                filename=filename,
                url=url,
            )
        )
    packages.sort(key=lambda pkg: pkg.name.lower())
    return Resolution(target=target, packages=packages)


def parse_failure(stderr: str) -> Tuple[str, List[str]]:
    """Extract a one-paragraph explanation and the unsatisfied requirement names from pip's stderr."""
    text = (stderr or "").strip()
    missing: List[str] = []
    for match in _NO_MATCH_RE.finditer(text):
        req = match.group("req").strip(".,")
        if req not in missing:
            missing.append(req)
    if not missing:
        for match in _NO_VERSION_RE.finditer(text):
            req = match.group("req").strip(".,")
            if req not in missing:
                missing.append(req)
    # pip prints the useful sentence(s) as ERROR: lines; everything else is noise.
    lines = [line for line in text.splitlines() if line.startswith("ERROR:")]
    summary = "\n".join(lines) if lines else (text.splitlines()[-1] if text else "pip failed without output")
    return summary, missing


def resolve(config: AppConfig, target: Target, *, runner: CommandRunner, python: Optional[str] = None) -> Resolution:
    """Resolve ``config.requirements`` for ``target`` without installing.

    Args:
        config: The validated app configuration.
        target: The device target.
        runner: A [`CommandRunner`][pythonnative.project.builder.CommandRunner].
        python: Interpreter to run pip with (defaults to the current one).

    Returns:
        A [`Resolution`][pythonnative.project.deps.Resolution]; check
        ``.ok`` rather than expecting an exception, so callers can
        report every target at once.
    """
    if not config.requirements:
        return Resolution(target=target)
    result = runner.run(report_args(config, target, python=python), capture=True)
    if not result.ok:
        summary, missing = parse_failure(result.stderr)
        return Resolution(target=target, error=summary, missing=missing)
    try:
        return parse_report(result.stdout, target)
    except (ValueError, TypeError) as exc:
        return Resolution(target=target, error=f"Could not parse pip's report: {exc}")


def resolve_all(
    config: AppConfig,
    targets: Sequence[Target],
    *,
    runner: CommandRunner,
    python: Optional[str] = None,
    detect_downgrades: bool = True,
) -> List[Resolution]:
    """[`resolve`][pythonnative.project.deps.resolve] every target in order.

    Args:
        config: The validated app configuration.
        targets: Targets to resolve for.
        runner: A [`CommandRunner`][pythonnative.project.builder.CommandRunner].
        python: Interpreter to run pip with (defaults to the current one).
        detect_downgrades: Also resolve once without any platform
            constraint and mark packages that got an older release on a
            target than that unconstrained resolution picked (see
            [`mark_downgrades`][pythonnative.project.deps.mark_downgrades]).
            One extra pip call; skipped when there are no requirements.
    """
    resolutions = [resolve(config, target, runner=runner, python=python) for target in targets]
    if detect_downgrades and config.requirements and any(res.ok and res.packages for res in resolutions):
        reference = resolve_reference(config, runner=runner, python=python)
        if reference is not None:
            mark_downgrades(resolutions, reference)
    return resolutions


def reference_args(config: AppConfig, *, python: Optional[str] = None) -> List[str]:
    """Pip arguments for an unconstrained dry-run resolution of ``config.requirements``.

    No platform or ABI flags and source distributions allowed, so pip
    picks the newest release it would give a desktop. Only the versions
    matter; nothing is downloaded beyond metadata.
    """
    return [
        python or sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--dry-run",
        "--ignore-installed",
        "--quiet",
        "--report",
        "-",
        *[arg for url in config.extra_index_urls for arg in ("--extra-index-url", url)],
        *config.requirements,
    ]


def resolve_reference(
    config: AppConfig, *, runner: CommandRunner, python: Optional[str] = None
) -> Optional[Dict[str, str]]:
    """Resolve the requirements with no target constraint; return ``{name: version}``.

    Returns ``None`` when pip can't resolve them at all (the per-target
    errors already say why) or the report can't be parsed.
    """
    if not config.requirements:
        return {}
    result = runner.run(reference_args(config, python=python), capture=True)
    if not result.ok:
        return None
    try:
        data = json.loads(result.stdout or "{}")
    except ValueError:
        return None
    versions: Dict[str, str] = {}
    for item in data.get("install", []):
        metadata = item.get("metadata", {})
        versions[_canonical(str(metadata.get("name", "")))] = str(metadata.get("version", ""))
    return versions


def mark_downgrades(resolutions: Sequence[Resolution], reference: Dict[str, str]) -> None:
    """Set ``latest`` on every resolved package that is older than in ``reference``.

    pip's cross-resolution silently walks back through a package's
    release history until it finds a version with a usable wheel for
    the target. That is the right call for a build (it works), but it
    is a surprise for the developer who gets a two-year-old API on the
    device and the current one in their tests. Marking the gap lets
    ``pn deps`` say so.

    Args:
        resolutions: Per-target resolutions to annotate in place.
        reference: ``{canonical name: version}`` from an unconstrained
            resolution (see
            [`resolve_reference`][pythonnative.project.deps.resolve_reference]).
    """
    for res in resolutions:
        for pkg in res.packages:
            latest = reference.get(_canonical(pkg.name))
            if latest and _version_key(latest) > _version_key(pkg.version):
                pkg.latest = latest


def _canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _version_key(version: str) -> Tuple[int, ...]:
    """Order versions by their numeric release segment, enough to detect a walk-back.

    Pre/post/dev suffixes are ignored on purpose: a ``2.5.2`` versus
    ``2.5.2.post1`` gap is not the kind of downgrade worth a warning.
    """
    match = re.match(r"^\d+(?:\.\d+)*", version)
    return tuple(int(part) for part in match.group(0).split(".")) if match else ()


def install(
    config: AppConfig,
    target: Target,
    dest: Path,
    *,
    runner: CommandRunner,
    python: Optional[str] = None,
) -> None:
    """Install ``config.requirements`` for ``target`` into ``dest``.

    Args:
        config: The validated app configuration.
        target: The device target (an iOS one; Android installs happen in
            Gradle).
        dest: The ``app_packages.<sdk>`` directory to populate.
        runner: A [`CommandRunner`][pythonnative.project.builder.CommandRunner].
        python: Interpreter to run pip with (defaults to the current one).

    Raises:
        DependencyError: When pip can't satisfy the requirements for the
            target, with the unsatisfiable requirement(s) named.
    """
    if not config.requirements:
        return
    dest.mkdir(parents=True, exist_ok=True)
    result = runner.run(install_args(config, target, dest, python=python), capture=True)
    if result.ok:
        return
    summary, missing = parse_failure(result.stderr)
    raise DependencyError(explain_failure(target, summary, missing))


def explain_failure(target: Target, summary: str, missing: Sequence[str]) -> str:
    """Compose the user-facing message for a failed resolution."""
    names = ", ".join(missing) if missing else "one or more requirements"
    lines = [f"Could not resolve {names} for {target.label} (Python {target.python_version})."]
    if summary:
        lines.append(summary)
    if target.platform == "ios":
        lines.append(
            "iOS needs a wheel tagged for the device (ios_*_arm64_iphoneos) and, for 'pn run ios', the "
            "Simulator (ios_*_iphonesimulator). Pure-Python packages always work; for a C extension, check "
            f"{BEEWARE_INDEX_URL} or ask upstream for iOS wheels (PEP 730)."
        )
    else:
        lines.append(
            "Android needs a wheel tagged android_*_arm64_v8a / android_*_x86_64 (PEP 738). Pure-Python "
            f"packages always work; for a C extension, check {CHAQUOPY_INDEX_URL} or PyPI's Android wheels."
        )
    lines.append("Run 'pn deps' for a per-target report; see https://pythonnative.com/guides/pypi-packages/.")
    return "\n".join(lines)


# ======================================================================
# Reporting
# ======================================================================


def format_report(resolutions: Sequence[Resolution], *, requirements: Sequence[str]) -> str:
    """Render resolutions as the terminal report ``pn deps`` prints."""
    if not requirements:
        return "No [requirements].packages declared in pythonnative.toml; nothing to resolve."
    out: List[str] = []
    for res in resolutions:
        header = res.target.label
        if res.target.platform == "android":
            header += "   (preview; Chaquopy resolves again inside the Gradle build)"
        out.append(header)
        if not res.ok:
            out.append("  [x] " + (res.error or "resolution failed").replace("\n", "\n      "))
            out.append("")
            continue
        width = max((len(f"{pkg.name} {pkg.version}") for pkg in res.packages), default=0)
        for pkg in res.packages:
            name = f"{pkg.name} {pkg.version}".ljust(width)
            kind = "pure Python" if pkg.is_pure else f"binary wheel  {pkg.platform_tag}  ({pkg.source_label})"
            marker = "[!!]" if pkg.downgraded else "[ok]"
            out.append(f"  {marker} {name}  {kind}")
            if pkg.downgraded:
                out.append(
                    f"       older than the desktop resolution ({pkg.latest}): newer releases have no wheel here"
                )
        out.append("")
    failed = [res for res in resolutions if not res.ok]
    downgraded = sorted({pkg.name for res in resolutions for pkg in res.downgraded_packages}, key=str.lower)
    if downgraded:
        out.append(
            f"Older release selected for: {', '.join(downgraded)} ([!!] above). Pin a version in "
            "[requirements].packages if the API difference matters."
        )
    if failed:
        out.append(f"{len(failed)} of {len(resolutions)} targets cannot be satisfied. See the [x] lines above.")
    else:
        out.append(f"All {len(resolutions)} targets resolved.")
    return "\n".join(out)
