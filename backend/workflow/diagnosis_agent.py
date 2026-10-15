"""
诊断Agent — 阶段3: 综合推理 + 输出
输入: 对话历史(messages) + search_results
输出: 综合分析文本 + 免责声明
"""
from __future__ import annotations

import logging
import os

from config.settings import Settings
from llm.real_llm_adapter import RealLLMAdapter, LLMAPIError, LLMRateLimitError, LLMTimeoutError
from llm.real_llm_adapter import _load_prompt_template, _split_system_user

logger = logging.getLogger(__name__)
settings = Settings()
_adapter: RealLLMAdapter | None = None  # LLM适配器单例


def _get_adapter() -> RealLLMAdapter:
    """获取LLM适配器单例"""
    global _adapter
    if _adapter is None:
        _adapter = RealLLMAdapter()
    return _adapter


class DiagnosisAgent:
    """诊断代理类：基于对话历史和知识库生成综合分析报告"""

    def __init__(self) -> None:
        self.adapter = _get_adapter()  # 获取LLM适配器

    async def generate(self, collected_info: dict, search_results: list,
                       messages: list, disclaimer: str) -> str:
        """
        生成诊断报告
        :param collected_info: 已收集的患者信息
        :param search_results: 知识库检索结果
        :param messages: 对话历史
        :param disclaimer: 免责声明文本
        :return: 综合分析报告
        """
        logger.info("DiagnosisAgent: msg_count=%d", len(messages))

        try:
            # 1. 从检索结果中提取知识片段（最多3条，每条取前300字符）
            knowledge = ""
            if search_results:
                fragments = [r.get("content", "")[:300] for r in search_results[:3] if isinstance(r, dict)]
                knowledge = "\n".join(fragments)

            # 2. 格式化对话历史（取最近10条）
            conversation = _format_history(messages, limit=10)
            
            # 3. 将结构化患者信息转换为文本
            patient_info_text = ""
            if collected_info:
                patient_info = collected_info.get("patient_info", collected_info)
                patient_info_text = "\n".join([f"- {k}: {v}" for k, v in patient_info.items() if v])

            # 4. 记录诊断输入信息（调试用）
            if patient_info_text:
                logger.debug("【患者信息】%s", patient_info_text)
            logger.debug("【问诊对话】%s", conversation)
            logger.debug("【知识库参考】%s", knowledge)
            
            # 5. 加载模板并渲染 prompt
            template = _load_prompt_template("diagnosis")
            prompt_str = template.render(
                patient_info_text=patient_info_text or "暂无结构化患者信息",
                conversation=conversation or "暂无对话历史",
                knowledge=knowledge or "暂无相关知识库参考",
            )
            system_prompt, user_content = _split_system_user(prompt_str)

            # 6. 调用LLM生成综合分析
            result = await self.adapter.generate(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=1024, temperature=0.3,
            )

            # 4. 检查内容是否安全
            content = result.get("content", "")
            if not content:
                raise RuntimeError("LLM returned empty content")
            _check_safe(content)

            # 5. 返回结果（免责声明由 prompt 模板统一生成）
            return content

        except (LLMAPIError, LLMRateLimitError, LLMTimeoutError):
            raise  # 直接向上抛出LLM相关错误
        except Exception as e:
            logger.error("DiagnosisAgent LLM failed: %s", e, exc_info=True)
            raise


def _format_history(messages: list, limit: int = 10) -> str:
    """格式化对话历史为可读文本"""
    lines: list[str] = []
    for msg in messages[-limit:]:  # 只取最近的limit条消息
        role = msg.get("role", "") if isinstance(msg, dict) else getattr(msg, "type", "")
        content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
        if role in ("user", "human"):
            lines.append(f"用户: {content}")
        elif role in ("assistant", "ai"):
            lines.append(f"助手: {content}")
    return "\n".join(lines)


def _check_safe(content: str) -> None:
    """安全检查：检测违规表述（不阻塞，仅记录警告）"""
    import re
    neg = r'(?<![不没未难无可应须能])'  # 否定词前向断言
    patterns = [neg + r'确诊[^断排检筛查]', neg + r'保证[能可会]', r'肯定没问题']
    for p in patterns:
        if re.search(p, content):
            logger.warning("Safety check triggered (not blocking): pattern=%s", p)