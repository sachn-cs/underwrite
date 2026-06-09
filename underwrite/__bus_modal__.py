"""Modal-backed event bus implementation.

Publishes events to a Modal distributed queue and polls for messages
in a background thread.  Requires ``modal`` (install ``underwrite[modal]``).
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


class ModalBus(EventBus):
    """Event bus backed by a Modal distributed queue."""

    def __init__(
        self,
        queue_name: str = "underwrite-bus",
        poll_interval: float = 1.0,
        store: Store | None = None,
    ) -> None:
        self.__queue_name: str = queue_name
        self.__poll_interval: float = max(0.1, poll_interval)
        self.__modal_queue: Any = None
        self.__handlers: dict[str, list[tuple[str, Callable[[Event],
                                                            None]]]] = {}
        self.__running: bool = False
        self.__poll_thread: threading.Thread | None = None
        self.__lock: threading.Lock = threading.Lock()
        self.__dlq: DeadLetterQueue = DeadLetterQueue(store=store)
        self.__idempotency: IdempotencyGuard = IdempotencyGuard()
        self.__import_modal()

    def __import_modal(self) -> None:
        try:
            import modal  # type: ignore[import-untyped]
            self.__modal = modal
            self.__modal_queue = modal.Queue(
                self.__queue_name)  # type: ignore[call-arg]
        except ImportError:
            self.__modal = None  # type: ignore[assignment]

    def publish(self, event: Event) -> str:
        if self.__modal is None:
            raise RuntimeError(
                "modal is not installed; install underwrite[modal]")
        body: str = json.dumps(event.to_dict())
        self.__modal_queue.put(body)
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
                                              name="modal-poll")
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
                raw = self.__modal_queue.get(block=False)
                while raw is not None and self.__running:
                    data: dict[str, Any] = json.loads(raw)
                    event: Event = Event.from_dict(data)
                    self.__dispatch(event)
                    raw = self.__modal_queue.get(block=False)
            except Exception:
                pass
            if self.__running:
                time.sleep(self.__poll_interval)

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
