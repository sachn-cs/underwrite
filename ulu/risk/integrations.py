"""External integration stubs for Account Aggregator and credit bureaus.

Items 37 and 38 from production roadmap.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from ulu.infra.circuit_breaker import bureau_breaker
from ulu.infra.logging import logger


@dataclass
class AaCashFlowData:
    """Cash flow data returned by Account Aggregator (Sahamati)."""

    account_id: str
    monthly_inflow: float
    monthly_outflow: float
    average_balance: float
    num_bounce_events: int
    data_timestamp: str


@dataclass
class BureauCreditReport:
    """Credit report returned by Indian credit bureaus (CIBIL/Experian)."""

    bureau_id: str
    credit_score: int
    total_outstanding: float
    num_active_accounts: int
    num_delinquent_accounts: int
    report_date: str


class AccountAggregatorClient:
    """Stub client for Sahamati Account Aggregator network.

    Production implementation should handle consent management,
    FI data fetching, and decryption per RBI AA regulations.
    """

    def __init__(self, base_url: str | None = None, timeout: float = 30.0) -> None:
        self.base_url = base_url or "https://api.sahamati.org.in"
        self.timeout = timeout

    async def fetch_cash_flow(
        self,
        consent_handle: str,
        fip_id: str,
    ) -> AaCashFlowData:
        """Fetches anonymized cash flow data via AA consent."""
        logger.info("aa_fetch_started", consent_handle=consent_handle, fip_id=fip_id)
        await asyncio.sleep(0)  # stub
        raise NotImplementedError(
            "Account Aggregator integration requires consent flow implementation. "
            "See https://sahamati.org.in for API specifications."
        )

    def health(self) -> dict[str, Any]:
        """Returns AA gateway health status."""
        return {"status": "unknown", "gateway": self.base_url}


class CreditBureauClient:
    """Stub client for Indian credit bureau integrations (CIBIL, Experian, CRIF).

    Production implementation requires NBFC registration, API credentials,
    and XML/JSON report parsing.
    """

    def __init__(self, bureau_name: str, base_url: str | None = None, timeout: float = 30.0) -> None:
        self.bureau_name = bureau_name
        self.base_url = base_url or f"https://api.{bureau_name.lower()}.co.in"
        self.timeout = timeout

    def _fetch_stub(self, pan: str, phone: str) -> BureauCreditReport:
        """Blocking stub for bureau report fetching."""
        logger.info("bureau_fetch_started", bureau=self.bureau_name, pan=pan[:4] + "****")
        raise NotImplementedError(
            f"{self.bureau_name} bureau integration requires NBFC registration and API credentials. "
            "Contact the bureau for sandbox access."
        )

    async def fetch_credit_report(self, pan: str, phone: str) -> BureauCreditReport:
        """Fetches credit report with circuit breaker and timeout."""
        loop = asyncio.get_event_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(None, bureau_breaker(self._fetch_stub), pan, phone),
            timeout=self.timeout,
        )

    def health(self) -> dict[str, Any]:
        """Returns bureau gateway health status."""
        return {"status": "unknown", "bureau": self.bureau_name, "gateway": self.base_url}
