import os
from crewai import Agent
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-pro-latest",
    verbose=True,
    temperature=0.5,
    google_api_key=os.getenv("GEMINI_API_KEY")
)

skill_mapper = Agent(
    role='محلل المهارات والموارد',
    goal='استخراج وتصنيف المهارات، الخبرات، والموارد لكل شخص من البيانات المدخلة بشكل دقيق.',
    backstory='أنت خبير في الموارد البشرية وتحليل القدرات، تمتلك قدرة فائقة على قراءة السير الذاتية والبيانات واستخراج نقاط القوة والموارد الخفية للأشخاص.',
    verbose=True,
    allow_delegation=False,
    llm=llm
)

problem_discovery = Agent(
    role='مكتشف المشكلات والاحتياجات',
    goal='تحليل السوق واكتشاف مشكلات حقيقية واحتياجات قابلة للحل بناءً على المجالات التي يهتم بها الأشخاص المتاحون.',
    backstory='أنت باحث سوق استراتيجي ومبتكر، تستطيع رؤية الفجوات في السوق والمشكلات التي يعاني منها الناس والتي يمكن تحويلها إلى فرص تجارية.',
    verbose=True,
    allow_delegation=False,
    llm=llm
)

team_formation = Agent(
    role='مهندس بناء الفرق',
    goal='تكوين فريق متجانس من الأشخاص المتاحين بحيث تتكامل مهاراتهم (وليس فقط تتشابه) لحل مشكلة محددة.',
    backstory='أنت خبير في ديناميكيات الفرق وتكامل المواهب. تعرف كيف تجمع المطور مع المسوق والمصمم لإنشاء فريق لا يُقهر.',
    verbose=True,
    allow_delegation=False,
    llm=llm
)

opportunity_designer = Agent(
    role='مصمم الفرص ونماذج العمل',
    goal='تحويل الفريق والمشكلة إلى مشروع أو خدمة واضحة ومبتكرة مع تحديد العميل المستهدف ونموذج الربح.',
    backstory='أنت رائد أعمال متسلسل ومصمم منتجات، تبني نماذج عمل تجارية ناجحة وتحدد بدقة كيف سيقدم الفريق القيمة وكيف سيجني المال.',
    verbose=True,
    allow_delegation=False,
    llm=llm
)

critic = Agent(
    role='الناقد ومحلل المخاطر',
    goal='النقد البناء للفكرة، تحديد المخاطر، الافتراضات غير المؤكدة، والمهارات الناقصة في الفريق، وتقييم الفكرة.',
    backstory='أنت مستثمر رأس مال جريء حازم ولكنك عادل. تبحث عن الثغرات في المشاريع لضمان متانتها، وتكتشف ما ينقص الفرق لتحقيق النجاح.',
    verbose=True,
    allow_delegation=False,
    llm=llm
)

experiment_planner = Agent(
    role='مخطط تجارب التحقق',
    goal='إنشاء خطة عملية وبسيطة (Lean) لاختبار الفكرة والتحقق من وجود عملاء مستعدين للدفع بأقل تكلفة ووقت.',
    backstory='أنت خبير في منهجية Lean Startup، لا تؤمن بالخطط الورقية بل بالتجارب العملية والأدلة الحقيقية من السوق.',
    verbose=True,
    allow_delegation=False,
    llm=llm
)

manager = Agent(
    role='المدير العام والتنفيذي',
    goal='تنسيق النتائج من جميع الوكلاء، صياغتها، والتأكد من إخراج التقرير النهائي بالصيغة المطلوبة (JSON) واللغة العربية حصراً.',
    backstory='أنت مدير مشروع دقيق ومنظم، تضمن توافق جميع مخرجات الفريق مع المعايير المطلوبة وتتأكد من خلو العمل من الأخطاء.',
    verbose=True,
    allow_delegation=True,
    llm=llm
)
