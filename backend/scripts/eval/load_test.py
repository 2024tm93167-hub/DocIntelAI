"""Locust load-test configuration for DocIntel AI backend performance evaluation.

Measures p50/p95 latency for key endpoints under simulated user load.
Results can be cross-checked against the /metrics/summary endpoint.

Prerequisites:
    pip install locust

Usage:
    cd backend
    venv/bin/locust -f scripts/eval/load_test.py --host http://127.0.0.1:8000

Then open http://localhost:8089 in your browser to configure the number of
users and spawn rate. Use a valid Firebase ID token as the "token" input.

What this tests:
    - GET /documents (list documents)
    - GET /documents/{id} (fetch a document)
    - PATCH /documents/{id} (save a document)
    - GET /documents/{id}/versions (list versions)
    - GET /documents/{id}/versions/{vid}/diff (diff a version)
    - POST /ai/action (non-streaming AI action)

Metrics collected:
    - Requests per second
    - Response time p50/p95/p99
    - Failure rate
    - Cross-reference with GET /metrics/summary for server-side latency

Targets (from evaluation plan):
    - p95 < 500ms for read endpoints
    - p95 < 1500ms for AI actions
"""
import os
import random

from locust import HttpUser, between, task


# Set DOCINTEL_TOKEN to a valid Firebase ID token before running.
# You can get one from the browser's localStorage or the auth interceptor.
TOKEN = os.environ.get("DOCINTEL_TOKEN", "")
DOCUMENT_ID = os.environ.get("DOCINTEL_DOC_ID", "")


class DocIntelUser(HttpUser):
    wait_time = between(1, 3)
    weight = 1

    def on_start(self):
        if not TOKEN:
            raise RuntimeError(
                "Set DOCINTEL_TOKEN environment variable to a valid Firebase ID token. "
                "Example: DOCINTEL_TOKEN=eyJ... venv/bin/locust -f scripts/eval/load_test.py"
            )
        self.client.headers.update({"Authorization": f"Bearer {TOKEN}"})
        # Discover a document ID if not provided
        if not DOCUMENT_ID:
            resp = self.client.get("/documents")
            if resp.ok and resp.json():
                self.doc_id = resp.json()[0]["id"]
            else:
                self.doc_id = None
        else:
            self.doc_id = DOCUMENT_ID

    @task(3)
    def list_documents(self):
        self.client.get("/documents")

    @task(2)
    def get_document(self):
        if self.doc_id:
            self.client.get(f"/documents/{self.doc_id}")

    @task(1)
    def save_document(self):
        if not self.doc_id:
            return
        # Fetch current revision first
        resp = self.client.get(f"/documents/{self.doc_id}")
        if not resp.ok:
            return
        doc = resp.json()
        self.client.patch(
            f"/documents/{self.doc_id}",
            json={
                "title": doc["title"],
                "content": doc["content"],
                "word_count": doc["word_count"],
                "base_revision": doc["revision"],
            },
        )

    @task(1)
    def list_versions(self):
        if self.doc_id:
            self.client.get(f"/documents/{self.doc_id}/versions")

    @task(1)
    def diff_version(self):
        if not self.doc_id:
            return
        resp = self.client.get(f"/documents/{self.doc_id}/versions")
        if not resp.ok or not resp.json():
            return
        versions = resp.json()
        if len(versions) >= 1:
            vid = versions[0]["id"]
            self.client.get(f"/documents/{self.doc_id}/versions/{vid}/diff")

    @task(1)
    def ai_action(self):
        if not self.doc_id:
            return
        self.client.post(
            "/ai/action",
            json={
                "action": "grammar",
                "text": "This are a test sentence with some errors.",
                "document_title": "Load Test",
            },
        )

    @task(1)
    def get_metrics(self):
        """Fetch server-side metrics to cross-reference with locust results."""
        self.client.get("/metrics/summary")
