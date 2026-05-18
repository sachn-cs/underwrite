"""Velocity checks for wash lending and burst pattern detection.

Item 45 from production roadmap.
"""

from __future__ import annotations

import dataclasses
import datetime

from ulu.infra.logging import logger


@dataclasses.dataclass
class VelocityRecord:
    """A single origination or repayment event for velocity tracking."""

    borrower_id: str
    event_type: str  # "origination" or "repayment"
    amount: float
    timestamp: datetime.datetime


class VelocityCheckService:
    """Detects rapid origination-repayment cycles and burst origination patterns."""

    def __init__(self) -> None:
        self._records: dict[str, list[VelocityRecord]] = {}

    def _add(self, borrower_id: str, event_type: str, amount: float) -> None:
        record = VelocityRecord(
            borrower_id=borrower_id,
            event_type=event_type,
            amount=amount,
            timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
        )
        self._records.setdefault(borrower_id, []).append(record)
        logger.info("velocity_recorded", borrower_id=borrower_id, event_type=event_type, amount=amount)

    def record_origination(self, borrower_id: str, principal: float) -> None:
        self._add(borrower_id, "origination", principal)

    def record_repayment(self, borrower_id: str, amount: float) -> None:
        self._add(borrower_id, "repayment", amount)

    def check_wash_lending(
        self,
        borrower_id: str,
        window_hours: float = 24.0,
        min_cycle_count: int = 3,
    ) -> tuple[bool, float]:
        """Returns (flagged, score) if borrower shows rapid origination-repayment cycles."""
        records = self._records.get(borrower_id, [])
        if len(records) < min_cycle_count * 2:
            return False, 0.0

        now = datetime.datetime.now(tz=datetime.timezone.utc)
        cutoff = now - datetime.timedelta(hours=window_hours)
        recent = [r for r in records if r.timestamp >= cutoff]
        recent.sort(key=lambda r: r.timestamp)

        cycles = 0
        i = 0
        while i < len(recent) - 1:
            if recent[i].event_type == "origination" and recent[i + 1].event_type == "repayment":
                cycles += 1
                i += 2
            else:
                i += 1

        score = min(100.0, (cycles / max(1, min_cycle_count)) * 50.0)
        flagged = cycles >= min_cycle_count
        if flagged:
            logger.warning("wash_lending_detected", borrower_id=borrower_id, cycles=cycles, score=score)
        return flagged, score

    def check_burst_pattern(
        self,
        borrower_id: str,
        window_hours: float = 24.0,
        max_originations: int = 3,
    ) -> tuple[bool, int]:
        """Flags borrowers with more than max_originations within window_hours."""
        records = self._records.get(borrower_id, [])
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        cutoff = now - datetime.timedelta(hours=window_hours)
        originations = [r for r in records if r.event_type == "origination" and r.timestamp >= cutoff]
        count = len(originations)
        flagged = count > max_originations
        if flagged:
            logger.warning(
                "burst_origination_detected", borrower_id=borrower_id, count=count, window=window_hours
            )
        return flagged, count

    def get_records(self, borrower_id: str) -> list[VelocityRecord]:
        return list(self._records.get(borrower_id, []))
