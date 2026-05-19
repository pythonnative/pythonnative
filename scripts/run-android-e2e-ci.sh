#!/usr/bin/env bash
# Build the hello-world Android app and run Maestro E2E tests in CI.

set -Eeuo pipefail

dump_android_debug() {
  local status=$?
  trap - ERR
  set +e

  echo "::group::Android E2E debug"
  adb devices
  adb shell dumpsys window | grep -E "mCurrentFocus|mFocusedApp" || true
  adb shell dumpsys activity top | sed -n "1,120p" || true
  adb shell uiautomator dump /sdcard/window.xml || true
  adb shell cat /sdcard/window.xml || true
  adb logcat -d -t 1000 \
    PythonNative:D \
    MainActivity:D \
    ScreenFragment:D \
    python.stdout:I \
    python.stderr:E \
    AndroidRuntime:E \
    '*:S' || true
  echo "::endgroup::"

  exit "$status"
}

trap dump_android_debug ERR

export MAESTRO_CLI_NO_ANALYTICS=1

cd examples/hello-world
pn run android --no-logs

cd ../..
maestro test tests/e2e/android.yaml
