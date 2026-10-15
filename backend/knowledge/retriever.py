"""
RAG 检索增强生成 — 混合检索 + 去重 + 权威/时效评分
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from knowledge import SearchResult
from knowledge.vector_store import get_vector_store, VectorStore

logger = logging.getLogger(__name__)

# ── 嵌入模型适配器 ────────────────────


@dataclass
class EmbeddingConfig:
    provider: str = "openai"
    model: str = "text-embedding-3-small"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    dimensions: int = 1024


def load_embedding_config() -> EmbeddingConfig:
    return EmbeddingConfig(
        provider=os.getenv("EMBEDDING_PROVIDER", "aliyun"),
        model=os.getenv("EMBEDDING_MODEL", "text-embedding-v4"),
        base_url=os.getenv("EMBEDDING_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        api_key=os.getenv("EMBEDDING_API_KEY", os.getenv("OPENAI_API_KEY", "")),
        dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "1024")),
    )


class EmbeddingEncoder:
    def __init__(self, config: EmbeddingConfig | None = None) -> None:
        self.config = config or load_embedding_config()
        self._cached_dim = self.config.dimensions
        self._bge_model = None

    def _get_bge(self):
        if self._bge_model is None:
            try:
                from FlagEmbedding import BGEM3FlagModel
                bge_path = os.getenv("BGE_MODEL_PATH", "BAAI/bge-m3")
                self._bge_model = BGEM3FlagModel(bge_path, use_fp16=False)
                self._cached_dim = self._bge_model.model.model.config.hidden_size
                logger.info("BGE-M3 loaded, dim=%d", self._cached_dim)
            except ImportError:
                logger.warning("FlagEmbedding not installed, run: pip install FlagEmbedding")
            except Exception as e:
                logger.warning("BGE-M3 load failed: %s", e)
        return self._bge_model

    async def encode(self, texts: list[str]) -> list[list[float]]:
        if self.config.api_key:
            try:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=self.config.api_key, base_url=self.config.base_url)
                resp = await client.embeddings.create(model=self.config.model, input=texts)
                return [d.embedding for d in resp.data]
            except Exception as e:
                logger.warning("Embedding API failed, trying BGE-M3: %s", e)

        bge = self._get_bge()
        if bge is not None:
            try:
                result = bge.encode(texts, batch_size=8, max_length=512)
                return [vec.tolist() for vec in result['dense_vecs']]
            except Exception as e:
                logger.warning("BGE-M3 failed: %s", e)

        logger.warning(
            "Embedding not available: neither EMBEDDING_API_KEY nor BGE_MODEL_PATH configured. "
            "RAG knowledge retrieval will be skipped. "
            "Set EMBEDDING_API_KEY in .env or BGE_MODEL_PATH to enable."
        )
        return []

    @property
    def dimensions(self) -> int:
        return self._cached_dim


# ── RAG 检索器 ────────────────────────


class RAGRetriever:
    def __init__(self, store: VectorStore | None = None,
                 encoder: EmbeddingEncoder | None = None) -> None:
        self.store = store or get_vector_store()
        self.encoder = encoder or EmbeddingEncoder()

    async def retrieve(
        self, query: str, top_k: int = 10,
        min_authority: float = 0.0, min_freshness: float = 0.0,
        source_types: list[str] | None = None,
    ) -> list[SearchResult]:
        vector_results = await self._vector_search(query, top_k * 2)
        keyword_results = await self._keyword_search(query, top_k)
        merged = self._reciprocal_rank_fusion(vector_results, keyword_results, k=60)
        scored = self._apply_scoring(merged)
        filtered = [
            r for r in scored
            if r.authority_score >= min_authority
            and r.freshness_score >= min_freshness
            and (not source_types or r.source_type in source_types)
        ]
        deduped = self._deduplicate(filtered)
        return deduped[:top_k]

    async def retrieve_for_symptoms(
        self, collected_info: dict, top_k: int = 10,
    ) -> list[SearchResult]:
        queries = self._build_symptom_queries(collected_info)
        if not queries:
            return []
        all_results: list[SearchResult] = []
        for q in queries:
            results = await self.retrieve(q, top_k=top_k)
            all_results.extend(results)
        return self._deduplicate(all_results)[:top_k]

    async def _vector_search(self, query: str, top_k: int) -> list[dict]:
        vectors = await self.encoder.encode([query])
        if not vectors:
            return []
        return await self.store.search(vectors[0], top_k=top_k)

    async def _keyword_search(self, query: str, top_k: int) -> list[dict]:
        results = await self.store.search([0.5] * self.encoder.dimensions, top_k=top_k)
        keywords = set(query.lower().split())
        scored = []
        for r in results:
            meta = r.get("metadata", {})
            content = meta.get("content", "").lower()
            hits = sum(1 for kw in keywords if kw in content)
            if hits > 0:
                r["score"] = min(1.0, hits / max(len(keywords), 1))
                scored.append(r)
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    @staticmethod
    def _reciprocal_rank_fusion(vector_results: list[dict],
                                keyword_results: list[dict], k: int = 60) -> list[dict]:
        fused: dict[str, tuple[dict, float]] = {}
        for rank, r in enumerate(vector_results):
            vid = r.get("id", str(rank))
            fused[vid] = (r, 1.0 / (k + rank + 1))
        for rank, r in enumerate(keyword_results):
            vid = r.get("id", str(rank))
            if vid in fused:
                _, prev = fused[vid]
                fused[vid] = (r, prev + 1.0 / (k + rank + 1))
            else:
                fused[vid] = (r, 1.0 / (k + rank + 1))
        merged = list(fused.values())
        merged.sort(key=lambda x: x[1], reverse=True)
        return [r for r, score in merged]

    @staticmethod
    def _apply_scoring(raw: list[dict]) -> list[SearchResult]:
        results = []
        for r in raw:
            meta = r.get("metadata", {})
            results.append(SearchResult(
                content=meta.get("content", ""),
                source=meta.get("source", ""),
                source_type=meta.get("source_type", ""),
                authority_score=meta.get("authority_score", 0.5),
                freshness_score=meta.get("freshness_score", 1.0),
                relevance_score=r.get("score", 0.0),
                knowledge_entry_id=r.get("id", ""),
                title=meta.get("title", ""),
                publish_year=meta.get("publish_year", 0),
                url=meta.get("url", ""),
            ))
        return results

    @staticmethod
    def _deduplicate(results: list[SearchResult]) -> list[SearchResult]:
        seen: set[str] = set()
        deduped: list[SearchResult] = []
        for r in results:
            key = r.knowledge_entry_id or r.content[:100]
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        return deduped

    @staticmethod
    def _build_symptom_queries(collected_info: dict) -> list[str]:
        queries: list[str] = []
        patient_info = collected_info.get("patient_info", {})
        chief = patient_info.get("chief_complaint", "")
        if chief:
            queries.append(f"{chief} 鉴别诊断 临床指南")
        accompanying = collected_info.get("accompanying_symptoms", [])
        if accompanying:
            queries.append(f"{chief} {' '.join(accompanying)} 可能诊断")
        return queries


# ── 便捷函数 ──────────────────────────

_retriever: RAGRetriever | None = None


def _get_retriever() -> RAGRetriever:
    global _retriever
    if _retriever is None:
        _retriever = RAGRetriever()
    return _retriever


async def retrieve(query: str, top_k: int = 10,
                   min_authority: float = 0.0) -> list[SearchResult]:
    return await _get_retriever().retrieve(query, top_k, min_authority=min_authority)


async def retrieve_for_symptoms(collected_info: dict,
                                top_k: int = 10) -> list[SearchResult]:
    return await _get_retriever().retrieve_for_symptoms(collected_info, top_k)
