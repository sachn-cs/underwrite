# ADR 003: Ed25519 Cryptographic Provenance

**Status**: Accepted

## Context

The `underwrite` platform certifies financial events (loan origination, disbursement, default occurrence, fee assessment). Regulatory audit requires non-repudiation — the emitter must not be able to deny having emitted an event. Events are also the unit of audit for the `AuditService` (`services/audit/service.py`), which maintains an append-only ledger.

The signing infrastructure is in `__identity__.py` (Identity class, KeyRotationManager). Signature verification is in `__authz__.py` (`AccessControl.verify_signature()`). The signing scheme is defined at `services/base.py:132` where events are signed during `emit()`.

## Problem

How can the platform provide cryptographic proof of event provenance that survives log export, satisfies audit requirements, and works within a single-process pub-sub architecture?

## Decision

Every emitted `Event` carries an Ed25519 signature computed by the emitting service's `Identity` (`__identity__.py:30`).

### Signing Protocol

1. Each `NanoService` is assigned an `Identity` containing an Ed25519 keypair (`services/base.py:129`)
2. On `emit()`, the payload is serialized with `json.dumps(payload, sort_keys=True)` (`__authz__.py:166`)
3. The canonical string is constructed as:
   ```
   to_verify = f"{event_id}:{timestamp}:{event_type}:{payload_str}"
   ```
4. The private key signs this string; the base64-encoded signature is attached to the event as `signature` (`__identity__.py:126-142`)
5. The emitter's public key is included as `source_key` on the event envelope

### Verification Protocol

1. On receipt, `AccessControl.assert_verified(event)` (`__authz__.py:207`) calls `verify_signature()`
2. The trusted public key for `event.source` is looked up in `__trusted_keys` (registered via `trust(service_id, public_key)`)
3. The canonical string is reconstructed and verified with `Ed25519PublicKey.verify()` (`__authz__.py:163-170`)
4. If the signature is missing or invalid, `AuthzError` is raised and the event is dropped before reaching the handler

### Key Rotation

`KeyRotationManager` (`__identity__.py:166`) handles rotation:
- **TTL**: 86,400 seconds (24 hours) by default
- **Grace period**: 3,600 seconds (1 hour) — old keys remain accepted for verification during this window
- `verify_with_rotation()` checks current key first, then falls back to the previous key if within the grace period

### Key Storage

Private keys are stored in PEM format. When `encryption_passphrase` is provided, the key is encrypted at rest using PKCS8 `BestAvailableEncryption` (`__identity__.py:89-90`). Backends: env vars, Vault (`VaultSecretsBackend`), or AWS Secrets Manager (`AwsSecretsBackend`), all via `SecretsManager` (`__secrets__.py`).

## Alternatives Considered

- **HMAC with shared secret**: Simpler (symmetric) but lacks non-repudiation — any service holding the shared secret could forge events from another service. An auditor could not distinguish which service created an event.

- **JWT (JSON Web Tokens)**: Adds complexity (token expiry, refresh, standard claims) without benefit. Ed25519 provides the same cryptographic guarantee with fewer moving parts. JWTs also require clock synchronization for expiry validation.

- **No signatures (trust all intra-process events)**: Fastest option (no ~100 µs signing/verification per event) but unacceptable for audit. Without signatures, the audit log contains events that could have been forged by any compromised service in the process.

## Consequences

### Positive
- Cryptographic provenance — every event can be independently verified against the emitter's public key, even after export from the system
- Non-repudiation — the emitter cannot deny having emitted a signed event
- Transparent rotation — `KeyRotationManager` keeps the system available during key transitions

### Negative
- Signing/verification overhead — ~100 µs per event. Acceptable for financial workloads where throughput is <10k events/s
- Key management dependency — services need access to their private key at startup. Mitigated by `SecretsManager` with three backends, but adds deployment complexity
- `cryptography` library mandatory — adds a C-extension build dependency (`pyproject.toml` line 31: `"cryptography>=41.0"`). Without it, `__identity__.py` raises a warning at module load
- Signature does not cover the full event chain — only a single event is signed. A malicious actor could reorder events in the audit log. Mitigated by the `correlation_id` chain linking events across a transaction
