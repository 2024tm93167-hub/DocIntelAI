"""WebSocket endpoint for document presence and realtime notifications.

Clients connect with a `token` query parameter (Firebase ID token) and a
`document_id` path parameter. The server verifies the token, checks that the
user has at least viewer access to the document, and joins them to the
document's presence channel.

Events sent to clients:
- ``presence``: a user joined or left (action: joined/left, user_id, name)
- ``presence_list``: full list of currently connected users
- ``document_updated``: a document was saved (revision, updated_by, updated_by_name)
- ``version_created``: a version snapshot was created (version_id, label, created_by)
- ``cursor``: a collaborator moved their cursor or changed selection (user_id, name, from, to, empty)

Events received from clients:
- ``{"type": "cursor", "from": <int>, "to": <int>, "empty": <bool>}``: cursor/selection update
"""
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.deps import AuthenticatedUser
from app.firebase.admin import verify_id_token
from app.services.connection_manager import Connection, connection_manager
from app.services.permissions import get_document_with_role
from app.utils.exceptions import NotFoundError, PermissionDeniedError

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/documents/{document_id}")
async def document_ws(websocket: WebSocket, document_id: str) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    try:
        decoded = verify_id_token(token)
    except Exception:
        await websocket.close(code=4003, reason="Invalid or expired token")
        return

    user = AuthenticatedUser(uid=decoded["uid"], email=decoded.get("email"), name=decoded.get("name"))

    try:
        get_document_with_role(document_id, user, min_role="viewer")
    except (NotFoundError, PermissionDeniedError):
        await websocket.close(code=4003, reason="Access denied")
        return

    conn = Connection(
        websocket=websocket, document_id=document_id,
        user_id=user.uid, user_name=user.name, user_email=user.email,
    )

    await connection_manager.connect(conn)
    try:
        while True:
            raw = await websocket.receive_text()
            await _handle_client_message(raw, conn)
    except WebSocketDisconnect:
        pass
    finally:
        await connection_manager.disconnect(conn)


async def _handle_client_message(raw: str, conn: Connection) -> None:
    """Process an incoming client WebSocket message."""
    try:
        msg = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return
    if not isinstance(msg, dict):
        return
    msg_type = msg.get("type")
    if msg_type == "cursor":
        cursor_data = {
            "from": msg.get("from", 0),
            "to": msg.get("to", 0),
            "empty": msg.get("empty", False),
        }
        await connection_manager.broadcast_cursor(conn.document_id, conn, cursor_data)
