"""Unsecured lending underwriting baseline package."""

from importlib.metadata import version

from ulu.audit import AppendOnlyLedger, LedgerEvent
from ulu.core.mechanism import DelegatedUnderwriting
from ulu.core.models import LoanQuote, ProtocolConfig, ProtocolState
from ulu.errors import InfeasibleOperationError, InvariantViolationError, ProtocolError, UnknownUserError

try:
    __version__ = version("ulu")
except Exception:
    __version__ = "unknown"

__all__ = [
    "AppendOnlyLedger",
    "DelegatedUnderwriting",
    "InfeasibleOperationError",
    "InvariantViolationError",
    "LedgerEvent",
    "LoanQuote",
    "ProtocolConfig",
    "ProtocolError",
    "ProtocolState",
    "UnknownUserError",
]
