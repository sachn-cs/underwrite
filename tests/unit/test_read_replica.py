"""Tests for read replica session routing.

Item 9 from production roadmap.
"""

from __future__ import annotations

import pytest

from ulu.infra.db import _get_engine, _get_read_engine


class TestReadReplica:
    @pytest.mark.asyncio
    async def test_read_engine_fallback_to_primary(self, monkeypatch) -> None:
        monkeypatch.setattr("ulu.infra.db.settings.database_url", "sqlite+aiosqlite:///:memory:")
        primary = _get_engine()
        read = _get_read_engine()
        assert str(read.url) == str(primary.url)
