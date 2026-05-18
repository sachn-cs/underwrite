"""On-chain parameter update execution via Algorand application calls.

Item 52 from production roadmap.
"""

from __future__ import annotations

import json

from ulu.blockchain.client import AlgorandClient
from ulu.governance.parameters import ProtocolParameters
from ulu.infra.logging import logger


class ParameterUpdateExecutor:
    """Submits winning governance parameter updates to the Algorand blockchain."""

    def __init__(self, client: AlgorandClient) -> None:
        self.client = client

    async def execute(
        self,
        params: ProtocolParameters,
        sender: str,
        private_key: str,
        app_id: int,
    ) -> str:
        """Serializes parameters and submits an app call to the governance contract.

        Returns the transaction ID.
        """
        payload = json.dumps(params.to_dict(), separators=(",", ":"))
        args = [b"update", payload.encode("utf-8")]
        txid = await self.client.submit_app_call(
            sender=sender,
            private_key=private_key,
            app_id=app_id,
            args=args,
        )
        logger.info("parameter_update_executed", txid=txid, app_id=app_id, payload=payload)
        return txid
