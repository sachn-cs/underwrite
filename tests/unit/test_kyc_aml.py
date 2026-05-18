"""Unit tests for KYC/AML service including audit trail."""

from __future__ import annotations

import datetime

import pytest

from ulu.compliance.kyc_aml import AmlAuditRecord, AmlAuditTrail, KycAmlService
from ulu.domain.users import AmlStatus, KycStatus, User, UserRole


class TestKycAmlService:
    def test_verify_kyc_stub_raises(self) -> None:
        svc = KycAmlService()
        user = User(identifier="u1", role=UserRole.BORROWER)
        with pytest.raises(NotImplementedError):
            svc.verify_kyc(user, "ABCDE1234F", "hash123")

    def test_transition_kyc(self) -> None:
        svc = KycAmlService()
        user = User(identifier="u1", role=UserRole.BORROWER)
        event = svc.transition_kyc(user, KycStatus.VERIFIED)
        assert user.kyc_status == KycStatus.VERIFIED
        assert event is not None
        assert event.new_status == "verified"

    def test_invalid_kyc_transition_raises(self) -> None:
        svc = KycAmlService()
        user = User(identifier="u1", role=UserRole.BORROWER, kyc_status=KycStatus.VERIFIED)
        with pytest.raises(ValueError, match="invalid KYC transition"):
            svc.transition_kyc(user, KycStatus.REJECTED)

    def test_screen_aml_clear(self) -> None:
        svc = KycAmlService()
        user = User(identifier="u1", role=UserRole.BORROWER, aml_status=AmlStatus.FLAGGED)
        status, event = svc.screen_aml(user, watchlist_hit=False)
        assert status == AmlStatus.CLEAR
        assert event is not None
        assert event.reason == "screening_clear"

    def test_screen_aml_hit(self) -> None:
        svc = KycAmlService()
        user = User(identifier="u1", role=UserRole.BORROWER, aml_status=AmlStatus.CLEAR)
        status, event = svc.screen_aml(user, watchlist_hit=True)
        assert status == AmlStatus.FROZEN
        assert event is not None
        assert event.reason == "watchlist_hit"

    def test_screen_aml_no_change(self) -> None:
        svc = KycAmlService()
        user = User(identifier="u1", role=UserRole.BORROWER, aml_status=AmlStatus.CLEAR)
        status, event = svc.screen_aml(user, watchlist_hit=False)
        assert status == AmlStatus.CLEAR
        assert event is None

    def test_is_compliant(self) -> None:
        svc = KycAmlService()
        user = User(identifier="u1", role=UserRole.BORROWER)
        user.kyc_status = KycStatus.VERIFIED
        user.aml_status = AmlStatus.CLEAR
        assert svc.is_compliant(user) is True
        user.aml_status = AmlStatus.FROZEN
        assert svc.is_compliant(user) is False


class TestAmlAuditTrail:
    def test_append_and_get(self) -> None:
        trail = AmlAuditTrail()
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        record = AmlAuditRecord(
            record_id="r1",
            user_id="u1",
            old_status="clear",
            new_status="frozen",
            reason="watchlist_hit",
            screened_at=now,
            watchlist_hit=True,
        )
        trail.append(record)
        assert len(trail.get_by_user("u1")) == 1
        assert len(trail.get_all()) == 1

    def test_count_hits(self) -> None:
        trail = AmlAuditTrail()
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        trail.append(AmlAuditRecord("r1", "u1", "clear", "frozen", "hit", now, True))
        trail.append(AmlAuditRecord("r2", "u1", "frozen", "clear", "clear", now, False))
        assert trail.count_hits("u1") == 1

    def test_get_by_user_empty(self) -> None:
        trail = AmlAuditTrail()
        assert trail.get_by_user("nobody") == []
        assert trail.count_hits("nobody") == 0

    def test_screen_aml_creates_audit_record(self) -> None:
        trail = AmlAuditTrail()
        svc = KycAmlService(audit_trail=trail)
        user = User(identifier="u1", role=UserRole.BORROWER)
        svc.screen_aml(user, watchlist_hit=True)
        records = trail.get_by_user("u1")
        assert len(records) == 1
        assert records[0].watchlist_hit is True
        assert records[0].new_status == "frozen"
