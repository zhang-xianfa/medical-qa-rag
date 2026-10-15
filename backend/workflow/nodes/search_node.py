from knowledge.retriever import retrieve_for_symptoms


async def search_node(state: dict) -> dict:
    collected_info = state.get("collected_info", {})
    search_results = state.get("search_results", [])
    search_queries = state.get("search_queries", [])

    results = await retrieve_for_symptoms(collected_info)
    existing_ids = {r.get("knowledge_entry_id", "") for r in search_results if isinstance(r, dict)}
    for result in results:
        rid = result.knowledge_entry_id if hasattr(result, 'knowledge_entry_id') else result.get("knowledge_entry_id", "")
        if rid and rid not in existing_ids:
            existing_ids.add(rid)
            search_results.append({
                "content": result.content if hasattr(result, 'content') else result.get("content", ""),
                "source": result.source if hasattr(result, 'source') else result.get("source", ""),
                "knowledge_entry_id": rid,
                "relevance_score": result.relevance_score if hasattr(result, 'relevance_score') else result.get("relevance_score", 0.0),
            })

    return {
        "search_results": search_results,
        "search_queries": search_queries,
    }
