import uuid

from app.config import settings
from app.db import get_db, init_db
from app.migrations import run_migrations


def test_versioned_migrations_backfill_legacy_workspaces_and_vectors(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db_file = str(tmp_path / "legacy.db")
    monkeypatch.setattr(settings, "DB_PATH", db_file)
    init_db(db_file)

    owner_id, member_id = str(uuid.uuid4()), str(uuid.uuid4())
    workspace_id, document_id, chunk_id = [str(uuid.uuid4()) for _ in range(3)]
    with get_db(db_file) as conn:
        for uid, email in [(owner_id, "legacy-owner@test.invalid"),
                           (member_id, "legacy-member@test.invalid")]:
            conn.execute(
                "INSERT INTO users(id,email,full_name,hashed_password) VALUES(?,?,?,?)",
                (uid, email, email, "hash"),
            )
        conn.execute(
            "INSERT INTO workspaces(id,name,slug,created_by) VALUES(?,?,?,?)",
            (workspace_id, "Legacy workspace", "legacy-workspace", owner_id),
        )
        conn.execute(
            "INSERT INTO workspace_members(id,workspace_id,user_id,role) VALUES(?,?,?,'editor')",
            (str(uuid.uuid4()), workspace_id, member_id),
        )
        conn.execute(
            "INSERT INTO documents(id,workspace_id,title,content,created_by) VALUES(?,?,?,?,?)",
            (document_id, workspace_id, "Legacy document", "content", owner_id),
        )
        conn.execute(
            "INSERT INTO document_chunks(id,document_id,workspace_id,chunk_index,content,embedding) VALUES(?,?,?,?,?,?)",
            (chunk_id, document_id, workspace_id, 0, "content", b"legacy-vector"),
        )

    first = run_migrations()
    second = run_migrations()
    assert first["applied"] == [1, 2]
    assert second["applied"] == []

    with get_db(db_file) as conn:
        workspace = conn.execute(
            "SELECT tenant_id FROM workspaces WHERE id=?", (workspace_id,)
        ).fetchone()
        tenant_id = workspace["tenant_id"]
        assert tenant_id
        roles = {
            row["user_id"]: row["role"]
            for row in conn.execute(
                "SELECT user_id,role FROM tenant_memberships WHERE tenant_id=?",
                (tenant_id,),
            ).fetchall()
        }
        assert roles[owner_id] == "owner"
        assert roles[member_id] == "member"
        chunk = conn.execute(
            "SELECT tenant_id FROM document_chunks WHERE id=?", (chunk_id,)
        ).fetchone()
        assert chunk["tenant_id"] == tenant_id
        versions = conn.execute(
            "SELECT version,name FROM schema_migrations ORDER BY version"
        ).fetchall()
        assert [(row["version"], row["name"]) for row in versions] == [
            (1, "tenant_foundation"), (2, "tenant_audit_events")
        ]
