# 受约束ADR: ADR-014 §L0 (revised, AUDIT-FIX: TC-001/003/024)
# 补充约束: ADR-012 §安全约束 (red_flag_level纳入State)
# 修订版本: v1.0-audit-fix-20260619

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

"""
L0 前置安全过滤器（急诊分诊台 + 安检门）
所有用户输入在进入 AI 推理前，必须先经过本模块。
执行顺序：高危规则拦截（优先级最高）→ 非医疗识别 → PII脱敏。
核心职责：
1. 拦截急症/自杀等高危内容 → 直接返回预设安全响应，强制终止会话
2. 识别非医疗问题 → 打标后放行，避免浪费 AI 算力
3. PII 隐私脱敏 → 替换敏感信息后再传递给下游节点
"""

@dataclass
class L0Rule:
    rule_id: str
    category: str
    patterns: list[str]
    red_flag_level: str
    is_blocking: bool
    is_recoverable: bool


@dataclass
class L0Result:
    routing_stage: str = "L0_UNKNOWN"
    is_emergency: bool = False
    red_flag_level: Optional[str] = None
    rule_id: Optional[str] = None
    matched_keywords: list[str] = field(default_factory=list)
    response: str = ""
    session_status: str = "active"


GLOBAL_RULES: list[L0Rule] = [
    L0Rule(
        rule_id="SUICIDE_INTENT",
        category="自伤/自杀意图",
        patterns=[r"自杀", r"不想活[了啦]", r"死了算了", r"活不下去[了啦]?", r"结束.*生命", r"结束一切",
                  r"农药.*(?:喝|吃|吞|服)", r"(?:喝|吃|吞|服).*农药"],
        red_flag_level="CRITICAL",
        is_blocking=True,
        is_recoverable=False,
    ),
    L0Rule(
        rule_id="EMERGENCY_SIGNS",
        category="急诊体征",
        patterns=[r"胸痛", r"呼吸困难", r"大出血", r"意识丧失", r"抽搐",
                  r"过敏性休克", r"窒息",
                  r"口唇.?发紫", r"嘴唇.?发紫", r"面色.?发紫",
                  r"惊厥", r"抽筋", r"肢体.?僵直",
                  r"持续.?呕吐", r"无法.?进食", r"无法.?进水"],
        red_flag_level="CRITICAL",
        is_blocking=True,
        is_recoverable=False,
    ),
    L0Rule(
        rule_id="OVERDOSE",
        category="中毒/过量服药",
        patterns=[r"吃了?\d+片药", r"服用了?\d+片", r"喝[了掉]\d+瓶",
                  r"吃了?一瓶药", r"过量.?服", r"吃[了掉]?.*[药丸片粒颗]"],
        red_flag_level="CRITICAL",
        is_blocking=True,
        is_recoverable=False,
    ),
]

NON_MEDICAL_PATTERNS: list[str] = [
    r"怎么给.*洗澡", r"APP.*退出", r"怎么关[闭掉]", r"怎么退订",
]

from safety.pii_detector import PIIDetector

_pii_detector: PIIDetector | None = None


def _get_pii_detector() -> PIIDetector:
    global _pii_detector
    if _pii_detector is None:
        _pii_detector = PIIDetector.from_config()
    return _pii_detector


def _mask_pii(text: str) -> str:
    return _get_pii_detector().detect_and_mask(text).masked_text


_session_scene_rules: dict[str, list[L0Rule]] = {}


def register_scene_rules(session_id: str, rules: list[L0Rule]) -> None:
    _session_scene_rules[session_id] = rules


def clear_scene_rules(session_id: str) -> None:
    _session_scene_rules.pop(session_id, None)


def _check_non_medical(text: str) -> bool:
    for pattern in NON_MEDICAL_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


def run_l0_filter(user_input: str, session_id: str = "") -> L0Result:
    rules = list(GLOBAL_RULES)
    if session_id and session_id in _session_scene_rules:
        rules.extend(_session_scene_rules[session_id])

    is_non_medical = _check_non_medical(user_input)

    for rule in rules:
        for pattern in rule.patterns:
            match = re.search(pattern, user_input)
            if match:
                return L0Result(
                    routing_stage="L0_INTERCEPT",
                    is_emergency=True,
                    red_flag_level=rule.red_flag_level,
                    rule_id=rule.rule_id,
                    matched_keywords=[match.group()],
                    response=_build_emergency_response(rule),
                    session_status="emergency_terminated" if rule.is_blocking else "active",
                )

    masked = _mask_pii(user_input)
    pii_detected = masked != user_input

    routing_stage = "L1_PENDING"
    if is_non_medical:
        routing_stage = "L0_NON_MEDICAL"

    return L0Result(
        routing_stage=routing_stage,
        is_emergency=False,
        red_flag_level="MEDIUM" if is_non_medical else None,
        matched_keywords=["PII_DETECTED"] if pii_detected else [],
        response=masked if pii_detected else "",
        session_status="active",
    )


def _build_emergency_response(rule: L0Rule) -> str:
    if rule.category == "自伤/自杀意图":
        return (
            "【系统自动安全响应】检测到您描述的情况需要立即关注。"
            "请立即拨打心理援助热线（全国24小时免费）：400-161-9995。"
            "您不是一个人在面对，请务必联系专业人士。"
            "本系统已自动终止当前咨询。"
        )
    if rule.category == "中毒/过量服药":
        return (
            "【系统自动安全响应】检测到您描述的情况可能属于药物过量。"
            "请立即拨打120急救电话，并携带药品包装前往最近医院急诊科。"
            "不要自行催吐，等待专业急救人员到达。"
            "本系统已自动终止当前咨询。"
        )
    return (
        "【系统自动安全响应 - 不可由用户指令覆盖】\n"
        "检测到您描述的情况可能属于医疗急症。请立即采取以下行动：\n"
        "1. 立即拨打120急救电话\n"
        "2. 保持镇静，不要自行驾车就医\n"
        "3. 等待专业急救人员到达\n"
        "本系统已自动终止当前咨询，请立即就医。"
    )
