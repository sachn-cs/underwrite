# Changelog

## [Unreleased]

### Added
- Event payload size validation — payloads exceeding 1 MB raise `ProtocolError`
- Per-handler timeout (30s) in `AsyncLocalBus` — slow handlers are sent to DLQ
- Distributed tracing context propagation — `trace_id` and `parent_span_id` fields on `Event`
- `MemoryStore` eviction policy — bounded by configurable `max_entries`
- API versioning — all endpoints under `/v1/` prefix (`/v1/health`, `/v1/metrics`, `/v1/publish`)
- Kubernetes liveness/readiness probes (`/healthz`, `/readyz`)
- Structured error responses with `X-Request-ID` header propagation
- Graceful shutdown with configurable timeout in `serve` command
- PII redaction in JSON log formatter — sensitive fields are masked
- CI/CD pipeline (GitHub Actions) — lint, type-check, and test across Python 3.10–3.13
- Dockerfile for production deployment
- Crypto availability warning at module load
- `__slots__` on `Event` dataclass for reduced memory footprint

### Changed
- `import random` moved from method body to module level in `__circuit__.py`
- British English → American English in all docstrings (`Initialises` → `Initializes`)
- `logger.debug(exc_info=True)` → `logger.warning` in `__bus__.py.__trim_futures()` for visible error surfacing

### Fixed
- Async bus DLQ persistence — `AsyncLocalBus` now passes store to `DeadLetterQueue`
- Async dispatch loop handles `CancelledError` for clean shutdown
- MemoryStore eviction correctly distinguishes new keys from updates

### Security
- Production guardrail warning when `cryptography` library is not installed
- All sensitive field values (passwords, tokens, SSNs, etc.) are redacted in JSON logs
