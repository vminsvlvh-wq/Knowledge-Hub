# Knowledge Intelligence — Target Architecture

## Architectural decision
Build one modular product that supports both SaaS and private deployment. Start as a modular monolith; split services only when scale or operational isolation requires it.

## Logical layers
1. Experience: responsive web application, organization console and APIs.
2. Identity and tenancy: authentication, tenant context, RBAC, optional ABAC and SSO integration.
3. Ingestion: upload, malware scanning, MIME validation, OCR, parsing, normalization and chunking.
4. Intelligence: model gateway, embeddings, retrieval, reranking, grounded generation and evaluation.
5. Knowledge services: documents, versions, decisions, handovers, entities and relationships.
6. Storage: PostgreSQL with pgvector initially; object storage for source files; graph database only when justified.
7. Governance: tenant isolation, encryption, audit events, retention, consent, export and deletion.
8. Runtime: containers, managed cloud for SaaS, customer infrastructure for private deployments.

## Recommended MVP stack
- Frontend: Next.js + TypeScript.
- Backend: Python + FastAPI.
- Primary database: PostgreSQL.
- Vector retrieval: pgvector.
- File storage: S3-compatible object storage abstraction.
- Background work: simple queue and worker initially.
- AI: provider adapter / model gateway; Gemini can be an initial provider, not a hard dependency.
- Observability: structured logs, metrics and traces.
- Packaging: Docker; Kubernetes is not required for the first pilot.

## Core data model
tenants, users, tenant_memberships, workspaces, workspace_members, documents, document_versions, document_chunks, ingestion_jobs, source_citations, decisions, knowledge_handoffs, audit_events and model_usage_events.

Every tenant-owned record must carry a tenant identifier or be reachable only through a tenant-scoped parent with enforced constraints. Every retrieval query must apply authorization filters before content is passed to a model.

## Security invariants
- Tenant identity is derived from the authenticated session, never trusted from arbitrary client input alone.
- Authorization is checked server-side on every read, write, search and download.
- Retrieval filters are applied before vector similarity results are exposed.
- Object storage keys and signed URLs are tenant-scoped and short-lived.
- Secrets are stored only in deployment secret stores, never in source control.
- Customer data is not used for shared model training without explicit opt-in.
- Audit records capture actor, tenant, action, target, timestamp and outcome without unnecessarily copying sensitive content.

## RAG answer contract
1. Resolve tenant and user permissions.
2. Retrieve only authorized source chunks.
3. Evaluate evidence sufficiency.
4. Generate an answer constrained to retrieved evidence.
5. Return citations that resolve to authorized source passages.
6. Abstain when evidence is insufficient.
7. Record a minimal audit and usage event.

## Hybrid deployment
The same container images and configuration contract should run in both modes. Cloud mode adds tenant provisioning and shared operations. Private mode uses dedicated database, storage, secrets and model connectivity settings. Avoid separate feature branches or divergent product versions.

## Migration approach
1. Preserve current Knowledge-Hub code and tests.
2. Create a KI foundation branch.
3. Establish architecture decisions and a security baseline.
4. Add automated tests for tenant isolation, retrieval authorization and citation correctness.
5. Introduce versioned database migrations before production data changes.
6. Refactor the current SQLite/PostgreSQL compatibility layer toward PostgreSQL-first repositories.
7. Implement ingestion and retrieval behind stable service interfaces.
8. Add the web experience after API and security contracts are stable.
