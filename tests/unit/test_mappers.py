"""Unit tests for ORM-domain mappers."""

from __future__ import annotations

from ulu.domain.collateral import CollateralEscrow as DomainCollateralEscrow
from ulu.domain.collateral import CollateralType
from ulu.domain.users import AmlStatus, KycStatus, User, UserRole
from ulu.infra.mappers import CollateralEscrowMapper, UserMapper


class TestUserMapper:
    def test_round_trip(self) -> None:
        domain = User("u1", UserRole.BORROWER, KycStatus.VERIFIED, AmlStatus.CLEAR)
        orm = UserMapper.to_orm(domain)
        assert orm.identifier == "u1"
        assert orm.user_type.value == "borrower"
        restored = UserMapper.to_domain(orm)
        assert restored.identifier == "u1"
        assert restored.role == UserRole.BORROWER
        assert restored.kyc_status == KycStatus.VERIFIED
        assert restored.aml_status == AmlStatus.CLEAR


class TestCollateralEscrowMapper:
    def test_to_domain(self) -> None:
        domain = DomainCollateralEscrow("o1", CollateralType.CASH_DEPOSIT, 1000.0, 0.1, loan_id="l1")
        orm = CollateralEscrowMapper.to_orm(domain)
        assert orm.nominal_value == 1000.0
        assert orm.haircut == 0.1
        restored = CollateralEscrowMapper.to_domain(orm)
        assert restored.owner_id == "o1"
        assert restored.collateral_type == CollateralType.CASH_DEPOSIT
        assert restored.nominal_value == 1000.0
        assert restored.loan_id == "l1"
