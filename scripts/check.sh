#!/usr/bin/env bash
# Run the same checks as .github/workflows/ci.yml locally, in the same order.
# Stops at the first failure. If this script is green, CI should be green too.
#
# Uses uv to manage the project venv and CI dependencies. Install uv first:
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

if [[ ! -x ".venv/bin/python" ]]; then
  printf "\n==> Creating .venv (uv venv --seed)\n"
  uv venv --seed
fi

printf "\n==> Syncing CI dependencies\n"
uv pip install --python .venv/bin/python -e ".[ci]" build

PY=".venv/bin/python"

step() {
  printf "\n==> %s\n" "$1"
}

step "Lint (Ruff)"
"$PY" -m ruff check .

step "Format check (Black)"
"$PY" -m black --check src examples tests

step "Type check (MyPy)"
"$PY" -m mypy --install-types --non-interactive

step "Build package (sdist + wheel)"
"$PY" -m build

step "Run tests (pytest)"
"$PY" -m pytest -q

step "Check E2E coverage"
"$PY" scripts/check-e2e-coverage.py

printf "\nAll CI checks passed.\n"
