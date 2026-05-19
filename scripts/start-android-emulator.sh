#!/usr/bin/env bash
# Start the local Android emulator used for testing pythonnative apps.
#
# Usage:
#   ./scripts/start-android-emulator.sh [avd-name]
#
# Defaults to the "Medium_Phone" AVD. List available AVDs with:
#   ~/Library/Android/sdk/emulator/emulator -list-avds

set -euo pipefail

AVD_NAME="${1:-Medium_Phone}"
EMULATOR_BIN="${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}/emulator/emulator"

if [[ ! -x "$EMULATOR_BIN" ]]; then
  echo "Error: emulator binary not found at $EMULATOR_BIN" >&2
  echo "Set ANDROID_SDK_ROOT or install the Android SDK emulator." >&2
  exit 1
fi

exec "$EMULATOR_BIN" -avd "$AVD_NAME"
