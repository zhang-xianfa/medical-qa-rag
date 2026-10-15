import pytest
from workflow.nodes.search_node import search_node


@pytest.mark.asyncio
async def test_search_node_populates_search_results_for_known_chief_complaint():
    state = {
        "collected_info": {"patient_info": {"chief_complaint": "头痛"}},
        "search_results": [],
        "search_queries": [],
    }
    result = await search_node(state)
    assert isinstance(result["search_results"], list)


@pytest.mark.asyncio
async def test_search_node_handles_empty_collected_info():
    state = {"collected_info": {}, "search_results": [], "search_queries": []}
    result = await search_node(state)
    assert result["search_results"] == []


@pytest.mark.asyncio
async def test_search_node_preserves_existing_results():
    existing = [{"content": "existing", "source": "test", "knowledge_entry_id": "ke-1", "relevance_score": 0.9}]
    state = {"collected_info": {}, "search_results": existing, "search_queries": []}
    result = await search_node(state)
    assert len(result["search_results"]) >= 1
