"""Tests for the WebSocket presence and document update notification system."""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.connection_manager import Connection, ConnectionManager


FAKE_DECODED_TOKEN = {"uid": "owner-uid", "email": "owner@example.com", "name": "Owner"}
SECOND_DECODED_TOKEN = {"uid": "editor-uid", "email": "editor@example.com", "name": "Editor"}
FAKE_DOC = MagicMock()
FAKE_DOC.owner_id = "owner-uid"


@pytest.fixture()
def ws_client():
    return TestClient(app)


def test_ws_rejects_missing_token(ws_client):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with ws_client.websocket_connect("/ws/documents/doc-1"):
            pass


def test_ws_rejects_invalid_token(ws_client):
    from starlette.websockets import WebSocketDisconnect
    with patch("app.api.routers.ws.verify_id_token", side_effect=Exception("bad token")):
        with pytest.raises(WebSocketDisconnect):
            with ws_client.websocket_connect("/ws/documents/doc-1?token=bad"):
                pass


def test_ws_rejects_no_access(ws_client):
    from starlette.websockets import WebSocketDisconnect
    with patch("app.api.routers.ws.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.ws.get_document_with_role",
        side_effect=__import__("app.utils.exceptions", fromlist=["PermissionDeniedError"]).PermissionDeniedError("no access")
    ):
        with pytest.raises(WebSocketDisconnect):
            with ws_client.websocket_connect("/ws/documents/doc-1?token=good"):
                pass


def test_ws_connects_and_receives_presence(ws_client):
    with patch("app.api.routers.ws.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.ws.get_document_with_role", return_value=(FAKE_DOC, "owner")
    ):
        with ws_client.websocket_connect("/ws/documents/doc-1?token=good") as ws:
            # Should receive a presence_list message on connect
            message = json.loads(ws.receive_text())
            assert message["type"] == "presence_list"
            assert len(message["users"]) == 1
            assert message["users"][0]["user_id"] == "owner-uid"


def test_ws_two_users_see_each_other(ws_client):
    with patch(
        "app.api.routers.ws.verify_id_token",
        side_effect=lambda token: SECOND_DECODED_TOKEN if token == "token-b" else FAKE_DECODED_TOKEN,
    ), patch(
        "app.api.routers.ws.get_document_with_role", return_value=(FAKE_DOC, "owner")
    ):
        with ws_client.websocket_connect("/ws/documents/doc-1?token=good") as ws1:
            # Receive presence_list for first user
            msg1 = json.loads(ws1.receive_text())
            assert msg1["type"] == "presence_list"
            assert len(msg1["users"]) == 1

            with ws_client.websocket_connect("/ws/documents/doc-1?token=token-b") as ws2:
                # Second user receives presence_list with 2 users
                msg2 = json.loads(ws2.receive_text())
                assert msg2["type"] == "presence_list"
                assert len(msg2["users"]) == 2

                # First user receives presence "joined" then presence_list
                # (order may vary, but both should arrive)
                messages = []
                for _ in range(2):
                    messages.append(json.loads(ws1.receive_text()))
                types = [m["type"] for m in messages]
                assert "presence" in types
                assert "presence_list" in types
                joined = next(m for m in messages if m["type"] == "presence")
                assert joined["action"] == "joined"


def test_ws_same_user_multiple_tabs_counts_once(ws_client):
    with patch("app.api.routers.ws.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.ws.get_document_with_role", return_value=(FAKE_DOC, "owner")
    ):
        with ws_client.websocket_connect("/ws/documents/doc-1?token=good") as ws1:
            msg1 = json.loads(ws1.receive_text())
            assert len(msg1["users"]) == 1

            with ws_client.websocket_connect("/ws/documents/doc-1?token=good") as ws2:
                # Same uid on a second socket must not duplicate the avatar.
                msg2 = json.loads(ws2.receive_text())
                assert msg2["type"] == "presence_list"
                assert len(msg2["users"]) == 1


def test_connection_manager_broadcast_document_update():
    manager = ConnectionManager()
    ws = AsyncMock()
    conn = Connection(
        websocket=ws, document_id="doc-1", user_id="u1",
        user_name="User", user_email="u@e.com",
    )
    manager._connections["doc-1"] = [conn]

    asyncio.run(
        manager.broadcast_document_update("doc-1", 5, "u2", "Editor")
    )
    ws.send_text.assert_called_once()
    sent = json.loads(ws.send_text.call_args.args[0])
    assert sent["type"] == "document_updated"
    assert sent["revision"] == 5
    assert sent["updated_by"] == "u2"
    assert sent["updated_by_name"] == "Editor"


def test_connection_manager_broadcast_version_created():
    manager = ConnectionManager()
    ws = AsyncMock()
    conn = Connection(
        websocket=ws, document_id="doc-1", user_id="u1",
        user_name="User", user_email="u@e.com",
    )
    manager._connections["doc-1"] = [conn]

    asyncio.run(
        manager.broadcast_version_created("doc-1", "ver-1", "Draft", "u2")
    )
    ws.send_text.assert_called_once()
    sent = json.loads(ws.send_text.call_args.args[0])
    assert sent["type"] == "version_created"
    assert sent["version_id"] == "ver-1"
    assert sent["label"] == "Draft"


def test_connection_manager_get_connected_users():
    manager = ConnectionManager()
    ws = AsyncMock()
    conn = Connection(
        websocket=ws, document_id="doc-1", user_id="u1",
        user_name="Alice", user_email="a@e.com",
    )
    manager._connections["doc-1"] = [conn]
    users = manager.get_connected_users("doc-1")
    assert len(users) == 1
    assert users[0].user_id == "u1"
    assert users[0].name == "Alice"


def test_connection_manager_dedupes_users_with_multiple_connections():
    manager = ConnectionManager()
    tab1 = Connection(websocket=AsyncMock(), document_id="doc-1", user_id="u1", user_name="Alice", user_email="a@e.com")
    tab2 = Connection(websocket=AsyncMock(), document_id="doc-1", user_id="u1", user_name="Alice", user_email="a@e.com")
    other = Connection(websocket=AsyncMock(), document_id="doc-1", user_id="u2", user_name="Bob", user_email="b@e.com")
    manager._connections["doc-1"] = [tab1, tab2, other]
    users = manager.get_connected_users("doc-1")
    assert [u.user_id for u in users] == ["u1", "u2"]


def test_connection_manager_prunes_dead_connections_and_rebroadcasts():
    manager = ConnectionManager()
    dead_ws = AsyncMock()
    dead_ws.send_text.side_effect = RuntimeError("socket gone")
    live_ws = AsyncMock()
    ghost = Connection(websocket=dead_ws, document_id="doc-1", user_id="ghost", user_name="Ghost", user_email="g@e.com")
    live = Connection(websocket=live_ws, document_id="doc-1", user_id="u1", user_name="Alice", user_email="a@e.com")
    manager._connections["doc-1"] = [ghost, live]

    asyncio.run(manager.broadcast_document_update("doc-1", 5, "u1", "Alice"))

    assert manager._connections["doc-1"] == [live]
    sent_types = [json.loads(call.args[0])["type"] for call in live_ws.send_text.call_args_list]
    assert sent_types == ["document_updated", "presence_list"]


def test_connection_manager_broadcast_cursor_excludes_sender():
    manager = ConnectionManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    sender = Connection(websocket=ws1, document_id="doc-1", user_id="u1", user_name="Alice", user_email="a@e.com")
    other = Connection(websocket=ws2, document_id="doc-1", user_id="u2", user_name="Bob", user_email="b@e.com")
    manager._connections["doc-1"] = [sender, other]

    asyncio.run(
        manager.broadcast_cursor("doc-1", sender, {"from": 5, "to": 10, "empty": False})
    )
    # Sender should NOT receive its own cursor
    ws1.send_text.assert_not_called()
    # Other user should receive the cursor message
    ws2.send_text.assert_called_once()
    sent = json.loads(ws2.send_text.call_args.args[0])
    assert sent["type"] == "cursor"
    assert sent["user_id"] == "u1"
    assert sent["name"] == "Alice"
    assert sent["from"] == 5
    assert sent["to"] == 10
    assert sent["empty"] is False


def test_connection_manager_cursor_excludes_all_sender_connections():
    # A user's own cursor must not echo to their other tabs — otherwise they
    # see a remote cursor labeled with their own name.
    manager = ConnectionManager()
    ws1, ws2, ws3 = AsyncMock(), AsyncMock(), AsyncMock()
    tab1 = Connection(websocket=ws1, document_id="doc-1", user_id="u1", user_name="Alice", user_email="a@e.com")
    tab2 = Connection(websocket=ws2, document_id="doc-1", user_id="u1", user_name="Alice", user_email="a@e.com")
    other = Connection(websocket=ws3, document_id="doc-1", user_id="u2", user_name="Bob", user_email="b@e.com")
    manager._connections["doc-1"] = [tab1, tab2, other]

    asyncio.run(manager.broadcast_cursor("doc-1", tab1, {"from": 1, "to": 2, "empty": False}))

    ws1.send_text.assert_not_called()
    ws2.send_text.assert_not_called()
    ws3.send_text.assert_called_once()


def test_ws_cursor_message_broadcasts_to_others(ws_client):
    with patch(
        "app.api.routers.ws.verify_id_token",
        side_effect=lambda token: SECOND_DECODED_TOKEN if token == "token-b" else FAKE_DECODED_TOKEN,
    ), patch(
        "app.api.routers.ws.get_document_with_role", return_value=(FAKE_DOC, "owner")
    ):
        with ws_client.websocket_connect("/ws/documents/doc-1?token=good") as ws1:
            json.loads(ws1.receive_text())  # presence_list

            with ws_client.websocket_connect("/ws/documents/doc-1?token=token-b") as ws2:
                json.loads(ws2.receive_text())  # presence_list for ws2
                # ws1 receives presence + presence_list for ws2
                for _ in range(2):
                    json.loads(ws1.receive_text())

                # ws2 sends a cursor message
                ws2.send_text(json.dumps({"type": "cursor", "from": 3, "to": 7, "empty": False}))

                # ws1 should receive the cursor broadcast
                msg = json.loads(ws1.receive_text())
                assert msg["type"] == "cursor"
                assert msg["from"] == 3
                assert msg["to"] == 7
