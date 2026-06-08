"""Shared fixtures for the underwrite test suite."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from underwrite.__bus__ import LocalBus
from underwrite.__events__ import Event, EventType
from underwrite.__store__ import MemoryStore, Store

# -- Domain event fixture ------------------------------------------------------


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


# -- Store fixtures ------------------------------------------------------------


@pytest.fixture
def store() -> MemoryStore:
    """Return a fresh MemoryStore instance."""
    return MemoryStore()


@pytest.fixture(scope="session")
def postgres_dsn() -> str:
    """Return a Postgres DSN from env or start a testcontainer."""
    dsn = os.environ.get("UNDERWRITE_TEST_PG_DSN", "")
    if dsn:
        return dsn
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers not installed")
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg.get_connection_url()


@pytest.fixture
def pg_store(postgres_dsn: str) -> Generator[Store, None, None]:
    """Return a PostgresStore backed by a temporary table.

    Requires the ``postgres`` extra and ``testcontainers``.
    """
    import uuid

    from underwrite.__store__ import PostgresStore

    table = f"test_store_{uuid.uuid4().hex[:12]}"
    store = PostgresStore(dsn=postgres_dsn, table=table)
    store.migrate(_empty_plan())
    yield store
    try:
        pool = store._get_pool()
        conn = pool.getconn()
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()
        pool.putconn(conn)
    except Exception:
        pass


def _empty_plan() -> Any:
    from underwrite.__migrate__ import MigrationPlan

    return MigrationPlan(migrations=[])


# -- Bus fixture ---------------------------------------------------------------


@pytest.fixture
def bus() -> LocalBus:
    """Return a fresh LocalBus instance."""
    return LocalBus()


# -- Config fixture ------------------------------------------------------------


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


# -- HTTP test client fixture --------------------------------------------------


@pytest.fixture
def client() -> Any:
    """Return a test HTTP client using the serve module.

    Requires the ``serve`` extra.
    """
    try:
        from underwrite.__serve__ import create_app
    except ImportError:
        pytest.skip("serve extra not installed")
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi not installed")
    app = create_app()
    return TestClient(app)


# -- Failure mock fixtures -----------------------------------------------------


class FailAfterCountStore(MemoryStore):
    """Memory store that fails after N operations.  Useful for error-path tests."""

    def __init__(self, fail_after: int = 1) -> None:
        super().__init__()
        self.__fail_after = fail_after
        self.__ops = 0

    def _maybe_fail(self) -> None:
        self.__ops += 1
        if self.__ops > self.__fail_after:
            msg = "simulated store failure"
            raise RuntimeError(msg)

    def get(self, key: str) -> Any | None:
        self._maybe_fail()
        return super().get(key)

    def set(self, key: str, value: Any) -> None:
        self._maybe_fail()
        super().set(key, value)

    def delete(self, key: str) -> bool:
        self._maybe_fail()
        return super().delete(key)

    def exists(self, key: str) -> bool:
        self._maybe_fail()
        return super().exists(key)


@pytest.fixture
def fail_store() -> FailAfterCountStore:
    """Return a MemoryStore that fails after 1 operation."""
    return FailAfterCountStore(fail_after=1)


@pytest.fixture
def injecting_bus() -> LocalBus:
    """Return a LocalBus whose first publish always raises.

    Useful for testing emit/compensation error paths.
    """

    class InjectingBus(LocalBus):

        def publish(self, event: Event) -> None:
            msg = "injected publish failure"
            raise RuntimeError(msg)

    return InjectingBus()
