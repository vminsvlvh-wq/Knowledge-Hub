# KI Security Baseline — Foundation Stage

## Implemented in ki-foundation
- Every workspace is assigned a tenant identifier; legacy workspaces are backfilled into separate tenants.
- Tenant and membership tables are created by the core database bootstrap, including direct init_db() use.
- Workspace-level authorization requires both workspace membership and membership in the workspace's current tenant.
- Document-level authorization checks tenant membership before honoring direct document grants.
- Direct document grants add the grantee to the owning tenant.
- Moving a workspace to a tenant is blocked until all workspace members and direct document grantees belong to the target tenant.
- WebSocket read connections require document view access; content updates and snapshots separately require edit access.
- PostgreSQL column migration uses ADD COLUMN IF NOT EXISTS; SQLite checks schema metadata before altering.
- Production configuration requires an explicitly provided 32+ character JWT secret. The built-in development secret is not suitable for production.

## Additional controls added in the security hardening pass
- Application-level append-only audit event writer and tenant-scoped audit event table.
- Tenant owners/admins can read only their own tenant's audit history, with bounded pagination.
- Audit metadata is recorded for tenant creation/invitations, workspace membership changes, document reads/writes/archives/permission changes, and AI search/ask/summary operations. Document bodies, prompts, tokens and secrets are not copied into audit metadata.
- Workspace discovery now requires a matching tenant membership; workspace role changes validate the role and only an existing workspace owner may appoint, demote or remove another owner.
- Collaborative WebSocket content updates reject non-string payloads and content larger than 2 MB.
- Semantic-search document allow-list lookup independently joins the tenant membership boundary.

## Automated coverage added
- Legacy workspace backfill and separation.
- Idempotent tenant bootstrap.
- Workspace membership without tenant membership is rejected.
- A direct document permission cannot bypass the tenant boundary.
- Read-only WebSocket users cannot send content changes.
- PostgreSQL integration test checks schema initialization and cross-tenant document denial.

## Remaining before customer data
1. Add tenant-aware constraints to every future table and migration; keep the tenant identifier immutable except through a reviewed transfer workflow.
2. Complete route-by-route review of all workspace, decision, knowledge-transfer, skills and admin endpoints.
3. Verify vector index filters and deletion propagation, and introduce tenant-aware object-storage keys and short-lived signed URLs.
4. Add append-only audit events for membership, permission, ingestion, search and AI actions.
5. Add malware scanning, parser isolation, upload size/type controls and retention/deletion workflows.
6. Add database migration tooling with versioned and reversible migrations.
7. Run dependency, secret, SAST, DAST and independent penetration testing.
8. Add versioned/reversible schema migrations; current tenant schema setup is additive bootstrap DDL, not a migration framework.
9. Implement tenant-scoped object storage only after selecting a provider; this repository currently has no object-storage service or upload/download pipeline.
8. Verify backup/restore, encryption, key rotation, SSO and deployment hardening for both SaaS and Private modes.

## Release decision
Audit events are application-level append-only records; database administrators can still alter them, and tamper-evident external log export is not yet implemented.

This is a foundational security improvement, not a production security sign-off, certification or legal compliance assessment. Keep the pull request unmerged until CI passes and the remaining controls are reviewed.
