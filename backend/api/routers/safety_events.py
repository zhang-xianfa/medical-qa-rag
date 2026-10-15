from fastapi import APIRouter, Depends

from api.dependencies import get_current_user

router = APIRouter()


@router.get("/sessions/{session_id}/safety")
async def list_safety_events(session_id: str, category: str = None, limit: int = 20, offset: int = 0, user: dict = Depends(get_current_user)):
    data = []
    return {
        "data": data,
        "pagination": {"total": 0, "limit": limit, "offset": offset, "has_more": False},
        "summary": {"total_events": 0, "red_flag_count": 0, "pii_detection_count": 0},
    }
