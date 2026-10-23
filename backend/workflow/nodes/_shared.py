"""
问诊节点共享工具函数

被 basic_interview_node 和 expert_interview_node 共同引用。
包含：消息解析、知识上下文格式化。
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# 已问问题只保留最近 N 条，避免 prompt 无限膨胀
MAX_ASKED_QUESTIONS = 20
# 同一个问题最多问几遍，超过则强制推进到下一阶段
MAX_SAME_QUESTION = 2

_PUNCT_RE = re.compile(r"[\s，。？！?!,.、；;：:\"'“”‘’（）()]+")


def normalize_question(text: str) -> str:
    """把问题归一化后用于比较：去掉空白和标点，避免换个问号就当成新问题"""
    return _PUNCT_RE.sub("", text or "")


def register_question(asked: list[str], text: str) -> tuple[list[str], bool]:
    """登记本轮问题，并判断是否已经反复问同一个问题。

    Returns:
        (更新后的已问列表, 是否已经问过太多次)
    """
    asked = list(asked or [])
    key = normalize_question(text)
    if not key:
        return asked, False

    repeats = sum(1 for q in asked if normalize_question(q) == key)
    asked.append(text)
    if len(asked) > MAX_ASKED_QUESTIONS:
        asked = asked[-MAX_ASKED_QUESTIONS:]
    return asked, repeats >= MAX_SAME_QUESTION


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
