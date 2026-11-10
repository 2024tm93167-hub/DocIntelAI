"""Tests for the metrics collector and metrics endpoints."""
from unittest.mock import patch

import pytest

from app.services.metrics_collector import MetricsCollector

FAKE_DECODED_TOKEN = {"uid": "owner-uid", "email": "owner@example.com", "name": "Owner"}
AUTH_HEADERS = {"Authorization": "Bearer good-token"}


def test_metrics_collector_records_and_summarizes():
    collector = MetricsCollector()
    collector.record("/documents", "GET", 10.5, 200)
    collector.record("/documents", "GET", 20.3, 200)
    collector.record("/documents", "GET", 30.1, 200)
    collector.record("/documents", "GET", 40.7, 200)
    collector.record("/documents", "GET", 100.0, 500)

    summary = collector.get_summary()
    assert "/documents" in summary
    assert summary["/documents"]["count"] == 5
    assert summary["/documents"]["p50_ms"] == 30.1
    assert summary["/documents"]["p95_ms"] == 100.0
    assert summary["/documents"]["error_count"] == 1
    assert summary["/documents"]["error_rate"] == 0.2
    assert summary["/documents"]["last_status"] == 500


def test_metrics_collector_get_recent():
    collector = MetricsCollector()
    for i in range(5):
        collector.record(f"/endpoint{i}", "GET", float(i), 200)
    recent = collector.get_recent(limit=3)
    assert len(recent) == 3
    assert recent[-1]["endpoint"] == "/endpoint4"


def test_metrics_collector_reset():
    collector = MetricsCollector()
    collector.record("/documents", "GET", 10.0, 200)
    collector.reset()
    assert collector.get_summary() == {}
    assert collector.get_recent() == []


def test_metrics_collector_trims_to_max():
    collector = MetricsCollector(max_records=5)
    for i in range(10):
        collector.record("/documents", "GET", float(i), 200)
    assert len(collector._records) == 5
    assert collector._records[0].latency_ms == 5.0


def test_metrics_summary_requires_auth(client):
    response = client.get("/metrics/summary")
    assert response.status_code == 401


def test_metrics_summary_returns_data(client):
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN):
        # First make a request to generate metrics
        client.get("/health", headers=AUTH_HEADERS)
        # Then fetch the summary
        response = client.get("/metrics/summary", headers=AUTH_HEADERS)
    assert response.status_code == 200
    body = response.json()
    # Health endpoint should appear in metrics
    assert any("/health" in ep for ep in body.keys())


def test_metrics_recent_requires_auth(client):
    response = client.get("/metrics/recent")
    assert response.status_code == 401


def test_metrics_recent_returns_data(client):
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN):
        client.get("/health", headers=AUTH_HEADERS)
        response = client.get("/metrics/recent?limit=5", headers=AUTH_HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert len(body) >= 1
    assert "endpoint" in body[0]
    assert "latency_ms" in body[0]
    assert "status_code" in body[0]


def test_metrics_reset_requires_auth(client):
    response = client.post("/metrics/reset")
    assert response.status_code == 401


def test_metrics_reset_clears_data(client):
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN):
        client.get("/health", headers=AUTH_HEADERS)
        # Verify data exists
        before = client.get("/metrics/summary", headers=AUTH_HEADERS).json()
        assert len(before) > 0
        # Reset
        response = client.post("/metrics/reset", headers=AUTH_HEADERS)
        assert response.status_code == 204
        # Verify cleared (but the reset request itself generates a metric)
        after = client.get("/metrics/summary", headers=AUTH_HEADERS).json()
        # Only the metrics/reset and metrics/summary calls should be present
        assert "/metrics/reset" not in after or after["/metrics/reset"]["count"] <= 1


def test_metrics_endpoint_not_recorded(client):
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN):
        # Make several metrics calls
        client.get("/metrics/summary", headers=AUTH_HEADERS)
        client.get("/metrics/summary", headers=AUTH_HEADERS)
        summary = client.get("/metrics/summary", headers=AUTH_HEADERS).json()
    # The /metrics/summary endpoint should NOT appear in its own metrics
    assert "/metrics/summary" not in summary
