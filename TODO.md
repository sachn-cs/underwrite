# TODO — Feature Discovery & Implementation Backlog

Based on comprehensive codebase analysis (June 2026). Covers unimplemented backends, stubs, missing tests, and planned features.

---

## Legend

| Emoji | Meaning |
|-------|---------|
| 🔴 | High impact / must-have for v1.0.0 |
| 🟡 | Medium impact |
| 🟢 | Lower impact / polish |

---

## 🟢 Critical Bugs (from ROADMAP)

- [ ] **CD2** Exclude `token` from `Configuration.to_dict()` — `underwrite/__config__.py:465-470`
- [ ] **CD4/HD6** Fix path traversal in `FileStore.__path` — `underwrite/__store__.py:244-253`
- [ ] **HD3** Bound `FraudService.__records` with `deque(maxlen=100000)` — `underwrite/services/fraud/service.py:25`
- [ ] **CD5** Add `FileStore` thread cleanup in `ServiceSupervisor.shutdown()` — `underwrite/__store__.py:157`
- [ ] **HD8** Add `PrometheusMiddleware` import-failure warning — `underwrite/__serve__.py:24-29`
- [ ] **MD5** Fix env var type coercion in `Configuration.__apply_env_overrides` — `underwrite/__config__.py:609-613`

---

## 🔴 High Impact — New Features

### Bus Backends (v1.0.0 must-have)

- [ ] **SQS Event Bus Backend** — `SQSBackend(EventBus)` for distributed deployment via Amazon SQS
  - References: `__config__.py:69`, `docs/ROADMAP.md:69`, `docs/DESIGN_DECISIONS.md:117`
  - Config value `sqs` accepted but only `LocalBus` exists
- [ ] **Modal Event Bus Backend** — `ModalBackend(EventBus)` for Modal.com serverless queues
  - References: `__config__.py:69`, `docs/ROADMAP.md:69`
  - Same pattern — accepted in config, zero code exists

### Infrastructure (v1.0.0 must-have)

- [ ] **Saga Persistence** — Store-backed saga log (currently in-memory only, all sagas lost on restart)
  - References: `__saga__.py`, `docs/ADR/004-saga-orchestration.md:80`, `docs/ROADMAP.md:23`
- [ ] **DLQ Persistence + Replay Automation** — Persist dead-letter queue items, CLI for replay
  - References: `__bus__.py`, `docs/ROADMAP.md:41`
- [ ] **Distributed Rate Limiting** — `DistributedRateLimiter` with Redis/Store backend (currently per-process)
  - References: `docs/ROADMAP.md:40`

### Services

- [ ] **Real Recovery Service** — Currently a stub: immediately completes at flat 30% recovery rate with no workflow
  - References: `underwrite/services/recovery/service.py` (entire 53-line file)
  - Needs: negotiation workflows, payment plans, escalation, actual recovery rate computation

### Observability (v1.0.0 must-have)

- [ ] **Prometheus `/metrics` at Standard Path** — Currently at `/v1/metrics`, not the standard Prometheus path
  - References: `docs/ROADMAP.md:22`
- [ ] **Structured Logging with Correlation IDs** — Proper middleware-based correlation ID propagation
  - References: `__runtime__.py:186` (currently `type: ignore[attr-defined]`), `docs/ROADMAP.md:65`
- [ ] **FastAPI OTLP Auto-Instrumentation** — `opentelemetry-instrumentation-fastapi` integration
  - References: `docs/ROADMAP.md:39`

---

## 🟡 Medium Impact — Features & Improvements

### New Functionality

- [ ] **Config-Driven Fee Schedules** — Replace `FEE_SCHEDULES` hardcoded dict with configurable rules
  - References: `docs/ROADMAP.md:28`
- [ ] **Plugin-Based Risk Model Loading** — Dynamic loading of `RiskScoringStrategy` implementations from external packages
  - References: `docs/ROADMAP.md:37`, `docs/DESIGN_DECISIONS.md:200`
- [ ] **Event Payload Schema Versioning** — No mechanism for coexisting v1/v2 of the same event type
  - References: `docs/ADR/002-event-driven-communication.md:49`, `__schema__.py`
- [ ] **Async Event Bus** — `AsyncLocalBus` exists but not integrated as a first-class backend option
  - References: `__async_bus__.py`, `docs/ROADMAP.md:27`
- [ ] **`EnvSecretsBackend.set()` Implementation** — Currently a no-op `pass  # read-only`
  - References: `underwrite/__secrets__.py:34-35`

### Missing Tests (High Risk)

- [ ] **`__plugins__.py` Test Coverage** — 52-line module doing dynamic import loading via `importlib.metadata.entry_points` — zero tests
  - File: `underwrite/__plugins__.py`
- [ ] **`__service_registry__.py` Test Coverage** — 140-line module with all 28 service mappings and event wiring — zero tests. Wiring errors = silent event drops at runtime
  - File: `underwrite/__service_registry__.py`
- [ ] **`DelegationGraph` Direct Unit Tests** — 273-line graph engine (`graph.py`) tested only indirectly through `MechanismService`
  - File: `underwrite/services/mechanism/graph.py`
- [ ] **`TestMechanismConcurrency` Placeholder** — Entire class body is `pass`, skipped with `@pytest.mark.skip`
  - File: `tests/test_concurrency_faults.py:308-310`

### Code Quality

- [ ] **`BatchPersistenceMixin` Concrete Implementation** — Abstract `do_sync_store()` method with no service using the mixin
  - References: `underwrite/services/base.py:88-90`
- [ ] **`StoreRepository.serialize/deserialize` Real Implementations** — Currently passthrough methods meant to be overridden
  - References: `underwrite/services/persistence.py:83-89`
- [ ] **`postgres_dsn` Session-Scoped Skip Bug** — Missing `testcontainers` skips the entire test session (should be `pytest.importorskip`)
  - File: `tests/conftest.py:44-55`

---

## 🟢 Lower Impact — Polish & Tooling

### CI / Infrastructure

- [ ] **PyPI Publishing CI** — GitHub Actions release workflow for PyPI
  - References: `docs/ROADMAP.md:43`
- [ ] **Mutation Testing Integration** — `mutmut` declared + configured in `pyproject.toml` but never invoked in CI or Makefile
  - References: `pyproject.toml:65-67`, `[tool.mutmut]` section
- [ ] **`FileStore.keys()` Pagination** — No pagination for listing keys in large datasets
  - References: `docs/ROADMAP.md:32`
- [ ] **`docker-compose.yml` with Postgres + Vault + OTLP** — Currently single-service only
  - References: `docs/ROADMAP.md:71`

### Dependencies

- [ ] **`twilio` Missing from `pyproject.toml`** — Imported and used in notification service but not declared as a dependency
  - File: `underwrite/services/notification/service.py:117`

### Redundancy / Cleanup

- [ ] **`tests/test_new_services.py` Duplicates Coverage** — Smoke tests duplicate coverage already present in 6 dedicated service test files
- [ ] **`tests/test_new_features.py` Missing Assertions** — Several tests rely on "no exception raised" rather than asserting outcomes

---

## Summary

| Priority | Items | Category |
|----------|-------|----------|
| 🔴 High | 12 | Bus backends (SQS/Modal), saga persistence, DLQ replay, distributed rate limiting, real recovery service, Prometheus path, correlation IDs, OTLP auto-instr + 4 critical bugs |
| 🟡 Medium | 12 | Fee schedules, plugin models, schema versioning, async bus, secrets set() + 5 missing test areas + 3 code quality |
| 🟢 Low | 7 | PyPI CI, mutation testing, pagination, compose, twilio dep + 2 cleanup |
| **Total** | **31** | |
