import sys

# 日志固定 UTF-8：否则 Windows 下重定向到文件会按 cp936 写，中文全乱码
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

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
    from persistence.audit_store import ensure_audit_tables
    from persistence.database import _get_engine
    from sqlalchemy import text

    await ensure_tables()
    await ensure_audit_tables()

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


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    """兜底异常：统一成前端认识的 {error, code, message} 结构，不暴露堆栈。"""
    logging.getLogger("main").exception(
        "Unhandled error on %s %s: %s", request.method, request.url.path, exc
    )
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=500,
        content={"error": "INTERNAL_ERROR", "code": 500, "message": "服务暂时不可用，请稍后重试"},
    )

app.include_router(sessions.router, prefix="/api/v1", tags=["Sessions"])
app.include_router(messages.router, prefix="/api/v1", tags=["Messages"])
app.include_router(safety_events.router, prefix="/api/v1", tags=["Safety"])
app.include_router(auth.router, prefix="/api/v1", tags=["Auth"])
app.include_router(profile.router, prefix="/api/v1", tags=["Profile"])


@app.get("/api/health")
@app.get("/api/v1/health")
async def health_check():
    """真实检查数据库连通性，别返回写死的 healthy"""
    from persistence.database import check_db_connection

    db_ok = await check_db_connection()
    return {
        "status": "healthy" if db_ok else "degraded",
        "version": "1.0.0",
        "components": {
            "database": "up" if db_ok else "down",
            "vector_store": settings.VECTOR_STORE_BACKEND,
            "llm": "configured" if settings.DEEPSEEK_API_KEY else "missing_key",
        },
        "uptime_seconds": 0,
    }
