"""
医疗问答 AI 工作流编排器（LangGraph）

阶段性串行流程：
  safety_check → basic_interview(循环) → expert_interview(循环) → response → END

基础问诊完成（LLM判断或达轮次上限）后，若 use_expert=True 则进入专家问诊，
专家问诊完成后再进入诊断报告。
"""
from workflow.state import MedicalQAState
from workflow.nodes.safety_check_node import safety_check_node
from workflow.nodes.basic_interview_node import basic_interview_node
from workflow.nodes.expert_interview_node import expert_interview_node
from workflow.nodes.response_node import response_node
from workflow.nodes.human_review_node import human_review_node
from workflow.routes import (
    route_by_intent,
    check_basic_interview_complete,
    check_expert_interview_complete,
    after_response,
)


def build_workflow():
    from langgraph.graph import StateGraph, END

    workflow = StateGraph(MedicalQAState)

    # 注册节点
    workflow.add_node("safety_check", safety_check_node)           # 安全安检入口
    workflow.add_node("basic_interview", basic_interview_node)     # 阶段1：基础问诊（纯 prompt 模板）
    workflow.add_node("expert_interview", expert_interview_node)   # 阶段2：专家问诊（RAG 知识增强）
    workflow.add_node("response", response_node)                   # 阶段3：生成诊断报告
    workflow.add_node("human_review", human_review_node)           # 人工兜底审核

    # 统一从安检进入
    workflow.set_entry_point("safety_check")

    # 安检后分流：医疗意图→基础问诊，否则→直接回复
    workflow.add_conditional_edges("safety_check", route_by_intent, {
        "basic_interview": "basic_interview",
        "response": "response",
    })

    # 阶段1：基础问诊循环 → 完成后进入专家问诊（或直接诊断）
    workflow.add_conditional_edges("basic_interview", check_basic_interview_complete, {
        "basic_interview": "basic_interview",
        "expert_interview": "expert_interview",
        "response": "response",
    })

    # 阶段2：专家问诊循环 → 完成后进入诊断报告
    workflow.add_conditional_edges("expert_interview", check_expert_interview_complete, {
        "expert_interview": "expert_interview",
        "response": "response",
    })

    # 回复后出口：正常结束或转人工审核
    workflow.add_conditional_edges("response", after_response, {
        "done": END,
        "human_review": "human_review",
    })

    # 人工审核完成后流程结束
    workflow.add_edge("human_review", END)

    return workflow.compile()
