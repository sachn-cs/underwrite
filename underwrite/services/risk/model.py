"""Risk scoring model (optional sklearn wrapper).

Loads a pre-trained model from a joblib file or reconstructs from a
JSON parameter file. Falls back to a heuristic default-probability
calculator when no model file is available.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("underwrite")


class _JsonModel:
    """Minimal linear model reconstructed from JSON-serialised parameters."""

    def __init__(self, params: dict[str, Any]) -> None:
        self.__coef: list[float] = params.get("coef_", [0.0, 0.0])
        self.__intercept: float = params.get("intercept_", 0.0)

    def predict(self, X: list[list[float]]) -> list[float]:
        return [
            sum(xi * c for xi, c in zip(row, self.__coef, strict=False)) + self.__intercept
            for row in X
        ]


class RiskModel:
    """Wraps a trained model or uses a heuristic fallback.

    The model must expose a ``predict(X)`` method that accepts a list
    of feature vectors and returns a list of predictions.
    """

    def __init__(self, model_path: str = "") -> None:
        """Load a pre-trained model from a file or use a heuristic fallback.

        Supports joblib files (preferred) and JSON parameter files with
        ``coef_`` and ``intercept_`` keys.

        Args:
            model_path: Path to a serialised model file. If empty or missing,
                only the heuristic fallback is used.
        """
        self.__model: Any | None = None
        if model_path and Path(model_path).exists():
            self.__verify_integrity(model_path)
            self.__model = self.__load_model_safe(model_path)

    @staticmethod
    def __verify_integrity(model_path: str) -> None:
        expected = os.environ.get("RISK_MODEL_SHA256", "")
        sidecar = Path(str(model_path) + ".sha256")
        if not expected and sidecar.exists():
            expected = sidecar.read_text().strip()
        if expected:
            with open(model_path, "rb") as f:
                actual = hashlib.sha256(f.read()).hexdigest()
            if actual != expected:
                raise ValueError(
                    f"Model integrity check failed: expected {expected}, got {actual}"
                )

    @staticmethod
    def __load_model_safe(model_path: str) -> Any:
        """Load a model file with safe deserialisation.

        Tries joblib first; falls back to JSON-based reconstruction
        using ``_JsonModel``.  Validates the resulting object exposes
        a ``predict`` callable.

        Args:
            model_path: Path to the model file.

        Returns:
            A model object with a ``predict`` method.

        Raises:
            ValueError: If deserialisation fails or the loaded object
                is not a valid model.
        """
        try:
            import joblib
            model = joblib.load(model_path)
            if not callable(getattr(model, "predict", None)):
                raise ValueError(
                    "joblib-loaded object has no predict method")
            return model
        except ImportError:
            logger.info("joblib not available, falling back to JSON load")
        except Exception as exc:
            logger.warning("joblib load failed for %s: %s", model_path, exc)

        # Safe JSON fallback — no pickle, no arbitrary code execution.
        try:
            with open(model_path) as fh:
                params = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(
                f"Failed to parse model file {model_path}: {exc}") from exc

        if not isinstance(params, dict):
            raise ValueError(
                f"JSON model file must contain a JSON object, got {type(params).__name__}"
            )
        json_model: Any = _JsonModel(params)
        if not callable(getattr(json_model, "predict", None)):
            raise ValueError(
                "reconstructed model has no predict method")
        return json_model

    def predict(self, principal: float, term: float) -> float:
        """Returns a default-probability score in [0.0, 1.0]."""
        if self.__model is not None:
            try:
                result = self.__model.predict([[principal, term]])
                return float(result[0])
            except Exception as exc:
                logger.exception("risk model predict failed: %s", exc)
        return self.__heuristic(principal, term)

    @staticmethod
    def __heuristic(principal: float, term: float) -> float:
        safe_term: float = max(term, 1.0)
        if principal <= 0:
            return 0.0
        raw: float = (principal / 1_000_000.0) * (1.0 / safe_term)
        return min(max(raw, 0.01), 0.5)
