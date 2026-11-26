# Initial Technical Audit — Knowledge-Hub to KI

Audit basis: source files reviewed on 2026-11-26 through the connected GitHub repository. This is a source-level review, not a penetration test or a successful local execution.

## Existing assets worth retaining
- FastAPI application and modular routers.
- User authentication and workspace membership model.
- Role-based access control foundations.
- Document hierarchy, version history and document-level permissions.
- Document chunking and semantic retrieval foundations.
- Knowledge-transfer workflow.
- Voluntary skills self-assessment with small-group suppression.
- Existing automated tests and Arabic UI foundation.

## Findings and risks to resolve

### P0 — before any real customer data
1. Tenant model is not yet explicit. Workspaces exist, but a first-class organization/tenant boundary and tenant-wide isolation contract are not evident in the reviewed core schema. Define tenant ownership and enforce it across every query, file, vector record and background job.
2. Authorization must be proven end-to-end. The RBAC helpers are a useful base, but all endpoints, document downloads, collaboration sockets, search paths and background tasks need a route-by-route authorization audit.
3. Production database migration is not mature. The code supports SQLite and a PostgreSQL adapter, while schema creation is performed at startup with CREATE TABLE IF NOT EXISTS. Add versioned, reversible migrations and test PostgreSQL as the production target.
4. No production security sign-off. Add threat modelling, secret review, dependency scanning, backup/restore testing and independent security assessment before onboarding customers.

### P1 — required for a credible MVP
5. AI provider integration is not yet a clean product boundary. agents.py directly configures Gemini and imports optional agent frameworks. Move provider access behind a model gateway; isolate optional dependencies and fail gracefully when not configured.
6. Evidence and evaluation need formal tests. Benchmark Arabic and English retrieval, citation validity, unsupported-question abstention, prompt injection in documents and cross-tenant retrieval leakage.
7. Auditability is incomplete. Add append-only audit events for sensitive reads, permission changes, document lifecycle and AI-assisted operations.
8. Ingestion lifecycle needs hardening. Add file type and size limits, malware scanning, parser isolation, OCR error handling, idempotent jobs and deletion propagation to indexes and object storage.

### P2 — product and operational maturity
9. Add organization administration, tenant provisioning and subscription/usage metering.
10. Add SSO, retention policies, export/deletion workflows and customer-configurable deployment settings.
11. Add observability, alerting, operational runbooks and tested backup/restore.
12. Replace legacy product labels and scope references (including Saudi 2030) with the approved KI identity and current private-sector scope.

## Scope decisions
- Government is out of current scope.
- Do not claim Vision 2030 alignment, official accreditation, PDPL compliance or security certification without evidence and appropriate review.
- Skills intelligence remains voluntary and developmental; do not turn it into employee ranking or automated HR decisions.
- Cross-organization exchange is deferred until consent, licensing, provenance and revocation controls are designed.

## Immediate implementation sequence
1. Keep this branch isolated from main.
2. Add a tenant/security design and acceptance tests.
3. Inventory every API route and database query for tenant scoping.
4. Add migration tooling and PostgreSQL CI.
5. Build a small, testable ingestion to retrieval to cited-answer vertical slice.
6. Run security and functional tests before deployment.

## Important limitations
The source review did not execute the application, run the test suite, inspect deployed environment variables, or verify production infrastructure. Findings above are prioritized engineering observations, not a certification or guarantee that no other issues exist.
