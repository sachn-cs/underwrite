"""Unit tests for DLG pool reconciliation."""

from __future__ import annotations

import datetime

import pytest

from ulu.compliance.rbi_dlg import (
    DlgPoolReconciliationService,
    RbiDlgCompliance,
)


class TestDlgPoolReconciliationService:
    def test_add_and_list_entries(self) -> None:
        svc = DlgPoolReconciliationService()
        svc.add_entry("E1", "POOL1", "cash_deposit", 100000.0, reference="REF001")
        entries = svc.list_entries("POOL1")
        assert len(entries) == 1
        assert entries[0].entry_id == "E1"
        assert entries[0].entry_type == "cash_deposit"

    def test_add_duplicate_raises(self) -> None:
        svc = DlgPoolReconciliationService()
        svc.add_entry("E1", "POOL1", "cash_deposit", 100000.0)
        with pytest.raises(ValueError, match="already exists"):
            svc.add_entry("E1", "POOL1", "cash_deposit", 200000.0)

    def test_add_negative_amount_raises(self) -> None:
        svc = DlgPoolReconciliationService()
        with pytest.raises(ValueError, match="must be positive"):
            svc.add_entry("E1", "POOL1", "cash_deposit", -100.0)

    def test_actual_pool_balance(self) -> None:
        svc = DlgPoolReconciliationService()
        svc.add_entry("E1", "POOL1", "cash_deposit", 100000.0)
        svc.add_entry("E2", "POOL1", "lien_marked_fd", 50000.0)
        svc.add_entry("E3", "POOL2", "cash_deposit", 20000.0)
        assert svc.actual_pool_balance("POOL1") == 150000.0
        assert svc.actual_pool_balance("POOL2") == 20000.0

    def test_expired_entries_excluded(self) -> None:
        svc = DlgPoolReconciliationService()
        past = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=1)
        svc.add_entry("E1", "POOL1", "bank_guarantee", 100000.0, expires_at=past)
        assert svc.actual_pool_balance("POOL1") == 0.0

    def test_reconcile_sufficient(self) -> None:
        svc = DlgPoolReconciliationService()
        svc.add_entry("E1", "POOL1", "cash_deposit", 100000.0)
        result = svc.reconcile("POOL1", portfolio_outstanding=1000000.0, dlg_cap_ratio=0.05)
        assert result["actual_balance"] == 100000.0
        assert result["required_balance"] == 50000.0
        assert result["gap"] == -50000.0
        assert result["sufficient"] is True

    def test_reconcile_insufficient(self) -> None:
        svc = DlgPoolReconciliationService()
        svc.add_entry("E1", "POOL1", "cash_deposit", 30000.0)
        result = svc.reconcile("POOL1", portfolio_outstanding=1000000.0, dlg_cap_ratio=0.05)
        assert result["actual_balance"] == 30000.0
        assert result["required_balance"] == 50000.0
        assert result["gap"] == 20000.0
        assert result["sufficient"] is False

    def test_remove_entry(self) -> None:
        svc = DlgPoolReconciliationService()
        svc.add_entry("E1", "POOL1", "cash_deposit", 100000.0)
        svc.remove_entry("E1")
        assert svc.actual_pool_balance("POOL1") == 0.0

    def test_remove_unknown_raises(self) -> None:
        svc = DlgPoolReconciliationService()
        with pytest.raises(ValueError, match="not found"):
            svc.remove_entry("E99")


class TestRbiDlgCompliance:
    def test_physical_recovery_limit(self) -> None:
        comp = RbiDlgCompliance(dlg_cap_ratio=0.05)
        assert comp.physical_recovery_limit(1_000_000.0) == 50_000.0

    def test_compute_physical_recovery(self) -> None:
        comp = RbiDlgCompliance(dlg_cap_ratio=0.05)
        assert comp.compute_physical_recovery(30_000.0, 1_000_000.0) == 30_000.0
        assert comp.compute_physical_recovery(100_000.0, 1_000_000.0) == 50_000.0

    def test_remaining_bank_absorption(self) -> None:
        comp = RbiDlgCompliance(dlg_cap_ratio=0.05)
        assert comp.remaining_bank_absorption(100_000.0, 1_000_000.0) == 50_000.0

    def test_can_originate(self) -> None:
        comp = RbiDlgCompliance(dlg_cap_ratio=0.05)
        assert comp.can_originate(1_000_000.0, 50_000.0) is True
        assert comp.can_originate(1_000_000.0, 49_999.99) is False

    def test_invalid_ratio_raises(self) -> None:
        with pytest.raises(ValueError, match="dlg_cap_ratio"):
            RbiDlgCompliance(dlg_cap_ratio=1.5)
