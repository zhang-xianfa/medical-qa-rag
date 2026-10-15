"""
问诊节点共享工具函数

被 basic_interview_node 和 expert_interview_node 共同引用。
包含：消息解析、知识上下文格式化。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def msg_role(msg) -> str:
    """从消息对象中提取角色类型（user/assistant）"""
    if hasattr(msg, "type"):
        t = msg.type
        return "user" if t == "human" else ("assistant" if t == "ai" else t)
    return msg.get("role", "")


def msg_content(msg) -> str:
    """从消息对象中提取文本内容"""
    if hasattr(msg, "content"):
        return msg.content or ""
    return msg.get("content", "")


def format_knowledge_context(search_results: list) -> str:
    """将检索结果格式化为可注入 prompt 的知识上下文字符串"""
    if not search_results:
        return "（暂无相关医学知识参考）"

    parts: list[str] = []
    for i, r in enumerate(search_results[:5], 1):
        content = r.get("content", "") if isinstance(r, dict) else (
            r.content if hasattr(r, "content") else ""
        )
        source = r.get("source", "") if isinstance(r, dict) else (
            r.source if hasattr(r, "source") else ""
        )
        if content:
            line = f"[参考{i}] {content[:500]}"
            if source:
                line += f" (来源: {source})"
            parts.append(line)

    return "\n".join(parts) if parts else "（暂无相关医学知识参考）"
