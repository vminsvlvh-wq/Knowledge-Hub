from crewai import Task
from agents import (
    skill_mapper, problem_discovery, team_formation, 
    opportunity_designer, critic, experiment_planner, manager
)
from schemas import OpportunityReport
from sample_data import users_data

def create_tasks():
    users_info = str(users_data)

    task1 = Task(
        description=f'قم بتحليل البيانات التالية للأشخاص: {users_info}. استخرج المهارات التقنية، الناعمة، الموارد، والوقت المتاح لكل شخص. قدم ملخصاً واضحاً باللغة العربية.',
        expected_output='قائمة مفصلة بمهارات وموارد كل شخص باللغة العربية.',
        agent=skill_mapper
    )

    task2 = Task(
        description='بناءً على اهتمامات الأشخاص في الخطوة السابقة ومهاراتهم (مثل التعليم الرقمي، التجارة الإلكترونية، الذكاء الاصطناعي)، اقترح 3 مشكلات حقيقية في السوق تحتاج إلى حل.',
        expected_output='وصف لـ 3 مشكلات حقيقية في السوق باللغة العربية.',
        agent=problem_discovery
    )

    task3 = Task(
        description='اختر مشكلة واحدة من المشكلات المقترحة. ثم قم بتشكيل فريق من الأشخاص المتاحين لحل هذه المشكلة. اشرح كيف تتكامل مهاراتهم معاً.',
        expected_output='وصف للفريق المكون وكيفية تكامل مهاراتهم لحل المشكلة المختارة باللغة العربية.',
        agent=team_formation
    )

    task4 = Task(
        description='بناءً على المشكلة والفريق، ابتكر مشروعاً أو خدمة. حدد: العميل المستهدف بدقة، أدوار كل عضو في الفريق، القيمة المقدمة (Value Proposition)، ونموذج الربح.',
        expected_output='تصميم كامل للفرصة التجارية وأدوار الفريق ونموذج الربح باللغة العربية.',
        agent=opportunity_designer
    )

    task5 = Task(
        description='انقد المشروع المقترح. حدد المخاطر الأساسية، المهارات أو الموارد التي لا يمتلكها الفريق (Missing Skills)، وأعطِ تقييماً للفكرة من 1 إلى 100.',
        expected_output='قائمة بالمخاطر، المهارات الناقصة، وتقييم رقمي للفكرة باللغة العربية.',
        agent=critic
    )

    task6 = Task(
        description='ضع خطة اختبار عملية من 3 خطوات للتحقق من أن العميل المستهدف مستعد للدفع مقابل هذا الحل، دون الحاجة لبناء المنتج الكامل.',
        expected_output='خطة اختبار (Validation Plan) من 3 خطوات باللغة العربية.',
        agent=experiment_planner
    )

    task7 = Task(
        description='أنت المدير. قم بجمع جميع المخرجات من المهام السابقة وصغها بدقة في هيكل البيانات المطلوب (JSON). تأكد أن جميع الحقول المطلوبة موجودة وأن المحتوى باللغة العربية بالكامل.',
        expected_output='ملف JSON يحتوي على التقرير النهائي متوافق مع هيكل البيانات المطلوب.',
        agent=manager,
        output_pydantic=OpportunityReport
    )

    return [task1, task2, task3, task4, task5, task6, task7]
