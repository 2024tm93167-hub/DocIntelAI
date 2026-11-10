"""Firebase Admin SDK initialization and thin accessors for Auth / Firestore.

All Firebase-specific wiring is isolated here so the rest of the backend
(business services, repositories) never touches the Admin SDK directly.
"""
from threading import RLock

import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials, firestore
from google.cloud.firestore import Client as FirestoreClient

from app.config.settings import get_settings

_initialization_lock = RLock()
_firebase_app: firebase_admin.App | None = None
_firestore_client: FirestoreClient | None = None


def init_firebase() -> firebase_admin.App:
    """Initialize the Firebase Admin app exactly once (idempotent)."""
    global _firebase_app
    with _initialization_lock:
        if _firebase_app is None:
            settings = get_settings()
            cred = credentials.Certificate(settings.firebase_service_account_path)
            options = {"projectId": settings.firebase_project_id} if settings.firebase_project_id else {}
            _firebase_app = firebase_admin.initialize_app(cred, options)
        return _firebase_app


def get_firestore() -> FirestoreClient:
    """Return a singleton Firestore client bound to the Admin app."""
    global _firestore_client
    with _initialization_lock:
        if _firestore_client is None:
            init_firebase()
            _firestore_client = firestore.client()
        return _firestore_client


def verify_id_token(id_token: str) -> dict:
    """Verify a Firebase Authentication ID token and return its decoded claims."""
    init_firebase()
    return firebase_auth.verify_id_token(id_token)
