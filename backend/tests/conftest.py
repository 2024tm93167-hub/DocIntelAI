import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("FIREBASE_SERVICE_ACCOUNT_PATH", str(BACKEND_ROOT / "serviceAccountKey.json"))
os.environ.setdefault("ENVIRONMENT", "test")

from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def block_live_firebase(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Live Firebase access is forbidden in unit tests. Use a test double.")

    def blocked_provider(*args, **kwargs):
        raise AssertionError("Live AI providers are forbidden in unit tests. Use a test double.")

    monkeypatch.setattr("app.api.routers.ai.get_ai_provider", blocked_provider)
    monkeypatch.setattr("app.firebase.admin.init_firebase", blocked)
    monkeypatch.setattr("firebase_admin.initialize_app", blocked)
    monkeypatch.setattr("app.firebase.admin.firestore.client", blocked)
    monkeypatch.setattr("app.firebase.admin._firestore_client", None)
    monkeypatch.setattr("app.firebase.admin._firebase_app", None)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)
