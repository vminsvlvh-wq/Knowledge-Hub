# KnowledgeHub Saudi 2030 — Knowledge Transfer Phase

## Implemented
- Workspace-scoped knowledge handover records, including knowledge area, written procedure, criticality, owner, optional successor and source document ID.
- Review workflow: draft -> in_review -> approved; approval requires an assigned successor and workspace admin or owner.
- Basic risk summary: high-criticality unapproved records, records without a successor, approved records.
- REST API under `/api/v1/workspaces/{workspace_id}/knowledge-transfers`.
- Two new tests covering lifecycle, role restrictions, invalid references, and workspace isolation.

## API
- `POST /api/v1/workspaces/{workspace_id}/knowledge-transfers`
- `GET /api/v1/workspaces/{workspace_id}/knowledge-transfers`
- `GET /api/v1/workspaces/{workspace_id}/knowledge-transfers/risk-summary`
- `GET /api/v1/workspaces/{workspace_id}/knowledge-transfers/{transfer_id}`
- `PATCH /api/v1/workspaces/{workspace_id}/knowledge-transfers/{transfer_id}/review`

## Limitations / next steps
- No dedicated frontend screen yet; use Swagger UI at `/docs`.
- No recipient acknowledgement or audit-event log yet.
- Knowledge risk summary measures only records users enter; it does not detect all organizational risks.
- No AI-assisted interviews, automatic skills inference, or production security assessment.
- Before production: add per-record access control, secure document reference permissions, audit trail, CSRF/threat review, DB migrations, and deployment testing.

## Run
`pip install -r requirements.txt`
`uvicorn app.main:app --reload`
`python -m pytest -q`

## Follow-up update — Arabic web UI
- Added the **نقل المعرفة** workspace tab with title, knowledge area, procedure, criticality and successor selector populated from active workspace members.
- Added risk counters and review/approval actions gated by workspace role.
- Approved transfer state is now locked in the API; approval rejects a successor removed from the workspace.
- Recipient acknowledgement, record editing, per-record confidentiality and change history remain unimplemented.
