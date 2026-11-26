import uuid

import pytest
from fastapi import HTTPException

from app.config import settings
from app.db import get_db, init_db
from app.tenant_core import init_tenant_schema
from app.schemas import WorkspaceMemberAdd, WorkspaceMemberUpdate
from app.workspaces import add_workspace_member, update_member_role, list_workspace_members


@pytest.fixture
def rbac_fixture(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db_file = str(tmp_path / "workspace_rbac.db")
    monkeypatch.setattr(settings, "DB_PATH", db_file)
    init_db(db_file)
    owner, admin, target, stale = [str(uuid.uuid4()) for _ in range(4)]
    workspace, tenant = str(uuid.uuid4()), str(uuid.uuid4())
    with get_db(db_file) as conn:
        for uid, email in [
            (owner, "owner@rbac.test"), (admin, "admin@rbac.test"),
            (target, "target@rbac.test"), (stale, "stale@rbac.test"),
        ]:
            conn.execute(
                "INSERT INTO users(id,email,full_name,hashed_password) VALUES(?,?,?,?)",
                (uid, email, email, "hash"),
            )
        conn.execute(
            "INSERT INTO workspaces(id,name,slug,created_by) VALUES(?,?,?,?)",
            (workspace, "RBAC Workspace", "rbac-workspace", owner),
        )
    init_tenant_schema()
    with get_db(db_file) as conn:
        conn.execute(
            "INSERT INTO tenants(id,name,slug,created_by) VALUES(?,?,?,?)",
            (tenant, "RBAC Tenant", "rbac-tenant", owner),
        )
        for uid, role in [(owner, "owner"), (admin, "member"), (target, "member")]:
            conn.execute(
                "INSERT INTO tenant_memberships(id,tenant_id,user_id,role) VALUES(?,?,?,?)",
                (str(uuid.uuid4()), tenant, uid, role),
            )
        for uid, role in [(owner, "owner"), (admin, "admin"), (stale, "viewer")]:
            conn.execute(
                "INSERT INTO workspace_members(id,workspace_id,user_id,role) VALUES(?,?,?,?)",
                (str(uuid.uuid4()), workspace, uid, role),
            )
        conn.execute("UPDATE workspaces SET tenant_id=? WHERE id=?", (tenant, workspace))
    return {"workspace": workspace, "owner": owner, "admin": admin, "target": target, "stale": stale}


def test_admin_cannot_grant_owner_role(rbac_fixture):
    f = rbac_fixture
    with pytest.raises(HTTPException) as exc:
        add_workspace_member(
            f["workspace"],
            WorkspaceMemberAdd(email="target@rbac.test", role="owner"),
            current_user={"id": f["admin"]},
        )
    assert exc.value.status_code == 403


def test_unknown_role_is_rejected(rbac_fixture):
    f = rbac_fixture
    with pytest.raises(HTTPException) as exc:
        update_member_role(
            f["workspace"], f["target"], WorkspaceMemberUpdate(role="superuser"),
            current_user={"id": f["owner"]},
        )
    assert exc.value.status_code == 400


def test_last_owner_cannot_be_demoted(rbac_fixture):
    f = rbac_fixture
    with pytest.raises(HTTPException) as exc:
        update_member_role(
            f["workspace"], f["owner"], WorkspaceMemberUpdate(role="viewer"),
            current_user={"id": f["owner"]},
        )
    assert exc.value.status_code == 400


def test_member_listing_hides_workspace_members_without_tenant_membership(rbac_fixture):
    f = rbac_fixture
    rows = list_workspace_members(f["workspace"], current_user={"id": f["owner"]})
    assert f["stale"] not in {row["user_id"] for row in rows}
