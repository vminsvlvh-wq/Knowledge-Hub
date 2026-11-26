import uuid
import pytest
from fastapi import HTTPException

from app.config import settings
from app.db import get_db, init_db
from app.tenant_core import init_tenant_schema


def test_legacy_workspaces_are_backfilled_into_separate_tenants(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db_file = str(tmp_path / "tenancy.db")
    monkeypatch.setattr(settings, "DB_PATH", db_file)
    init_db(db_file)

    user_a, user_b = str(uuid.uuid4()), str(uuid.uuid4())
    ws_a, ws_b = str(uuid.uuid4()), str(uuid.uuid4())
    with get_db(db_file) as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO users(id,email,full_name,hashed_password) VALUES(?,?,?,?)",
                    (user_a, "a@example.test", "A", "hash"))
        cur.execute("INSERT INTO users(id,email,full_name,hashed_password) VALUES(?,?,?,?)",
                    (user_b, "b@example.test", "B", "hash"))
        cur.execute("INSERT INTO workspaces(id,name,slug,created_by) VALUES(?,?,?,?)",
                    (ws_a, "Org A", "org-a", user_a))
        cur.execute("INSERT INTO workspaces(id,name,slug,created_by) VALUES(?,?,?,?)",
                    (ws_b, "Org B", "org-b", user_b))
        cur.execute("INSERT INTO workspace_members(id,workspace_id,user_id,role) VALUES(?,?,?,'owner')",
                    (str(uuid.uuid4()), ws_a, user_a))
        cur.execute("INSERT INTO workspace_members(id,workspace_id,user_id,role) VALUES(?,?,?,'owner')",
                    (str(uuid.uuid4()), ws_b, user_b))

    init_tenant_schema()

    with get_db(db_file) as conn:
        cur = conn.cursor()
        cur.execute("SELECT tenant_id FROM workspaces WHERE id=?", (ws_a,))
        tenant_a = cur.fetchone()["tenant_id"]
        cur.execute("SELECT tenant_id FROM workspaces WHERE id=?", (ws_b,))
        tenant_b = cur.fetchone()["tenant_id"]
        assert tenant_a and tenant_b and tenant_a != tenant_b
        cur.execute("SELECT COUNT(*) AS n FROM tenant_memberships WHERE tenant_id=? AND user_id=?",
                    (tenant_a, user_a))
        assert cur.fetchone()["n"] == 1
        cur.execute("SELECT COUNT(*) AS n FROM tenant_memberships WHERE tenant_id=? AND user_id=?",
                    (tenant_a, user_b))
        assert cur.fetchone()["n"] == 0


def test_tenant_bootstrap_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db_file = str(tmp_path / "tenancy_idempotent.db")
    monkeypatch.setattr(settings, "DB_PATH", db_file)
    init_db(db_file)
    init_tenant_schema()
    init_tenant_schema()
    with get_db(db_file) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS n FROM tenants")
        assert cur.fetchone()["n"] == 0


def test_document_direct_grant_cannot_cross_tenant_boundary(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db_file = str(tmp_path / "tenant_boundary.db")
    monkeypatch.setattr(settings, "DB_PATH", db_file)
    init_db(db_file)

    owner_id, outsider_id = str(uuid.uuid4()), str(uuid.uuid4())
    workspace_id, document_id = str(uuid.uuid4()), str(uuid.uuid4())
    with get_db(db_file) as conn:
        cur = conn.cursor()
        for uid, email in ((owner_id, "owner@tenant.test"), (outsider_id, "outsider@tenant.test")):
            cur.execute("INSERT INTO users(id,email,full_name,hashed_password) VALUES(?,?,?,?)",
                        (uid, email, email, "hash"))
        cur.execute("INSERT INTO workspaces(id,name,slug,created_by) VALUES(?,?,?,?)",
                    (workspace_id, "Private Workspace", "private-workspace", owner_id))
        cur.execute("INSERT INTO workspace_members(id,workspace_id,user_id,role) VALUES(?,?,?,'owner')",
                    (str(uuid.uuid4()), workspace_id, owner_id))

    init_tenant_schema()
    with get_db(db_file) as conn:
        cur = conn.cursor()
        cur.execute("SELECT tenant_id FROM workspaces WHERE id=?", (workspace_id,))
        tenant_id = cur.fetchone()["tenant_id"]
        outsider_tenant = str(uuid.uuid4())
        cur.execute("INSERT INTO tenants(id,name,slug,created_by) VALUES(?,?,?,?)",
                    (outsider_tenant, "Outsider Org", "outsider-org", outsider_id))
        cur.execute("INSERT INTO tenant_memberships(id,tenant_id,user_id,role) VALUES(?,?,?,'owner')",
                    (str(uuid.uuid4()), outsider_tenant, outsider_id))
        cur.execute("INSERT INTO documents(id,workspace_id,title,content,created_by) VALUES(?,?,?,?,?)",
                    (document_id, workspace_id, "Secret", "Tenant-only content", owner_id))
        # Even an accidentally created direct grant must not bypass tenant isolation.
        cur.execute("INSERT INTO document_permissions(id,document_id,user_id,permission) VALUES(?,?,?,'view')",
                    (str(uuid.uuid4()), document_id, outsider_id))

    from app.rbac import check_document_access
    with pytest.raises(HTTPException) as exc:
        check_document_access(document_id, outsider_id, "view")
    assert exc.value.status_code == 403


def test_workspace_role_requires_tenant_membership(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db_file = str(tmp_path / "workspace_tenant_boundary.db")
    monkeypatch.setattr(settings, "DB_PATH", db_file)
    init_db(db_file)

    owner_id, outsider_id = str(uuid.uuid4()), str(uuid.uuid4())
    workspace_id = str(uuid.uuid4())
    with get_db(db_file) as conn:
        cur = conn.cursor()
        for uid, email in ((owner_id, "owner2@tenant.test"), (outsider_id, "outsider2@tenant.test")):
            cur.execute("INSERT INTO users(id,email,full_name,hashed_password) VALUES(?,?,?,?)",
                        (uid, email, email, "hash"))
        cur.execute("INSERT INTO workspaces(id,name,slug,created_by) VALUES(?,?,?,?)",
                    (workspace_id, "Workspace", "workspace-tenant", owner_id))
        cur.execute("INSERT INTO workspace_members(id,workspace_id,user_id,role) VALUES(?,?,?,'owner')",
                    (str(uuid.uuid4()), workspace_id, owner_id))
    init_tenant_schema()
    # Simulate a stale/incorrect workspace grant without corresponding tenant membership.
    with get_db(db_file) as conn:
        conn.execute("INSERT INTO workspace_members(id,workspace_id,user_id,role) VALUES(?,?,?,'viewer')",
                     (str(uuid.uuid4()), workspace_id, outsider_id))
    from app.rbac import Role, require_workspace_role
    with pytest.raises(HTTPException) as exc:
        require_workspace_role(workspace_id, outsider_id, Role.GUEST)
    assert exc.value.status_code == 403
