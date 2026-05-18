"""Unit tests for loan restructuring workflows."""

from __future__ import annotations

import pytest

from ulu.domain.loans import LoanStatus, RestructureType
from ulu.servicing.restructure import RestructureService


class TestRestructureService:
    def test_moratorium(self) -> None:
        svc = RestructureService()
        new_principal, new_term, moratorium, status, event = svc.restructure(
            loan_id="l1",
            borrower_id="b1",
            outstanding_principal=1000.0,
            remaining_term=12,
            accrued_interest=50.0,
            restructure_type=RestructureType.MORATORIUM,
            moratorium_months=3,
        )
        assert new_principal == 1050.0
        assert new_term == 15
        assert moratorium == 3
        assert status == LoanStatus.RESTRUCTURED
        assert event.restructure_type == "moratorium"

    def test_tenor_extension(self) -> None:
        svc = RestructureService()
        new_principal, new_term, moratorium, status, event = svc.restructure(
            loan_id="l1",
            borrower_id="b1",
            outstanding_principal=5000.0,
            remaining_term=24,
            accrued_interest=200.0,
            restructure_type=RestructureType.TENOR_EXTENSION,
            extension_months=6,
        )
        assert new_principal == 5200.0
        assert new_term == 30
        assert status == LoanStatus.RESTRUCTURED

    def test_rate_reduction(self) -> None:
        svc = RestructureService()
        new_principal, new_term, moratorium, status, event = svc.restructure(
            loan_id="l1",
            borrower_id="b1",
            outstanding_principal=10000.0,
            remaining_term=18,
            accrued_interest=0.0,
            restructure_type=RestructureType.RATE_REDUCTION,
            rate_reduction=0.02,
        )
        assert new_principal == 10000.0
        assert new_term == 18
        assert status == LoanStatus.RESTRUCTURED

    def test_invalid_principal_rejected(self) -> None:
        svc = RestructureService()
        with pytest.raises(ValueError, match="positive"):
            svc.restructure(
                loan_id="l1",
                borrower_id="b1",
                outstanding_principal=0.0,
                remaining_term=12,
                accrued_interest=0.0,
                restructure_type=RestructureType.MORATORIUM,
                moratorium_months=3,
            )

    def test_invalid_term_rejected(self) -> None:
        svc = RestructureService()
        with pytest.raises(ValueError, match="positive"):
            svc.restructure(
                loan_id="l1",
                borrower_id="b1",
                outstanding_principal=1000.0,
                remaining_term=0.0,
                accrued_interest=0.0,
                restructure_type=RestructureType.TENOR_EXTENSION,
                extension_months=6,
            )

    def test_zero_moratorium_rejected(self) -> None:
        svc = RestructureService()
        with pytest.raises(ValueError, match="moratorium_months"):
            svc.restructure(
                loan_id="l1",
                borrower_id="b1",
                outstanding_principal=1000.0,
                remaining_term=12,
                accrued_interest=0.0,
                restructure_type=RestructureType.MORATORIUM,
                moratorium_months=0,
            )

    def test_zero_extension_rejected(self) -> None:
        svc = RestructureService()
        with pytest.raises(ValueError, match="extension_months"):
            svc.restructure(
                loan_id="l1",
                borrower_id="b1",
                outstanding_principal=1000.0,
                remaining_term=12,
                accrued_interest=0.0,
                restructure_type=RestructureType.TENOR_EXTENSION,
                extension_months=0,
            )

    def test_zero_rate_reduction_rejected(self) -> None:
        svc = RestructureService()
        with pytest.raises(ValueError, match="rate_reduction"):
            svc.restructure(
                loan_id="l1",
                borrower_id="b1",
                outstanding_principal=1000.0,
                remaining_term=12,
                accrued_interest=0.0,
                restructure_type=RestructureType.RATE_REDUCTION,
                rate_reduction=0.0,
            )

    def test_negative_interest_rejected(self) -> None:
        svc = RestructureService()
        with pytest.raises(ValueError, match="non-negative"):
            svc.restructure(
                loan_id="l1",
                borrower_id="b1",
                outstanding_principal=1000.0,
                remaining_term=12,
                accrued_interest=-10.0,
                restructure_type=RestructureType.MORATORIUM,
                moratorium_months=3,
            )
