import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db import init_db
from app.routers import auth, workspaces, documents, collaboration, decisions, knowledge_transfer, skills

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="خادم خلفي متكامل لإدارة المعرفة المؤسسية يدعم مساحات العمل، الصلاحيات المتقدمة (RBAC)، والتحرير التعاوني اللحظي."
)

# CORS configuration for frontend clients (e.g. Next.js running on localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "" if os.getenv("ENVIRONMENT") == "production" else "http://localhost:3000,http://localhost:8000").split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database schema on startup
@app.on_event("startup")
def on_startup():
    init_db()

from fastapi.responses import HTMLResponse
import os

STATIC_INDEX_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "index.html")

@app.get("/", response_class=HTMLResponse, tags=["الواجهة الأمامية (Frontend Web App)"])
def serve_frontend():
    if os.path.exists(STATIC_INDEX_PATH):
        with open(STATIC_INDEX_PATH, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>منظومة إدارة المعرفة المؤسسية جاهزة</h1>")

@app.get("/api/health", tags=["الحالة العامة (Health)"])
def health():
    return {
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online"
    }


@app.get("/api/ready", tags=["الحالة العامة (Health)"])
def ready():
    from fastapi import HTTPException
    from app.db import get_db
    try:
        with get_db() as conn:
            conn.execute("SELECT 1").fetchone()
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ready"}

# Mount routers
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(workspaces.router, prefix=settings.API_V1_PREFIX)
app.include_router(documents.router, prefix=settings.API_V1_PREFIX)
app.include_router(decisions.router, prefix=settings.API_V1_PREFIX)
app.include_router(knowledge_transfer.router, prefix=settings.API_V1_PREFIX)
app.include_router(skills.router, prefix=settings.API_V1_PREFIX)
app.include_router(collaboration.router) # WebSocket route /ws/documents/{document_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
