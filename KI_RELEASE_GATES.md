# KI Release Gates

This checklist is the authoritative pre-release gate for the current hybrid KI product. A checked item requires evidence for the exact release candidate; source code alone is not evidence of operational completion.

## Foundation and automated validation

- [x] First-class tenant registry and tenant memberships.
- [x] Workspace ownership linked to tenants with legacy backfill.
- [x] Tenant-scoped vector metadata and retrieval filters.
- [x] Workspace RBAC and document authorization hardening.
- [x] Cookie-authenticated WebSockets with Origin validation; query-string JWTs rejected.
- [x] Versioned additive migrations and schema readiness gate.
- [x] Append-only audit table guards for ordinary application UPDATE/DELETE.
- [ ] Full SQLite test suite green on the latest release SHA.
- [ ] PostgreSQL integration test green on the latest release SHA.
- [ ] CI results reviewed and attached to release record.

## P0 — before any customer data

- [ ] Complete route-by-route authorization review for every read, write, export, search, background task and realtime path.
- [ ] Add private tenant-scoped object storage and authorized upload/download APIs.
- [ ] Add file size/type/content validation and safe filename handling.
- [ ] Add malware scanning and isolated parsing/OCR workers with resource limits.
- [ ] Add ingestion job lifecycle, idempotency, retries and deletion propagation.
- [ ] Add cross-tenant negative tests for object IDs, guessed paths, signed URLs and asynchronous jobs.
- [ ] Verify encryption in transit and at rest, secret rotation and least-privilege database credentials.
- [ ] Complete independent security assessment / penetration test and remediate findings.
- [ ] Complete dependency, secret, SAST and DAST scans; review and disposition findings.
- [ ] Complete privacy/legal review for each target jurisdiction and customer contract.

## P1 — before production operations

- [ ] Configure independent audit-log export with tamper-evident integrity verification and restricted credentials.
- [ ] Define migration rollback/forward-recovery procedures and rehearse them.
- [ ] Configure automated backups, retention and point-in-time recovery as supported by the selected provider.
- [ ] Complete and record a restore rehearsal using a clean environment.
- [ ] Configure structured logs, metrics, tracing, alerting and incident escalation.
- [ ] Define tenant provisioning, suspension, export, deletion and retention workflows.
- [ ] Validate production CORS, cookie, HTTPS, domain and security-header configuration.
- [ ] Test SaaS tenant isolation and private deployment isolation separately.
- [ ] Complete load, resilience and failure-mode testing.

## Release controls

- [ ] All required gates above are evidenced for the exact release SHA.
- [ ] No unresolved critical/high security findings.
- [ ] Product owner explicitly approves release.
- [ ] Release is deployed to a test environment and smoke-tested with synthetic data.
- [ ] Customer data onboarding is explicitly authorized.

## Current constraints

- Government use is outside current scope.
- File ingestion must remain disabled until storage, scanning and parser isolation gates are complete.
- Audit triggers are not tamper-proof against a privileged database owner; do not describe them as immutable or certified.
- No PDPL compliance, certification, accreditation or penetration-test completion is claimed.
- The current branch and PR are a development foundation, not a production release.
