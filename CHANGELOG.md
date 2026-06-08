# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive 37-page documentation site under `docs/` — architecture, system design, domain model, API reference, deployment, operations, security, troubleshooting, and more
- `setup.sh` — production-quality, idempotent environment bootstrap script (venv, deps, pre-commit, validation)
- `lint.sh`, `test.sh`, `format.sh` — standalone companion scripts
- `cleanup.sh` — removes all build/test artifacts
- CI security scanning — `bandit` static analysis and `pip-audit` dependency auditing in GitHub Actions
- Docker build + smoke test job in CI pipeline
- Per-saga locking in `SagaOrchestrator` — different sagas execute concurrently instead of blocking on a global lock
- Concurrent handler dispatch — `NanoService` now supports `ThreadPoolExecutor` via `max_concurrent` parameter
- Window-slot distributed rate limiter — replaces TOCTOU `get()`/`set()` with time-window key pattern
- Postgres testcontainer fixtures, HTTP `TestClient` fixture, and failure-mock fixtures (`FailAfterCountStore`, `InjectingBus`) in `conftest.py`
- `UNDERWRITE_ALLOW_JOBLIB` env var to gate `joblib.load()` deserialization
- `RISK_MODEL_SHA256` verification enforced on risk model files
- `bus` property on `NanoService` for downstream idempotency access
- Real bus health check — validates bus isn't stopped, reports subscriber count + DLQ depth
- Notification channel dispatch — SES email + Twilio SMS via `ThreadPoolExecutor`
- `principal` field in `DEFAULT_OCCURRED` payload for recovery workflow

### Changed
- PostgresStore pool replaced hand-rolled list+lock with `psycopg2.pool.ThreadedConnectionPool`
- Sagas use per-saga `RLock` instead of global `RLock`
- Each migration version wraps in its own transaction with commit/rollback
- `MechanismService.__persist_or_rollback` keeps `state_lock` held during store write
- `OtlpSpanExporter` lazily initializes SDK once at construction time
- `document/service.py` uses `uuid.uuid4().hex` instead of `str(uuid.uuid4())[:8]`
- Fee payment check moved entirely inside `state_lock`
- `PostgresStore._get_pool()` lazy-connects on first use
- Risk model loads via JSON by default; joblib requires `UNDERWRITE_ALLOW_JOBLIB=true`
- `pyproject.toml` updated to write `__version__.py` instead of `_version.py`

### Fixed
- Event signature forgery — removed `json.dumps(default=str)` from signing paths; non-JSON payloads are now correctly rejected
- Silent data loss — `StoreRepository.save()` no longer swallows `Exception`
- Dispatch crash — `NanoService.__dispatch` no longer re-raises after logging; DLQ handles redelivery
- Double disbursement — idempotency guard in `disbursement/service.py`
- Concurrent mutation loss — state lock held across store write
- Root container — `addgroup`/`adduser` + `USER underwrite` in Dockerfile
- Port mismatch — `docker-compose.yml` port changed to `8000:8080`
- No restart policy — added `restart: unless-stopped`
- Health no-op — bus health now validates bus state
- UUID collision — full 32-char hex UUID instead of 8-char prefix
- Zero recovery — `MechanismService.__default` includes `principal` and reads from graph
- Phantom payments — idempotency guard in servicing `REPAID` handler
- `ServicingService.handle()` references `self.bus` via property instead of name-mangled private attribute
- Missing `logger` import in `disbursement/service.py`

### Security
- Ed25519 signature verification enforced on all events — `default=str` removed from signing
- Risk model integrity — SHA-256 verification via env var or sidecar; joblib gated behind explicit opt-in
- Bandit SAST scanning in CI pipeline
- `pip-audit` dependency vulnerability scanning in CI

---

## [0.4.0] — 2026-06-07

### Added
- `AsyncLocalBus` — async event bus with per-handler timeouts (30s), dead-letter routing, and CancelledError handling
- `__schema__.py` — schema management for state store migrations
- `__plugins__.py` — plugin discovery and loading framework
- `_version.py` — auto-generated version module via setuptools-scm
- `bandit` configuration for security SAST
- `Dockerfile` — production container image
- `docker-compose.yml` — multi-service orchestration with restart policy
- `CHANGELOG.md` — project changelog
- `conftest.py` — shared test fixtures (Postgres, TestClient, mock stores/buses)
- `test_error_paths.py` — comprehensive error-path and boundary testing
- New service modules: notification (SES/Twilio dispatch), document (generation), governance (rules engine)

### Changed
- Migrated from `bandit` config file (`.bandit`) to `pyproject.toml` integration
- `__config__.py` major refactor — consolidated 600+ line config into `ServiceConfig`-driven model
- `__runtime__.py` — startup/shutdown lifecycle with configurable timeout
- `__cli__.py` — added `serve`, `migrate` commands; streamlined `identity` and `health`
- Store backends — `PostgresStore` lazy initialization on first connection
- Service discovery — dynamic import via `__plugins__` instead of hardcoded registry
- Test suite expanded to cover: concurrency faults, runtime faults, supervisor faults, secrets faults, risk faults, and audit trails
- `REVIEW.md` removed — systematic findings migrated to CHANGELOG and issue tracker

### Fixed
- CI pipeline — removed `PYTEST_DISABLE_PLUGIN_AUTOLOAD` to fix async integration tests
- `__health__.py` — bus health checks now validate bus is not stopped
- `OtlpSpanExporter` — singleton initialization prevents gRPC connection storm on module import
- Service graph — traversal caching and missing edge cases in mechanism state machine

### Security
- `UNDERWRITE_AUTHZ_ENABLED` gating for Ed25519 signature verification
- Authorization policy file support with `UNDERWRITE_AUTHZ_POLICY_FILE`
- Crypto availability warning when `cryptography` library is missing

---

## [0.3.3] — 2026-05-29

### Added
- Service lifecycle — supervisor auto-restart with configurable backoff
- `__supervisor__.py` — monitors registered services and restarts on failure
- `UNDERWRITE_RECOVERY_AUTO_RESTART` environment variable
- `UNDERWRITE_RECOVERY_MAX_RESTARTS` and `UNDERWRITE_RECOVERY_BACKOFF` tuning knobs

### Changed
- `AsyncLocalBus` — improved concurrency with per-handler futures tracking
- `__config__.py` — environment variable binding for recovery settings
- Test isolation — all integration tests use dedicated store/bus instances
- Configuration loading — strict validation of unknown keys

### Fixed
- Dead-letter queue records now correctly persist across bus restarts
- `MemoryStore` eviction correctly distinguishes new key insertions from key updates
- Service dispatch no longer silently drops exceptions from slow handlers

### Security
- Early-warning system for missing `cryptography` dependency at import time

---

## [0.3.2] — 2026-05-29

### Added
- `AsyncLocalBus` — initial async event bus implementation
- `__schema__.py` — schema version tracking and migration coordination
- `conftest.py` — shared test fixtures for store, bus, and runtime integration
- `Dockerfile` — multi-stage production build
- `docker-compose.yml` — container orchestration with filesystem backend
- `bandit` security linter configuration
- Kubernetes liveness/readiness probes (`/healthz`, `/readyz`)

### Changed
- `Runtime` — event-driven startup/shutdown with configurable graceful timeout
- `__cli__.py` — `underwrite serve` command with `--host`, `--port`, `--services`, `--rate-limit`, `--require-auth` flags
- `__config__.py` — extracted environment variable prefix handling into `__env__` helper
- Store backends — `PostgresStore` uses `psycopg2.pool.ThreadedConnectionPool`
- CI pipeline — split into separate `lint` and `docker` jobs

### Fixed
- Port mismatch in docker-compose (`8000` host → `8080` container)
- Container runs as `root` — added `addgroup`/`adduser` + `USER underwrite` in Dockerfile
- Missing `restart: unless-stopped` policy in docker-compose

---

## [0.3.1] — 2026-05-27

### Added
- `uv.lock` — deterministic dependency lockfile
- Notification service — base channel dispatch infrastructure
- Document service — template rendering and PDF generation stubs

### Changed
- Risk model loading — lazy sklearn imports; model loaded on first `handle()` call
- `__runtime__.py` — added `readonly` mode for health/metrics without service startup
- `__store__.py` — improved error messages on connection failures
- `__bus__.py` — rate limiter uses configurable window size

### Fixed
- `ServicingService.handle()` now correctly accesses `self.bus` via public property
- Missing `logger` import in `disbursement/service.py`
- Collateral service — `loan_id` now propagated through all collateral events

---

## [0.3.0] — 2026-05-26

### Added
- Circuit breaker infrastructure — per-subscriber failure tracking with configurable thresholds
- Per-handler timeout (30s) — slow event handlers are routed to dead-letter queue
- Event payload size validation — payloads exceeding 1 MB raise `ProtocolError`
- `CircuitBreakerMiddleware` for automatic subscriber suspension
- `UNDERWRITE_BUS_MAX_FUTURES` — configurable maximum pending futures

### Changed
- `import random` moved from method body to module level in `__circuit__.py`
- British English → American English in all docstrings (`Initialises` → `Initializes`)
- `logger.debug(exc_info=True)` → `logger.warning` in `__bus__.py.__trim_futures()` for visible error surfacing
- Metrics export — configurable interval via `UNDERWRITE_METRICS_EXPORT_INTERVAL`

### Fixed
- MemoryStore eviction correctly distinguishes new keys from updates
- Async bus dispatch loop handles `CancelledError` for clean shutdown

---

## [0.2.0] — 2026-05-25

### Added
- `.env.example` — documented all `UNDERWRITE_*` environment variables
- `.pre-commit-config.yaml` — pre-commit hooks for linting and formatting
- `tox.ini` — multi-environment test matrix
- `test_bus_extras.py` — bus edge-case tests (rate limiting, DLQ replay, subscription validation)
- `test_fee.py`, `test_fraud.py`, `test_mechanism.py` — service-specific test suites
- `test_saga.py` — saga orchestration tests (commit, rollback, concurrent isolation)
- `test_store.py` — store backend tests (memory, file, postgres CRUD + pagination)
- `TODO.md` — project roadmap and outstanding tasks

### Changed
- `__bus__.py` — DLQ replay support; improved rate limiter with configurable window
- `__config__.py` — `Configuration.default()` returns sensible production defaults
- `__cli__.py` — `underwrite init` creates config with mechanism + audit enabled
- PII redaction — field name matching uses case-insensitive regex
- `__authz__.py` — Ed25519 key derivation uses SHA-256 hash of service name

### Fixed
- `__identity__.py` — key TTL enforcement with grace period
- Store DSN parsing for Postgres connection strings with special characters

### Security
- PII redactor — masks passwords, tokens, SSNs, credit card numbers, and API keys in JSON logs
- `UNDERWRITE_AUTHZ_ENABLED` defaults to `true` in production config

---

## [0.1.1] — 2026-05-22

### Added
- `CONTRIBUTING.md` — contribution guidelines and workflow
- `SECURITY.md` — security policy and disclosure process
- `conftest.py` — initial shared test infrastructure
- Test suites: `test_audit.py`, `test_configuration.py`, `test_concurrency_faults.py`, `test_risk_faults.py`, `test_runtime_faults.py`, `test_secrets_faults.py`, `test_supervisor_faults.py`, `test_validate_faults.py`

### Changed
- `__authz__.py` — service identity binding with key rotation support
- `__bus__.py` — subscriber registration validates handler signatures
- `__cli__.py` — `list`, `health`, `dlq`, `metrics` commands with structured output
- `__config__.py` — environment variable overrides for all major subsystems
- `__events__.py` — event type registry with `EventType` enum
- `__serve__.py` — FastAPI application factory with health/metrics endpoints
- `__store__.py` — filesystem store with atomic writes

### Fixed
- `pyproject.toml` — setuptools package discovery for CI builds (non-recursive `find`)
- mypy type errors across the codebase

---

## [0.1.0] — 2026-05-22

### Added
- Initial nano-service platform implementation
- **Core infrastructure**: `__bus__.py` (event bus), `__store__.py` (state store), `__saga__.py` (saga orchestrator), `__authz__.py` (access control), `__circuit__.py` (circuit breaker), `__config__.py` (configuration), `__runtime__.py` (lifecycle manager), `__cli__.py` (CLI), `__serve__.py` (HTTP server)
- **Event system**: `__events__.py` (typed events), `__identity__.py` (Ed25519 keys), Ed25519 cryptographic signatures on all events
- **28 nano-services**: mechanism (delegation state machine), risk (ML scoring with scikit-learn), fraud detection, KYC/AML, collateral management, fee assessment, loan origination/servicing, collections, recovery, notifications, document generation, governance, pricing, provisioning, disbursement, fulfillment, agreement management, and more
- **Pluggable store backends**: `MemoryStore`, `FileStore`, `PostgresStore`
- **Observability**: `__metrics__.py` (Prometheus), `__tracer__.py` (OpenTelemetry), `__logger__.py` (structured JSON with PII redaction)
- **Resilience**: dead-letter queue, retry policies, circuit breakers, idempotency guards, grace-period penalties, concentration limits
- **HTTP API**: FastAPI server with `/v1/health`, `/v1/metrics`, `/v1/publish` endpoints, bearer auth, rate limiting, request ID propagation
- **CLI**: `underwrite {init,run,list,identity,health,dlq,metrics}` commands
- **Database**: Alembic migration infrastructure, connection pool tuning, read replica support, soft-delete, cursor-based pagination, batch inserts
- **Docker**: Multi-stage production Dockerfile, docker-compose orchestration
- **CI/CD**: GitHub Actions pipeline (lint, type-check, test across Python 3.10–3.13)
- **Testing**: 828+ tests across 58 test files including property-based tests (Hypothesis), load tests (Locust), mutation tests (mutmut), chaos tests, contract tests
- **Security**: JWT auth, API key management, Ed25519 event signing, PII redaction, CSP headers, secret manager (env/vault)
- **Financial features**: e-NACH integration, payment gateway stubs, EMI auto-debit, partial prepayment, loan restructuring, liquidation workflow, collateral revaluation, bankruptcy tracking, RBI complaint management, GST verification
- **Kubernetes**: Production manifests with blue/green deployment support
- **Blockchain**: Algorand client with connection pooling, TEAL contract integration, multi-sig wallet, cross-chain bridge

---

[Unreleased]: https://github.com/sachn-cs/unsecured-lending-underwriting/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/sachn-cs/unsecured-lending-underwriting/releases/tag/v0.4.0
[0.3.3]: https://github.com/sachn-cs/unsecured-lending-underwriting/releases/tag/v0.3.3
[0.3.2]: https://github.com/sachn-cs/unsecured-lending-underwriting/releases/tag/v0.3.2
[0.3.1]: https://github.com/sachn-cs/unsecured-lending-underwriting/releases/tag/v0.3.1
[0.3.0]: https://github.com/sachn-cs/unsecured-lending-underwriting/releases/tag/v0.3.0
[0.2.0]: https://github.com/sachn-cs/unsecured-lending-underwriting/releases/tag/v0.2.0
[0.1.1]: https://github.com/sachn-cs/unsecured-lending-underwriting/releases/tag/v0.1.1
[0.1.0]: https://github.com/sachn-cs/unsecured-lending-underwriting/releases/tag/v0.1.0
