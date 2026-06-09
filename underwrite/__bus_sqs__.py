"""SQS-backed event bus implementation.

Publishes events to an AWS SQS queue and polls for messages in a
background thread.  Requires ``boto3`` (install ``underwrite[aws]``).
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections.abc import Callable
from typing import Any

from underwrite.__bus__ import DeadLetterQueue, EventBus, IdempotencyGuard
from underwrite.__events__ import Event
from underwrite.__logger__ import logger
from underwrite.__store__ import Store


class SqsBus(EventBus):
    """Event bus backed by an SQS queue."""

    def __init__(
        self,
        queue_url: str = "",
        region: str = "",
        max_messages: int = 10,
        wait_time: int = 20,
        store: Store | None = None,
    ) -> None:
        self.__queue_url: str = queue_url
        self.__region: str = region
        self.__max_messages: int = max(1, min(max_messages, 10))
        self.__wait_time: int = max(0, min(wait_time, 20))
        self.__client: Any = None
        self.__handlers: dict[str, list[tuple[str, Callable[[Event],
                                                            None]]]] = {}
        self.__running: bool = False
        self.__poll_thread: threading.Thread | None = None
        self.__lock: threading.Lock = threading.Lock()
        self.__dlq: DeadLetterQueue = DeadLetterQueue(store=store)
        self.__idempotency: IdempotencyGuard = IdempotencyGuard()
        self.__import_boto3()

    def __import_boto3(self) -> None:
        try:
            import boto3  # type: ignore[import-untyped]
            self.__boto3 = boto3
        except ImportError:
            self.__boto3 = None

    @property
    def _client(self) -> Any:
        if self.__client is None:
            if self.__boto3 is None:
                raise RuntimeError(
                    "boto3 is not installed; install underwrite[aws]")
            kwargs: dict[str, Any] = {}
            if self.__region:
                kwargs["region_name"] = self.__region
            self.__client = self.__boto3.client("sqs", **kwargs)
        return self.__client

    def publish(self, event: Event) -> str:
        if self.__boto3 is None:
            raise RuntimeError(
                "boto3 is not installed; install underwrite[aws]")
        body: str = json.dumps(event.to_dict())
        self._client.send_message(
            QueueUrl=self.__queue_url,
            MessageBody=body,
            MessageDeduplicationId=event.event_id,
            MessageGroupId=event.event_type,
        )
        return event.event_id

    def subscribe(self, event_type: str, handler: Callable[[Event],
                                                           None]) -> str:
        sid: str = uuid.uuid4().hex
        with self.__lock:
            self.__handlers.setdefault(event_type, []).append((sid, handler))
        return sid

    def unsubscribe(self, subscription_id: str) -> None:
        with self.__lock:
            for handlers in self.__handlers.values():
                for i, (sid, _) in enumerate(handlers):
                    if sid == subscription_id:
                        handlers.pop(i)
                        return

    def start(self) -> None:
        if self.__running:
            return
        self.__running = True
        self.__poll_thread = threading.Thread(target=self.__poll_loop,
                                              daemon=True,
                                              name="sqs-poll")
        self.__poll_thread.start()

    def stop(self) -> None:
        self.__running = False
        if self.__poll_thread:
            self.__poll_thread.join(timeout=5)
            self.__poll_thread = None
        with self.__lock:
            self.__handlers.clear()

    @property
    def dlq(self) -> DeadLetterQueue:
        return self.__dlq

    @property
    def idempotency(self) -> IdempotencyGuard:
        return self.__idempotency

    def __poll_loop(self) -> None:
        while self.__running:
            try:
                resp: Any = self._client.receive_message(
                    QueueUrl=self.__queue_url,
                    MaxNumberOfMessages=self.__max_messages,
                    WaitTimeSeconds=self.__wait_time,
                )
                messages: list[Any] = resp.get("Messages", [])
                for msg in messages:
                    if not self.__running:
                        break
                    try:
                        data: dict[str, Any] = json.loads(msg["Body"])
                        event: Event = Event.from_dict(data)
                        self.__dispatch(event)
                        self._client.delete_message(
                            QueueUrl=self.__queue_url,
                            ReceiptHandle=msg["ReceiptHandle"],
                        )
                    except Exception:
                        logger.exception("failed to process SQS message %s",
                                         msg.get("MessageId", "?"))
            except Exception:
                if self.__running:
                    logger.exception("SQS poll error")
                    time.sleep(1)

    def __dispatch(self, event: Event) -> None:
        with self.__lock:
            wildcards: list[tuple[str, Callable[[Event], None]]] = \
                self.__handlers.get("*", [])
            specific: list[tuple[str, Callable[[Event], None]]] = \
                self.__handlers.get(event.event_type, [])
        for sid, handler in wildcards + specific:
            try:
                handler(event)
            except Exception as exc:
                logger.exception("handler failed for %s", event.event_type)
                self.__dlq.put(event, f"{type(exc).__name__}: {exc}", sid)
