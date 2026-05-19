"""Integration tests for batch insert operations.

Item 116 from production roadmap.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from ulu.infra.models import AuditEvent
from ulu.infra.repositories import AuditEventRepository


class TestBatchInserts:
    @pytest.mark.asyncio
    async def test_audit_event_bulk_create(self, async_session) -> None:
        repo = AuditEventRepository(async_session)
        events = [
            AuditEvent(seq=index, event_type="test_event", payload={"n": index})
            for index in range(100)
        ]
        created = await repo.bulk_create(events)
        assert len(created) == 100
        for index, event in enumerate(created):
            assert event.seq == index
            assert event.event_type == "test_event"

    @pytest.mark.asyncio
    async def test_audit_event_bulk_create_commits(self, async_session) -> None:
        repo = AuditEventRepository(async_session)
        events = [
            AuditEvent(seq=index, event_type="commit_test", payload={})
            for index in range(10)
        ]
        await repo.bulk_create(events)
        result = await async_session.execute(
            select(AuditEvent).where(AuditEvent.event_type == "commit_test")
        )
        assert len(result.scalars().all()) == 10
