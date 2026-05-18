"""FastAPI application exposing delegated-underwriting operations."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from hashlib import sha256
from pathlib import Path
from threading import RLock
from time import perf_counter
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from ulu import AppendOnlyLedger, DelegatedUnderwriting
from ulu.api.deps import require_admin
from ulu.errors import ProtocolError
from ulu.infra.config import settings
from ulu.infra.logging import logger

REQUESTS_TOTAL = Counter(
    "ulu_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
REQUEST_ERRORS_TOTAL = Counter(
    "ulu_request_errors_total",
    "Total HTTP request errors",
    ["method", "endpoint"],
)
REQUEST_LATENCY = Histogram(
    "ulu_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
)
IDEMPOTENCY_HITS_TOTAL = Counter(
    "ulu_idempotency_hits_total",
    "Total idempotency cache hits",
)
IDEMPOTENCY_CONFLICTS_TOTAL = Counter(
    "ulu_idempotency_conflicts_total",
    "Total idempotency key conflicts",
)


class SeedRequest(BaseModel):
    user: str
    base_budget: float = Field(gt=0)


class UserRequest(BaseModel):
    sponsor: str
    user: str
    delegation_amount: float = Field(gt=0)


class RepayRequest(BaseModel):
    user: str
    delta_earned: float = Field(ge=0)


class RevokeRequest(BaseModel):
    sponsor: str
    child: str
    new_delegation: float = Field(ge=0)


class QuoteRequest(BaseModel):
    borrower: str
    principal: float = Field(gt=0)
    term: float = Field(gt=0)
    default_probability: float = Field(gt=0, lt=1)
    protocol_rate: float = Field(ge=0, le=10.0)
    max_delegation_rate: float = Field(ge=0, le=10.0)


class DefaultRequest(BaseModel):
    borrower: str


class SaveRequest(BaseModel):
    path: str


class LoadRequest(BaseModel):
    path: str


class LedgerSaveRequest(BaseModel):
    path: str


class LedgerLoadRequest(BaseModel):
    path: str


class StatusResponse(BaseModel):
    status: str


class QuoteResponse(BaseModel):
    borrower: str
    principal: float
    term: float
    protocol_premium: float
    delegation_premium: float
    total_interest: float
    delegation_utilization: float
    delegation_rate: float
    locked_by_edge: dict[str, float]
    delegation_payouts: dict[str, float]


class OriginateResponse(BaseModel):
    borrower: str
    principal: float
    term: float
    total_interest: float


class StateResponse(BaseModel):
    state: dict[str, Any]


class LedgerResponse(BaseModel):
    events: list[dict[str, Any]]


class GraphResponse(BaseModel):
    seeds: list[str]
    parent: dict[str, str]
    edges: list[dict[str, Any]]


class UtilizationResponse(BaseModel):
    delegation_utilization: float


class SolvencyResponse(BaseModel):
    invariants: str
    required_delegation: dict[str, float]


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str


class LiveResponse(BaseModel):
    status: str


_IDEMPOTENCY_MAX_SIZE = 10_000
_DATA_DIR = Path(os.environ.get("ULU_DATA_DIR", "/tmp/ulu_data"))


def _ensure_data_dir() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def _validate_path(raw: str) -> Path:
    _ensure_data_dir()
    target = (_DATA_DIR / raw).resolve()
    try:
        target.relative_to(_DATA_DIR.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid path: must be inside data directory") from exc
    return target


class ProtocolService:
    """Holds thread-safe runtime objects used by API handlers."""

    def __init__(self) -> None:
        self.lock = RLock()
        self.ledger = AppendOnlyLedger()
        self.engine = DelegatedUnderwriting(ledger=self.ledger)
        self.idempotency_cache: dict[str, tuple[str, dict[str, Any]]] = {}

    def _prune_idempotency_cache(self) -> None:
        if len(self.idempotency_cache) > _IDEMPOTENCY_MAX_SIZE:
            keys = list(self.idempotency_cache.keys())
            for key in keys[: len(keys) // 4]:
                self.idempotency_cache.pop(key, None)


service = ProtocolService()
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="ULU API", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def metrics_middleware(request, call_next):
    """Collects lightweight request metrics."""
    start = perf_counter()
    response = await call_next(request)
    elapsed = perf_counter() - start
    route = request.scope.get("route")
    endpoint = route.name if route else "unknown"
    REQUESTS_TOTAL.labels(method=request.method, endpoint=endpoint, status=str(response.status_code)).inc()
    REQUEST_LATENCY.labels(method=request.method, endpoint=endpoint).observe(elapsed)
    if response.status_code >= 400:
        REQUEST_ERRORS_TOTAL.labels(method=request.method, endpoint=endpoint).inc()
    return response


def safe_call(fn: Callable[[], Any]) -> Any:
    """Maps protocol errors to HTTP 400 responses; logs unexpected errors."""
    try:
        return fn()
    except ProtocolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("unexpected_error", context="safe_call")
        raise HTTPException(status_code=500, detail="internal server error") from exc


def ledger_events_payload() -> list[dict[str, Any]]:
    """Returns serialized ledger event payloads."""
    return [
        {
            "seq": event.seq,
            "event_type": event.event_type,
            "payload": event.payload,
            "timestamp_utc": event.timestamp_utc,
        }
        for event in service.ledger.events()
    ]


def canonical_request_hash(payload: Mapping[str, Any]) -> str:
    """Creates deterministic hash for idempotent mutation payload."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(blob.encode("utf-8")).hexdigest()


def idempotent_mutation(
    operation_name: str,
    payload: Mapping[str, Any],
    action: Callable[[], Any],
    idempotency_key: str | None,
) -> Any:
    """Executes idempotent mutation when idempotency key is provided."""
    if not idempotency_key:
        return action()

    cache_key = f"{operation_name}:{idempotency_key}"
    payload_hash = canonical_request_hash(payload)
    cached = service.idempotency_cache.get(cache_key)
    if cached is not None:
        cached_hash, cached_response = cached
        if cached_hash != payload_hash:
            IDEMPOTENCY_CONFLICTS_TOTAL.inc()
            raise HTTPException(
                status_code=409,
                detail="idempotency key replayed with different payload",
            )
        IDEMPOTENCY_HITS_TOTAL.inc()
        return cached_response

    response = action()
    service._prune_idempotency_cache()
    service.idempotency_cache[cache_key] = (payload_hash, response)
    return response


def quote_response_payload(quote: Any) -> dict[str, Any]:
    """Builds response payload for quote-like operations."""
    return {
        "borrower": quote.borrower,
        "principal": quote.principal,
        "term": quote.term,
        "protocol_premium": quote.protocol_premium,
        "delegation_premium": quote.delegation_premium,
        "total_interest": quote.total_interest,
        "delegation_utilization": quote.delegation_utilization,
        "delegation_rate": quote.delegation_rate,
        "locked_by_edge": {f"{source}->{target}": amount for (source, target), amount in quote.locked_by_edge.items()},
        "delegation_payouts": quote.delegation_payouts,
    }


def graph_payload() -> dict[str, Any]:
    """Builds graph view for admin inspection."""
    edges = [
        {"sponsor": sponsor, "child": child, "amount": amount}
        for (sponsor, child), amount in sorted(service.engine.delegation.items())
    ]
    return {
        "seeds": sorted(service.engine.seeds),
        "parent": dict(service.engine.parent),
        "edges": edges,
    }


async def _db_is_healthy() -> bool:
    """Checks PostgreSQL connectivity when DATABASE_URL is configured."""
    if not settings.database_url:
        return True
    try:
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return True
    except Exception:
        return False


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/live", response_model=LiveResponse)
def live() -> LiveResponse:
    return LiveResponse(status="alive")


@app.get("/ready", response_model=ReadyResponse)
async def ready() -> ReadyResponse:
    with service.lock:
        try:
            service.engine.assert_invariants()
        except ProtocolError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not await _db_is_healthy():
        raise HTTPException(status_code=503, detail="database unreachable")
    return ReadyResponse(status="ready")


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/state", response_model=dict[str, Any])
def get_state() -> dict[str, Any]:
    with service.lock:
        return service.engine.to_dict()


@app.get("/ledger", response_model=LedgerResponse)
def get_ledger() -> LedgerResponse:
    with service.lock:
        return LedgerResponse(events=ledger_events_payload())


@app.get("/admin/graph", response_model=GraphResponse)
def admin_graph(_: None = Depends(require_admin)) -> GraphResponse:
    """Returns the current delegation graph for admin inspection."""
    with service.lock:
        payload = graph_payload()
    return GraphResponse(
        seeds=payload["seeds"],
        parent=payload["parent"],
        edges=payload["edges"],
    )


@app.get("/admin/utilization", response_model=UtilizationResponse)
def admin_utilization(_: None = Depends(require_admin)) -> UtilizationResponse:
    """Returns seed delegation utilization metrics."""
    with service.lock:
        util = safe_call(service.engine.seed_delegation_utilization)
    return UtilizationResponse(delegation_utilization=util)


@app.get("/admin/solvency", response_model=SolvencyResponse)
def admin_solvency(_: None = Depends(require_admin)) -> SolvencyResponse:
    """Returns solvency invariants and required delegation per user."""
    with service.lock:
        safe_call(service.engine.assert_invariants)
        required: dict[str, float] = {}
        for user in sorted(service.engine.earned):
            if user not in service.engine.seeds:
                required[user] = service.engine.required_delegation(user)
    return SolvencyResponse(invariants="ok", required_delegation=required)


@app.post("/admin/reset", response_model=StatusResponse)
@limiter.limit("5/minute")
def admin_reset(
    request: Request,
    _: None = Depends(require_admin),
) -> StatusResponse:
    """Resets protocol state, ledger, and idempotency cache."""
    with service.lock:
        service.ledger = AppendOnlyLedger()
        service.engine = DelegatedUnderwriting(ledger=service.ledger)
        service.idempotency_cache.clear()
    logger.info("admin_reset_executed")
    return StatusResponse(status="ok")


@app.post("/seed", response_model=StatusResponse)
@limiter.limit("10/minute")
def add_seed(
    request: Request,
    body: SeedRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> StatusResponse:
    def action() -> StatusResponse:
        safe_call(lambda: service.engine.add_seed(body.user, body.base_budget))
        return StatusResponse(status="ok")

    with service.lock:
        return idempotent_mutation("add_seed", body.model_dump(), action, idempotency_key)


@app.post("/user", response_model=StatusResponse)
@limiter.limit("10/minute")
def add_user(
    request: Request,
    body: UserRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> StatusResponse:
    def action() -> StatusResponse:
        safe_call(
            lambda: service.engine.add_user(
                body.sponsor,
                body.user,
                body.delegation_amount,
            )
        )
        return StatusResponse(status="ok")

    with service.lock:
        return idempotent_mutation("add_user", body.model_dump(), action, idempotency_key)


@app.post("/repay", response_model=StatusResponse)
@limiter.limit("10/minute")
def repay(
    request: Request,
    body: RepayRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> StatusResponse:
    def action() -> StatusResponse:
        safe_call(lambda: service.engine.repay(body.user, body.delta_earned))
        return StatusResponse(status="ok")

    with service.lock:
        return idempotent_mutation("repay", body.model_dump(), action, idempotency_key)


@app.post("/revoke", response_model=StatusResponse)
@limiter.limit("10/minute")
def revoke(
    request: Request,
    body: RevokeRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> StatusResponse:
    def action() -> StatusResponse:
        safe_call(
            lambda: service.engine.revoke(
                body.sponsor,
                body.child,
                body.new_delegation,
            )
        )
        return StatusResponse(status="ok")

    with service.lock:
        return idempotent_mutation("revoke", body.model_dump(), action, idempotency_key)


@app.post("/quote", response_model=QuoteResponse)
@limiter.limit("30/minute")
def quote(
    request: Request,
    body: QuoteRequest,
) -> QuoteResponse:
    with service.lock:
        quote_value = safe_call(
            lambda: service.engine.quote_loan(
                borrower=body.borrower,
                principal=body.principal,
                term=body.term,
                default_probability=body.default_probability,
                protocol_rate=body.protocol_rate,
                max_delegation_rate=body.max_delegation_rate,
            )
        )
    return QuoteResponse(**quote_response_payload(quote_value))


@app.post("/originate", response_model=OriginateResponse)
@limiter.limit("10/minute")
def originate(
    request: Request,
    body: QuoteRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> OriginateResponse:
    def action() -> OriginateResponse:
        quote_value = safe_call(
            lambda: service.engine.originate_loan(
                borrower=body.borrower,
                principal=body.principal,
                term=body.term,
                default_probability=body.default_probability,
                protocol_rate=body.protocol_rate,
                max_delegation_rate=body.max_delegation_rate,
            )
        )
        return OriginateResponse(
            borrower=quote_value.borrower,
            principal=quote_value.principal,
            term=quote_value.term,
            total_interest=quote_value.total_interest,
        )

    with service.lock:
        return idempotent_mutation("originate", body.model_dump(), action, idempotency_key)


@app.post("/default", response_model=StatusResponse)
@limiter.limit("10/minute")
def default(
    request: Request,
    body: DefaultRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> StatusResponse:
    def action() -> StatusResponse:
        safe_call(lambda: service.engine.default(body.borrower))
        return StatusResponse(status="ok")

    with service.lock:
        return idempotent_mutation("default", body.model_dump(), action, idempotency_key)


@app.post("/state/save", response_model=StatusResponse)
@limiter.limit("20/minute")
def save_state(
    request: Request,
    body: SaveRequest,
) -> StatusResponse:
    """Saves protocol state to a file inside the data directory."""
    target = _validate_path(body.path)
    with service.lock:
        safe_call(lambda: service.engine.save_json(str(target)))
    return StatusResponse(status="ok")


@app.post("/state/load", response_model=StatusResponse)
@limiter.limit("20/minute")
def load_state(
    request: Request,
    body: LoadRequest,
) -> StatusResponse:
    """Loads protocol state from a file inside the data directory."""
    target = _validate_path(body.path)

    def load_action() -> None:
        service.engine = DelegatedUnderwriting.load_json(str(target))
        service.engine.ledger = service.ledger

    with service.lock:
        safe_call(load_action)
    return StatusResponse(status="ok")


@app.post("/ledger/save", response_model=StatusResponse)
@limiter.limit("20/minute")
def save_ledger(
    request: Request,
    body: LedgerSaveRequest,
) -> StatusResponse:
    """Saves ledger events to a file inside the data directory."""
    target = _validate_path(body.path)
    with service.lock:
        service.ledger.save_jsonl(str(target))
    return StatusResponse(status="ok")


@app.post("/ledger/load", response_model=StatusResponse)
@limiter.limit("20/minute")
def load_ledger(
    request: Request,
    body: LedgerLoadRequest,
) -> StatusResponse:
    """Loads ledger events from a file inside the data directory."""
    target = _validate_path(body.path)
    with service.lock:
        service.ledger = AppendOnlyLedger.load_jsonl(str(target))
        service.engine.ledger = service.ledger
    return StatusResponse(status="ok")
