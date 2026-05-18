"""ORM-to-domain and domain-to-ORM mappers for repository layer isolation.

Item 96 from production roadmap.
"""

from __future__ import annotations

from ulu.domain.collateral import CollateralEscrow as DomainCollateralEscrow
from ulu.domain.collateral import CollateralType as DomainCollateralType
from ulu.domain.loans import LoanStatus as DomainLoanStatus
from ulu.domain.users import AmlStatus as DomainAmlStatus
from ulu.domain.users import KycStatus as DomainKycStatus
from ulu.domain.users import User as DomainUser
from ulu.domain.users import UserRole as DomainUserRole
from ulu.infra.models import (
    AmlStatus,
    CollateralEscrow,
    CollateralType,
    KycStatus,
    LienStatus,
    Loan,
    LoanStatus,
    User,
    UserType,
)


class UserMapper:
    """Maps between User ORM and domain models."""

    @staticmethod
    def to_domain(orm: User) -> DomainUser:
        return DomainUser(
            identifier=orm.identifier,
            role=DomainUserRole(orm.user_type.value),
            kyc_status=DomainKycStatus(orm.kyc_status.value),
            aml_status=DomainAmlStatus(orm.aml_status.value),
        )

    @staticmethod
    def to_orm(domain: DomainUser) -> User:
        return User(
            identifier=domain.identifier,
            user_type=UserType(domain.role.value),
            kyc_status=KycStatus(domain.kyc_status.value),
            aml_status=AmlStatus(domain.aml_status.value),
        )


class LoanMapper:
    """Maps between Loan ORM and domain representations."""

    @staticmethod
    def to_domain(orm: Loan) -> dict:
        return {
            "id": str(orm.id),
            "borrower_id": str(orm.borrower_id),
            "principal": orm.principal,
            "term": orm.term,
            "protocol_rate": orm.protocol_rate,
            "delegation_rate": orm.delegation_rate,
            "status": DomainLoanStatus(orm.status.value),
            "originated_at": orm.originated_at.isoformat() if orm.originated_at else None,
        }

    @staticmethod
    def to_orm(payload: dict) -> Loan:
        return Loan(
            borrower_id=payload["borrower_id"],
            principal=payload["principal"],
            term=payload["term"],
            protocol_rate=payload["protocol_rate"],
            delegation_rate=payload["delegation_rate"],
            status=LoanStatus(payload.get("status", "originated")),
        )


class CollateralEscrowMapper:
    """Maps between CollateralEscrow ORM and domain models."""

    @staticmethod
    def to_domain(orm: CollateralEscrow) -> DomainCollateralEscrow:
        return DomainCollateralEscrow(
            owner_id=str(orm.owner_id),
            collateral_type=DomainCollateralType(orm.collateral_type.value),
            nominal_value=orm.nominal_value,
            haircut=orm.haircut,
            loan_id=str(orm.loan_id) if orm.loan_id else None,
        )

    @staticmethod
    def to_orm(domain: DomainCollateralEscrow) -> CollateralEscrow:
        return CollateralEscrow(
            owner_id=domain.owner_id,
            collateral_type=CollateralType(domain.collateral_type.value),
            nominal_value=domain.nominal_value,
            effective_value=domain.effective_value,
            haircut=domain.haircut,
            lien_status=LienStatus(domain.lien_status.value),
            loan_id=domain.loan_id,
        )
