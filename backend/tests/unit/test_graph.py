import pytest
from workflow.graph import build_workflow


def test_graph_compiles_without_error():
    graph = build_workflow()
    assert graph is not None


@pytest.mark.asyncio
async def test_graph_invoke_greeting_completes():
    graph = build_workflow()
    state = {
        "messages": [{"role": "user", "content": "你好"}],
        "intent": "greeting",
        "red_flag_raised": False,
        "safety_checks_passed": True,
        "collected_info": {},
        "search_results": [],
        "search_queries": [],
        "diagnosis_result": None,
        "round_count": 0,
        "max_rounds": 5,
        "session_id": "test-session",
        "current_stage": "init",
        "route_decision": "response",
    }
    result = await graph.ainvoke(state)
    assert len(result["messages"]) >= 1


@pytest.mark.asyncio
async def test_graph_invoke_emergency_path():
    graph = build_workflow()
    state = {
        "messages": [{"role": "user", "content": "我想结束自己的生命"}],
        "intent": "diagnosis",
        "red_flag_raised": True,
        "safety_checks_passed": False,
        "collected_info": {},
        "search_results": [],
        "search_queries": [],
        "diagnosis_result": None,
        "round_count": 0,
        "max_rounds": 5,
        "session_id": "test-session",
        "current_stage": "init",
        "route_decision": "response",
    }
    result = await graph.ainvoke(state)
    assert result["red_flag_raised"] is True or result["current_stage"] == "done"


@pytest.mark.asyncio
async def test_graph_v2_interview_with_background_search():
    """v2.0: 问诊结点 Twin-Track + 后台搜索"""
    graph = build_workflow()
    state = {
        "messages": [{"role": "user", "content": "我膝盖疼"}],
        "intent": "diagnosis",
        "red_flag_raised": False,
        "safety_checks_passed": True,
        "collected_info": {},
        "search_results": [],
        "search_queries": [],
        "diagnosis_result": None,
        "round_count": 0,
        "max_rounds": 5,
        "session_id": "test-twin-track",
        "current_stage": "init",
        "route_decision": "",
    }
    result = await graph.ainvoke(state)
    assert result["current_stage"] in ("collect", "done")
