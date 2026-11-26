import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.auth import get_current_user
from app.db import get_db

router = APIRouter(prefix="/tenants", tags=["KI Tenancy"])

class TenantCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9-]*$")

def init_tenant_schema():
    """Additive, idempotent bootstrap migration. Existing workspaces are isolated individually."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS tenants (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
            created_by TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE CASCADE
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS tenant_memberships (
            id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, user_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('owner','admin','member')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(tenant_id,user_id),
            FOREIGN KEY(tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )""")
        try:
            cur.execute("ALTER TABLE workspaces ADD COLUMN tenant_id TEXT")
        except Exception as exc:
            # SQLite and PostgreSQL both report an error when the column already exists.
            if "duplicate column" not in str(exc).lower() and "already exists" not in str(exc).lower():
                raise
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
    return {"id": tenant_id, "name": payload.name.strip(), "slug": slug, "role": "owner"}

@router.get("")
def list_my_tenants(user=Depends(get_current_user)):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""SELECT t.id,t.name,t.slug,tm.role
                       FROM tenants t JOIN tenant_memberships tm ON tm.tenant_id=t.id
                       WHERE tm.user_id=? ORDER BY t.created_at DESC""", (user["id"],))
        return [dict(row) for row in cur.fetchall()]
