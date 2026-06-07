"""Shared fixtures for the underwrite test suite."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from underwrite.__bus__ import LocalBus
from underwrite.__events__ import Event, EventType
from underwrite.__store__ import MemoryStore


@pytest.fixture
def event() -> Event:
    """Return a minimal domain event for testing."""
    return Event(
        event_type=EventType.LOAN_ORIGINATED,
        source="test",
        source_key="test",
        payload={
            "borrower": "alice",
            "principal": 10000.0,
            "term": 12.0
        },
        correlation_id="test-correlation",
    )


@pytest.fixture
def store() -> MemoryStore:
    """Return a fresh MemoryStore instance."""
    return MemoryStore()


@pytest.fixture
def bus() -> LocalBus:
    """Return a fresh LocalBus instance."""
    return LocalBus()


@pytest.fixture
def tmp_config(tmp_path: Path) -> dict[str, Any]:
    """Return a dummy config file path + data for Configuration tests."""
    data = {
        "bus": {
            "rate_limit": 100.0,
            "max_workers": 4,
        },
    }
    p = tmp_path / "config.json"
    p.write_text(__import__("json").dumps(data))
    return {"path": str(p), "data": data}
