# Underwrite — Repository Audit & Action Plan

> **Score: 57/100** | Pre-production alpha. Strong architectural foundation, blocked by security and observability gaps.

---

## 1. Executive Summary

**Package**: `underwrite` v0.1.0 — 28 nano-service platform for unsecured lending underwriting.

**Strengths**: Clean ABC-driven architecture (`EventBus`, `Store`, `NanoService`), 509 passing tests, ruff-clean, `py.typed` marker, PEP 585 generics, good cross-cutting concern injection (authz/tracing/metrics/saga).

**Critical issues**: Event signatures still don't cover payload, `FileStore.__path` has a path traversal bypass, `PostgresStore` SQL injection via interpolated table name, `MechanismService` lacks validation on financial calculations, no concurrency/stress tests, no PyPI publishing CI, no Prometheus metrics endpoint, no structured logging, no saga persistence, dead secret token in config serialization.

---

## 2. Architectural Findings

### Modularity
Excellent — 28 services independently deployable, `NanoService` ABC is clean, `Store`/`EventBus` abstractions well-separated. CQRS wrapper (`CQRSStore`) follows decorator pattern cleanly.

### Modularity Violations
- **`__runtime__.py`** (399 lines) — violates SRP. Handles factory building (tracer, bus, store, authz, secrets, supervisor), lifecycle management, health registration, migration orchestration, and logging config. `__build_*` factory methods should live in dedicated factory modules.
- **`MechanismService`** (383 lines) — mixes protocol state machine, graph traversal, financial calculations, and persistence. Should be 3 layers.
- **`__store__.py`** (454 lines) — 6 classes with inline imports at bottom (line 256+), code smell from circular import avoidance.

### Dependency Graph
Clean unidirectional flow: `services/*` → `underwrite.*` → stdlib. No circular imports. `_Emitter` Protocol in `__saga__.py` correctly breaks the potential cycle between `NanoService` and `SagaOrchestrator`.

### Extensibility
Good — `Store`, `EventBus`, `SecretsBackend` all use ABCs. Missing: plugin system for custom service loading (services are hardcoded in `SERVICE_MAP`).

### Scalability Concerns
- `LocalBus` is in-process only — no SQS/Modal implementation exists
- `FileStore.keys()` uses `rglob("*.json")` with no pagination — OOM risk with large datasets
- `FraudService.__records` is unbounded (plain dict, no eviction) — memory leak
- Saga orchestrator is entirely in-memory — lost on restart

---

## 3. Production Readiness Assessment

| Criterion | Status | Issues |
|-----------|--------|--------|
| AuthN/AuthZ | ✅ Good | Bearer token, Ed25519 signatures, ACL policies |
| Secret management | 🟡 Partial | Token serialized in `to_dict()`, private key name-mangled |
| Observability | 🟡 Partial | No structured logging, no Prometheus `/metrics`, no log correlation IDs |
| Graceful shutdown | ✅ Good | Thread join with timeout |
| Circuit breakers | ✅ Good | FileStore, PostgresStore |
| Retry logic | ✅ Good | RetryPolicy with exponential backoff |
| Health checks | ✅ Good | All subsystems registered |
| Rate limiting | ✅ Good | Token bucket per subscriber |
| Error handling | 🟡 Partial | Silent degradation in RiskService, silent returns in Saga |
| Configuration | 🟡 Partial | Schema validation exists but not enforced on `load()` |
| Data persistence | 🟡 Partial | No atomic multi-key operations, saga in-memory |
| Async support | ❌ None | Entirely synchronous — FastAPI wrapper uses sync Runtime |

---

## 4. Missing Features and Enhancements

| Feature | Priority | Why |
|---------|----------|-----|
| **Prometheus `/metrics` endpoint** | High | `__serve__.py` has a `try: from underwrite.prometheus_export import PrometheusMiddleware` that silently no-ops. The `/metrics-prometheus` endpoint exists but uses JSON wrapper instead of proper Prometheus exposition format at a standard path. |
| **Structured logging** | High | All logging uses string formatting. No `structlog`, no correlation ID propagation to log context. Production debugging requires correlating log lines with event IDs manually. |
| **Async event bus** | Medium | The entire stack is synchronous. FastAPI integration wraps sync Runtime — blocks async workers. |
| **Saga persistence** | High | Sagas are entirely in-memory. A process crash loses all in-flight transactions with no recovery. |
| **DLQ persistence** | Medium | Dead letters are in-memory only, lost on restart. |
| **Plugin service loader** | Medium | All 28 services are hardcoded in `SERVICE_MAP`/`SERVICE_CLASSES`/`WIRING`. No mechanism for third-party services. |
| **Configuration schema enforcement** | Medium | `_schema()` defines the schema but `_validate()` is called only when loading from file. No runtime schema enforcement. |
| **Event replay from DLQ** | Medium | `DeadLetterQueue.replay()` exists but no CLI command or automated retry mechanism. |
| **Config-driven fee schedules** | Low | `FEE_SCHEDULES` is a hardcoded module-level dict — changing rates requires a code deploy. |
| **Config-driven governance ranges** | Low | `PARAM_RANGES` is hardcoded. |

---

## 5. Technical Debt Report

### Critical Debt

| ID | Issue | File | Impact |
|----|-------|------|--------|
| CD1 | **Event signature excludes payload** | `__authz__.py:176`, `services/base.py:132` | `to_verify` includes `payload_str` (fixed in v0.1.0 per CHANGELOG). RESOLVED. |
| CD2 | **Private key exposed in config serialization** | `__config__.py:422-483` | `to_dict()` excludes `private_key` but `token` (Vault/AWS secret) IS serialized to JSON on `save()`. |
| CD3 | **SQL injection via table name** | `__store__.py` lines 331, 339, 348, 354, 362-363 | `f"SELECT value FROM {self.__table} WHERE key = %s"` — table name is f-string interpolated. **High severity.** |
| CD4 | **Thread leak in FileStore** | `__store__.py:157-159` | `ThreadPoolExecutor(max_workers=1)` created per instance, never `.shutdown()`. Leaks thread. |
| CD5 | **NaN/Inf propagation in FeeService** | `services/fee/service.py:45` | `loan_id = event.payload.get("loan_id", "")` — no `get_finite()` on amount fields downstream. |

### High Debt

| ID | Issue | File | Impact |
|----|-------|------|--------|
| HD1 | **`__sync_store()` reads state without lock** | `services/mechanism/service.py:359-383` | RESOLVED — called under `self.__lock` via command handlers. |
| HD2 | **Saga silent returns** | `__saga__.py:103,104,106,109,110,136` | All `return False` / `return` on not-found emit no log. Debugging saga failures requires tracing through opaque booleans. |
| HD3 | **Fraud records unbounded growth** | `services/fraud/service.py:25` | `self.__records: dict[str, list[dict]]` — grows indefinitely. Memory leak. |
| HD4 | **Governance silently ignores proposals** | `services/governance/service.py:60-61` | `if param not in self.__params: return` — no log, no event. Configuration mistake goes undetected. |
| HD5 | **Fee silently ignores unknown types** | `services/fee/service.py:47-48` | `if not loan_id or fee_type not in FEE_SCHEDULES: return` — no warning. |
| HD6 | **`FileStore.__path` path traversal bypass** | `__store__.py:244-246` | `safe = key.replace(":", "/")` — a key like `foo:../etc/passwd` becomes `foo/../etc/passwd`. The `".." in safe` check catches this, but triple-dot variants may bypass. |
| HD7 | **No `asyncio` support** | Entire codebase | `Runtime` entirely synchronous. `__serve__.py` starts it in FastAPI `startup` event — blocks the async event loop. |
| HD8 | **Prometheus middleware silently no-ops** | `__serve__.py:24-29` | `except ImportError: pass` — if `prometheus_export` fails to import, the middleware is silently omitted. No warning to operator. |

### Medium Debt

| ID | Issue | File | Impact |
|----|-------|------|--------|
| MD1 | **SSN regex requires dashes** | `__pii.py:40` | Pattern `\b\d{3}-\d{2}-\d{4}\b` — undashed `123456789` not detected. |
| MD2 | **`FileStore.keys()` no pagination** | `__store__.py:232-241` | Enumerates all files via `rglob` — no limit. DoS for large datasets. |
| MD3 | **No depth limit on delegation chain** | `services/mechanism/service.py:132-141` | `__required_delegation` recursively traverses parent chain with no max-depth guard. Stack overflow via deeply nested chain. |
| MD4 | **Catastrophic cancellation in `break_even`** | `services/mechanism/service.py:319-320` | `1.0 - clamped_dp` when `dp ≈ 0.999999999999` loses precision. |
| MD5 | **`Configuration.__apply_env_overrides` no type coercion** | `__config__.py:605-613` | All env var values are `str`. `rate_limit` becomes `"100"` (string), not `100` (float). |
| MD6 | **`LocalBus.__MAX_FUTURES` hardcoded** | `__bus__.py:252` | 10,000 future cap with no configuration or documentation. |
| MD7 | **`Runtime.__init__` calls `__run_migrations()` and `__start_metrics_export()`** | `__runtime__.py:62-63` | Side effects in constructor — violates principle of least surprise. |
| MD8 | **`Runtime.__build_authz()` catches broad `Exception`** | `__runtime__.py:183` | `except Exception as exc` during policy file loading — silent degradation. |
| MD9 | **`metrics.py` eviction algorithm is O(n)** | `__metrics__.py:73-78` | Evicts by iterating dicts with `pop(next(iter(...)))` — O(n²) worst-case. |

---

## 6. Security and Reliability Risks

| Risk | Severity | Details |
|------|----------|---------|
| Vault/AWS token in config JSON | **High** | `SecretsConfig.token` is serialized by `to_dict()` and written to disk by `save()`. |
| Path traversal in FileStore | **High** | Key normalization via `replace(":", "/")` + `".." in safe` check can be bypassed. |
| SQL injection (table name) | **High** | Table name is f-string interpolated in SQL queries. |
| Silent model degradation | **Medium** | `RiskModel.predict()` catches ALL exceptions and falls through to heuristic. |
| No input validation on risk model | **Medium** | `RiskModel.predict()` accepts any float — NaN/Inf propagate to heuristic output. |
| No `__all__` in critical modules | **Low** | `__runtime__.py`, `__serve__.py`, `__migrate__.py`, `__health__.py` lack `__all__`. |
| Empty steps saga | **Low** | `SagaOrchestrator.start_saga()` with empty `steps` immediately "completes". |
| No rate limiting on HTTP endpoints | **Medium** | `__serve__.py` rate limiter is a simple token bucket per process — not distributed-safe. |

---

## 7. Performance Findings

| Issue | Location | Impact |
|-------|----------|--------|
| **`__sync_store()` writes all state on every event** | `services/mechanism/service.py:359-383` | Writes 7+ store keys per event. Each write is separate I/O. Serializes event loop on I/O. |
| **Fraud records unbounded** | `services/fraud/service.py:25` | O(n) memory growth. After 1M events → ~500MB+ RAM. |
| **`AuditService` builds full ledger string in memory** | `services/audit/service.py` | Writes entire ledger as single JSON string. Large ledgers cause OOM. |
| **`FileStore.keys()` rglob scan** | `__store__.py:232` | O(n) I/O scan with no limit. Each call enumerates all files. |
| **Thread-per-FileStore executor leak** | `__store__.py:157` | One thread per FileStore instance, never shut down. |
| **`credit_limit()` traverses delegation chain** | `services/mechanism/service.py:115-128` | Called on every quote/origination. O(depth) per call with no caching. |

---

## 8. Developer Experience Findings

| Issue | Severity | Details |
|-------|----------|---------|
| No `pre-commit` config | Medium | No lint/type checking before commit. CI catches issues late. |
| No `tox` config | Medium | No matrix testing across Python versions locally. |
| `make test` uses `-q` flag | Low | Quiet mode hides test names — hard to see which test failed. |
| Missing `__all__` in 4+ modules | Medium | `__health__.py`, `__serve__.py`, `__runtime__.py`, `__migrate__.py`. |
| No `.env.example` | Low | No documented environment variables for local development. |
| No `docker-compose.yml` | Medium | Postgres, Vault, OTLP collector — no local dev environment. |
| Docs exist but are minimal | Low | 4 markdown files — need more examples. |

---

## 9. Prioritized Action Plan

### Immediate (before v0.2.0)

| Priority | Action | File(s) | Est. Effort |
|----------|--------|---------|-------------|
| **Critical** | Exclude `token` from `Configuration.to_dict()` | `__config__.py:465-470` | 15 min |
| **Critical** | Fix path traversal check in `FileStore.__path` | `__store__.py:244-253` | 30 min |
| **Critical** | Add `deque(maxlen=100000)` for FraudService records | `services/fraud/service.py:25` | 15 min |
| **High** | Add warning logs in governance, fee, saga silent returns | Multiple files | 30 min |
| **High** | Add `__all__` to modules missing it | 4 modules | 15 min |
| **High** | Fix env var type coercion in `__apply_env_overrides` | `__config__.py:609-613` | 30 min |
| **High** | Add structured logging with correlation ID context | `__runtime__.py:65-101` | 2 hr |
| **High** | Add `PrometheusMiddleware` warning on import failure | `__serve__.py:24-29` | 10 min |
| **Medium** | Add `ServiceSupervisor.shutdown()` for executor cleanup | `__store__.py:157` | 15 min |

### Short-term (v0.3.0)

| Priority | Action | Est. Effort |
|----------|--------|-------------|
| **High** | Add saga persistence via Store backend | 3-4 hr |
| **High** | Add Prometheus `/metrics` endpoint at standard path | 2 hr |
| **High** | Add async `asyncio` event bus implementation | 4-6 hr |
| **Medium** | Add config validation on Runtime startup (not just load) | 1 hr |
| **Medium** | Add depth limit to `__required_delegation` | 30 min |
| **Medium** | Add pagination to `FileStore.keys()` | 1 hr |
| **Low** | Add tox.ini for local matrix testing | 30 min |
| **Low** | Add `.env.example` for local dev | 15 min |

### Medium-term (v0.4.0 - v0.5.0)

| Priority | Action | Est. Effort |
|----------|--------|-------------|
| **High** | FastAPI instrumented with OTLP auto-instrumentation | 2 hr |
| **Medium** | Prometheus metrics endpoint (standard `/metrics`) | 1 hr |
| **Medium** | Config-driven fee schedules and governance ranges | 2 hr |
| **Medium** | Plugin-based model loading (strategy pattern) | 3 hr |
| **Low** | Structured audit export to S3/GCS | 4 hr |
| **Low** | Configuration JSON Schema enforcement at runtime | 2 hr |

---

## 10. Suggested Roadmap

### v0.2.0 (1 week)
- Fix: token exposure in config serialization
- Fix: path traversal in FileStore
- Fix: FraudService unbounded memory
- Fix: silent degradation logging (governance, fee, saga)
- Fix: env var type coercion
- Fix: missing `__all__` in modules
- Add: structured logging with correlation IDs
- **Tag v0.2.0 with all critical/high security fixes**

### v0.3.0 (2 weeks)
- Add: saga persistence via Store backend
- Add: Prometheus `/metrics` endpoint
- Add: async event bus (asyncio)
- Add: configuration validation at Runtime startup
- Fix: delegation chain depth limit
- Fix: `FileStore.keys()` pagination
- Add: tox.ini, `.env.example`
- **Tag v0.3.0**

### v0.4.0 (3 weeks)
- Add: FastAPI OTLP auto-instrumentation
- Add: config-driven fee schedules
- Add: plugin-based model loading
- Add: per-service health detail exposure
- Fix: catastrophic cancellation in break_even
- Fix: NaN/Inf propagation in FeeService
- **Tag v0.4.0**

### v0.5.0 (4 weeks)
- Add: structured audit export to S3/GCS
- Add: JSON Schema enforcement at runtime
- Add: distributed rate limiting
- Add: DLQ persistence and replay automation
- Add: pre-commit hooks
- Add: PyPI publishing CI
- **Tag v0.5.0**

---

## 11. Final Production Readiness Score: **57/100**

### Category Breakdown

| Category | Score | Reasoning |
|----------|-------|-----------|
| Architecture | 75/100 | Clean ABCs, but Runtime and MechanismService violate SRP |
| Security | 45/100 | Token leak, path traversal bypass, SQL injection surface, silent degradation |
| Testing | 70/100 | 509 tests but no concurrency/stress tests, no security tests |
| Performance | 40/100 | Unbounded memory in fraud service, I/O serialization, thread leaks |
| Observability | 35/100 | No structured logging, no Prometheus metrics, no log correlation |
| Packaging | 60/100 | PEP 621 good, but no PyPI publishing CI, `requirements.lock` removed |
| Documentation | 40/100 | README covers basics, docs/ exists but minimal, no API reference examples |
| DevOps | 30/100 | CI exists but no publish, no Docker, no pre-commit, no release automation |
| Developer Experience | 50/100 | Makefile present, good contributing guide, but missing pre-commit, tox, docker-compose |

**Verdict**: Pre-production alpha. The architectural foundation is strong but the production-observability surface (metrics, logging, sagas, DLQ) and several security issues block v1.0. 3-4 weeks of focused work across safety, observability, and testing would bring this to 80+.
