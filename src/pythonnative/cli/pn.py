"""`pn` CLI: scaffold, diagnose, start, run, and build PythonNative apps.

The console script `pn` (declared in `pyproject.toml`) dispatches to:

- `pn init [name]`: scaffold a new project (``pythonnative.toml`` +
  ``app/``) into ``./name/``, or into the current directory when no name
  is given.
- `pn doctor [platform]`: diagnose the local toolchain and config.
- `pn deps [platform]`: resolve ``[requirements].packages`` for every
  device target and report which wheels would be used (or why a package
  can't be installed), without building anything.
- `pn start`: run the dev server. It renders the app in a browser tab
  and syncs every save to every connected debug build (simulators,
  emulators, physical devices) with Fast Refresh; device logs stream
  back into the same terminal.
- `pn preview`: `pn start` plus opening the browser preview.
- `pn devices [platform]`: list connected devices, emulators, and
  simulators, as a table or as JSON with `--json`.
- `pn run android|ios [--device D]`: stage + build + install + launch a
  debug build that connects to the dev server. The native project is
  only rebuilt when something outside ``app/`` changed.
- `pn logs android|ios [--device D]`: stream logs from the running app
  without rebuilding.
- `pn build android|ios`: produce standalone artifacts (signed APK/AAB,
  or an iOS archive/IPA, optionally uploaded to App Store Connect).
- `pn app-id android|ios`: print the resolved application/bundle id
  (handy for scripts and CI).
- `pn clean`: remove the local `build/` directory.

The heavy lifting lives in the ``pythonnative.project`` and
``pythonnative.devserver`` packages; this module is a thin,
side-effect-y shell that wires arguments to them and handles the
device-facing steps (simulator boot, launch, log streaming) that can't
be unit tested.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import shutil
import subprocess
import sys
from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, TextIO
from urllib.request import urlopen

from ..project import builder as builder_mod
from ..project import deps as deps_mod
from ..project import devices as devices_mod
from ..project import doctor as doctor_mod
from ..project import fingerprint as fingerprint_mod
from ..project.android import collect_logcat_filters
from ..project.config import CONFIG_FILENAME, AppConfig, ConfigError, render_default_toml

DEFAULT_DEV_PORT = 8765
"""Port `pn start` listens on unless `--port` says otherwise."""


# ======================================================================
# init
# ======================================================================

_MAIN_TEMPLATE = """from typing import TypedDict

import pythonnative as pn

Stack = pn.create_stack_navigator()


class DetailParams(TypedDict):
    count: int


@pn.component
def HomeScreen():
    count, set_count = pn.use_state(0)
    nav = pn.use_navigation()
    theme = pn.use_theme()
    return pn.ScrollView(
        pn.Column(
            pn.Text("Hello from PythonNative!", style={"font_size": theme.font_size_title, "bold": True}),
            pn.Text(f"Tapped {count} times"),
            pn.Button("Tap me", on_press=lambda: set_count(count + 1)),
            pn.Button("Open detail", on_press=lambda: nav.navigate("Detail", count=count)),
            style={"spacing": theme.spacing_large, "padding": 16, "align_items": "stretch"},
        )
    )


@pn.component
def DetailScreen():
    nav = pn.use_navigation()
    route = pn.use_route(DetailParams)
    return pn.Column(
        pn.Text(f"Detail: count was {route.params['count']}", style={"font_size": 20}),
        pn.Button("Back", on_press=nav.go_back),
        style={"spacing": 12, "padding": 16},
    )


@pn.component
def App():
    return pn.NavigationContainer(
        Stack.Navigator(
            Stack.Screen("Home", HomeScreen, title="Home"),
            Stack.Screen("Detail", DetailScreen, title="Detail"),
        )
    )
"""

_GITIGNORE = "# PythonNative\n__pycache__/\n*.pyc\n.venv/\nbuild/\n.DS_Store\n"


_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
"""Legal ``pn init`` project names, in the spirit of ``flutter create`` / ``cargo new``."""

_FALLBACK_NAME = "my_app"


def _sanitize_name(name: str) -> str:
    """Return a legal project name derived from ``name``.

    Lowercases, collapses each run of illegal characters to one
    underscore, trims leading and trailing ``_`` and ``-``, and prefixes
    a name that doesn't start with a letter. The result always matches
    ``_NAME_RE``, falling back to ``_FALLBACK_NAME`` when nothing usable
    survives.

    Args:
        name: The rejected name, which may be empty.

    Returns:
        A name suitable for suggesting back to the user.
    """
    slug = re.sub(r"[^a-z0-9_-]+", "_", name.lower()).strip("_-")
    if not slug:
        return _FALLBACK_NAME
    if not slug[0].isascii() or not slug[0].isalpha():
        slug = f"app_{slug}"
    return slug


def _app_id_from_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9_]", "", name.lower())
    if not slug or not slug[0].isalpha():
        slug = "app" + slug
    return f"com.example.{slug}"


def init_project(args: argparse.Namespace) -> None:
    """Scaffold a new PythonNative project.

    Given a name, this creates ``./<name>/`` and scaffolds into it. Without
    one, it scaffolds into the current directory and names the project after
    it. Either way it writes ``app/main.py``, ``pythonnative.toml``, and
    ``.gitignore``.

    A name you pass has to match ``^[a-z][a-z0-9_-]*$``: lowercase letters,
    digits, ``-``, and ``_``, starting with a letter. Anything else is
    refused with a legal suggestion. That keeps the directory name and the
    ``name`` field in the generated config identical, in the same spirit as
    ``flutter create`` and ``cargo new``. The name taken from the current
    directory when you pass none is used as-is, so an existing directory
    with any name still works.

    The name also has to be a single directory name, so the project always
    lands inside the current directory. Anything that reads as a path, such
    as ``a/b``, ``..``, or ``/tmp/app``, is refused, and so is a name that
    resolves somewhere else, such as a symlink to another directory.

    It won't scaffold into a target directory that already holds files, and it
    won't overwrite any of the three paths above; pass ``--force`` to override
    both. An existing but empty target directory is fine. A plain file at
    ``./<name>`` is always refused, since ``--force`` can't turn it into a
    directory, and ``--force`` lifts neither of the rules above.

    Args:
        args: Parsed namespace with ``name`` (optional) and ``force``.
    """
    name: Optional[str] = getattr(args, "name", None)
    force: bool = getattr(args, "force", False)

    # Lexical check, before anything reads the filesystem. ``Path("..").name``
    # is "..", so ".." needs naming explicitly; the rest (absolute, nested,
    # trailing separator, ".") fall out of the name check.
    if name and (name in (os.curdir, os.pardir) or Path(name).name != name):
        print(f"Refusing to treat a path as a project name: {name!r}. Use a single directory name like my_app.")
        sys.exit(1)

    # Charset check, still lexical, so it stays ahead of ``Path.cwd()`` below.
    # ``is not None`` rather than truthiness: "" is invalid under the pattern,
    # and falling through to the no-name path would silently scaffold here.
    # ``fullmatch``, not ``match``: ``$`` also matches before a trailing
    # newline, so ``match`` would accept "app\n" and create a directory
    # whose name contains one.
    if name is not None and not _NAME_RE.fullmatch(name):
        print(
            f"Invalid project name: {name!r}. Use lowercase letters, digits, '-', and '_', "
            f"starting with a letter. Try: {_sanitize_name(name)}"
        )
        sys.exit(1)

    cwd = Path.cwd()
    target = cwd / name if name else cwd
    project_name: str = name or cwd.name

    # A lexically clean name can still resolve elsewhere, and ``exists()`` and
    # ``is_dir()`` below follow symlinks. Check containment rather than just
    # ``is_symlink()`` so the whole class is closed, not one spelling of it.
    if name and (target.is_symlink() or target.resolve().parent != cwd.resolve()):
        print(
            f"Refusing to scaffold through a link or outside the current directory: {name}. Use a plain directory name."
        )
        sys.exit(1)

    app_dir = target / "app"
    config_path = target / CONFIG_FILENAME
    gitignore_path = target / ".gitignore"

    if name and target.exists():
        if not target.is_dir():
            print(f"Refusing to overwrite existing file: {name}. Remove it or choose a different name.")
            sys.exit(1)
        if any(target.iterdir()) and not force:
            print(f"Refusing to overwrite existing non-empty directory: {name}/. Use --force to overwrite.")
            sys.exit(1)

    if not force:
        existing = [
            label
            for label, path in (("app/", app_dir), (CONFIG_FILENAME, config_path), (".gitignore", gitignore_path))
            if path.exists()
        ]
        if existing:
            print(f"Refusing to overwrite existing: {', '.join(existing)}. Use --force to overwrite.")
            sys.exit(1)

    app_dir.mkdir(parents=True, exist_ok=True)
    main_py = app_dir / "main.py"
    if force or not main_py.exists():
        main_py.write_text(_MAIN_TEMPLATE, encoding="utf-8")

    config_path.write_text(
        render_default_toml(name=project_name, app_id=_app_id_from_name(project_name)),
        encoding="utf-8",
    )
    if force or not gitignore_path.exists():
        gitignore_path.write_text(_GITIGNORE, encoding="utf-8")

    print(f"Initialized PythonNative project in {target}.")
    next_steps = "pn start   (browser preview + dev server)   |   pn run android   |   pn run ios"
    if name:
        next_steps = f"cd {name}   |   {next_steps}"
    print(f"Next: {next_steps}")


# ======================================================================
# doctor / app-id
# ======================================================================


def doctor_command(args: argparse.Namespace) -> None:
    """Run toolchain/config diagnostics and exit non-zero on errors.

    Args:
        args: Parsed namespace with optional ``platform``.
    """
    platform: Optional[str] = getattr(args, "platform", None)
    results = doctor_mod.run_doctor(Path.cwd(), platform=platform)
    print("PythonNative doctor\n")
    for result in results:
        print(result.format())
    level = doctor_mod.worst_level(results)
    print()
    if level == doctor_mod.ERROR:
        print("Found problems that will block builds. Address the [x] items above.")
        sys.exit(1)
    if level == doctor_mod.WARN:
        print("Ready, with warnings. Review the [!] items above.")
    else:
        print("Everything looks good.")


def app_id_command(args: argparse.Namespace) -> None:
    """Print the resolved application id (Android) or bundle id (iOS).

    Args:
        args: Parsed namespace with ``platform``.
    """
    config = _load_config_or_exit()
    print(config.application_id if args.platform == "android" else config.bundle_id)


# ======================================================================
# deps
# ======================================================================


def deps_command(args: argparse.Namespace) -> None:
    """Report how ``[requirements].packages`` resolve for each device target.

    Runs pip in its cross-platform dry-run mode once per target (iOS
    device, iOS Simulator, and one per Android ABI) and prints the
    wheel each package would use, flagging binary wheels and their
    source index. Exits non-zero when any target can't be satisfied,
    so it doubles as a CI gate. ``--json`` emits the same data as a
    machine-readable document.

    Args:
        args: Parsed namespace with optional ``platform``, ``json``, and
            ``python`` (the interpreter to run pip with).
    """
    platform: Optional[str] = getattr(args, "platform", None)
    as_json: bool = getattr(args, "json", False)
    python: Optional[str] = getattr(args, "python", None)

    config = _load_config_or_exit()
    targets = deps_mod.targets_for(config, platform)
    runner = builder_mod.SubprocessRunner()
    if not as_json and config.requirements:
        print(
            f"Resolving {len(config.requirements)} requirement(s) for Python {config.python_version} "
            f"across {len(targets)} target(s)...\n"
        )
    resolutions = deps_mod.resolve_all(config, targets, runner=runner, python=python)

    if as_json:
        print(
            json.dumps(
                {
                    "python_version": config.python_version,
                    "requirements": list(config.requirements),
                    "targets": [res.to_dict() for res in resolutions],
                },
                indent=2,
            )
        )
    else:
        print(deps_mod.format_report(resolutions, requirements=config.requirements))
    if any(not res.ok for res in resolutions):
        sys.exit(1)


# ======================================================================
# start / preview
# ======================================================================


def start_command(args: argparse.Namespace, *, open_browser: bool = False) -> None:
    """Run the dev server (and the browser preview) for the current project.

    Re-execs under ``PN_PLATFORM=web`` so every module binds to the
    browser backend, then hands off to ``pythonnative.preview.serve``.

    Args:
        args: Parsed namespace (``entry``, ``host``, ``port``, ``open``,
            ``no_open``).
        open_browser: Open the preview page once the server is up
            (``pn preview`` sets this; ``--open`` does too).
    """
    if os.environ.get("PN_PLATFORM") != "web":
        try:
            completed = subprocess.run(
                [sys.executable, "-m", "pythonnative.cli.pn", *sys.argv[1:]],
                env={**os.environ, "PN_PLATFORM": "web"},
            )
        except KeyboardInterrupt:
            sys.exit(130)
        sys.exit(completed.returncode)

    project_dir = Path.cwd()
    entry: Optional[str] = getattr(args, "entry", None)
    project_name = ""
    requirements: List[str] = []
    try:
        config = AppConfig.load(project_dir)
        entry = entry or config.entry_module
        project_name = config.name
        requirements = list(config.requirements)
    except ConfigError:
        entry = entry or "app.main"
    missing = _missing_requirements(requirements)
    if missing:
        print(f"Warning: {', '.join(missing)} from [requirements] is not installed in this Python environment.")
        print(
            "         The browser preview imports your app here, so install it first (e.g. `pip install "
            + " ".join(missing)
            + "`)."
        )
    if not (project_dir / "app").is_dir():
        print(f"Error: no app/ directory in {project_dir}. Run 'pn init' first or cd into a PythonNative project.")
        sys.exit(1)

    from pythonnative.preview import serve

    open_browser = open_browser or bool(getattr(args, "open", False))
    if getattr(args, "no_open", False):
        open_browser = False
    try:
        serve(
            entry,
            project_root=str(project_dir),
            host=getattr(args, "host", "0.0.0.0") or "0.0.0.0",
            port=int(getattr(args, "port", DEFAULT_DEV_PORT) or 0),
            project_name=project_name,
            open_browser=open_browser,
        )
    except OSError as exc:
        print(f"Error: could not start the dev server: {exc}")
        print("Is another 'pn start' running? Pick a different port with --port.")
        sys.exit(1)
    except RuntimeError as exc:
        print(f"Error: {exc}")
        sys.exit(1)


def _missing_requirements(requirements: Sequence[str]) -> List[str]:
    """Names from ``[requirements]`` that aren't installed in this interpreter.

    Requirement strings may carry version specifiers or extras
    (``"httpx[http2]>=0.27"``); only the distribution name is checked.
    """
    import importlib.metadata as metadata

    missing: List[str] = []
    for requirement in requirements:
        name = re.split(r"[\s\[<>=!~;@]", requirement.strip(), maxsplit=1)[0]
        if not name:
            continue
        try:
            metadata.distribution(name)
        except metadata.PackageNotFoundError:
            missing.append(name)
    return missing


def preview_command(args: argparse.Namespace) -> None:
    """``pn preview``: ``pn start`` that also opens the browser preview."""
    start_command(args, open_browser=True)


def _running_dev_server(port: int) -> Optional[Dict[str, Any]]:
    """Return ``/status`` of a dev server on ``localhost:port``, or ``None``."""
    try:
        with urlopen(f"http://127.0.0.1:{port}/status", timeout=0.5) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


# ======================================================================
# devices
# ======================================================================


def _print_no_devices_hints(stream: TextIO) -> None:
    """Print the "no devices" guidance to ``stream``.

    Shared by both output modes so the wording can't drift between the
    table (which sends it to stdout) and ``--json`` (stderr).

    Args:
        stream: Where to write, ``sys.stdout`` or ``sys.stderr``.
    """
    print("No devices found.", file=stream)
    print("Android: start an emulator or connect a device with USB debugging enabled.", file=stream)
    print("iOS: open Xcode once to install Simulators, or plug in a device.", file=stream)


def devices_command(args: argparse.Namespace) -> None:
    """List connected devices, emulators, and simulators.

    Prints an aligned table and exits 1 when nothing is connected.

    With ``--json``, stdout carries a JSON array and nothing else, one
    object per device (see ``Device.to_dict``), so it stays parseable.
    The "no devices" hints go to stderr instead, an empty result prints
    ``[]``, and the exit status is 0 either way, since "no devices" is a
    valid answer for a script rather than a failure.

    Args:
        args: Parsed namespace with optional ``platform`` and ``json``.
    """
    platform: Optional[str] = getattr(args, "platform", None)
    as_json: bool = getattr(args, "json", False)
    devices = devices_mod.list_devices(platform)

    if as_json:
        if not devices:
            _print_no_devices_hints(sys.stderr)
        print(json.dumps([device.to_dict() for device in devices], indent=2))
        return

    if not devices:
        _print_no_devices_hints(sys.stdout)
        sys.exit(1)
    print(f"  {'IDENTIFIER':<40} {'KIND':<10} {'STATE':<10} NAME")
    for device in devices:
        print(device.format())
    print("\nTarget one with: pn run <platform> --device <identifier or name>")


def _resolve_device(platform: str, query: Optional[str]) -> Optional[devices_mod.Device]:
    """Resolve ``--device`` to a concrete target, exiting on a bad query."""
    if not query:
        return None
    device = devices_mod.find_device(devices_mod.list_devices(platform), query)
    if device is None:
        print(f"Error: no {platform} device matches {query!r}. Run 'pn devices {platform}' to list targets.")
        sys.exit(1)
    return device


# ======================================================================
# run
# ======================================================================


def _dev_server_url_for(platform: str, device: Optional[devices_mod.Device], port: int) -> str:
    """The WebSocket URL a launched app should use to reach ``pn start``.

    Simulators share the host's loopback. Android emulators and USB
    devices reach it through ``adb reverse`` (set up by the caller), so
    ``localhost`` works for every Android target. A physical iOS device
    is on the LAN, so it gets the first LAN address.
    """
    if platform == "ios" and device is not None and device.kind == "device":
        from ..devserver import lan_addresses

        for address in lan_addresses():
            return f"ws://{address}:{port}/ws?role=client"
    return f"ws://localhost:{port}/ws?role=client"


def run_project(args: argparse.Namespace) -> None:
    """Stage, build, install, and launch a debug build that talks to ``pn start``.

    The native toolchain only runs when a native input changed (see
    ``pythonnative.project.fingerprint``) or when no dev server is up
    to deliver the latest sources; otherwise the previous artifact is
    reinstalled, which turns the edit/relaunch loop from minutes into
    seconds.

    Args:
        args: Parsed namespace (``platform``, ``device``,
            ``prepare_only``, ``no_logs``, ``rebuild``, ``dev_server``,
            ``port``, ``dev_client``).
    """
    platform: str = args.platform
    prepare_only: bool = getattr(args, "prepare_only", False)
    show_logs: bool = not getattr(args, "no_logs", False)
    force_rebuild: bool = getattr(args, "rebuild", False)
    dev_client: bool = getattr(args, "dev_client", False)
    port: int = int(getattr(args, "port", DEFAULT_DEV_PORT) or DEFAULT_DEV_PORT)
    device = _resolve_device(platform, getattr(args, "device", None))

    config = _load_config_or_exit()
    if dev_client:
        # A dev client is the same native app whose entry module is the
        # connect screen; the real app arrives from the dev server.
        config = dataclasses.replace(config, entry_point="pythonnative/devclient.py")
    builder = builder_mod.Builder(config, log=print)

    # Resolve third-party packages only for the destination being built
    # (device wheels and Simulator wheels differ); prepare-only keeps both
    # slices so the staged project builds for either in Xcode.
    if prepare_only:
        ios_sdks: tuple = deps_mod.IOS_SDKS
    elif device is not None and device.kind == "device":
        ios_sdks = ("iphoneos",)
    else:
        ios_sdks = ("iphonesimulator",)

    explicit_server: Optional[str] = getattr(args, "dev_server", None)
    status = _running_dev_server(port) if not explicit_server else None
    if explicit_server:
        server_url: Optional[str] = explicit_server
    elif status is not None:
        server_url = _dev_server_url_for(platform, device, int(status.get("port") or port))
    else:
        server_url = None
        if not prepare_only:
            print(
                f"Note: no dev server on port {port}. Run 'pn start' in another terminal and relaunch, or the "
                "app will run its bundled sources without Fast Refresh."
            )

    fingerprint = _native_fingerprint(config, platform, builder, ios_sdks=ios_sdks, dev_client=dev_client)
    build_dir = builder.build_root / platform
    stamp = fingerprint_mod.read_stamp(build_dir)
    artifact = Path(stamp["artifact"]) if stamp and stamp.get("artifact") else None
    reuse = (
        not prepare_only
        and not force_rebuild
        and server_url is not None
        and stamp is not None
        and stamp.get("fingerprint") == fingerprint
        and artifact is not None
        and artifact.exists()
    )

    prepared: Optional[builder_mod.PreparedProject] = None
    if reuse:
        print(f"Native inputs unchanged; reinstalling {artifact} (use --rebuild to force a build).")
    else:
        try:
            prepared = builder.prepare(platform, ios_sdks=ios_sdks)
        except builder_mod.BuildError as exc:
            print(f"Error: {exc}")
            sys.exit(1)
        if prepare_only:
            print(f"Prepared {platform} project in {prepared.project_dir} (prepare-only).")
            return

    app_id = config.application_id if platform == "android" else config.bundle_id
    if server_url:
        print(f"Dev server: {server_url} (saves in app/ apply with Fast Refresh).")
    try:
        if platform == "android":
            artifact = _run_android(
                builder, prepared, artifact=artifact, app_id=app_id, device=device, server_url=server_url, port=port
            )
        elif device is not None and device.kind == "device":
            artifact = _run_ios_device(
                builder, prepared, artifact=artifact, app_id=app_id, device=device, server_url=server_url
            )
        else:
            artifact = _run_ios_simulator(
                builder,
                prepared,
                artifact=artifact,
                app_id=app_id,
                device=device,
                server_url=server_url,
                show_logs=show_logs,
            )
    except builder_mod.BuildError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    if artifact is not None and not reuse:
        fingerprint_mod.write_stamp(build_dir, fingerprint, artifact=artifact)

    if show_logs and platform == "android":
        _stream_logs_until_interrupt(platform, app_id, device)


def _native_fingerprint(
    config: AppConfig,
    platform: str,
    builder: builder_mod.Builder,
    *,
    ios_sdks: tuple,
    dev_client: bool,
) -> str:
    return fingerprint_mod.compute(
        config,
        platform,
        template_root=builder_mod.template_source(platform),
        lib_root=builder.dev_lib_root,
        ios_sdks=ios_sdks,
        extra={"dev_client": "1" if dev_client else "0"},
    )


def _run_android(
    builder: builder_mod.Builder,
    prepared: Optional[builder_mod.PreparedProject],
    *,
    artifact: Optional[Path],
    app_id: str,
    device: Optional[devices_mod.Device],
    server_url: Optional[str],
    port: int,
) -> Optional[Path]:
    if device is not None:
        # Both Gradle's install task and every adb call below honor
        # ANDROID_SERIAL, so exporting it targets the whole run.
        os.environ["ANDROID_SERIAL"] = device.identifier
    if prepared is not None:
        builder.install_android_debug(prepared)
        artifact = builder.android_debug_apk(prepared)
    elif artifact is not None:
        install = subprocess.run(["adb", "install", "-r", str(artifact)], check=False)
        if install.returncode != 0:
            raise builder_mod.BuildError("adb install failed; run again with --rebuild.")
    if server_url and "localhost" in server_url:
        # Emulators and USB devices reach the host through adb's reverse tunnel.
        subprocess.run(["adb", "reverse", f"tcp:{port}", f"tcp:{port}"], check=False, capture_output=True)
    command = ["adb", "shell", "am", "start", "-n", f"{app_id}/.MainActivity"]
    if server_url:
        command += ["--es", "pn_dev_server", server_url]
    subprocess.run(command, check=True)
    return artifact


def _run_ios_simulator(
    builder: builder_mod.Builder,
    prepared: Optional[builder_mod.PreparedProject],
    *,
    artifact: Optional[Path],
    app_id: str,
    device: Optional[devices_mod.Device],
    server_url: Optional[str],
    show_logs: bool,
) -> Optional[Path]:
    if prepared is not None:
        artifact = builder.build_ios_simulator(prepared)
    if artifact is None:
        raise builder_mod.BuildError("No simulator build to install; run again with --rebuild.")
    udid = device.identifier if device is not None else _select_ios_simulator()
    if udid is None:
        print("No available iOS Simulators found; open the project in Xcode to run.")
        return artifact
    subprocess.run(["xcrun", "simctl", "boot", udid], check=False, capture_output=True)
    subprocess.run(["xcrun", "simctl", "install", udid, str(artifact)], check=False)
    env = {**os.environ, "SIMCTL_CHILD_PYTHONUNBUFFERED": "1"}
    if server_url:
        env["SIMCTL_CHILD_PN_DEV_SERVER"] = server_url
    command = ["xcrun", "simctl", "launch", "--terminate-running-process"]
    if show_logs:
        # A console PTY streams Python's stdout here; the launch blocks.
        command.append("--console-pty")
    command += [udid, app_id]
    if not show_logs:
        subprocess.run(command, env=env, check=False)
        print("Launched iOS app on Simulator.")
        return artifact
    print("Launched iOS app on Simulator. Streaming logs (Ctrl+C to stop)...")
    try:
        subprocess.run(command, env=env, check=False)
    except KeyboardInterrupt:
        print()
        subprocess.run(["xcrun", "simctl", "terminate", udid, app_id], check=False, capture_output=True)
        print("Stopped log streaming.")
    return artifact


def _run_ios_device(
    builder: builder_mod.Builder,
    prepared: Optional[builder_mod.PreparedProject],
    *,
    artifact: Optional[Path],
    app_id: str,
    device: devices_mod.Device,
    server_url: Optional[str],
) -> Optional[Path]:
    """Build, install, and launch on a physical iOS device via devicectl."""
    if prepared is not None:
        artifact = builder.build_ios_device(prepared)
    if artifact is None:
        raise builder_mod.BuildError("No device build to install; run again with --rebuild.")
    print(f"Installing on {device.name}...")
    install = subprocess.run(
        ["xcrun", "devicectl", "device", "install", "app", "--device", device.identifier, str(artifact)],
        check=False,
    )
    if install.returncode != 0:
        print(
            "Error: install failed. Make sure the device is unlocked, paired with this Mac, "
            "and has Developer Mode enabled (Settings > Privacy & Security > Developer Mode)."
        )
        sys.exit(1)
    command = ["xcrun", "devicectl", "device", "process", "launch", "--terminate-existing"]
    if server_url:
        command += ["--environment-variables", json.dumps({"PN_DEV_SERVER": server_url})]
    command += ["--device", device.identifier, app_id]
    launch = subprocess.run(command, check=False)
    if launch.returncode != 0:
        print("Error: launch failed. Launch the app from the home screen to see details.")
        sys.exit(1)
    print(f"Launched on {device.name}. Logs stream to the 'pn start' terminal (or Console.app).")
    return artifact


def _stream_logs_until_interrupt(platform: str, app_id: str, device: Optional[devices_mod.Device]) -> None:
    """Tail the app's stdout on a simulator/emulator until Ctrl+C."""
    if platform == "android":
        proc = _start_android_log_stream()
    else:
        udid = device.identifier if device is not None else None
        proc = _start_ios_log_stream(app_id, udid=udid)
    if proc is None:
        return
    try:
        proc.wait()
    except KeyboardInterrupt:
        print()
        _terminate_subprocess(proc)
        print("Stopped log streaming.")


# ======================================================================
# build
# ======================================================================


def build_project(args: argparse.Namespace) -> None:
    """Build standalone, distributable artifacts for ``platform``.

    Args:
        args: Parsed namespace (``platform``, ``debug``, ``upload``).
    """
    platform: str = args.platform
    debug: bool = getattr(args, "debug", False)
    upload: bool = getattr(args, "upload", False)

    config = _load_config_or_exit()
    builder = builder_mod.Builder(config, log=print)

    if upload and (platform != "ios" or debug):
        print("Error: --upload applies to 'pn build ios' release builds only.")
        sys.exit(1)
    if upload and config.ios.signing.export_method != "app-store":
        print('Error: --upload requires [ios.signing] export_method = "app-store" in pythonnative.toml.')
        sys.exit(1)

    try:
        prepared = builder.prepare(
            platform,
            release=not debug,
            ios_sdks=("iphonesimulator",) if debug else ("iphoneos",),
        )
        if platform == "android":
            artifacts = builder.build_android(prepared, debug=debug)
        else:
            if debug:
                app_path = builder.build_ios_simulator(prepared)
                artifacts = builder_mod.BuildArtifacts(paths=[app_path])
            else:
                artifacts = builder.build_ios_archive(prepared, upload=upload)
    except builder_mod.BuildError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    if upload:
        print("\nUploaded to App Store Connect. Check the build's status at appstoreconnect.apple.com.")
    if not artifacts.paths:
        if not upload:
            print("Build completed, but no artifacts were found. Check the build output above.")
        return
    print("\nBuilt artifacts:")
    for path in artifacts.paths:
        print(f"  {path}")


# ======================================================================
# logs
# ======================================================================


def logs_command(args: argparse.Namespace) -> None:
    """Stream logs from the running app without rebuilding.

    Args:
        args: Parsed namespace (``platform``, ``device``).
    """
    platform: str = args.platform
    device = _resolve_device(platform, getattr(args, "device", None))
    if platform == "android":
        if device is not None:
            # Both adb and logcat below honor ANDROID_SERIAL, so exporting
            # it targets the whole log stream at the chosen device.
            os.environ["ANDROID_SERIAL"] = device.identifier
        proc = _start_android_log_stream()
        if proc is None:
            sys.exit(1)
        try:
            proc.wait()
        except KeyboardInterrupt:
            print()
            _terminate_subprocess(proc)
            print("Stopped log streaming.")
        return

    # iOS: relaunch the app on the booted simulator with a console PTY so
    # Python's stdout/stderr stream to this terminal.
    if device is not None and device.kind == "device":
        print("For a physical device, use Console.app or Xcode > Devices and Simulators.")
        sys.exit(1)
    config = _load_config_or_exit()
    udid = device.identifier if device is not None else None
    proc = _start_ios_log_stream(config.bundle_id, udid=udid)
    if proc is None:
        print("For a physical device, use Console.app or Xcode > Devices and Simulators.")
        sys.exit(1)
    try:
        proc.wait()
    except KeyboardInterrupt:
        print()
        _terminate_subprocess(proc)
        print("Stopped log streaming.")


# ======================================================================
# clean
# ======================================================================


def clean_project(args: argparse.Namespace) -> None:
    """Remove the local ``build/`` directory.

    Args:
        args: Parsed namespace (unused).
    """
    build_dir = Path.cwd() / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir)
        print("Removed build/ directory.")
    else:
        print("No build/ directory to remove.")


# ======================================================================
# Config helpers
# ======================================================================


def _load_config_or_exit(project_dir: Optional[Path] = None) -> AppConfig:
    try:
        return AppConfig.load(project_dir or Path.cwd())
    except ConfigError as exc:
        print(f"Error: {exc}")
        sys.exit(1)


# ======================================================================
# Device log streaming
# ======================================================================


def _start_android_log_stream() -> Optional[subprocess.Popen]:
    """Clear logcat and stream Python-relevant tags to the terminal.

    Returns:
        The ``adb logcat`` process, or ``None`` if ``adb`` is missing.
    """
    try:
        subprocess.run(["adb", "logcat", "-c"], check=False, capture_output=True)
    except FileNotFoundError:
        print("Note: 'adb' not found on PATH; skipping log streaming.")
        return None
    try:
        proc = subprocess.Popen(["adb", "logcat", *collect_logcat_filters()])
    except FileNotFoundError:
        return None
    print("Streaming Python logs from device (Ctrl+C to stop)...")
    return proc


def _booted_ios_udid() -> Optional[str]:
    """Return a booted iOS Simulator's UDID, or ``None`` if none is booted."""
    try:
        result = subprocess.run(
            ["xcrun", "simctl", "list", "devices", "booted", "--json"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return None
    for _runtime, devices in (data.get("devices") or {}).items():
        for device in devices or []:
            if device.get("state") == "Booted" and device.get("udid"):
                return str(device["udid"])
    return None


def _select_ios_simulator() -> Optional[str]:
    """Return a simulator UDID to target (booted first, else an iPhone)."""
    booted = _booted_ios_udid()
    if booted:
        return booted
    try:
        result = subprocess.run(
            ["xcrun", "simctl", "list", "devices", "available", "--json"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return None
    devices: List[Dict[str, Any]] = [d for lst in (data.get("devices") or {}).values() for d in (lst or [])]
    for device in devices:
        if "iphone 15" in (device.get("name") or "").lower() and device.get("isAvailable"):
            return device.get("udid")
    for device in devices:
        if device.get("isAvailable") and (device.get("name") or "").lower().startswith("iphone"):
            return device.get("udid")
    return None


def _start_ios_log_stream(bundle_id: str, *, udid: Optional[str] = None) -> Optional[subprocess.Popen]:
    """Re-launch the iOS app with a console PTY so its stdio streams here.

    Args:
        bundle_id: The app's bundle identifier.
        udid: A specific simulator UDID to target. Falls back to the
            booted simulator when not given.

    Returns:
        The launched process, or ``None`` when no simulator is booted.
    """
    if udid is None:
        udid = _booted_ios_udid()
    if udid is None:
        print("Note: no booted iOS Simulator found; skipping log streaming.")
        return None
    env = {**os.environ, "SIMCTL_CHILD_PYTHONUNBUFFERED": "1"}
    try:
        proc = subprocess.Popen(
            ["xcrun", "simctl", "launch", "--console-pty", "--terminate-running-process", udid, bundle_id],
            env=env,
        )
    except FileNotFoundError:
        print("Note: 'xcrun' not found on PATH; skipping iOS log streaming.")
        return None
    print("Streaming iOS app logs from the simulator (Ctrl+C to stop)...")
    return proc


def _terminate_subprocess(proc: Optional[subprocess.Popen]) -> None:
    """Politely stop a subprocess, escalating to ``SIGKILL`` if needed."""
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


# ======================================================================
# Argument parsing
# ======================================================================


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pn", description="PythonNative CLI")
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=f"pn {pkg_version('pythonnative')}",
    )
    subparsers = parser.add_subparsers()

    parser_init = subparsers.add_parser("init", help="Scaffold a new project")
    parser_init.add_argument(
        "name",
        nargs="?",
        help="Project name, matching ^[a-z][a-z0-9_-]*$; creates ./<name>/ (default: current directory)",
    )
    parser_init.add_argument("--force", action="store_true", help="Overwrite existing files or a non-empty directory")
    parser_init.set_defaults(func=init_project)

    parser_doctor = subparsers.add_parser("doctor", help="Diagnose the local toolchain and config")
    parser_doctor.add_argument("platform", nargs="?", choices=["android", "ios"], help="Restrict checks to a platform")
    parser_doctor.set_defaults(func=doctor_command)

    parser_deps = subparsers.add_parser(
        "deps", help="Check which wheels [requirements].packages resolve to on each device target"
    )
    parser_deps.add_argument("platform", nargs="?", choices=["android", "ios"], help="Restrict to a platform")
    parser_deps.add_argument("--json", action="store_true", help="Print a JSON report for scripting")
    parser_deps.add_argument(
        "--python",
        help="Interpreter to run pip with (default: the one running pn; any version works, pip cross-resolves)",
    )
    parser_deps.set_defaults(func=deps_command)

    def _add_server_args(sub: argparse.ArgumentParser) -> None:
        sub.add_argument(
            "entry",
            nargs="?",
            help="Entry module (e.g. app.main); defaults to the project entry point",
        )
        sub.add_argument(
            "--port", type=int, default=DEFAULT_DEV_PORT, help=f"Port to listen on (default: {DEFAULT_DEV_PORT})"
        )
        sub.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0 so devices can connect)")

    parser_start = subparsers.add_parser(
        "start", help="Run the dev server: browser preview + Fast Refresh for every connected debug build"
    )
    _add_server_args(parser_start)
    parser_start.add_argument("--open", action="store_true", help="Also open the browser preview")
    parser_start.set_defaults(func=start_command)

    parser_preview = subparsers.add_parser("preview", help="Run the dev server and open the browser preview")
    _add_server_args(parser_preview)
    parser_preview.add_argument("--no-open", action="store_true", help="Don't open the browser automatically")
    parser_preview.set_defaults(func=preview_command)

    parser_devices = subparsers.add_parser("devices", help="List devices, emulators, and simulators")
    parser_devices.add_argument("platform", nargs="?", choices=["android", "ios"], help="Restrict to a platform")
    parser_devices.add_argument(
        "--json", action="store_true", help="Print a JSON array to stdout for scripting (hints go to stderr)"
    )
    parser_devices.set_defaults(func=devices_command)

    parser_run = subparsers.add_parser("run", help="Build, install, and launch on a device/simulator")
    parser_run.add_argument("platform", choices=["android", "ios"])
    parser_run.add_argument(
        "--device",
        "-d",
        help="Target device: an identifier or name from 'pn devices' "
        "(physical iOS devices need [ios].development_team)",
    )
    parser_run.add_argument("--prepare-only", action="store_true", help="Stage + configure without building")
    parser_run.add_argument("--no-logs", action="store_true", help="Don't stream device logs after launch")
    parser_run.add_argument(
        "--rebuild", action="store_true", help="Run the native toolchain even when no native input changed"
    )
    parser_run.add_argument(
        "--dev-server",
        help="Dev server WebSocket URL for the app (default: the 'pn start' found on --port, via localhost/LAN)",
    )
    parser_run.add_argument(
        "--port", type=int, default=DEFAULT_DEV_PORT, help=f"Port 'pn start' listens on (default: {DEFAULT_DEV_PORT})"
    )
    parser_run.add_argument(
        "--dev-client",
        action="store_true",
        help="Build a dev client: a shell app that shows a connect screen and loads the app from any dev server",
    )
    parser_run.set_defaults(func=run_project)

    parser_logs = subparsers.add_parser("logs", help="Stream logs from the running app")
    parser_logs.add_argument("platform", choices=["android", "ios"])
    parser_logs.add_argument(
        "--device",
        "-d",
        help="Target device: an identifier or name from 'pn devices' "
        "(physical iOS devices aren't supported for log streaming)",
    )
    parser_logs.set_defaults(func=logs_command)

    parser_build = subparsers.add_parser("build", help="Build distributable artifacts")
    parser_build.add_argument("platform", choices=["android", "ios"])
    parser_build.add_argument("--debug", action="store_true", help="Build the debug variant instead of release")
    parser_build.add_argument(
        "--upload",
        action="store_true",
        help='Upload the iOS release build to App Store Connect (needs export_method = "app-store")',
    )
    parser_build.set_defaults(func=build_project)

    parser_app_id = subparsers.add_parser("app-id", help="Print the resolved application/bundle id")
    parser_app_id.add_argument("platform", choices=["android", "ios"])
    parser_app_id.set_defaults(func=app_id_command)

    parser_clean = subparsers.add_parser("clean", help="Remove the local build/ directory")
    parser_clean.set_defaults(func=clean_project)

    return parser


def main() -> None:
    """Entry point for the ``pn`` console script."""
    parser = _build_parser()
    args = parser.parse_args()
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        sys.exit(1)
    func(args)


if __name__ == "__main__":
    main()
