"""
注意：此 State 仅用于后端各节点间传递数据（黑板模式）。
严禁直接将此对象序列化后作为 API 响应返回给前端！
对外接口请在 response_node 中按需提取字段，并按 SDD-03 契约重新组装。
"""

from typing import TypedDict, List, Optional, Annotated
from langgraph.graph.message import add_messages


def dict_merge(left: dict, right: dict) -> dict:
    if isinstance(right, list) and isinstance(left, list):
        seen = {r.get("knowledge_entry_id", "") for r in left if isinstance(r, dict)}
        merged = list(left)
        for item in right:
            if isinstance(item, dict) and item.get("knowledge_entry_id", "") not in seen:
                seen.add(item["knowledge_entry_id"])
                merged.append(item)
        return merged
    if not isinstance(right, dict):
        return left
    merged = dict(left)
    for k, v in right.items():
        if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
            merged[k] = dict_merge(merged[k], v)
        else:
            merged[k] = v
    return merged


class MedicalQAState(TypedDict):
    """
    LangGraph 工作流核心状态契约。

    注意: 此状态模型需与 architecture-decisions.md 中的 SDD-01-State契约 保持同步。
    新增/修改字段前须确认对应 ADR 已审批，避免节点间数据契约断裂。
    """

    # --- 对话历史 (使用 LangGraph 内置 reducer 自动追加消息) ---
    messages: Annotated[List[dict], add_messages]  # 全量对话消息

    # --- 问诊选项 ---
    options: List[dict]  # 当前问题的选择题选项

    # --- 流程控制 ---
    current_stage: str  # 对话阶段标识
    intent: str  # 用户识别意图
    route_decision: str  # 节点路由判断
    round_count: int  # 当前问诊轮数
    max_rounds: int  # 最大问诊上限

    # --- 信息收集与检索 (dict_merge: 累计合并，新值覆盖旧值) ---
    collected_info: Annotated[dict, dict_merge]  # 提取的用户关键信息
    search_queries: List[str]  # 知识库检索问句
    search_results: Annotated[List[dict], dict_merge]  # 检索返回内容（列表合并+去重）
    scenario_context: Annotated[dict, dict_merge]  # 场景全局上下文

    # --- 诊断与安全 ---
    diagnosis_result: Optional[dict]  # 最终诊断评估结果
    red_flag_raised: bool  # 是否识别高危风险
    safety_checks_passed: bool  # 安全校验是否通过

    # --- 会话标识 ---
    session_id: str  # 会话唯一编号
    current_scenario: str  # 当前业务场景类型
