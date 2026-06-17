"""Tests for CreditBureauService — credit bureau checks and CKYC verification."""

from __future__ import annotations

import pytest

from underwrite.__bus__ import LocalBus
from underwrite.__events__ import Event, EventType
from underwrite.services.credit_bureau.client import (
    CkycResponse,
    CreditReport,
    MockCreditBureauClient,
)
from underwrite.services.credit_bureau.service import CreditBureauService


def svc(**kw) -> CreditBureauService:
    return CreditBureauService(service_id="credit_bureau", **kw)


class TestCreditBureauCheck:
    def test_check_bureau_emits_checked(self) -> None:
        bus = LocalBus()
        received: list = []
        bus.subscribe(EventType.CREDIT_BUREAU_CHECKED, lambda e: received.append(e))
        s = svc(bus=bus)
        s._client = MockCreditBureauClient()
        s._client.add_report(
            "ABCDE1234F", CreditReport(bureau="cibil", pan="ABCDE1234F", name="A", dob="1990-01-01", score=750)
        )
        bus.start()
        s.handle(
            Event(
                event_type=EventType.CREDIT_BUREAU_CHECK,
                source="test",
                payload={"pan": "ABCDE1234F", "bureau": "cibil"},
            )
        )
        assert len(received) == 1
        assert received[0].payload["pan"] == "ABCDE1234F"
        assert received[0].payload["score"] == 750

    def test_check_bureau_missing_pan_ignored(self) -> None:
        s = svc()
        bus = LocalBus()
        s = svc(bus=bus)
        received: list = []
        bus.subscribe(EventType.CREDIT_BUREAU_CHECKED, lambda e: received.append(e))
        bus.start()
        s.handle(Event(event_type=EventType.CREDIT_BUREAU_CHECK, source="test", payload={"bureau": "cibil"}))
        assert len(received) == 0

    def test_check_bureau_failure_emits_failed(self) -> None:
        bus = LocalBus()
        received: list = []
        bus.subscribe(EventType.CREDIT_BUREAU_CHECK_FAILED, lambda e: received.append(e))
        s = svc(bus=bus)
        mock = MockCreditBureauClient()
        s._client = mock
        bus.start()
        s.handle(
            Event(
                event_type=EventType.CREDIT_BUREAU_CHECK, source="test", payload={"pan": "NOTFOUND1", "bureau": "cibil"}
            )
        )
        assert len(received) == 1
        assert "NOTFOUND1" in received[0].payload["error"]

    def test_get_report_after_check(self) -> None:
        s = svc()
        s._client = MockCreditBureauClient()
        s._client.add_report(
            "ABCDE1234F", CreditReport(bureau="cibil", pan="ABCDE1234F", name="Test", dob="1990-06-15", score=720)
        )
        s.handle(
            Event(
                event_type=EventType.CREDIT_BUREAU_CHECK,
                source="test",
                payload={"pan": "ABCDE1234F", "bureau": "cibil"},
            )
        )
        report = s.get_report("ABCDE1234F")
        assert report is not None
        assert report.score == 720
        assert report.name == "Test"

    def test_get_report_nonexistent(self) -> None:
        s = svc()
        assert s.get_report("NOPAN") is None

    def test_multiple_bureau_checks(self) -> None:
        s = svc()
        s._client = MockCreditBureauClient()
        s._client.add_report("PAN1", CreditReport(bureau="cibil", pan="PAN1", name="A", dob="1990-01-01", score=750))
        s._client.add_report("PAN2", CreditReport(bureau="experian", pan="PAN2", name="B", dob="1991-02-02", score=680))
        s.handle(
            Event(event_type=EventType.CREDIT_BUREAU_CHECK, source="test", payload={"pan": "PAN1", "bureau": "cibil"})
        )
        s.handle(
            Event(
                event_type=EventType.CREDIT_BUREAU_CHECK, source="test", payload={"pan": "PAN2", "bureau": "experian"}
            )
        )
        r1 = s.get_report("PAN1")
        r2 = s.get_report("PAN2")
        assert r1 is not None and r2 is not None
        assert r1.score == 750
        assert r2.score == 680


class TestCkycVerification:
    def test_verify_ckyc_emits_verified(self) -> None:
        bus = LocalBus()
        received: list = []
        bus.subscribe(EventType.CKYC_VERIFIED, lambda e: received.append(e))
        s = svc(bus=bus)
        mock = MockCreditBureauClient()
        s._client = mock
        mock.add_ckyc(
            "CKYC1234567890",
            CkycResponse(
                ckyc_number="CKYC1234567890",
                name="Test User",
                dob="1990-01-01",
                gender="M",
                pan="ABCDE1234F",
                aadhaar_verified=True,
                address="Addr",
                status="verified",
            ),
        )
        bus.start()
        s.handle(
            Event(
                event_type=EventType.CKYC_VERIFY,
                source="test",
                payload={"ckyc_number": "CKYC1234567890", "aadhaar": "1234"},
            )
        )
        assert len(received) == 1
        assert received[0].payload["status"] == "verified"

    def test_verify_ckyc_missing_fields_ignored(self) -> None:
        bus = LocalBus()
        received: list = []
        bus.subscribe(EventType.CKYC_VERIFIED, lambda e: received.append(e))
        s = svc(bus=bus)
        bus.start()
        s.handle(Event(event_type=EventType.CKYC_VERIFY, source="test", payload={"ckyc_number": "CKYC1234567890"}))
        s.handle(Event(event_type=EventType.CKYC_VERIFY, source="test", payload={"aadhaar": "1234"}))
        assert len(received) == 0

    def test_verify_ckyc_failure_emits_rejected(self) -> None:
        bus = LocalBus()
        received: list = []
        bus.subscribe(EventType.CKYC_REJECTED, lambda e: received.append(e))
        s = svc(bus=bus)
        s._client = MockCreditBureauClient()
        bus.start()
        s.handle(
            Event(
                event_type=EventType.CKYC_VERIFY, source="test", payload={"ckyc_number": "UNKNOWN", "aadhaar": "0000"}
            )
        )
        assert len(received) == 1
        assert "UNKNOWN" in received[0].payload["error"]

    def test_get_ckyc_after_verify(self) -> None:
        s = svc()
        mock = MockCreditBureauClient()
        s._client = mock
        mock.add_ckyc(
            "CKYC9999999999",
            CkycResponse(
                ckyc_number="CKYC9999999999",
                name="Jane Doe",
                dob="1985-05-20",
                gender="F",
                pan="ZYXWV9876K",
                aadhaar_verified=True,
                address="Addr",
                status="verified",
            ),
        )
        s.handle(
            Event(
                event_type=EventType.CKYC_VERIFY,
                source="test",
                payload={"ckyc_number": "CKYC9999999999", "aadhaar": "6789"},
            )
        )
        record = s.get_ckyc("CKYC9999999999")
        assert record is not None
        assert record["name"] == "Jane Doe"
        assert record["status"] == "verified"

    def test_get_ckyc_nonexistent(self) -> None:
        s = svc()
        assert s.get_ckyc("NOCKYC") is None


class TestMockCreditBureauClient:
    def test_fetch_report_not_found(self) -> None:
        from underwrite.services.credit_bureau.client import CreditBureauNotFoundError

        mock = MockCreditBureauClient()
        with pytest.raises(CreditBureauNotFoundError):
            mock.fetch_credit_report("NOPAN")

    def test_verify_ckyc_not_found(self) -> None:
        from underwrite.services.credit_bureau.client import CreditBureauNotFoundError

        mock = MockCreditBureauClient()
        with pytest.raises(CreditBureauNotFoundError):
            mock.verify_ckyc("NOCKYC", "0000")

    def test_fail_on(self) -> None:
        from underwrite.services.credit_bureau.client import CreditBureauError

        mock = MockCreditBureauClient()
        mock.fail_on["fetch_credit_report"] = CreditBureauError("down")
        mock.add_report("PAN1", CreditReport(bureau="cibil", pan="PAN1", name="A", dob="1990-01-01", score=750))
        with pytest.raises(CreditBureauError):
            mock.fetch_credit_report("PAN1")

    def test_fetch_report_success(self) -> None:
        mock = MockCreditBureauClient()
        report = CreditReport(
            bureau="cibil",
            pan="ABCDE1234F",
            name="A",
            dob="1990-01-01",
            score=780,
            active_accounts=3,
            delinquent_accounts=1,
        )
        mock.add_report("ABCDE1234F", report)
        result = mock.fetch_credit_report("ABCDE1234F")
        assert result.score == 780
        assert result.active_accounts == 3

    def test_verify_ckyc_success(self) -> None:
        mock = MockCreditBureauClient()
        resp = CkycResponse(
            ckyc_number="CKYC1234",
            name="Test",
            dob="1990-01-01",
            gender="M",
            pan="ABCDE1234F",
            aadhaar_verified=True,
            address="Addr",
            status="verified",
        )
        mock.add_ckyc("CKYC1234", resp)
        result = mock.verify_ckyc("CKYC1234", "1234")
        assert result.status == "verified"
        assert result.aadhaar_verified is True


class TestHealthCheck:
    def test_health_returns_counts(self) -> None:
        s = svc()
        s._client = MockCreditBureauClient()
        s._client.add_report("PAN1", CreditReport(bureau="cibil", pan="PAN1", name="A", dob="1990-01-01", score=750))
        s.handle(
            Event(event_type=EventType.CREDIT_BUREAU_CHECK, source="test", payload={"pan": "PAN1", "bureau": "cibil"})
        )
        health = s.health_check()
        assert health["reports_cached"] == 1
