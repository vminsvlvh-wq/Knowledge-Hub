import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import settings
from app.main import app


def test_http_only_cookie_authenticates_websocket_and_query_token_is_rejected(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "ws-auth.db"))
    with TestClient(app) as client:
        registered = client.post("/api/v1/auth/register", json={
            "email": "ws-cookie@example.test",
            "full_name": "WebSocket Cookie",
            "password": "Password123",
        })
        assert registered.status_code == 201
        token = registered.json()["access_token"]
        cookie = registered.headers.get("set-cookie", "").lower()
        assert "ki_access_token=" in cookie
        assert "httponly" in cookie
        assert "samesite=lax" in cookie

        headers = {"Authorization": f"Bearer {token}"}
        workspace = client.post("/api/v1/workspaces", json={
            "name": "WebSocket Test", "slug": "websocket-test", "description": ""
        }, headers=headers)
        assert workspace.status_code == 201
        doc = client.post(
            f"/api/v1/workspaces/{workspace.json()['id']}/documents",
            json={"title": "Realtime", "content": "private text", "content_type": "markdown"},
            headers=headers,
        )
        assert doc.status_code == 201
        document_id = doc.json()["id"]

        with client.websocket_connect(
            f"/ws/documents/{document_id}",
            headers={"Origin": "http://testserver", "Cookie": f"ki_access_token={token}"},
        ) as socket:
            assert socket.receive_json()["type"] == "init"

        # The HTTP client retains login cookies; remove it so this request proves
        # that a query-string token alone is rejected.
        client.cookies.delete("ki_access_token")
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                f"/ws/documents/{document_id}?token={token}",
                headers={"Origin": "http://testserver"},
            ):
                pass

        logout = client.post("/api/v1/auth/logout")
        assert logout.status_code == 204
        assert "max-age=0" in logout.headers.get("set-cookie", "").lower()
