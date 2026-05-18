"""EMI auto-debit scheduling with retry logic.

Item 21 from production roadmap: cron-based EMI deduction on due dates
with 3 retry attempts.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from ulu.domain.loans import Installment
from ulu.infra.logging import logger


@dataclass
class DebitAttempt:
    """Records a single auto-debit attempt."""

    installment_seq: int
    amount: float
    attempted_at: datetime.datetime
    status: str  # "success", "failed", "pending"
    failure_reason: str | None = None


class EmiScheduler:
    """Schedules and tracks EMI auto-debit attempts for a loan.

    Does not perform actual bank transfers; generates debit instructions
    for downstream NPCI e-NACH or payment-gateway processors.
    """

    MAX_RETRIES = 3
    RETRY_DELAYS_DAYS = [1, 3, 5]

    def __init__(self, loan_id: str, schedule: list[Installment]) -> None:
        self.loan_id = loan_id
        self.schedule = schedule
        self.attempts: list[DebitAttempt] = []

    def _today(self) -> datetime.date:
        return datetime.datetime.now(datetime.timezone.utc).date()

    def overdue_installments(self) -> list[Installment]:
        """Returns installments whose due date has passed and are unpaid."""
        today = self._today()
        paid_seqs = {a.installment_seq for a in self.attempts if a.status == "success"}
        return [
            inst
            for inst in self.schedule
            if inst.sequence not in paid_seqs and self._due_date(inst.sequence) <= today
        ]

    def _due_date(self, seq: int) -> datetime.date:
        """Computes due date as origination + seq months (naive)."""
        return self._today()  # stub: real implementation needs loan origination date

    def create_debit_instruction(self, installment: Installment) -> dict[str, str | float | int]:
        """Returns a debit instruction payload for the given installment."""
        return {
            "loan_id": self.loan_id,
            "installment_seq": installment.sequence,
            "principal_due": installment.principal_due,
            "interest_due": installment.interest_due,
            "total_due": installment.total_due,
            "retry_count": self._retry_count(installment.sequence),
        }

    def _retry_count(self, seq: int) -> int:
        return sum(1 for a in self.attempts if a.installment_seq == seq)

    def can_retry(self, seq: int) -> bool:
        """Returns True if the installment has not exceeded max retries."""
        return self._retry_count(seq) < self.MAX_RETRIES

    def record_attempt(self, seq: int, amount: float, status: str, reason: str | None = None) -> None:
        """Records a debit attempt outcome."""
        attempt = DebitAttempt(
            installment_seq=seq,
            amount=amount,
            attempted_at=datetime.datetime.now(datetime.timezone.utc),
            status=status,
            failure_reason=reason,
        )
        self.attempts.append(attempt)
        logger.info(
            "emi_debit_attempt",
            loan_id=self.loan_id,
            seq=seq,
            status=status,
            amount=amount,
            reason=reason,
        )

    def next_retry_date(self, seq: int) -> datetime.date | None:
        """Returns the next retry date based on attempt count, or None if exhausted."""
        count = self._retry_count(seq)
        if count >= self.MAX_RETRIES:
            return None
        delta = datetime.timedelta(days=self.RETRY_DELAYS_DAYS[count])
        return self._today() + delta

    def run_daily_evaluation(self) -> list[dict[str, str | float | int]]:
        """Evaluates all installments and returns debit instructions for today.

        Returns:
            List of debit instruction payloads that should be processed today.
        """
        instructions: list[dict[str, str | float | int]] = []
        for inst in self.overdue_installments():
            if self.can_retry(inst.sequence):
                instructions.append(self.create_debit_instruction(inst))
            else:
                logger.warning(
                    "emi_retries_exhausted",
                    loan_id=self.loan_id,
                    seq=inst.sequence,
                    max_retries=self.MAX_RETRIES,
                )
        return instructions
