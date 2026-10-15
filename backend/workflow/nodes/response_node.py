import logging

from config.settings import Settings

logger = logging.getLogger(__name__)

settings = Settings()


async def response_node(state: dict) -> dict:
    intent = state.get("intent", "greeting")              # 用户意图：greeting(问候)/diagnosis(诊断)/question(咨询)等
    current_stage = state.get("current_stage", "")        # 当前对话阶段：init(初始)/collect(信息收集)/diagnose(诊断)/done(完成)
    red_flag_raised = state.get("red_flag_raised", False) # 是否触发危险信号（红旗症状）
    collected_info = state.get("collected_info", {})      # 已收集的患者信息（主诉、症状、病史等）
    search_results = state.get("search_results", [])      # 知识库检索结果
    disclaimer = settings.DISCLAIMER_TEXT                  # 免责声明文本（从配置读取）
    messages = state.get("messages", [])                  # 对话消息历史

    output = ""
    # 如果检测到危险信号或下一阶段为紧急情况
    if red_flag_raised or state.get("next_stage") == "emergency":
        # 输出紧急就医提示（优先使用状态中的output，否则使用默认提示）
        output = state.get("output", "") or "您描述的症状需要立即就医。请立即拨打120急救电话，保持镇定，不要自行驾车就医。"
        dr = {
            "primary_diagnosis": {"name": "紧急情况", "probability": "N/A", "rationale": "红旗症状触发", "certainty_level": "high"},
            "risk_assessment": {"severity": "危及生命", "urgency": "立即急诊", "warning_signs": []},
            "recommendations": [{"category": "就医建议", "content": "立即拨打120或前往最近急诊科", "priority": 1}],
            "red_flags": [{"symptom": "用户描述包含紧急红旗症状", "action": "立即急诊就医"}],
            "references": [],
            "disclaimer": disclaimer,
        }
        return {"messages": [{"role": "assistant", "content": output}], "current_stage": "done", "diagnosis_result": dr}

    next_stage = "done" # 默认完成

    if intent in ("greeting",):
        output = "您好！我是智能健康助手。请描述您的症状，我会尽力帮助您分析。请注意，本系统不能替代专业医疗诊断，如有紧急情况请立即就医。"
    elif intent in ("question",) and search_results:
        fragments = [r.get("content", "")[:200] for r in search_results[:3] if isinstance(r, dict)]
        output = "根据相关知识库：" + "；".join(fragments) + f"\n\n{disclaimer}"
    elif current_stage == "collect":
        output = _extract_last_assistant_message(messages) or "请继续描述您的症状。"
        next_stage = "collect"
        logger.info("response_node collect: msgcount=%d output_len=%d preview=%s",
                     len(messages), len(output), output[:80])
    elif current_stage == "diagnose":
        from workflow.diagnosis_agent import DiagnosisAgent
        output = await DiagnosisAgent().generate(collected_info, search_results, messages, disclaimer)
    else:
        output = f"我已收到您的信息。{disclaimer}"

    if state.get("blocked"):
        output = state.get("output", "请咨询医生")

    return {"messages": [{"role": "assistant", "content": output}], "current_stage": next_stage, "output": output}


def _extract_last_assistant_message(messages: list) -> str:
    for msg in reversed(messages):
        role = msg.get("role", "") if isinstance(msg, dict) else getattr(msg, "type", "")
        content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
        if role in ("assistant", "ai"):
            return content or ""
    return ""


