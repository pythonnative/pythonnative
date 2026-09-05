# PyPI packages

A PythonNative app runs on an embedded CPython, so its third-party
packages have to be resolved for the **phone**, not for the laptop
running `pn`. This guide explains what works, how the CLI resolves and
bundles packages for each device target, and how to check a package
before you build.

## Declare requirements

List pip requirements in `[requirements].packages` in
`pythonnative.toml`. Specifiers work the way they do in a
`requirements.txt`:

```toml
[requirements]
packages = ["httpx>=0.27", "numpy", "pillow~=11.0"]
```

Every `pn run` and `pn build` resolves that list for each target the
build needs, installs the resolved wheels, and bundles them into the
app. Nothing from your host environment leaks in: a package that's
importable on your Mac but has no wheel for the device is a build
error, not a runtime `ImportError`.

!!! warning "Don't list `pythonnative`"
    The CLI bundles the installed `pythonnative` package directly.
    Validation rejects it in `[requirements].packages`.

## What works

**Pure-Python packages** (`py3-none-any` wheels) work on every target.

**Binary wheels** (compiled extensions) work when the package publishes
a wheel for the target:

| Target | Platform tags | Where wheels come from |
| --- | --- | --- |
| iOS device | `ios_13_0_arm64_iphoneos` | PyPI (PEP 730) and [BeeWare's index](https://pypi.anaconda.org/beeware/simple) |
| iOS Simulator | `ios_13_0_arm64_iphonesimulator`, `ios_13_0_x86_64_iphonesimulator` | PyPI and BeeWare's index |
| Android arm64-v8a | `android_24_arm64_v8a` | PyPI (PEP 738) and [Chaquopy's index](https://chaquo.com/pypi-13.1/) |
| Android x86_64 (emulator) | `android_24_x86_64` | PyPI and Chaquopy's index |

**No wheel for the target** is a hard failure. pip runs with
`--only-binary=:all:` because it can't cross-compile an sdist for a
foreign platform, and pure-Python fallbacks that live inside an sdist
(PyYAML, MarkupSafe) can't be used either.

### Downgrades

When the newest release of a package has no wheel for a target, pip
walks back through older releases until it finds one that does.
Chaquopy builds its Android wheels itself and typically lags PyPI by a
release line, so most binary packages resolve to a slightly older
version on Android than on iOS or your desktop. `pn deps` marks these
with `[!!]` and prints the desktop version alongside. Pin a version in
`[requirements].packages` if the API difference matters to you.

pydantic is the notable case: pydantic 2 needs `pydantic-core`, which
has no iOS or Android wheel, so an unpinned `pydantic` resolves to the
1.x line everywhere. Pin `pydantic<2` explicitly so the choice is
visible in your config.

## Check before you build: `pn deps`

`pn deps` runs the same resolution the build does, for every target,
without installing anything:

```console
$ pn deps
Resolving 3 requirement(s) for Python 3.13 across 4 target(s)...

iOS device (arm64, iOS 13.0+)
  [ok] httpx 0.28.1     pure Python
  [ok] numpy 2.5.2.post1  binary wheel  ios_13_0_arm64_iphoneos  (BeeWare)
  [ok] pillow 12.3.0      binary wheel  ios_13_0_arm64_iphoneos  (PyPI)
  ...

Android arm64-v8a (API 24+)   (preview; Chaquopy resolves again inside the Gradle build)
  [ok] httpx 0.28.1     pure Python
  [!!] numpy 1.26.2     binary wheel  android_24_arm64_v8a  (Chaquopy)
       older than the desktop resolution (2.5.2): newer releases have no wheel here
  ...

Older release selected for: numpy ([!!] above). Pin a version in [requirements].packages if the API difference matters.
All 4 targets resolved.
```

- `pn deps ios` or `pn deps android` restricts the report to one
  platform.
- `pn deps --json` prints the same data as a document for scripting.
- The command exits non-zero when any target can't be satisfied, so it
  works as a CI gate.

When a package can't be resolved, the report names the requirement,
the target, and the platform tags that would have been needed:

```console
iOS device (arm64, iOS 13.0+)
  [x] Could not resolve pandas for iOS device (arm64, iOS 13.0+) (Python 3.13).
      No matching distribution found for pandas
      iOS needs a wheel tagged for the device (ios_*_arm64_iphoneos) and, for 'pn run ios', the
      Simulator (ios_*_iphonesimulator). Pure-Python packages always work; for a C extension, check
      https://pypi.anaconda.org/beeware/simple or ask upstream for iOS wheels (PEP 730).
```

## Extra indexes

Private or self-hosted wheel indexes are searched after PyPI and the
platform indexes when listed in `[requirements].extra_index_urls`:

```toml
[requirements]
packages = ["mycompany-sdk"]
extra_index_urls = ["https://wheels.mycompany.example/simple"]
```

The same URLs are passed to Chaquopy for the Android build.

## How packages are bundled

- **iOS**: the CLI installs one `app_packages.<sdk>` directory per SDK
  (`iphoneos` for devices, `iphonesimulator` for the Simulator) under
  `build/ios/`, and the Xcode run script copies the slice that matches
  the SDK being built into the app bundle. `pn run ios` against a
  Simulator resolves only the Simulator slice; `pn build ios` resolves
  both.
- **Android**: the CLI writes `requirements.txt` and the pip index
  options into the staged Gradle project, and Chaquopy performs the
  authoritative install inside the Gradle build, once per ABI in
  `[android].abi_filters`. The `pn deps` Android columns are a fast
  preview of that step.

## Compatibility matrix

The table below is generated by `scripts/package-matrix.py` from
`tests/packages/matrix.toml` against the live indexes. The `packages`
CI workflow re-runs the check weekly and on any change to the resolver
or manifest, so the table and the test suite can't disagree for long.
"ok" means the package resolves to a wheel for that target; "older"
means it resolves, but to an older release than a desktop gets; "no
wheel" means resolution fails.

<!-- matrix:start -->
<!-- Generated by scripts/package-matrix.py on 2026-09-03 for Python 3.13. Edit tests/packages/matrix.toml, not this table. -->
| Package | Kind | iOS device | iOS Simulator | Android arm64-v8a | Android x86_64 | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `httpx` | pure | 0.28.1 | 0.28.1 | 0.28.1 | 0.28.1 | HTTP client; PythonNative's own `fetch` is a lighter alternative. |
| `attrs` | pure | 26.1.0 | 26.1.0 | 26.1.0 | 26.1.0 |  |
| `python-dateutil` | pure | 2.9.0.post0 | 2.9.0.post0 | 2.9.0.post0 | 2.9.0.post0 |  |
| `rich` | pure | 15.0.0 | 15.0.0 | 15.0.0 | 15.0.0 |  |
| `emoji` | pure | 2.15.0 | 2.15.0 | 2.15.0 | 2.15.0 | Used by examples/hello-world. |
| `numpy` | binary | 2.5.2.post1, binary | 2.5.2.post1, binary | 1.26.2 (latest 2.5.2), binary | 1.26.2 (latest 2.5.2), binary | iOS wheel from BeeWare (current release); Android wheel from Chaquopy's index (1.26 line). Exercised on device by the E2E suite. |
| `pillow` | binary | 12.3.0, binary | 12.3.0, binary | 11.0.0 (latest 12.3.0), binary | 11.0.0 (latest 12.3.0), binary | iOS wheel on PyPI itself (PEP 730); Android from Chaquopy's index. |
| `cryptography` | binary | 47.0.0 (latest 50.0.1), binary | 47.0.0 (latest 50.0.1), binary | 42.0.8 (latest 50.0.1), binary | 42.0.8 (latest 50.0.1), binary | Pulls cffi, also binary. |
| `cffi` | binary | 2.1.1, binary | 2.1.1, binary | 1.17.1 (latest 2.1.1), binary | 1.17.1 (latest 2.1.1), binary |  |
| `pandas` | binary | no wheel | no wheel | 2.1.3 (latest 3.0.5), binary | 2.1.3 (latest 3.0.5), binary | No iOS wheel published yet. |
| `lxml` | binary | no wheel | no wheel | 5.3.0 (latest 6.1.3), binary | 5.3.0 (latest 6.1.3), binary | No iOS wheel published yet. |
| `pyyaml` | binary | no wheel | no wheel | 6.0.3, binary | 6.0.3, binary | No iOS wheel; `ruamel.yaml` is a pure-Python alternative. |
| `markupsafe` | binary | no wheel | no wheel | 3.0.3, binary | 3.0.3, binary | Ships only sdist + binary wheels; the pure-Python fallback inside the sdist can't be used because pip won't build for a foreign platform. |
| `pydantic` | pure | 1.10.26 (latest 2.13.5) | 1.10.26 (latest 2.13.5) | 1.10.26 (latest 2.13.5) | 1.10.26 (latest 2.13.5) | Resolves to the 1.x line: pydantic 2 needs pydantic-core, which has no iOS or Android wheel. Pin `pydantic<2` explicitly or expect the older API. |
<!-- matrix:end -->

To add a package to the matrix, append a `[[package]]` entry to
`tests/packages/matrix.toml` with the expected outcome per platform and
run `uv run pytest tests/packages -m network`.

## Python version

`[app].python_version` selects the embedded interpreter (`3.13` or
`3.14`). Wheels are matched against that version, not your host's, so
`pn doctor` checks that a matching `python3.X` is on `PATH` for pip to
run under. If a package has wheels for 3.13 but not 3.14 yet, set
`python_version = "3.13"`.

## Next steps

- Configure requirements and indexes in
  [Configuration](configuration.md#requirements).
- Platform build details: [iOS](ios.md) and [Android](android.md).
- The `pn deps` reference in the [CLI](../api/cli.md).
