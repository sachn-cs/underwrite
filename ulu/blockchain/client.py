"""Async Algorand client wrapper with retry, circuit breaker, and timeouts."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from algosdk.error import AlgodHTTPError
from algosdk.v2client.algod import AlgodClient

from ulu.infra.circuit_breaker import blockchain_breaker


class BlockchainConnectionError(Exception):
    """Raised when the Algorand node is unreachable or returns an error."""


class AlgorandClient:
    """Lightweight async wrapper around AlgodClient for settlement anchoring."""

    def __init__(self, algod_url: str, algod_token: str, timeout: float = 30.0) -> None:
        self.algod_url = algod_url
        self.algod_token = algod_token
        self.timeout = timeout
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

    async def _async_call(self, fn: Any) -> Any:
        """Executes blocking call via asyncio.to_thread with circuit breaker and timeout."""
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(blockchain_breaker(self._call_with_retry), fn),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError as exc:
            raise BlockchainConnectionError(f"Algorand node call timed out after {self.timeout}s") from exc

    async def health(self) -> dict:
        """Returns node status for health checks."""
        try:
            return await self._async_call(self.client.status)
        except AlgodHTTPError as exc:
            raise BlockchainConnectionError(f"Algorand node returned error: {exc}") from exc

    async def suggested_params(self) -> dict:
        """Returns suggested transaction parameters."""
        try:
            return await self._async_call(self.client.suggested_params)
        except AlgodHTTPError as exc:
            raise BlockchainConnectionError(f"Algorand node returned error: {exc}") from exc
