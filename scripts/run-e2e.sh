#!/usr/bin/env bash
# Build the e2e-suite example app and run the comprehensive Maestro suite.
#
# This script is the supported way for AI agents and humans to run the
# full E2E pass locally. It mirrors what CI does in .github/workflows/e2e.yml.
#
# Usage:
#     ./scripts/run-e2e.sh android [suite]
#     ./scripts/run-e2e.sh ios     [suite]
#
# Examples:
#     ./scripts/run-e2e.sh android                 # full suite
#     ./scripts/run-e2e.sh android components      # only the components suite
#     ./scripts/run-e2e.sh ios hooks               # only the hooks suite on iOS
#
# Available suites: full, components, hooks, navigation, layout, styling,
# animations, misc.
#
# Prerequisites:
#     - `pn` CLI available (e.g. via `pip install -e .`).
#     - `maestro` CLI on PATH (https://maestro.dev/).
#     - For Android: an emulator running.
#     - For iOS: a simulator running (and `idb-companion` installed).
#
# The script:
#     1. Builds + installs the e2e-suite app via `pn run <platform> --no-logs`.
#     2. Picks the right Maestro YAML based on platform + suite.
#     3. Runs `maestro test` up to ``MAESTRO_MAX_ATTEMPTS`` times (default
#        2) and exits with the last attempt's exit code.
#
# A successful run prints "All E2E suites passed." at the end and exits 0.
# Any failed flow is reported by Maestro in its standard format; see
# tests/e2e/AGENTS.md for guidance on interpreting failures.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

PLATFORM="${1:-android}"
SUITE="${2:-full}"

case "$PLATFORM" in
  android|ios) ;;
  *)
    echo "Error: platform must be 'android' or 'ios' (got: $PLATFORM)" >&2
    exit 2
    ;;
esac

if ! command -v pn > /dev/null; then
  echo "Error: 'pn' CLI not found on PATH. Install via 'pip install -e .'" >&2
  exit 2
fi

if ! command -v maestro > /dev/null; then
  echo "Error: 'maestro' CLI not found on PATH." >&2
  echo "Install: curl -Ls 'https://get.maestro.mobile.dev' | bash" >&2
  exit 2
fi

case "$PLATFORM" in
  android) APP_ID="com.pythonnative.android_template" ;;
  ios)     APP_ID="com.pythonnative.ios-template" ;;
esac

case "$SUITE" in
  full)
    if [[ "$PLATFORM" == "android" ]]; then
      MAESTRO_TARGET="tests/e2e/android.yaml"
    else
      MAESTRO_TARGET="tests/e2e/ios.yaml"
    fi
    ;;
  components|hooks|navigation|layout|styling|animations|misc)
    MAESTRO_TARGET="tests/e2e/suites/${SUITE}.yaml"
    ;;
  *)
    echo "Error: unknown suite '$SUITE'" >&2
    echo "Available suites: full, components, hooks, navigation, layout, styling, animations, misc" >&2
    exit 2
    ;;
esac

printf "\n==> Building e2e-suite app for %s\n" "$PLATFORM"
pushd examples/e2e-suite > /dev/null
pn run "$PLATFORM" --no-logs
popd > /dev/null

run_maestro() {
  if [[ "$PLATFORM" == "ios" ]]; then
    maestro --platform ios test -e "APP_ID=$APP_ID" "$MAESTRO_TARGET"
  else
    maestro test -e "APP_ID=$APP_ID" "$MAESTRO_TARGET"
  fi
}

printf "\n==> Running Maestro suite: %s\n" "$MAESTRO_TARGET"

# Maestro's iOS XCUITest driver occasionally loses its connection to the
# app during long suites and surfaces transient "Application is not
# running" / "Request for viewHierarchy failed" errors that have nothing
# to do with the test under test. Allow one automatic retry of the whole
# suite (overridable via ``MAESTRO_MAX_ATTEMPTS``) so CI doesn't fail on
# driver flakes. A retry can also mask a genuine race in the suite, so
# treat the "retrying..." line as a signal to investigate, not just to
# trust the second pass.
MAX_ATTEMPTS="${MAESTRO_MAX_ATTEMPTS:-2}"
attempt=1
while (( attempt <= MAX_ATTEMPTS )); do
  if run_maestro; then
    break
  fi
  if (( attempt == MAX_ATTEMPTS )); then
    printf "\nMaestro suite failed after %d attempt(s).\n" "$attempt" >&2
    exit 1
  fi
  printf "\n==> Maestro suite failed (attempt %d/%d); retrying...\n" \
    "$attempt" "$MAX_ATTEMPTS" >&2
  attempt=$(( attempt + 1 ))
done

printf "\nAll E2E suites passed.\n"
