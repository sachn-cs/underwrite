#!/usr/bin/env bash
#
# lint.sh — Run ruff linter (check + format) and mypy type checker.
#
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
    echo "No .venv found — run ./setup.sh first" >&2
    exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> ruff check..."
ruff check underwrite/ tests/

echo "==> ruff format (check)..."
ruff format underwrite/ tests/ --check

echo "==> mypy..."
mypy underwrite/

echo "Lint passed."
