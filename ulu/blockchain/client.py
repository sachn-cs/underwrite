"""Async Algorand client wrapper with retry, circuit breaker, timeouts, and connection pooling."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import requests
from algosdk.error import AlgodHTTPError
from algosdk.v2client.algod import AlgodClient

from ulu.infra.circuit_breaker import blockchain_breaker


class BlockchainConnectionError(Exception):
    """Raised when the Algorand node is unreachable or returns an error."""


class SessionAlgodClient(AlgodClient):
    """AlgodClient backed by requests.Session for connection pooling."""

    def __init__(
        self,
        algod_token: str,
        algod_address: str,
        headers: dict[str, str] | None = None,
        session: requests.Session | None = None,
    ) -> None:
        super().__init__(algod_token, algod_address, headers)
        self.session = session or requests.Session()

    def algod_request(  # type: ignore[override]
        self,
        method: str,
        requrl: str,
        params: Any | None = None,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        response_format: str = "json",
        timeout: int = 30,
    ) -> Any:
        from urllib import parse

        from algosdk.v2client.algod import api_version_path_prefix
        from algosdk.v2client.algod import constants as algod_constants

        header = {"User-Agent": "py-algorand-sdk"}
        if self.headers:
            header.update(self.headers)
        if headers:
            header.update(headers)
        if requrl not in algod_constants.no_auth:
            header.update({algod_constants.algod_auth_header: self.algod_token})
        if requrl not in algod_constants.unversioned_paths:
            requrl = api_version_path_prefix + requrl
        if params:
            requrl = requrl + "?" + parse.urlencode(params)

        url = self.algod_address + requrl
        try:
            resp = self.session.request(
                method, url, headers=header, data=data, timeout=timeout
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise AlgodHTTPError(str(exc)) from exc

        if response_format == "json":
            if resp.status_code == 200 and not resp.content:
                return {}
            return resp.json()
        return resp.content


class AlgorandClient:
    """Lightweight async wrapper around AlgodClient for settlement anchoring."""

    def __init__(
        self,
        algod_url: str,
        algod_token: str,
        timeout: float = 30.0,
        session: requests.Session | None = None,
    ) -> None:
        self.algod_url = algod_url
        self.algod_token = algod_token
        self.timeout = timeout
        self.client = SessionAlgodClient(self.algod_token, self.algod_url, session=session)

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
