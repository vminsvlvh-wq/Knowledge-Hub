import os

class Settings:
    PROJECT_NAME: str = "KnowledgeHub Saudi 2030"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 24 hours
    
    DB_PATH: str = os.getenv(
        "DATABASE_PATH",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "km.db")
    )

settings = Settings()
if os.getenv("ENVIRONMENT", "development").lower() == "production":
    if len(settings.JWT_SECRET_KEY) < 32:
        raise RuntimeError("Set JWT_SECRET_KEY to a random 32+ character value in production")
    if not os.getenv("DATABASE_URL", "").startswith(("postgresql://", "postgres://")):
        raise RuntimeError("Production requires a dedicated PostgreSQL DATABASE_URL")
