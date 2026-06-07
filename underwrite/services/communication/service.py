"""Communication dispatch service.

Sends notifications through configured channels (email, SMS, push).
In serverless mode this delegates to a cloud function.  Emits
``communication.sent`` on successful dispatch.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from underwrite.__events__ import Event, EventType
from underwrite.services.base import NanoService

logger = logging.getLogger(__name__)


class CommunicationService(NanoService):
    """Dispatches outbound messages through configured channels.

    In production, each channel (email / SMS / push) is backed by a
    cloud function or third-party API.  This service logs the dispatch
    and emits ``communication.sent``.
    """

    def handle(self, event: Event) -> None:
        if event.event_type == EventType.COMMUNICATION_SEND:
            recipient: str = event.payload.get("recipient", "")
            subject: str = event.payload.get("subject", "")
            channel: str = event.payload.get("channel", "email")
            if not recipient:
                logger.warning(
                    "dropping COMMUNICATION_SEND with missing recipient")
                return
            message_id: str = f"msg_{recipient}_{int(datetime.now(timezone.utc).timestamp())}"
            msg = {
                "recipient": recipient,
                "subject": subject,
                "channel": channel,
                "sent_at": datetime.now(timezone.utc).isoformat(),
            }
            self.store.set(f"message:{message_id}", msg)
            self.emit(EventType.COMMUNICATION_SENT, {
                "message_id": message_id,
                "recipient": recipient,
                "channel": channel,
                "subject": subject,
            },
                      correlation_id=event.correlation_id)

        elif event.event_type == EventType.DOCUMENT_GENERATED:
            loan_id: str = event.payload.get("loan_id", "")
            doc_type: str = event.payload.get("type", "")
            if not loan_id or not doc_type:
                logger.warning(
                    "dropping DOCUMENT_GENERATED with missing loan_id or type")
                return
            doc_notification = {
                "loan_id": loan_id,
                "type": doc_type,
                "notified": True,
                "notified_at": datetime.now(timezone.utc).isoformat(),
            }
            self.store.set(f"comm_doc:{loan_id}:{doc_type}", doc_notification)

        elif event.event_type == EventType.STATEMENT_GENERATED:
            loan_id = event.payload.get("loan_id", "")
            if loan_id:
                stmt_key = f"comm_stmt:{loan_id}:{datetime.now(timezone.utc).isoformat()}"
                stmt_notification = {
                    "loan_id": loan_id,
                    "notified": True,
                }
                self.store.set(stmt_key, stmt_notification)
