#!/usr/bin/env bash
#
# test.sh — Run the test suite with coverage.
#
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
    echo "No .venv found — run ./setup.sh first" >&2
    exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> pytest..."
exec python -m pytest tests/ -v --tb=short -q --cov=underwrite --cov-report=term-missing
