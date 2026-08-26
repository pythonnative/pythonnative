#!/usr/bin/env bash
# Build the e2e-suite example app and run the comprehensive Maestro suite.
#
# This script is the supported way for AI agents and humans to run the
# full E2E pass locally. It mirrors what CI does in .github/workflows/e2e.yml.
#
# Usage:
#     ./scripts/run-e2e.sh android [suite ...]
#     ./scripts/run-e2e.sh ios     [suite ...]
#
# Examples:
#     ./scripts/run-e2e.sh android                     # full suite
#     ./scripts/run-e2e.sh android components          # only the components suite
#     ./scripts/run-e2e.sh ios hooks                   # only the hooks suite on iOS
#     ./scripts/run-e2e.sh android hooks navigation    # two categories, one session
#
# Available suites: full, components, hooks, navigation, layout, styling,
# animations, gestures, misc.
#
# Multiple category suites can be passed at once; they run sequentially in
# a single Maestro session (and against a single emulator/simulator boot).
# CI uses this to shard the Android run into a few balanced groups so no
# single emulator session has to survive the entire 60-flow marathon;
# GitHub-hosted Android emulators grow unstable under ~15 minutes of
# sustained Maestro driving and start reporting "device offline". See
# .github/workflows/e2e.yml and tests/e2e/AGENTS.md.
#
# Prerequisites:
#     - `pn` CLI available (e.g. via `pip install -e .`).
#     - `maestro` CLI on PATH (https://maestro.dev/).
#     - For Android: an emulator running.
#     - For iOS: a simulator running.
#
# The script:
#     1. Builds + installs the e2e-suite app via `pn run <platform> --no-logs`.
#     2. Resolves each requested suite to its Maestro YAML target.
#     3. Runs `maestro test` (over all targets) up to ``MAESTRO_MAX_ATTEMPTS``
#        times (default 2) and exits with the last attempt's exit code.
#
# A successful run prints "All E2E suites passed." at the end and exits 0.
# Any failed flow is reported by Maestro in its standard format; see
# tests/e2e/AGENTS.md for guidance on interpreting failures.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

PLATFORM="${1:-android}"
shift || true
# Remaining args are suite names; default to the full aggregate suite.
SUITES=("$@")
if [[ ${#SUITES[@]} -eq 0 ]]; then
  SUITES=("full")
fi

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

# Resolve the app/bundle id straight from the example's pythonnative.toml so
# this stays correct no matter what id the config declares.
APP_ID="$(cd examples/e2e-suite && pn app-id "$PLATFORM")"
if [[ -z "$APP_ID" ]]; then
  echo "Error: could not resolve APP_ID via 'pn app-id $PLATFORM'." >&2
  exit 2
fi

# Resolve each requested suite to a Maestro YAML target. ``full`` expands
# to the platform's master aggregate; the category names map to the
# per-category suite files under tests/e2e/suites/.
MAESTRO_TARGETS=()
for suite in "${SUITES[@]}"; do
  case "$suite" in
    full)
      if [[ "$PLATFORM" == "android" ]]; then
        MAESTRO_TARGETS+=("tests/e2e/android.yaml")
      else
        MAESTRO_TARGETS+=("tests/e2e/ios.yaml")
      fi
      ;;
    components|components-a|components-b|hooks|navigation|layout|styling|animations|gestures|misc)
      MAESTRO_TARGETS+=("tests/e2e/suites/${suite}.yaml")
      ;;
    *)
      echo "Error: unknown suite '$suite'" >&2
      echo "Available suites: full, components, components-a, components-b, hooks, navigation, layout, styling, animations, gestures, misc" >&2
      exit 2
      ;;
  esac
done

printf "\n==> Building e2e-suite app for %s\n" "$PLATFORM"
pushd examples/e2e-suite > /dev/null
pn run "$PLATFORM" --no-logs
popd > /dev/null

run_maestro() {
  if [[ "$PLATFORM" == "ios" ]]; then
    maestro --platform ios test -e "APP_ID=$APP_ID" "${MAESTRO_TARGETS[@]}"
  else
    maestro test -e "APP_ID=$APP_ID" "${MAESTRO_TARGETS[@]}"
  fi
}

printf "\n==> Running Maestro suite(s): %s\n" "${MAESTRO_TARGETS[*]}"

# Maestro's iOS XCUITest driver occasionally loses its connection to the
# app during long suites and surfaces transient "Application is not
# running" / "Request for viewHierarchy failed" errors that have nothing
# to do with the test under test. Allow one automatic retry of the whole
# suite (overridable via ``MAESTRO_MAX_ATTEMPTS``) so CI doesn't fail on
# driver flakes. A retry can also mask a genuine race in the suite, so
# treat the "retrying..." line as a signal to investigate, not just to
# trust the second pass.

# Kill the app so the next Maestro attempt starts from a cold launch
# (open_demo relaunches a dead app). A failed attempt can leave the app
# mid-demo with dirty in-process state (e.g. module-level counters some
# demos display), which would make a same-process retry fail assertions
# that hold on a first visit.
terminate_app() {
  if [[ "$PLATFORM" == "ios" ]]; then
    xcrun simctl terminate booted "$APP_ID" 2> /dev/null || true
  else
    adb shell am force-stop "$APP_ID" 2> /dev/null || true
  fi
}

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
  printf "\n==> Maestro suite failed (attempt %d/%d); restarting app and retrying...\n" \
    "$attempt" "$MAX_ATTEMPTS" >&2
  terminate_app
  attempt=$(( attempt + 1 ))
done

printf "\nAll E2E suites passed.\n"
