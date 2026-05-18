"""Payment gateway integration for UPI, net banking, and card payments.

Item 27 from production roadmap.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass

from ulu.infra.logging import logger


class PaymentMethod(enum.Enum):
    UPI = "upi"
    NET_BANKING = "net_banking"
    CARD = "card"
    WALLET = "wallet"


class PaymentStatus(enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"


@dataclass
class Payment:
    """Represents a single payment transaction."""

    txn_id: str
    loan_id: str
    borrower_id: str
    amount: float
    method: PaymentMethod
    status: PaymentStatus
    gateway_ref: str
    created_at: str


class PaymentGatewayClient:
    """Stub client for payment gateway operations (Razorpay / Stripe / PayU).

    Production implementation requires merchant onboarding, webhook handling,
    and idempotency key management.
    """

    def __init__(self, gateway_name: str, base_url: str | None = None) -> None:
        self.gateway_name = gateway_name
        self.base_url = base_url or f"https://api.{gateway_name.lower()}.com"
        self._payments: dict[str, Payment] = {}

    def initiate_payment(
        self,
        loan_id: str,
        borrower_id: str,
        amount: float,
        method: PaymentMethod,
    ) -> Payment:
        """Initiates a payment and returns a pending payment object."""
        if amount <= 0:
            raise ValueError("amount must be positive")
        txn_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"
        payment = Payment(
            txn_id=txn_id,
            loan_id=loan_id,
            borrower_id=borrower_id,
            amount=amount,
            method=method,
            status=PaymentStatus.PENDING,
            gateway_ref=f"{self.gateway_name.upper()}-{uuid.uuid4().hex[:8]}",
            created_at="",
        )
        self._payments[txn_id] = payment
        logger.info(
            "payment_initiated",
            txn_id=txn_id,
            loan_id=loan_id,
            borrower_id=borrower_id,
            amount=amount,
            method=method.value,
        )
        return payment

    def get_payment(self, txn_id: str) -> Payment | None:
        """Returns payment status by transaction ID."""
        return self._payments.get(txn_id)

    def confirm_payment(self, txn_id: str) -> Payment:
        """Confirms a successful payment (webhook callback in production)."""
        payment = self._payments.get(txn_id)
        if payment is None:
            raise ValueError(f"payment not found: {txn_id}")
        payment.status = PaymentStatus.SUCCESS
        logger.info("payment_confirmed", txn_id=txn_id, amount=payment.amount)
        return payment

    def fail_payment(self, txn_id: str, reason: str = "") -> Payment:
        """Marks a payment as failed."""
        payment = self._payments.get(txn_id)
        if payment is None:
            raise ValueError(f"payment not found: {txn_id}")
        payment.status = PaymentStatus.FAILED
        logger.info("payment_failed", txn_id=txn_id, reason=reason)
        return payment

    def refund_payment(self, txn_id: str, amount: float | None = None) -> Payment:
        """Refunds a confirmed payment."""
        payment = self._payments.get(txn_id)
        if payment is None:
            raise ValueError(f"payment not found: {txn_id}")
        if payment.status != PaymentStatus.SUCCESS:
            raise ValueError(f"cannot refund payment with status {payment.status.value}")
        refund_amount = amount if amount is not None else payment.amount
        if refund_amount > payment.amount:
            raise ValueError(f"refund amount {refund_amount} exceeds payment amount {payment.amount}")
        payment.status = PaymentStatus.REFUNDED
        logger.info("payment_refunded", txn_id=txn_id, refund_amount=refund_amount)
        return payment
