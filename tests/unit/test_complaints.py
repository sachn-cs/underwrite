"""Unit tests for RBI complaint management."""

from __future__ import annotations

import datetime

import pytest

from ulu.compliance.complaints import (
    ComplaintCategory,
    ComplaintService,
    ComplaintStatus,
)


class TestComplaintService:
    def test_register_complaint(self) -> None:
        svc = ComplaintService()
        c = svc.register("C001", "b1", ComplaintCategory.LOAN_DISBURSEMENT, "loan not disbursed")
        assert c.complaint_id == "C001"
        assert c.borrower_id == "b1"
        assert c.status == ComplaintStatus.RECEIVED
        assert c.sla_deadline > c.created_at

    def test_register_duplicate_raises(self) -> None:
        svc = ComplaintService()
        svc.register("C001", "b1", ComplaintCategory.OTHER, "issue")
        with pytest.raises(ValueError, match="already exists"):
            svc.register("C001", "b1", ComplaintCategory.OTHER, "issue")

    def test_acknowledge(self) -> None:
        svc = ComplaintService()
        svc.register("C001", "b1", ComplaintCategory.OTHER, "issue")
        c = svc.acknowledge("C001")
        assert c.status == ComplaintStatus.ACKNOWLEDGED

    def test_acknowledge_wrong_status_raises(self) -> None:
        svc = ComplaintService()
        svc.register("C001", "b1", ComplaintCategory.OTHER, "issue")
        svc.acknowledge("C001")
        with pytest.raises(ValueError, match="cannot acknowledge"):
            svc.acknowledge("C001")

    def test_resolve(self) -> None:
        svc = ComplaintService()
        svc.register("C001", "b1", ComplaintCategory.OTHER, "issue")
        c = svc.resolve("C001", notes="fixed")
        assert c.status == ComplaintStatus.RESOLVED
        assert c.resolved_at is not None
        assert c.resolution_notes == "fixed"

    def test_close(self) -> None:
        svc = ComplaintService()
        svc.register("C001", "b1", ComplaintCategory.OTHER, "issue")
        svc.resolve("C001")
        c = svc.close("C001")
        assert c.status == ComplaintStatus.CLOSED

    def test_close_unresolved_raises(self) -> None:
        svc = ComplaintService()
        svc.register("C001", "b1", ComplaintCategory.OTHER, "issue")
        with pytest.raises(ValueError, match="only resolved"):
            svc.close("C001")

    def test_escalate(self) -> None:
        svc = ComplaintService()
        svc.register("C001", "b1", ComplaintCategory.OTHER, "issue")
        c = svc.escalate("C001", to="Nodal_Officer")
        assert c.status == ComplaintStatus.ESCALATED
        assert c.escalated_to == "Nodal_Officer"

    def test_escalate_resolved_raises(self) -> None:
        svc = ComplaintService()
        svc.register("C001", "b1", ComplaintCategory.OTHER, "issue")
        svc.resolve("C001")
        with pytest.raises(ValueError, match="cannot escalate"):
            svc.escalate("C001")

    def test_get_and_list(self) -> None:
        svc = ComplaintService()
        svc.register("C001", "b1", ComplaintCategory.OTHER, "a")
        svc.register("C002", "b1", ComplaintCategory.OTHER, "b")
        svc.register("C003", "b2", ComplaintCategory.OTHER, "c")
        assert svc.get("C001") is not None
        assert svc.get("C999") is None
        assert len(svc.list_by_borrower("b1")) == 2
        assert len(svc.list_by_status(ComplaintStatus.RECEIVED)) == 3

    def test_list_overdue_sla(self) -> None:
        svc = ComplaintService()
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        c = svc.register("C001", "b1", ComplaintCategory.OTHER, "issue", sla_days=-1)
        assert c.sla_deadline < now
        overdue = svc.list_overdue_sla()
        assert len(overdue) == 1
        assert overdue[0].complaint_id == "C001"

    def test_summary(self) -> None:
        svc = ComplaintService()
        svc.register("C001", "b1", ComplaintCategory.OTHER, "a")
        svc.register("C002", "b2", ComplaintCategory.OTHER, "b")
        svc.resolve("C001")
        svc.close("C001")
        summary = svc.summary()
        assert summary["received"] == 1
        assert summary["resolved"] == 0
        assert summary["closed"] == 1
