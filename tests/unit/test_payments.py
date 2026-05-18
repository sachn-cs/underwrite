"""Unit tests for payment gateway integration."""

from __future__ import annotations

import pytest

from ulu.servicing.payments import PaymentGatewayClient, PaymentMethod, PaymentStatus


class TestPaymentGatewayClient:
    def test_initiate_payment(self) -> None:
        client = PaymentGatewayClient("razorpay")
        payment = client.initiate_payment("loan-1", "b1", 500.0, PaymentMethod.UPI)
        assert payment.loan_id == "loan-1"
        assert payment.amount == 500.0
        assert payment.status == PaymentStatus.PENDING
        assert payment.gateway_ref.startswith("RAZORPAY")

    def test_negative_amount_rejected(self) -> None:
        client = PaymentGatewayClient("stripe")
        with pytest.raises(ValueError, match="positive"):
            client.initiate_payment("loan-1", "b1", -10.0, PaymentMethod.CARD)

    def test_confirm_payment(self) -> None:
        client = PaymentGatewayClient("payu")
        payment = client.initiate_payment("loan-1", "b1", 1000.0, PaymentMethod.NET_BANKING)
        confirmed = client.confirm_payment(payment.txn_id)
        assert confirmed.status == PaymentStatus.SUCCESS

    def test_fail_payment(self) -> None:
        client = PaymentGatewayClient("razorpay")
        payment = client.initiate_payment("loan-1", "b1", 500.0, PaymentMethod.UPI)
        failed = client.fail_payment(payment.txn_id, reason="insufficient_funds")
        assert failed.status == PaymentStatus.FAILED

    def test_refund_payment(self) -> None:
        client = PaymentGatewayClient("stripe")
        payment = client.initiate_payment("loan-1", "b1", 1000.0, PaymentMethod.CARD)
        client.confirm_payment(payment.txn_id)
        refunded = client.refund_payment(payment.txn_id, amount=500.0)
        assert refunded.status == PaymentStatus.REFUNDED

    def test_refund_unconfirmed_rejected(self) -> None:
        client = PaymentGatewayClient("razorpay")
        payment = client.initiate_payment("loan-1", "b1", 500.0, PaymentMethod.UPI)
        with pytest.raises(ValueError, match="cannot refund"):
            client.refund_payment(payment.txn_id)

    def test_refund_exceeds_amount_rejected(self) -> None:
        client = PaymentGatewayClient("payu")
        payment = client.initiate_payment("loan-1", "b1", 500.0, PaymentMethod.WALLET)
        client.confirm_payment(payment.txn_id)
        with pytest.raises(ValueError, match="exceeds"):
            client.refund_payment(payment.txn_id, amount=600.0)
