"""FastAPI middleware to record request latency for evaluation metrics.

Records endpoint, method, latency, and status code for every request.
Does not record request/response bodies or user-identifiable data.
"""
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.services.metrics_collector import metrics_collector


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip the metrics endpoint itself to avoid self-referential noise
        if request.url.path.startswith("/metrics"):
            return await call_next(request)

        start = time.perf_counter()
        response: Response = await call_next(request)
        latency_ms = (time.perf_counter() - start) * 1000

        # Normalize path: replace IDs with placeholders for aggregation
        path = request.url.path
        # Replace UUID-like and document-id segments with {id}
        parts = path.split("/")
        normalized = []
        for part in parts:
            if len(part) > 12 and "-" in part:
                normalized.append("{id}")
            elif part and not part.isalpha() and not part.isdigit():
                normalized.append("{id}")
            else:
                normalized.append(part)
        endpoint = "/".join(normalized) or "/"

        metrics_collector.record(
            endpoint=endpoint,
            method=request.method,
            latency_ms=latency_ms,
            status_code=response.status_code,
        )
        return response
