"""Shared Firestore collection accessors and helpers used by all repositories."""
from datetime import datetime, timezone

from google.cloud.firestore import CollectionReference

from app.firebase.admin import get_firestore


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def users_collection() -> CollectionReference:
    return get_firestore().collection("users")


def documents_collection() -> CollectionReference:
    return get_firestore().collection("documents")


def versions_collection() -> CollectionReference:
    return get_firestore().collection("versions")


def editing_sessions_collection() -> CollectionReference:
    return get_firestore().collection("editingSessions")


def evaluation_responses_collection() -> CollectionReference:
    return get_firestore().collection("evaluationResponses")


def suggestions_collection() -> CollectionReference:
    return get_firestore().collection("suggestions")


def collaborators_collection() -> CollectionReference:
    return get_firestore().collection("documentCollaborators")
