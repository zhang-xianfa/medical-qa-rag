"""专家问诊节点（RAG 知识增强）

与基础问诊节点的核心差异：
1. 每轮**同步**检索知识库
2. 检索结果注入 prompt 模板，让 LLM 基于医学知识生成更专业的选择题
3. 使用 expert_consultation.j2 模板（含 {{ knowledge_context }} 区块）
"""

import logging
import json
import traceback

from llm.real_llm_adapter import RealL2Adapter
from knowledge.retriever import retrieve_for_symptoms
from workflow.nodes._shared import msg_role, msg_content, format_knowledge_context

logger = logging.getLogger(__name__)
_adapter = RealL2Adapter()


async def expert_interview_node(state: dict) -> dict:
    """专家问诊：同步检索知识库 → 注入 prompt → 生成知识增强选择题"""
    collected_info = state.get("collected_info", {})
    round_count = state.get("round_count", 0)
    max_rounds = state.get("max_rounds", 10)
    messages = state.get("messages", [])

    # 安全熔断
    if state.get("red_flag_raised"):
        return {"current_stage": "emergency", "max_rounds": max_rounds}

    # 防自说自话
    if messages and msg_role(messages[-1]) in ("assistant", "ai"):
        return {"current_stage": "collect", "max_rounds": max_rounds}

    last_user = next((msg_content(m) for m in reversed(messages) if msg_role(m) == "user"), "")

    # 初始化患者主诉
    if round_count == 0:
        collected_info.setdefault("patient_info", {})["chief_complaint"] = last_user.strip()
        round_count = 1

    # 格式化消息
    formatted_messages = []
    for msg in messages:
        formatted_messages.append({"role": msg_role(msg), "content": msg_content(msg)})

    logger.info("ExpertInterview messages: %s", json.dumps(formatted_messages, ensure_ascii=False))

    # ── 专家节点核心差异：同步知识库检索 ──
    scenario_context = dict(state.get("scenario_context", {}))
    scenario_context["prompt_template"] = "expert_consultation"

    search_results = []
    try:
        search_results = await retrieve_for_symptoms(collected_info, top_k=5)
        knowledge_context = format_knowledge_context(search_results)
        scenario_context["knowledge_context"] = knowledge_context

        count = len(search_results) if search_results else 0
        logger.debug("检索到 %d 条结果", count)
        if search_results:
            for i, r in enumerate(search_results, 1):
                title = r.get('title', '') if isinstance(r, dict) else getattr(r, 'title', '')
                content_excerpt = (r.get('content_excerpt', '') if isinstance(r, dict) else getattr(r, 'content', ''))
                logger.debug("  %s: %.80s", title or f"item_{i}", content_excerpt or "")
        else:
            logger.debug("  未检索到相关知识条目")

        logger.info(
            "Expert: retrieved %d knowledge entries for round %d",
            count, round_count,
        )
    except Exception as e:
        logger.debug("专家问诊节点知识库检索失败: %s - %s", type(e).__name__, str(e) or '(无)')
        logger.debug("详细追踪: %s", traceback.format_exc())
        logger.warning("Expert knowledge retrieval failed, proceeding without: %s", e)
        scenario_context["knowledge_context"] = "（知识库检索暂不可用，请基于通用医学知识进行问诊）"

    # 调用 LLM 生成知识增强问题
    try:
        llm_result = await _adapter.generate_question(
            collected_facts=collected_info,
            scenario_context=scenario_context,
            messages=formatted_messages,
            round_count=round_count,
            max_rounds=max_rounds,
        )
    except Exception as e:
        logger.error("Expert LLM failed: %s", e)
        raise RuntimeError(f"LLM generation failed: {e}") from e

    # 提取结构化信息
    if extracted := llm_result.get("extracted_facts"):
        patient_info = collected_info.setdefault("patient_info", {})
        if isinstance(extracted, dict) and "patient_info" in extracted:
            extracted = extracted["patient_info"]
        patient_info.update(extracted)

    logger.info("Expert collected: %s", json.dumps(collected_info, ensure_ascii=False))

    # ── 合并本轮的检索结果到 state（去重）──
    old_results = state.get("search_results", [])
    if search_results:
        old_ids = {r.get("knowledge_entry_id", "") for r in old_results if isinstance(r, dict)}
        for r in search_results:
            if hasattr(r, "content"):
                rid = r.knowledge_entry_id if hasattr(r, "knowledge_entry_id") else r.get("knowledge_entry_id", "")
                if rid and rid not in old_ids:
                    old_ids.add(rid)
                    old_results.append({
                        "content": r.content, "source": r.source,
                        "knowledge_entry_id": rid,
                        "relevance_score": r.relevance_score if hasattr(r, "relevance_score") else 0,
                    })
    merged_results = old_results

    next_action = llm_result.get("next_action", "continue")
    round_count += 1

    # 终止判断
    if next_action in ("assess", "emergency") or round_count >= max_rounds:
        stage = "emergency" if next_action == "emergency" else "diagnose"
        return {
            "collected_info": collected_info,
            "round_count": round_count,
            "max_rounds": max_rounds,
            "current_stage": stage,
            "search_results": merged_results,
        }

    return {
        "collected_info": collected_info,
        "round_count": round_count,
        "max_rounds": max_rounds,
        "current_stage": "collect",
        "messages": [{"role": "assistant", "content": llm_result["response_text"]}],
        "options": llm_result.get("options", []),
        "search_results": merged_results,
    }
