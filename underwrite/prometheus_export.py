"""Prometheus text-format export for underwrite MetricsCollector.

Usage:
    exporter = MetricsExporter()
    text = exporter.to_prometheus_text(runtime)
"""

from __future__ import annotations

__all__ = [
    "MetricsExporter",
    "PrometheusMiddleware",
    "metrics_as_text",
]

from typing import Any


class MetricsExporter:
    """Formats runtime metrics into Prometheus exposition text format.

    Serialises counters, gauges, and timers from the Runtime's
    ``MetricsCollector`` snapshot into the Prometheus text format
    with ``TYPE`` and ``HELP`` headers.
    """

    @staticmethod
    def to_prometheus_text(runtime: Any) -> str:
        """Serialise the Runtime's metrics snapshot as Prometheus exposition text.

        Args:
            runtime: An underwrite Runtime instance with a ``metrics`` property.

        Returns:
            Prometheus-format text with TYPE/HELP headers for counters,
            gauges, and timers.
        """
        mc = runtime.metrics
        if mc is None:
            return ""
        snap = mc.snapshot()
        lines: list[str] = []

        for name, data in snap.get("counters", {}).items():
            safe = MetricsExporter.__sanitize(name)
            tags = MetricsExporter.__format_tags(data.get("tags", {}))
            lines.append(f"# HELP {safe} Counter metric")
            lines.append(f"# TYPE {safe} counter")
            lines.append(f"{safe}{{{tags}}} {data['value']}")

        for name, data in snap.get("gauges", {}).items():
            safe = MetricsExporter.__sanitize(name)
            tags = MetricsExporter.__format_tags(data.get("tags", {}))
            lines.append(f"# HELP {safe} Gauge metric")
            lines.append(f"# TYPE {safe} gauge")
            lines.append(f"{safe}{{{tags}}} {data['value']}")

        for name, data in snap.get("timers", {}).items():
            safe = MetricsExporter.__sanitize(name)
            tags = MetricsExporter.__format_tags(data.get("tags", {}))
            lines.append(f"# HELP {safe} Timer metric")
            lines.append(f"# TYPE {safe} gauge")
            lines.append(f"{safe}_count{{{tags}}} {data['count']}")
            lines.append(f"{safe}_avg_ms{{{tags}}} {data['avg_ms']}")
            lines.append(f"{safe}_min_ms{{{tags}}} {data['min_ms']}")
            lines.append(f"{safe}_max_ms{{{tags}}} {data['max_ms']}")

        return "\n".join(lines) + "\n"

    @staticmethod
    def __sanitize(name: str) -> str:
        """Replace non-Prometheus-safe characters in metric names."""
        return name.replace(":", "_").replace(".", "_").replace("-", "_")

    @staticmethod
    def __format_tags(tags: dict[str, str]) -> str:
        """Format a dict of tags as a Prometheus label string."""
        parts = [f'{k}="{v}"' for k, v in sorted(tags.items())]
        return ",".join(parts)


# ---------------------------------------------------------------------------
# Backward-compatible standalone function wrapper
# ---------------------------------------------------------------------------

_exporter = MetricsExporter()


def metrics_as_text(runtime: Any) -> str:
    return _exporter.to_prometheus_text(runtime)


class PrometheusMiddleware:
    """Starlette/FastAPI middleware that exposes Prometheus metrics.

    Attaches a ``/metrics-prometheus`` endpoint that returns the
    underwrite Runtime's internal metrics in Prometheus text format.
    """

    def __init__(self, app: Any, runtime: Any) -> None:
        self.app = app
        self.runtime = runtime

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] == "http" and scope.get(
                "path") == "/metrics-prometheus":
            from fastapi.responses import PlainTextResponse
            text = _exporter.to_prometheus_text(self.runtime)
            response = PlainTextResponse(
                text, media_type="text/plain; version=0.0.4")
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
