import pytest
from safety.l0_filter import run_l0_filter


def test_suicide_with_exclusion_term_keywords_still_triggers_intercept():
    result = run_l0_filter("我刚看了个讲自杀的电影，现在我也想喝农药结束生命")
    assert result.is_emergency is True
    assert result.routing_stage == "L0_INTERCEPT"
    assert result.session_status == "emergency_terminated"


def test_emergency_signs_overrides_non_medical_mixed_input():
    result = run_l0_filter("我胸痛得厉害，顺便问下APP怎么退出")
    assert result.is_emergency is True
    assert result.routing_stage == "L0_INTERCEPT"
    assert result.rule_id == "EMERGENCY_SIGNS"


def test_pure_non_medical_with_pii_detection_and_desensitization():
    result = run_l0_filter("我叫张三，手机号13800138000，怎么给猫洗澡")
    assert result.is_emergency is False
    assert result.routing_stage == "L0_NON_MEDICAL"
    assert "PII_DETECTED" in result.matched_keywords
    assert result.response != ""
    assert "[姓名]" in result.response
    assert "[手机号]" in result.response
