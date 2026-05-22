"""Fee assessment service.

Calculates and tracks fees: late payment fees, origination fees,
prepayment penalties, and service charges.  Emits ``fee.assessed``
when a fee is applied to a loan.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from underwrite.__events__ import Event, EventType
from underwrite.services.base import NanoService
from underwrite.validate import get_finite

FEE_SCHEDULES: dict[str, float] = {
    "late_payment": 25.0,
    "origination": 0.01,
    "prepayment": 0.005,
    "service": 5.0,
}


class FeeService(NanoService):
    """Manages fee assessment, tracking, and lifecycle."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.__lock: threading.RLock = threading.RLock()
        self.__fees: dict[str, dict[str, Any]] = {}
        self.__load_store()

    def handle(self, event: Event) -> None:
        """Assess and pay fees based on incoming events.

        Supports fee assessment (``fee.assess``), fee payment (``fee.pay``),
        and automatic late-payment fees on overdue loans.

        Args:
            event: The incoming event.
        """
        if event.event_type == EventType.FEE_ASSESS:
            loan_id: str = event.payload.get("loan_id", "")
            fee_type: str = event.payload.get("fee_type", "")
            if not loan_id or fee_type not in FEE_SCHEDULES:
                return
            amount: float = FEE_SCHEDULES[fee_type]
            if fee_type == "origination":
                principal: float = get_finite(event.payload, "principal", 0.0)
                amount = principal * FEE_SCHEDULES["origination"]

            fee_id: str = f"fee_{loan_id}_{fee_type}_{int(datetime.now(timezone.utc).timestamp())}"
            fee_record = {
                "loan_id": loan_id,
                "fee_type": fee_type,
                "amount": amount,
                "assessed_at": datetime.now(timezone.utc).isoformat(),
                "paid": False,
            }
            self.store.set(f"fee:{fee_id}", fee_record)
            self.__fees[f"fee:{fee_id}"] = fee_record
            self.__sync_store()
            self.emit(EventType.FEE_ASSESSED, {
                "fee_id": fee_id,
                "loan_id": loan_id,
                "fee_type": fee_type,
                "amount": amount,
            },
                      correlation_id=event.correlation_id)

        elif event.event_type == EventType.FEE_PAY:
            fee_id = event.payload.get("fee_id", "")
            record = self.store.get(f"fee:{fee_id}")
            if record and not record["paid"]:
                record["paid"] = True
                record["paid_at"] = datetime.now(timezone.utc).isoformat()
                self.store.set(f"fee:{fee_id}", record)
                self.__fees[f"fee:{fee_id}"] = dict(record)
                self.__sync_store()

        elif event.event_type == EventType.PAYMENT_OVERDUE:
            loan_id = event.payload.get("loan_id", "")
            if loan_id:
                self.emit("fee.assess", {
                    "loan_id": loan_id,
                    "fee_type": "late_payment",
                },
                          correlation_id=event.correlation_id)

    # -- state persistence ---------------------------------------------------

    def __load_store(self) -> None:
        """Restore fee records from the store, if present."""
        with self.__lock:
            raw = self.store.get(f"{self.service_id}:fees")
            if raw is not None and isinstance(raw, dict):
                self.__fees = dict(raw)

    def __sync_store(self) -> None:
        """Persist the current fee records to the store."""
        with self.__lock:
            self.store.set(f"{self.service_id}:fees", dict(self.__fees))
