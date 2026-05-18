"""Unit tests for webhook dispatcher."""

from __future__ import annotations

import pytest

from ulu.api.webhooks import WebhookConfig, WebhookDispatcher
from ulu.domain.events import LoanOriginatedEvent, RepaymentEvent


class TestWebhookDispatcher:
    def test_subscribe_and_unsubscribe(self) -> None:
        d = WebhookDispatcher()
        cfg = WebhookConfig(url="https://example.com/hook", events=["loan_originated"])
        d.subscribe(cfg)
        assert len(d.subscribers) == 1
        d.unsubscribe("https://example.com/hook")
        assert len(d.subscribers) == 0

    def test_should_dispatch_all_events_when_none_specified(self) -> None:
        d = WebhookDispatcher()
        cfg = WebhookConfig(url="https://example.com/hook")
        event = LoanOriginatedEvent(
            event_type="loan_originated", payload={}, loan_id="l1", borrower_id="b1", principal=100.0, term=1.0
        )
        assert d._should_dispatch(cfg, event) is True

    def test_should_dispatch_filtered_events(self) -> None:
        d = WebhookDispatcher()
        cfg = WebhookConfig(url="https://example.com/hook", events=["repayment"])
        orig = LoanOriginatedEvent(
            event_type="loan_originated", payload={}, loan_id="l1", borrower_id="b1", principal=100.0, term=1.0
        )
        repay = RepaymentEvent(event_type="repayment", payload={}, loan_id="l1", amount=10.0, delta_earned=10.0)
        assert d._should_dispatch(cfg, orig) is False
        assert d._should_dispatch(cfg, repay) is True

    def test_sign_payload(self) -> None:
        d = WebhookDispatcher()
        sig = d._sign_payload('{"a":1}', "secret")
        assert len(sig) == 64

    @pytest.mark.asyncio
    async def test_dispatch_no_subscribers(self) -> None:
        d = WebhookDispatcher()
        event = LoanOriginatedEvent(
            event_type="loan_originated", payload={}, loan_id="l1", borrower_id="b1", principal=100.0, term=1.0
        )
        await d.dispatch(event)  # should not raise

    def test_dispatch_sync(self) -> None:
        d = WebhookDispatcher()
        cfg = WebhookConfig(url="https://example.com/hook")
        d.subscribe(cfg)
        event = LoanOriginatedEvent(
            event_type="loan_originated", payload={}, loan_id="l1", borrower_id="b1", principal=100.0, term=1.0
        )
        d.dispatch_sync(event)  # should not raise
