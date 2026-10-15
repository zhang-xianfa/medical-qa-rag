"""认证路由：注册 + 登录"""
import time
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException
import bcrypt
from jose import jwt
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from persistence.database import _get_engine
from api.schemas.auth import RegisterRequest, LoginRequest, TokenResponse

router = APIRouter()

import os
SECRET_KEY = os.getenv("JWT_SECRET", "change-me-to-a-random-secret-in-env")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


@router.post("/auth/register", status_code=201)
async def register(req: RegisterRequest):
    """用户注册（SELECT + INSERT 在同一事务中，避免 TOCTOU 竞态条件）"""
    engine = _get_engine()
    user_id = str(uuid.uuid4())
    password_hash = _hash_password(req.password)

    async with engine.begin() as conn:
        # 事务内检查手机号是否已存在
        result = await conn.execute(
            text("SELECT id FROM users WHERE phone = :phone"),
            {"phone": req.phone},
        )
        if result.fetchone():
            raise HTTPException(status_code=409, detail="手机号已注册")

        # 事务内插入新用户，UNIQUE 约束兜底捕获并发冲突
        try:
            await conn.execute(
                text("""
                    INSERT INTO users (id, phone, password_hash, nickname)
                    VALUES (:id, :phone, :hash, :nickname)
                """),
                {"id": user_id, "phone": req.phone, "hash": password_hash, "nickname": req.nickname},
            )
        except IntegrityError:
            raise HTTPException(status_code=409, detail="手机号已注册")

    # 签发 token（事务外）
    token = _create_token(user_id, req.phone)
    return TokenResponse(access_token=token, user_id=user_id, nickname=req.nickname)


_login_attempts: dict[str, list[float]] = {}

def _check_rate_limit(phone: str, max_attempts: int = 5, window: int = 300) -> bool:
    """Returns True if within rate limit, False if exceeded."""
    now = time.time()
    attempts = [t for t in _login_attempts.get(phone, []) if now - t < window]
    _login_attempts[phone] = attempts
    return len(attempts) < max_attempts

def _record_attempt(phone: str):
    _login_attempts.setdefault(phone, []).append(time.time())


@router.post("/auth/login")
async def login(req: LoginRequest):
    """用户登录"""
    if not _check_rate_limit(req.phone):
        raise HTTPException(status_code=429, detail="登录尝试过于频繁，请5分钟后再试")

    engine = _get_engine()

    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT id, phone, password_hash, nickname FROM users WHERE phone = :phone"),
            {"phone": req.phone},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="手机号或密码错误")
        if not _verify_password(req.password, row[2]):
            raise HTTPException(status_code=401, detail="手机号或密码错误")

    _record_attempt(req.phone)
    _login_attempts.pop(req.phone, None)  # Clear rate limit on success

    token = _create_token(str(row[0]), row[1])
    return TokenResponse(access_token=token, user_id=str(row[0]), nickname=row[3])


def _create_token(user_id: str, phone: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {"sub": user_id, "phone": phone, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
