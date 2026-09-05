"""Deterministic, hash-verified wheel locks for embedded Python targets."""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path
from typing import Any, Sequence

from .config import AppConfig
from .deps import DependencyError, Resolution, Target

NAME = "pn.lock"


def target_key(target: Target) -> str:
    """Identify every platform constraint that changes compatible wheels."""
    return ":".join((target.platform, target.python_version, target.arch, target.sdk, target.os_version))


def write(config: AppConfig, resolutions: Sequence[Resolution]) -> Path:
    """Record every selected wheel and its SHA-256 digest atomically."""
    targets: dict[str, Any] = {}
    for resolution in resolutions:
        if not resolution.ok:
            raise DependencyError(f"Cannot lock unsuccessful target: {resolution.target.label}")
        packages = []
        for package in resolution.packages:
            if not re.fullmatch(r"[0-9a-f]{64}", package.sha256):
                raise DependencyError(f"The index did not supply a SHA-256 digest for {package.filename}")
            packages.append(
                {
                    "name": package.name,
                    "version": package.version,
                    "filename": package.filename,
                    "url": package.url,
                    "sha256": package.sha256,
                }
            )
        targets[target_key(resolution.target)] = {"target": dataclasses.asdict(resolution.target), "packages": packages}
    path = config.project_root / NAME
    try:
        previous = read(config)
    except DependencyError:
        previous = None
    if previous:
        targets = previous["targets"] | targets
    document = {
        "version": 1,
        "python": config.python_version,
        "requirements": list(config.requirements),
        "indexes": list(config.extra_index_urls),
        "targets": targets,
    }
    temporary = path.with_suffix(".lock.tmp")
    temporary.write_text(json.dumps(document, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def read(config: AppConfig) -> dict[str, Any] | None:
    """Read a lock and reject stale requirements instead of silently resolving."""
    path = config.project_root / NAME
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if (
        value.get("version") != 1
        or value.get("python") != config.python_version
        or value.get("requirements") != list(config.requirements)
        or value.get("indexes") != list(config.extra_index_urls)
    ):
        raise DependencyError("pn.lock doesn't match this app. Run 'pn deps --lock' to update it.")
    return value


def requirements(config: AppConfig, targets: Sequence[Target], *, direct: bool = False) -> str | None:
    """Build pip input containing exact versions and every allowed wheel hash."""
    document = read(config)
    if document is None:
        return None
    packages: dict[str, dict[str, Any]] = {}
    for target in targets:
        selected = document["targets"].get(target_key(target))
        if selected is None:
            raise DependencyError(f"pn.lock has no {target.label}. Run 'pn deps {target.platform} --lock'.")
        for package in selected["packages"]:
            key = re.sub(r"[-_.]+", "-", package["name"]).lower()
            old = packages.setdefault(key, package | {"hashes": set()})
            if old["version"] != package["version"]:
                raise DependencyError(
                    f"{key} resolves to different versions across architectures; pin one compatible version."
                )
            old["hashes"].add(package["sha256"])
    lines = ["--require-hashes"]
    for name, package in sorted(packages.items()):
        requirement = f"{name} @ {package['url']}" if direct else f"{name}=={package['version']}"
        lines.append(requirement + " " + " ".join(f"--hash=sha256:{digest}" for digest in sorted(package["hashes"])))
    return "\n".join(lines) + "\n"
