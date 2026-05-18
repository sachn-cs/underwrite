"""Unit tests for grace period and penalty calculations."""

from __future__ import annotations

import datetime

from ulu.servicing.penalties import PenaltyService


class TestPenaltyService:
    def test_no_penalty_when_paid_on_time(self) -> None:
        svc = PenaltyService(grace_period_days=3, penalty_rate_per_day=0.005)
        due = datetime.date(2026, 1, 10)
        penalty, overdue = svc.calculate_penalty(1000.0, due, due)
        assert penalty == 0.0
        assert overdue == 0

    def test_no_penalty_within_grace_period(self) -> None:
        svc = PenaltyService(grace_period_days=3, penalty_rate_per_day=0.005)
        due = datetime.date(2026, 1, 10)
        paid = datetime.date(2026, 1, 12)
        penalty, overdue = svc.calculate_penalty(1000.0, due, paid)
        assert penalty == 0.0
        assert overdue == 2

    def test_penalty_after_grace_period(self) -> None:
        svc = PenaltyService(grace_period_days=3, penalty_rate_per_day=0.005)
        due = datetime.date(2026, 1, 10)
        paid = datetime.date(2026, 1, 15)
        penalty, overdue = svc.calculate_penalty(1000.0, due, paid)
        assert overdue == 5
        assert penalty == 1000.0 * 0.005 * 2  # 2 chargeable days

    def test_is_within_grace_period(self) -> None:
        svc = PenaltyService(grace_period_days=3)
        due = datetime.date(2026, 1, 10)
        assert svc.is_within_grace_period(due, datetime.date(2026, 1, 13)) is True
        assert svc.is_within_grace_period(due, datetime.date(2026, 1, 14)) is False
