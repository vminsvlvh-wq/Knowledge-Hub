# KnowledgeHub — خطة التطوير المعتمدة

## المرحلة 1: Corporate Brain Foundation (منفذة جزئياً في هذه النسخة)
- فهرسة تلقائية للمستندات الموجودة عند الإنشاء والتعديل.
- تطبيق صلاحيات مساحة العمل قبل استرجاع المقاطع.
- عرض مقاطع مقتبسة مع معرّف المستند ودرجة الصلة.
- الامتناع عن تقديم إجابة عند عدم كفاية الأدلة.
- **الحدود:** البحث يعتمد على متجهات تجزئة محلية؛ لا يوجد نموذج توليد فعلي ولا تقييم جودة عربي شامل.

## المرحلة 2: Corporate Brain Advanced
- تحسين التجزئة والاسترجاع متعدد اللغات، وإضافة مزود LLM اختياري.
- بناء تقييمات دقة واستشهادات واختبارات مقاومة تسريب البيانات.
- عدم إرسال مستندات خاصة إلى أي مزود خارجي قبل إعداد سياسة خصوصية وموافقة.

## المرحلة 3: Decision Memory
- سجل قرارات به المشكلة، الخيارات، المبررات، الأدلة، صاحب القرار، النتيجة، والمراجعات.
- ربط القرارات بمستندات المصدر مع RBAC وسجل تغييرات.

## المرحلة 4: Knowledge Gap Detector
- رصد الأسئلة غير المجابة بشكل مجمع مع تنقية البيانات الحساسة.
- تجميع الفجوات وتعيين مالك وخطة معالجة.

## المرحلة 5: Knowledge Risk Radar
- مراقبة تقادم الوثائق ونقص المالكين والتوثيق والاعتماد على خبير واحد.
- لوحات متابعة ومؤشرات قابلة للتدقيق.

## معايير القبول للمرحلة 1
- مستند منشور في مساحة عمل يظهر بمصدر عند البحث عنه.
- عضو غير مصرح له لا يحصل على محتوى مستند من مساحة عمل أخرى.
- سؤال خارج نطاق الوثائق يعيد امتناعاً دون اختلاق معلومة.
- نجاح اختبارات الانحدار السابقة.

## 2026-10-10 implementation — Knowledge Transfer UI + Skills Intelligence MVP
- Added `نقل المعرفة` tab and review/approve controls, with server-side role checks.
- Added role requirements, voluntary self-report profiles, personal skills gap endpoint, and admin-only aggregate reports with small-group suppression.
- 21 automated tests pass. Inline frontend JavaScript syntax check passes; full browser E2E test not completed due execution-environment navigation restrictions.
- Next: successor acknowledgement, proper migrations, auditable changes, localized skills dictionaries, curated training catalog, authenticated deployment with persistent storage, and full privacy/security testing.
