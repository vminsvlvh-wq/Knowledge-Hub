# KnowledgeHub Saudi 2030 — Skills Intelligence MVP

## What's new

1. **Knowledge Transfer UI**: Arabic page to capture written procedures, priority and successor. Authorized editors may submit for review; workspace admins/owners may approve. Approved handovers cannot be reopened through the API.
2. **Skills Intelligence API + UI**: voluntary employee self-report, skills (levels 0–5), administrator-managed role requirements, private employee gap reports, and threshold-suppressed administrator group reports.
3. **No employee ranking**: the backend doesn't infer skill levels from documents and isn't intended for hiring, compensation or disciplinary decisions.

## API endpoints

All endpoints require authentication, membership in the requested workspace, and the role listed below.

| Method | Endpoint suffix (relative to `/api/v1/workspaces/{workspace_id}`) | Access |
|---|---|---|
| `GET` | `/skills/requirements` | viewer+ |
| `POST` | `/skills/requirements` | admin+ |
| `DELETE` | `/skills/requirements/{id}` | admin+ |
| `GET` | `/skills/my-profile` | viewer+ (self only) |
| `PUT` | `/skills/my-profile` | viewer+ (self only) |
| `GET` | `/skills/my-gap` | viewer+ (self only) |
| `GET` | `/skills/gap-summary` | admin+ (aggregated only) |

**POST requirement JSON:** `{"role_name":"محلل بيانات","skill_name":"SQL","target_level":4}`

**PUT profile JSON:** `{"role_name":"محلل بيانات","skills":[{"skill_name":"SQL","level":2,"evidence_note":"تقييم ذاتي"}]}`

Employee gaps compare levels to the role matrix, and unassessed requirements are flagged **unassessed** instead of reported as lacking. Aggregate reports are only available for a role containing at least **3 active workspace members with profiles**; additionally, per-skill results are hidden when fewer than **3 employees assessed that skill**. Small-group suppression is a basic safeguard, **not a formal privacy guarantee** (e.g. differencing between reports can still disclose data). Admins do not receive individually attributed employee skill profiles through the API.

## Run and inspect

```bash
python -m venv .venv
# macOS / Linux: source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Set JWT_SECRET_KEY to a long random value in your shell or deployment configuration.
uvicorn app.main:app --reload
python -m pytest -q
```

Visit `http://127.0.0.1:8000`. After signing in:

- Create/select a workspace.
- Click **نقل المعرفة** to capture handovers. Create at least one other registered member and add them to the workspace before assigning a recipient.
- Click **فجوات المهارات** to edit your profile. A workspace admin can create target skill levels for a named role.
- Enter skill lines in the format `SQL | 2 | optional note`; select **حفظ تقييمي الذاتي**. The comparison panel updates.
- Admin summary remains hidden for a role until at least 3 members have opted in and submitted profiles. Per-skill statistics are hidden until at least 3 assessments exist.

## Database compatibility

`init_db` uses **CREATE TABLE IF NOT EXISTS** for three new tables (`role_skill_requirements`, `skill_profiles`, `skill_assessments`) and creates one index. Before using on a non-test database, back it up, then run app startup. This does not constitute a versioned, rollback-capable production migration.

## Verification

- `python -m pytest -q --disable-warnings`: **21 passed** (2026-10-10 in the provided test environment).
- `node --check` on the inline frontend JS passed.
- A Chromium navigation-based smoke test **could not run** because local HTTP navigation was blocked by the execution environment. Hence end-to-end browser workflows are **not** verified; manual testing is still required.

## Deployment gaps

- Not deployed. No publicly accessible URL.
- SQLite requires persistent hosting storage. For production multiuser use, plan PostgreSQL, proper migrations and backups.
- No independent pen test, audit log for skills changes, per-field retention policy, enterprise SSO, formal PDPL assessment, or official Vision 2030 accreditation.
- No human-resources integration, auto-training plan, AI-assisted competency inference, or verifiable external certifications.
- For real employee data, obtain proper permission and consent as applicable and complete a privacy/security review before deploying.
