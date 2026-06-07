"""Tests for MetricsExporter prometheus text formatting."""

from __future__ import annotations

from unittest.mock import MagicMock

from underwrite.prometheus_export import MetricsExporter


def _mock_runtime(snapshot: dict) -> MagicMock:
    rt = MagicMock()
    mc = MagicMock()
    mc.snapshot.return_value = snapshot
    rt.metrics = mc
    return rt


class TestMetricsExporter:

    def test_empty_metrics_returns_trailing_newline(self) -> None:
        rt = _mock_runtime({})
        text = MetricsExporter.to_prometheus_text(rt)
        assert text == "\n"

    def test_no_metrics_collector(self) -> None:
        rt = MagicMock()
        rt.metrics = None
        text = MetricsExporter.to_prometheus_text(rt)
        assert text == ""

    def test_counter_output_format(self) -> None:
        snap = {
            "counters": {
                "events.handled": {
                    "value": 42,
                    "tags": {
                        "service": "test"
                    }
                }
            }
        }
        rt = _mock_runtime(snap)
        text = MetricsExporter.to_prometheus_text(rt)
        assert "# HELP events_handled Counter metric" in text
        assert "# TYPE events_handled counter" in text
        assert 'events_handled{service="test"} 42' in text

    def test_gauge_output_format(self) -> None:
        snap = {
            "gauges": {
                "active.loans": {
                    "value": 10,
                    "tags": {
                        "type": "unsecured"
                    }
                }
            }
        }
        rt = _mock_runtime(snap)
        text = MetricsExporter.to_prometheus_text(rt)
        assert "# HELP active_loans Gauge metric" in text
        assert "# TYPE active_loans gauge" in text
        assert 'active_loans{type="unsecured"} 10' in text

    def test_timer_output_format(self) -> None:
        snap = {
            "timers": {
                "handle.duration": {
                    "count": 5,
                    "avg_ms": 10.0,
                    "min_ms": 2.0,
                    "max_ms": 25.0,
                    "tags": {
                        "service": "test"
                    }
                }
            }
        }
        rt = _mock_runtime(snap)
        text = MetricsExporter.to_prometheus_text(rt)
        assert "# TYPE handle_duration gauge" in text
        assert 'handle_duration_count{service="test"} 5' in text
        assert 'handle_duration_avg_ms{service="test"} 10.0' in text
        assert 'handle_duration_min_ms{service="test"} 2.0' in text
        assert 'handle_duration_max_ms{service="test"} 25.0' in text
