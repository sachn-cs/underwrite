# Environment Variables

All `UNDERWRITE_*` environment variables override the corresponding JSON
configuration field at runtime. Additional variables control risk model
loading, notification channels, and secrets backend access.

---

## Configuration Overrides

Parsed by `Configuration.__apply_env_overrides()` in
`underwrite/__config__.py:402`.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `UNDERWRITE_BUS_BACKEND` | No | `local` | Event bus backend (`local`, `sqs`, `modal`) |
| `UNDERWRITE_BUS_RATE_LIMIT` | No | `0` | Max events/second per subscriber (`0` = unlimited) |
| `UNDERWRITE_BUS_MAX_WORKERS` | No | `0` | Thread pool size (`0` = synchronous dispatch) |
| `UNDERWRITE_BUS_MAX_FUTURES` | No | `10000` | Max pending futures before backpressure |
| `UNDERWRITE_STORE_BACKEND` | No | `memory` | Store backend (`memory`, `filesystem`, `postgres`) |
| `UNDERWRITE_STORE_DSN` | No | `""` | Store connection string |
| `UNDERWRITE_STORE_POOL_SIZE` | No | `5` | Database connection pool size |
| `UNDERWRITE_STORE_READ_BACKEND` | No | `""` | Read-replica store backend (empty = use `STORE_BACKEND`) |
| `UNDERWRITE_STORE_READ_DSN` | No | `""` | Read-replica DSN (empty = use `STORE_DSN`) |
| `UNDERWRITE_LOG_LEVEL` | No | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |
| `UNDERWRITE_LOG_OUTPUT` | No | `stdout` | Log output target |
| `UNDERWRITE_LOG_FORMAT` | No | `text` | Log format (`text`, `json`) |
| `UNDERWRITE_DATA_DIR` | No | `./data` | Filesystem store data directory |
| `UNDERWRITE_AUTHZ_ENABLED` | No | `true` | Enable access control |
| `UNDERWRITE_AUTHZ_POLICY_FILE` | No | `""` | Path to Rego/OPA policy file |
| `UNDERWRITE_METRICS_ENABLED` | No | `true` | Enable metrics collection |
| `UNDERWRITE_METRICS_EXPORT_INTERVAL` | No | `60` | Metrics export interval in seconds |
| `UNDERWRITE_TRACING_ENABLED` | No | `false` | Enable distributed tracing |
| `UNDERWRITE_TRACING_EXPORTER` | No | `console` | Tracer exporter (`console`, `otlp`, `noop`) |
| `UNDERWRITE_SAGA_ENABLED` | No | `true` | Enable saga orchestration |
| `UNDERWRITE_IDENTITY_KEY_TTL` | No | `86400` | Key rotation interval in seconds |
| `UNDERWRITE_IDENTITY_KEY_GRACE` | No | `3600` | Key overlap grace period in seconds |
| `UNDERWRITE_SECRETS_BACKEND` | No | `env` | Secrets backend (`env`, `vault`, `aws`) |
| `UNDERWRITE_SECRETS_VAULT_URL` | No | `""` | HashiCorp Vault server URL |
| `UNDERWRITE_SECRETS_VAULT_TOKEN` | No | `""` | Vault authentication token |
| `UNDERWRITE_SECRETS_AWS_REGION` | No | `""` | AWS region for Secrets Manager |
| `UNDERWRITE_RECOVERY_AUTO_RESTART` | No | `true` | Auto-restart crashed services |
| `UNDERWRITE_RECOVERY_MAX_RESTARTS` | No | `3` | Maximum restart attempts per service |
| `UNDERWRITE_RECOVERY_BACKOFF` | No | `1.0` | Initial backoff in seconds (exponential) |
| `UNDERWRITE_AUDIT_MAX_LEDGER` | No | `100000` | Max audit ledger entries before rotation |
| `UNDERWRITE_AUDIT_EXPORT_URL` | No | `""` | Audit log export endpoint |

---

## Environment Selector

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `UNDERWRITE_ENV` | No | `""` | When set, loads `config.{value}.json` if no explicit config path is given |

---

## HTTP Server

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `UNDERWRITE_API_TOKEN` | No | `""` | Bearer token required for all HTTP API requests (see `--require-auth`) |

---

## Risk Model

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `RISK_MODEL_PATH` | No | `""` | Path to serialized risk model file |
| `RISK_MODEL_SHA256` | No | `""` | Expected SHA-256 hash of the model file (integrity check) |
| `UNDERWRITE_ALLOW_JOBLIB` | No | `""` | Set to `true` to enable `joblib` deserialization for pickle-based models |

---

## Secrets Backend

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VAULT_TOKEN` | No | `""` | Vault token (alternative to `UNDERWRITE_SECRETS_VAULT_TOKEN`) |
| `UNDERWRITE_SECRET_<NAME>` | No | — | Read secrets from environment; key is uppercased with `/` and `-` replaced by `_` |

---

## Notification Service

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NOTIFICATION_EMAIL_ENABLED` | No | `false` | Enable email dispatch via SES |
| `NOTIFICATION_SMS_ENABLED` | No | `false` | Enable SMS dispatch via Twilio |
| `NOTIFICATION_EMAIL_SENDER` | No | `noreply@underwrite.local` | SES sender address |
| `AWS_REGION` | No | `""` | AWS region for SES (leave empty to log instead of sending) |
| `TWILIO_ACCOUNT_SID` | No | `""` | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | No | `""` | Twilio auth token |
| `TWILIO_FROM_NUMBER` | No | `""` | Twilio SMS source phone number |

---

## Testing

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `UNDERWRITE_TEST_PG_DSN` | No | `""` | PostgreSQL DSN for integration tests |

---

## Boolean Coercion

When an environment variable maps to a `bool` field, the string is considered
`true` if it equals (case-insensitive) `1`, `true`, or `yes`. All other values
produce `false`.
