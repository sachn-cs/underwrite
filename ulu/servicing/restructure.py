"""RBI-mandated loan restructuring workflows."""

from __future__ import annotations

from ulu.domain.events import RestructureEvent
from ulu.domain.loans import LoanStatus, RestructureType


class RestructureService:
    """Manages moratorium, tenor extension, and rate reduction per RBI norms."""

    def restructure(
        self,
        loan_id: str,
        borrower_id: str,
        outstanding_principal: float,
        remaining_term: float,
        accrued_interest: float,
        restructure_type: RestructureType,
        extension_months: int = 0,
        rate_reduction: float = 0.0,
        moratorium_months: int = 0,
    ) -> tuple[float, float, int, LoanStatus, RestructureEvent]:
        """Restructures a loan and returns updated parameters plus event.

        Args:
            loan_id: Unique loan identifier.
            borrower_id: Borrower identifier.
            outstanding_principal: Current outstanding principal.
            remaining_term: Remaining term in months.
            accrued_interest: Accrued but unpaid interest.
            restructure_type: Type of restructuring.
            extension_months: Months to extend tenor (for TENOR_EXTENSION).
            rate_reduction: New reduced rate as decimal (for RATE_REDUCTION).
            moratorium_months: Payment holiday months (for MORATORIUM).

        Returns:
            Tuple of (new_principal, new_term, moratorium_months, new_status, event).

        Raises:
            ValueError: If inputs are invalid.
        """
        if outstanding_principal <= 0:
            raise ValueError("outstanding_principal must be positive")
        if remaining_term <= 0:
            raise ValueError("remaining_term must be positive")
        if accrued_interest < 0:
            raise ValueError("accrued_interest must be non-negative")
        if extension_months < 0:
            raise ValueError("extension_months must be non-negative")
        if rate_reduction < 0:
            raise ValueError("rate_reduction must be non-negative")
        if moratorium_months < 0:
            raise ValueError("moratorium_months must be non-negative")

        new_principal = outstanding_principal + accrued_interest
        new_term = remaining_term
        status = LoanStatus.RESTRUCTURED

        if restructure_type == RestructureType.MORATORIUM:
            if moratorium_months == 0:
                raise ValueError("moratorium_months must be > 0 for moratorium")
            new_term = remaining_term + moratorium_months

        elif restructure_type == RestructureType.TENOR_EXTENSION:
            if extension_months == 0:
                raise ValueError("extension_months must be > 0 for tenor extension")
            new_term = remaining_term + extension_months

        elif restructure_type == RestructureType.RATE_REDUCTION:
            if rate_reduction <= 0:
                raise ValueError("rate_reduction must be > 0 for rate reduction")

        event = RestructureEvent(
            event_type="restructure",
            payload={
                "loan_id": loan_id,
                "borrower_id": borrower_id,
                "restructure_type": restructure_type.value,
                "original_term": remaining_term,
                "new_term": new_term,
                "original_principal": outstanding_principal,
                "new_principal": new_principal,
                "moratorium_months": moratorium_months,
            },
            loan_id=loan_id,
            borrower_id=borrower_id,
            restructure_type=restructure_type.value,
            original_term=remaining_term,
            new_term=new_term,
            original_principal=outstanding_principal,
            new_principal=new_principal,
            moratorium_months=moratorium_months,
        )
        return new_principal, new_term, moratorium_months, status, event
