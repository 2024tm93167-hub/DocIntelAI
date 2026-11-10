"""In-memory WebSocket connection manager for document presence and notifications.

Tracks connected users per document and broadcasts presence events (join/leave)
and document update notifications. This is a single-process manager suitable
for a prototype; multi-process deployment would require a pub/sub backend.
"""
import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import WebSocket


@dataclass
class Connection:
    websocket: WebSocket
    document_id: str
    user_id: str
    user_name: str | None
    user_email: str | None


@dataclass
class PresenceUser:
    user_id: str
    name: str | None
    email: str | None
    joined_at: str


class ConnectionManager:
    def __init__(self) -> None:
        # document_id -> list of Connection
        self._connections: dict[str, list[Connection]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, conn: Connection) -> None:
        async with self._lock:
            self._connections.setdefault(conn.document_id, []).append(conn)
        await conn.websocket.accept()
        await self._send_presence(conn.document_id, conn, "joined")
        await self._broadcast_user_list(conn.document_id)

    async def disconnect(self, conn: Connection) -> None:
        async with self._lock:
            conns = self._connections.get(conn.document_id, [])
            if conn in conns:
                conns.remove(conn)
            if not conns:
                self._connections.pop(conn.document_id, None)
        await self._send_presence(conn.document_id, conn, "left")
        await self._broadcast_user_list(conn.document_id)

    async def broadcast_document_update(
        self, document_id: str, revision: int, updated_by: str, updated_by_name: str | None
    ) -> None:
        """Broadcast a document_updated event to all connected users for a document."""
        message = json.dumps({
            "type": "document_updated",
            "document_id": document_id,
            "revision": revision,
            "updated_by": updated_by,
            "updated_by_name": updated_by_name,
        })
        await self._deliver(document_id, message)

    async def broadcast_version_created(
        self, document_id: str, version_id: str, label: str | None, created_by: str
    ) -> None:
        message = json.dumps({
            "type": "version_created",
            "document_id": document_id,
            "version_id": version_id,
            "label": label,
            "created_by": created_by,
        })
        await self._deliver(document_id, message)

    async def broadcast_cursor(
        self, document_id: str, sender: Connection, cursor_data: dict
    ) -> None:
        """Broadcast a cursor/selection update to all other connected users."""
        message = json.dumps({
            "type": "cursor",
            "document_id": document_id,
            "user_id": sender.user_id,
            "name": sender.user_name,
            "from": cursor_data.get("from", 0),
            "to": cursor_data.get("to", 0),
            "empty": cursor_data.get("empty", False),
        })
        await self._deliver(document_id, message, exclude_user_id=sender.user_id)

    def get_connected_users(self, document_id: str) -> list[PresenceUser]:
        seen: set[str] = set()
        users: list[PresenceUser] = []
        for c in self._connections.get(document_id, []):
            if c.user_id in seen:
                continue
            seen.add(c.user_id)
            users.append(PresenceUser(
                user_id=c.user_id, name=c.user_name, email=c.user_email,
                joined_at=datetime.now(timezone.utc).isoformat(),
            ))
        return users

    async def _send_presence(self, document_id: str, conn: Connection, action: str) -> None:
        message = json.dumps({
            "type": "presence",
            "action": action,
            "user_id": conn.user_id,
            "name": conn.user_name,
        })
        await self._deliver(document_id, message, exclude=conn)

    async def _broadcast_user_list(self, document_id: str) -> None:
        # One presence entry per user: a collaborator with multiple tabs or a
        # stale socket should render once, not once per connection.
        seen: set[str] = set()
        users = []
        for c in self._connections.get(document_id, []):
            if c.user_id in seen:
                continue
            seen.add(c.user_id)
            users.append({"user_id": c.user_id, "name": c.user_name, "email": c.user_email})
        if not users:
            return
        message = json.dumps({"type": "presence_list", "users": users})
        await self._deliver(document_id, message, prune=False)

    async def _deliver(
        self,
        document_id: str,
        message: str,
        exclude: Connection | None = None,
        exclude_user_id: str | None = None,
        prune: bool = True,
    ) -> None:
        """Send a message to every live connection for a document.

        A connection that fails to send is dropped — a socket whose client
        vanished without a clean close would otherwise linger in presence
        forever. After pruning, the user list is re-broadcast so remaining
        clients stop showing the ghost.
        """
        async with self._lock:
            conns = [
                c for c in self._connections.get(document_id, [])
                if c is not exclude and c.user_id != exclude_user_id
            ]
        if not conns:
            return
        dead: list[Connection] = []
        for conn in conns:
            try:
                await conn.websocket.send_text(message)
            except Exception:
                dead.append(conn)
        if not prune or not dead:
            return
        async with self._lock:
            current = self._connections.get(document_id, [])
            for conn in dead:
                if conn in current:
                    current.remove(conn)
            if not current:
                self._connections.pop(document_id, None)
        await self._broadcast_user_list(document_id)


connection_manager = ConnectionManager()
