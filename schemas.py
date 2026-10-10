from pydantic import BaseModel, Field
from typing import List

class OpportunityReport(BaseModel):
    members: List[str] = Field(..., description="أسماء أعضاء الفريق")
    extracted_skills: dict = Field(..., description="قاموس يحتوي على اسم كل عضو والمهارات/الموارد المستخرجة منه")
    complementary_skills: str = Field(..., description="شرح لكيفية تكامل مهارات أعضاء الفريق معاً")
    selected_problem: str = Field(..., description="المشكلة الحقيقية أو الاحتياج في السوق الذي تم اختياره")
    target_customer: str = Field(..., description="العميل المستهدف للمشروع")
    proposed_opportunity: str = Field(..., description="وصف فرصة العمل أو المشروع الجديد")
    team_roles: dict = Field(..., description="الأدوار المقترحة لكل عضو في الفريق بناءً على مهاراته")
    value_proposition: str = Field(..., description="القيمة المقدمة (Value Proposition) للمشروع")
    revenue_model: str = Field(..., description="نموذج الربح المقترح")
    missing_skills: List[str] = Field(..., description="المهارات أو الموارد الناقصة التي يحتاجها الفريق")
    risks: List[str] = Field(..., description="المخاطر والافتراضات غير المؤكدة في الفكرة")
    opportunity_score: int = Field(..., description="تقييم الفكرة من 1 إلى 100")
    validation_plan: List[str] = Field(..., description="خطة عملية لاختبار الفكرة والتحقق من استعداد العملاء للدفع")
    final_recommendation: str = Field(..., description="التوصية النهائية للإطلاق أو التعديل")
