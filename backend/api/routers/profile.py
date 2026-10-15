"""个人中心路由：查看 + 修改个人信息"""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from persistence.database import _get_engine
from api.dependencies import get_current_user
from api.schemas.auth import ProfileResponse, UpdateProfileRequest

router = APIRouter()


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(user: dict = Depends(get_current_user)):
    """获取当前用户的个人信息"""
    engine = _get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT id, phone, nickname, email, avatar, birth_date,
                       gender, height, weight, blood_type, medical_info
                FROM users WHERE id = :uid
            """),
            {"uid": user["user_id"]},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="用户不存在")

    return ProfileResponse(
        user_id=str(row[0]), phone=row[1], nickname=row[2],
        email=row[3], avatar=row[4],
        birth_date=row[5].isoformat() if row[5] else None,
        gender=row[6], height=row[7], weight=row[8], blood_type=row[9],
        medical_info=row[10] if row[10] else {},
    )


@router.patch("/profile", response_model=ProfileResponse)
async def update_profile(req: UpdateProfileRequest, user: dict = Depends(get_current_user)):
    """修改个人信息（PATCH：只更新传入的字段）"""
    engine = _get_engine()

    # 构建更新字段
    updates = {}
    if req.nickname is not None:
        updates["nickname"] = req.nickname
    if req.email is not None:
        updates["email"] = req.email
    if req.avatar is not None:
        updates["avatar"] = req.avatar
    if req.birth_date is not None:
        updates["birth_date"] = req.birth_date
    if req.gender is not None:
        updates["gender"] = req.gender
    if req.height is not None:
        updates["height"] = req.height
    if req.weight is not None:
        updates["weight"] = req.weight
    if req.blood_type is not None:
        updates["blood_type"] = req.blood_type

    # medical_info 单独处理（JSONB 部分更新）
    if any(x is not None for x in [req.allergies, req.chronic_diseases, req.surgeries, req.family_history]):
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT medical_info FROM users WHERE id = :uid"),
                {"uid": user["user_id"]},
            )
            row = result.fetchone()
            medical = row[0] if row and row[0] else {}

        if req.allergies is not None:
            medical["allergies"] = req.allergies
        if req.chronic_diseases is not None:
            medical["chronic_diseases"] = req.chronic_diseases
        if req.surgeries is not None:
            medical["surgeries"] = req.surgeries
        if req.family_history is not None:
            medical["family_history"] = req.family_history

        updates["medical_info"] = json.dumps(medical, ensure_ascii=False)

    if not updates:
        return await get_profile(user)

    # 执行更新
    set_clauses = []
    params = {"uid": user["user_id"]}
    for i, (k, v) in enumerate(updates.items()):
        if k == "medical_info":
            set_clauses.append(f"{k} = :{k}")
            params[k] = v  # json string
        else:
            set_clauses.append(f"{k} = :{k}")
            params[k] = v

    sql = f"UPDATE users SET {', '.join(set_clauses)} WHERE id = :uid"
    async with engine.begin() as conn:
        await conn.execute(text(sql), params)

    return await get_profile(user)
