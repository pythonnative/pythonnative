#!/usr/bin/env bash
# Run the same checks as .github/workflows/ci.yml locally, in the same order.
# Stops at the first failure. If this script is green, CI should be green too.
#
# Uses uv to manage the project venv and dev dependencies. `uv sync` creates
# and updates .venv itself, so there is no venv or activation step. Install
# uv first:
#   curl -LsSf https://astral.sh/uv/install.sh | sh
#
# Usage:
#   ./scripts/check.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v uv > /dev/null; then
  echo "Error: 'uv' is not installed." >&2
  echo "Install: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

printf "\n==> Syncing dependencies (uv sync --locked --group dev)\n"
uv sync --locked --group dev

step() {
  printf "\n==> %s\n" "$1"
}

step "Lint (Ruff)"
uv run ruff check .

step "Format check (Black)"
uv run black --check src examples tests

step "Type check (MyPy)"
uv run mypy

step "Type check the Inbox example (strict)"
(cd examples/inbox && MYPYPATH=../inbox-extension/src uv run --project ../.. mypy --strict app)

step "Type check the e2e suite (strict)"
(cd examples/e2e-suite && env -u MYPYPATH uv run --project ../.. mypy --strict app)

step "Rules of hooks (pn lint)"
uv run pn lint src/pythonnative examples

step "Build package (sdist + wheel)"
uv build

step "Run tests (pytest)"
uv run pytest -q

step "Check E2E coverage"
uv run scripts/check-e2e-coverage.py

printf "\nAll CI checks passed.\n"
