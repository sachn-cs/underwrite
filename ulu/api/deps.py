"""FastAPI dependency injection providers."""

from __future__ import annotations

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ulu.infra.config import settings
from ulu.infra.db import get_db_session
from ulu.infra.models import UserType
from ulu.infra.repositories import (
    AuditEventRepository,
    CollateralEscrowRepository,
    DefaultRepository,
    IdempotencyRepository,
    LoanRepository,
    NpaEventRepository,
    RepaymentRepository,
    UserRepository,
)


async def get_user_repo(session: AsyncSession = Depends(get_db_session)) -> UserRepository:
    return UserRepository(session)


async def get_loan_repo(session: AsyncSession = Depends(get_db_session)) -> LoanRepository:
    return LoanRepository(session)


async def get_repayment_repo(
    session: AsyncSession = Depends(get_db_session),
) -> RepaymentRepository:
    return RepaymentRepository(session)


async def get_default_repo(
    session: AsyncSession = Depends(get_db_session),
) -> DefaultRepository:
    return DefaultRepository(session)


async def get_collateral_repo(
    session: AsyncSession = Depends(get_db_session),
) -> CollateralEscrowRepository:
    return CollateralEscrowRepository(session)


async def get_npa_repo(session: AsyncSession = Depends(get_db_session)) -> NpaEventRepository:
    return NpaEventRepository(session)


async def get_audit_repo(
    session: AsyncSession = Depends(get_db_session),
) -> AuditEventRepository:
    return AuditEventRepository(session)


async def get_idempotency_repo(
    session: AsyncSession = Depends(get_db_session),
) -> IdempotencyRepository:
    return IdempotencyRepository(session)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc


async def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="missing authorization header")
    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="invalid authorization format")
    return _decode_token(parts[1])


def require_role(role: UserType):
    """Returns a dependency that enforces the given user role."""

    async def checker(user: dict = Depends(get_current_user)) -> dict:
        user_role = user.get("role")
        if user_role != role.value:
            raise HTTPException(status_code=403, detail=f"requires role: {role.value}")
        return user

    return checker


async def require_admin(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> None:
    """Validates admin bearer token for sensitive endpoints."""
    admin_token = authorization.split(" ")[1] if authorization and authorization.startswith("Bearer ") else ""
    if not admin_token:
        raise HTTPException(status_code=401, detail="missing authorization header")
    payload = _decode_token(admin_token)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="invalid admin token")
