import uuid
import os
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.auth import get_current_user
from app.db import get_db

router = APIRouter(prefix="/tenants", tags=["KI Tenancy"])

class TenantCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9-]*$")

class TenantMemberAdd(BaseModel):
    email: str = Field(min_length=5, max_length=254)

def init_tenant_schema():
    """Additive, idempotent bootstrap migration. Existing workspaces are isolated individually."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS tenants (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
            created_by TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE CASCADE
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS audit_events (
            id TEXT PRIMARY KEY, tenant_id TEXT, actor_id TEXT NOT NULL,
            action TEXT NOT NULL, resource_type TEXT NOT NULL, resource_id TEXT NOT NULL,
            details_json TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(tenant_id) REFERENCES tenants(id) ON DELETE SET NULL,
            FOREIGN KEY(actor_id) REFERENCES users(id) ON DELETE RESTRICT
        )""")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_tenant_created ON audit_events(tenant_id, created_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_events(resource_type, resource_id, created_at)")
        cur.execute("""CREATE TABLE IF NOT EXISTS tenant_memberships (
            id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, user_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('owner','admin','member')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(tenant_id,user_id),
            FOREIGN KEY(tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )""")
        if os.getenv("DATABASE_URL", "").strip():
            # PostgreSQL supports IF NOT EXISTS; avoid swallowing SQL errors because
            # PostgreSQL marks the whole transaction failed after a DDL exception.
            cur.execute("ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS tenant_id TEXT")
        else:
            cur.execute("PRAGMA table_info(workspaces)")
            columns = {row["name"] for row in cur.fetchall()}
            if "tenant_id" not in columns:
                cur.execute("ALTER TABLE workspaces ADD COLUMN tenant_id TEXT")
        cur.execute("SELECT id, name, slug, created_by, tenant_id FROM workspaces")
        for ws in cur.fetchall():
            if ws["tenant_id"]:
                continue
            tenant_id = str(uuid.uuid4())
            tenant_slug = ("legacy-" + str(ws["id"]).replace("-", ""))[:80]
            cur.execute("INSERT INTO tenants(id,name,slug,created_by) VALUES(?,?,?,?)",
                        (tenant_id, ws["name"], tenant_slug, ws["created_by"]))
            cur.execute("UPDATE workspaces SET tenant_id=? WHERE id=?", (tenant_id, ws["id"]))
            cur.execute("""INSERT INTO tenant_memberships(id,tenant_id,user_id,role)
                            VALUES(?,?,?,'owner')""",
                        (str(uuid.uuid4()), tenant_id, ws["created_by"]))
            cur.execute("SELECT user_id, role FROM workspace_members WHERE workspace_id=?", (ws["id"],))
            for member in cur.fetchall():
                cur.execute("""INSERT INTO tenant_memberships(id,tenant_id,user_id,role)
                               VALUES(?,?,?,'member') ON CONFLICT(tenant_id,user_id) DO NOTHING""",
                            (str(uuid.uuid4()), tenant_id, member["user_id"]))

        # Backfill pre-existing vector rows after all legacy workspaces have tenants.
        cur.execute("""UPDATE document_chunks
                       SET tenant_id=(SELECT w.tenant_id FROM workspaces w
                                      WHERE w.id=document_chunks.workspace_id)
                       WHERE tenant_id IS NULL
                         AND EXISTS (SELECT 1 FROM workspaces w
                                     WHERE w.id=document_chunks.workspace_id
                                       AND w.tenant_id IS NOT NULL)""")

@router.post("", status_code=status.HTTP_201_CREATED)
def create_tenant(payload: TenantCreate, user=Depends(get_current_user)):
    tenant_id = str(uuid.uuid4())
    slug = payload.slug.lower().strip()
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM tenants WHERE slug=?", (slug,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="معرّف المؤسسة مستخدم بالفعل")
        cur.execute("INSERT INTO tenants(id,name,slug,created_by) VALUES(?,?,?,?)",
                    (tenant_id, payload.name.strip(), slug, user["id"]))
        cur.execute("INSERT INTO tenant_memberships(id,tenant_id,user_id,role) VALUES(?,?,?,'owner')",
                    (str(uuid.uuid4()), tenant_id, user["id"]))
    from app.audit import record_audit_event
    record_audit_event(user["id"], "tenant.created", "tenant", tenant_id, tenant_id,
                       {"slug": slug})
    return {"id": tenant_id, "name": payload.name.strip(), "slug": slug, "role": "owner"}

@router.get("")
def list_my_tenants(user=Depends(get_current_user)):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""SELECT t.id,t.name,t.slug,tm.role
                       FROM tenants t JOIN tenant_memberships tm ON tm.tenant_id=t.id
                       WHERE tm.user_id=? ORDER BY t.created_at DESC""", (user["id"],))
        return [dict(row) for row in cur.fetchall()]


@router.post("/{tenant_id}/members", status_code=status.HTTP_201_CREATED)
def add_tenant_member(tenant_id: str, payload: TenantMemberAdd, user=Depends(get_current_user)):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT role FROM tenant_memberships WHERE tenant_id=? AND user_id=?",
                    (tenant_id, user["id"]))
        actor = cur.fetchone()
        if not actor or actor["role"] not in ("owner", "admin"):
            raise HTTPException(status_code=403, detail="صلاحية مالك أو مدير المؤسسة مطلوبة")
        cur.execute("SELECT id,email,full_name FROM users WHERE email=?",
                    (payload.email.lower().strip(),))
        target = cur.fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="المستخدم غير مسجل في النظام")
        cur.execute("""INSERT INTO tenant_memberships(id,tenant_id,user_id,role)
                       VALUES(?,?,?,'member') ON CONFLICT(tenant_id,user_id) DO NOTHING""",
                    (str(uuid.uuid4()), tenant_id, target["id"]))
    from app.audit import record_audit_event
    record_audit_event(user["id"], "tenant.member_added", "tenant_member", target["id"],
                       tenant_id, {"role": "member"})
    return {"tenant_id": tenant_id, "user_id": target["id"], "email": target["email"], "role": "member"}

@router.get("/{tenant_id}/audit-events")
def list_tenant_audit_events(
    tenant_id: str, limit: int = 100, offset: int = 0, user=Depends(get_current_user)
):
    if limit < 1 or limit > 200 or offset < 0:
        raise HTTPException(status_code=400, detail="قيم pagination غير صالحة")
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT role FROM tenant_memberships WHERE tenant_id=? AND user_id=?",
                    (tenant_id, user["id"]))
        actor = cur.fetchone()
        if not actor or actor["role"] not in ("owner", "admin"):
            raise HTTPException(status_code=403, detail="سجل التدقيق متاح لمالك أو مدير المؤسسة فقط")
        rows = cur.execute(
            """SELECT id, actor_id, action, resource_type, resource_id, details_json, created_at
               FROM audit_events WHERE tenant_id=?
               ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?""",
            (tenant_id, limit, offset),
        ).fetchall()
    import json
    return [{
        "id": row["id"], "actor_id": row["actor_id"], "action": row["action"],
        "resource_type": row["resource_type"], "resource_id": row["resource_id"],
        "details": json.loads(row["details_json"] or "{}"), "created_at": row["created_at"],
    } for row in rows]


@router.post("/{tenant_id}/workspaces/{workspace_id}")
def attach_workspace_to_tenant(tenant_id: str, workspace_id: str, user=Depends(get_current_user)):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT role FROM tenant_memberships WHERE tenant_id=? AND user_id=?",
                    (tenant_id, user["id"]))
        actor = cur.fetchone()
        if not actor or actor["role"] not in ("owner", "admin"):
            raise HTTPException(status_code=403, detail="صلاحية مدير المؤسسة مطلوبة")
        cur.execute("SELECT id,tenant_id FROM workspaces WHERE id=?", (workspace_id,))
        workspace = cur.fetchone()
        if not workspace:
            raise HTTPException(status_code=404, detail="مساحة العمل غير موجودة")
        cur.execute("SELECT role FROM workspace_members WHERE workspace_id=? AND user_id=?",
                    (workspace_id, user["id"]))
        workspace_actor = cur.fetchone()
        if not workspace_actor or workspace_actor["role"] not in ("owner", "admin"):
            raise HTTPException(status_code=403, detail="يجب أن تكون مالكاً أو مديراً لمساحة العمل")
        cur.execute("""SELECT COUNT(*) AS missing FROM (
                           SELECT wm.user_id FROM workspace_members wm
                           WHERE wm.workspace_id=?
                           UNION
                           SELECT dp.user_id FROM documents d
                           JOIN document_permissions dp ON dp.document_id=d.id
                           WHERE d.workspace_id=?
                       ) required_users
                       LEFT JOIN tenant_memberships tm
                         ON tm.tenant_id=? AND tm.user_id=required_users.user_id
                       WHERE tm.user_id IS NULL""",
                    (workspace_id, workspace_id, tenant_id))
        missing = cur.fetchone()["missing"]
        if missing:
            raise HTTPException(status_code=409, detail="أضف جميع أعضاء مساحة العمل إلى المؤسسة أولاً")
        previous_tenant_id = workspace["tenant_id"]
        cur.execute("UPDATE workspaces SET tenant_id=? WHERE id=?", (tenant_id, workspace_id))
    from app.audit import record_audit_event
    record_audit_event(user["id"], "workspace.tenant_attached", "workspace", workspace_id,
                       tenant_id, {"previous_tenant_id": previous_tenant_id})
    return {"tenant_id": tenant_id, "workspace_id": workspace_id, "status": "attached"}
