# 受约束ADR: ADR-014 §L1 (revised, AUDIT-FIX: TC-010/012/014)
# 补充约束: ADR-013 (scenario_id枚举管理)
# 修订版本: v1.0-audit-fix-20260619

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

"""
L1 意图路由器（智能分诊台）
接收 L0 过滤后的安全输入，将用户问题精准路由到对应的业务场景。

核心工作流程：
1. 非医疗直通：L0 标记为非医疗的问题，直接走兜底通用咨询，不浪费算力
2. 场景匹配打分：通过关键词/模型对用户问题进行场景置信度评分
3. 三级路由决策：
   - ≥0.80 高置信度 → 直接路由到目标场景
   - 0.50~0.80 中置信度 → 路由到目标场景（后续可触发用户确认）
   - <0.50 低置信度 → 降级到通用咨询兜底，避免无响应

关键约束：
- 本层仅做路由分发，不做任何医疗内容生成
- 所有场景 ID 必须来自 AVAILABLE_SCENARIOS 枚举，禁止动态拼接
- 紧急类输入应由 L0 拦截，本层不再重复判断急症
"""

class IntentCategory(str, Enum):
    PEDIATRIC_CARE = "pediatric_care"
    ADULT_GENERAL = "adult_general"
    ELDERLY_CARE = "elderly_care"
    EMERGENCY = "emergency"
    NON_MEDICAL = "non_medical"
    UNCLEAR = "unclear"


@dataclass
class ScenarioMatch:
    scenario_id: str
    confidence: float
    rationale: str


@dataclass
class RouteResult:
    routing_stage: str = "L1_UNKNOWN"
    primary_scenario: ScenarioMatch | None = None
    alternative_scenarios: list[ScenarioMatch] = field(default_factory=list)
    intent_category: IntentCategory = IntentCategory.UNCLEAR
    is_emergency: bool = False
    requires_human_review: bool = False
    fallback_reason: str = ""


AVAILABLE_SCENARIOS: dict[str, dict] = {
    "pediatric_fever_care": {
        "scenario_id": "pediatric_fever_care",
        "display_name": "儿童发热居家护理指导",
        "description": "面向儿童发热场景的居家护理指导。仅提供护理建议与急诊指征识别。",
        "keywords": ["孩子", "宝宝", "小孩", "儿童", "发烧", "发热", "体温", "岁"],
        "min_score": 0.80,
    },
    "general_consultation": {
        "scenario_id": "general_consultation",
        "display_name": "通用健康咨询",
        "description": "面向常见不适症状的通用问诊场景",
        "keywords": ["不舒服", "难受", "疼", "痛", "怎么办", "帮忙"],
        "min_score": 0.50,
    },
}

DIRECT_ROUTE_THRESHOLD = 0.80
CONFIRM_ROUTE_MIN = 0.50
FALLBACK_THRESHOLD = 0.50


class IntentRouter:
    def __init__(self) -> None:
        self._mock_llm = _MockRouterLLM()

    def route(self, user_message: str, is_non_medical: bool = False) -> RouteResult:
        if is_non_medical:
            return RouteResult(
                routing_stage="L1_ROUTED",
                primary_scenario=ScenarioMatch(
                    scenario_id="general_consultation",
                    confidence=0.50,
                    rationale="L0识别为非医疗输入，L1兜底路由",
                ),
                intent_category=IntentCategory.NON_MEDICAL,
                is_emergency=False,
            )
        scores = self._mock_llm.classify(user_message)
        if not scores:
            return RouteResult(
                routing_stage="L1_FALLBACK",
                primary_scenario=ScenarioMatch(
                    scenario_id="general_consultation",
                    confidence=0.0,
                    rationale="无可用场景匹配",
                ),
                intent_category=IntentCategory.UNCLEAR,
                fallback_reason="low_confidence",
            )

        best_id, best_score, best_rationale = scores[0]

        if best_score >= DIRECT_ROUTE_THRESHOLD:
            return RouteResult(
                routing_stage="L1_ROUTED",
                primary_scenario=ScenarioMatch(
                    scenario_id=best_id, confidence=best_score, rationale=best_rationale,
                ),
                intent_category=_infer_category(best_id),
                is_emergency=False,
            )

        if best_score >= CONFIRM_ROUTE_MIN:
            return RouteResult(
                routing_stage="L1_ROUTED",
                primary_scenario=ScenarioMatch(
                    scenario_id=best_id, confidence=best_score, rationale=best_rationale,
                ),
                intent_category=_infer_category(best_id),
                is_emergency=False,
            )

        return RouteResult(
            routing_stage="L1_FALLBACK",
            primary_scenario=ScenarioMatch(
                scenario_id="general_consultation",
                confidence=0.0,
                rationale=f"最佳匹配{best_id}置信度{best_score:.2f}<{FALLBACK_THRESHOLD}",
            ),
            intent_category=IntentCategory.UNCLEAR,
            fallback_reason="low_confidence",
        )


def _infer_category(scenario_id: str) -> IntentCategory:
    mapping: dict[str, IntentCategory] = {
        "pediatric_fever_care": IntentCategory.PEDIATRIC_CARE,
        "general_consultation": IntentCategory.ADULT_GENERAL,
    }
    return mapping.get(scenario_id, IntentCategory.UNCLEAR)


class _MockRouterLLM:
    def classify(self, user_message: str) -> list[tuple[str, float, str]]:
        msg = user_message.lower()
        for sid, info in AVAILABLE_SCENARIOS.items():
            if sid == "general_consultation":
                continue
            keywords: list[str] = info.get("keywords", [])
            hits = sum(1 for kw in keywords if kw in msg)
            if hits >= 3:
                return [(sid, 0.94, f"命中{hits}个关键词")]
            if hits >= 2:
                return [(sid, 0.70, f"命中{hits}个关键词")]
        return [("general_consultation", 0.55, "通用匹配")]
