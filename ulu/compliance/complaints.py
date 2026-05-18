"""RBI Ombudsman complaint management with SLA tracking.

Item 20 from production roadmap.
"""

from __future__ import annotations

import dataclasses
import datetime
import enum

from ulu.infra.logging import logger


class ComplaintStatus(enum.Enum):
    RECEIVED = "received"
    ACKNOWLEDGED = "acknowledged"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    CLOSED = "closed"


class ComplaintCategory(enum.Enum):
    LOAN_DISBURSEMENT = "loan_disbursement"
    INTEREST_CHARGES = "interest_charges"
    RECOVERY_HARASSMENT = "recovery_harassment"
    KYC_VERIFICATION = "kyc_verification"
    DATA_PRIVACY = "data_privacy"
    OTHER = "other"


@dataclasses.dataclass
class Complaint:
    """Represents a borrower complaint filed under RBI Ombudsman guidelines."""

    complaint_id: str
    borrower_id: str
    category: ComplaintCategory
    description: str
    status: ComplaintStatus
    created_at: datetime.datetime
    sla_deadline: datetime.datetime
    resolved_at: datetime.datetime | None = None
    resolution_notes: str = ""
    escalated_to: str = ""  # e.g., "RBI_Ombudsman", "Nodal_Officer"


class ComplaintService:
    """Manages complaint lifecycle with automatic SLA tracking."""

    DEFAULT_SLA_DAYS = 30
    ESCALATION_THRESHOLD_DAYS = 30

    def __init__(self) -> None:
        self._complaints: dict[str, Complaint] = {}

    def register(
        self,
        complaint_id: str,
        borrower_id: str,
        category: ComplaintCategory,
        description: str,
        sla_days: int | None = None,
    ) -> Complaint:
        """Registers a new complaint and sets SLA deadline."""
        if complaint_id in self._complaints:
            raise ValueError(f"complaint already exists: {complaint_id}")
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        deadline = now + datetime.timedelta(days=sla_days or self.DEFAULT_SLA_DAYS)
        complaint = Complaint(
            complaint_id=complaint_id,
            borrower_id=borrower_id,
            category=category,
            description=description,
            status=ComplaintStatus.RECEIVED,
            created_at=now,
            sla_deadline=deadline,
        )
        self._complaints[complaint_id] = complaint
        logger.info(
            "complaint_registered",
            complaint_id=complaint_id,
            borrower_id=borrower_id,
            category=category.value,
        )
        return complaint

    def acknowledge(self, complaint_id: str) -> Complaint:
        """Marks complaint as acknowledged."""
        complaint = self._get(complaint_id)
        if complaint.status != ComplaintStatus.RECEIVED:
            raise ValueError(f"cannot acknowledge complaint in status {complaint.status.value}")
        complaint.status = ComplaintStatus.ACKNOWLEDGED
        logger.info("complaint_acknowledged", complaint_id=complaint_id)
        return complaint

    def resolve(self, complaint_id: str, notes: str = "") -> Complaint:
        """Resolves a complaint with notes."""
        complaint = self._get(complaint_id)
        if complaint.status in {ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED}:
            raise ValueError(f"complaint already resolved/closed: {complaint_id}")
        complaint.status = ComplaintStatus.RESOLVED
        complaint.resolved_at = datetime.datetime.now(tz=datetime.timezone.utc)
        complaint.resolution_notes = notes
        logger.info("complaint_resolved", complaint_id=complaint_id, notes=notes)
        return complaint

    def close(self, complaint_id: str) -> Complaint:
        """Closes a resolved complaint."""
        complaint = self._get(complaint_id)
        if complaint.status != ComplaintStatus.RESOLVED:
            raise ValueError("only resolved complaints can be closed")
        complaint.status = ComplaintStatus.CLOSED
        logger.info("complaint_closed", complaint_id=complaint_id)
        return complaint

    def escalate(self, complaint_id: str, to: str = "RBI_Ombudsman") -> Complaint:
        """Escalates complaint to higher authority."""
        complaint = self._get(complaint_id)
        if complaint.status in {ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED}:
            raise ValueError("cannot escalate resolved/closed complaint")
        complaint.status = ComplaintStatus.ESCALATED
        complaint.escalated_to = to
        logger.info("complaint_escalated", complaint_id=complaint_id, to=to)
        return complaint

    def _get(self, complaint_id: str) -> Complaint:
        complaint = self._complaints.get(complaint_id)
        if complaint is None:
            raise ValueError(f"complaint not found: {complaint_id}")
        return complaint

    def get(self, complaint_id: str) -> Complaint | None:
        return self._complaints.get(complaint_id)

    def list_by_borrower(self, borrower_id: str) -> list[Complaint]:
        return [c for c in self._complaints.values() if c.borrower_id == borrower_id]

    def list_by_status(self, status: ComplaintStatus) -> list[Complaint]:
        return [c for c in self._complaints.values() if c.status == status]

    def list_overdue_sla(self) -> list[Complaint]:
        """Returns complaints whose SLA deadline has passed and are not resolved/closed."""
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        return [
            c for c in self._complaints.values()
            if c.sla_deadline < now and c.status not in {ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED}
        ]

    def summary(self) -> dict[str, int]:
        """Returns count of complaints per status."""
        counts: dict[str, int] = {}
        for status in ComplaintStatus:
            counts[status.value] = len(self.list_by_status(status))
        counts["overdue_sla"] = len(self.list_overdue_sla())
        return counts
