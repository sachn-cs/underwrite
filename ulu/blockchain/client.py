"""Async Algorand client wrapper with retry and connection pooling."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from algosdk.error import AlgodHTTPError
from algosdk.v2client.algod import AlgodClient


class BlockchainConnectionError(Exception):
    """Raised when the Algorand node is unreachable or returns an error."""


class AlgorandClient:
    """Lightweight async wrapper around AlgodClient for settlement anchoring."""

    def __init__(self, algod_url: str, algod_token: str) -> None:
        self.algod_url = algod_url
        self.algod_token = algod_token
        self.client = AlgodClient(self.algod_token, self.algod_url)

    def _call_with_retry(
        self,
        fn: Any,
        retries: int = 3,
        backoff: float = 1.0,
    ) -> Any:
        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                return fn()
            except (ConnectionError, TimeoutError) as exc:
                last_exc = exc
                if attempt < retries - 1:
                    time.sleep(backoff * (2 ** attempt))
        raise BlockchainConnectionError(f"Algorand node unreachable after {retries} attempts: {last_exc}") from last_exc

    async def health(self) -> dict:
        """Returns node status for health checks."""
        try:
            return await asyncio.to_thread(
                self._call_with_retry, self.client.status
            )
        except AlgodHTTPError as exc:
            raise BlockchainConnectionError(f"Algorand node returned error: {exc}") from exc

    async def suggested_params(self) -> dict:
        """Returns suggested transaction parameters."""
        try:
            return await asyncio.to_thread(
                self._call_with_retry, self.client.suggested_params
            )
        except AlgodHTTPError as exc:
            raise BlockchainConnectionError(f"Algorand node returned error: {exc}") from exc
