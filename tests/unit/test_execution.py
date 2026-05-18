"""Unit tests for on-chain parameter update execution."""

from __future__ import annotations

import json

import pytest

from ulu.governance.execution import ParameterUpdateExecutor
from ulu.governance.parameters import ProtocolParameters


class FakeClient:
    """Fake AlgorandClient capturing app call arguments."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def submit_app_call(
        self,
        sender: str,
        private_key: str,
        app_id: int,
        args: list[bytes],
        on_complete: int = 0,
    ) -> str:
        self.calls.append(
            {
                "sender": sender,
                "private_key": private_key,
                "app_id": app_id,
                "args": args,
                "on_complete": on_complete,
            }
        )
        return "FAKE_TXID_123"


class TestParameterUpdateExecutor:
    @pytest.mark.asyncio
    async def test_execute_app_call(self) -> None:
        fake = FakeClient()
        executor = ParameterUpdateExecutor(fake)
        params = ProtocolParameters(max_delegation_rate=0.15, rate_cap=0.6)
        txid = await executor.execute(
            params=params,
            sender="SENDER_ADDR",
            private_key="PRIVATE_KEY",
            app_id=42,
        )
        assert txid == "FAKE_TXID_123"
        assert len(fake.calls) == 1
        call = fake.calls[0]
        assert call["app_id"] == 42
        assert call["sender"] == "SENDER_ADDR"
        assert call["args"][0] == b"update"
        payload = json.loads(call["args"][1].decode("utf-8"))
        assert payload["max_delegation_rate"] == 0.15
        assert payload["rate_cap"] == 0.6
