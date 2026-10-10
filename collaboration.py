import uuid
import json
from typing import Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from app.db import get_db
from app.auth import decode_access_token
from app.rbac import check_document_access

router = APIRouter(tags=["التحرير التعاوني اللحظي (Real-time Collaboration)"])

class DocumentRoomManager:
    def __init__(self):
        # document_id -> {websocket: user_data}
        self.rooms: Dict[str, Dict[WebSocket, dict]] = {}

    async def connect(self, document_id: str, websocket: WebSocket, user_data: dict):
        await websocket.accept()
        if document_id not in self.rooms:
            self.rooms[document_id] = {}
        self.rooms[document_id][websocket] = user_data

    def disconnect(self, document_id: str, websocket: WebSocket) -> dict:
        user_data = None
        if document_id in self.rooms and websocket in self.rooms[document_id]:
            user_data = self.rooms[document_id].pop(websocket)
            if not self.rooms[document_id]:
                del self.rooms[document_id]
        return user_data

    async def broadcast(self, document_id: str, message: dict, exclude: WebSocket = None):
        if document_id in self.rooms:
            payload = json.dumps(message, ensure_ascii=False)
            for ws in list(self.rooms[document_id].keys()):
                if ws != exclude:
                    try:
                        await ws.send_text(payload)
                    except Exception:
                        pass

    def get_room_users(self, document_id: str) -> list:
        if document_id not in self.rooms:
            return []
        users = []
        seen_ids = set()
        for user in self.rooms[document_id].values():
            if user["id"] not in seen_ids:
                seen_ids.add(user["id"])
                users.append({
                    "id": user["id"],
                    "full_name": user["full_name"],
                    "email": user["email"],
                    "color": user.get("color", "#3B82F6")
                })
        return users

collab_manager = DocumentRoomManager()

USER_COLORS = ["#EF4444", "#3B82F6", "#10B981", "#F59E0B", "#8B5CF6", "#EC4899", "#14B8A6"]

@router.websocket("/ws/documents/{document_id}")
async def collaborative_editing_ws(
    websocket: WebSocket,
    document_id: str,
    token: str = Query(...)
):
    # 1. Authenticate user from JWT token
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 2. Verify user exists and retrieve profile
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, full_name FROM users WHERE id = ?", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        user = dict(user_row)

    # 3. Check document permission (RBAC)
    try:
        doc = check_document_access(document_id, user_id, required_permission="view")
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    color_idx = hash(user_id) % len(USER_COLORS)
    user["color"] = USER_COLORS[color_idx]

    # 4. Join room
    await collab_manager.connect(document_id, websocket, user)

    # 5. Send initial state to the newly connected user
    active_users = collab_manager.get_room_users(document_id)
    await websocket.send_text(json.dumps({
        "type": "init",
        "document_id": document_id,
        "title": doc["title"],
        "content": doc["content"],
        "active_users": active_users,
        "your_user_id": user_id
    }, ensure_ascii=False))

    # 6. Notify others that user joined
    await collab_manager.broadcast(document_id, {
        "type": "presence:joined",
        "user": {
            "id": user["id"],
            "full_name": user["full_name"],
            "color": user["color"]
        }
    }, exclude=websocket)

    # 7. Listen for collaborative events
    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                msg = json.loads(raw_data)
            except Exception:
                continue

            event_type = msg.get("type")

            # A. Cursor movement & selection broadcast
            if event_type == "cursor":
                await collab_manager.broadcast(document_id, {
                    "type": "presence:cursor",
                    "user_id": user_id,
                    "position": msg.get("position"), # e.g. {"line": 10, "ch": 5}
                    "selection": msg.get("selection")
                }, exclude=websocket)

            # B. Content edits / delta broadcasting
            elif event_type == "content_update":
                new_content = msg.get("content", "")
                # Broadcast real-time update to all collaborators
                await collab_manager.broadcast(document_id, {
                    "type": "content_updated",
                    "user_id": user_id,
                    "content": new_content,
                    "delta": msg.get("delta")
                }, exclude=websocket)

                # Update database content
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE documents SET content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (new_content, document_id)
                    )

            # C. Save Version Snapshot
            elif event_type == "save_snapshot":
                summary = msg.get("summary", "حفظ تلقائي للنسخة")
                content_to_save = msg.get("content")
                with get_db() as conn:
                    cursor = conn.cursor()
                    if content_to_save is None:
                        cursor.execute("SELECT content FROM documents WHERE id = ?", (document_id,))
                        row = cursor.fetchone()
                        content_to_save = row["content"] if row else ""
                    
                    cursor.execute(
                        "SELECT COALESCE(MAX(version_number), 0) + 1 AS next_ver FROM document_versions WHERE document_id = ?",
                        (document_id,)
                    )
                    next_ver = cursor.fetchone()["next_ver"]
                    ver_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO document_versions (id, document_id, version_number, content, change_summary, created_by)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (ver_id, document_id, next_ver, content_to_save, summary, user_id))

                await websocket.send_text(json.dumps({
                    "type": "snapshot_saved",
                    "version_number": next_ver,
                    "version_id": ver_id
                }, ensure_ascii=False))

            elif event_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        left_user = collab_manager.disconnect(document_id, websocket)
        if left_user:
            await collab_manager.broadcast(document_id, {
                "type": "presence:left",
                "user_id": left_user["id"],
                "full_name": left_user["full_name"]
            })
