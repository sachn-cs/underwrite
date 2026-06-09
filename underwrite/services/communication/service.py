"""Communication dispatch service.

Sends notifications through configured channels (email, SMS, push).
In serverless mode this delegates to a cloud function.  Emits
``communication.sent`` on successful dispatch.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from underwrite.__events__ import Event, EventType
from underwrite.__logger__ import logger
from underwrite.services.base import NanoService


class CommunicationService(NanoService):
    """Dispatches outbound messages through configured channels.

    In production, each channel (email / SMS / push) is backed by a
    cloud function or third-party API.  This service logs the dispatch
    and emits ``communication.sent``.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._handlers: dict[str, Any] = {
            EventType.COMMUNICATION_SEND: self.__on_communication_send,
            EventType.STATEMENT_GENERATED: self.__on_statement_generated,
        }

    def handle(self, event: Event) -> None:
        handler = self._handlers.get(event.event_type)
        if handler is not None:
            handler(event)

    def __on_communication_send(self, event: Event) -> None:
        recipient: str = event.payload.get("recipient", "")
        subject: str = event.payload.get("subject", "")
        channel: str = event.payload.get("channel", "email")
        if not recipient:
            logger.warning("dropping COMMUNICATION_SEND with missing recipient")
            return
        message_id: str = f"msg_{recipient}_{int(datetime.now(timezone.utc).timestamp())}"
        msg = {
            "recipient": recipient,
            "subject": subject,
            "channel": channel,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
        self.store.set(f"message:{message_id}", msg)
        self.emit(
            EventType.COMMUNICATION_SENT,
            {
                "message_id": message_id,
                "recipient": recipient,
                "channel": channel,
                "subject": subject,
            },
            correlation_id=event.correlation_id,
        )

    def __on_statement_generated(self, event: Event) -> None:
        loan_id = event.payload.get("loan_id", "")
        if loan_id:
            stmt_key = f"comm_stmt:{loan_id}:{datetime.now(timezone.utc).isoformat()}"
            stmt_notification = {
                "loan_id": loan_id,
                "notified": True,
            }
            self.store.set(stmt_key, stmt_notification)
