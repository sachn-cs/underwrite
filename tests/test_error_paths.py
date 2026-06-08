"""Error-path tests for narrowed exception blocks — graceful degradation checks."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from underwrite.__bus__ import EventBus, LocalBus
from underwrite.__config__ import Configuration
from underwrite.__events__ import Event
from underwrite.__exceptions__ import ProtocolError
from underwrite.__runtime__ import Runtime
from underwrite.__store__ import CQRSStore, MemoryStore, PostgresStore, Store
from underwrite.services.audit.service import AuditService
from underwrite.services.base import NanoService
from underwrite.services.mechanism.service import MechanismService
from underwrite.services.risk.model import RiskModel

# ---------------------------------------------------------------------------
# Concrete NanoService subclass for tests
# ---------------------------------------------------------------------------


class _ConcreteService(NanoService):
    """Minimal concrete NanoService for testing base-class error paths."""

    def handle(self, event: Event) -> None:
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _BrokenStore:
    """A store stub that raises on every get/set."""

    def get(self, key: str) -> None:
        raise OSError(f"mock io error for {key}")

    def set(self, key: str, value: object) -> None:
        raise OSError(f"mock io error for {key}")


class _RaisingStrategy:
    """A risk strategy that always raises."""

    @staticmethod
    def predict(principal: float, term: float) -> float:
        msg = "model failure"
        raise RuntimeError(msg)


class _BadStr:
    """An object whose __str__ raises, forcing json.dumps to fail."""

    def __str__(self) -> str:
        raise ValueError("bad str")


# ---------------------------------------------------------------------------
# 1) NanoService.safe_store_get returns default on store error
# ---------------------------------------------------------------------------


class TestSafeStoreGet:

    def test_returns_default_on_exception(self) -> None:
        svc = _ConcreteService(service_id="test_svc_get")
        svc._NanoService__store = _BrokenStore()  # type: ignore[attr-defined]
        result = svc.safe_store_get("some_key", default="fallback")
        assert result == "fallback"

    def test_returns_store_result_for_missing_key(self) -> None:
        svc = _ConcreteService(service_id="test_svc_get_missing")
        svc._NanoService__store = MemoryStore()  # type: ignore[attr-defined]
        result = svc.safe_store_get("missing", default=42)
        assert result is None


# ---------------------------------------------------------------------------
# 2) NanoService.safe_store_set returns False on store error
# ---------------------------------------------------------------------------


class TestSafeStoreSet:

    def test_returns_false_on_exception(self) -> None:
        svc = _ConcreteService(service_id="test_svc_set")
        svc._NanoService__store = _BrokenStore()  # type: ignore[attr-defined]
        result = svc.safe_store_set("some_key", "value")
        assert result is False


# ---------------------------------------------------------------------------
# 3) RiskModel.predict falls back to heuristic on strategy failure
# ---------------------------------------------------------------------------


class TestRiskModelPredictFallback:

    def test_falls_back_on_strategy_exception(self) -> None:
        model = RiskModel()
        model._RiskModel__strategy = _RaisingStrategy(
        )  # type: ignore[attr-defined]
        score = model.predict(10000.0, 12.0)
        assert 0.0 <= score <= 1.0

    def test_falls_back_for_extreme_input(self) -> None:
        model = RiskModel()
        model._RiskModel__strategy = _RaisingStrategy(
        )  # type: ignore[attr-defined]
        score = model.predict(float("nan"), 12.0)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# 4) Bus dispatch sends event to DLQ on handler failure
# ---------------------------------------------------------------------------


class TestBusSyncDispatchDLQ:

    def test_handler_failure_sends_to_dlq(self) -> None:
        bus: EventBus = LocalBus()
        bus.subscribe("test.event", lambda e:
                      (_ for _ in ()).throw(ValueError("fail")))
        bus.start()
        event = Event(event_type="test.event", source="test", payload={})
        bus.publish(event)
        assert bus.dlq.count > 0

    def test_dlq_contains_event_after_handler_failure(self) -> None:
        bus: EventBus = LocalBus()
        bus.subscribe("test.event3", lambda e:
                      (_ for _ in ()).throw(ValueError("fail")))
        bus.start()
        event = Event(event_type="test.event3", source="test", payload={})
        bus.publish(event)
        assert bus.dlq.count > 0


# ---------------------------------------------------------------------------
# 5) Config loading skips bad / non-existent file gracefully
# ---------------------------------------------------------------------------


class TestConfigSkipBadFile:

    def test_returns_default_on_nonexistent_path(self) -> None:
        config = Configuration.load(path="/nonexistent/config.json")
        assert isinstance(config, Configuration)

    def test_returns_default_on_malformed_json(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad_config.json"
        bad_file.write_text("{invalid json")
        config = Configuration.load(path=str(bad_file))
        assert isinstance(config, Configuration)


# ---------------------------------------------------------------------------
# 6) Event rejects non-serializable payload (bad __str__ → ValueError)
# ---------------------------------------------------------------------------


class TestEventNonSerializablePayload:

    def test_raises_protocol_error_on_bad_payload(self) -> None:
        with pytest.raises(ProtocolError, match="MAX_PAYLOAD_SIZE"):
            Event(
                event_type="test.bad",
                source="test",
                payload={"bad": _BadStr()},
            )


# ---------------------------------------------------------------------------
# 7) Runtime.__build_authz returns None on bad policy file content
# ---------------------------------------------------------------------------


class TestAuthzBuildFallback:

    def test_returns_none_on_malformed_policy_file(self,
                                                   tmp_path: Path) -> None:
        bad_policy = tmp_path / "policy.json"
        bad_policy.write_text("{bad json")
        config_data = {
            "authz": {
                "enabled": True,
                "policy_file": str(bad_policy),
            },
        }
        rt = Runtime(config=Configuration(**config_data))
        result = rt._Runtime__build_authz()  # type: ignore[attr-defined]
        assert result is None

    def test_returns_none_on_missing_policy_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent" / "policy.json"
        config_data = {
            "authz": {
                "enabled": True,
                "policy_file": str(missing),
            },
        }
        rt = Runtime(config=Configuration(**config_data))
        result = rt._Runtime__build_authz()  # type: ignore[attr-defined]
        assert result is not None


# ---------------------------------------------------------------------------
# 8) PostgresStore.health returns {"ok": False} on error
# ---------------------------------------------------------------------------


class TestPostgresStoreHealthFallback:

    def test_returns_ok_false_on_query_failure(self) -> None:
        store = PostgresStore(dsn="", table="test")
        store._PostgresStore__execute = MagicMock(  # type: ignore[attr-defined]
            side_effect=RuntimeError("db down"))
        result = store.health()
        assert result["ok"] is False
        assert "detail" in result


# ---------------------------------------------------------------------------
# 9) CQRSStore.health uses fallback on write store error
# ---------------------------------------------------------------------------


class TestCQRSStoreHealthFallback:

    def test_uses_fallback_on_write_store_exception(self) -> None:
        read_store = MemoryStore()
        write_store = MagicMock(spec=Store)
        write_store.health.side_effect = RuntimeError("write store down")
        store = CQRSStore(read_store=read_store, write_store=write_store)
        result = store.health()
        assert result["ok"] is False
        assert result["write_store"]["ok"] is False


# ---------------------------------------------------------------------------
# 10) MechanismService ProtocolError emits rejection event
# ---------------------------------------------------------------------------


class TestMechanismRejection:

    def test_repay_unknown_user_emits_rejected(self) -> None:
        bus: EventBus = LocalBus()
        bus.start()
        svc = MechanismService(service_id="mechanism", bus=bus)
        emitted: list[Event] = []

        def capture(e: Event) -> None:
            emitted.append(e)

        bus.subscribe("mechanism.rejected", capture)
        event = Event(
            event_type="mechanism",
            source="test",
            payload={
                "command": "repay",
                "user": "nobody",
                "amount": 100.0
            },
        )
        svc.handle(event)
        assert len(emitted) >= 1


# ---------------------------------------------------------------------------
# 11) AuditService.load_jsonl skips corrupted lines
# ---------------------------------------------------------------------------


class TestAuditLoadJsonl:

    def test_skips_corrupted_line(self, tmp_path: Path) -> None:
        ledger_file = tmp_path / "audit.jsonl"
        ledger_file.write_text(
            '{"valid": true}\nnot json\n{"also_valid": 42}\n')
        svc = AuditService(service_id="audit")
        svc.load_jsonl(str(ledger_file))
        records = svc._AuditService__ledger  # type: ignore[attr-defined]
        assert len(records) == 2
        assert records[0] == {"valid": True}
        assert records[1] == {"also_valid": 42}

    def test_handles_empty_file(self, tmp_path: Path) -> None:
        ledger_file = tmp_path / "empty.jsonl"
        ledger_file.write_text("")
        svc = AuditService(service_id="audit")
        svc.load_jsonl(str(ledger_file))
        records = svc._AuditService__ledger  # type: ignore[attr-defined]
        assert len(records) == 0

    def test_handles_missing_file(self) -> None:
        svc = AuditService(service_id="audit")
        svc.load_jsonl("/nonexistent/audit.jsonl")
        records = svc._AuditService__ledger  # type: ignore[attr-defined]
        assert len(records) == 0


# ---------------------------------------------------------------------------
# 12) RiskModel.load_strategy falls back to JSON on joblib ImportError
# ---------------------------------------------------------------------------


class TestLoadStrategyFallback:

    def test_load_strategy_uses_json(self, tmp_path: Path) -> None:
        model_file = tmp_path / "model.json"
        params = {"weights": [0.3, 0.7], "bias": 0.1}
        model_file.write_text(json.dumps(params))
        strategy = RiskModel.load_strategy(str(model_file))
        assert strategy is not None
        score = strategy.predict(10000.0, 12.0)
        assert 0.0 <= score <= 1.0

    def test_load_strategy_raises_on_bad_json(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json")
        with pytest.raises(ValueError):
            RiskModel.load_strategy(str(bad_file))

    def test_load_strategy_raises_on_missing_file(self) -> None:
        with pytest.raises(ValueError):
            RiskModel.load_strategy("/nonexistent/model.joblib")
