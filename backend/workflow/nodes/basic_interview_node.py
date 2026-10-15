"""基础问诊节点（基于提示词模板，不注入知识库上下文）"""
import logging
import json

from llm.real_llm_adapter import RealL2Adapter
from workflow.nodes._shared import msg_role, msg_content

logger = logging.getLogger(__name__)
_adapter = RealL2Adapter()


async def basic_interview_node(state: dict) -> dict:
    """基础问诊：纯 prompt 模板驱动，不检索知识库"""
    collected_info = state.get("collected_info", {})
    round_count = state.get("round_count", 0)
    total_max_rounds = state.get("max_rounds", 10)
    basic_max_rounds = state.get("scenario_context", {}).get("basic_max_rounds", 5)
    messages = state.get("messages", [])

    # 安全熔断
    if state.get("red_flag_raised"):
        return {"current_stage": "emergency", "max_rounds": total_max_rounds}

    # 防自说自话
    if messages and msg_role(messages[-1]) in ("assistant", "ai"):
        return {"current_stage": "collect", "max_rounds": total_max_rounds}

    last_user = next((msg_content(m) for m in reversed(messages) if msg_role(m) == "user"), "")

    # 初始化患者主诉
    if round_count == 0:
        collected_info.setdefault("patient_info", {})["chief_complaint"] = last_user.strip()
        round_count = 1

    # 格式化消息
    formatted_messages = []
    for msg in messages:
        formatted_messages.append({"role": msg_role(msg), "content": msg_content(msg)})

    logger.info("BasicInterview messages: %s", json.dumps(formatted_messages, ensure_ascii=False))

    # 调用 LLM 生成问题（告知基础阶段轮次上限）
    try:
        llm_result = await _adapter.generate_question(
            collected_facts=collected_info,
            scenario_context=state.get("scenario_context", {}),
            messages=formatted_messages,
            round_count=round_count,
            max_rounds=basic_max_rounds,
        )
    except Exception as e:
        logger.error("Basic LLM failed: %s", e)
        raise RuntimeError(f"LLM generation failed: {e}") from e

    # 提取结构化信息
    if extracted := llm_result.get("extracted_facts"):
        patient_info = collected_info.setdefault("patient_info", {})
        if isinstance(extracted, dict) and "patient_info" in extracted:
            extracted = extracted["patient_info"]
        patient_info.update(extracted)

    logger.info("Basic collected: %s", json.dumps(collected_info, ensure_ascii=False))

    next_action = llm_result.get("next_action", "continue")
    round_count += 1

    # 终止判断（基础阶段使用 basic_max_rounds）
    if next_action in ("assess", "emergency") or round_count >= basic_max_rounds:
        stage = "emergency" if next_action == "emergency" else "diagnose"
        return {
            "collected_info": collected_info,
            "round_count": round_count,
            "max_rounds": total_max_rounds,
            "current_stage": stage,
            "search_results": state.get("search_results", []),
        }

    return {
        "collected_info": collected_info,
        "round_count": round_count,
        "max_rounds": total_max_rounds,
        "current_stage": "collect",
        "messages": [{"role": "assistant", "content": llm_result["response_text"]}],
        "options": llm_result.get("options", []),
        "search_results": state.get("search_results", []),
    }
