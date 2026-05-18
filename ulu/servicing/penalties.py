"""Grace period and late payment penalty calculations.

Item 24 from production roadmap.
"""

from __future__ import annotations

import datetime


class PenaltyService:
    """Calculates late payment penalties after grace period."""

    def __init__(self, grace_period_days: int = 3, penalty_rate_per_day: float = 0.005) -> None:
        """
        Args:
            grace_period_days: Number of days after due date before penalties apply.
            penalty_rate_per_day: Daily penalty rate as decimal (default 0.5%).
        """
        self.grace_period_days = grace_period_days
        self.penalty_rate_per_day = penalty_rate_per_day

    def calculate_penalty(
        self,
        installment_amount: float,
        due_date: datetime.date,
        payment_date: datetime.date | None = None,
    ) -> tuple[float, int]:
        """Returns (penalty_amount, overdue_days).

        Penalty is zero if paid within grace period.
        """
        if payment_date is None:
            payment_date = datetime.datetime.now(datetime.timezone.utc).date()

        if payment_date <= due_date:
            return 0.0, 0

        overdue_days = (payment_date - due_date).days
        if overdue_days <= self.grace_period_days:
            return 0.0, overdue_days

        chargeable_days = overdue_days - self.grace_period_days
        penalty = installment_amount * self.penalty_rate_per_day * chargeable_days
        return penalty, overdue_days

    def is_within_grace_period(self, due_date: datetime.date, payment_date: datetime.date | None = None) -> bool:
        """Returns True if payment is within grace period."""
        if payment_date is None:
            payment_date = datetime.datetime.now(datetime.timezone.utc).date()
        overdue_days = max(0, (payment_date - due_date).days)
        return overdue_days <= self.grace_period_days
