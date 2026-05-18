"""Unit tests for governance proposal lifecycle."""

from __future__ import annotations

import pytest

from ulu.governance.proposals import ProposalLifecycleService, ProposalStatus


class TestProposalLifecycleService:
    def test_create(self) -> None:
        svc = ProposalLifecycleService()
        p = svc.create("P1", "title", "desc", "proposer1", {"rate_cap": 0.5})
        assert p.proposal_id == "P1"
        assert p.status == ProposalStatus.DRAFT
        assert p.parameter_changes == {"rate_cap": 0.5}

    def test_create_duplicate_raises(self) -> None:
        svc = ProposalLifecycleService()
        svc.create("P1", "t", "d", "p1")
        with pytest.raises(ValueError, match="already exists"):
            svc.create("P1", "t", "d", "p1")

    def test_start_voting(self) -> None:
        svc = ProposalLifecycleService()
        svc.create("P1", "t", "d", "p1")
        p = svc.start_voting("P1")
        assert p.status == ProposalStatus.VOTING
        assert p.voting_start is not None
        assert p.voting_end is not None

    def test_start_voting_wrong_status_raises(self) -> None:
        svc = ProposalLifecycleService()
        svc.create("P1", "t", "d", "p1")
        svc.start_voting("P1")
        with pytest.raises(ValueError, match="only draft"):
            svc.start_voting("P1")

    def test_finalize_passed(self) -> None:
        svc = ProposalLifecycleService(voting_duration_hours=0.0, timelock_hours=0.0)
        svc.create("P1", "t", "d", "p1")
        svc.start_voting("P1")
        p = svc.finalize("P1", passed=True)
        assert p.status == ProposalStatus.TIMELOCKED
        assert p.execution_time is not None

    def test_finalize_rejected(self) -> None:
        svc = ProposalLifecycleService(voting_duration_hours=0.0)
        svc.create("P1", "t", "d", "p1")
        svc.start_voting("P1")
        p = svc.finalize("P1", passed=False)
        assert p.status == ProposalStatus.REJECTED

    def test_finalize_before_end_raises(self) -> None:
        svc = ProposalLifecycleService(voting_duration_hours=24.0)
        svc.create("P1", "t", "d", "p1")
        svc.start_voting("P1")
        with pytest.raises(ValueError, match="voting period has not ended"):
            svc.finalize("P1", passed=True)

    def test_execute(self) -> None:
        svc = ProposalLifecycleService(voting_duration_hours=0.0, timelock_hours=0.0)
        svc.create("P1", "t", "d", "p1")
        svc.start_voting("P1")
        svc.finalize("P1", passed=True)
        p = svc.execute("P1")
        assert p.status == ProposalStatus.EXECUTED

    def test_execute_wrong_status_raises(self) -> None:
        svc = ProposalLifecycleService()
        svc.create("P1", "t", "d", "p1")
        with pytest.raises(ValueError, match="only timelocked"):
            svc.execute("P1")

    def test_execute_timelock_not_expired_raises(self) -> None:
        svc = ProposalLifecycleService(voting_duration_hours=0.0, timelock_hours=24.0)
        svc.create("P1", "t", "d", "p1")
        svc.start_voting("P1")
        svc.finalize("P1", passed=True)
        with pytest.raises(ValueError, match="timelock has not expired"):
            svc.execute("P1")

    def test_get_and_list(self) -> None:
        svc = ProposalLifecycleService()
        svc.create("P1", "t", "d", "p1")
        svc.create("P2", "t", "d", "p1")
        assert svc.get("P1") is not None
        assert svc.get("P99") is None
        assert len(svc.list_by_status(ProposalStatus.DRAFT)) == 2
