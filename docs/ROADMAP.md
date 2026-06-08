# Roadmap

Based on `TODO.md` (production readiness score: 57/100) and codebase analysis.

---

## Short-term — v0.2.0 (~1 week)

| Priority | Item | Files | Est. |
|----------|------|-------|------|
| Critical | Exclude `token` from `Configuration.to_dict()` (CD2) | `__config__.py:465-470` | 15m |
| Critical | Fix path traversal in `FileStore.__path` (CD4 / HD6) | `__store__.py:244-253` | 30m |
| Critical | Bound `FraudService.__records` with `deque(maxlen=100000)` (HD3) | `services/fraud/service.py:25` | 15m |
| High | Add warning logs for silent returns in governance, fee, saga | Multiple files | 30m |
| High | Add `__all__` to modules missing it (`__health__`, `__serve__`, `__runtime__`, `__migrate__`) | 4 modules | 15m |
| High | Fix env var type coercion in `Configuration.__apply_env_overrides` (MD5) | `__config__.py:609-613` | 30m |
| High | Add structured logging with correlation ID context | `__runtime__.py:65-101` | 2h |
| High | Add `PrometheusMiddleware` import-failure warning (HD8) | `__serve__.py:24-29` | 10m |
| Medium | `ServiceSupervisor.shutdown()` for `FileStore` thread cleanup (CD5) | `__store__.py:157` | 15m |

## Medium-term — v0.3.0 (~2 weeks)

| Priority | Item | Est. |
|----------|------|------|
| High | Saga persistence via Store backend (in-memory only today) | 3-4h |
| High | Prometheus `/metrics` endpoint at standard path | 2h |
| High | Async event bus (`asyncio`) implementation | 4-6h |
| Medium | Configuration validation at Runtime startup (not just load) | 1h |
| Medium | Delegation chain depth limit in `__required_delegation` (MD3) | 30m |
| Medium | `FileStore.keys()` pagination (MD2) | 1h |
| Low | `tox.ini` for local matrix testing | 30m |
| Low | `.env.example` for local dev | 15m |

## Long-term — v0.4.0 ~ v0.5.0 (~4 weeks)

| Priority | Feature | Est. |
|----------|---------|------|
| High | FastAPI OTLP auto-instrumentation (`opentelemetry-instrumentation-fastapi`) | 2h |
| Medium | Config-driven fee schedules (replace `FEE_SCHEDULES` module-level dict) | 2h |
| Medium | Plugin-based model loading (strategy pattern for risk models) | 3h |
| Medium | Distributed rate limiting (`DistributedRateLimiter` with Store backend) | 2h |
| Medium | DLQ persistence + replay automation (CLI command) | 2h |
| Medium | PyPI publishing CI (GitHub Actions release workflow) | 1h |
| Low | Structured audit export to S3/GCS | 4h |
| Low | JSON Schema enforcement at runtime | 2h |

## Production Readiness — v1.0.0

Target: **80+ production readiness score** (currently 57/100).

| Category | Target | Current |
|----------|--------|---------|
| Architecture | 85+ | 75 |
| Security | 80+ | 45 |
| Testing | 80+ | 70 |
| Performance | 70+ | 40 |
| Observability | 80+ | 35 |
| Packaging | 80+ | 60 |
| Documentation | 70+ | 40 |
| DevOps | 70+ | 30 |
| Developer Experience | 70+ | 50 |

### Must-have for v1.0.0
- Fix all critical security issues (token exposure, path traversal, SQL injection)
- Prometheus `/metrics` at standard path (`GET /metrics`, not `/v1/metrics`)
- Structured logging with correlation IDs
- Async event bus
- Saga persistence (not in-memory)
- Distributed event bus support (SQS/Modal) — at least one production backend
- Pre-commit hooks configured
- `docker-compose.yml` for local Postgres + Vault + OTLP
- 80%+ test coverage with concurrency stress tests

### Nice-to-have for v1.0.0
- Config-driven fee schedules
- Plugin-based model loading
- Structured audit export to object storage
- PyPI publishing CI
