"""Protocol governance — parameter management and proposals.

Maintains protocol-level parameters (protocol_rate, max_delegation_rate,
dlg_cap_ratio, ltv_ratio, min_base_budget) within defined ranges and
processes GOVERNANCE_PROPOSAL events to update them.
"""

from __future__ import annotations

from typing import Any

from underwrite.__events__ import Event, EventType
from underwrite.__logger__ import logger
from underwrite.services.base import StatefulService
from underwrite.services.persistence import TypedStoreRepository
from underwrite.validate import get_finite, get_non_empty

DEFAULT_PARAM_RANGES: dict[str, tuple[float, float]] = {
    "protocol_rate": (0.0, 1.0),
    "max_delegation_rate": (0.0, 1.0),
    "dlg_cap_ratio": (0.0, 1.0),
    "ltv_ratio": (0.0, 1.0),
    "min_base_budget": (0.0, float("inf")),
}

DEFAULT_PARAM_DEFAULTS: dict[str, float] = {
    "protocol_rate": 0.10,
    "max_delegation_rate": 0.05,
    "dlg_cap_ratio": 0.05,
    "ltv_ratio": 0.75,
    "min_base_budget": 1000.0,
}


class GovernanceService(StatefulService):
    """Manages protocol parameters and handles governance proposals."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialise the governance service with default parameter values.

        Args:
            **kwargs: Forwarded to NanoService.__init__.
        """
        raw_ranges: dict[str, list[float]] = kwargs.pop("param_ranges", {})
        raw_defaults: dict[str, float] = kwargs.pop("param_defaults", {})
        self.__ranges: dict[str, tuple[float, float]] = ({
            k: (float(v[0]), float(v[1]))
            for k, v in raw_ranges.items()
            if isinstance(v, (list, tuple)) and len(v) == 2
        } if raw_ranges else dict(DEFAULT_PARAM_RANGES))
        super().__init__(**kwargs)
        self.__params: dict[str, float] = dict(
            raw_defaults) if raw_defaults else dict(DEFAULT_PARAM_DEFAULTS)
        self._repo: TypedStoreRepository[dict[str, float]] = self.store_repo(
            "params", dict)
        loaded = self._repo.load(default={})
        if loaded:
            self.__params = loaded

    def handle(self, event: Event) -> None:
        """Process a governance proposal to update a protocol parameter.

        Validates the parameter name and value range before applying.

        Args:
            event: The incoming event. Only GOVERNANCE_PROPOSAL events are processed.
        """
        with self.state_lock:
            if event.event_type == EventType.GOVERNANCE_PROPOSAL:
                p = event.payload
                param: str = get_non_empty(p, "param")
                value: float = get_finite(p, "value")
                if param not in self.__params:
                    logger.warning(
                        "governance proposal for unknown param %r ignored",
                        param)
                    return
                lo, hi = self.__ranges[param]
                if not (lo <= value <= hi):
                    logger.warning(
                        "governance proposal for %r value %s outside range [%s, %s]",
                        param, value, lo, hi)
                    return
                self.__params[param] = value
                self.__sync()
                self.emit(
                    EventType.GOVERNANCE_EXECUTED,
                    {
                        "param": param,
                        "value": value,
                    },
                    correlation_id=event.correlation_id,
                )

    @property
    def params(self) -> dict[str, float]:
        """Return a snapshot of all current protocol parameters."""
        with self.state_lock:
            return dict(self.__params)

    def health_check(self) -> dict[str, Any]:
        """Governance-specific health: reports active param count."""
        with self.state_lock:
            return {
                **super().health_check(),
                "param_count": len(self.__params),
            }

    # -- state persistence ---------------------------------------------------

    def __sync(self) -> None:
        """Persist the current protocol parameters to the store."""
        self._repo.save(self.__params)
