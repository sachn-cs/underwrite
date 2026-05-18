"""Unit tests for portfolio concentration limits."""

from __future__ import annotations

import pytest

from ulu.risk.concentration import ConcentrationLimit, ConcentrationLimitBreached, ConcentrationService


class TestConcentrationService:
    def test_borrower_limit_ok(self) -> None:
        svc = ConcentrationService([ConcentrationLimit("borrower", max_exposure=5000.0)])
        svc.check_borrower_limit("b1", 1000.0, 3000.0, 10000.0)

    def test_borrower_limit_breached(self) -> None:
        svc = ConcentrationService([ConcentrationLimit("borrower", max_exposure=5000.0)])
        with pytest.raises(ConcentrationLimitBreached):
            svc.check_borrower_limit("b1", 3000.0, 3000.0, 10000.0)

    def test_borrower_ratio_breached(self) -> None:
        svc = ConcentrationService([ConcentrationLimit("borrower", max_exposure=99999.0, max_exposure_ratio=0.3)])
        with pytest.raises(ConcentrationLimitBreached):
            svc.check_borrower_limit("b1", 1000.0, 2500.0, 10000.0)

    def test_geography_limit_breached(self) -> None:
        svc = ConcentrationService([ConcentrationLimit("geography", max_exposure=1000.0)])
        with pytest.raises(ConcentrationLimitBreached):
            svc.check_geography_limit("MH", 500.0, 600.0, 10000.0)

    def test_sector_limit_breached(self) -> None:
        svc = ConcentrationService([ConcentrationLimit("sector", max_exposure=2000.0)])
        with pytest.raises(ConcentrationLimitBreached):
            svc.check_sector_limit("retail", 500.0, 1600.0, 10000.0)
