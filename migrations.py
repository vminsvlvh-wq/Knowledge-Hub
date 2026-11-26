"""Versioned, transactional database migrations for KI.

Migrations are additive and safe to re-run. Each version is recorded only after
its complete DDL/backfill succeeds on the active database.
"""
import uuid
from app.db import get_db


def _has_column(conn, table: str, column: str) -> bool:
    if hasattr(conn, "_conn"):  # PostgreSQLConnection adapter
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name=? AND column_name=?",
            (table, column),
        ).fetchall()
        return bool(rows)
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in rows)


def _migration_1_tenant_foundation(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS tenants (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
        created_by TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE CASCADE
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS tenant_memberships (
        id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, user_id TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('owner','admin','member')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(tenant_id,user_id),
        FOREIGN KEY(tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )""")
    if not _has_column(conn, "workspaces", "tenant_id"):
        conn.execute("ALTER TABLE workspaces ADD COLUMN tenant_id TEXT")
    if not _has_column(conn, "document_chunks", "tenant_id"):
        conn.execute("ALTER TABLE document_chunks ADD COLUMN tenant_id TEXT")

    for workspace in conn.execute(
        "SELECT id,name,created_by,tenant_id FROM workspaces"
    ).fetchall():
        tenant_id = workspace["tenant_id"]
        if not tenant_id:
            tenant_id = str(uuid.uuid4())
            slug = ("legacy-" + workspace["id"].replace("-", ""))[:80]
            conn.execute(
                "INSERT INTO tenants(id,name,slug,created_by) VALUES(?,?,?,?)",
                (tenant_id, workspace["name"], slug, workspace["created_by"]),
            )
            conn.execute("UPDATE workspaces SET tenant_id=? WHERE id=?",
                         (tenant_id, workspace["id"]))
        conn.execute(
            """INSERT INTO tenant_memberships(id,tenant_id,user_id,role)
               VALUES(?,?,?,'owner') ON CONFLICT(tenant_id,user_id) DO NOTHING""",
            (str(uuid.uuid4()), tenant_id, workspace["created_by"]),
        )
        for member in conn.execute(
            "SELECT user_id FROM workspace_members WHERE workspace_id=?",
            (workspace["id"],),
        ).fetchall():
            conn.execute(
                """INSERT INTO tenant_memberships(id,tenant_id,user_id,role)
                   VALUES(?,?,?,'member') ON CONFLICT(tenant_id,user_id) DO NOTHING""",
                (str(uuid.uuid4()), tenant_id, member["user_id"]),
            )
    conn.execute(
        """UPDATE document_chunks
           SET tenant_id=(SELECT w.tenant_id FROM workspaces w
                          WHERE w.id=document_chunks.workspace_id)
           WHERE tenant_id IS NULL
             AND EXISTS (SELECT 1 FROM workspaces w
                         WHERE w.id=document_chunks.workspace_id
                           AND w.tenant_id IS NOT NULL)"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tenant_memberships_user ON tenant_memberships(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_workspaces_tenant ON workspaces(tenant_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_tenant_workspace ON document_chunks(tenant_id,workspace_id)")


def _migration_2_audit_events(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_events (
        id TEXT PRIMARY KEY, tenant_id TEXT, actor_id TEXT NOT NULL,
        action TEXT NOT NULL, resource_type TEXT NOT NULL, resource_id TEXT NOT NULL,
        details_json TEXT NOT NULL DEFAULT '{}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(tenant_id) REFERENCES tenants(id) ON DELETE SET NULL,
        FOREIGN KEY(actor_id) REFERENCES users(id) ON DELETE RESTRICT
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_tenant_created ON audit_events(tenant_id,created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_events(resource_type,resource_id,created_at)")


def _migration_3_append_only_audit(conn):
    if hasattr(conn, "_conn"):
        conn.execute("""CREATE OR REPLACE FUNCTION ki_reject_audit_mutation()
            RETURNS trigger LANGUAGE plpgsql AS $
            BEGIN
                RAISE EXCEPTION 'audit_events is append-only';
            END;
            $""")
        conn.execute("DROP TRIGGER IF EXISTS trg_audit_events_no_update ON audit_events")
        conn.execute("DROP TRIGGER IF EXISTS trg_audit_events_no_delete ON audit_events")
        conn.execute("""CREATE TRIGGER trg_audit_events_no_update
            BEFORE UPDATE ON audit_events FOR EACH ROW EXECUTE FUNCTION ki_reject_audit_mutation()""")
        conn.execute("""CREATE TRIGGER trg_audit_events_no_delete
            BEFORE DELETE ON audit_events FOR EACH ROW EXECUTE FUNCTION ki_reject_audit_mutation()""")
    else:
        conn.execute("""CREATE TRIGGER IF NOT EXISTS trg_audit_events_no_update
            BEFORE UPDATE ON audit_events BEGIN
                SELECT RAISE(ABORT, 'audit_events is append-only');
            END""")
        conn.execute("""CREATE TRIGGER IF NOT EXISTS trg_audit_events_no_delete
            BEFORE DELETE ON audit_events BEGIN
                SELECT RAISE(ABORT, 'audit_events is append-only');
            END""")


MIGRATIONS = [
    (1, "tenant_foundation", _migration_1_tenant_foundation),
    (2, "tenant_audit_events", _migration_2_audit_events),
    (3, "append_only_audit_guards", _migration_3_append_only_audit),
]


def run_migrations():
    with get_db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY, name TEXT NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        applied = {row["version"] for row in conn.execute(
            "SELECT version FROM schema_migrations"
        ).fetchall()}
        for version, name, apply in MIGRATIONS:
            if version in applied:
                continue
            apply(conn)
            conn.execute(
                "INSERT INTO schema_migrations(version,name) VALUES(?,?)",
                (version, name),
            )
    return {"applied": [version for version, name, _ in MIGRATIONS if version not in applied]}
