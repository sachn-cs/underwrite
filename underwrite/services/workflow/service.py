"""Workflow orchestration service.

Coordinates multi-step business processes by tracking state machines.
Each workflow instance progresses through stages and emits
``workflow.started`` / ``workflow.completed`` events.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from underwrite.__events__ import Event, EventType
from underwrite.services.base import StatefulService

STAGES: dict[str, list[str]] = {
    "origination": [
        "created", "kyc_pending", "risk_review", "underwriting", "approved",
        "disbursed"
    ],
    "recovery":
    ["started", "contact_made", "negotiation", "settlement", "closed"],
    "default": [
        "noticed", "npa_classified", "collateral_review", "recovery",
        "chargeoff"
    ],
}


class WorkflowService(StatefulService):
    """Manages business process state machines for origination, recovery, etc."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._handlers: dict[str, Any] = {
            EventType.WORKFLOW_START: self.__on_workflow_start,
            EventType.WORKFLOW_ADVANCE: self.__on_workflow_advance,
            EventType.ORIGINATION_SUBMITTED: self.__on_origination_submitted,
            EventType.UNDERWRITER_APPROVED: self.__on_underwriter_approved,
        }

    def handle(self, event: Event) -> None:
        handler = self._handlers.get(event.event_type)
        if handler is not None:
            handler(event)

    def __on_workflow_start(self, event: Event) -> None:
        self.__start_workflow(
            event.payload.get("type", ""),
            event.payload.get("entity_id", ""),
            event.correlation_id,
        )

    def __on_workflow_advance(self, event: Event) -> None:
        self.__advance_workflow(
            event.payload.get("entity_id", ""),
            event.correlation_id,
        )

    def __on_origination_submitted(self, event: Event) -> None:
        entity_id = event.payload.get("application_id", "")
        if entity_id and not self.store.get(f"workflow:{entity_id}"):
            self.__start_workflow("origination", entity_id,
                                  event.correlation_id)

    def __on_underwriter_approved(self, event: Event) -> None:
        entity_id = event.payload.get("application_id", "")
        if entity_id:
            self.__advance_workflow(entity_id, event.correlation_id)

    def __start_workflow(self,
                         workflow_type: str,
                         entity_id: str,
                         correlation_id: str = "") -> None:
        if not workflow_type or not entity_id:
            return
        stages = STAGES.get(workflow_type, ["started"])
        self.store.set(
            f"workflow:{entity_id}",
            {
                "type": workflow_type,
                "entity_id": entity_id,
                "current_stage": stages[0],
                "stages": stages,
                "stage_index": 0,
                "status": "active",
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self.emit(
            EventType.WORKFLOW_STARTED,
            {
                "workflow_type": workflow_type,
                "entity_id": entity_id,
                "stage": stages[0],
            },
            correlation_id=correlation_id,
        )

    def __advance_workflow(self,
                           entity_id: str,
                           correlation_id: str = "") -> None:
        if not entity_id:
            return
        with self.state_lock:
            record = self.store.get(f"workflow:{entity_id}")
            if not record or record.get("status") != "active":
                return
            next_idx: int = record["stage_index"] + 1
            if next_idx >= len(record["stages"]):
                record["status"] = "completed"
                record["completed_at"] = datetime.now(timezone.utc).isoformat()
                self.store.set(f"workflow:{entity_id}", record)
            else:
                record["stage_index"] = next_idx
                record["current_stage"] = record["stages"][next_idx]
                self.store.set(f"workflow:{entity_id}", record)
        if record["status"] == "completed":
            self.emit(
                EventType.WORKFLOW_COMPLETED,
                {
                    "workflow_type": record["type"],
                    "entity_id": entity_id,
                },
                correlation_id=correlation_id,
            )
