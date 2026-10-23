import pytest
from workflow.routes import (
    route_by_intent,
    check_basic_interview_complete,
    check_expert_interview_complete,
    after_response,
)


# ── route_by_intent ──────────────────────────

@pytest.mark.asyncio
async def test_route_by_intent_diagnosis_goes_to_basic_interview():
    """医疗意图始终从基础问诊开始"""
    state = {"intent": "diagnosis", "red_flag_raised": False}
    assert await route_by_intent(state) == "basic_interview"


@pytest.mark.asyncio
async def test_route_by_intent_with_use_expert_still_starts_at_basic():
    """即使 use_expert=True，入口仍然是基础问诊"""
    state = {"intent": "diagnosis", "red_flag_raised": False, "use_expert": True}
    assert await route_by_intent(state) == "basic_interview"


@pytest.mark.asyncio
async def test_route_by_intent_greeting_goes_to_response():
    state = {"intent": "greeting", "red_flag_raised": False}
    assert await route_by_intent(state) == "response"


@pytest.mark.asyncio
async def test_route_by_intent_red_flag_always_to_response():
    state = {"intent": "diagnosis", "red_flag_raised": True}
    assert await route_by_intent(state) == "response"


@pytest.mark.asyncio
async def test_route_by_intent_question_goes_to_response():
    state = {"intent": "question", "red_flag_raised": False}
    assert await route_by_intent(state) == "response"


# ── check_basic_interview_complete ───────────

def test_basic_complete_diagnose_without_expert_goes_to_response():
    """基础完成且未启用专家 → 直接诊断"""
    state = {"current_stage": "diagnose", "red_flag_raised": False, "use_expert": False}
    assert check_basic_interview_complete(state) == "response"


def test_basic_complete_diagnose_with_expert_goes_to_expert():
    """基础完成且启用专家 → 进入专家问诊"""
    state = {"current_stage": "diagnose", "red_flag_raised": False, "use_expert": True}
    assert check_basic_interview_complete(state) == "expert_interview"


def test_basic_collect_continues_basic():
    """基础未完成 → 继续基础问诊"""
    state = {"current_stage": "collect", "red_flag_raised": False, "messages": []}
    assert check_basic_interview_complete(state) == "basic_interview"


def test_basic_collect_with_assistant_reply_goes_to_response():
    state = {"current_stage": "collect", "red_flag_raised": False,
             "messages": [{"role": "assistant", "content": "q"}]}
    assert check_basic_interview_complete(state) == "response"


def test_basic_red_flag_goes_to_response():
    state = {"current_stage": "collect", "red_flag_raised": True}
    assert check_basic_interview_complete(state) == "response"


def test_basic_emergency_goes_to_response():
    state = {"current_stage": "emergency", "red_flag_raised": False}
    assert check_basic_interview_complete(state) == "response"


# ── check_expert_interview_complete ──────────

def test_expert_complete_diagnose_goes_to_response():
    """专家完成 → 诊断报告"""
    state = {"current_stage": "diagnose", "red_flag_raised": False}
    assert check_expert_interview_complete(state) == "response"


def test_expert_collect_continues_expert():
    """专家未完成 → 继续专家问诊"""
    state = {"current_stage": "collect", "red_flag_raised": False, "messages": []}
    assert check_expert_interview_complete(state) == "expert_interview"


def test_expert_collect_with_assistant_reply_goes_to_response():
    state = {"current_stage": "collect", "red_flag_raised": False,
             "messages": [{"role": "assistant", "content": "q"}]}
    assert check_expert_interview_complete(state) == "response"


def test_expert_red_flag_goes_to_response():
    state = {"current_stage": "collect", "red_flag_raised": True}
    assert check_expert_interview_complete(state) == "response"


# ── after_response ───────────────────────────

def test_after_response_done_by_default():
    assert after_response({}) == "done"


def test_after_response_fallback_goes_to_human_review():
    assert after_response({"fallback_triggered": True}) == "human_review"


# ── 会话结束后的路由 ─────────────────────────

@pytest.mark.asyncio
async def test_route_by_intent_session_done_goes_to_response():
    """诊断完成后继续发消息，不再重新问诊/重新出诊断"""
    state = {"intent": "diagnosis", "red_flag_raised": False,
             "current_stage": "done", "session_status": "done", "round_count": 9}
    assert await route_by_intent(state) == "response"


@pytest.mark.asyncio
async def test_route_by_intent_terminated_session_goes_to_response():
    state = {"intent": "diagnosis", "red_flag_raised": False,
             "session_status": "emergency_terminated", "round_count": 3}
    assert await route_by_intent(state) == "response"
