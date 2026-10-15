import logging
logging.basicConfig(level=logging.INFO, format='%(name)s | %(levelname)s | %(message)s')

from pathlib import Path
from dotenv import load_dotenv

_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import Settings
from api.routers import sessions, messages, safety_events, auth, profile

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from persistence.session_store import ensure_tables
    from persistence.database import _get_engine
    from sqlalchemy import text

    await ensure_tables()

    # 确保 users 表存在
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                phone         VARCHAR(20) NOT NULL UNIQUE,
                password_hash VARCHAR(128) NOT NULL,
                nickname      VARCHAR(50) NOT NULL,
                email         VARCHAR(100),
                avatar        VARCHAR(500),
                birth_date    DATE,
                gender        VARCHAR(10),
                height        FLOAT,
                weight        FLOAT,
                blood_type    VARCHAR(5),
                medical_info  JSONB DEFAULT '{}',
                is_active     BOOLEAN DEFAULT TRUE,
                created_at    TIMESTAMPTZ DEFAULT NOW(),
                updated_at    TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_users_phone ON users (phone)
        """))

    logger = logging.getLogger("main")
    logger.info("Database tables verified")
    yield


app = FastAPI(
    title="医疗智能问答系统",
    description="AI 医疗健康咨询平台 API",
    version="1.0.0",
    docs_url="/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router, prefix="/api/v1", tags=["Sessions"])
app.include_router(messages.router, prefix="/api/v1", tags=["Messages"])
app.include_router(safety_events.router, prefix="/api/v1", tags=["Safety"])
app.include_router(auth.router, prefix="/api/v1", tags=["Auth"])
app.include_router(profile.router, prefix="/api/v1", tags=["Profile"])


@app.get("/api/health")
@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "components": {
            "database": "up",
            "vector_store": "pgvector",
            "llm": "up",
        },
        "uptime_seconds": 0,
    }
