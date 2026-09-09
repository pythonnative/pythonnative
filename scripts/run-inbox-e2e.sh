#!/usr/bin/env bash
# Build the separately packaged SDK extension and verify the reference app.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLATFORM="${1:?Usage: run-inbox-e2e.sh ios|android}"
case "$PLATFORM" in ios|android) ;; *) exit 2 ;; esac
cd "$ROOT_DIR"
uv build --wheel examples/inbox-extension --out-dir examples/inbox/vendor
cd examples/inbox
pn run "$PLATFORM" --no-logs
APP_ID="$(pn app-id "$PLATFORM")"
cd "$ROOT_DIR"
maestro --platform "$PLATFORM" test -e "APP_ID=$APP_ID" tests/e2e/reference/inbox.yaml
