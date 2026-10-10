import os
import sys
import tempfile
import json
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.db import init_db
from app.main import app
from fastapi.testclient import TestClient

class TestKnowledgeManagementBackend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.temp_db.close()
        settings.DB_PATH = cls.temp_db.name
        init_db(cls.temp_db.name)
        cls.client = TestClient(app)

        # 1. Register Users at setup
        resp = cls.client.post("/api/v1/auth/register", json={
            "email": "owner@enterprise.com",
            "full_name": "مدير النظام",
            "password": "Password123"
        })
        assert resp.status_code == 201, resp.text
        cls.owner_token = resp.json()["access_token"]
        cls.owner_id = resp.json()["user"]["id"]

        resp = cls.client.post("/api/v1/auth/register", json={
            "email": "editor@enterprise.com",
            "full_name": "سارة المحررة",
            "password": "Password123"
        })
        assert resp.status_code == 201, resp.text
        cls.editor_token = resp.json()["access_token"]
        cls.editor_id = resp.json()["user"]["id"]

        resp = cls.client.post("/api/v1/auth/register", json={
            "email": "viewer@enterprise.com",
            "full_name": "أحمد القارئ",
            "password": "Password123"
        })
        assert resp.status_code == 201, resp.text
        cls.viewer_token = resp.json()["access_token"]
        cls.viewer_id = resp.json()["user"]["id"]

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.temp_db.name):
            os.remove(cls.temp_db.name)

    def test_01_health_check(self):
        # Verify frontend serving on root
        resp_ui = self.client.get("/")
        self.assertEqual(resp_ui.status_code, 200)
        self.assertIn("KnowledgeHub", resp_ui.text)

        # Verify health endpoint
        resp_health = self.client.get("/api/health")
        self.assertEqual(resp_health.status_code, 200)
        self.assertEqual(resp_health.json()["status"], "online")

    def test_02_login_and_me(self):
        resp = self.client.post("/api/v1/auth/login", json={
            "email": "owner@enterprise.com",
            "password": "Password123"
        })
        self.assertEqual(resp.status_code, 200)
        token = resp.json()["access_token"]

        me_resp = self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_resp.status_code, 200)
        self.assertEqual(me_resp.json()["email"], "owner@enterprise.com")

    def test_03_workspaces_and_rbac(self):
        headers_owner = {"Authorization": f"Bearer {self.owner_token}"}
        headers_editor = {"Authorization": f"Bearer {self.editor_token}"}
        headers_viewer = {"Authorization": f"Bearer {self.viewer_token}"}

        # 1. Create Workspace
        ws_resp = self.client.post("/api/v1/workspaces", json={
            "name": "فريق الهندسة والبحث",
            "slug": "engineering-rnd",
            "description": "مساحة إدارة معرفة وتوثيق المشروعات الهندسية"
        }, headers=headers_owner)
        self.assertEqual(ws_resp.status_code, 201)
        TestKnowledgeManagementBackend.ws_id = ws_resp.json()["id"]

        # 2. Add Editor
        add_editor_resp = self.client.post(f"/api/v1/workspaces/{self.ws_id}/members", json={
            "email": "editor@enterprise.com",
            "role": "editor"
        }, headers=headers_owner)
        self.assertEqual(add_editor_resp.status_code, 201)

        # 3. Add Viewer
        add_viewer_resp = self.client.post(f"/api/v1/workspaces/{self.ws_id}/members", json={
            "email": "viewer@enterprise.com",
            "role": "viewer"
        }, headers=headers_owner)
        self.assertEqual(add_viewer_resp.status_code, 201)

        # 4. Viewer cannot add members
        forbidden_add = self.client.post(f"/api/v1/workspaces/{self.ws_id}/members", json={
            "email": "nonexistent@enterprise.com",
            "role": "editor"
        }, headers=headers_viewer)
        self.assertEqual(forbidden_add.status_code, 403)

        # 5. List members
        members_resp = self.client.get(f"/api/v1/workspaces/{self.ws_id}/members", headers=headers_viewer)
        self.assertEqual(members_resp.status_code, 200)
        self.assertEqual(len(members_resp.json()), 3)

    def test_04_document_hierarchy_and_permissions(self):
        headers_editor = {"Authorization": f"Bearer {self.editor_token}"}
        headers_viewer = {"Authorization": f"Bearer {self.viewer_token}"}

        # 1. Create Root Document
        root_resp = self.client.post(f"/api/v1/workspaces/{self.ws_id}/documents", json={
            "title": "مجلد البنية التحتية",
            "content": "# وثائق البنية التحتية والمخدمات",
            "content_type": "markdown"
        }, headers=headers_editor)
        self.assertEqual(root_resp.status_code, 201)
        root_id = root_resp.json()["id"]

        # 2. Create Child Document
        child_resp = self.client.post(f"/api/v1/workspaces/{self.ws_id}/documents", json={
            "title": "إعدادات قواعد البيانات",
            "parent_id": root_id,
            "content": "تفاصيل إعداد PostgreSQL وRedis للمزامنة.",
            "content_type": "markdown"
        }, headers=headers_editor)
        self.assertEqual(child_resp.status_code, 201)
        child_id = child_resp.json()["id"]
        TestKnowledgeManagementBackend.child_doc_id = child_id

        # 3. Document Tree
        tree_resp = self.client.get(f"/api/v1/workspaces/{self.ws_id}/documents", headers=headers_viewer)
        self.assertEqual(tree_resp.status_code, 200)
        tree = tree_resp.json()
        self.assertEqual(len(tree), 1)
        self.assertEqual(tree[0]["id"], root_id)
        self.assertEqual(len(tree[0]["children"]), 1)
        self.assertEqual(tree[0]["children"][0]["id"], child_id)

        # 4. Viewer reads child -> 200
        view_resp = self.client.get(f"/api/v1/documents/{child_id}", headers=headers_viewer)
        self.assertEqual(view_resp.status_code, 200)

        # 5. Viewer edits child -> 403 Forbidden
        unauth_edit = self.client.put(f"/api/v1/documents/{child_id}", json={
            "title": "محاولة تعديل غير مصرح بها",
            "content": "نص خبيث"
        }, headers=headers_viewer)
        self.assertEqual(unauth_edit.status_code, 403)

        # 6. Editor edits child -> 200 OK & Version created
        edit_resp = self.client.put(f"/api/v1/documents/{child_id}", json={
            "title": "إعدادات قواعد البيانات (محدثة)",
            "content": "محتوى محدث مع توثيق إضافي لـ Yjs وWebSocket.",
            "change_summary": "إضافة تفاصيل المزامنة اللحظية"
        }, headers=headers_editor)
        self.assertEqual(edit_resp.status_code, 200)

        # 7. Check Version History
        versions_resp = self.client.get(f"/api/v1/documents/{child_id}/versions", headers=headers_viewer)
        self.assertEqual(versions_resp.status_code, 200)
        self.assertEqual(len(versions_resp.json()), 2)
        self.assertEqual(versions_resp.json()[0]["version_number"], 2)

    def test_05_websocket_collaboration(self):
        ws_editor_url = f"/ws/documents/{self.child_doc_id}?token={self.editor_token}"
        with self.client.websocket_connect(ws_editor_url) as ws_editor:
            init_msg = ws_editor.receive_text()
            data = json.loads(init_msg)
            self.assertEqual(data["type"], "init")
            self.assertEqual(data["document_id"], self.child_doc_id)

            # Test ping/pong
            ws_editor.send_text(json.dumps({"type": "ping"}))
            pong_msg = ws_editor.receive_text()
            self.assertEqual(json.loads(pong_msg)["type"], "pong")

            # Connect Viewer
            ws_viewer_url = f"/ws/documents/{self.child_doc_id}?token={self.viewer_token}"
            with self.client.websocket_connect(ws_viewer_url) as ws_viewer:
                viewer_init = ws_viewer.receive_text()
                self.assertEqual(json.loads(viewer_init)["type"], "init")

                joined_event = ws_editor.receive_text()
                self.assertEqual(json.loads(joined_event)["type"], "presence:joined")

                # Move Cursor
                ws_editor.send_text(json.dumps({
                    "type": "cursor",
                    "position": {"line": 5, "ch": 12}
                }))
                cursor_event = ws_viewer.receive_text()
                self.assertEqual(json.loads(cursor_event)["type"], "presence:cursor")

                # Content update
                ws_editor.send_text(json.dumps({
                    "type": "content_update",
                    "content": "تعديل فوري أثناء البث المباشر."
                }))
                update_event = ws_viewer.receive_text()
                self.assertEqual(json.loads(update_event)["type"], "content_updated")
                self.assertEqual(json.loads(update_event)["content"], "تعديل فوري أثناء البث المباشر.")

if __name__ == "__main__":
    unittest.main()
