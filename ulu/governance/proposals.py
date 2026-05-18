"""Governance proposal lifecycle management.

Item 53 from production roadmap.
"""

from __future__ import annotations

import dataclasses
import datetime
import enum

from ulu.infra.logging import logger


class ProposalStatus(enum.Enum):
    DRAFT = "draft"
    VOTING = "voting"
    EXECUTED = "executed"
    REJECTED = "rejected"
    TIMELOCKED = "timelocked"


@dataclasses.dataclass
class Proposal:
    """A single governance proposal with lifecycle state."""

    proposal_id: str
    title: str
    description: str
    proposer_id: str
    status: ProposalStatus
    created_at: datetime.datetime
    voting_start: datetime.datetime | None = None
    voting_end: datetime.datetime | None = None
    execution_time: datetime.datetime | None = None
    parameter_changes: dict[str, object] = dataclasses.field(default_factory=dict)


class ProposalLifecycleService:
    """Manages proposal state transitions and time-locked execution."""

    def __init__(self, voting_duration_hours: float = 72.0, timelock_hours: float = 24.0) -> None:
        self.voting_duration = datetime.timedelta(hours=voting_duration_hours)
        self.timelock = datetime.timedelta(hours=timelock_hours)
        self._proposals: dict[str, Proposal] = {}

    def create(
        self,
        proposal_id: str,
        title: str,
        description: str,
        proposer_id: str,
        parameter_changes: dict[str, object] | None = None,
    ) -> Proposal:
        if proposal_id in self._proposals:
            raise ValueError(f"proposal already exists: {proposal_id}")
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        proposal = Proposal(
            proposal_id=proposal_id,
            title=title,
            description=description,
            proposer_id=proposer_id,
            status=ProposalStatus.DRAFT,
            created_at=now,
            parameter_changes=parameter_changes or {},
        )
        self._proposals[proposal_id] = proposal
        logger.info("proposal_created", proposal_id=proposal_id, proposer_id=proposer_id)
        return proposal

    def start_voting(self, proposal_id: str) -> Proposal:
        proposal = self._get(proposal_id)
        if proposal.status != ProposalStatus.DRAFT:
            raise ValueError("only draft proposals can start voting")
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        proposal.status = ProposalStatus.VOTING
        proposal.voting_start = now
        proposal.voting_end = now + self.voting_duration
        logger.info("proposal_voting_started", proposal_id=proposal_id, voting_end=proposal.voting_end.isoformat())
        return proposal

    def finalize(self, proposal_id: str, passed: bool) -> Proposal:
        proposal = self._get(proposal_id)
        if proposal.status != ProposalStatus.VOTING:
            raise ValueError("only voting proposals can be finalized")
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        if proposal.voting_end and now < proposal.voting_end:
            raise ValueError("voting period has not ended")
        if passed:
            proposal.status = ProposalStatus.TIMELOCKED
            proposal.execution_time = now + self.timelock
            logger.info(
                "proposal_timelocked",
                proposal_id=proposal_id,
                execution_time=proposal.execution_time.isoformat(),
            )
        else:
            proposal.status = ProposalStatus.REJECTED
            logger.info("proposal_rejected", proposal_id=proposal_id)
        return proposal

    def execute(self, proposal_id: str) -> Proposal:
        proposal = self._get(proposal_id)
        if proposal.status != ProposalStatus.TIMELOCKED:
            raise ValueError("only timelocked proposals can be executed")
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        if proposal.execution_time and now < proposal.execution_time:
            raise ValueError("timelock has not expired")
        proposal.status = ProposalStatus.EXECUTED
        logger.info("proposal_executed", proposal_id=proposal_id)
        return proposal

    def get(self, proposal_id: str) -> Proposal | None:
        return self._proposals.get(proposal_id)

    def list_by_status(self, status: ProposalStatus) -> list[Proposal]:
        return [p for p in self._proposals.values() if p.status == status]

    def _get(self, proposal_id: str) -> Proposal:
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"proposal not found: {proposal_id}")
        return proposal
