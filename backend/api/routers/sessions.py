"""
问诊会话管理 API 路由层（FastAPI Router）

会话元数据持久化到 PostgreSQL session_state 表。
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends

from api.schemas.session import UpdateSessionRequest, SessionResponse
from api.dependencies import get_current_user
from persistence.session_store import (
    load_state, save_state, load_messages,
    list_sessions_from_db, delete_session_from_db,
)

router = APIRouter()


@router.post("/sessions", status_code=201)
async def create_session(user: dict = Depends(get_current_user)):
    """创建新会话：用户身份从 JWT 解析，无需传参"""
    sid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    await save_state(sid, {
        "user_id": user["user_id"],
        "max_rounds": 10,
        "current_stage": "init",
        "round_count": 0,
        "red_flag_raised": False,
        "created_at": now.isoformat(),
    })

    return {
        "id": sid,
        "session_id": sid,
        "user_id": user["user_id"],
        "status": "active",
        "intent": "greeting",
        "current_stage": "init",
        "red_flag_raised": False,
        "round_count": 0,
        "max_rounds": 10,
        "close_reason": None,
        "closed_at": None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }


@router.get("/sessions")
async def list_sessions(
    status: str = None,
    limit: int = 20,
    offset: int = 0,
    user: dict = Depends(get_current_user),
):
    """查询会话列表：从 PostgreSQL 分页查询"""
    data, total = await list_sessions_from_db(
        status=status,
        user_id=user["user_id"],
        limit=limit,
        offset=offset,
    )

    return {
        "data": data,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
        },
    }


@router.get("/sessions/{session_id}")
async def get_session(session_id: uuid.UUID, user: dict = Depends(get_current_user)):
    """获取单个会话详情"""
    sid = str(session_id)
    state = await load_state(sid)
    if not state:
        raise HTTPException(status_code=404, detail="会话不存在")

    _, message_count = await load_messages(sid, limit=1)

    return {
        "id": sid,
        "session_id": sid,
        "status": state.get("current_stage", "init"),
        "current_stage": state.get("current_stage", "init"),
        "round_count": state.get("round_count", 0),
        "max_rounds": state.get("max_rounds", 10),
        "red_flag_raised": state.get("red_flag_raised", False),
        "medical_record_summary": state.get("diagnosis_result"),
        "message_count": message_count,
    }


@router.patch("/sessions/{session_id}")
async def update_session(session_id: uuid.UUID, req: UpdateSessionRequest, user: dict = Depends(get_current_user)):
    """更新会话配置"""
    sid = str(session_id)
    state = await load_state(sid)
    if not state:
        raise HTTPException(status_code=404, detail="会话不存在")

    if req.status:
        state["current_stage"] = req.status
    if req.max_rounds is not None:
        state["max_rounds"] = req.max_rounds

    await save_state(sid, state)

    return {
        "id": sid,
        "status": state.get("current_stage", "init"),
        "max_rounds": state.get("max_rounds", 10),
    }


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: uuid.UUID, user: dict = Depends(get_current_user)):
    """删除会话：级联删除消息 + 状态"""
    deleted = await delete_session_from_db(str(session_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="会话不存在")
