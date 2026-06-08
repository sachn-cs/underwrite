"""Fraud detection — velocity checks, wash lending, and rule-based alerts."""

from __future__ import annotations

from collections import OrderedDict, deque
from datetime import datetime, timezone
from typing import Any

from underwrite.__events__ import Event, EventType
from underwrite.services.base import StatefulService
from underwrite.services.persistence import TypedStoreRepository
from underwrite.validate import get_finite, get_non_empty


class FraudService(StatefulService):
    """Detects wash lending, burst origination patterns, and configurable fraud rules."""

    MAX_BORROWERS: int = 100000
    SYNC_INTERVAL: int = 10

    def __init__(self, **kwargs: Any) -> None:
        """Initialise the fraud service with an empty activity record store.

        Args:
            **kwargs: Forwarded to NanoService.__init__.
        """
        super().__init__(**kwargs)
        self.__records: OrderedDict[str, deque[dict[str, Any]]] = OrderedDict()
        self.__sync_counter: int = 0
        self._repo: TypedStoreRepository[dict[str, list[dict[
            str, Any]]]] = self.store_repo("records", dict)
        loaded = self._repo.load(default={})
        if loaded:
            self.__records = self.__deserialize_records(loaded)

    @property
    def records(self) -> OrderedDict[str, deque[dict[str, Any]]]:
        """Returns a snapshot of the internal records dict (test-accessible hook)."""
        with self.state_lock:
            result: OrderedDict[str, deque[dict[str, Any]]] = OrderedDict()
            for k, v in self.__records.items():
                result[k] = deque(v, maxlen=v.maxlen)
            return result

    def handle(self, event: Event) -> None:
        """Check loan origination and repayment events against fraud rules.

        Triggers alerts for wash lending cycles, velocity bursts, and
        large-value originations.

        Args:
            event: The incoming event. LOAN_ORIGINATED and REPAID are processed.
        """
        with self.state_lock:
            if event.event_type == EventType.LOAN_ORIGINATED:
                borrower: str = get_non_empty(event.payload, "borrower")
                principal: float = get_finite(event.payload, "principal")
                self.__record(borrower, "origination", principal)
                self.__check_wash(borrower, event.correlation_id)
                self.__check_burst(borrower, event.correlation_id)
                if principal > 1_000_000:
                    self.emit(
                        EventType.FRAUD_ALERT,
                        {
                            "rule": "large_origination",
                            "borrower": borrower,
                            "principal": principal,
                        },
                        correlation_id=event.correlation_id,
                    )
            elif event.event_type == EventType.REPAID:
                user: str = get_non_empty(event.payload, "user")
                delta: float = get_finite(event.payload, "delta_earned")
                self.__record(user, "repayment", delta)
                self.__check_wash(user, event.correlation_id)

    def __record(self, borrower: str, event_type: str, amount: float) -> None:
        if borrower not in self.__records:
            if len(self.__records) >= self.MAX_BORROWERS:
                self.__records.popitem(last=False)
            self.__records[borrower] = deque(maxlen=1000)
        else:
            self.__records.move_to_end(borrower)
        records = self.__records[borrower]
        records.append({
            "event_type": event_type,
            "amount": amount,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self.__maybe_sync()

    def __check_wash(self, borrower: str, correlation_id: str) -> None:
        records = self.__records.get(borrower, deque())
        cycles: int = 0
        i: int = 0
        while i < len(records) - 1:
            if records[i]["event_type"] == "origination" and records[
                    i + 1]["event_type"] == "repayment":
                cycles += 1
                i += 2
            else:
                i += 1
        if cycles >= 3:
            self.emit(
                EventType.WASH_FLAG,
                {
                    "borrower": borrower,
                    "cycles": cycles,
                    "score": min(100.0, cycles * 16.67),
                },
                correlation_id=correlation_id,
            )

    def __check_burst(self, borrower: str, correlation_id: str) -> None:
        records = self.__records.get(borrower, deque())
        recent = [r for r in records if r["event_type"] == "origination"]
        if len(recent) > 3:
            self.emit(
                EventType.VELOCITY_FLAG,
                {
                    "borrower": borrower,
                    "count": len(recent),
                },
                correlation_id=correlation_id,
            )

    # -- state persistence ---------------------------------------------------

    def __maybe_sync(self) -> None:
        """Persist records to store every SYNC_INTERVAL calls."""
        self.__sync_counter += 1
        if self.__sync_counter >= self.SYNC_INTERVAL:
            self.__sync_counter = 0
            self._repo.save(self.__serialize_records())

    def __serialize_records(self) -> dict[str, list[dict[str, Any]]]:
        """Convert internal OrderedDict[deque] to store-friendly dict[list]."""
        return {k: list(v) for k, v in self.__records.items()}

    @staticmethod
    def __deserialize_records(
        raw: dict[str, list[dict[str, Any]]]
    ) -> OrderedDict[str, deque[dict[str, Any]]]:
        """Restore internal format from store-friendly dict[list]."""
        result: OrderedDict[str, deque[dict[str, Any]]] = OrderedDict()
        for k, v in raw.items():
            if isinstance(v, list):
                result[k] = deque(v, maxlen=1000)
        return result
