# KnowledgeHub Saudi — Implementation priorities

This roadmap is a proposed product alignment with Saudi Vision 2030 themes, not a claim of government endorsement or legal compliance.

## Release A — Arabic Corporate Brain (implemented in this package)
- Normalize common Arabic hamza, diacritic and letter variants for deterministic retrieval.
- Keep evidence-only answers and source citations.
- Preserve workspace/document authorization filters.
- Rebuild old search indexes using `python scripts/reindex_arabic.py` after backing up the database.

## Release B — Decision Impact Tracker (planned)
- Decision records: problem, owner, options, evidence, timestamp, expected KPI, baseline, review date, measured result.
- Audit history and permission checks for each decision.

## Release C — Knowledge Transfer (planned)
- Structured handover interview, reviewed knowledge notes, successor sign-off.
- Risk flags for undocumented processes and single-expert dependencies.

## Release D — Skills Intelligence (planned)
- Role competency matrices, consent-aware employee skill profiles, anonymized aggregated gap reports.

## Acceptance metrics (pilot proposals, not measured results)
- Source citation rate; unanswered-question rate; retrieval quality on a labeled Arabic question set.
- Median time to find a policy; percent of decisions with reviewed outcomes.
- Documents with accountable owners and current review dates.

## Deployment controls
- Validate PDPL applicability and SDAIA/NDMO guidance with qualified compliance professionals.
- Configure retention, backups, access audit logs, and hosting residency as appropriate to the customer.
- Avoid claiming formal Vision 2030 accreditation.

## Decision Impact Tracker — implemented MVP
- سجل قرارات لكل مساحة عمل بصلاحيات Owner/Admin/Editor للكتابة وViewer للقراءة.
- مؤشرات قابلة للقياس: baseline، target، unit، direction، وقياسات مؤرخة.
- تقرير أثر يحتوي على التغير المطلق والنسبة المئوية وحالة تحقيق الهدف، دون ادعاء السببية.
- واجهة عربية لإضافة القرارات والمؤشرات والقياسات.
- لا توجد تكاملات مع أنظمة ERP/HR حالياً، ولا يوجد تدقيق متقدم أو اعتماد إداري للقياسات.

## Release D — Skills Intelligence (implemented MVP)
- Self-reported and individually editable skill profiles; workspace-admin-defined role competency matrix.
- Individual gap comparison, distinguishing unknown skills from below-target skills.
- Privacy-aware thresholding of admin-only aggregate reports (>=3 group profiles and >=3 actual assessments per skill).
- Arabic UI tab for profiles, requirements and summaries.
- No AI inference, hiring scores, credentials verification or HRIS connection. See `SKILLS_INTELLIGENCE_PHASE.md`.

**Status:** this alignment reflects potential contributions to productivity and human-capital development; it is not an official governmental endorsement or Saudi regulatory certification.
