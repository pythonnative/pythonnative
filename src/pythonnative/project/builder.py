"""Build orchestration for PythonNative projects.

The [`Builder`][pythonnative.project.builder.Builder] ties the pieces
together: it stages the bundled native template, runs the platform
[`configurators`][pythonnative.project.android], stages the Python
sources and (on iOS) the embedded CPython runtime into the native
project, and invokes the native toolchains (Gradle / Xcode).

On iOS, the staged project is self-contained: ``Python.xcframework`` is
linked at build time and an Xcode build phase installs the standard
library and app code into the bundle, so ``xcodebuild`` output is
directly runnable and archivable with no post-build patching.

All shell-outs go through a small
[`CommandRunner`][pythonnative.project.builder.CommandRunner] abstraction
so the orchestration logic can be unit tested with a recording fake
instead of a real device toolchain. The default
[`SubprocessRunner`][pythonnative.project.builder.SubprocessRunner] simply
delegates to :mod:`subprocess`.

Device interaction that genuinely needs a device (booting simulators,
installing, launching, streaming logs, hot reload) lives in the CLI; the
builder stops at producing installable/archivable artifacts.
"""

from __future__ import annotations

import compileall
import os
import platform as platform_module
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Union

from . import android as android_config
from . import ios as ios_config
from . import plugins as native_plugins
from . import runtime_assets
from .android import AndroidLayout
from .config import AppConfig
from .ios import IOSLayout

Logger = Callable[[str], None]


class BuildError(Exception):
    """Raised when a native build step fails.

    Carries a user-facing message; the CLI prints it and exits non-zero.
    """


# ======================================================================
# Command runner abstraction
# ======================================================================


@dataclass
class CommandResult:
    """The outcome of a single command invocation.

    Attributes:
        returncode: Process exit status.
        stdout: Captured standard output (empty unless captured).
        stderr: Captured standard error (empty unless captured).
    """

    returncode: int
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        """Whether the command exited successfully (return code 0)."""
        return self.returncode == 0


class CommandRunner:
    """Protocol for running external commands.

    Implementations execute a command and return a
    [`CommandResult`][pythonnative.project.builder.CommandResult]. Tests
    provide a recording fake; production uses
    [`SubprocessRunner`][pythonnative.project.builder.SubprocessRunner].
    """

    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Optional[Path] = None,
        env: Optional[dict] = None,
        capture: bool = False,
    ) -> CommandResult:
        """Run a command.

        Args:
            args: The command and its arguments.
            cwd: Working directory, or ``None`` for the current one.
            env: Full environment mapping, or ``None`` to inherit.
            capture: Whether to capture and return stdout/stderr.

        Returns:
            A [`CommandResult`][pythonnative.project.builder.CommandResult].
        """
        raise NotImplementedError


class SubprocessRunner(CommandRunner):
    """A [`CommandRunner`][pythonnative.project.builder.CommandRunner] backed by :mod:`subprocess`."""

    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Optional[Path] = None,
        env: Optional[dict] = None,
        capture: bool = False,
    ) -> CommandResult:
        """Execute ``args`` with :func:`subprocess.run`."""
        completed = subprocess.run(
            list(args),
            cwd=str(cwd) if cwd else None,
            env=env,
            capture_output=capture,
            text=True,
        )
        return CommandResult(
            returncode=completed.returncode,
            stdout=completed.stdout or "" if capture else "",
            stderr=completed.stderr or "" if capture else "",
        )


# ======================================================================
# Result/state dataclasses
# ======================================================================


@dataclass
class PreparedProject:
    """A staged, configured project ready to build.

    Attributes:
        platform: ``"android"`` or ``"ios"``.
        build_dir: The ``build/<platform>`` directory.
        project_dir: The staged native project directory.
        app_id: The resolved application id / bundle id for the platform.
        android: Android layout (when ``platform == "android"``).
        ios: iOS layout (when ``platform == "ios"``).
    """

    platform: str
    build_dir: Path
    project_dir: Path
    app_id: str
    android: Optional[AndroidLayout] = None
    ios: Optional[IOSLayout] = None


@dataclass
class BuildArtifacts:
    """Paths to artifacts produced by a release/standalone build.

    Attributes:
        paths: Output artifact paths (APK/AAB/IPA/.app).
    """

    paths: List[Path] = field(default_factory=list)


# ======================================================================
# Template staging
# ======================================================================

_TEMPLATE_NAMES = {"android": "android_template", "ios": "ios_template"}

# A source checkout accumulates Gradle, SwiftPM, and Xcode outputs next to
# the native library sources; a staged project must start from a clean tree.
_TEMPLATE_IGNORE = shutil.ignore_patterns(
    "build",
    ".build",
    ".gradle",
    ".swiftpm",
    "xcuserdata",
    "DerivedData",
    "__pycache__",
    "*.pyc",
    ".DS_Store",
)


def stage_template(template_name: str, destination: Path) -> Path:
    """Copy a bundled native template into ``destination``.

    Resolution order mirrors the historical CLI: a local source checkout
    first (so dev edits take effect immediately), then installed package
    data via :mod:`importlib.resources`.

    Args:
        template_name: ``"android_template"`` or ``"ios_template"``.
        destination: Parent directory; the template lands at
            ``destination/<template_name>``.

    Returns:
        The path to the staged template directory.

    Raises:
        BuildError: If no bundled copy can be located.
    """
    dest_path = destination / template_name
    destination.mkdir(parents=True, exist_ok=True)

    # Dev-first: local source package templates.
    local = Path(__file__).resolve().parents[1] / "templates" / template_name
    if local.is_dir():
        shutil.copytree(local, dest_path, dirs_exist_ok=True, ignore=_TEMPLATE_IGNORE)
        return dest_path

    try:
        candidate = resources.files("pythonnative").joinpath("templates").joinpath(template_name)
        with resources.as_file(candidate) as resolved:
            if Path(resolved).is_dir():
                shutil.copytree(resolved, dest_path, dirs_exist_ok=True, ignore=_TEMPLATE_IGNORE)
                return dest_path
    except (ModuleNotFoundError, FileNotFoundError, OSError):
        pass

    raise BuildError(
        f"Could not find bundled template {template_name!r}. Reinstall pythonnative or run from a source checkout."
    )


# ======================================================================
# The builder
# ======================================================================


class Builder:
    """Stages, configures, and builds a PythonNative project.

    Args:
        config: The validated app configuration.
        runner: Command runner (defaults to
            [`SubprocessRunner`][pythonnative.project.builder.SubprocessRunner]).
        log: Progress logger (defaults to :func:`print`).
        build_root: Override for the ``build/`` directory.
        dev_lib_root: Override for the ``pythonnative`` package directory
            to bundle (defaults to the running package).
    """

    def __init__(
        self,
        config: AppConfig,
        *,
        runner: Optional[CommandRunner] = None,
        log: Optional[Logger] = None,
        build_root: Optional[Path] = None,
        dev_lib_root: Optional[Path] = None,
    ) -> None:
        self.config = config
        self.runner = runner or SubprocessRunner()
        self.log: Logger = log or print
        self.build_root = build_root or (config.project_root / "build")
        # The currently-running pythonnative package is bundled into the app
        # (works for both a source checkout and a pip install).
        self.dev_lib_root = dev_lib_root or Path(__file__).resolve().parents[1]

    # -- Preparation ----------------------------------------------------

    def prepare(self, platform: str, *, release: bool = False) -> PreparedProject:
        """Stage and configure the native project for ``platform``.

        Args:
            platform: ``"android"`` or ``"ios"``.
            release: Prepare for a release/store build. On iOS this
                byte-compiles the staged Python code and drops the
                ``.py`` sources from the bundle. (Chaquopy does the
                equivalent on Android automatically.)

        Returns:
            A [`PreparedProject`][pythonnative.project.builder.PreparedProject].

        Raises:
            BuildError: For an unknown platform or a staging failure.
        """
        if platform not in _TEMPLATE_NAMES:
            raise BuildError(f"Unknown platform: {platform!r} (expected 'android' or 'ios').")

        build_dir = self.build_root / platform
        build_dir.mkdir(parents=True, exist_ok=True)
        project_dir = stage_template(_TEMPLATE_NAMES[platform], build_dir)
        plugins = self._discover_plugins()

        if platform == "android":
            layout = android_config.configure(
                project_dir,
                self.config,
                dev_lib_root=self.dev_lib_root,
                log=self.log,
            )
            native_plugins.stage_android_plugins(project_dir, plugins, log=self.log)
            return PreparedProject(
                platform=platform,
                build_dir=build_dir,
                project_dir=project_dir,
                app_id=layout.application_id,
                android=layout,
            )

        ios_layout = ios_config.configure(project_dir, self.config, log=self.log)
        native_plugins.stage_ios_plugins(project_dir, plugins, log=self.log)
        self._stage_ios_python(project_dir, release=release)
        self._link_ios_runtime(project_dir)
        return PreparedProject(
            platform=platform,
            build_dir=build_dir,
            project_dir=project_dir,
            app_id=ios_layout.bundle_id,
            ios=ios_layout,
        )

    def _discover_plugins(self) -> List[native_plugins.NativePlugin]:
        """Collect native plugins from entry points and ``[plugins].paths``.

        Raises:
            BuildError: If a project-local plugin directory is invalid.
        """
        try:
            return native_plugins.discover_plugins(
                extra_paths=[self.config.resolve_path(p) for p in self.config.plugin_paths],
                log=self.log,
            )
        except native_plugins.PluginError as exc:
            raise BuildError(f"Invalid native plugin: {exc}") from exc

    def _stage_ios_python(self, project_dir: Path, *, release: bool) -> None:
        """Stage ``app/`` and ``app_packages/`` at the Xcode project root.

        The Xcode project references both folders as bundle resources
        and the "Install Python runtime" build phase converts any
        binary modules inside them into signed frameworks.
        """
        app_dir = project_dir / "app"
        packages_dir = project_dir / "app_packages"
        for directory in (app_dir, packages_dir):
            if directory.exists():
                shutil.rmtree(directory)
            directory.mkdir(parents=True, exist_ok=True)

        app_src = self.config.project_root / "app"
        if not app_src.is_dir():
            raise BuildError(f"No app/ directory found at {app_src}; nothing to bundle.")
        shutil.copytree(app_src, app_dir, dirs_exist_ok=True)

        if self.dev_lib_root.is_dir():
            shutil.copytree(
                self.dev_lib_root,
                packages_dir / "pythonnative",
                dirs_exist_ok=True,
                ignore=android_config.LIB_IGNORE,
            )

        # The framework has no Python-side native dependencies (the
        # bridge into PythonNativeKit is ctypes); only user requirements
        # are installed into the site directory.
        if self.config.requirements:
            result = self.runner.run(
                [sys.executable, "-m", "pip", "install", "-t", str(packages_dir), *self.config.requirements],
                capture=True,
            )
            if not result.ok:
                raise BuildError(f"pip install of [requirements].packages failed:\n{result.stderr}")

        if release:
            self._compile_ios_bytecode(app_dir, packages_dir)

    def _compile_ios_bytecode(self, *roots: Path) -> None:
        """Byte-compile staged Python code and drop the ``.py`` sources.

        Ships ``.pyc`` only: smaller bundles, faster cold start, and no
        plain-text source in the store artifact. Requires the host
        interpreter to match ``app.python_version``, since bytecode is
        version-specific.
        """
        host_version = f"{sys.version_info[0]}.{sys.version_info[1]}"
        if host_version != self.config.python_version:
            self.log(
                f"Skipping bytecode compilation: the build host runs Python {host_version} "
                f"but app.python_version is {self.config.python_version}, and bytecode is "
                "version-specific. The app will ship .py sources. Run pn with Python "
                f"{self.config.python_version} to ship bytecode."
            )
            return
        for root in roots:
            # legacy=True writes module.pyc next to module.py (no
            # __pycache__), which the embedded interpreter imports
            # directly once the .py files are gone.
            if not compileall.compile_dir(str(root), quiet=1, legacy=True, optimize=1):
                raise BuildError(f"Byte-compiling {root} failed; fix the syntax error above.")
            for source in root.rglob("*.py"):
                source.unlink()
        self.log("Compiled Python sources to bytecode for release.")

    def _link_ios_runtime(self, project_dir: Path) -> None:
        """Make ``Python.xcframework`` available at the project root.

        A symlink into the shared runtime cache is preferred (the
        framework is hundreds of megabytes); staging falls back to a
        copy when symlinks are unavailable.
        """
        runtime = self._ios_runtime()
        link = project_dir / "Python.xcframework"
        if link.is_symlink() or link.is_file():
            link.unlink()
        elif link.is_dir():
            shutil.rmtree(link)
        try:
            link.symlink_to(runtime.xcframework_dir, target_is_directory=True)
        except OSError:
            shutil.copytree(runtime.xcframework_dir, link)
        self.log(f"Linked Python.xcframework (Python {self.config.python_version}).")

    # -- Android builds -------------------------------------------------

    def install_android_debug(self, prepared: PreparedProject) -> None:
        """Build and install the debug APK on a connected device/emulator.

        Args:
            prepared: A prepared Android project.

        Raises:
            BuildError: If the Gradle build fails.
        """
        self._gradlew(prepared, ["installDebug"])

    def build_android(self, prepared: PreparedProject, *, debug: bool = False) -> BuildArtifacts:
        """Assemble standalone Android artifacts (APK + AAB).

        Args:
            prepared: A prepared Android project.
            debug: Build the debug variant instead of release.

        Returns:
            The produced artifact paths.

        Raises:
            BuildError: If the Gradle build fails.
        """
        if debug:
            self._gradlew(prepared, ["assembleDebug"])
            outputs = prepared.project_dir / "app" / "build" / "outputs"
            return BuildArtifacts(paths=_existing(outputs.rglob("*-debug.apk")))

        self._gradlew(prepared, ["assembleRelease", "bundleRelease"])
        outputs = prepared.project_dir / "app" / "build" / "outputs"
        candidates = list(outputs.rglob("*-release.apk")) + list(outputs.rglob("*-release.aab"))
        if not config_has_android_signing(self.config):
            candidates += list(outputs.rglob("*-release-unsigned.apk"))
        return BuildArtifacts(paths=_existing(candidates))

    def _gradlew(self, prepared: PreparedProject, tasks: Sequence[str]) -> None:
        gradlew = prepared.project_dir / "gradlew"
        if gradlew.exists():
            os.chmod(gradlew, 0o755)
        env = self._android_env()
        result = self.runner.run(["./gradlew", *tasks], cwd=prepared.project_dir, env=env)
        if not result.ok:
            raise BuildError(f"Gradle build failed ({' '.join(tasks)}). See output above.")

    def _android_env(self) -> dict:
        env = dict(os.environ)
        if sys.platform == "darwin" and not env.get("JAVA_HOME"):
            try:
                jdk = subprocess.check_output(["brew", "--prefix", "openjdk@17"], text=True).strip()
                if jdk:
                    env["JAVA_HOME"] = jdk
            except Exception:
                pass
        return env

    # -- iOS builds -----------------------------------------------------

    def build_ios_simulator(self, prepared: PreparedProject) -> Path:
        """Build the iOS app for the simulator.

        The Xcode build produces a complete, runnable ``.app``: the
        Python framework is linked and the "Install Python runtime"
        build phase embeds the standard library and staged sources.

        Args:
            prepared: A prepared iOS project.

        Returns:
            Path to the built ``.app``.

        Raises:
            BuildError: If the build fails.
        """
        derived = prepared.project_dir / "build"
        settings = ios_config.build_settings(self.config)
        # The simulator runs on the host CPU, and BeeWare's runtime
        # install script requires a single-architecture build (its
        # stdlib layout is per-arch), so pin ARCHS to the host.
        host_arch = "arm64" if platform_module.machine() == "arm64" else "x86_64"
        settings.append(f"ARCHS={host_arch}")
        result = self.runner.run(
            [
                "xcodebuild",
                "-project",
                ios_config.PROJECT_FILE,
                "-scheme",
                ios_config.PROJECT_NAME,
                "-configuration",
                "Debug",
                "-destination",
                "generic/platform=iOS Simulator",
                "-derivedDataPath",
                str(derived),
                "build",
                *settings,
            ],
            cwd=prepared.project_dir,
        )
        if not result.ok:
            raise BuildError("xcodebuild (simulator) failed. See output above.")

        app_path = derived / "Build" / "Products" / "Debug-iphonesimulator" / ios_config.APP_BUNDLE_NAME
        if not app_path.is_dir():
            raise BuildError(f"Built app not found at {app_path}.")
        return app_path

    def build_ios_device(self, prepared: PreparedProject) -> Path:
        """Build a signed Debug app for a physical iOS device.

        Requires ``[ios].development_team`` for automatic signing.

        Args:
            prepared: A prepared iOS project.

        Returns:
            Path to the built ``.app``.

        Raises:
            BuildError: If the build fails or signing is not set up.
        """
        if not self.config.ios.development_team:
            raise BuildError(
                "Running on a physical iOS device requires code signing. "
                "Set [ios].development_team in pythonnative.toml."
            )
        derived = prepared.project_dir / "build"
        settings = ios_config.build_settings(self.config)
        settings.append("-allowProvisioningUpdates")
        result = self.runner.run(
            [
                "xcodebuild",
                "-project",
                ios_config.PROJECT_FILE,
                "-scheme",
                ios_config.PROJECT_NAME,
                "-configuration",
                "Debug",
                "-destination",
                "generic/platform=iOS",
                "-derivedDataPath",
                str(derived),
                "build",
                *settings,
            ],
            cwd=prepared.project_dir,
        )
        if not result.ok:
            raise BuildError("xcodebuild (device) failed. See output above.")

        app_path = derived / "Build" / "Products" / "Debug-iphoneos" / ios_config.APP_BUNDLE_NAME
        if not app_path.is_dir():
            raise BuildError(f"Built app not found at {app_path}.")
        return app_path

    def build_ios_archive(self, prepared: PreparedProject, *, upload: bool = False) -> BuildArtifacts:
        """Archive the iOS app and export a signed IPA (or upload it).

        Args:
            prepared: A prepared iOS project (use ``release=True``).
            upload: Upload directly to App Store Connect instead of
                exporting a local ``.ipa`` (requires
                ``export_method = "app-store"`` and stored ASC
                credentials in Xcode).

        Returns:
            The produced ``.ipa`` (and ``.xcarchive``) paths.

        Raises:
            BuildError: If archiving or export fails.
        """
        archive_path = prepared.build_dir / "ios_template.xcarchive"
        settings = ios_config.build_settings(self.config, for_archive=True)
        result = self.runner.run(
            [
                "xcodebuild",
                "-project",
                ios_config.PROJECT_FILE,
                "-scheme",
                ios_config.PROJECT_NAME,
                "-configuration",
                "Release",
                "-destination",
                "generic/platform=iOS",
                "-archivePath",
                str(archive_path),
                "-allowProvisioningUpdates",
                "archive",
                *settings,
            ],
            cwd=prepared.project_dir,
        )
        if not result.ok:
            raise BuildError("xcodebuild archive failed. See output above.")

        export_dir = prepared.build_dir / "export"
        options = ios_config.write_export_options(
            self.config, prepared.build_dir / "exportOptions.plist", upload=upload
        )
        result = self.runner.run(
            [
                "xcodebuild",
                "-exportArchive",
                "-archivePath",
                str(archive_path),
                "-exportOptionsPlist",
                str(options),
                "-exportPath",
                str(export_dir),
                "-allowProvisioningUpdates",
            ],
            cwd=prepared.project_dir,
        )
        if not result.ok:
            raise BuildError("xcodebuild -exportArchive failed. Check signing settings in [ios.signing].")

        return BuildArtifacts(paths=_existing(list(export_dir.rglob("*.ipa")) + [archive_path]))

    def _ios_runtime(self) -> runtime_assets.IOSRuntime:
        cache = self.build_root / "ios_runtime"
        try:
            return runtime_assets.prepare_ios_runtime(cache, self.config.python_version, log=self.log)
        except RuntimeError as exc:
            raise BuildError(str(exc)) from exc


# ======================================================================
# Helpers
# ======================================================================


def config_has_android_signing(config: AppConfig) -> bool:
    """Return whether the config defines an Android release signing key.

    Args:
        config: The app configuration.

    Returns:
        ``True`` if a keystore and alias are configured.
    """
    return config.android.signing.is_configured


def _existing(paths: Union[Sequence[Path], object]) -> List[Path]:
    result: List[Path] = []
    for path in paths:  # type: ignore[union-attr]
        candidate = Path(path)
        if candidate.exists() and candidate not in result:
            result.append(candidate)
    return result
