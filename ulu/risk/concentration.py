"""Portfolio concentration limit enforcement.

Item 41 from production roadmap.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConcentrationLimit:
    """Defines a concentration limit rule."""

    dimension: str  # "borrower", "geography", "sector"
    max_exposure: float
    max_exposure_ratio: float | None = None  # as ratio of total portfolio


class ConcentrationLimitBreached(Exception):
    """Raised when a concentration limit is exceeded."""


class ConcentrationService:
    """Checks portfolio concentration limits per borrower, geography, and sector."""

    def __init__(self, limits: list[ConcentrationLimit] | None = None) -> None:
        self.limits = limits or []

    def check_borrower_limit(
        self,
        borrower_id: str,
        proposed_amount: float,
        current_exposure: float,
        total_portfolio: float,
    ) -> None:
        """Checks if adding proposed_amount would breach borrower concentration limits."""
        new_exposure = current_exposure + proposed_amount
        for limit in self.limits:
            if limit.dimension != "borrower":
                continue
            if limit.max_exposure is not None and new_exposure > limit.max_exposure:
                raise ConcentrationLimitBreached(
                    f"borrower {borrower_id} exposure {new_exposure:.2f} exceeds max {limit.max_exposure:.2f}"
                )
            if limit.max_exposure_ratio is not None and total_portfolio > 0:
                ratio = new_exposure / total_portfolio
                if ratio > limit.max_exposure_ratio:
                    raise ConcentrationLimitBreached(
                        f"borrower {borrower_id} ratio {ratio:.2%} exceeds max {limit.max_exposure_ratio:.2%}"
                    )

    def check_geography_limit(
        self,
        geography: str,
        proposed_amount: float,
        current_exposure: float,
        total_portfolio: float,
    ) -> None:
        """Checks geography concentration limits."""
        new_exposure = current_exposure + proposed_amount
        for limit in self.limits:
            if limit.dimension != "geography":
                continue
            if limit.max_exposure is not None and new_exposure > limit.max_exposure:
                raise ConcentrationLimitBreached(
                    f"geography {geography} exposure {new_exposure:.2f} exceeds max {limit.max_exposure:.2f}"
                )
            if limit.max_exposure_ratio is not None and total_portfolio > 0:
                ratio = new_exposure / total_portfolio
                if ratio > limit.max_exposure_ratio:
                    raise ConcentrationLimitBreached(
                        f"geography {geography} ratio {ratio:.2%} exceeds max {limit.max_exposure_ratio:.2%}"
                    )

    def check_sector_limit(
        self,
        sector: str,
        proposed_amount: float,
        current_exposure: float,
        total_portfolio: float,
    ) -> None:
        """Checks sector concentration limits."""
        new_exposure = current_exposure + proposed_amount
        for limit in self.limits:
            if limit.dimension != "sector":
                continue
            if limit.max_exposure is not None and new_exposure > limit.max_exposure:
                raise ConcentrationLimitBreached(
                    f"sector {sector} exposure {new_exposure:.2f} exceeds max {limit.max_exposure:.2f}"
                )
            if limit.max_exposure_ratio is not None and total_portfolio > 0:
                ratio = new_exposure / total_portfolio
                if ratio > limit.max_exposure_ratio:
                    raise ConcentrationLimitBreached(
                        f"sector {sector} ratio {ratio:.2%} exceeds max {limit.max_exposure_ratio:.2%}"
                    )
