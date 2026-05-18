"""e-NACH / e-Mandate integration for auto-debit EMI repayments via NPCI.

Item 19 from production roadmap.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass

from ulu.infra.logging import logger


class EnachStatus(enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    REVOKED = "revoked"
    FAILED = "failed"


class EnachFrequency(enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    AS_PRESENTED = "as_presented"


@dataclass
class Mandate:
    """Represents an NPCI e-NACH mandate registration."""

    mandate_id: str
    borrower_id: str
    bank_account_number: str
    ifsc_code: str
    umrn: str  # Unique Mandate Reference Number
    max_amount: float
    frequency: EnachFrequency
    start_date: str
    end_date: str
    status: EnachStatus


class EnachClient:
    """Stub client for NPCI e-NACH/e-Mandate operations.

    Production implementation requires integration with an NPCI sponsor bank
    and a payment aggregator (e.g., Razorpay, PayU, BillDesk) for mandate
    creation, amendment, and revocation.
    """

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or "https://api.npci.org.in/enach"
        self._mandates: dict[str, Mandate] = {}

    def create_mandate(
        self,
        borrower_id: str,
        bank_account_number: str,
        ifsc_code: str,
        max_amount: float,
        frequency: EnachFrequency = EnachFrequency.AS_PRESENTED,
        start_date: str = "",
        end_date: str = "",
    ) -> Mandate:
        """Registers a new e-NACH mandate.

        In production this would redirect the borrower to their bank's
        net-banking portal for electronic authentication.
        """
        mandate_id = f"MAN-{uuid.uuid4().hex[:12].upper()}"
        umrn = f"UMRN{uuid.uuid4().hex[:10].upper()}"
        mandate = Mandate(
            mandate_id=mandate_id,
            borrower_id=borrower_id,
            bank_account_number=bank_account_number,
            ifsc_code=ifsc_code,
            umrn=umrn,
            max_amount=max_amount,
            frequency=frequency,
            start_date=start_date,
            end_date=end_date,
            status=EnachStatus.PENDING,
        )
        self._mandates[mandate_id] = mandate
        logger.info(
            "enach_mandate_created",
            mandate_id=mandate_id,
            borrower_id=borrower_id,
            umrn=umrn,
        )
        return mandate

    def get_mandate(self, mandate_id: str) -> Mandate | None:
        """Returns an existing mandate by ID."""
        return self._mandates.get(mandate_id)

    def present_for_debit(self, mandate_id: str, amount: float, narration: str = "EMI") -> dict:
        """Presents a debit instruction against an active mandate.

        In production this would be sent to the sponsor bank for processing
        via the NPCI ACH network.
        """
        mandate = self._mandates.get(mandate_id)
        if mandate is None:
            raise ValueError(f"mandate not found: {mandate_id}")
        if mandate.status != EnachStatus.ACTIVE:
            raise ValueError(f"mandate {mandate_id} is not active")
        if amount > mandate.max_amount:
            raise ValueError(f"amount {amount} exceeds mandate limit {mandate.max_amount}")

        import uuid

        txn_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"
        logger.info(
            "enach_debit_presented",
            mandate_id=mandate_id,
            txn_id=txn_id,
            amount=amount,
            narration=narration,
        )
        return {
            "txn_id": txn_id,
            "mandate_id": mandate_id,
            "amount": amount,
            "status": "presented",
            "narration": narration,
        }

    def revoke_mandate(self, mandate_id: str) -> Mandate:
        """Revokes an existing mandate."""
        mandate = self._mandates.get(mandate_id)
        if mandate is None:
            raise ValueError(f"mandate not found: {mandate_id}")
        mandate.status = EnachStatus.REVOKED
        logger.info("enach_mandate_revoked", mandate_id=mandate_id)
        return mandate
