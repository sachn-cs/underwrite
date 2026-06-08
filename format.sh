#!/usr/bin/env bash
#
# format.sh — Auto-format all Python files with ruff.
#
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
    echo "No .venv found — run ./setup.sh first" >&2
    exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> ruff format..."
ruff format underwrite/ tests/

echo "==> ruff check --fix..."
ruff check --fix underwrite/ tests/

echo "Format complete."
