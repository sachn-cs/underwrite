"""Unit tests for e-NACH integration."""

from __future__ import annotations

import pytest

from ulu.servicing.enach import EnachClient, EnachFrequency, EnachStatus


class TestEnachClient:
    def test_create_mandate(self) -> None:
        client = EnachClient()
        mandate = client.create_mandate(
            borrower_id="b1",
            bank_account_number="1234567890",
            ifsc_code="HDFC0000123",
            max_amount=5000.0,
            frequency=EnachFrequency.MONTHLY,
            start_date="2026-01-01",
            end_date="2027-01-01",
        )
        assert mandate.borrower_id == "b1"
        assert mandate.status == EnachStatus.PENDING
        assert mandate.umrn.startswith("UMRN")

    def test_get_mandate(self) -> None:
        client = EnachClient()
        created = client.create_mandate("b1", "1234567890", "HDFC0000123", 1000.0)
        fetched = client.get_mandate(created.mandate_id)
        assert fetched is not None
        assert fetched.mandate_id == created.mandate_id

    def test_present_for_debit_requires_active(self) -> None:
        client = EnachClient()
        mandate = client.create_mandate("b1", "1234567890", "HDFC0000123", 1000.0)
        with pytest.raises(ValueError, match="not active"):
            client.present_for_debit(mandate.mandate_id, 500.0)

    def test_present_for_debit_exceeds_limit(self) -> None:
        client = EnachClient()
        mandate = client.create_mandate("b1", "1234567890", "HDFC0000123", 1000.0)
        # Hack: set status to active for testing
        mandate.status = EnachStatus.ACTIVE
        with pytest.raises(ValueError, match="exceeds"):
            client.present_for_debit(mandate.mandate_id, 2000.0)

    def test_revoke_mandate(self) -> None:
        client = EnachClient()
        mandate = client.create_mandate("b1", "1234567890", "HDFC0000123", 1000.0)
        revoked = client.revoke_mandate(mandate.mandate_id)
        assert revoked.status == EnachStatus.REVOKED

    def test_revoke_unknown_rejected(self) -> None:
        client = EnachClient()
        with pytest.raises(ValueError, match="not found"):
            client.revoke_mandate("unknown")
