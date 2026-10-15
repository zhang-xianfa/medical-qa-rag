"""FastAPI 依赖注入：JWT 认证"""
import os
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

SECRET_KEY = os.getenv("JWT_SECRET", "change-me-to-a-random-secret-in-env")
ALGORITHM = "HS256"

security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """从 JWT token 解析当前登录用户"""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="无效的登录凭证")
        return {"user_id": user_id, "phone": payload.get("phone", "")}
    except JWTError:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
