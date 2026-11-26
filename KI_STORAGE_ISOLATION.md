# KI Storage Isolation Review — Foundation

## Vector index

Implemented on `ki-foundation`:
- Every `document_chunks` row carries the owning `tenant_id` in addition to `workspace_id`.
- New chunks derive their tenant from the document's actual workspace; indexing fails closed if the document/workspace relation or tenant is missing.
- Semantic retrieval resolves the workspace tenant from the database and filters on both `workspace_id` and `tenant_id`.
- Retrieval also joins the document on its workspace and requires an active document.
- Existing installations receive an additive nullable column; legacy rows are backfilled from their owning workspace after tenant migration.
- A regression test deliberately corrupts a chunk's tenant metadata and verifies it is not returned.

## Versioned schema migrations

Tenant tables, workspace tenant ownership, vector tenant metadata/backfill, and audit-event storage are applied by numbered migrations recorded in `schema_migrations`. The runner applies each migration in a transaction and skips versions already recorded. Migrations are currently additive; there are no automatic down-migrations.

## Object/file storage

The current branch does not implement a separate object-storage service, bucket, file-upload endpoint, or signed-download URL flow. Document bodies are stored in the relational database and text is indexed into `document_chunks`. Therefore there is no object bucket to tenant-isolate yet, and no claim is made that S3/R2 storage controls are implemented.

Before introducing attachments or external object storage:
1. Create tenant-scoped object keys, e.g. `tenants/{tenant_id}/documents/{document_id}/...`; never accept tenant IDs or object keys as authorization evidence from the client.
2. Authorize every upload, download, preview, copy, and delete against the current document and tenant membership.
3. Issue short-lived signed URLs only after server-side authorization; keep buckets private and block public ACLs.
4. Validate file type by content, size, extension and parser limits; scan malware and process untrusted formats in an isolated worker.
5. Persist object metadata and tenant/document ownership transactionally; use lifecycle cleanup for failed uploads and deletions.
6. Ensure deletion, retention, export, backup and restore workflows include object bytes and derived text/vector chunks.
7. Add cross-tenant negative tests for object IDs, guessed paths, signed URL reuse, and asynchronous ingestion jobs.

## Realtime and audit metadata

WebSocket access now uses an HttpOnly `ki_access_token` cookie, validates the Origin against configured origins or the request host, and rejects query-string JWTs. This is intended for same-origin browser use. Audit events record operational metadata, not document bodies or secrets; they are not cryptographically tamper-evident.

## Release status

Vector metadata isolation and query filtering have been implemented, subject to CI validation. Object storage is explicitly deferred because the current product has no object-storage/upload subsystem. Do not onboard customer files until the future upload/storage path has these controls and independent review.
