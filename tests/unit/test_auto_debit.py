"""Unit tests for EMI auto-debit scheduler."""

from __future__ import annotations

from ulu.domain.loans import Installment
from ulu.servicing.auto_debit import EmiScheduler


class TestEmiScheduler:
    def test_overdue_installments_empty(self) -> None:
        schedule = [Installment(1, 100.0, 10.0, 110.0)]
        scheduler = EmiScheduler("l1", schedule)
        scheduler.record_attempt(1, 110.0, "success")
        assert scheduler.overdue_installments() == []

    def test_can_retry(self) -> None:
        schedule = [Installment(1, 100.0, 10.0, 110.0)]
        scheduler = EmiScheduler("l1", schedule)
        assert scheduler.can_retry(1) is True
        for _ in range(3):
            scheduler.record_attempt(1, 110.0, "failed", reason="nsf")
        assert scheduler.can_retry(1) is False

    def test_retry_count(self) -> None:
        schedule = [Installment(1, 100.0, 10.0, 110.0)]
        scheduler = EmiScheduler("l1", schedule)
        assert scheduler._retry_count(1) == 0
        scheduler.record_attempt(1, 110.0, "failed")
        assert scheduler._retry_count(1) == 1

    def test_next_retry_date(self) -> None:
        schedule = [Installment(1, 100.0, 10.0, 110.0)]
        scheduler = EmiScheduler("l1", schedule)
        next_date = scheduler.next_retry_date(1)
        assert next_date is not None
        for _ in range(3):
            scheduler.record_attempt(1, 110.0, "failed")
        assert scheduler.next_retry_date(1) is None

    def test_create_debit_instruction(self) -> None:
        schedule = [Installment(1, 100.0, 10.0, 110.0)]
        scheduler = EmiScheduler("l1", schedule)
        inst = scheduler.create_debit_instruction(schedule[0])
        assert inst["loan_id"] == "l1"
        assert inst["installment_seq"] == 1
        assert inst["total_due"] == 110.0

    def test_run_daily_evaluation_skips_exhausted(self) -> None:
        schedule = [Installment(1, 100.0, 10.0, 110.0)]
        scheduler = EmiScheduler("l1", schedule)
        for _ in range(3):
            scheduler.record_attempt(1, 110.0, "failed")
        instructions = scheduler.run_daily_evaluation()
        assert instructions == []
