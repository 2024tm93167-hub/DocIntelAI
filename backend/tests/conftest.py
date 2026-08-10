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


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)
