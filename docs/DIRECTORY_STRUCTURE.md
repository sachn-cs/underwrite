# Directory Structure

```
underwrite/                          # Main package (29 source modules + 28 service dirs)
├── __init__.py                     # Public API exports (Runtime, NanoService, LocalBus, Store, etc.)
├── __bus__.py                      # Event bus: LocalBus, AsyncLocalBus, DeadLetterQueue,
│                                   #   IdempotencyGuard, RateLimiter, CircuitBreaker (per-subscriber)
├── __store__.py                    # State store ABC + implementations: MemoryStore, FileStore,
│                                   #   PostgresStore, CQRSStore wrapper
├── __saga__.py                     # Saga orchestration: Saga, SagaStep, SagaOrchestrator
│                                   #   with store-backed persistence and idempotent step execution
├── __authz__.py                    # Access control: Policy, AccessControl with allow/deny rules
│                                   #   and Ed25519 signature verification per event
├── __circuit__.py                  # Circuit breaker (CLOSED/OPEN/HALF_OPEN) + RetryPolicy
│                                   #   with exponential backoff and jitter
├── __config__.py                   # Pydantic-based configuration engine: Configuration model,
│                                   #   nested configs for bus/store/logging/identity/authz/metrics/
│                                   #   tracing/saga/secrets/recovery/fee/governance/audit.
│                                   #   Loads JSON config, env overrides, defines SERVICE_NAMES (28)
├── __runtime__.py                  # Service lifecycle manager: Runtime class wires, starts,
│                                   #   stops, and restarts all nano services; builds bus, store,
│                                   #   tracer, authz, saga orchestrator, supervisor, metrics export
├── __serve__.py                    # FastAPI HTTP server: /v1/health, /v1/metrics, /v1/publish,
│                                   #   /healthz, /readyz with bearer auth, rate limiting, OTel instr.
├── __cli__.py                      # Typer CLI: underwrite init/run/list/identity/health/dlq/
│                                   #   metrics/serve/migrate
├── __identity__.py                 # Ed25519 key management: Identity (create/sign/verify/attest),
│                                   #   KeyRotationManager with TTL and grace period
├── __tracer__.py                   # Distributed tracing: Tracer, Span, SpanContext,
│                                   #   ConsoleSpanExporter, OtlpSpanExporter
├── __metrics__.py                  # In-memory metrics: MetricsCollector with counters, timers,
│                                   #   gauges, TimerContext; bounded eviction
├── __health__.py                   # Health-check registry: HealthRegistry with per-subsystem
│                                   #   callables aggregated into single status report
├── __events__.py                   # Event type definitions: Event dataclass (frozen, signed),
│                                   #   EventType enum with 80+ domain event types
├── __exceptions__.py               # All custom exceptions: UnderwriteError base, 14 subtypes
│                                   #   (ConfigurationError, ProtocolError, AuthzError, etc.)
├── __secrets__.py                  # Secrets management: SecretsBackend ABC with EnvSecretsBackend,
│                                   #   VaultSecretsBackend, AwsSecretsBackend
├── __async_bus__.py                # Async event bus: AsyncLocalBus using asyncio.Queue
│                                   #   with concurrent dispatch via asyncio.gather
├── __supervisor__.py               # Service auto-restart: ServiceSupervisor tracks consecutive
│                                   #   failures, exponential backoff, max-restart threshold
├── __schema__.py                   # JSON Schema generation: SchemaRegistry, EventSchema for
│                                   #   per-event-type payload validation with versioning
├── __pii.py                        # PII detection/redaction: PIISanitizer, field/value patterns
│                                   #   for Aadhaar, PAN, SSN, phone, email, bank account, etc.
├── __plugins__.py                  # Plugin system: discover_plugins() via importlib.metadata
│                                   #   entry_points under "underwrite.services"
├── __service_registry__.py         # Service registry: SERVICE_MAP (name -> module path),
│                                   #   SERVICE_CLASSES (name -> class name),
│                                   #   WIRING (event_type -> subscriber list)
├── __migrate__.py                  # Schema migration engine: Migration, MigrationPlan,
│                                   #   default_plan() for store schema versioning
├── __logger__.py                   # Centralized logging: single "underwrite" logger instance
├── __main__.py                     # python -m underwrite entry point (delegates to CLI)
├── __version__.py                  # Auto-generated version via setuptools-scm
├── validate.py                     # Payload validation helpers: PayloadValidator, get_positive,
│                                   #   get_in_range, get_finite, get_match, etc. (382 lines)
├── prometheus_export.py            # Prometheus text-format export: MetricsExporter,
│                                   #   PrometheusMiddleware for FastAPI, metrics_as_text()
├── py.typed                        # PEP 561 marker for typed package
└── services/                       # 28 nano-service implementations
    ├── __init__.py                 # Exports NanoService, StatefulService
    ├── base.py                     # NanoService (ABC), StatefulService, BatchPersistenceMixin
    │                               #   — event emission/signing, subscription, dispatch
    │                               #   — ThreadPoolExecutor for concurrent handlers
    │                               #   — idempotency, authz gating, tracing, metrics, supervisor
    ├── persistence.py              # StoreRepository[T], TypedStoreRepository[T],
    │                               #   BatchedStoreRepository[T] (generic, type-safe, batched)
    ├── mechanism/                  # Core state machine: DelegationGraph, seed/user management,
    │   ├── __init__.py             #   quote/originate/repay/default/revoke commands
    │   ├── graph.py                #   Emits core domain events (seed.added, user.added, etc.)
    │   └── service.py
    ├── audit/                      # Event audit log: records all events to ledger.json
    │   ├── __init__.py             #   with PII redaction, bounded ledger size
    │   └── service.py
    ├── risk/                       # ML risk scoring: RiskModel with Strategy pattern
    │   ├── __init__.py             #   (HeuristicStrategy, JsonModelStrategy, JoblibModelStrategy)
    │   ├── model.py                #   SHA-256 model integrity verification, strategy registry
    │   └── service.py
    ├── fraud/                      # Fraud detection: wash trading, velocity checks, alerts
    │   ├── __init__.py
    │   └── service.py
    ├── compliance/                 # KYC/AML verification: processes kyc.verified, aml.cleared,
    │   ├── __init__.py             #   aml.frozen, kyc.rejected
    │   └── service.py
    ├── decision/                   # Signal aggregation & decision rules: evaluates risk/fraud/
    │   ├── __init__.py             #   compliance signals, emits decision.made
    │   └── service.py
    ├── quote/                      # Loan quote generation: computes terms from pricing
    │   ├── __init__.py
    │   └── service.py
    ├── pricing/                    # Pricing computation: interest rate models
    │   ├── __init__.py
    │   └── service.py
    ├── underwriter/                # Manual underwriting approval/rejection workflow
    │   ├── __init__.py
    │   └── service.py
    ├── origination/                # Loan origination: create/submit loan applications
    │   ├── __init__.py
    │   └── service.py
    ├── collateral/                 # Collateral marking, valuation, liquidation
    │   ├── __init__.py
    │   └── service.py
    ├── disbursement/               # Fund disbursement processing
    │   ├── __init__.py
    │   └── service.py
    ├── servicing/                  # Loan servicing lifecycle
    │   ├── __init__.py
    │   └── service.py
    ├── payment/                    # Payment processing: receive, schedule, overdue detection
    │   ├── __init__.py
    │   └── service.py
    ├── collection/                 # Collections: NPA bucket tracking, collection updates
    │   ├── __init__.py
    │   └── service.py
    ├── npa/                        # Non-performing asset classification: bucket changes,
    │   ├── __init__.py             #   DLG (Delegated Loss Given) triggers
    │   └── service.py
    ├── recovery/                   # Asset recovery workflow
    │   ├── __init__.py
    │   └── service.py
    ├── settlement/                 # Settlement completion
    │   ├── __init__.py
    │   └── service.py
    ├── fee/                        # Fee assessment: late payment, origination, prepayment,
    │   ├── __init__.py             #   service fees with configurable schedules
    │   └── service.py
    ├── statement/                  # Statement generation
    │   ├── __init__.py
    │   └── service.py
    ├── notification/               # Outbound notification dispatch
    │   ├── __init__.py
    │   └── service.py
    ├── communication/              # Communication sending (email/SMS)
    │   ├── __init__.py
    │   └── service.py
    ├── document/                   # Document generation
    │   ├── __init__.py
    │   └── service.py
    ├── governance/                 # Protocol governance: parameter proposals, voting, execution
    │   ├── __init__.py
    │   └── service.py
    ├── graph/                      # Delegation graph queries: path finding, credit limit,
    │   ├── __init__.py             #   user listing (read-only query service)
    │   └── service.py
    ├── identity/                   # On-chain/off-chain identity registration and rotation
    │   ├── __init__.py
    │   └── service.py
    ├── reporting/                  # Report generation
    │   ├── __init__.py
    │   └── service.py
    ├── workflow/                   # Workflow orchestration: start, advance, complete
    │   ├── __init__.py
    │   └── service.py
    └── (16 more service dirs)      # Each follows: __init__.py + service.py

tests/                              # 59 test files (828+ tests)
├── conftest.py                    # Shared fixtures, mock bus/store/identity
├── test_mechanism.py              # Largest test file (767 lines)
├── test_framework.py              # Core framework tests (NanoService, LocalBus, Store)
├── test_runtime_e2e.py            # End-to-end integration tests
├── test_saga.py                   # Saga orchestration tests
├── test_error_paths.py            # Fault injection tests
├── test_risk.py / test_risk_model.py / test_risk_faults.py
├── test_store.py
├── test_authz.py / test_bus_extras.py
├── test_identity.py / test_identity_extras.py
├── test_pii.py / test_pii_extras.py
├── test_secrets_faults.py / test_supervisor_faults.py
├── test_validate_faults.py
├── test_concurrency.py / test_concurrency_faults.py
├── (one test file per service: test_audit, test_fraud, test_collateral, etc.)
└── test_new_features.py / test_new_services.py

docs/                               # Documentation (MkDocs)
├── index.md
├── architecture.md
├── api-reference.md
├── getting-started.md
├── README.md
├── DIRECTORY_STRUCTURE.md          # This file
└── DESIGN_DECISIONS.md            # Architectural trade-offs

data/                               # Runtime data
├── audit/
│   └── ledger.json                # Event audit ledger
├── bus/
│   └── dlq.json                   # Dead-letter queue persistence
└── protocol/
    └── state.json                 # Mechanism protocol state

pyproject.toml                      # PEP 621 project metadata, dependencies, tool configs
Dockerfile                          # Container build
docker-compose.yml                  # Multi-service deployment
Makefile                            # Common task runner
tox.ini                             # Multi-python-version test matrix
mkdocs.yml                          # Documentation site config
uv.lock                             # Dependency lockfile
```

## Top-Level Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | PEP 621 build config. Single-source of truth for dependencies, scripts, and tool config (ruff, mypy, pytest, bandit, mutmut). Uses `setuptools-scm` for versioning. No `requirements.txt`. |
| `Dockerfile` | Container build for the underwrite runtime |
| `docker-compose.yml` | Orchestrates underwrite + Postgres + optional Vault/Prometheus |
| `Makefile` | Targets: `install`, `test`, `lint`, `typecheck`, `security`, `clean`, `build`, `serve` |
| `tox.ini` | Test matrix across Python 3.10–3.13 |
| `mkdocs.yml` | MkDocs config for documentation site generation |
| `uv.lock` | Lockfile for `uv` package manager |
| `README.md` | Project overview and quickstart |
| `CHANGELOG.md` | Release changelog |
| `CONTRIBUTING.md` | Contribution guidelines |
| `SECURITY.md` | Security policy |
| `TODO.md` | Known issues and planned work |
| `LICENSE` | MIT license |
| `.env.example` | Environment variable template |
| `.pre-commit-config.yaml` | Pre-commit hook config (ruff, mypy, bandit) |

## `data/` Directory

| Path | Purpose |
|------|---------|
| `data/audit/ledger.json` | Append-only event ledger written by the AuditService |
| `data/bus/dlq.json` | Dead-letter queue persistence via FileStore |
| `data/protocol/state.json` | Mechanism delegation graph state persisted by FileStore |
