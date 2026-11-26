import uuid

from app.config import settings
from app.db import get_db, init_db
from app.tenant_core import init_tenant_schema
from app.audit import record_audit_event


def test_audit_events_are_persisted_with_tenant_and_actor(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db_file = str(tmp_path / "audit.db")
    monkeypatch.setattr(settings, "DB_PATH", db_file)
    init_db(db_file)
    actor_id = str(uuid.uuid4())
    with get_db(db_file) as conn:
        conn.execute(
            "INSERT INTO users(id,email,full_name,hashed_password) VALUES(?,?,?,?)",
            (actor_id, "audit@example.test", "Audit Actor", "hash"),
        )
    init_tenant_schema()
    tenant_id = str(uuid.uuid4())
    with get_db(db_file) as conn:
        conn.execute(
            "INSERT INTO tenants(id,name,slug,created_by) VALUES(?,?,?,?)",
            (tenant_id, "Audit Tenant", "audit-tenant", actor_id),
        )
    record_audit_event(
        actor_id=actor_id, tenant_id=tenant_id, action="member.invited",
        resource_type="tenant", resource_id=tenant_id,
        details={"role": "member"},
    )
    with get_db(db_file) as conn:
        rows = conn.execute(
            "SELECT tenant_id,actor_id,action,resource_type,resource_id,details_json FROM audit_events"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["tenant_id"] == tenant_id
    assert rows[0]["actor_id"] == actor_id
    assert rows[0]["action"] == "member.invited"
    assert '"role": "member"' in rows[0]["details_json"]
