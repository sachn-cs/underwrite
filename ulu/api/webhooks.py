"""Webhook dispatcher for async event notifications.

Item 64 from production roadmap: notify external systems of loan
origination, default, repayment events.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
from dataclasses import dataclass
from typing import Any

from ulu.domain.events import DomainEvent
from ulu.infra.logging import logger


@dataclass
class WebhookConfig:
    """Configuration for a webhook subscriber."""

    url: str
    secret: str | None = None
    events: list[str] | None = None  # None = all events


class WebhookDispatcher:
    """Dispatches domain events to configured webhook endpoints.

    Uses asyncio for non-blocking delivery. In production, replace
    in-memory queue with Celery/Redis task queue.
    """

    def __init__(self) -> None:
        self.subscribers: list[WebhookConfig] = []

    def subscribe(self, config: WebhookConfig) -> None:
        """Registers a new webhook subscriber."""
        self.subscribers.append(config)
        logger.info("webhook_subscribed", url=config.url, events=config.events)

    def unsubscribe(self, url: str) -> None:
        """Removes a webhook subscriber by URL."""
        self.subscribers = [s for s in self.subscribers if s.url != url]
        logger.info("webhook_unsubscribed", url=url)

    def _should_dispatch(self, config: WebhookConfig, event: DomainEvent) -> bool:
        if config.events is None:
            return True
        return event.event_type in config.events

    def _sign_payload(self, payload: str, secret: str) -> str:
        return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

    async def _send(self, config: WebhookConfig, payload: dict[str, Any]) -> None:
        """Sends webhook payload (stub; production uses httpx/aiohttp)."""
        import json

        body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        headers = {"Content-Type": "application/json"}
        if config.secret:
            headers["X-Webhook-Signature"] = self._sign_payload(body, config.secret)

        logger.info("webhook_dispatch", url=config.url, event_type=payload.get("event_type"))

        try:
            await asyncio.sleep(0)  # yield control to event loop
        except Exception as exc:
            logger.error("webhook_dispatch_failed", url=config.url, error=str(exc))

    async def dispatch(self, event: DomainEvent) -> None:
        """Dispatches event to all matching subscribers concurrently."""
        payload = {
            "event_type": event.event_type,
            "payload": event.payload,
        }
        tasks = [
            self._send(sub, payload)
            for sub in self.subscribers
            if self._should_dispatch(sub, event)
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def dispatch_sync(self, event: DomainEvent) -> None:
        """Synchronous wrapper for dispatch (use in non-async contexts)."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.dispatch(event))
        except RuntimeError:
            asyncio.run(self.dispatch(event))
