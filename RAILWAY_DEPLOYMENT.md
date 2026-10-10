# KnowledgeHub Saudi 2030 — Railway deployment

## Isolation
Create a NEW Railway project named `knowledgehub-saudi-2030`, with ONE new PostgreSQL service and ONE new FastAPI service. Do not attach to existing accounts' services, databases, or environment variable groups. Originals in Google Drive must not be changed.

## Build and configuration
- Deploy the source code folder as the app service (e.g. from a dedicated new GitHub repository).
- Add a **new** Railway PostgreSQL instance within this new project.
- Set `DATABASE_URL` on the API service via Railway's **reference variable** to the new Postgres service (`${{Postgres.DATABASE_URL}}` in the Railway UI, exact service name as created). Never paste secrets into conversation.
- Set `ENVIRONMENT=production`.
- Generate and set a unique `JWT_SECRET_KEY` of at least 32 random characters via Railway's secret management UI.
- Keep `CORS_ORIGINS` empty for the same-origin frontend in this service.
- Railway auto-provides `PORT`; `railway.json` runs Uvicorn and checks `/api/ready`.
- Provision a new Railway public domain for the API and bundled frontend.

## Verify before rollout
1. `GET /api/health` returns online.
2. `GET /api/ready` returns ready only when new PostgreSQL DB is reachable.
3. With **non-sensitive test data**, register a user, create a workspace, document and query Corporate Brain, add a decision with metrics, enter knowledge transfer, and use skill targets and assessments.
4. Verify a second user cannot access the first workspace's records.
5. Review HTTPS, logs, backups, retention and data location before uploading employee or institutional data.

## Cautions
- `init_db` performs idempotent **initial schema creation**, not versioned migrations. Add Alembic before changing an existing production schema.
- This package contains no production credentials or customer data.
- Do not treat this app as Saudi PDPL-certified or ready for sensitive data without independent security/privacy review.
- No real managed PostgreSQL integration test was run without an isolated PostgreSQL instance.
- For WebSocket collaboration across multiple replicas, the in-memory manager will need a shared message broker.
