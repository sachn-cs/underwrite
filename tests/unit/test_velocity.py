"""Unit tests for velocity check anti-fraud service."""

from __future__ import annotations

from ulu.anti_fraud.velocity import VelocityCheckService


class TestVelocityCheckService:
    def test_record_and_get(self) -> None:
        svc = VelocityCheckService()
        svc.record_origination("b1", 1000.0)
        svc.record_repayment("b1", 1000.0)
        records = svc.get_records("b1")
        assert len(records) == 2
        assert records[0].event_type == "origination"
        assert records[1].event_type == "repayment"

    def test_check_wash_lending_not_enough_records(self) -> None:
        svc = VelocityCheckService()
        flagged, score = svc.check_wash_lending("b1")
        assert flagged is False
        assert score == 0.0

    def test_check_wash_lending_detected(self) -> None:
        svc = VelocityCheckService()
        for _ in range(3):
            svc.record_origination("b1", 500.0)
            svc.record_repayment("b1", 500.0)
        flagged, score = svc.check_wash_lending("b1", window_hours=24, min_cycle_count=3)
        assert flagged is True
        assert score > 0

    def test_check_burst_pattern_under_threshold(self) -> None:
        svc = VelocityCheckService()
        svc.record_origination("b1", 1000.0)
        flagged, count = svc.check_burst_pattern("b1", max_originations=3)
        assert flagged is False
        assert count == 1

    def test_check_burst_pattern_over_threshold(self) -> None:
        svc = VelocityCheckService()
        for _ in range(5):
            svc.record_origination("b1", 1000.0)
        flagged, count = svc.check_burst_pattern("b1", max_originations=3)
        assert flagged is True
        assert count == 5

    def test_empty_borrower(self) -> None:
        svc = VelocityCheckService()
        flagged, score = svc.check_wash_lending("nobody")
        assert flagged is False
        flagged2, count = svc.check_burst_pattern("nobody")
        assert flagged2 is False
        assert svc.get_records("nobody") == []
