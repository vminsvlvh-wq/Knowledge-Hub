# Knowledge Intelligence — Railway Deployment Runbook

## Deployment posture

KI supports two deployment modes from the same application code:
- **Cloud SaaS:** shared application runtime with strict tenant isolation and separately managed tenant data boundaries.
- **Private Enterprise:** a dedicated deployment, database, storage, secrets and model-provider configuration under the customer's operational control.

This runbook describes a **non-production pilot** on Railway. Do not use it to onboard real institutional, employee, confidential or regulated data until every release gate below is closed.

## Required services

Create a new, isolated Railway project for KI with:
1. One FastAPI application service built from this repository and the approved branch.
2. One new PostgreSQL service (PostgreSQL 16 or supported newer version).
3. No connection to databases, volumes, variables or services belonging to another project.

Do not deploy the `main` branch by default. Use the reviewed `ki-foundation` branch only for a disposable test environment until the pull request is reviewed and merged through the normal release process.

## Application configuration

Configure secrets through Railway's secret/variable UI. Never commit real credentials or paste them into chat.

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` only after production approval; use `test` for CI |
| `DATABASE_URL` | Railway reference to the new PostgreSQL service |
| `JWT_SECRET_KEY` | Newly generated random secret, at least 32 characters |
| `CORS_ORIGINS` | Exact trusted frontend origins; keep empty for same-origin deployment |

Railway supplies `PORT`. Confirm the start command and health-check path in `railway.json`. Do not expose PostgreSQL publicly.

## Pre-deployment checks

- Confirm the exact commit SHA and branch being deployed.
- Require green SQLite and PostgreSQL CI for that exact SHA.
- Confirm `/api/health` responds and `/api/ready` only reports ready after migrations complete.
- Use synthetic test accounts and non-sensitive sample content only.
- Verify that a user in tenant A cannot enumerate, read, modify, search, export or collaborate on tenant B data.
- Verify cookie security, HTTPS, trusted origins, logout invalidation and secret rotation.
- Verify database backups and complete a restore rehearsal before any real customer data.
- Configure logs, alerting, retention and incident ownership.

## Current implementation limits

The repository currently provides tenant/workspace isolation foundations, PostgreSQL migrations, audit events and cookie-authenticated WebSockets. It does **not** yet provide:
- Object storage, attachment upload/download APIs or signed URL flows.
- Malware scanning, content-disarm or isolated document parsers.
- Independently exported cryptographically tamper-evident audit logs.
- A completed independent penetration test or documented SAST/DAST/security sign-off.
- A verified production backup/restore exercise or production configuration review.

Until these are implemented and tested, do not enable customer file ingestion or claim production security readiness. Document text currently lives in the relational database; do not assume an external bucket exists.

## Hybrid/private deployment principles

For a private customer deployment, use dedicated infrastructure and customer-controlled secrets, database, storage and model-provider connectivity. Do not share storage credentials or database instances across customers. Keep the same versioned application release and configuration contract across SaaS and private deployments.

## Release decision

A successful container start is not a production approval. Release requires:
1. Green CI on the exact release SHA.
2. Security review and remediation of all P0/P1 findings.
3. Storage/ingestion security controls before file uploads.
4. Backup/restore proof, observability and incident runbooks.
5. Privacy/legal review appropriate to the deployment jurisdiction and customer data.
6. Explicit release approval.

No PDPL compliance, certification, accreditation or penetration-test status is claimed by this repository.
