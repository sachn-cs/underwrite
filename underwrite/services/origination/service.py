"""Loan origination service.

Handles the intake, validation, and submission of loan applications.
Emits ``origination.created`` when a new application is started and
``origination.submitted`` when the application is ready for review.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from underwrite.__events__ import Event, EventType
from underwrite.__logger__ import logger
from underwrite.services.base import NanoService
from underwrite.validate import get_finite


class OriginationService(NanoService):
    """Manages loan application lifecycle: creation, validation, submission."""

    def __init__(self, **kwargs: Any) -> None:
        self.__lock: threading.RLock = threading.RLock()
        super().__init__(**kwargs)

    def handle(self, event: Event) -> None:
        if event.event_type == EventType.ORIGINATION_CREATE:
            borrower: str = event.payload.get("borrower", "")
            principal: float = get_finite(event.payload, "principal", 0.0)
            if not borrower or principal <= 0:
                logger.warning(
                    "dropping ORIGINATION_CREATE with missing borrower or principal"
                )
                return
            application_id: str = f"app_{borrower}_{int(datetime.now(timezone.utc).timestamp())}"
            app_record = {
                "borrower": borrower,
                "principal": principal,
                "status": "created",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            self.store.set(f"origination:{application_id}", app_record)
            self.emit(
                EventType.ORIGINATION_CREATED,
                {
                    "application_id": application_id,
                    "borrower": borrower,
                    "principal": principal,
                },
                correlation_id=event.correlation_id,
            )

        elif event.event_type == EventType.ORIGINATION_SUBMIT:
            application_id = event.payload.get("application_id", "")
            with self.__lock:
                record = self.store.get(f"origination:{application_id}")
                if not record or record.get("status") != "created":
                    return
                record["status"] = "submitted"
                record["submitted_at"] = datetime.now(timezone.utc).isoformat()
                self.store.set(f"origination:{application_id}", record)
            self.emit(
                EventType.ORIGINATION_SUBMITTED,
                {
                    "application_id": application_id,
                    "borrower": record["borrower"],
                    "principal": record["principal"],
                },
                correlation_id=event.correlation_id,
            )
