# Quickstart — 5 Minute Guide

## 1. Clone and Setup

```bash
git clone <repo-url>
cd unsecured-lending-underwriting
./setup.sh
```

## 2. Activate Environment

```bash
source .venv/bin/activate
```

## 3. Run Tests

```bash
make test
# or
./test.sh
```

Tests include the in-memory protocol engine, fraud detection, payment scheduling, PII redaction, error paths, and compliance checks.

## 4. Start Services

Launch individual nano services. Each runs as a long-lived process:

```bash
underwrite run mechanism audit risk
```

Start them in separate terminals to watch per-service output:

```bash
# Terminal 1 — mechanism (core state machine)
underwrite run mechanism

# Terminal 2 — audit (event ledger)
underwrite run audit

# Terminal 3 — risk (scoring and early warnings)
underwrite run risk
```

You will see log lines as each service starts and subscribes to events.

## 5. Check Health

```bash
underwrite health
```

Example output:

```
Status: healthy
OK: True
Checks:
  [OK] bus — subscribers: 3, dlq_count: 0
  [OK] store
  [OK] services — running: ['mechanism', 'audit', 'risk']
  [OK] saga
  [OK] dlq — dead_letter_count: 0
  [OK] service:mechanism
  [OK] service:audit
  [OK] service:risk
```

## 6. Publish an Event

### Via CLI (event bus — same process)

While `underwrite run mechanism` is running in another terminal, publish a command:

```bash
python -c "
from underwrite.__cli__ import load_config
from underwrite.__runtime__ import Runtime

config = load_config()
with Runtime(config) as rt:
    rt.start(['mechanism'])
    rt.publish('mechanism', {
        'command': 'add_seed',
        'user': 'bank-a',
        'base_budget': 1000000.0,
    })
    rt.publish('mechanism', {
        'command': 'add_user',
        'sponsor': 'bank-a',
        'user': 'borrower-1',
        'delegation_amount': 50000.0,
    })
    print('Events published')
"
```

Check the mechanism terminal — it will log each command and emit domain events (`seed.added`, `user.added`).

### Via HTTP (serve mode)

Start the HTTP daemon:

```bash
underwrite serve --port 8080 --services mechanism,audit,risk
```

Publish via curl:

```bash
curl -X POST http://localhost:8080/event \
  -H "Content-Type: application/json" \
  -d '{"event_type": "mechanism", "payload": {"command": "add_seed", "user": "bank-b", "base_budget": 500000.0}}'
```

## 7. View the Dead Letter Queue

If any service fails to process an event, it lands in the DLQ:

```bash
underwrite dlq
```

Example output with no failures:

```
Dead-letter queue: 0 entries
```

Replay failed events:

```bash
underwrite dlq --replay --max 10
```

## 8. Metrics

```bash
underwrite metrics
```

Example output after processing some events:

```
Counters:
  events.emitted: 2
  events.handled: 4
Timers:
  handle.duration: count=2 avg=1.2ms min=0.8ms max=1.6ms
```
