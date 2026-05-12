"""`pn` CLI: scaffold, run, and clean PythonNative projects.

The console script `pn` (declared in `pyproject.toml` under
`[project.scripts]`) dispatches to one of three subcommands:

- `pn init [name]`: scaffold a new project in the current directory.
- `pn run android|ios`: stage code into a native template, build it,
  install it, and stream logs back to the terminal.
- `pn clean`: remove the local `build/` directory.

The implementation here is intentionally side-effect heavy: it shells
out to `gradle`, `xcodebuild`, `adb`, and `xcrun simctl`. Errors from
those tools are usually surfaced inline so the developer sees the
underlying message.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import sysconfig
import time
import urllib.request
from importlib import resources
from typing import Any, Dict, List, Optional


def init_project(args: argparse.Namespace) -> None:
    """Scaffold a new PythonNative project in the current directory.

    Creates `app/main.py`, `pythonnative.json`, `requirements.txt`,
    and `.gitignore`. Refuses to overwrite existing files unless
    `--force` is passed.

    Args:
        args: The parsed argparse namespace. Recognized attributes:

            - `name` (`str`, optional): Project name (defaults to the
              current directory name).
            - `force` (`bool`): Overwrite existing files.
    """
    project_name: str = getattr(args, "name", None) or os.path.basename(os.getcwd())
    cwd: str = os.getcwd()

    app_dir = os.path.join(cwd, "app")
    config_path = os.path.join(cwd, "pythonnative.json")
    requirements_path = os.path.join(cwd, "requirements.txt")
    gitignore_path = os.path.join(cwd, ".gitignore")

    # Prevent accidental overwrite unless --force is provided
    if not getattr(args, "force", False):
        exists = []
        if os.path.exists(app_dir):
            exists.append("app/")
        if os.path.exists(config_path):
            exists.append("pythonnative.json")
        if os.path.exists(requirements_path):
            exists.append("requirements.txt")
        if os.path.exists(gitignore_path):
            exists.append(".gitignore")
        if exists:
            print(f"Refusing to overwrite existing: {', '.join(exists)}. Use --force to overwrite.")
            sys.exit(1)

    os.makedirs(app_dir, exist_ok=True)

    main_py = os.path.join(app_dir, "main.py")
    if not os.path.exists(main_py) or args.force:
        with open(main_py, "w", encoding="utf-8") as f:
            f.write("""import pythonnative as pn

Stack = pn.create_stack_navigator()


@pn.component
def HomeScreen():
    count, set_count = pn.use_state(0)
    nav = pn.use_navigation()
    return pn.ScrollView(
        pn.Column(
            pn.Text("Hello from PythonNative!", style={"font_size": 24, "bold": True}),
            pn.Text(f"Tapped {count} times"),
            pn.Button("Tap me", on_click=lambda: set_count(count + 1)),
            pn.Button("Open detail", on_click=lambda: nav.navigate("Detail", {"count": count})),
            style={"spacing": 12, "padding": 16, "align_items": "stretch"},
        )
    )


@pn.component
def DetailScreen():
    nav = pn.use_navigation()
    params = pn.use_route()
    return pn.Column(
        pn.Text(f"Detail: count was {params.get('count', 0)}", style={"font_size": 20}),
        pn.Button("Back", on_click=nav.go_back),
        style={"spacing": 12, "padding": 16},
    )


@pn.component
def App():
    return pn.NavigationContainer(
        Stack.Navigator(
            Stack.Screen("Home", component=HomeScreen, options={"title": "Home"}),
            Stack.Screen("Detail", component=DetailScreen, options={"title": "Detail"}),
        )
    )
""")

    # Create config
    config = {
        "name": project_name,
        "appId": "com.example." + project_name.replace(" ", "").lower(),
        "entryPoint": "app/main.py",
        "pythonVersion": "3.11",
        "ios": {},
        "android": {},
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    # Requirements (third-party packages only; pythonnative itself is bundled by the CLI)
    if not os.path.exists(requirements_path) or args.force:
        with open(requirements_path, "w", encoding="utf-8") as f:
            f.write("")

    # .gitignore
    default_gitignore = "# PythonNative\n" "__pycache__/\n" "*.pyc\n" ".venv/\n" "build/\n" ".DS_Store\n"
    if not os.path.exists(gitignore_path) or args.force:
        with open(gitignore_path, "w", encoding="utf-8") as f:
            f.write(default_gitignore)

    print("Initialized PythonNative project.")


def _copy_dir(src: str, dst: str) -> None:
    """Recursively copy `src` into `dst`, creating parents as needed."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copytree(src, dst, dirs_exist_ok=True)


def _copy_bundled_template_dir(template_dir: str, destination: str) -> None:
    """Copy a bundled template directory into `destination`.

    Search order:

    1. Local source checkout (`src/pythonnative/templates/<name>`).
    2. Repository `templates/<name>` (used when running from a clone).
    3. Installed package data via `importlib.resources`.
    4. `sysconfig` data/site directories (last resort).

    Args:
        template_dir: The bundled template subdirectory to copy
            (e.g., `"android_template"`).
        destination: Parent directory; the template lands at
            `<destination>/<template_dir>`.

    Raises:
        FileNotFoundError: If no bundled copy can be located.
    """
    dest_path = os.path.join(destination, template_dir)

    # Dev-first: prefer local source templates if running from a checkout (avoid stale packaged data)
    try:
        # __file__ -> src/pythonnative/cli/pn.py, so go up to src/, then to repo root
        src_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        # Check templates located inside the source package tree
        local_pkg_templates = os.path.join(src_dir, "pythonnative", "templates", template_dir)
        if os.path.isdir(local_pkg_templates):
            _copy_dir(local_pkg_templates, dest_path)
            return
        repo_root = os.path.abspath(os.path.join(src_dir, ".."))
        repo_templates = os.path.join(repo_root, "templates")
        candidate_dir = os.path.join(repo_templates, template_dir)
        if os.path.isdir(candidate_dir):
            _copy_dir(candidate_dir, dest_path)
            return
    except Exception:
        pass

    # Try to load from installed package resources (templates packaged inside the module)
    try:
        cand = resources.files("pythonnative").joinpath("templates").joinpath(template_dir)
        with resources.as_file(cand) as p:
            resource_path = str(p)
            if os.path.isdir(resource_path):
                _copy_dir(resource_path, dest_path)
                return
    except Exception:
        pass

    # Last resort: check typical data-file locations
    try:
        data_paths = sysconfig.get_paths()
        search_bases = [
            data_paths.get("data"),
            data_paths.get("purelib"),
            data_paths.get("platlib"),
        ]
        for base in filter(None, search_bases):
            candidate_dir = os.path.join(base, "pythonnative", "templates", template_dir)
            if os.path.isdir(candidate_dir):
                _copy_dir(candidate_dir, dest_path)
                return
    except Exception:
        pass

    raise FileNotFoundError(f"Could not find bundled template directory {template_dir}. Ensure templates are packaged.")


def _github_json(url: str) -> Any:
    """Fetch a GitHub JSON endpoint, optionally authenticated.

    Reads `GITHUB_TOKEN` or `GH_TOKEN` from the environment to raise
    the unauthenticated rate limit.
    """
    headers: dict[str, str] = {"User-Agent": "pythonnative-cli"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode("utf-8"))


def _resolve_python_apple_support_asset(
    py_major_minor: str = "3.11", preferred_name: str = "Python-3.11-iOS-support.b7.tar.gz"
) -> Optional[str]:
    """Resolve a download URL for a `Python-Apple-support` release asset.

    Prefers an exact name match for `preferred_name`; otherwise falls
    back to the newest asset whose name contains
    `Python-{py_major_minor}-iOS-support` and ends with `.tar.gz`.

    Args:
        py_major_minor: Python version string used in the asset name
            (e.g., `"3.11"`).
        preferred_name: Exact filename to prefer when multiple matching
            assets exist.

    Returns:
        A `browser_download_url` string, or `None` if the GitHub API
        call fails or no matching asset is found.
    """
    try:
        releases = _github_json("https://api.github.com/repos/beeware/Python-Apple-support/releases?per_page=100")
        # Search all releases for preferred_name first
        for rel in releases:
            for a in rel.get("assets", []) or []:
                name = a.get("name") or ""
                if name == preferred_name:
                    return a.get("browser_download_url")
        # Fallback: any matching Python-{version}-iOS-support*.tar.gz (take first encountered)
        needle = f"Python-{py_major_minor}-iOS-support"
        for rel in releases:
            for a in rel.get("assets", []) or []:
                name = a.get("name") or ""
                if needle in name and name.endswith(".tar.gz"):
                    return a.get("browser_download_url")
    except Exception:
        pass
    return None


def create_android_project(project_name: str, destination: str) -> None:
    """Stage the bundled Android template into `destination`.

    Args:
        project_name: Project name (currently informational; the
            template uses fixed package IDs).
        destination: Directory to receive the staged project.
    """
    _copy_bundled_template_dir("android_template", destination)


def create_ios_project(project_name: str, destination: str) -> None:
    """Stage the bundled iOS template into `destination`.

    Args:
        project_name: Project name (currently informational; the
            template uses fixed bundle IDs).
        destination: Directory to receive the staged project.
    """
    _copy_bundled_template_dir("ios_template", destination)


def _read_project_config() -> dict:
    """Read `pythonnative.json` from the current working directory.

    Returns:
        The parsed config dict, or `{}` if the file is missing.
    """
    config_path = os.path.join(os.getcwd(), "pythonnative.json")
    if os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _read_requirements(requirements_path: str) -> list[str]:
    """Read a requirements file and return non-empty, non-comment lines.

    Exits with an error if `pythonnative` is listed: the CLI bundles
    it directly, so it must not be installed separately via pip or
    Chaquopy.

    Args:
        requirements_path: Path to a `requirements.txt` file.

    Returns:
        A list of requirement specifier strings, in file order.
    """
    if not os.path.exists(requirements_path):
        return []
    with open(requirements_path, encoding="utf-8") as f:
        lines = f.readlines()
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            continue
        pkg_name = re.split(r"[\[><=!;]", stripped)[0].strip()
        if pkg_name.lower().replace("-", "_") == "pythonnative":
            print(
                "Error: 'pythonnative' must not be in requirements.txt.\n"
                "The pn CLI automatically bundles the installed pythonnative into your app.\n"
                "requirements.txt is for third-party packages only (e.g. humanize, requests).\n"
                "Remove the pythonnative line from requirements.txt and try again."
            )
            sys.exit(1)
        result.append(stripped)
    return result


ANDROID_PACKAGE_ID: str = "com.pythonnative.android_template"
HOT_RELOAD_DEV_ROOT: str = "pythonnative_dev"

ANDROID_LOGCAT_FILTERS: list[str] = [
    "python.stdout:V",
    "python.stderr:V",
    "MainActivity:V",
    "ScreenFragment:V",
    "Navigator:V",
    "PythonNative:V",
    "AndroidRuntime:E",
    "System.err:W",
    "*:S",
]

IOS_BUNDLE_ID: str = "com.pythonnative.ios-template"


def _start_android_log_stream() -> Optional[subprocess.Popen]:
    """Clear logcat and stream Python-relevant log tags to the terminal.

    Python's `print()` output reaches logcat via Chaquopy, which
    redirects `sys.stdout`/`sys.stderr` to the `python.stdout` and
    `python.stderr` tags.

    Returns:
        The `adb logcat` subprocess, or `None` when `adb` is
        unavailable on `PATH`.
    """
    try:
        subprocess.run(["adb", "logcat", "-c"], check=False, capture_output=True)
    except FileNotFoundError:
        print("Note: 'adb' not found on PATH; skipping log streaming.")
        return None
    try:
        proc = subprocess.Popen(["adb", "logcat", *ANDROID_LOGCAT_FILTERS])
    except FileNotFoundError:
        return None
    print("Streaming Python logs from device (Ctrl+C to stop)...")
    return proc


def _booted_ios_udid() -> Optional[str]:
    """Return a booted iOS Simulator's UDID, or `None` if none is booted.

    Used by `_start_ios_log_stream` so the hot-reload path doesn't
    need to thread the UDID through from the install step.
    """
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
            if device.get("state") == "Booted":
                udid = device.get("udid")
                if udid:
                    return str(udid)
    return None


def _start_ios_log_stream() -> Optional[subprocess.Popen]:
    """Re-launch the iOS app with a console PTY so its stdio streams here.

    Mirrors the approach `pn run ios` (without `--hot-reload`) takes:
    ``xcrun simctl launch --console-pty`` attaches the parent
    terminal to the app's stderr, which is where Python ``print()``
    output is routed (see `pythonnative._ios_log`) and where Swift
    ``NSLog`` calls land. Unlike ``log stream``, this *only*
    surfaces what the app writes itself — none of UIKit's verbose
    ``os_log`` chatter.

    Returns:
        The launched subprocess (output inherits the parent
        terminal), or `None` when no simulator is booted or
        `xcrun` is unavailable.
    """
    udid = _booted_ios_udid()
    if udid is None:
        print("Note: no booted iOS Simulator found; skipping log streaming.")
        return None
    sim_env = os.environ.copy()
    sim_env["SIMCTL_CHILD_PYTHONUNBUFFERED"] = "1"
    try:
        proc = subprocess.Popen(
            [
                "xcrun",
                "simctl",
                "launch",
                "--console-pty",
                "--terminate-running-process",
                udid,
                IOS_BUNDLE_ID,
            ],
            env=sim_env,
        )
    except FileNotFoundError:
        print("Note: 'xcrun' not found on PATH; skipping iOS log streaming.")
        return None
    print("Streaming iOS app logs from the simulator (Ctrl+C to stop)...")
    return proc


def _terminate_subprocess(proc: Optional[subprocess.Popen]) -> None:
    """Politely stop a subprocess, escalating to `SIGKILL` if needed.

    A no-op when `proc` is `None` or has already exited.
    """
    if proc is None:
        return
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


def _hot_reload_manifest_payload(
    changed_files: List[str],
    project_dir: str,
    *,
    version: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the reload manifest consumed by the running app."""
    from pythonnative.hot_reload import ModuleReloader

    rel_files = sorted(os.path.relpath(path, project_dir) for path in changed_files)
    return {
        "version": version or str(time.time_ns()),
        "files": rel_files,
        "modules": ModuleReloader.modules_from_files(rel_files),
    }


def _write_hot_reload_manifest(changed_files: List[str], project_dir: str, build_dir: str) -> str:
    """Write a local hot-reload manifest and return its path."""
    manifest_dir = os.path.join(build_dir, "hot_reload")
    os.makedirs(manifest_dir, exist_ok=True)
    manifest_path = os.path.join(manifest_dir, "reload.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(_hot_reload_manifest_payload(changed_files, project_dir), f)
    return manifest_path


def _android_hot_reload_dest(rel_path: str) -> str:
    """Return a `run-as` relative destination for an app source file."""
    return os.path.join("files", HOT_RELOAD_DEV_ROOT, rel_path)


def _push_android_hot_reload_file(local_path: str, rel_path: str) -> bool:
    """Push one file into the Android app's writable hot-reload overlay."""
    tmp_path = f"/data/local/tmp/pythonnative-hot-reload-{os.getpid()}-{os.path.basename(local_path)}"
    dest_path = _android_hot_reload_dest(rel_path)
    dest_dir = os.path.dirname(dest_path)
    push = subprocess.run(["adb", "push", local_path, tmp_path], check=False, capture_output=True)
    if push.returncode != 0:
        return False
    subprocess.run(
        ["adb", "shell", "run-as", ANDROID_PACKAGE_ID, "mkdir", "-p", dest_dir],
        check=False,
        capture_output=True,
    )
    copy = subprocess.run(
        ["adb", "shell", "run-as", ANDROID_PACKAGE_ID, "cp", tmp_path, dest_path],
        check=False,
        capture_output=True,
    )
    subprocess.run(["adb", "shell", "rm", "-f", tmp_path], check=False, capture_output=True)
    return copy.returncode == 0


def _ios_data_container() -> Optional[str]:
    """Return the booted simulator's app data container, if available."""
    try:
        result = subprocess.run(
            ["xcrun", "simctl", "get_app_container", "booted", IOS_BUNDLE_ID, "data"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    container = result.stdout.strip()
    return container or None


def _push_ios_hot_reload_file(local_path: str, rel_path: str) -> bool:
    """Copy one file into the booted iOS Simulator's hot-reload overlay."""
    container = _ios_data_container()
    if container is None:
        return False
    dest_path = os.path.join(container, "Documents", HOT_RELOAD_DEV_ROOT, rel_path)
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    shutil.copy2(local_path, dest_path)
    return True


def _clear_android_hot_reload_overlay() -> bool:
    """Remove stale Android hot-reload files before launching."""
    result = subprocess.run(
        ["adb", "shell", "run-as", ANDROID_PACKAGE_ID, "rm", "-rf", f"files/{HOT_RELOAD_DEV_ROOT}"],
        check=False,
        capture_output=True,
    )
    return result.returncode == 0


def _clear_ios_hot_reload_overlay() -> bool:
    """Remove stale iOS Simulator hot-reload files before launching."""
    container = _ios_data_container()
    if container is None:
        return False
    shutil.rmtree(os.path.join(container, "Documents", HOT_RELOAD_DEV_ROOT), ignore_errors=True)
    return True


def _clear_hot_reload_overlay(platform: str) -> bool:
    """Remove stale hot-reload overlay files for `platform`."""
    if platform == "android":
        return _clear_android_hot_reload_overlay()
    if platform == "ios":
        return _clear_ios_hot_reload_overlay()
    return False


def _push_hot_reload_file(platform: str, local_path: str, rel_path: str) -> bool:
    """Push a changed source file to the running app."""
    if platform == "android":
        return _push_android_hot_reload_file(local_path, rel_path)
    if platform == "ios":
        return _push_ios_hot_reload_file(local_path, rel_path)
    return False


def run_project(args: argparse.Namespace) -> None:
    """Build and run the project on the requested platform.

    Stages templates, copies the user's `app/` into the platform
    project, optionally installs Python requirements, and (unless
    `--prepare-only` is set) builds and launches the app on a
    connected device or simulator. With `--hot-reload`, also watches
    `app/` for changes and pushes updates to the device.

    Args:
        args: Parsed argparse namespace. Recognized attributes:

            - `platform` (`"android"` | `"ios"`): Build target.
            - `prepare_only` (`bool`): Stage files but skip the build.
            - `hot_reload` (`bool`): Watch `app/` and push changes.
            - `no_logs` (`bool`): Don't stream device logs after launch.
    """
    # Determine the platform
    platform: str = args.platform
    prepare_only: bool = getattr(args, "prepare_only", False)
    hot_reload: bool = getattr(args, "hot_reload", False)
    show_logs: bool = not getattr(args, "no_logs", False)

    # Read project configuration and save project root before any chdir
    project_dir: str = os.getcwd()
    config = _read_project_config()
    python_version: str = config.get("pythonVersion", "3.11")

    # Define the build directory
    build_dir: str = os.path.join(project_dir, "build", platform)

    # Create the build directory if it doesn't exist
    os.makedirs(build_dir, exist_ok=True)

    # Generate the required project files
    if platform == "android":
        create_android_project("MyApp", build_dir)
    elif platform == "ios":
        create_ios_project("MyApp", build_dir)

    # Copy the user's Python code into the project
    src_dir: str = os.path.join(os.getcwd(), "app")

    # Adjust the destination directory for Android project
    if platform == "android":
        dest_dir: str = os.path.join(build_dir, "android_template", "app", "src", "main", "python", "app")
    else:
        # For iOS, stage the Python app in a top-level folder for later integration scripts
        dest_dir = os.path.join(build_dir, "app")

    # Create the destination directory if it doesn't exist
    os.makedirs(dest_dir, exist_ok=True)
    shutil.copytree(src_dir, dest_dir, dirs_exist_ok=True)

    # During local development (running from repository), also bundle the
    # local library sources so the app uses the in-repo version instead of
    # the PyPI package. This provides faster inner-loop iteration and avoids
    # version skew during development.
    try:
        # __file__ -> src/pythonnative/cli/pn.py, so repo root is one up from src/
        src_root = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".."))
        local_lib = os.path.join(src_root, "pythonnative")
        if os.path.isdir(local_lib):
            if platform == "android":
                python_root = os.path.join(build_dir, "android_template", "app", "src", "main", "python")
            else:
                python_root = os.path.join(build_dir)  # staged at build/ios/app for iOS below
            os.makedirs(python_root, exist_ok=True)
            shutil.copytree(local_lib, os.path.join(python_root, "pythonnative"), dirs_exist_ok=True)
    except Exception:
        # Non-fatal; fallback to the packaged PyPI dependency if present
        pass

    # Validate and read the user's requirements.txt
    requirements_path = os.path.join(project_dir, "requirements.txt")
    pip_reqs = _read_requirements(requirements_path)

    if platform == "android":
        # Patch the Android build.gradle with the configured Python version
        app_build_gradle = os.path.join(build_dir, "android_template", "app", "build.gradle")
        if os.path.exists(app_build_gradle):
            with open(app_build_gradle, encoding="utf-8") as f:
                content = f.read()
            content = content.replace('version "3.11"', f'version "{python_version}"')
            with open(app_build_gradle, "w", encoding="utf-8") as f:
                f.write(content)
        # Copy requirements.txt into the Android project for Chaquopy
        android_reqs_path = os.path.join(build_dir, "android_template", "app", "requirements.txt")
        if os.path.exists(requirements_path):
            shutil.copy2(requirements_path, android_reqs_path)
        else:
            with open(android_reqs_path, "w", encoding="utf-8") as f:
                f.write("")

    # Install any necessary Python packages into the host environment
    # Skip installation during prepare-only to avoid network access and speed up scaffolding
    if not prepare_only:
        if os.path.exists(requirements_path):
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", requirements_path], check=False)

    # Run the project
    if prepare_only:
        print("Prepared project in build/ without building (prepare-only).")
        return

    if platform == "android":
        # Change to the Android project directory
        android_project_dir: str = os.path.join(build_dir, "android_template")
        os.chdir(android_project_dir)

        # Add executable permissions to the gradlew script
        gradlew_path: str = os.path.join(android_project_dir, "gradlew")
        os.chmod(gradlew_path, 0o755)  # this makes the file executable for the user

        # Build the Android project and install it on the device
        env: dict[str, str] = os.environ.copy()
        # Respect JAVA_HOME if set; otherwise, attempt a best-effort on macOS via Homebrew
        if sys.platform == "darwin" and not env.get("JAVA_HOME"):
            try:
                jdk_path: str = subprocess.check_output(["brew", "--prefix", "openjdk@17"]).decode().strip()
                env["JAVA_HOME"] = jdk_path
            except Exception:
                pass
        subprocess.run(["./gradlew", "installDebug"], check=True, env=env)

        _clear_hot_reload_overlay(platform)

        # Run the Android app
        # Assumes that the package name of your app is "com.example.myapp" and the main activity is "MainActivity"
        # Replace "com.example.myapp" and ".MainActivity" with your actual package name and main activity
        subprocess.run(
            [
                "adb",
                "shell",
                "am",
                "start",
                "-n",
                f"{ANDROID_PACKAGE_ID}/.MainActivity",
            ],
            check=True,
        )

        # Stream Python logs from logcat unless the user opted out or requested
        # hot-reload (hot-reload handles its own log tailing below).
        if show_logs and not hot_reload:
            logcat_proc = _start_android_log_stream()
            if logcat_proc is not None:
                try:
                    logcat_proc.wait()
                except KeyboardInterrupt:
                    print()
                    _terminate_subprocess(logcat_proc)
                    print("Stopped log streaming.")
    elif platform == "ios":
        # Attempt to build and run on iOS Simulator (best-effort)
        ios_project_dir: str = os.path.join(build_dir, "ios_template")
        if os.path.isdir(ios_project_dir):
            # Stage embedded Python runtime inputs by downloading pinned assets
            try:
                assets_dir = os.path.join(build_dir, "ios_runtime")
                os.makedirs(assets_dir, exist_ok=True)
                # Pinned preferred asset name and checksum (b7)
                preferred_name = "Python-3.11-iOS-support.b7.tar.gz"
                sha256 = "2b7d8589715b9890e8dd7e1bce91c210bb5287417e17b9af120fc577675ed28e"
                # Resolve a working download URL from GitHub Releases
                url = _resolve_python_apple_support_asset("3.11", preferred_name=preferred_name)
                if not url:
                    raise RuntimeError("Could not resolve Python-Apple-support asset URL from GitHub Releases.")
                tar_path = os.path.join(assets_dir, os.path.basename(url))
                if not os.path.exists(tar_path):
                    print("Downloading Python-Apple-support (3.11 iOS)")
                    req = urllib.request.Request(url, headers={"User-Agent": "pythonnative-cli"})
                    with urllib.request.urlopen(req) as r, open(tar_path, "wb") as f:
                        f.write(r.read())
                # Verify checksum
                h = hashlib.sha256()
                with open(tar_path, "rb") as f:
                    for chunk in iter(lambda: f.read(1024 * 1024), b""):
                        h.update(chunk)
                if h.hexdigest() != sha256:
                    raise RuntimeError("SHA256 mismatch for Python-Apple-support tarball")
                # Extract only once
                extract_root = os.path.join(assets_dir, "extracted")
                if not os.path.isdir(extract_root):
                    os.makedirs(extract_root, exist_ok=True)
                    subprocess.run(["tar", "-xzf", tar_path, "-C", extract_root], check=True)
                # Provide Python.xcframework to the Xcode project and stdlib for bundling
                # Try both common layouts
                cand_frameworks = [
                    os.path.join(extract_root, "Python.xcframework"),
                    os.path.join(extract_root, "support", "Python.xcframework"),
                ]
                xc_src = next((p for p in cand_frameworks if os.path.isdir(p)), None)
                if xc_src:
                    shutil.copytree(xc_src, os.path.join(ios_project_dir, "Python.xcframework"), dirs_exist_ok=True)
                # Stdlib path
                cand_stdlib = [
                    os.path.join(extract_root, "Python.xcframework", "ios-arm64_x86_64-simulator", "lib", "python3.11"),
                    os.path.join(
                        extract_root, "support", "Python.xcframework", "ios-arm64_x86_64-simulator", "lib", "python3.11"
                    ),
                ]
                stdlib_src = next((p for p in cand_stdlib if os.path.isdir(p)), None)
            except Exception as e:
                print(f"Warning: failed to prepare Python runtime: {e}")

            os.chdir(ios_project_dir)
            derived_data = os.path.join(ios_project_dir, "build")
            try:
                # Detect a simulator UDID to target: prefer Booted; else any iPhone
                sim_udid: Optional[str] = None
                try:
                    import json as _json

                    devices_out = subprocess.run(
                        ["xcrun", "simctl", "list", "devices", "available", "--json"],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    devs = _json.loads(devices_out.stdout or "{}").get("devices") or {}
                    all_devs = [d for lst in devs.values() for d in (lst or [])]
                    for d in all_devs:
                        if d.get("state") == "Booted":
                            sim_udid = d.get("udid")
                            break
                    if not sim_udid:
                        for d in all_devs:
                            if (d.get("isAvailable") or d.get("availability")) and (
                                d.get("name") or ""
                            ).lower().startswith("iphone"):
                                sim_udid = d.get("udid")
                                break
                except Exception:
                    pass

                xcode_dest = (
                    ["-destination", f"id={sim_udid}"] if sim_udid else ["-destination", "platform=iOS Simulator"]
                )

                # Provide header and lib paths for CPython (Simulator slice) ONLY if the
                # XCFramework is not already added to the Xcode project. When the project
                # contains `Python.xcframework`, Xcode manages headers and linking to avoid
                # duplicate module.modulemap definitions.
                extra_xcode_settings: list[str] = []
                try:
                    xc_present = os.path.isdir(os.path.join(ios_project_dir, "Python.xcframework"))
                    if not xc_present and "extract_root" in locals():
                        sim_headers = os.path.join(
                            extract_root, "Python.xcframework", "ios-arm64_x86_64-simulator", "Headers"
                        )
                        sim_lib = os.path.join(
                            extract_root, "Python.xcframework", "ios-arm64_x86_64-simulator", "libPython3.11.a"
                        )
                        if os.path.isdir(sim_headers):
                            extra_xcode_settings.extend(
                                [
                                    f"HEADER_SEARCH_PATHS={sim_headers}",
                                    f"SWIFT_INCLUDE_PATHS={sim_headers}",
                                ]
                            )
                        if os.path.exists(sim_lib):
                            extra_xcode_settings.append(f"OTHER_LDFLAGS=-force_load {sim_lib}")
                except Exception:
                    pass

                subprocess.run(
                    [
                        "xcodebuild",
                        "-project",
                        "ios_template.xcodeproj",
                        "-scheme",
                        "ios_template",
                        "-configuration",
                        "Debug",
                        *xcode_dest,
                        "-derivedDataPath",
                        derived_data,
                        "build",
                        *extra_xcode_settings,
                    ],
                    check=False,
                )
            except FileNotFoundError:
                print("xcodebuild not found. Skipping iOS build step.")
                return

            # Locate built app
            app_path = os.path.join(derived_data, "Build", "Products", "Debug-iphonesimulator", "ios_template.app")
            if not os.path.isdir(app_path):
                print("Could not locate built .app; open the project in Xcode to run.")
                return

            # Copy staged Python app and optional embedded runtime into the .app bundle
            try:
                staged_app_src = os.path.join(build_dir, "app")
                if os.path.isdir(staged_app_src):
                    shutil.copytree(staged_app_src, os.path.join(app_path, "app"), dirs_exist_ok=True)
                # Also copy local library sources if present for dev flow
                src_root = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".."))
                local_lib = os.path.join(src_root, "pythonnative")
                if os.path.isdir(local_lib):
                    shutil.copytree(local_lib, os.path.join(app_path, "pythonnative"), dirs_exist_ok=True)
                # Copy stdlib from downloaded support if available
                if "stdlib_src" in locals() and stdlib_src and os.path.isdir(stdlib_src):
                    shutil.copytree(stdlib_src, os.path.join(app_path, "python-stdlib"), dirs_exist_ok=True)
                # Embed Python.framework for Simulator so PythonKit can dlopen it (from downloaded XCFramework)
                sim_fw = None
                if "extract_root" in locals():
                    cand_fw = [
                        os.path.join(
                            extract_root, "Python.xcframework", "ios-arm64_x86_64-simulator", "Python.framework"
                        ),
                        os.path.join(
                            extract_root,
                            "support",
                            "Python.xcframework",
                            "ios-arm64_x86_64-simulator",
                            "Python.framework",
                        ),
                    ]
                    sim_fw = next((p for p in cand_fw if os.path.isdir(p)), None)
                fw_dest_dir = os.path.join(app_path, "Frameworks")
                os.makedirs(fw_dest_dir, exist_ok=True)
                if sim_fw and os.path.isdir(sim_fw):
                    shutil.copytree(sim_fw, os.path.join(fw_dest_dir, "Python.framework"), dirs_exist_ok=True)
                # Install rubicon-objc into platform-site

                # Ensure importlib.metadata finds package metadata for rubicon-objc by
                # installing it into a site-like dir that is on sys.path (platform-site).
                try:
                    tmp_site = os.path.join(build_dir, "ios_site")
                    if os.path.isdir(tmp_site):
                        shutil.rmtree(tmp_site)
                    os.makedirs(tmp_site, exist_ok=True)
                    # Install pure-Python rubicon-objc distribution metadata and package
                    subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "pip",
                            "install",
                            "--no-deps",
                            "--upgrade",
                            "rubicon-objc",
                            "-t",
                            tmp_site,
                        ],
                        check=False,
                    )
                    platform_site_dir = os.path.join(app_path, "platform-site")
                    os.makedirs(platform_site_dir, exist_ok=True)
                    for entry in os.listdir(tmp_site):
                        src_entry = os.path.join(tmp_site, entry)
                        dst_entry = os.path.join(platform_site_dir, entry)
                        if os.path.isdir(src_entry):
                            shutil.copytree(src_entry, dst_entry, dirs_exist_ok=True)
                        else:
                            shutil.copy2(src_entry, dst_entry)
                except Exception:
                    # Non-fatal; if metadata isn't present, rubicon import may fail and fallback UI will appear
                    pass
                # Install user's pip requirements (pure-Python packages) into the app bundle
                if pip_reqs:
                    try:
                        reqs_tmp = os.path.join(build_dir, "ios_requirements.txt")
                        with open(reqs_tmp, "w", encoding="utf-8") as f:
                            f.write("\n".join(pip_reqs) + "\n")
                        tmp_reqs_dir = os.path.join(build_dir, "ios_user_packages")
                        if os.path.isdir(tmp_reqs_dir):
                            shutil.rmtree(tmp_reqs_dir)
                        os.makedirs(tmp_reqs_dir, exist_ok=True)
                        subprocess.run(
                            [sys.executable, "-m", "pip", "install", "-t", tmp_reqs_dir, "-r", reqs_tmp],
                            check=False,
                        )
                        for entry in os.listdir(tmp_reqs_dir):
                            src_entry = os.path.join(tmp_reqs_dir, entry)
                            dst_entry = os.path.join(platform_site_dir, entry)
                            if os.path.isdir(src_entry):
                                shutil.copytree(src_entry, dst_entry, dirs_exist_ok=True)
                            else:
                                shutil.copy2(src_entry, dst_entry)
                    except Exception:
                        pass
                # Note: Python.xcframework provides a static library for Simulator; it must be linked at build time.
                # We copy the XCFramework into the project directory above so Xcode can link it.
            except Exception:
                # Non-fatal; fallback UI will appear if import fails
                pass

            # Find an available simulator and boot it
            try:
                import json as _json

                result = subprocess.run(
                    ["xcrun", "simctl", "list", "devices", "available", "--json"],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                devices_json = _json.loads(result.stdout or "{}")
                all_devices: List[Dict[str, Any]] = []
                for _runtime, devices in (devices_json.get("devices") or {}).items():
                    all_devices.extend(devices or [])
                # Prefer iPhone 15/15 Pro names; else first available iPhone
                preferred = None
                for d in all_devices:
                    name = (d.get("name") or "").lower()
                    if "iphone 15" in name and d.get("isAvailable"):
                        preferred = d
                        break
                if not preferred:
                    for d in all_devices:
                        if d.get("isAvailable") and (d.get("name") or "").lower().startswith("iphone"):
                            preferred = d
                            break
                if not preferred:
                    print("No available iOS Simulators found; open the project in Xcode to run.")
                    return

                udid = preferred.get("udid")
                # Boot (no-op if already booted). simctl returns non-zero and
                # prints to stderr when the device is already Booted; we
                # don't care about that case, so swallow its output.
                subprocess.run(["xcrun", "simctl", "boot", udid], check=False, capture_output=True)
                # Install
                subprocess.run(["xcrun", "simctl", "install", udid, app_path], check=False)
                _clear_hot_reload_overlay(platform)
                if show_logs and not hot_reload:
                    # Attach the app's stdout/stderr to this terminal so Python
                    # print() calls and exceptions are visible. SIMCTL_CHILD_*
                    # env vars are forwarded to the launched process.
                    sim_env = os.environ.copy()
                    sim_env["SIMCTL_CHILD_PYTHONUNBUFFERED"] = "1"
                    print("Launched iOS app on Simulator. Streaming logs (Ctrl+C to stop)...")
                    try:
                        subprocess.run(
                            [
                                "xcrun",
                                "simctl",
                                "launch",
                                "--console-pty",
                                "--terminate-running-process",
                                udid,
                                IOS_BUNDLE_ID,
                            ],
                            env=sim_env,
                            check=False,
                        )
                    except KeyboardInterrupt:
                        print()
                        subprocess.run(
                            ["xcrun", "simctl", "terminate", udid, IOS_BUNDLE_ID],
                            check=False,
                            capture_output=True,
                        )
                        print("Stopped log streaming.")
                elif hot_reload:
                    # Skip launching here; ``_run_hot_reload`` will
                    # spawn the app via ``simctl launch --console-pty``
                    # so its ``print()`` / ``NSLog`` output streams to
                    # the parent terminal alongside the file watcher.
                    pass
                else:
                    subprocess.run(["xcrun", "simctl", "launch", udid, IOS_BUNDLE_ID], check=False)
                    print("Launched iOS app on Simulator (best-effort).")
            except Exception:
                print("Failed to auto-run on Simulator; open the project in Xcode to run.")

    # Hot-reload file watcher
    if hot_reload and not prepare_only:
        _run_hot_reload(platform, project_dir, build_dir, show_logs=show_logs)


def _run_hot_reload(platform: str, project_dir: str, build_dir: str, show_logs: bool = True) -> None:
    """Watch `app/` for changes and push updated files to the device.

    When `show_logs` is true and targeting Android, `adb logcat` is
    streamed in parallel so Python print and exception output stays
    visible alongside hot-reload notifications.

    Args:
        platform: Either `"android"` or `"ios"`.
        project_dir: Absolute path to the user's project root.
        build_dir: Absolute path to the staged build directory.
        show_logs: Whether to stream device logs in parallel.
    """
    from ..hot_reload import FileWatcher

    app_dir = os.path.join(project_dir, "app")

    def on_change(changed_files: List[str]) -> None:
        pushed: List[str] = []
        for fpath in changed_files:
            rel = os.path.relpath(fpath, project_dir)
            print(f"[hot-reload] Changed: {rel}")
            if _push_hot_reload_file(platform, fpath, rel):
                pushed.append(fpath)
            else:
                print(f"[hot-reload] Failed to push {rel}")
        if pushed:
            manifest = _write_hot_reload_manifest(pushed, project_dir, build_dir)
            if _push_hot_reload_file(platform, manifest, "reload.json"):
                print(f"[hot-reload] Signaled reload for {len(pushed)} file(s).")
            else:
                print("[hot-reload] Failed to signal reload; app will not refresh automatically.")

    print("[hot-reload] Watching app/ for changes. Press Ctrl+C to stop.")
    watcher = FileWatcher(app_dir, on_change, interval=1.0)
    watcher.start()

    log_proc: Optional[subprocess.Popen] = None
    if show_logs:
        if platform == "android":
            log_proc = _start_android_log_stream()
        elif platform == "ios":
            log_proc = _start_ios_log_stream()

    try:
        if log_proc is not None:
            log_proc.wait()
        else:
            import time

            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        _terminate_subprocess(log_proc)
        watcher.stop()
        print("\n[hot-reload] Stopped.")


def clean_project(args: argparse.Namespace) -> None:
    """Remove the local `build/` directory.

    Args:
        args: Parsed argparse namespace (unused; accepted for the
            `set_defaults(func=...)` dispatch shape).
    """
    # Define the build directory
    build_dir: str = os.path.join(os.getcwd(), "build")

    # Check if the build directory exists
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
        print("Removed build/ directory.")
    else:
        print("No build/ directory to remove.")


def main() -> None:
    """Entry point for the `pn` console script.

    Wires up the `init`, `run`, and `clean` subcommands and dispatches
    to the corresponding handler.
    """
    parser = argparse.ArgumentParser(prog="pn", description="PythonNative CLI")
    subparsers = parser.add_subparsers()

    # Create a new command 'init' that calls init_project
    parser_init = subparsers.add_parser("init")
    parser_init.add_argument("name", nargs="?", help="Project name (defaults to current directory name)")
    parser_init.add_argument("--force", action="store_true", help="Overwrite existing files if present")
    parser_init.set_defaults(func=init_project)

    # Create a new command 'run' that calls run_project
    parser_run = subparsers.add_parser("run")
    parser_run.add_argument("platform", choices=["android", "ios"])
    parser_run.add_argument(
        "--prepare-only",
        action="store_true",
        help="Extract templates and stage app without building",
    )
    parser_run.add_argument(
        "--hot-reload",
        action="store_true",
        help="Watch app/ for changes and push updates to the running app",
    )
    parser_run.add_argument(
        "--no-logs",
        action="store_true",
        help="Don't attach to the app's stdout/stderr after launching (default: stream logs)",
    )
    parser_run.set_defaults(func=run_project)

    # Create a new command 'clean' that calls clean_project
    parser_clean = subparsers.add_parser("clean")
    parser_clean.set_defaults(func=clean_project)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
