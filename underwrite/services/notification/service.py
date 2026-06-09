"""Notification service — dispatches alerts via configurable channels."""

from __future__ import annotations

import concurrent.futures
import os
from typing import Any

from underwrite.__events__ import Event, EventType
from underwrite.__logger__ import logger
from underwrite.services import NanoService


class NotificationService(NanoService):
    """Sends notifications for fraud alerts, NPA events, and early warnings.

    Dispatches via configurable channels (SES/SendGrid for email,
    Twilio/SNS for SMS) in a background thread pool to avoid
    blocking event dispatch.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.__executor: concurrent.futures.ThreadPoolExecutor | None = (
            concurrent.futures.ThreadPoolExecutor(max_workers=4))

    def stop(self) -> None:
        if self.__executor is not None:
            self.__executor.shutdown(wait=False)
            self.__executor = None
        super().stop()

    def handle(self, event: Event) -> None:
        notify_types = {
            EventType.FRAUD_ALERT,
            EventType.WASH_FLAG,
            EventType.VELOCITY_FLAG,
            EventType.RISK_EARLY_WARNING,
            EventType.NPA_BUCKET_CHANGED,
            EventType.DLG_TRIGGERED,
        }
        if event.event_type not in notify_types:
            return

        assert self.__executor is not None
        self.__executor.submit(self.__dispatch_notification, event)
        self.emit(
            EventType.NOTIFICATION_SENT,
            {
                "original_event": event.event_type,
                "payload": dict(event.payload),
            },
            correlation_id=event.correlation_id,
        )

    def __dispatch_notification(self, event: Event) -> None:
        try:
            payload = event.payload
            recipient = payload.get("borrower") or payload.get("user") or ""
            event_type = event.event_type

            log_data = f"event={event_type} recipient={recipient}"

            email_enabled = os.environ.get("NOTIFICATION_EMAIL_ENABLED",
                                           "false").lower() == "true"
            sms_enabled = os.environ.get("NOTIFICATION_SMS_ENABLED",
                                         "false").lower() == "true"

            if email_enabled:
                self.__send_email(recipient, event_type, payload)
            if sms_enabled:
                self.__send_sms(recipient, event_type, payload)

            if not email_enabled and not sms_enabled:
                logger.info("notification dispatched (log-only): %s", log_data)
            else:
                logger.info("notification dispatched: %s", log_data)
        except Exception:
            logger.exception("failed to dispatch notification for %s",
                             event.event_id)

    def __send_email(self, recipient: str, event_type: str,
                     payload: dict[str, Any]) -> None:
        """Send an email notification.  Uses SES/SendGrid when configured."""
        ses_region = os.environ.get("AWS_REGION", "")
        sender = os.environ.get("NOTIFICATION_EMAIL_SENDER",
                                "noreply@underwrite.local")
        if ses_region:
            try:
                import boto3

                client = boto3.client("ses", region_name=ses_region)
                client.send_email(
                    Source=sender,
                    Destination={"ToAddresses": [recipient]},
                    Message={
                        "Subject": {
                            "Data": f"Underwrite Alert: {event_type}"
                        },
                        "Body": {
                            "Text": {
                                "Data": str(payload)
                            }
                        },
                    },
                )
            except Exception:
                logger.exception("SES email failed for %s", recipient)
        else:
            logger.info("email to %s: [%s] %s", recipient, event_type, payload)

    def __send_sms(self, recipient: str, event_type: str,
                   payload: dict[str, Any]) -> None:
        """Send an SMS notification.  Uses Twilio/SNS when configured."""
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        from_number = os.environ.get("TWILIO_FROM_NUMBER", "")
        if account_sid and auth_token and from_number:
            try:
                try:
                    from twilio.rest import Client
                except ImportError:
                    logger.warning(
                        "twilio not installed; install underwrite[notify] "
                        "or pip install twilio")
                    return
                client = Client(account_sid, auth_token)
                client.messages.create(
                    body=f"Underwrite Alert ({event_type}): {payload}",
                    from_=from_number,
                    to=recipient,
                )
            except Exception:
                logger.exception("Twilio SMS failed for %s", recipient)
        else:
            logger.info("SMS to %s: [%s] %s", recipient, event_type, payload)
