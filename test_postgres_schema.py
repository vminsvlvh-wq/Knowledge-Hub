import os
import uuid
import pytest
from fastapi import HTTPException

from app.db import get_db, init_db
from app.tenant_core import init_tenant_schema
from app.rbac import Role, require_workspace_role, check_document_access


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="PostgreSQL integration test only")
def test_postgres_tenant_schema_and_authorization():
    init_db()
    init_tenant_schema()

    owner_id, outsider_id = str(uuid.uuid4()), str(uuid.uuid4())
    workspace_id, document_id = str(uuid.uuid4()), str(uuid.uuid4())
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO users(id,email,full_name,hashed_password) VALUES(?,?,?,?)",
                    (owner_id, f"{owner_id}@ki.test", "Owner", "hash"))
        cur.execute("INSERT INTO users(id,email,full_name,hashed_password) VALUES(?,?,?,?)",
                    (outsider_id, f"{outsider_id}@ki.test", "Outsider", "hash"))
        cur.execute("INSERT INTO workspaces(id,name,slug,created_by) VALUES(?,?,?,?)",
                    (workspace_id, "Postgres Workspace", f"ws-{workspace_id[:8]}", owner_id))
        cur.execute("INSERT INTO workspace_members(id,workspace_id,user_id,role) VALUES(?,?,?,'owner')",
                    (str(uuid.uuid4()), workspace_id, owner_id))

    init_tenant_schema()

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT tenant_id FROM workspaces WHERE id=?", (workspace_id,))
        tenant_id = cur.fetchone()["tenant_id"]
        assert tenant_id
        cur.execute("INSERT INTO tenants(id,name,slug,created_by) VALUES(?,?,?,?)",
                    (str(uuid.uuid4()), "Outsider Tenant", f"out-{outsider_id[:8]}", outsider_id))
        cur.execute("INSERT INTO tenant_memberships(id,tenant_id,user_id,role) VALUES(?,?,?,'owner')",
                    (str(uuid.uuid4()), cur.execute("SELECT id FROM tenants WHERE slug=?", (f"out-{outsider_id[:8]}",)).fetchone()["id"], outsider_id))
        cur.execute("INSERT INTO documents(id,workspace_id,title,content,created_by) VALUES(?,?,?,?,?)",
                    (document_id, workspace_id, "Private", "private evidence", owner_id))
        cur.execute("INSERT INTO document_permissions(id,document_id,user_id,permission) VALUES(?,?,?,'view')",
                    (str(uuid.uuid4()), document_id, outsider_id))

    require_workspace_role(workspace_id, owner_id, Role.OWNER)
    with pytest.raises(HTTPException) as exc:
        check_document_access(document_id, outsider_id, "view")
    assert exc.value.status_code == 403
