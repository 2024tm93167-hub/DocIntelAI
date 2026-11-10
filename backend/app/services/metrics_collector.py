"""In-memory request metrics collector for evaluation instrumentation.

Records latency and status code for sampled API requests. Provides p50/p95
aggregations per endpoint. This is a single-process collector suitable for
prototype evaluation; production would use a proper metrics backend.

No document content or user-identifiable data is recorded — only endpoint
path, latency, status code, and timestamp.
"""
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import quantiles


@dataclass
class RequestRecord:
    endpoint: str
    method: str
    latency_ms: float
    status_code: int
    timestamp: str


class MetricsCollector:
    def __init__(self, max_records: int = 10000) -> None:
        self._records: list[RequestRecord] = []
        self._max_records = max_records
        self._by_endpoint: dict[str, list[RequestRecord]] = defaultdict(list)

    def record(self, endpoint: str, method: str, latency_ms: float, status_code: int) -> None:
        rec = RequestRecord(
            endpoint=endpoint,
            method=method,
            latency_ms=round(latency_ms, 2),
            status_code=status_code,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._records.append(rec)
        self._by_endpoint[endpoint].append(rec)
        # Trim if exceeding max
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records:]
        for ep, recs in self._by_endpoint.items():
            if len(recs) > self._max_records:
                self._by_endpoint[ep] = recs[-self._max_records:]

    def get_summary(self) -> dict:
        """Return per-endpoint p50/p95 latency and request counts."""
        summary: dict[str, dict] = {}
        for endpoint, recs in self._by_endpoint.items():
            if not recs:
                continue
            latencies = sorted(r.latency_ms for r in recs)
            n = len(latencies)
            p50 = latencies[n // 2] if n > 0 else 0
            p95 = latencies[min(int(n * 0.95), n - 1)] if n > 0 else 0
            errors = sum(1 for r in recs if r.status_code >= 400)
            summary[endpoint] = {
                "count": n,
                "p50_ms": round(p50, 2),
                "p95_ms": round(p95, 2),
                "error_count": errors,
                "error_rate": round(errors / n, 4) if n > 0 else 0,
                "last_status": recs[-1].status_code,
            }
        return summary

    def get_recent(self, limit: int = 100) -> list[dict]:
        """Return the most recent request records."""
        recent = self._records[-limit:]
        return [
            {
                "endpoint": r.endpoint,
                "method": r.method,
                "latency_ms": r.latency_ms,
                "status_code": r.status_code,
                "timestamp": r.timestamp,
            }
            for r in recent
        ]

    def reset(self) -> None:
        self._records.clear()
        self._by_endpoint.clear()


metrics_collector = MetricsCollector()
