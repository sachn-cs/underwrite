# underwrite — Delegated Underwriting Protocol

[![CI](https://github.com/sachn-cs/unsecured-lending-underwriting/actions/workflows/ci.yml/badge.svg)](https://github.com/sachn-cs/unsecured-lending-underwriting/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12%20|%203.13-blue)](https://pypi.org/project/underwrite/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

A **nano-service platform** for unsecured lending underwriting. Each service is independently deployable, configuration-driven, and communicates over a shared in-process event bus with Ed25519 cryptographic attestation.

- **28 nano-services** — risk scoring (ML), fraud detection, KYC/AML, collateral management, loan origination (servicing), fee assessment, collections, recovery, notifications, governance, and more
- **Event-driven architecture** — typed events with Ed25519 signatures, saga orchestration, dead-letter queues, circuit breakers
- **Pluggable backends** — memory / filesystem / Postgres for state; local or OTLP for observability
- **Production-hardened** — 828+ tests, rate limiting, idempotency guards, distributed tracing, structured logging with PII redaction, Prometheus metrics, Kubernetes probes
- **Type-safe** — 90 source modules, fully typed (PEP 585/604), `py.typed` marker, ruff/mypy clean

---

## Documentation

Full documentation site at [`docs/`](docs/README.md):

| Area | Documents |
|------|-----------|
| **Getting Started** | [Installation](docs/INSTALLATION.md) · [Quickstart](docs/QUICKSTART.md) · [Configuration](docs/CONFIGURATION.md) · [Env Vars](docs/ENVIRONMENT_VARIABLES.md) |
| **Architecture** | [Overview](docs/ARCHITECTURE.md) · [System Design](docs/SYSTEM_DESIGN.md) · [Domain Model](docs/DOMAIN_MODEL.md) · [Design Decisions](docs/DESIGN_DECISIONS.md) |
| **Development** | [Guide](docs/DEVELOPMENT.md) · [Testing](docs/TESTING.md) · [Debugging](docs/DEBUGGING.md) · [Code Style](docs/CODE_STYLE.md) · [Build](docs/BUILD.md) |
| **Operations** | [Deployment](docs/DEPLOYMENT.md) · [Operations](docs/OPERATIONS.md) · [Observability](docs/OBSERVABILITY.md) · [Security](docs/SECURITY.md) · [Performance](docs/PERFORMANCE.md) |
| **Reference** | [API](docs/API.md) · [Troubleshooting](docs/TROUBLESHOOTING.md) · [FAQ](docs/FAQ.md) · [Glossary](docs/GLOSSARY.md) |
| **Project** | [Contributing](docs/CONTRIBUTING.md) · [Maintenance](docs/MAINTENANCE.md) · [Roadmap](docs/ROADMAP.md) · [Changelog](CHANGELOG.md) |

---

## Prerequisites

- **Python 3.10+**
- **PostgreSQL 14+** (only if using `underwrite[postgres]` backend)
- **Docker** (optional, for containerised deployment)

---

## Quick Start

```bash
# Clone and setup
git clone https://github.com/sachn-cs/unsecured-lending-underwriting.git
cd unsecured-lending-underwriting
./setup.sh

# Activate environment
source .venv/bin/activate

# Run all tests
pytest

# Start services interactively
underwrite run mechanism audit risk

# Check health
underwrite health
```

---

## Installation

```bash
# From PyPI
pip install underwrite

# With extras
pip install "underwrite[risk,serve,postgres,otlp,vault,aws]"

# Development
pip install -e ".[dev,risk,serve,postgres,otlp,vault,aws]"
```

### Optional Extras

| Extra | Provides |
|-------|----------|
| `risk` | NumPy, scikit-learn — ML risk scoring models |
| `serve` | Uvicorn, FastAPI — HTTP server (`underwrite serve`) |
| `postgres` | psycopg2-binary — Postgres state store |
| `otlp` | OpenTelemetry SDK — distributed tracing |
| `vault` | hvac — HashiCorp Vault secrets backend |
| `aws` | boto3 — AWS SES/SNS notifications |
| `gcs` | google-cloud-storage — GCS backup |
| `security` | bandit, pip-audit — vulnerability scanning |
| `dev` | pytest, ruff, mypy, hypothesis, testcontainers |

---

## Configuration

underwrite can be configured via **JSON config file**, **environment variables**, or **both** (env vars override).

### Config File

Create a default config:

```bash
underwrite init
```

This writes `underwrite.json` with sensible defaults. Edit it to enable/disable services and tune behaviour.

### Environment Variables

Every setting can be overridden via `UNDERWRITE_*` env vars. See [`.env.example`](.env.example) for the full list:

```bash
UNDERWRITE_STORE_BACKEND=postgres
UNDERWRITE_STORE_DSN=postgresql://user:pass@localhost:5432/underwrite
UNDERWRITE_LOG_LEVEL=DEBUG
UNDERWRITE_BUS_RATE_LIMIT=200
```

### HTTP Server Authentication

Set `UNDERWRITE_API_TOKEN` and start with `underwrite serve --require-auth` to require `Authorization: Bearer <token>` on every request.

---

## CLI Usage

```
underwrite — Delegated Underwriting Protocol — nano-service platform

Commands:
  init [PATH]              Create default config file
  run <service>...         Start one or more services
  list                     List all available nano-services
  identity <service>       Generate Ed25519 identity for a service
  health                   Show system health status
  dlq [--replay] [--max N] Show or replay dead-letter queue
  metrics                  Show metrics snapshot
  migrate                  Run pending schema migrations
  serve                    Start HTTP daemon (requires [serve] extra)
```

### Examples

```bash
# Start interactive services
underwrite run mechanism risk audit fraud fee collection recovery

# HTTP daemon on port 8080 with auth
UNDERWRITE_API_TOKEN=secret underwrite serve --host 0.0.0.0 --port 8080 --require-auth

# View dead-letter queue
underwrite dlq

# Replay failed events
underwrite dlq --replay --max 50
```

---

## HTTP API

When running with `underwrite serve`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/healthz` | GET | Kubernetes liveness probe |
| `/readyz` | GET | Kubernetes readiness probe |
| `/v1/health` | GET | Full system health (bus, store, services) |
| `/v1/metrics` | GET | Prometheus-format metrics |
| `/v1/publish` | POST | Publish a domain event |

### Publish Example

```bash
curl -X POST http://localhost:8080/v1/publish \
  -H "Content-Type: application/json" \
  -d '{"event_type": "loan_originated", "payload": {"loan_id": "abc123"}}'
```

All responses include `X-Request-ID` for tracing. The `--require-auth` flag enables bearer-token authentication.

---

## Docker

```bash
# Build
docker build -t underwrite .

# Run with Postgres
docker-compose up

# Or standalone
docker run -d -p 8080:8080 \
  -e UNDERWRITE_STORE_BACKEND=filesystem \
  underwrite serve --services mechanism,audit,risk
```

The container runs as non-root user `underwrite` (UID 1001). See [`docker-compose.yml`](docker-compose.yml) for the full setup.

---

## Development

```bash
# Automated bootstrap
./setup.sh

# Or manual
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,risk,serve,postgres,otlp,vault,aws]"
pre-commit install

# Run tests (with coverage)
pytest --cov=underwrite

# Lint
ruff check underwrite/ tests/
ruff format --check underwrite/ tests/

# Type check
mypy underwrite/

# Security audit
bandit -r underwrite/ -c pyproject.toml
pip-audit

# Build wheel + sdist
python -m build
```

### Companion Scripts

| Script | Purpose |
|--------|---------|
| `./setup.sh` | Idempotent environment bootstrap (venv, deps, pre-commit) |
| `./test.sh` | Run tests with coverage |
| `./lint.sh` | Run ruff check + mypy |
| `./format.sh` | Auto-format with ruff |
| `./cleanup.sh` | Remove all build/test artifacts |

### Makefile

```bash
make test       # pytest -v
make lint       # ruff check
make typecheck  # mypy
make build      # python -m build
make clean      # remove artifacts
```

---

## Project Structure

```
underwrite/                          # Source package (90 modules)
  __init__.py                        # Public API exports
  __bus__.py                         # Event bus — pub/sub, DLQ, rate limiter, idempotency
  __store__.py                       # State store — memory / file / postgres with CQRS
  __saga__.py                        # Saga orchestrator — per-saga locking, auto-rollback
  __authz__.py                       # Access control & Ed25519 signature verification
  __circuit__.py                     # Circuit breaker & retry policy
  __config__.py                      # Configuration engine (Pydantic)
  __runtime__.py                     # Service lifecycle manager
  __serve__.py                       # FastAPI HTTP server
  __cli__.py                         # CLI (typer-based, 9 commands)
  __events__.py                      # Event type registry
  __identity__.py                    # Ed25519 key management
  __logger__.py                      # Structured JSON logger with PII redaction
  __tracer__.py                      # OpenTelemetry distributed tracing
  __metrics__.py                     # Prometheus metrics collection
  __exceptions__.py                  # Domain exception hierarchy
  __version__.py                     # Auto-generated by setuptools-scm
  services/                          # 28 nano-service implementations
    base.py                          # NanoService ABC with ThreadPoolExecutor dispatch
    mechanism/                       # Delegation state machine (core)
    risk/                            # ML risk scoring (scikit-learn + JSON fallback)
    fraud/                           # Fraud detection
    fee/                             # Fee assessment & collection
    audit/                           # Event audit log
    collection/                      # Collections workflow
    recovery/                        # Recovery & rollback
    notification/                    # SES email + Twilio SMS dispatch
    document/                        # Document generation
    governance/                      # Governance rules engine
    collateral/                      # Collateral management
    kyc/                             # KYC/AML verification
    disbursement/                    # Loan disbursement (with idempotency guard)
    servicing/                       # Loan servicing (repayments, delinquency)
    kybp/                            # KYB (business verification)
    pricing/                         # Pricing engine
    provision/                       # Provisioning
    origination/                     # Origination workflow
    fulfillment/                     # Fulfillment workflow
    agreement/                       # Agreement management
    ...                              # (remaining nano-services)
tests/                               # 58 test files, 828+ tests
docs/                                # 37-page documentation site
```

---

## Architecture

Each nano-service extends `NanoService` and implements a single `handle(event: Event) -> None` method:

1. **Subscribe** — services declare interest in event types via config
2. **Dispatch** — `__dispatch()` wraps every handler with authz verification, idempotency check, distributed tracing span, metrics recording, and timeout enforcement
3. **Emit** — services call `self.emit(event)` which signs the event with the service's Ed25519 key
4. **Persist** — state flows through the `Store` abstraction (MemoryStore, FileStore, PostgresStore)

Cross-cutting concerns — authz, tracing, metrics, sagas, service supervisor, circuit breaker — are injected by the bus and runtime, not inherited by services.

### Key Design Decisions

| Principle | Implementation |
|-----------|----------------|
| **Event provenance** | Every event carries an Ed25519 signature — verified before dispatch |
| **Concurrent safety** | Per-saga locks; window-slot rate limiter; state lock during CQRS writes |
| **Fault isolation** | Dead-letter queue with replay; circuit breaker per subscriber; per-handler timeout |
| **No single point of failure** | ThreadPoolExecutor dispatch; lazy Postgres pool; graceful shutdown timeout |
| **Security-first** | No `json.dumps(default=str)` in signing; joblib gated by env var; bearer auth |

---

## License

MIT — see [LICENSE](LICENSE) for details.
