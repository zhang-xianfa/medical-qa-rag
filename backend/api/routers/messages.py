# =============================================================================
# 问诊对话 API 路由层（FastAPI Router）
#
# 会话状态和消息已接入 PostgreSQL 持久化存储（persistence/session_store.py）。
# =============================================================================

import logging
import uuid
import json
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from api.schemas.message import SendMessageRequest, SendMessageResponse, MessageResponse
from api.dependencies import get_current_user
from workflow.graph import build_workflow
from persistence.database import _get_engine
from persistence.session_store import (
    load_state, save_state, append_message, load_messages,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_graph():
    return build_workflow()


@router.post("/sessions/{session_id}/messages")
async def send_message(session_id: uuid.UUID, req: SendMessageRequest, user: dict = Depends(get_current_user)):
    """
    发送消息接口：用户每发一条消息，就驱动AI问诊引擎走一步。

    完整流程：
    1. 把用户消息存入历史记录
    2. 组装引擎所需的初始状态（state）
    3. 调用 LangGraph 工作流执行一轮推理
    4. 根据引擎输出判断下一步动作，封装成标准响应返回
    """
    graph = _get_graph()

    sid = str(session_id)

    # ---- 第1步：从 DB 加载累积状态 ----
    prev = await load_state(sid)

    # 从 DB 加载完整历史消息（转换为工作流引擎需要的格式）
    all_msgs, _ = await load_messages(sid, limit=200, need_count=False)
    history_messages = []
    for msg in all_msgs:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role and content:
            history_messages.append({"role": role, "content": content})
    # 追加当前用户消息（尚未持久化到 DB；workflow 需要它作为输入）
    history_messages.append({"role": "user", "content": req.content})
    
    state = {
        "messages": history_messages,
        "intent": "diagnosis",
        "red_flag_raised": prev.get("red_flag_raised", False),
        "safety_checks_passed": prev.get("safety_checks_passed", True),
        "collected_info": prev.get("collected_info", {}),
        "search_results": prev.get("search_results", []),
        "search_queries": prev.get("search_queries", []),
        "diagnosis_result": prev.get("diagnosis_result"),
        "round_count": prev.get("round_count", 0),
        "max_rounds": prev.get("max_rounds", 5),
        "session_id": sid,
        "current_stage": prev.get("current_stage", "init"),
        "route_decision": prev.get("route_decision", ""),
        "current_scenario": prev.get("current_scenario", "general_consultation"),
        "scenario_context": prev.get("scenario_context", {}),
        "options": prev.get("options", []),
    }

    if not state.get("scenario_context"):
        sc = _detect_scenario(req.content)
        state["scenario_context"] = sc
        # 将场景配置中的参数应用到 state（仅首次）
        if sc.get("use_expert"):
            state["use_expert"] = True
        if sc.get("max_rounds"):
            state["max_rounds"] = sc["max_rounds"]

    # 确保 use_expert 从持久化的 scenario_context 中恢复到 state
    if state.get("scenario_context", {}).get("use_expert"):
        state["use_expert"] = True

    # ---- 注入用户个人健康信息（仅首轮）----
    if state["round_count"] == 0:
        user_id = prev.get("user_id", "")
        if user_id:
            user_profile = await _load_user_profile(user_id)
            if user_profile:
                patient_info = state["collected_info"].setdefault("patient_info", {})
                for key, value in user_profile.items():
                    if key not in patient_info or patient_info[key] is None:
                        patient_info[key] = value
                logger.info("Injected user profile: %d fields for user=%s",
                            len(user_profile), user_id[:8])

    # ---- 第3步：执行AI工作流 ----
    result = await graph.ainvoke(state)

    # ---- 第4步：持久化用户消息（仅在 workflow 成功后）----
    user_msg = {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "round_number": prev.get("round_count", 0),
        "role": "user",
        "content": req.content,
        "content_type": req.content_type,
        "agent_source": None,
        "token_count": None,
        "created_at": datetime.now(timezone.utc),
    }
    await append_message(sid, user_msg)

    # ---- 保存状态到 DB ----
    await save_state(sid, {
        "collected_info": result.get("collected_info", {}),
        "round_count": result.get("round_count", 0),
        "max_rounds": result.get("max_rounds", prev.get("max_rounds", 5)),
        "current_stage": result.get("current_stage", "init"),
        "red_flag_raised": result.get("red_flag_raised", False),
        "safety_checks_passed": result.get("safety_checks_passed", True),
        "search_results": result.get("search_results", []),
        "title": prev.get("title") or req.content[:40],
        "search_queries": result.get("search_queries", []),
        "diagnosis_result": result.get("diagnosis_result"),
        "route_decision": result.get("route_decision", ""),
        "current_scenario": result.get("current_scenario", "general_consultation"),
        "scenario_context": result.get("scenario_context", prev.get("scenario_context", {})),
        "options": result.get("options", []),
    })

    # ---- 第5步：根据引擎输出决定前端下一步动作 ----
    red_flag = result.get("red_flag_raised", False)
    stage = result.get("current_stage", "init")
    round_count = result.get("round_count", 0)
    collected = result.get("collected_info", {})

    next_action = "continue"              # 默认继续对话
    if red_flag:
        next_action = "emergency_interrupted"   # 触发紧急中断
    elif stage == "diagnose":
        next_action = "diagnosis_ready"         # 可以出诊断了
    elif stage == "done":
        next_action = "completed"               # 问诊流程结束

    assistant_reply = _extract_assistant_reply(result.get("messages", []))

    # 提取选项（需在持久化 AI 消息之前，以便一并存储）
    options = result.get("options", []) if stage == "collect" else []

    if assistant_reply:
        ai_msg = {
            "id": str(uuid.uuid4()),
            "session_id": sid,
            "round_number": round_count,
            "role": "assistant",
            "content": assistant_reply,
            "content_type": "text",
            "agent_source": "system",
            "token_count": None,
            "options": options,
            "created_at": datetime.now(timezone.utc),
        }
        await append_message(sid, ai_msg)

    return SendMessageResponse(
        message=MessageResponse(**user_msg),
        session_status="active",
        current_stage=stage,
        red_flag_raised=red_flag,
        round_count=round_count,
        collected_fields_summary=_summarize(collected),
        next_action=next_action,
        response_content=assistant_reply,
        options=options,
        scenario=result.get("current_scenario"),
    )


@router.get("/sessions/{session_id}/messages")
async def list_messages(session_id: uuid.UUID, limit: int = 20, offset: int = 0, round_number: int = None, user: dict = Depends(get_current_user)):
    """查询历史消息：支持分页 + 按轮次过滤"""
    data, total = await load_messages(
        str(session_id), limit=limit, offset=offset, round_number=round_number,
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


@router.get("/sessions/{session_id}/stream")
async def stream_events(session_id: uuid.UUID, user: dict = Depends(get_current_user)):
    """
    SSE流式推送接口：实时向前端推送问诊过程中的各类事件。

    ⚠️ 当前为占位实现！仅发送心跳和欢迎语。
    生产环境应接入工作流引擎的异步事件队列，
    实时推送 message / diagnosis_progress / emergency 等事件。
    """
    async def event_stream():
        # 先发一个心跳，确认连接建立成功
        yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
        # 再发一条欢迎消息作为示例
        yield f"data: {json.dumps({'type': 'message', 'role': 'assistant', 'content': '您好，请描述您的症状。'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",       # 禁止缓存，确保实时性
            "Connection": "keep-alive",        # 保持长连接
            "X-Accel-Buffering": "no",         # 关闭Nginx缓冲，防止SSE被攒批发送
        },
    )


async def _load_user_profile(user_id: str) -> dict:
    """从 users 表加载用户个人健康信息，转为 workflow 可用格式"""
    if not user_id:
        return {}

    engine = _get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT gender, birth_date, height, weight, blood_type, medical_info FROM users WHERE id = :uid"),
            {"uid": user_id},
        )
        row = result.fetchone()
        if not row:
            return {}

    profile = {}
    if row[0]:  # gender
        profile["gender"] = row[0]
    if row[1]:  # birth_date → age
        today = date.today()
        bd = row[1]
        age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
        profile["age"] = age
    if row[2]:  # height
        profile["height"] = row[2]
    if row[3]:  # weight
        profile["weight"] = row[3]
    if row[4]:  # blood_type
        profile["blood_type"] = row[4]
    if row[5]:  # medical_info JSON
        medical = row[5] or {}
        if medical.get("allergies"):
            profile["allergies"] = medical["allergies"]
        if medical.get("chronic_diseases"):
            profile["chronic_diseases"] = medical["chronic_diseases"]
        if medical.get("surgeries"):
            profile["surgeries"] = medical["surgeries"]
        if medical.get("family_history"):
            profile["family_history"] = medical["family_history"]

    return profile


def _detect_scenario(user_msg: str) -> dict:
    return {
        "scenario_id": "general_consultation",
        "prompt_template": "basic_consultation",
        "display_name": "通用健康咨询",
        "max_rounds": 10,
        "use_expert": True,        # 启用专家模式：基础阶段结束后进入专家问诊
        "basic_max_rounds": 5,     # 基础问诊最多 5 轮，之后 LLM 判断结束或达上限→专家
    }


def _extract_assistant_reply(messages: list) -> str:
    for msg in reversed(messages):
        role = msg.get("role", "") if isinstance(msg, dict) else getattr(msg, "type", "")
        content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
        if role in ("assistant", "ai"):
            return content or ""
    return ""


def _summarize(collected: dict) -> dict:
    summary = {}
    patient_info = collected.get("patient_info", {})
    for key, value in patient_info.items():
        if value is not None:
            summary[key] = value
    for key in ("pain_character", "swelling", "redness", "heat", "accompanying_symptoms"):
        if key in collected and collected[key] is not None:
            summary[key] = collected[key]
    return summary