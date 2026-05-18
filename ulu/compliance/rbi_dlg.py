"""RBI Digital Lending Directions compliance — DLG cap and dual-layer settlement."""

from __future__ import annotations

import dataclasses
import datetime

from ulu.infra.logging import logger


@dataclasses.dataclass
class DlgPoolEntry:
    """Tracks an actual cash deposit, FD lien, or bank guarantee backing the DLG pool."""

    entry_id: str
    pool_id: str
    entry_type: str  # "cash_deposit", "lien_marked_fd", "bank_guarantee"
    amount: float
    created_at: datetime.datetime
    expires_at: datetime.datetime | None = None
    reference: str = ""  # bank reference number or FD receipt


class DlgPoolReconciliationService:
    """Reconciles actual DLG pool balances against computed regulatory requirements."""

    def __init__(self) -> None:
        self._entries: dict[str, DlgPoolEntry] = {}

    def add_entry(
        self,
        entry_id: str,
        pool_id: str,
        entry_type: str,
        amount: float,
        reference: str = "",
        expires_at: datetime.datetime | None = None,
    ) -> DlgPoolEntry:
        if amount <= 0:
            raise ValueError("entry amount must be positive")
        if entry_id in self._entries:
            raise ValueError(f"entry already exists: {entry_id}")
        entry = DlgPoolEntry(
            entry_id=entry_id,
            pool_id=pool_id,
            entry_type=entry_type,
            amount=amount,
            created_at=datetime.datetime.now(tz=datetime.timezone.utc),
            expires_at=expires_at,
            reference=reference,
        )
        self._entries[entry_id] = entry
        logger.info("dlg_pool_entry_added", entry_id=entry_id, pool_id=pool_id, amount=amount)
        return entry

    def remove_entry(self, entry_id: str) -> None:
        entry = self._entries.pop(entry_id, None)
        if entry is None:
            raise ValueError(f"entry not found: {entry_id}")
        logger.info("dlg_pool_entry_removed", entry_id=entry_id, pool_id=entry.pool_id)

    def actual_pool_balance(self, pool_id: str) -> float:
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        return sum(
            e.amount
            for e in self._entries.values()
            if e.pool_id == pool_id and (e.expires_at is None or e.expires_at > now)
        )

    def reconcile(
        self,
        pool_id: str,
        portfolio_outstanding: float,
        dlg_cap_ratio: float,
    ) -> dict[str, float]:
        """Compares actual pool balance to computed requirement."""
        actual = self.actual_pool_balance(pool_id)
        required = portfolio_outstanding * dlg_cap_ratio
        gap = required - actual
        return {
            "actual_balance": actual,
            "required_balance": required,
            "gap": gap,
            "sufficient": gap <= 0,
        }

    def list_entries(self, pool_id: str) -> list[DlgPoolEntry]:
        return [e for e in self._entries.values() if e.pool_id == pool_id]


class RbiDlgCompliance:
    """Enforces the RBI-mandated 5% Default Loss Guarantee cap."""

    def __init__(self, dlg_cap_ratio: float) -> None:
        if not (0.0 <= dlg_cap_ratio <= 1.0):
            raise ValueError(f"dlg_cap_ratio must be in [0, 1], got {dlg_cap_ratio}")
        self.dlg_cap_ratio = dlg_cap_ratio

    def physical_recovery_limit(self, portfolio_outstanding: float) -> float:
        """Returns maximum physical cash recovery allowed under DLG."""
        return portfolio_outstanding * self.dlg_cap_ratio

    def compute_physical_recovery(self, logical_loss: float, portfolio_outstanding: float) -> float:
        """Caps logical loss to DLG limit."""
        logical_loss = max(0.0, logical_loss)
        limit = self.physical_recovery_limit(portfolio_outstanding)
        return min(logical_loss, limit)

    def remaining_bank_absorption(self, logical_loss: float, portfolio_outstanding: float) -> float:
        """Loss absorbed on bank/RE balance sheet after DLG cap."""
        physical = self.compute_physical_recovery(logical_loss, portfolio_outstanding)
        return max(0.0, logical_loss - physical)

    def can_originate(self, portfolio_outstanding: float, dlg_pool_balance: float) -> bool:
        """Returns False if DLG pool is below regulatory minimum."""
        required = portfolio_outstanding * self.dlg_cap_ratio
        return dlg_pool_balance >= required
