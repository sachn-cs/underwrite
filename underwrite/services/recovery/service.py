"""Recovery workflows — post-default recovery orchestration.

Implements a multi-stage recovery process tracked in-memory:
  1. NEGOTIATION — offer is sent (stage recorded)
  2. PAYMENT_PLAN — tracked when payments arrive
  3. ESCALATION — flagged if too many offers rejected
  4. SETTLEMENT — recovery completed or loss recognized

State is in-memory per borrower.  The full workflow is driven by
incoming events (DEFAULT_OCCURRED, PAYMENT_RECEIVED) rather than
internal event chaining, so tests can call handle() directly.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from underwrite.__events__ import Event, EventType
from underwrite.__logger__ import logger
from underwrite.services import NanoService
from underwrite.validate import get_finite, get_non_empty

DEFAULT_RECOVERY_RATE: float = 0.3
NEGOTIATION_DAYS: int = 30
ESCALATION_THRESHOLD: int = 3


class RecoveryStage(str, Enum):
    NEGOTIATION = "negotiation"
    PAYMENT_PLAN = "payment_plan"
    ESCALATION = "escalation"
    SETTLEMENT = "settlement"


class RecoveryService(NanoService):
    """Orchestrates multi-stage recovery after a default event.

    Tracks recovery state in-memory per borrower.  The service
    reacts to DEFAULT_OCCURRED, PAYMENT_RECEIVED, and offer
    response events to drive recovery forward.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.__recoveries: dict[str, dict[str, Any]] = {}

    def handle(self, event: Event) -> None:
        if event.event_type == EventType.DEFAULT_OCCURRED:
            self.__start_recovery(event)
        elif event.event_type == EventType.PAYMENT_RECEIVED:
            self.__on_payment_received(event)
        elif event.event_type == "recovery.offer_response":
            self.__on_offer_response(event)

    def __start_recovery(self, event: Event) -> None:
        borrower: str = get_non_empty(event.payload, "borrower")
        principal: float = get_finite(event.payload, "principal")

        recovery: dict[str, Any] = {
            "borrower": borrower,
            "principal": principal,
            "stage": RecoveryStage.NEGOTIATION.value,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "offer_count": 0,
            "plan_failures": 0,
            "recovered": 0.0,
            "last_action": datetime.now(timezone.utc).isoformat(),
        }
        self.__recoveries[borrower] = recovery

        logger.info("recovery started for %s (principal=%.2f)", borrower,
                    principal)
        self.emit(
            EventType.RECOVERY_STARTED,
            {
                "borrower": borrower,
                "principal": principal,
                "stage": RecoveryStage.NEGOTIATION.value,
                "started_at": recovery["started_at"],
            },
            correlation_id=event.correlation_id,
        )

        offer_amount: float = principal * DEFAULT_RECOVERY_RATE
        recovery["offer_count"] += 1
        recovery["last_action"] = datetime.now(timezone.utc).isoformat()

        self.emit(
            "recovery.offer",
            {
                "borrower":
                    borrower,
                "offer_amount":
                    offer_amount,
                "due_by": (datetime.now(timezone.utc) +
                           timedelta(days=NEGOTIATION_DAYS)).isoformat(),
                "stage":
                    RecoveryStage.NEGOTIATION.value,
            },
            correlation_id=event.correlation_id,
        )

    def __on_offer_response(self, event: Event) -> None:
        borrower: str = get_non_empty(event.payload, "borrower")
        accepted: bool = event.payload.get("accepted", False)
        recovery = self.__recoveries.get(borrower)
        if not recovery:
            return
        if recovery["stage"] in (
                RecoveryStage.ESCALATION.value,
                RecoveryStage.SETTLEMENT.value,
        ):
            return

        if accepted:
            recovery["stage"] = RecoveryStage.PAYMENT_PLAN.value
            recovery["last_action"] = datetime.now(timezone.utc).isoformat()
            logger.info("recovery offer accepted for %s", borrower)
            self.emit(
                EventType.RECOVERY_STARTED,
                {
                    "borrower": borrower,
                    "principal": recovery["principal"],
                    "stage": RecoveryStage.PAYMENT_PLAN.value,
                    "message": "payment plan agreed",
                },
                correlation_id=event.correlation_id,
            )
        else:
            recovery["offer_count"] += 1
            if recovery["offer_count"] >= ESCALATION_THRESHOLD:
                recovery["stage"] = RecoveryStage.ESCALATION.value
                recovery["last_action"] = datetime.now(timezone.utc).isoformat()
                logger.warning("recovery escalated for %s", borrower)
                self.emit(
                    "recovery.escalated",
                    {
                        "borrower": borrower,
                        "principal": recovery["principal"],
                        "stage": RecoveryStage.ESCALATION.value,
                    },
                    correlation_id=event.correlation_id,
                )
            else:
                recovery["last_action"] = datetime.now(timezone.utc).isoformat()
                offer_amount = recovery["principal"] * DEFAULT_RECOVERY_RATE
                self.emit(
                    "recovery.offer",
                    {
                        "borrower":
                            borrower,
                        "offer_amount":
                            offer_amount,
                        "due_by":
                            (datetime.now(timezone.utc) +
                             timedelta(days=NEGOTIATION_DAYS)).isoformat(),
                        "stage":
                            RecoveryStage.NEGOTIATION.value,
                    },
                    correlation_id=event.correlation_id,
                )

    def __on_payment_received(self, event: Event) -> None:
        borrower: str = get_non_empty(event.payload, "borrower")
        amount: float = get_finite(event.payload, "amount")
        recovery = self.__recoveries.get(borrower)
        if not recovery:
            return
        if recovery["stage"] == RecoveryStage.SETTLEMENT.value:
            return

        recovery["recovered"] += amount
        recovery["last_action"] = datetime.now(timezone.utc).isoformat()
        outstanding: float = recovery["principal"] - recovery["recovered"]

        if outstanding <= 0:
            recovery["stage"] = RecoveryStage.SETTLEMENT.value
            logger.info("recovery completed for %s (recovered=%.2f)", borrower,
                        recovery["recovered"])
            self.emit(
                EventType.RECOVERY_COMPLETED,
                {
                    "borrower": borrower,
                    "recovered": recovery["recovered"],
                    "outstanding": 0.0,
                    "stage": RecoveryStage.SETTLEMENT.value,
                },
                correlation_id=event.correlation_id,
            )
        else:
            recovery["last_action"] = datetime.now(timezone.utc).isoformat()
            logger.info(
                "recovery progress for %s: recovered=%.2f "
                "outstanding=%.2f", borrower, recovery["recovered"],
                outstanding)
            self.emit(
                "recovery.progress",
                {
                    "borrower": borrower,
                    "recovered": recovery["recovered"],
                    "outstanding": outstanding,
                    "stage": recovery["stage"],
                },
                correlation_id=event.correlation_id,
            )
