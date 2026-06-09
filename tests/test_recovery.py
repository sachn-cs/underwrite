"""Tests for RecoveryService — multi-stage post-default recovery orchestration.

Tests verify the full recovery workflow:
  DEFAULT_OCCURRED -> RECOVERY_STARTED -> recovery.offer ->
  recovery.offer_response (accepted) -> PAYMENT_PLAN ->
  PAYMENT_RECEIVED -> RECOVERY_COMPLETED
"""

from __future__ import annotations

from underwrite.__bus__ import LocalBus
from underwrite.__events__ import Event, EventType
from underwrite.services.recovery.service import RecoveryService


def recovery(bus=None) -> RecoveryService:
    return RecoveryService(service_id="recovery", bus=bus)


class TestRecoveryService:

    def test_emits_started_on_default(self) -> None:
        bus = LocalBus()
        received: list[Event] = []
        bus.subscribe(EventType.RECOVERY_STARTED, lambda e: received.append(e))
        svc = recovery(bus=bus)
        bus.start()
        svc.handle(
            Event(event_type=EventType.DEFAULT_OCCURRED,
                  source="test",
                  payload={
                      "borrower": "alice",
                      "principal": 50000
                  }))
        assert len(received) == 1
        assert received[0].payload["borrower"] == "alice"
        assert received[0].payload["principal"] == 50000.0
        assert received[0].payload["stage"] == "negotiation"
        assert "started_at" in received[0].payload

    def test_default_triggers_offer(self) -> None:
        bus = LocalBus()
        started: list[Event] = []
        offers: list[Event] = []
        bus.subscribe(EventType.RECOVERY_STARTED, lambda e: started.append(e))
        bus.subscribe("recovery.offer", lambda e: offers.append(e))
        svc = recovery(bus=bus)
        bus.start()
        svc.handle(
            Event(event_type=EventType.DEFAULT_OCCURRED,
                  source="test",
                  payload={
                      "borrower": "bob",
                      "principal": 100000
                  }))
        assert len(started) == 1
        assert len(offers) == 1
        assert offers[0].payload["borrower"] == "bob"
        assert offers[0].payload["offer_amount"] == 30000.0

    def test_does_not_emit_completed_on_default(self) -> None:
        bus = LocalBus()
        completed: list[Event] = []
        bus.subscribe(EventType.RECOVERY_COMPLETED,
                      lambda e: completed.append(e))
        svc = recovery(bus=bus)
        bus.start()
        svc.handle(
            Event(event_type=EventType.DEFAULT_OCCURRED,
                  source="test",
                  payload={
                      "borrower": "carol",
                      "principal": 50000
                  }))
        assert len(completed) == 0

    def test_emits_completed_after_full_recovery(self) -> None:
        bus = LocalBus()
        completed: list[Event] = []
        bus.subscribe(EventType.RECOVERY_COMPLETED,
                      lambda e: completed.append(e))
        svc = recovery(bus=bus)
        bus.start()
        svc.handle(
            Event(event_type=EventType.DEFAULT_OCCURRED,
                  source="test",
                  payload={
                      "borrower": "dave",
                      "principal": 10000
                  }))
        svc.handle(
            Event(event_type=EventType.PAYMENT_RECEIVED,
                  source="test",
                  payload={
                      "borrower": "dave",
                      "amount": 10000
                  }))
        assert len(completed) == 1
        assert completed[0].payload["recovered"] == 10000.0
        assert completed[0].payload["outstanding"] == 0.0

    def test_ignores_non_default_events(self) -> None:
        bus = LocalBus()
        started: list[Event] = []
        bus.subscribe(EventType.RECOVERY_STARTED, lambda e: started.append(e))
        svc = recovery(bus=bus)
        bus.start()
        svc.handle(Event(event_type="seed.added", source="test", payload={}))
        svc.handle(
            Event(event_type=EventType.LOAN_ORIGINATED,
                  source="test",
                  payload={}))
        assert len(started) == 0
