"""NPA tracking — RBI-mandated asset classification and DLG triggers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from underwrite.__events__ import Event, EventType
from underwrite.__logger__ import logger
from underwrite.services.base import StatefulService
from underwrite.services.persistence import TypedStoreRepository
from underwrite.validate import get_finite, get_non_empty


class NPAService(StatefulService):
    """Tracks days-past-due and transitions accounts through NPA buckets.

    Buckets follow RBI Master Circular:
      - Standard:    0-90 days
      - Substandard: 91-180 days
      - Doubtful:    181-360 days
      - Loss:        >360 days
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.__accounts: dict[str, dict[str, Any]] = {}
        self.__trigger_days: int = 120
        self._repo: TypedStoreRepository[dict[str,
                                              dict[str,
                                                   Any]]] = self.store_repo(
                                                       "accounts", dict)
        loaded = self._repo.load(default={})
        if loaded:
            self.__accounts = loaded

    def handle(self, event: Event) -> None:
        with self.state_lock:
            if event.event_type == EventType.LOAN_ORIGINATED:
                borrower: str = get_non_empty(event.payload, "borrower")
                self.__accounts[borrower] = {
                    "originated_at": datetime.now(timezone.utc).isoformat(),
                    "days_overdue": 0,
                    "dlg_invoked": False,
                }
                self.__sync()
            elif event.event_type == EventType.DEFAULT_OCCURRED:
                borrower = event.payload.get("borrower", "")
                if not borrower:
                    logger.warning(
                        "dropping DEFAULT_OCCURRED with missing borrower")
                    return
                record = self.__accounts.get(borrower, {})
                days: int = record.get("days_overdue", self.__trigger_days)
                bucket: str = self.classify_overdue_days(days)
                should_trigger_dlg: bool = (
                    borrower in self.__accounts and days >= self.__trigger_days
                    and not record.get("dlg_invoked", False))
                if should_trigger_dlg:
                    self.__accounts[borrower]["dlg_invoked"] = True
                self.emit(
                    EventType.NPA_BUCKET_CHANGED,
                    {
                        "borrower": borrower,
                        "bucket": bucket,
                    },
                    correlation_id=event.correlation_id,
                )
                if should_trigger_dlg:
                    self.__sync()
                    self.emit(
                        EventType.DLG_TRIGGERED,
                        {
                            "loan_id":
                            borrower,
                            "recovery_amount":
                            get_finite(event.payload, "principal", 0.0),
                        },
                        correlation_id=event.correlation_id,
                    )

    def mark_overdue(self, borrower: str, days: int) -> None:
        """Update the days-past-due counter for a borrower.

        Args:
            borrower: The borrower identifier.
            days: Number of days past due to record.
        """
        with self.state_lock:
            if borrower in self.__accounts:
                self.__accounts[borrower]["days_overdue"] = days
                self.__sync()

    # -- state persistence ---------------------------------------------------

    def __sync(self) -> None:
        """Persist the current NPA accounts to the store."""
        self._repo.save(self.__accounts)

    @staticmethod
    def classify_overdue_days(days: int) -> str:
        """Classify days-past-due into RBI NPA bucket."""
        if days <= 90:
            return "standard"
        if days <= 180:
            return "substandard"
        if days <= 360:
            return "doubtful"
        return "loss"
