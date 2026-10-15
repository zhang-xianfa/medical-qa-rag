import pytest
from knowledge import SearchResult
from knowledge.vector_store import InMemoryVectorStore
from knowledge.retriever import RAGRetriever, EmbeddingEncoder


class MockEmbeddingEncoder(EmbeddingEncoder):
    async def encode(self, texts: list[str]) -> list[list[float]]:
        return [[0.1 * (i + 1)] * self.dimensions for i in range(len(texts))]


@pytest.fixture
def retriever():
    store = InMemoryVectorStore()
    encoder = MockEmbeddingEncoder()
    return RAGRetriever(store=store, encoder=encoder)


@pytest.mark.asyncio
async def test_retrieve_returns_empty_for_empty_store(retriever):
    results = await retriever.retrieve("头痛")
    assert results == []


@pytest.mark.asyncio
async def test_retrieve_for_symptoms_generates_results(retriever):
    await retriever.store.insert(
        [[1.0] * 1536, [0.5] * 1536],
        [
            {"content": "紧张性头痛指南内容", "source": "中华医学会", "source_type": "guideline",
             "authority_score": 0.9, "freshness_score": 0.85, "knowledge_entry_id": "ke-1",
             "title": "紧张性头痛诊疗指南", "publish_year": 2023},
            {"content": "偏头痛内容", "source": "神经病学分会", "source_type": "consensus",
             "authority_score": 0.75, "freshness_score": 0.7, "knowledge_entry_id": "ke-2",
             "title": "偏头痛共识", "publish_year": 2021},
        ],
    )
    collected_info = {
        "patient_info": {"chief_complaint": "头痛"},
        "accompanying_symptoms": ["恶心", "低烧"],
    }
    results = await retriever.retrieve_for_symptoms(collected_info, top_k=5)
    assert len(results) > 0
    assert isinstance(results[0], SearchResult)


@pytest.mark.asyncio
async def test_retrieve_for_symptoms_empty_info_returns_empty(retriever):
    results = await retriever.retrieve_for_symptoms({})
    assert results == []


@pytest.mark.asyncio
async def test_retrieve_filters_by_authority(retriever):
    await retriever.store.insert(
        [[1.0] * 1536, [0.9] * 1536],
        [
            {"content": "low_quality", "source": "unknown", "source_type": "case_report",
             "authority_score": 0.2, "freshness_score": 0.9, "knowledge_entry_id": "ke-low"},
            {"content": "high_quality", "source": "权威机构", "source_type": "guideline",
             "authority_score": 0.9, "freshness_score": 0.9, "knowledge_entry_id": "ke-high"},
        ],
    )
    results = await retriever.retrieve("测试查询", top_k=5, min_authority=0.5)
    assert all(r.authority_score >= 0.5 for r in results)


@pytest.mark.asyncio
async def test_deduplicate_removes_duplicates():
    r1 = SearchResult(content="same", source="s1", source_type="guideline",
                      authority_score=0.9, freshness_score=0.8, relevance_score=0.5,
                      knowledge_entry_id="ke-dup")
    r2 = SearchResult(content="same", source="s2", source_type="guideline",
                      authority_score=0.9, freshness_score=0.8, relevance_score=0.4,
                      knowledge_entry_id="ke-dup")
    result = RAGRetriever._deduplicate([r1, r2])
    assert len(result) == 1
