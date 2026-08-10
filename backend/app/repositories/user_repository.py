"""Firestore-backed persistence for users/{uid}."""
from app.models.user import UserModel
from app.repositories.base import users_collection, utcnow


class UserRepository:
    def get(self, uid: str) -> UserModel | None:
        snap = users_collection().document(uid).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        return UserModel(
            uid=uid,
            name=data.get("name"),
            email=data.get("email"),
            created_at=data.get("createdAt"),
            last_login_at=data.get("lastLoginAt"),
        )

    def get_or_create(self, uid: str, email: str | None, name: str | None) -> UserModel:
        doc_ref = users_collection().document(uid)
        snap = doc_ref.get()
        now = utcnow()

        if not snap.exists:
            resolved_name = name or (email.split("@")[0] if email else "User")
            payload = {
                "name": resolved_name,
                "email": email,
                "createdAt": now,
                "lastLoginAt": now,
            }
            doc_ref.set(payload)
            return UserModel(uid=uid, name=resolved_name, email=email, created_at=now, last_login_at=now)

        doc_ref.update({"lastLoginAt": now})
        data = snap.to_dict() or {}
        return UserModel(
            uid=uid,
            name=data.get("name"),
            email=data.get("email") or email,
            created_at=data.get("createdAt"),
            last_login_at=now,
        )


user_repository = UserRepository()
