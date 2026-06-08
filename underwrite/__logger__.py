"""Centralised logging for the underwrite platform.

All services and infrastructure modules import ``logger`` from this
module instead of creating their own via ``logging.getLogger()``.
Logging configuration (format, level, handlers) is managed by
:func:`Runtime.__setup_logging` in :mod:`underwrite.__runtime__`.
"""

from __future__ import annotations

import logging

__all__ = ["logger"]

logger = logging.getLogger("underwrite")
