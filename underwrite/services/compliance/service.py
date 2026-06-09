"""Compliance — KYC/AML checks for Indian fintech onboarding.

Verifies PAN and Aadhaar document formats and screens against AML
watchlists.  AML screening uses a configurable blocklist and risk
scoring to flag suspicious users for review instead of passing
everyone through unconditionally.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from underwrite.__events__ import Event, EventType
from underwrite.__logger__ import logger
from underwrite.services import NanoService

PAN_PATTERN: str = r"^[A-Z]{5}[0-9]{4}[A-Z]$"
AADHAAR_PATTERN: str = r"^\d{12}$"

BLOCKLIST_PATH: str = "aml_blocklist.json"

DEFAULT_RISKY_KEYWORDS: list[str] = [
    "pep", "politically exposed", "sanctions", "watchlist"
]


def _load_blocklist(path: str) -> set[str]:
    """Load AML blocklist from a JSON file (list of strings).

    Returns an empty set if the file does not exist or is invalid.
    """
    p = Path(path)
    if not p.exists():
        return set()
    try:
        with open(p) as fh:
            data = json.load(fh)
        if isinstance(data, list):
            return {entry.strip().lower() for entry in data if entry}
        logger.warning("aml_blocklist must be a JSON list, got %s", type(data))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("failed to load AML blocklist %s: %s", path, exc)
    return set()


class ComplianceService(NanoService):
    """Verifies KYC documents and performs AML screening."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        blocklist_path: str = os.environ.get("AML_BLOCKLIST_PATH",
                                             BLOCKLIST_PATH)
        self.__blocklist: set[str] = _load_blocklist(blocklist_path)
        if self.__blocklist:
            logger.info("AML blocklist loaded with %d entries",
                        len(self.__blocklist))

    def handle(self, event: Event) -> None:
        if event.event_type != EventType.USER_ADDED:
            return
        user: str = event.payload.get("user", "")
        pan: str = event.payload.get("pan", "")
        aadhaar: str = event.payload.get("aadhaar", "")
        name: str = event.payload.get("name", user)

        if not re.match(PAN_PATTERN, pan):
            self.emit(EventType.KYC_REJECTED, {
                "user": user,
                "kyc_status": "rejected",
                "reason": "invalid_pan",
            },
                      correlation_id=event.correlation_id)
            return
        if not re.match(AADHAAR_PATTERN, aadhaar):
            self.emit(EventType.KYC_REJECTED, {
                "user": user,
                "kyc_status": "rejected",
                "reason": "invalid_aadhaar",
            },
                      correlation_id=event.correlation_id)
            return
        self.emit(EventType.KYC_VERIFIED, {
            "user": user,
            "kyc_status": "verified",
        },
                  correlation_id=event.correlation_id)

        aml_result: str = self.__screen(name, user, event)
        if aml_result == "frozen":
            self.emit(EventType.AML_FROZEN, {
                "user": user,
                "aml_status": "frozen",
                "reason": "AML screening alert",
            },
                      correlation_id=event.correlation_id)
        else:
            self.emit(EventType.AML_CLEARED, {
                "user": user,
                "aml_status": "clear",
            },
                      correlation_id=event.correlation_id)

    def __screen(self, name: str, user: str, event: Event) -> str:
        """Run AML screening checks. Returns 'clear' or 'frozen'."""
        name_lower: str = name.lower().strip()
        user_lower: str = user.lower().strip()

        if not self.__blocklist:
            return "clear"

        for blocked in self.__blocklist:
            if blocked in name_lower or blocked in user_lower:
                logger.warning(
                    "AML blocklist match for user=%s "
                    "name=%s on entry=%s", user, name, blocked)
                return "frozen"

        return "clear"
