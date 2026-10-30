"""
RAG 检索增强生成 — 混合检索 + 去重 + 权威/时效评分
"""

from __future__ import annotations

import logging
import math
import os
import re
from collections import Counter
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
        self._st_model = None

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

    def _get_st(self):
        """本地 sentence-transformers 兜底（无 embedding API key 时用）。"""
        if self._st_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                # 优先环境变量，其次仓库内 models/ 目录（Docker 镜像与本地都适用）
                default_path = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)),
                    "models", "bge-small-zh-v1.5",
                )
                st_path = os.getenv("ST_MODEL_PATH") or default_path
                self._st_model = SentenceTransformer(st_path)
                self._cached_dim = self._st_model.get_sentence_embedding_dimension()
                logger.info("SentenceTransformer loaded: %s dim=%d", st_path, self._cached_dim)
            except Exception as e:
                logger.warning("SentenceTransformer load failed: %s", e)
        return self._st_model

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

        st = self._get_st()
        if st is not None:
            try:
                vecs = st.encode(texts, normalize_embeddings=True)
                return [v.tolist() for v in vecs]
            except Exception as e:
                logger.warning("SentenceTransformer failed: %s", e)

        logger.warning(
            "Embedding not available: neither EMBEDDING_API_KEY nor BGE_MODEL_PATH configured. "
            "RAG knowledge retrieval will be skipped. "
            "Set EMBEDDING_API_KEY in .env or BGE_MODEL_PATH to enable."
        )
        return []

    @property
    def dimensions(self) -> int:
        return self._cached_dim


# ── BM25 关键词检索 ───────────────────

_CJK_RE = re.compile(r"[一-鿿]")
_LATIN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    """中英混合分词：英文/数字按词，中文按 jieba（不可用时退化为二字切片）。"""
    text = (text or "").lower()
    tokens = _LATIN_RE.findall(text)
    try:
        import jieba
        tokens += [w for w in jieba.lcut(text) if _CJK_RE.search(w) and len(w) > 1]
    except ImportError:  # 没装 jieba 时用字符二元组兜底
        cjk = _CJK_RE.findall(text)
        tokens += ["".join(cjk[i:i + 2]) for i in range(len(cjk) - 1)]
    return tokens


class BM25Index:
    """BM25（Okapi）打分，用于知识库的关键词召回。

    知识库规模在千条量级，每次查询直接对全量文档算分即可（O(N×|q|)），
    不必引入独立全文索引；语料变化时按条目数重建。
    """

    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._tfs = [Counter(d) for d in docs]
        self._lens = [len(d) for d in docs]
        self._avgdl = (sum(self._lens) / len(self._lens)) if self._lens else 0.0
        df: Counter = Counter()
        for d in docs:
            df.update(set(d))
        n = len(docs)
        # 带平滑的 IDF：词在全部文档中都出现时仍保留正权重
        self._idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def scores(self, query_tokens: list[str]) -> list[float]:
        out: list[float] = []
        for tf, dl in zip(self._tfs, self._lens):
            s = 0.0
            for t in query_tokens:
                f = tf.get(t, 0)
                if not f or t not in self._idf:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * dl / (self._avgdl or 1.0))
                s += self._idf[t] * f * (self.k1 + 1) / denom
            out.append(s)
        return out


# ── RAG 检索器 ────────────────────────


class RAGRetriever:
    def __init__(self, store: VectorStore | None = None,
                 encoder: EmbeddingEncoder | None = None) -> None:
        self.store = store or get_vector_store()
        self.encoder = encoder or EmbeddingEncoder()
        # 关键词检索的语料与倒排索引缓存：条目数变化时重建
        self._corpus: list[dict] = []
        self._corpus_size = -1
        self._bm25: BM25Index | None = None

    async def retrieve(
        self, query: str, top_k: int = 10,
        min_authority: float = 0.0, min_freshness: float = 0.0,
        source_types: list[str] | None = None,
    ) -> list[SearchResult]:
        vector_results = await self._vector_search(query, top_k * 2)
        keyword_results = await self._keyword_search(query, top_k)
        merged = self._reciprocal_rank_fusion(vector_results, keyword_results, k=60)
        scored = self._apply_scoring(merged)
        scored.sort(key=lambda r: r.relevance_score, reverse=True)
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

    async def _load_corpus(self) -> list[dict]:
        """取出知识库全量条目；条目数变化时重建 BM25 索引。"""
        try:
            size = await self.store.count()
        except Exception as e:  # 存储不可用 → 关键词路静默跳过，向量路照常
            logger.warning("Keyword search skipped, store unavailable: %s", e)
            return []
        if size == self._corpus_size and self._bm25 is not None:
            return self._corpus
        self._corpus = await self.store.fetch_all()
        self._corpus_size = len(self._corpus)
        self._bm25 = BM25Index(
            [_tokenize(e.get("metadata", {}).get("content", "")) for e in self._corpus]
        )
        logger.debug("BM25 index built over %d entries", len(self._corpus))
        return self._corpus

    async def _keyword_search(self, query: str, top_k: int) -> list[dict]:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []
        corpus = await self._load_corpus()
        if not corpus or self._bm25 is None:
            return []
        scores = self._bm25.scores(query_tokens)
        best = max(scores, default=0.0)
        if best <= 0:
            return []
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        results = []
        for i in ranked[:top_k]:
            if scores[i] <= 0:
                break
            entry = dict(corpus[i])
            entry["score"] = scores[i] / best  # 归一到 (0, 1]，与向量分同量级
            results.append(entry)
        return results

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
        # 把融合分写回条目，后续评分与排序以它为基准（单路原始分已无意义）
        return [{**r, "score": score} for r, score in merged]

    @staticmethod
    def _apply_scoring(raw: list[dict]) -> list[SearchResult]:
        """RRF 融合分 × 权威度 × 时效性，归一化后作为 relevance_score。

        权威度与时效都只调权、不过滤：低权威材料仍可能被召回，
        只是排在后面，避免「知识库太小、过滤后无结果」。
        """
        if not raw:
            return []
        weighted = []
        for r in raw:
            meta = r.get("metadata", {})
            authority = float(meta.get("authority_score", 0.5))
            freshness = float(meta.get("freshness_score", 1.0))
            base = float(r.get("score", 0.0))
            weighted.append((r, meta, base * (0.5 + 0.5 * authority) * (0.5 + 0.5 * freshness)))
        top = max(w for _, _, w in weighted) or 1.0
        results = []
        for r, meta, w in weighted:
            results.append(SearchResult(
                content=meta.get("content", ""),
                source=meta.get("source", ""),
                source_type=meta.get("source_type", ""),
                authority_score=float(meta.get("authority_score", 0.5)),
                freshness_score=float(meta.get("freshness_score", 1.0)),
                relevance_score=w / top,
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
