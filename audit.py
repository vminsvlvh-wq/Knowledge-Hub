"""Application-level append-only audit event writer for sensitive KI operations."""
import json
import uuid
from typing import Any, Optional
from app.db import get_db


def record_audit_event(
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    tenant_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    """Persist minimal metadata only; never pass document contents, tokens or secrets."""
    with get_db() as conn:
        conn.execute(
            """INSERT INTO audit_events
               (id, tenant_id, actor_id, action, resource_type, resource_id, details_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()), tenant_id, actor_id, action, resource_type,
                resource_id, json.dumps(details or {}, ensure_ascii=False, sort_keys=True),
            ),
        )
