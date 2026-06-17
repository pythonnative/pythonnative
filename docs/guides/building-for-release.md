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
toolchain: for Android, `adb`, a JDK, and whether release signing is
configured; for iOS, macOS, Xcode, `simctl`, and a development team. It
exits non-zero on anything that will block a build, so you can gate CI
on it.

---

## Android

`pn build android` runs `assembleRelease` and `bundleRelease`, producing
both an APK and a Play-ready AAB. Artifacts are reported at the end of
the build and live under the staged project:

```
build/android/android_template/app/build/outputs/apk/release/app-release.apk
build/android/android_template/app/build/outputs/bundle/release/app-release.aab
```

### Signing

Without signing configured, Gradle emits an **unsigned** release APK
(`app-release-unsigned.apk`), fine for inspection, not for the store.
To produce signed artifacts, create a keystore once:

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

`pn build ios` archives the app for a device with `xcodebuild archive`,
embeds the device CPython slice into the archive, and exports a signed
`.ipa` with `xcodebuild -exportArchive`. Outputs:

```
build/ios/ios_template/build/export/*.ipa
build/ios/ios_template/build/ios_template.xcarchive
```

!!! warning "Experimental"
    The device archive/export path embeds and re-signs the embedded
    Python framework. Treat it as experimental and verify on a real
    device before relying on it for store submission.

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
`exportOptions.plist` that `xcodebuild -exportArchive` consumes. If
export fails, the error points you back at `[ios.signing]`.

### Embedded Python runtime

iOS has no system Python, so PythonNative embeds CPython from the
[Python-Apple-support](https://github.com/beeware/Python-Apple-support)
project. On the first iOS build, `pn` downloads the pinned, checksum-
verified runtime for your `app.python_version` and caches it under
`build/ios/ios_runtime/`. The correct slice (Simulator vs. device) is
embedded into the app bundle along with the standard library, your
`app/` sources, the bundled `pythonnative` package, and any pure-Python
`[requirements].packages`.

iOS currently ships a verified runtime for **Python 3.11**; set
`python_version = "3.11"` in `[app]` for device builds.

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

If Pillow isn't installed the build still succeeds; it just keeps the
template's default assets. `pn doctor` reports whether Pillow is
available.

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
