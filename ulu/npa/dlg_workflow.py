"""End-to-end DLG invocation workflow connecting NPA aging with RBI compliance.

Items 32 and 33 from production roadmap.
"""

from __future__ import annotations

from dataclasses import dataclass

from ulu.compliance.rbi_dlg import RbiDlgCompliance
from ulu.domain.events import DlgInvocationEvent
from ulu.infra.logging import logger
from ulu.npa.scheduler import NpaScheduler
from ulu.npa.triggers import DlgTriggerService


@dataclass
class DlgWorkflowResult:
    """Outcome of a DLG invocation workflow."""

    loan_id: str
    days_overdue: int
    logical_loss: float
    physical_recovery: float
    bank_absorption: float
    invoked: bool
    event: DlgInvocationEvent | None = None


class DlgInvocationWorkflow:
    """Orchestrates DLG invocation from NPA evaluation to physical settlement."""

    def __init__(
        self,
        scheduler: NpaScheduler | None = None,
        trigger_service: DlgTriggerService | None = None,
        compliance: RbiDlgCompliance | None = None,
    ) -> None:
        self.scheduler = scheduler if scheduler is not None else NpaScheduler()
        self.trigger_service = trigger_service if trigger_service is not None else DlgTriggerService()
        self.compliance = compliance if compliance is not None else RbiDlgCompliance(dlg_cap_ratio=0.05)

    def evaluate_and_invoke(
        self,
        loan_id: str,
        days_overdue: int,
        already_invoked: bool,
        portfolio_outstanding: float,
        logical_loss: float,
    ) -> DlgWorkflowResult:
        """Evaluates NPA status and triggers DLG if conditions are met.

        Args:
            loan_id: Unique loan identifier.
            days_overdue: Current days overdue.
            already_invoked: Whether DLG was already invoked for this loan.
            portfolio_outstanding: Total outstanding principal of the portfolio.
            logical_loss: Full logical loss from the default event.

        Returns:
            DlgWorkflowResult with physical recovery capped to 5% DLG limit.
        """
        new_days, bucket, dlg_trigger = self.scheduler.evaluate(days_overdue)

        if not dlg_trigger or already_invoked:
            return DlgWorkflowResult(
                loan_id=loan_id,
                days_overdue=new_days,
                logical_loss=logical_loss,
                physical_recovery=0.0,
                bank_absorption=logical_loss,
                invoked=False,
            )

        if not self.trigger_service.should_invoke(new_days, already_invoked):
            return DlgWorkflowResult(
                loan_id=loan_id,
                days_overdue=new_days,
                logical_loss=logical_loss,
                physical_recovery=0.0,
                bank_absorption=logical_loss,
                invoked=False,
            )

        physical = self.compliance.compute_physical_recovery(logical_loss, portfolio_outstanding)
        absorption = self.compliance.remaining_bank_absorption(logical_loss, portfolio_outstanding)
        event = self.trigger_service.invoke(loan_id, physical)

        logger.warning(
            "dlg_invoked",
            loan_id=loan_id,
            days_overdue=new_days,
            logical_loss=logical_loss,
            physical_recovery=physical,
            bank_absorption=absorption,
        )

        return DlgWorkflowResult(
            loan_id=loan_id,
            days_overdue=new_days,
            logical_loss=logical_loss,
            physical_recovery=physical,
            bank_absorption=absorption,
            invoked=True,
            event=event,
        )

    def can_originate(self, portfolio_outstanding: float, dlg_pool_balance: float) -> bool:
        """Returns True if DLG pool meets regulatory minimum for new originations."""
        return self.compliance.can_originate(portfolio_outstanding, dlg_pool_balance)
