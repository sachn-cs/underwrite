# Configuration

The underwrite platform is configuration-driven. A single JSON file controls
which services are enabled, how they connect to infrastructure (bus, store,
identity), and service-specific parameters.

---

## 1. Configuration Loading

At startup, `Configuration.load()` (`underwrite/__config__.py:231`) searches
for a configuration file in the following order:

1.  **Explicit path** — if a path argument is provided and the file exists,
    it is loaded immediately.
2.  **`UNDERWRITE_ENV`** — if set to e.g. `production`, the loader tries
    `config.production.json`.
3.  **`Configuration.default()`** — if no file is found, a sensible default
    configuration is used.

After file loading, `__apply_env_overrides()` overlays any matching
`UNDERWRITE_*` environment variables on top (see
[ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md)).

```python
config = Configuration.load("underwrite.json")
# or
config = Configuration.default()
```

---

## 2. Pydantic Schema

`Configuration` extends `ForbidExtra` (which sets
`model_config = {"extra": "forbid"}`), so unknown keys in a JSON file cause a
`ConfigurationError`.

### Top-level fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `bus` | `BusConfig` | `BusConfig()` | Event bus settings |
| `store` | `StoreConfig` | `StoreConfig()` | Persistence backend |
| `logging` | `LoggingConfig` | `LoggingConfig()` | Log level/format/output |
| `identity` | `IdentityConfig` | `IdentityConfig()` | Ed25519 key material |
| `authz` | `AuthzConfig` | `AuthzConfig()` | Access control |
| `metrics` | `MetricsConfig` | `MetricsConfig()` | Metrics collection |
| `migration` | `MigrationConfig` | `MigrationConfig()` | Schema migration |
| `tracing` | `TracingConfig` | `TracingConfig()` | Distributed tracing |
| `saga` | `SagaConfig` | `SagaConfig()` | Saga orchestration |
| `secrets` | `SecretsConfig` | `SecretsConfig()` | Secrets backend configuration |
| `recovery` | `RecoveryConfig` | `RecoveryConfig()` | Auto-recovery settings |
| `fee` | `FeeConfig` | `FeeConfig()` | Fee schedules |
| `governance` | `GovernanceConfig` | `GovernanceConfig()` | Protocol governance parameters |
| `audit` | `AuditConfig` | `AuditConfig()` | Audit ledger limits |
| `data_dir` | `str` | `"./data"` | Filesystem store data directory |
| `services` | `dict[str, ServiceConfig]` | `{}` | Per-service enablement/priority |

### BusConfig

| Field | Type | Default | Valid values |
|-------|------|---------|--------------|
| `backend` | `str` | `"local"` | `local`, `sqs`, `modal` |
| `rate_limit` | `float` | `0.0` | >= 0 (0 = unlimited) |
| `max_workers` | `int` | `0` | >= 0 (0 = synchronous dispatch) |
| `max_futures` | `int` | `10000` | >= 1 |

### StoreConfig

| Field | Type | Default | Valid values |
|-------|------|---------|--------------|
| `backend` | `str` | `"memory"` | `memory`, `filesystem`, `postgres` |
| `dsn` | `str` | `""` | Connection string |
| `pool_size` | `int` | `5` | >= 1 |
| `read_backend` | `str` | `""` | Read-replica backend (empty = same as `backend`) |
| `read_dsn` | `str` | `""` | Read-replica DSN (empty = same as `dsn`) |

### LoggingConfig

| Field | Type | Default | Valid values |
|-------|------|---------|--------------|
| `level` | `str` | `"INFO"` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `output` | `str` | `"stdout"` | Free-form (e.g. `stdout`, `stderr`, file path) |
| `log_format` | `str` | `"text"` | `text`, `json` |

### IdentityConfig

| Field | Type | Default |
|-------|------|---------|
| `private_key` | `str` | `""` |
| `public_key` | `str` | `""` |
| `encryption_passphrase` | `str` | `""` |
| `key_ttl` | `float` | `86400.0` |
| `key_grace` | `float` | `3600.0` |

### AuthzConfig

| Field | Type | Default |
|-------|------|---------|
| `enabled` | `bool` | `true` |
| `policy_file` | `str` | `""` |

### MetricsConfig

| Field | Type | Default |
|-------|------|---------|
| `enabled` | `bool` | `true` |
| `export_interval` | `int` | `60` |

### TracingConfig

| Field | Type | Default | Valid values |
|-------|------|---------|--------------|
| `enabled` | `bool` | `false` | |
| `exporter` | `str` | `"console"` | `console`, `otlp`, `noop` |

### SecretsConfig

| Field | Type | Default |
|-------|------|---------|
| `backend` | `str` | `"env"` |
| `url` | `str` | `""` |
| `token` | `str` | `""` |
| `region` | `str` | `""` |

### RecoveryConfig

| Field | Type | Default |
|-------|------|---------|
| `auto_restart` | `bool` | `true` |
| `max_restarts` | `int` | `3` |
| `backoff_seconds` | `float` | `1.0` |

### ServiceConfig

| Field | Type | Default |
|-------|------|---------|
| `enabled` | `bool` | `false` |
| `priority` | `int` | `0` |

---

## 3. Environment Variable Overrides

Every configuration field can be overridden at runtime via
`UNDERWRITE_<SECTION>_<FIELD>` environment variables. The
`__apply_env_overrides()` method (`__config__.py:402`) iterates a hardcoded
mapping, coerces the string value to the target type, and updates the config
object.

Boolean coersion accepts `1`, `true`, `yes` (case-insensitive) for `True`;
everything else is `False`.

See [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md) for the complete
alphabetical listing.

---

## 4. Validation

- **Schema-level**: Pydantic `field_validator` decorators enforce constrained
  values (e.g. `bus.backend` must be one of `local`, `sqs`, `modal`;
  `rate_limit` must be >= 0; `logging.level` must match a known log level).
- **File-level**: `Configuration.__merge()` (`__config__.py:288`) validates
  every section against its Pydantic model via `model_copy` + re-instantiation.
  Unknown top-level keys and unknown per-section fields raise
  `ConfigurationError` with a descriptive message.
- **Path traversal**: The loader rejects file paths containing `..`.

---

## 5. Serialization

```python
config.to_dict()      # → dict (strips secrets.token and identity.private_key)
config.save("path")   # → JSON file (creates parent directories)
```

`to_dict()` excludes `None` values and redacts sensitive fields (`token`,
`private_key`) so serialised output is safe to log or store.

---

## 6. Default Configuration

`Configuration.default()` (`__config__.py:222`) provides:

```python
Configuration(
    store=StoreConfig(backend="filesystem"),
    services={name: ServiceConfig(enabled=False) for name in SERVICE_NAMES},
)
```

All other sections use their Pydantic model defaults (rate_limit=0, max_workers=0,
logging level=INFO, metrics enabled, etc.).

### Example configuration file (`underwrite.json`)

```json
{
    "bus": {
        "rate_limit": 100.0,
        "max_workers": 4,
        "max_futures": 10000,
        "max_buffer_size": 10000
    },
    "store": {
        "backend": "filesystem",
        "dsn": "./data"
    },
    "services": {
        "mechanism": {"enabled": true},
        "audit": {"enabled": true},
        "risk": {"enabled": true}
    }
}
```

> **Note**: `max_buffer_size` is accepted by `LocalBus.__init__()` but is not
> a field in `BusConfig`. Set it directly in JSON — it will be passed through
> at bus construction time.

---

## Available Services

The platform defines 28 nano services (`underwrite/__config__.py:461`):

`audit`, `collateral`, `collection`, `communication`, `decision`,
`disbursement`, `document`, `fee`, `fraud`, `governance`, `graph`, `identity`,
`mechanism`, `npa`, `notification`, `origination`, `payment`, `pricing`,
`quote`, `recovery`, `reporting`, `risk`, `servicing`, `settlement`,
`statement`, `underwriter`, `workflow`
