from fastapi import APIRouter, Depends

from api.dependencies import get_current_user
from persistence.audit_store import list_audit, summarize_audit

router = APIRouter()


@router.get("/sessions/{session_id}/safety")
async def list_safety_events(session_id: str, category: str = None, limit: int = 20,
                             offset: int = 0, user: dict = Depends(get_current_user)):
    """查询会话的安全审计事件（红线拦截 / PII 脱敏 / 诊断记录等）"""
    data, total = await list_audit(session_id, category=category, limit=limit, offset=offset)
    summary = await summarize_audit(session_id)

    return {
        "data": data,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
        },
        "summary": summary,
    }
