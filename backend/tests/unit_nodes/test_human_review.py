import pytest
from workflow.nodes.human_review_node import human_review_node


@pytest.mark.asyncio
async def test_fallback_response_contains_safe_guidance():
    state = {"messages": []}
    result = await human_review_node(state)
    assert len(result["messages"]) == 1
    assert "就医" in result["messages"][0]["content"]


@pytest.mark.asyncio
async def test_fallback_triggered_flag_is_set():
    state = {"messages": []}
    result = await human_review_node(state)
    assert result["fallback_triggered"] is True


@pytest.mark.asyncio
async def test_current_stage_transitions_to_done():
    state = {"messages": []}
    result = await human_review_node(state)
    assert result["current_stage"] == "done"


@pytest.mark.asyncio
async def test_diagnosis_result_contains_disclaimer():
    state = {"messages": []}
    result = await human_review_node(state)
    dr = result.get("diagnosis_result", {})
    assert "不能替代专业医疗诊断" in dr.get("disclaimer", "")
