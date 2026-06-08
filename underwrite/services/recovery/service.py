"""Recovery workflows — post-default recovery orchestration.

NOTE: This is a stub implementation.  In production, this service
should integrate with collections, legal workflow, and external
recovery agencies.  The current implementation immediately marks
recovery as complete at a flat 30% recovery rate.
"""

from __future__ import annotations

from datetime import datetime, timezone

from underwrite.__events__ import Event, EventType
from underwrite.__logger__ import logger
from underwrite.services import NanoService
from underwrite.validate import get_finite, get_non_empty

DEFAULT_RECOVERY_RATE: float = 0.3


class RecoveryService(NanoService):
    """Orchestrates recovery actions after a default event.

    Currently a stub — emits RECOVERY_STARTED then immediately
    RECOVERY_COMPLETED at a flat rate.  Replace with real workflow.
    """

    def handle(self, event: Event) -> None:
        if event.event_type != EventType.DEFAULT_OCCURRED:
            return
        borrower: str = get_non_empty(event.payload, "borrower")
        principal: float = get_finite(event.payload, "principal")
        logger.warning("recovery stub: starting recovery for %s (%.2f)",
                       borrower, principal)
        self.emit(
            EventType.RECOVERY_STARTED,
            {
                "borrower": borrower,
                "principal": principal,
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
            correlation_id=event.correlation_id,
        )
        recovery_amount: float = principal * DEFAULT_RECOVERY_RATE
        self.emit(
            EventType.RECOVERY_COMPLETED,
            {
                "borrower": borrower,
                "recovered": recovery_amount,
                "outstanding": principal - recovery_amount,
            },
            correlation_id=event.correlation_id,
        )
