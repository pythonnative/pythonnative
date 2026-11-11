# Building for release

`pn run` is for iterating on a device or simulator. When you're ready to
ship, `pn build` produces standalone, distributable artifacts:

```bash
pn build android     # release APK + AAB
pn build ios         # signed .ipa via xcodebuild archive + export
```

Pass `--debug` to build the debug variant instead (a debug APK on
Android; a Simulator `.app` on iOS):

```bash
pn build android --debug
pn build ios --debug
```

When the build looks right, [`pn submit`](#submitting-to-the-stores) uploads
it. To try the release configuration first, `pn run --release` builds and
launches it on a simulator or emulator, with no dev server.

## What a release build refuses

A release build stops, rather than producing something a store will reject,
when:

- `[assets].icon` isn't set, or Pillow isn't installed to render it;
- an Android release has no `[android.signing]` key;
- a capability in `[plugins].use` needs a `[permissions]` entry that's
  missing, because iOS crashes an app that reaches a protected API without
  its usage string.
- a [worklet](motion.md#release-builds) uses Python the UI thread can't
  run. Release builds ship without source, so staging compiles every
  worklet into `pn_worklets.json` first and lists each one that fails;
  `pn lint` reports the same errors as `PN201`.

`--allow-unsigned` turns off the icon and signing checks for a smoke build
that won't reach a store. On iOS it signs ad hoc and stops at the archive.
PythonNative's own CI builds this way:

```bash
pn build android --allow-unsigned
pn build ios --allow-unsigned
```

`pn build` reads identity, permissions, assets, and signing from
[`pythonnative.toml`](configuration.md). Run [`pn doctor`](#check-first-pn-doctor)
first to confirm the toolchain is ready.

---

## Check first: `pn doctor`

```bash
pn doctor android
pn doctor ios
```

`pn doctor` validates `pythonnative.toml` and checks the platform
toolchain: Android needs JDK 17 through 23, the configured SDK (36 by
default), NDK 28.2.13676358, and `adb`. iOS needs macOS, Xcode 26 or
later, and `simctl`. The doctor also reports signing, lockfile, and
privacy-manifest configuration. It
exits non-zero on anything that will block a build, so you can gate CI
on it.

---

## Frozen dependencies

Release builds with Python dependencies require a current `pn.lock` covering
all build targets. Resolve and review the lock before building:

```bash
pn deps android --lock
pn deps ios --lock
```

`pn deps --lock` prints the full resolution report first. A lock has to
cover every target, so if any target fails to resolve, it says which ones
failed, doesn't write `pn.lock`, and exits with status 1. Fix the failing
requirement (or the target's wheel availability) and run it again.

Commit the lock with your application. Changing requirements or replacing a
local wheel requires refreshing it. Release builds reject missing or stale
locks. A development build (`pn run`, or `pn build --debug`) with a stale
lock prints a warning and resolves the current requirements without the lock,
so you can keep iterating before you refresh it. Native extension manifests
pin SwiftPM and Maven dependencies to exact versions.

## What a release bundle leaves out

Every build bundles a copy of the `pythonnative` package. Debug builds
are dev clients, so their copy is complete. Release builds leave out the
modules that exist only for development:

- the `pn` CLI and build tooling (`pythonnative/cli`, `pythonnative/project`);
- the dev server and browser preview (`pythonnative/devserver`,
  `pythonnative/preview.py`, `pythonnative/bridge/web.py`);
- the dev client and Fast Refresh (`pythonnative/devclient.py`,
  `pythonnative/hot_reload.py`, `pythonnative/refresh.py`);
- the test helpers (`pythonnative/testing`, `pythonnative/bridge/fake.py`);
- the SDK code generators (`pythonnative/sdk/codegen.py`,
  `builtins.py`, `module_codegen.py`, and their templates).

The runtime never imports them, and the test suite checks that it stays
that way, so a release app behaves exactly like a debug build that isn't
connected to `pn start`. If your own code imports one of these modules,
it works in debug builds but fails with `ModuleNotFoundError` in a
release build; keep such imports in development-only code paths.

iOS release builds also omit the `NSLocalNetworkUsageDescription` that
debug builds add so they can reach `pn start` over Wi-Fi. If your app
uses the local network itself, declare the key with your own wording in
`[ios].extra_info_plist`.

## Android

`pn build android` runs `assembleRelease` and `bundleRelease`, producing
both an APK and a Play-ready AAB. Artifacts are reported at the end of
the build and live under the staged project:

```
build/android/android_template/app/build/outputs/apk/release/app-release.apk
build/android/android_template/app/build/outputs/bundle/release/app-release.aab
```

### Toolchain and packaged binaries

The template uses compile/target SDK 36, Gradle 8.13, Android Gradle Plugin
8.11.1, Kotlin 2.2.21, and NDK 28.2.13676358. Release builds reject a target
SDK below 36. These are PythonNative's supported build defaults, independent
of store submission deadlines.

After Gradle builds, PythonNative inspects the APK and AAB. Every packaged
64-bit ELF library must have 16 KB aligned LOAD segments, including Python
extensions inside Chaquopy assets. Uncompressed APK libraries must also be
ZIP aligned, and the AAB must request compatible generated APK alignment.
An error names the offending dependency. Rebuild or replace that dependency;
upgrading your app's NDK can't repair a prebuilt wheel. See Android's
[16 KB page-size guidance](https://developer.android.com/guide/practices/page-sizes).

### Signing

A release build fails without signing configured. Only `--allow-unsigned`
produces an **unsigned** release APK (`app-release-unsigned.apk`), which is
fine for inspection but not for the store. To produce signed artifacts, create
a keystore once:

```bash
keytool -genkeypair -v -keystore release.keystore \
  -alias myapp -keyalg RSA -keysize 2048 -validity 10000
```

…then point `pythonnative.toml` at it:

```toml
[android.signing]
keystore = "release.keystore"
key_alias = "myapp"
# store_password_env / key_password_env default to
# PN_ANDROID_KEYSTORE_PASSWORD / PN_ANDROID_KEY_PASSWORD
```

Passwords are **never** stored in the config, only the names of the
environment variables that hold them. Provide the secrets at build time:

```bash
export PN_ANDROID_KEYSTORE_PASSWORD=…
export PN_ANDROID_KEY_PASSWORD=…
pn build android
```

When signing is configured, `pn` injects a Gradle `signingConfig` into
the release build so the resulting APK/AAB are signed and upload-ready.

!!! tip "Keep keystores out of git"
    Commit neither the keystore nor the passwords. Store the keystore as
    a CI secret/file and inject the passwords via environment variables.

---

## iOS

`pn build ios` archives the app with `xcodebuild archive` and exports a
signed `.ipa` with `xcodebuild -exportArchive`. The Python framework,
standard library, and app code are installed and signed during the
Xcode build itself, so the archive needs no post-processing. Outputs:

```
build/ios/export/*.ipa
build/ios/ios_template.xcarchive
```

### Privacy manifests

The app's `PrivacyInfo.xcprivacy` starts with what the embedded runtime
itself uses: `SystemBootTime` (35F9.1), `DiskSpace` (E174.1), `FileTimestamp`
(C617.1), and `UserDefaults` (CA92.1). Each capability in `[plugins].use` adds
its own. Add your app's declarations with a path relative to the project;
they merge with the others:

```toml
[ios]
privacy_manifest = "assets/PrivacyInfo.xcprivacy"
```

PythonNativeKit ships its own resource-bundle manifest for preferences and
cache-file timestamps. Archive validation checks that the app and runtime
manifests are present and structurally valid before export. It also parses
manifests supplied by bundled dependencies. This check doesn't infer your
application's data collection or tracking. Declare those from your actual
behavior using Apple's
[privacy-manifest documentation](https://developer.apple.com/documentation/bundleresources/privacy-manifest-files).

Release builds also remove `bin/` and test suites from the wheels they bundle
on iOS. Those scripts carry a build machine's shebang, which stores flag.

### Bytecode everywhere

An app bundle is read-only, so the device can't cache what it compiles.
`pn` therefore compiles ahead of time, in every build:

- **Release builds** byte-compile your `app/` sources, every bundled
  package, and the embedded standard library to sourceless `.pyc` files
  and drop the `.py` files. That shrinks the bundle, speeds up launch,
  and avoids shipping plain-text source.
- **Debug builds** (`pn run`, `pn build --debug`) keep the `.py` files
  beside `__pycache__` bytecode, so tracebacks show source lines and Fast
  Refresh can read sources, while launch still skips compilation. Sources
  the dev client syncs are cached on the device after their first import.

Bytecode records bundle-relative file names (`app/main.py`), never paths
on your build machine. Because bytecode is version-specific, compiling
needs an interpreter matching `app.python_version`: the one running `pn`,
or `python3.13` (for example) on your `PATH`. iOS release builds fail
without one; debug builds warn and let the device compile at launch.
Android compiles with Chaquopy, which needs that same matching interpreter
on the build machine whenever the app has `[requirements]` packages to
install. `pn doctor` reports whether it found one.

### Signing

Set your Apple Developer Team ID and an export method:

```toml
[ios]
development_team = "ABCDE12345"

[ios.signing]
export_method = "app-store"          # development | ad-hoc | app-store | enterprise
provisioning_profile = "My App Distribution"
```

`development_team` drives signing during `archive`; `export_method` and
the optional `provisioning_profile` are written into the
`exportOptions.plist` that `xcodebuild -exportArchive` consumes. A
`provisioning_profile` also switches the archive itself to manual signing, so a
CI runner with no Xcode account can build. If export fails, the error points
you back at `[ios.signing]`.

With an App Store Connect API key in `PN_ASC_KEY_PATH`, `PN_ASC_KEY_ID`, and
`PN_ASC_ISSUER_ID`, automatic signing uses that key instead of an Xcode account.

### Embedded Python runtime

iOS has no system Python, so PythonNative embeds CPython from the
[Python-Apple-support](https://github.com/beeware/Python-Apple-support)
project. The first iOS build on a machine downloads the pinned,
checksum-verified runtime for your `app.python_version` into a cache
every project shares (`~/Library/Caches/pythonnative/ios/`, or
`$PN_CACHE_DIR/ios/`) and prepares it once: the standard library loses
CPython's test suite, GUI toolkits, installers, and test-only extension
modules, and the rest is compiled to bytecode. `pn clean` doesn't touch
this cache. The Xcode build links `Python.xcframework`, installs the
prepared standard library, and bundles your `app/` sources, the
`pythonnative` package, and the `[requirements].packages` resolved for
the SDK being built (device or Simulator), binary wheels included.

Pinned, verified runtimes exist for **Python 3.13 and 3.14**; set
`python_version` in `[app]` accordingly. Unpinned versions are
rejected rather than fetched unverified. See
[PyPI packages](pypi-packages.md) for how requirements are resolved
per target.

---

## App icon and splash

Provide a single high-resolution source image and PythonNative renders
every per-platform, per-density variant at build time:

```toml
[assets]
icon = "assets/icon.png"      # 1024x1024 PNG
splash = "assets/splash.png"
```

- **iOS**: a universal `AppIcon.appiconset` (Xcode resizes the rest)
  and a `Splash` image set referenced by the generated launch screen.
- **Android**: `mipmap-*` launcher icons at every density plus a round
  variant, and a centered icon for the Android 12+ splash screen.

Image processing needs [Pillow](https://python-pillow.org/), an optional
dependency:

```bash
pip install 'pythonnative[build]'
```

If Pillow isn't installed, a debug build keeps the template's default
assets. A release build with an icon fails instead, unless you pass
`--allow-unsigned`. `pn doctor` reports whether Pillow is available.

---

## Versioning

Two fields in `[app]` drive the store-visible version and the internal
build number:

```toml
[app]
version = "1.2.0"     # CFBundleShortVersionString / versionName
build = 7             # CFBundleVersion / versionCode (bump every upload)
```

Both stores reject a new upload that reuses an existing build number, so
increment `build` for each submission.

---

## Continuous integration

A typical release job:

```bash
pip install 'pythonnative[build]'
pn doctor android            # fail fast on a misconfigured runner
export PN_ANDROID_KEYSTORE_PASSWORD=$KEYSTORE_PW
export PN_ANDROID_KEY_PASSWORD=$KEY_PW
pn build android
```

`pn app-id android` / `pn app-id ios` print the resolved id, which is
handy for downstream steps (uploaders, smoke tests) that need it without
re-parsing the config.

---

## Prepare without building

To hand off to Android Studio or Xcode instead of building from the CLI,
stage and configure the native project without compiling:

```bash
pn run android --prepare-only
pn run ios --prepare-only
```

This writes a fully configured project (identity, permissions, icons,
relocated Android package) under `build/`, which you can open and build
with the native IDE, useful for debugging signing or build issues with
the platform's own tooling.

---

## Submitting to the stores

`pn submit` uploads the latest release build, with credentials from the
environment, so it runs the same on a laptop and in CI.

```bash
pn submit ios
pn submit android --track internal
```

**App Store Connect** needs an API key, created under Users and Access >
Integrations, and an `.ipa` from `export_method = "app-store"`:

```bash
export PN_ASC_KEY_PATH=AuthKey_ABC123.p8
export PN_ASC_KEY_ID=ABC123
export PN_ASC_ISSUER_ID=00000000-0000-0000-0000-000000000000
```

**Google Play** needs a service account's JSON key, granted access in the Play
Console under Users and permissions:

```bash
export PN_PLAY_SERVICE_ACCOUNT=play-service-account.json
```

Tracks are `internal`, `alpha`, `beta`, and `production`. Google requires an app's
first release to go through the Play Console, so use `--draft` until then.
`--path` uploads a specific artifact rather than the latest.

!!! warning "What hasn't been proven"
    PythonNative's CI builds and runs release artifacts and tests `pn submit`
    against a fake Play API and a stubbed `altool`. It can't hold store credentials, so
    a real upload is the first true test of your signing and store setup. Try
    TestFlight and an internal track well before a deadline.
