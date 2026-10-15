import pytest
import pytest_asyncio
from knowledge.vector_store import (
    InMemoryVectorStore, VectorStoreConfig,
    _cosine_similarity, _euclidean_score,
)


@pytest.fixture
def store():
    return InMemoryVectorStore()


@pytest_asyncio.fixture
async def populated_store(store):
    await store.insert(
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        [
            {"content": "c1", "knowledge_entry_id": "ke-1"},
            {"content": "c2", "knowledge_entry_id": "ke-2"},
            {"content": "c3", "knowledge_entry_id": "ke-3"},
        ],
    )
    return store


@pytest.mark.asyncio
async def test_create_collection_no_error(store):
    await store.create_collection()


@pytest.mark.asyncio
async def test_insert_and_count(store):
    ids = await store.insert([[1.0, 0.0], [0.0, 1.0]], [{"title": "a"}, {"title": "b"}])
    assert len(ids) == 2
    assert await store.count() == 2


@pytest.mark.asyncio
async def test_search_returns_top_k(populated_store):
    results = await populated_store.search([1.0, 0.1, 0.0], top_k=2)
    assert len(results) == 2
    assert results[0]["score"] >= results[1]["score"]


@pytest.mark.asyncio
async def test_delete_removes_vectors(store):
    ids = await store.insert([[1.0, 2.0]], [{"title": "x"}])
    removed = await store.delete(ids)
    assert removed == 1
    assert await store.count() == 0


@pytest.mark.asyncio
async def test_update_replaces_vector(store):
    ids = await store.insert([[1.0, 0.0]], [{"title": "old"}])
    updated = await store.update(ids[0], [0.0, 1.0], {"title": "new"})
    assert updated is True
    results = await store.search([0.0, 1.0], top_k=1)
    assert results[0]["metadata"]["title"] == "new"


@pytest.mark.asyncio
async def test_search_empty_store(store):
    results = await store.search([1.0, 0.0])
    assert results == []


@pytest.mark.asyncio
async def test_cosine_similarity_identical():
    assert _cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0, rel=1e-4)


@pytest.mark.asyncio
async def test_cosine_similarity_orthogonal():
    assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


@pytest.mark.asyncio
async def test_euclidean_score():
    score = _euclidean_score([0.0, 0.0], [0.0, 0.0])
    assert score == 1.0


def test_vector_store_config_defaults():
    cfg = VectorStoreConfig()
    assert cfg.backend == "pgvector"
    assert cfg.vector_dim == 1024
    assert cfg.metric_type == "COSINE"


@pytest.mark.asyncio
async def test_inmemory_update_non_existent(store):
    ok = await store.update("nonexistent", [1.0], {"title": "x"})
    assert ok is True
