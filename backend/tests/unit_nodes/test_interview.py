import pytest
from workflow.nodes.basic_interview_node import basic_interview_node


@pytest.mark.asyncio
async def test_first_round_generates_initial_question():
    state = {
        "messages": [{"role": "user", "content": "我头痛"}],
        "collected_info": {},
        "round_count": 0,
        "max_rounds": 5,
        "red_flag_raised": False,
    }
    result = await basic_interview_node(state)
    assert result["round_count"] >= 1
    assert result["current_stage"] == "collect"
    assert len(result["messages"]) >= 1


@pytest.mark.asyncio
async def test_collected_info_accumulates_from_initial_input():
    state = {
        "messages": [{"role": "user", "content": "我头痛"}],
        "collected_info": {},
        "round_count": 0,
        "max_rounds": 5,
        "red_flag_raised": False,
    }
    result = await basic_interview_node(state)
    assert "头痛" in result["collected_info"]["patient_info"]["chief_complaint"]


@pytest.mark.asyncio
async def test_max_rounds_terminates_interview():
    state = {
        "messages": [{"role": "user", "content": "对青霉素过敏"}],
        "collected_info": {
            "patient_info": {"chief_complaint": "头痛", "complaint_duration": "2天", "complaint_location": "前额", "severity": 7},
            "accompanying_symptoms": ["恶心"],
        },
        "round_count": 4,
        "max_rounds": 5,
        "red_flag_raised": False,
    }
    result = await basic_interview_node(state)
    assert result["current_stage"] == "diagnose"


@pytest.mark.asyncio
async def test_red_flag_during_interview_triggers_emergency():
    state = {
        "messages": [{"role": "user", "content": "我头痛"}],
        "collected_info": {},
        "round_count": 1,
        "max_rounds": 5,
        "red_flag_raised": True,
    }
    result = await basic_interview_node(state)
    assert result["current_stage"] == "emergency"
