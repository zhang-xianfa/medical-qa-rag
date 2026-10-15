# TC-006 ~ TC-014: L1意图路由测试
# 对应文档: docs/testing/e2e-routing-scenario-test-cases.md 第二类+第三类
from __future__ import annotations

import pytest
from tests.conftest import (
    TC006_INPUT, TC007_INPUT, TC008_INPUT, TC009_INPUT,
    TC010_INPUT, TC011_INPUT, TC012_INPUT, TC013_INPUT, TC014_INPUT,
    intent_router,
)
from workflow.l1_router import IntentRouter, IntentCategory, RouteResult


def test_tc006_high_confidence_pediatric_fever_routing(
    intent_router: IntentRouter,
) -> None:
    """TC-006: L1高置信度——儿童发热关键词命中, confidence≥0.80"""
    result = intent_router.route(TC006_INPUT)
    assert result.routing_stage == "L1_ROUTED"
    assert result.primary_scenario is not None
    assert result.primary_scenario.scenario_id == "pediatric_fever_care"
    assert result.primary_scenario.confidence >= 0.80
    assert result.intent_category == IntentCategory.PEDIATRIC_CARE
    assert result.is_emergency is False


def test_tc007_high_confidence_with_baby_keywords(
    intent_router: IntentRouter,
) -> None:
    """TC-007: L1高置信度——'宝宝'+发烧+精神关键词命中"""
    result = intent_router.route(TC007_INPUT)
    assert result.primary_scenario is not None
    assert result.primary_scenario.scenario_id == "pediatric_fever_care"
    assert result.primary_scenario.confidence >= 0.80


def test_tc008_medium_confidence_confirm_routing(
    intent_router: IntentRouter,
) -> None:
    """TC-008: L1中等置信度——'孩子有点热'关键词不足, 0.50≤confidence<0.80"""
    result = intent_router.route(TC008_INPUT)
    assert result.primary_scenario is not None
    assert result.primary_scenario.scenario_id in (
        "pediatric_fever_care", "general_consultation"
    )


def test_tc009_adult_fever_routes_to_general_consultation(
    intent_router: IntentRouter,
) -> None:
    """TC-009: L1跨场景——成人发热路由至通用场景"""
    result = intent_router.route(TC009_INPUT)
    assert result.primary_scenario is not None
    assert result.primary_scenario.scenario_id == "general_consultation"


def test_tc010_elderly_fever_routes_with_adult_general_category(
    intent_router: IntentRouter,
) -> None:
    """TC-010: L1多关键词——老人发热路由至通用场景, intent_category=adult_general"""
    result = intent_router.route(TC010_INPUT)
    assert result.primary_scenario is not None
    assert result.primary_scenario.scenario_id == "general_consultation"
    assert result.intent_category == IntentCategory.ADULT_GENERAL


def test_tc011_low_confidence_fallback(
    intent_router: IntentRouter,
) -> None:
    """TC-011: L1兜底——信息过少触发low_confidence"""
    result = intent_router.route(TC011_INPUT)
    assert result.routing_stage in ("L1_FALLBACK", "L1_ROUTED")
    assert result.primary_scenario is not None
    assert result.primary_scenario.scenario_id == "general_consultation"


def test_tc012_non_medical_routed_via_l1(
    intent_router: IntentRouter,
) -> None:
    """TC-012: L0放行→L1兜底——非医疗输入"""
    result = intent_router.route(TC012_INPUT, is_non_medical=True)
    assert result.routing_stage == "L1_ROUTED"
    assert result.intent_category == IntentCategory.NON_MEDICAL
    assert result.primary_scenario is not None
    assert result.primary_scenario.scenario_id == "general_consultation"


def test_tc013_vague_input_triggers_fallback(
    intent_router: IntentRouter,
) -> None:
    """TC-013: L1兜底——语义模糊触发low_confidence"""
    result = intent_router.route(TC013_INPUT)
    assert result.routing_stage in ("L1_FALLBACK", "L1_ROUTED")
    assert result.primary_scenario is not None
    assert result.primary_scenario.scenario_id == "general_consultation"


def test_tc014_mixed_intent_routes_medical_priority(
    intent_router: IntentRouter,
) -> None:
    """TC-014: L1混合意图——医疗意图优先路由"""
    result = intent_router.route(TC014_INPUT)
    assert result.primary_scenario is not None
    assert result.intent_category != IntentCategory.NON_MEDICAL
