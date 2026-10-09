"""Distribution validation, partial-upload recovery, and release app-bundle contents."""

import ast
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any, Iterator, List, Optional, Set, Tuple

import pytest


def load_script(name: str) -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = load_script("check-distributions")
assets = load_script("release-assets")
VERSION = "0.40.0"
METADATA = f"Metadata-Version: 2.4\nName: pythonnative\nVersion: {VERSION}\n"
PLATFORMS = [
    "manylinux_2_28_x86_64",
    "manylinux_2_28_aarch64",
    "macosx_11_0_x86_64",
    "macosx_11_0_arm64",
    "win_amd64",
]


def wheel_files(python: str, platform: str) -> dict[str, bytes]:
    suffix = "pyd" if platform == "win_amd64" else "so"
    return {
        **dict.fromkeys(checker.PACKAGE_FILES, b"resource"),
        f"pythonnative/_yoga.{python}.{suffix}": b"native library",
        f"pythonnative-{VERSION}.dist-info/METADATA": METADATA.encode(),
        f"pythonnative-{VERSION}.dist-info/WHEEL": (
            f"Wheel-Version: 1.0\nRoot-Is-Purelib: false\nTag: {python}-{python}-{platform}\n".encode()
        ),
    }


def write_wheel(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)


@pytest.fixture
def distributions(tmp_path: Path) -> Path:
    for python in ("cp313", "cp314"):
        for platform in PLATFORMS:
            write_wheel(
                tmp_path / f"pythonnative-{VERSION}-{python}-{python}-{platform}.whl",
                wheel_files(python, platform),
            )
    source_files = {
        **dict.fromkeys(("src/" + name for name in checker.PACKAGE_FILES), b"source"),
        "setup.py": b"build configuration",
        "tests/test_layout.py": b"layout tests",
        "PKG-INFO": METADATA.encode(),
        "pyproject.toml": f'[project]\nversion = "{VERSION}"\n'.encode(),
    }
    with tarfile.open(tmp_path / f"pythonnative-{VERSION}.tar.gz", "w:gz") as archive:
        for name, data in source_files.items():
            info = tarfile.TarInfo(f"pythonnative-{VERSION}/{name}")
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return tmp_path


def test_complete_distribution_matrix(distributions: Path) -> None:
    checker.check_distributions(distributions, VERSION)


def test_original_linux_wheel_rejection(distributions: Path) -> None:
    path = next(distributions.glob("*cp314-cp314-manylinux_2_28_x86_64.whl"))
    path.rename(path.with_name(path.name.replace("manylinux_2_28", "linux")))
    with pytest.raises(ValueError, match="Unsupported release platform tag: linux_x86_64"):
        checker.check_distributions(distributions, VERSION)


@pytest.mark.parametrize("pattern", ["*cp313-cp313-win_amd64.whl", "*.tar.gz"])
def test_missing_artifact_blocks_publish(distributions: Path, pattern: str) -> None:
    next(distributions.glob(pattern)).unlink()
    with pytest.raises(ValueError, match="Incomplete release"):
        checker.check_distributions(distributions, VERSION)


@pytest.mark.parametrize("damage", ["version", "tags", "pure", "extension", "resource"])
def test_bad_wheel_contents_block_publish(distributions: Path, damage: str) -> None:
    path = next(distributions.glob("*cp313-cp313-win_amd64.whl"))
    files = wheel_files("cp313", "win_amd64")
    metadata = f"pythonnative-{VERSION}.dist-info/METADATA"
    wheel = f"pythonnative-{VERSION}.dist-info/WHEEL"
    if damage == "version":
        files[metadata] = files[metadata].replace(b"0.40.0", b"0.39.0")
    elif damage == "tags":
        files[wheel] = files[wheel].replace(b"win_amd64", b"linux_x86_64")
    elif damage == "pure":
        files[wheel] = files[wheel].replace(b"false", b"true")
    elif damage == "extension":
        del files["pythonnative/_yoga.cp313.pyd"]
    else:
        del files["pythonnative/native/yoga/yoga/Yoga.h"]
    write_wheel(path, files)
    with pytest.raises(ValueError):
        checker.check_distributions(distributions, VERSION)


@pytest.mark.parametrize("platform", ["linux_x86_64", "any", "manylinux_2_39_x86_64", "macosx_15_0_arm64"])
def test_incompatible_platforms(platform: str) -> None:
    with pytest.raises(ValueError, match="Unsupported release platform"):
        checker.platform_family(platform)


def test_recovery_reuses_original_bytes_after_partial_upload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = tmp_path / "pythonnative-0.40.0-cp313-cp313-win_amd64.whl"
    second = tmp_path / "pythonnative-0.40.0.tar.gz"
    first.write_bytes(b"original wheel")
    second.write_bytes(b"original source")
    remote: dict[str, bytes] = {}
    fail_upload = True

    def gh(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert command[:2] == ["gh", "release"]
        action = command[2]
        if action == "view":
            return subprocess.CompletedProcess(command, 0, json.dumps({"assets": [{"name": n} for n in remote]}))
        if action == "upload":
            path = Path(command[4])
            if fail_upload and path == second:
                raise subprocess.CalledProcessError(1, command)
            assert path.name not in remote, "Recovery must never overwrite a published asset"
            remote[path.name] = path.read_bytes()
        elif action == "download":
            name = command[command.index("--pattern") + 1]
            (Path(command[command.index("--dir") + 1]) / name).write_bytes(remote[name])
        else:
            pytest.fail(f"Unexpected gh command: {command}")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(assets.subprocess, "run", gh)
    with pytest.raises(subprocess.CalledProcessError):
        assets.sync_assets("v0.40.0", tmp_path)
    assert remote == {first.name: b"original wheel"}
    first.write_bytes(b"rebuilt wheel with a different timestamp")
    fail_upload = False
    assets.sync_assets("v0.40.0", tmp_path)
    assert first.read_bytes() == b"original wheel"
    assert remote[second.name] == b"original source"
    assets.sync_assets("v0.40.0", tmp_path)
    assert first.read_bytes() == b"original wheel"


# ======================================================================
# Release app bundles: development modules stay out
# ======================================================================

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "src" / "pythonnative"

# Function-local imports of development modules that remain in release
# bundles. Each runs only on a development path, so a release app never
# executes it: ``(importing module, enclosing function, imported module)``.
DEV_ONLY_LAZY_IMPORTS = {
    # `start(dev=True)` starts the dev client; release templates pass False.
    ("pythonnative.bootstrap", "start", "pythonnative.devclient"),
    # Fast Refresh fingerprint; guarded by `except ImportError` for release.
    ("pythonnative.component", "_hook_signature", "pythonnative.refresh"),
    # Hot reload entry points, called only by the dev client and preview.
    ("pythonnative.hosts.base", "ScreenHost.reload", "pythonnative.hot_reload"),
    ("pythonnative.hosts.base", "ScreenHost._try_fast_refresh", "pythonnative.hot_reload"),
    # Error-screen editor links; the host event exists only in dev mode and
    # the handler returns before importing when dev mode is off.
    ("pythonnative.hosts.native", "_open_in_editor", "pythonnative.devtools"),
    # Contract derivation; only a development checkout whose generated
    # `_builtin_contracts.json` predates a protocol change reaches it.
    ("pythonnative.components", "_install_contracts", "pythonnative.sdk.builtins"),
}


def _module_name(root: Path, path: Path) -> str:
    parts = list(path.relative_to(root.parent).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _is_type_checking(node: ast.AST) -> bool:
    test = node.test if isinstance(node, ast.If) else None
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def _imports(root: Path, path: Path) -> Iterator[Tuple[str, Optional[str], Set[str]]]:
    """Yield ``(module, enclosing function or None, imported names)`` for each import in ``path``.

    Imported names include ``package.name`` for ``from package import name``,
    since ``name`` may be a submodule. Imports under ``if TYPE_CHECKING:`` are skipped.
    """
    module = _module_name(root, path)
    package = module if path.name == "__init__.py" else module.rpartition(".")[0]
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def visit(node: ast.AST, scope: List[str], in_function: bool) -> Iterator[Tuple[str, Optional[str], Set[str]]]:
        for child in ast.iter_child_nodes(node):
            if _is_type_checking(child):
                continue
            if isinstance(child, ast.Import):
                yield module, ".".join(scope) if in_function else None, {alias.name for alias in child.names}
            elif isinstance(child, ast.ImportFrom):
                if child.level:
                    base = package.split(".")[: len(package.split(".")) - (child.level - 1)]
                    target = ".".join(base + ([child.module] if child.module else []))
                else:
                    target = child.module or ""
                names = {target} | {f"{target}.{alias.name}" for alias in child.names}
                yield module, ".".join(scope) if in_function else None, names
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield from visit(child, scope + [child.name], True)
            elif isinstance(child, ast.ClassDef):
                yield from visit(child, scope + [child.name], in_function)
            else:
                yield from visit(child, scope, in_function)

    yield from visit(tree, [], False)


@pytest.fixture(scope="module")
def release_bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    from pythonnative.project.bundle import copy_library

    destination = tmp_path_factory.mktemp("release") / "pythonnative"
    copy_library(PACKAGE_ROOT, destination, release=True)
    return destination


def _modules(root: Path) -> Set[str]:
    return {_module_name(root, path) for path in root.rglob("*.py")}


def test_release_bundle_omits_development_modules(release_bundle: Path) -> None:
    from pythonnative.project.bundle import DEV_ONLY_PATHS

    for rel in DEV_ONLY_PATHS:
        assert (PACKAGE_ROOT / rel).exists(), f"stale entry in DEV_ONLY_PATHS: {rel}"
        assert not (release_bundle / rel).exists(), rel
    shipped = _modules(release_bundle)
    for name in ("pythonnative", "pythonnative.bootstrap", "pythonnative.component", "pythonnative.sdk.schema"):
        assert name in shipped
    assert not any(path.suffix in (".so", ".pyc") or path.name == "__pycache__" for path in release_bundle.rglob("*"))


def test_release_bundle_never_imports_development_modules(release_bundle: Path) -> None:
    excluded = _modules(PACKAGE_ROOT) - _modules(release_bundle)
    assert "pythonnative.devclient" in excluded and "pythonnative.cli.pn" in excluded

    def is_excluded(name: str) -> bool:
        return any(name == module or name.startswith(module + ".") for module in excluded)

    top_level: List[str] = []
    lazy: Set[Tuple[str, str, str]] = set()
    for path in sorted(release_bundle.rglob("*.py")):
        for module, function, names in _imports(release_bundle, path):
            for name in sorted(n for n in names if is_excluded(n)):
                if function is None:
                    top_level.append(f"{module} imports {name}")
                else:
                    lazy.add((module, function, name))
    # Collapse `from pkg import name` pairs onto the module actually imported.
    lazy = {entry for entry in lazy if not any(entry[2].startswith(other[2] + ".") for other in lazy if other != entry)}
    assert top_level == [], "release bundles would fail to import:\n" + "\n".join(top_level)
    unexpected = lazy - DEV_ONLY_LAZY_IMPORTS
    assert not unexpected, f"new lazy imports of development modules (allowlist them only if dev-only): {unexpected}"
    stale = DEV_ONLY_LAZY_IMPORTS - lazy
    assert not stale, f"stale DEV_ONLY_LAZY_IMPORTS entries: {stale}"


def test_debug_bundle_keeps_development_modules(tmp_path: Path) -> None:
    from pythonnative.project.bundle import copy_library

    destination = tmp_path / "pythonnative"
    (destination / "stale.py").parent.mkdir(parents=True)
    (destination / "stale.py").write_text("")
    copy_library(PACKAGE_ROOT, destination, release=False)
    assert not (destination / "stale.py").exists()
    for rel in ("devclient.py", "hot_reload.py", "refresh.py", "devserver/ws.py", "devserver/static/index.html"):
        assert (destination / rel).exists(), rel
    assert not (destination / "templates").exists()
    assert not (destination / "native").exists()


def test_release_runtime_imports_without_development_modules(release_bundle: Path, tmp_path: Path) -> None:
    """The runtime (and a component definition) imports from a release bundle in a fresh interpreter."""
    site = tmp_path / "site"
    site.mkdir()
    shutil.copytree(release_bundle, site / "pythonnative")
    script = (
        "import sys; sys.path.insert(0, sys.argv[1]);"
        "import pythonnative as pn, pythonnative.bootstrap, pythonnative.sdk.schema;"
        "assert pn.__file__.startswith(sys.argv[1]), pn.__file__;"
        "Hello = pn.component(lambda: pn.Text('hi'));"
        "assert Hello.refresh_signature is None;"
        "import importlib.util as u;"
        "assert u.find_spec('pythonnative.devclient') is None;"
        "assert u.find_spec('pythonnative.hot_reload') is None"
    )
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PN_PLATFORM")}
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script, str(site)], capture_output=True, text=True, env=env, cwd=tmp_path
    )
    assert result.returncode == 0, result.stderr
