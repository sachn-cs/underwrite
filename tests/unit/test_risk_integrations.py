"""Unit tests for risk integration stubs."""

from __future__ import annotations

import pytest

from ulu.risk.integrations import AccountAggregatorClient, CreditBureauClient


class TestAccountAggregatorClient:
    def test_init_defaults(self) -> None:
        client = AccountAggregatorClient()
        assert client.base_url == "https://api.sahamati.org.in"

    @pytest.mark.asyncio
    async def test_fetch_cash_flow_not_implemented(self) -> None:
        client = AccountAggregatorClient()
        with pytest.raises(NotImplementedError):
            await client.fetch_cash_flow("consent-123", "fip-456")

    def test_health(self) -> None:
        client = AccountAggregatorClient()
        assert client.health()["status"] == "unknown"


class TestCreditBureauClient:
    def test_init_defaults(self) -> None:
        client = CreditBureauClient("CIBIL")
        assert client.bureau_name == "CIBIL"

    @pytest.mark.asyncio
    async def test_fetch_credit_report_not_implemented(self) -> None:
        client = CreditBureauClient("CIBIL")
        with pytest.raises(NotImplementedError):
            await client.fetch_credit_report("ABCDE1234F", "9999999999")

    def test_health(self) -> None:
        client = CreditBureauClient("Experian")
        assert client.health()["bureau"] == "Experian"
