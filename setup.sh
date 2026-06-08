#!/usr/bin/env bash
#
# setup.sh — Idempotent local development environment bootstrap
#
# Usage:  ./setup.sh
#
# Detects the project structure, creates a virtual environment,
# installs dependencies (editable + dev extras), configures
# pre-commit hooks, copies default environment files, and
# validates the result.
#
set -euo pipefail
shopt -s globstar nullglob

# ── Colours ──────────────────────────────────────────────────────────────────
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m' # No Colour

# ── Helpers ──────────────────────────────────────────────────────────────────

log_step()   { printf "${CYAN}==>${NC} %s\n" "$*"; }
log_ok()     { printf "${GREEN}  [✓]${NC} %s\n" "$*"; }
log_warn()   { printf "${YELLOW}  [!]${NC} %s\n" "$*"; }
log_fail()   { printf "${RED}  [✗]${NC} %s\n" "$*"; return 1; }

die()        { printf "${RED}Error:${NC} %s\n" "$*" >&2; exit 1; }

# ── Prerequisites ────────────────────────────────────────────────────────────

check_prereqs() {
    log_step "Checking prerequisites..."

    local missing=0
    for cmd in python3 pip git; do
        if command -v "$cmd" &>/dev/null; then
            log_ok "$cmd found ($(command -v "$cmd"))"
        else
            log_fail "$cmd not found — please install it first"
            missing=$((missing + 1))
        fi
    done

    # Python must be >= 3.10
    if command -v python3 &>/dev/null; then
        local py_ver
        py_ver="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
        if python3 -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" &>/dev/null; then
            log_ok "Python $py_ver (>= 3.10)"
        else
            die "Python $py_ver is too old; need >= 3.10"
        fi
    fi

    if (( missing > 0 )); then
        die "Install the missing prerequisite(s) above and re-run setup.sh"
    fi
}

# ── Virtual environment ──────────────────────────────────────────────────────

setup_venv() {
    log_step "Setting up virtual environment..."

    if [[ -d .venv && -x .venv/bin/python ]]; then
        log_ok "Virtual environment already exists at .venv/"
    else
        python3 -m venv .venv
        log_ok "Created virtual environment at .venv/"
    fi

    # shellcheck disable=SC1091
    source .venv/bin/activate

    log_step "Upgrading pip, setuptools, wheel..."
    pip install --quiet --upgrade pip setuptools wheel
    log_ok "pip, setuptools, wheel are up to date"
}

# ── Dependency installation ──────────────────────────────────────────────────

install_deps() {
    log_step "Installing project dependencies..."

    if [[ -f pyproject.toml ]]; then
        if grep -q '"dev"' pyproject.toml 2>/dev/null || grep -q "'dev'" pyproject.toml 2>/dev/null; then
            log_ok "Found pyproject.toml with dev extras"
            pip install --quiet -e ".[dev]"
        else
            pip install --quiet -e .
        fi
    elif [[ -f requirements-dev.txt ]]; then
        log_ok "Found requirements-dev.txt"
        pip install --quiet -e .
        pip install --quiet -r requirements-dev.txt
    elif [[ -f requirements.txt ]]; then
        log_ok "Found requirements.txt"
        pip install --quiet -r requirements.txt
    else
        log_warn "No dependency manifest found — installing package in editable mode"
        pip install --quiet -e .
    fi

    log_ok "Dependencies installed"
}

# ── Pre-commit hooks ─────────────────────────────────────────────────────────

setup_precommit() {
    if [[ ! -f .pre-commit-config.yaml ]]; then
        log_warn "No .pre-commit-config.yaml found — skipping pre-commit setup"
        return
    fi

    log_step "Configuring pre-commit hooks..."

    if command -v pre-commit &>/dev/null; then
        log_ok "pre-commit is available"
    else
        pip install --quiet pre-commit
        log_ok "Installed pre-commit"
    fi

    if pre-commit install &>/dev/null; then
        log_ok "Pre-commit hooks installed"
    else
        log_warn "pre-commit install failed — hooks not active"
    fi
}

# ── Environment file ─────────────────────────────────────────────────────────

setup_env_file() {
    if [[ ! -f .env.example ]]; then
        return
    fi

    if [[ -f .env ]]; then
        log_ok ".env already exists — keeping existing file"
    else
        cp .env.example .env
        log_ok "Created .env from .env.example (review and adjust as needed)"
    fi
}

# ── Validation ───────────────────────────────────────────────────────────────

run_validation() {
    log_step "Validating environment..."

    # shellcheck disable=SC1091
    source .venv/bin/activate

    if [[ "$(command -v python3)" == *".venv/"* ]]; then
        log_ok "Virtual environment is active"
    else
        log_fail "Virtual environment is NOT active"
        return 1
    fi

    if python3 -c "import underwrite" &>/dev/null; then
        log_ok "Package 'underwrite' imports successfully"
    else
        log_fail "Package 'underwrite' cannot be imported"
        return 1
    fi

    local ver
    ver="$(python3 -c "import underwrite; print(underwrite.__version__, end='')" 2>/dev/null || echo "unknown")"
    log_ok "Package version: $ver"

    log_step "Checking key dev tools..."
    for tool in ruff mypy pytest; do
        if command -v "$tool" &>/dev/null; then
            log_ok "$tool found"
        else
            log_warn "$tool not found in PATH"
        fi
    done

    log_ok "Environment validation passed"
}

# ── Optional enhancements ────────────────────────────────────────────────────

setup_direnv() {
    if [[ -f .envrc ]]; then
        if command -v direnv &>/dev/null; then
            direnv allow &>/dev/null || true
            log_ok "direnv allowed (.envrc present)"
        else
            log_warn ".envrc found but direnv is not installed — install with: brew install direnv"
        fi
    fi
}

setup_docker() {
    if [[ -f docker-compose.yml ]] && command -v docker &>/dev/null; then
        log_ok "docker-compose.yml detected (not started automatically)"
    fi
}

# ── Summary ──────────────────────────────────────────────────────────────────

print_summary() {
    printf "\n${GREEN}Setup complete.${NC}\n\n"
    printf "Activate the environment:\n\n"
    printf "  ${CYAN}source .venv/bin/activate${NC}\n\n"
    printf "Then you can run:\n\n"
    printf "  ${CYAN}make lint${NC}       — ruff check\n"
    printf "  ${CYAN}make typecheck${NC}  — mypy check\n"
    printf "  ${CYAN}make test${NC}       — run tests\n"
    printf "  ${CYAN}make clean${NC}      — remove artifacts\n\n"
    printf "Or use the helper scripts:\n\n"
    printf "  ${CYAN}./lint.sh${NC}       — lint + format check\n"
    printf "  ${CYAN}./test.sh${NC}       — run test suite\n"
    printf "  ${CYAN}./cleanup.sh${NC}    — remove all artifacts\n"
}

# ── Main ─────────────────────────────────────────────────────────────────────

main() {
    printf "${CYAN}━━━ Underwrite — Development Environment Setup ━━━${NC}\n\n"

    check_prereqs
    setup_venv
    install_deps
    setup_precommit
    setup_env_file
    setup_direnv
    setup_docker
    run_validation
    print_summary
}

main "$@"
