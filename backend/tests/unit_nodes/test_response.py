import pytest
from workflow.nodes.response_node import response_node


@pytest.mark.asyncio
async def test_greeting_intent_returns_welcome():
    state = {"messages": [], "intent": "greeting"}
    result = await response_node(state)
    assert len(result["messages"]) == 1
    assert result["current_stage"] == "done"


@pytest.mark.asyncio
async def test_emergency_generates_guidance():
    state = {
        "messages": [{"role": "user", "content": "胸痛"}],
        "intent": "emergency",
        "red_flag_raised": True,
        "next_stage": "emergency",
        "output": "请立即就医",
        "collected_info": {},
        "search_results": [],
    }
    result = await response_node(state)
    assert result["current_stage"] == "done"
    assert "120" in result["messages"][-1]["content"] or "就医" in result["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_disclaimer_present_in_diagnostic_response():
    state = {
        "messages": [{"role": "user", "content": "我头痛"}],
        "intent": "diagnosis",
        "current_stage": "diagnose",
        "collected_info": {"patient_info": {"chief_complaint": "头痛"}},
        "search_results": [],
        "red_flag_raised": False,
    }
    result = await response_node(state)
    output = result["messages"][-1]["content"]
    assert "不能替代专业医疗诊断" in output


@pytest.mark.asyncio
async def test_blocked_output_uses_compliance_phrase():
    state = {
        "messages": [],
        "intent": "diagnosis",
        "blocked": True,
        "output": "请咨询医生",
        "collected_info": {},
        "search_results": [],
        "red_flag_raised": False,
    }
    result = await response_node(state)
    output = result["messages"][-1]["content"]
    assert "请咨询医生" in output
