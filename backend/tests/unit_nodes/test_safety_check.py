import pytest
from workflow.nodes.safety_check_node import safety_check_node


@pytest.mark.asyncio
async def test_normal_message_passes_all_checks():
    state = {"messages": [{"role": "user", "content": "我头痛两天了"}]}
    result = await safety_check_node(state)
    assert result["red_flag_raised"] is False
    assert result["safety_checks_passed"] is True


@pytest.mark.asyncio
async def test_suicide_message_triggers_red_flag():
    state = {"messages": [{"role": "user", "content": "我想结束自己的生命"}]}
    result = await safety_check_node(state)
    assert result["red_flag_raised"] is True
    assert result["safety_checks_passed"] is False
    assert result["next_stage"] == "emergency"


@pytest.mark.asyncio
async def test_id_card_message_does_not_trigger_red_flag():
    state = {"messages": [{"role": "user", "content": "我叫张三，身份证号110101199003071234"}]}
    result = await safety_check_node(state)
    assert result["red_flag_raised"] is False


@pytest.mark.asyncio
async def test_dosage_query_is_detected():
    state = {"messages": [{"role": "user", "content": "阿司匹林每次吃几片"}]}
    result = await safety_check_node(state)
    assert result["blocked"] is True or result["output"] != ""


@pytest.mark.asyncio
async def test_red_flag_supersedes_blocked():
    state = {"messages": [{"role": "user", "content": "我想自杀"}]}
    result = await safety_check_node(state)
    assert result["red_flag_raised"] is True


@pytest.mark.asyncio
async def test_empty_messages_returns_safe_defaults():
    state = {"messages": []}
    result = await safety_check_node(state)
    assert result["safety_checks_passed"] is True
    assert result["red_flag_raised"] is False
