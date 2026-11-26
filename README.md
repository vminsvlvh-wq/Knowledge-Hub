# Knowledge Intelligence (KI)

From Institutional Memory to National Intelligence.

Remember · Understand · Anticipate.

KI is a customizable enterprise knowledge-intelligence platform for private-sector organizations, universities and research centers. Government deployments are outside the current product scope.

## Deployment model
- KI Cloud: multi-tenant SaaS.
- KI Private: dedicated or customer-managed deployment.

## Current foundation
- FastAPI backend and workspace-based authorization.
- Document management, version history and evidence-oriented retrieval.
- Knowledge transfer and voluntary skills intelligence.
- Initial tenant registry, tenant membership and workspace assignment APIs.

## Tenant API
All routes are under `/api/v1/tenants` and require a bearer token:
- `POST /` — create an organization.
- `GET /` — list organizations the signed-in user belongs to.
- `POST /{tenant_id}/members` — invite an existing registered user to the organization.
- `POST /{tenant_id}/workspaces/{workspace_id}` — attach a workspace after confirming all workspace members belong to the organization.

New workspaces are provisioned with an isolated tenant by default. Existing workspaces are backfilled into separate tenants on startup; they are not automatically combined into one organization.

## Local development
Install `requirements.txt`, configure `JWT_SECRET_KEY`, then run the FastAPI application using the repository's deployment entry point. Run tests with `python -m pytest -q`.

## Security status
Tenant foundations are an initial implementation, not a completed enterprise security boundary or compliance certification. Before production customer data: audit every endpoint and WebSocket for tenant scoping, verify object and vector-store isolation, add versioned migrations, and run security and PostgreSQL integration tests.

See:
- [Product brief](KI_PRODUCT_BRIEF.md)
- [Target architecture](KI_ARCHITECTURE.md)
- [Technical audit](KI_TECHNICAL_AUDIT.md)
- [Security baseline](KI_SECURITY_BASELINE.md)


## Security engineering
- [Security baseline](KI_SECURITY_BASELINE.md)
- [Storage isolation review](KI_STORAGE_ISOLATION.md)
