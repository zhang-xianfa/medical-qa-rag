"""
工作流路由决策器（交通信号灯）
根据 State 中的标志位，动态决定工作流的下一个节点走向。

核心路由规则：
1. 安全熔断优先：任何节点只要触发 red_flag_raised，立即强制跳转到 response 节点
2. 意图分流：医疗意图始终从基础问诊起步
3. 阶段性串行：
   - 基础问诊循环：LLM 判断结束(next_action="assess") 或 达到 basic_max_rounds → 进入专家或诊断
   - 专家问诊循环：LLM 判断结束 或 达到 max_rounds → 进入诊断报告
4. 人工兜底触发：仅当 response 节点标记 fallback_triggered 时转人工审核

关键约束：
- 所有路由函数必须是无状态的纯函数，禁止修改 state、禁止依赖全局可变状态
- 路由返回值必须与 build_workflow() 中 conditional_edges 的映射键严格一致
"""

import logging

from llm.real_llm_adapter import RealRouterLLM

logger = logging.getLogger(__name__)

_router_llm: RealRouterLLM | None = None


def _get_router() -> RealRouterLLM:
    global _router_llm
    if _router_llm is None:
        _router_llm = RealRouterLLM()
    return _router_llm


def _extract_last_user_message(state: dict) -> str:
    messages = state.get("messages", [])
    for msg in reversed(messages):
        role = msg.get("role", "") if isinstance(msg, dict) else getattr(msg, "type", "")
        content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
        if role == "user" or role == "human":
            return content or ""
    return ""


def _last_is_assistant(messages: list) -> bool:
    if not messages:
        return False
    last = messages[-1]
    role = last.get("role", "") if isinstance(last, dict) else getattr(last, "type", "")
    return role in ("assistant", "ai")


def _should_use_expert(state: dict) -> bool:
    """判断是否启用专家问诊阶段"""
    if state.get("use_expert"):
        return True
    scenario = state.get("scenario_context", {})
    return bool(scenario.get("use_expert"))


# ═══════════════════════════════════════════════════════════════
# 路由函数
# ═══════════════════════════════════════════════════════════════


async def route_by_intent(state: dict) -> str:
    """安检后路由：非医疗意图→直接回复，医疗意图→从基础问诊开始"""
    if state.get("red_flag_raised"):
        return "response"

    intent = state.get("intent", "greeting")

    try:
        last_msg = _extract_last_user_message(state)
        if last_msg:
            routes = await _get_router().classify(last_msg)
            if routes and routes[0][0] in ("general_consultation",):
                scenario_id = routes[0][0]
                logger.info("LLM routed: scenario=%s confidence=%.2f", scenario_id, routes[0][1])
                state["route_decision"] = scenario_id
                state["route_confidence"] = routes[0][1]
                state["route_rationale"] = routes[0][2]
                state["current_scenario"] = scenario_id
                return "basic_interview"
    except Exception:
        logger.debug("RealRouterLLM unavailable, using hardcoded routing")

    if intent in ("diagnosis", "follow_up"):
        return "basic_interview"
    if intent == "emergency":
        return "response"
    return "response"


def check_basic_interview_complete(state: dict) -> str:
    """基础问诊循环控制：
    - LLM 判断信息足够(next_action="assess") 或 达轮次上限 → 结束基础阶段
    - 如果 use_expert=True → 进入专家问诊
    - 否则 → 直接进入诊断报告
    """
    if state.get("red_flag_raised"):
        return "response"

    current_stage = state.get("current_stage", "")

    # 紧急情况
    if current_stage == "emergency":
        return "response"

    # 基础问诊完成：LLM 认为可以评估，或达到轮次上限
    if current_stage == "diagnose" or current_stage == "emergency":
        if _should_use_expert(state):
            logger.info("Basic interview complete → switching to expert")
            # 重置 current_stage 让专家节点开始工作
            state["current_stage"] = "expert"
            return "expert_interview"
        return "response"

    # 防自说自话
    if current_stage == "collect" and _last_is_assistant(state.get("messages", [])):
        return "response"

    # 继续基础问诊
    return "basic_interview"


def check_expert_interview_complete(state: dict) -> str:
    """专家问诊循环控制：
    - LLM 判断信息足够 或 达总轮次上限 → 进入诊断报告
    - 否则继续专家问诊
    """
    if state.get("red_flag_raised"):
        return "response"

    current_stage = state.get("current_stage", "")

    # 专家问诊完成
    if current_stage == "diagnose" or current_stage == "emergency":
        return "response"

    # 防自说自话
    if current_stage == "collect" and _last_is_assistant(state.get("messages", [])):
        return "response"

    # 继续专家问诊
    return "expert_interview"


def after_response(state: dict) -> str:
    if state.get("fallback_triggered"):
        return "human_review"
    return "done"
