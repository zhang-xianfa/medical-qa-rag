"""
向量数据库集成：PostgreSQL + pgvector（主） / InMemory（降级）
支持余弦相似度，配置从 .env 读取
"""

from __future__ import annotations

import logging
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ── 配置 ──────────────────────────────

@dataclass
class VectorStoreConfig:
    backend: str = "pgvector"
    vector_dim: int = 1024
    metric_type: str = "COSINE"


def load_vector_config() -> VectorStoreConfig:
    return VectorStoreConfig(
        backend=os.getenv("VECTOR_BACKEND", "memory"),
        vector_dim=int(os.getenv("VECTOR_DIM", "1024")),
        metric_type=os.getenv("VECTOR_METRIC", "COSINE"),
    )


# ── 抽象接口 ──────────────────────────

class VectorStore(ABC):
    config: VectorStoreConfig

    @abstractmethod
    async def create_collection(self) -> None: ...

    @abstractmethod
    async def insert(self, vectors: list[list[float]], metadata: list[dict]) -> list[str]: ...

    @abstractmethod
    async def search(self, query_vector: list[float], top_k: int = 10,
                     filters: dict | None = None) -> list[dict]: ...

    @abstractmethod
    async def update(self, id: str, vector: list[float], metadata: dict) -> bool: ...

    @abstractmethod
    async def delete(self, ids: list[str]) -> int: ...

    @abstractmethod
    async def count(self) -> int: ...



class InMemoryVectorStore(VectorStore):
    def __init__(self, config: VectorStoreConfig | None = None) -> None:
        self.config = config or load_vector_config()
        self._store: dict[str, tuple[list[float], dict]] = {}
        self._counter = 0

    async def create_collection(self) -> None: pass

    async def insert(self, vectors: list[list[float]], metadata: list[dict]) -> list[str]:
        ids = []
        for vec, meta in zip(vectors, metadata):
            self._counter += 1
            vid = meta.get("knowledge_entry_id", f"ke_{self._counter}")
            self._store[vid] = (vec, meta)
            ids.append(vid)
        return ids

    async def search(self, query_vector: list[float], top_k: int = 10,
                     filters: dict | None = None) -> list[dict]:
        metric = self.config.metric_type
        results = []
        for vid, (vec, meta) in self._store.items():
            score = _cosine_similarity(query_vector, vec) if metric == "COSINE" else _euclidean_score(query_vector, vec)
            results.append({"id": vid, "score": score, "metadata": meta})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    async def update(self, id: str, vector: list[float], metadata: dict) -> bool:
        self._store[id] = (vector, metadata)
        return True

    async def delete(self, ids: list[str]) -> int:
        removed = 0
        for vid in ids:
            if vid in self._store:
                del self._store[vid]
                removed += 1
        return removed

    async def count(self) -> int:
        return len(self._store)


# ── PostgreSQL + pgvector 实现 ──────────

class PGVectorStore(VectorStore):
    def __init__(self, config: VectorStoreConfig | None = None) -> None:
        self.config = config or load_vector_config()
        self._table = "knowledge_vectors"
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', self._table):
            raise ValueError(f"Invalid table name: {self._table}")
        self._engine = None

    async def _get_engine(self):
        if self._engine is None:
            from persistence.database import _get_engine
            self._engine = _get_engine()
            async with self._engine.begin() as conn:
                from sqlalchemy import text
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                await conn.execute(text(f"""
                    CREATE TABLE IF NOT EXISTS {self._table} (
                        id TEXT PRIMARY KEY,
                        embedding vector({self.config.vector_dim}),
                        content TEXT,
                        source TEXT,
                        source_type TEXT,
                        title TEXT,
                        authority_score FLOAT DEFAULT 0.5,
                        freshness_score FLOAT DEFAULT 1.0,
                        publish_year INT DEFAULT 2024
                    )
                """))
        return self._engine

    async def create_collection(self) -> None:
        await self._get_engine()

    async def insert(self, vectors: list[list[float]], metadata: list[dict]) -> list[str]:
        from sqlalchemy import text
        engine = await self._get_engine()
        ids = []
        async with engine.begin() as conn:
            for vec, meta in zip(vectors, metadata):
                vid = meta.get("knowledge_entry_id", f"ke_{len(ids)}")
                emb_str = f"[{','.join(str(x) for x in vec)}]"
                await conn.execute(text(
                    f"INSERT INTO {self._table} (id, embedding, content, source, source_type, "
                    f"title, authority_score, freshness_score, publish_year) "
                    f"VALUES (:id, CAST(:emb AS vector), :content, :source, :stype, :title, :auth, :fresh, :year) "
                    f"ON CONFLICT (id) DO UPDATE SET embedding=EXCLUDED.embedding, content=EXCLUDED.content"
                ), {"id": vid, "emb": emb_str,
                    "content": meta.get("content", ""),
                    "source": meta.get("source", ""), "stype": meta.get("source_type", ""),
                    "title": meta.get("title", ""), "auth": meta.get("authority_score", 0.5),
                    "fresh": meta.get("freshness_score", 1.0), "year": meta.get("publish_year", 2024)})
                ids.append(vid)
        return ids

    async def search(self, query_vector: list[float], top_k: int = 10,
                     filters: dict | None = None) -> list[dict]:
        from sqlalchemy import text
        vec_str = f"[{','.join(str(x) for x in query_vector)}]"
        engine = await self._get_engine()
        async with engine.connect() as conn:
            rows = await conn.execute(text(
                f"SELECT id, 1 - (embedding <=> CAST(:vec AS vector)) AS score, content, source, "
                f"source_type, title, authority_score, freshness_score, publish_year "
                f"FROM {self._table} ORDER BY embedding <=> CAST(:vec AS vector) LIMIT :k"
            ), {"vec": vec_str, "k": top_k})
            results = rows.fetchall()
        return [{"id": r[0], "score": r[1],
                 "metadata": {"content": r[2], "source": r[3], "source_type": r[4],
                              "title": r[5], "authority_score": r[6],
                              "freshness_score": r[7], "publish_year": r[8]}}
                for r in results]

    async def update(self, id: str, vector: list[float], metadata: dict) -> bool:
        from sqlalchemy import text
        engine = await self._get_engine()
        async with engine.begin() as conn:
            result = await conn.execute(text(
                f"UPDATE {self._table} SET embedding=:emb, content=:content, source=:src, "
                f"source_type=:st, title=:t, authority_score=:as, freshness_score=:fs WHERE id=:id"
            ), {"emb": vector, "content": metadata.get("content", ""), "src": metadata.get("source", ""),
                "st": metadata.get("source_type", ""), "t": metadata.get("title", ""),
                "as": metadata.get("authority_score", 0.5), "fs": metadata.get("freshness_score", 1.0), "id": id})
        return result.rowcount > 0

    async def delete(self, ids: list[str]) -> int:
        from sqlalchemy import text
        engine = await self._get_engine()
        async with engine.begin() as conn:
            result = await conn.execute(text(f"DELETE FROM {self._table} WHERE id = ANY(:ids)"), {"ids": ids})
        return result.rowcount

    async def count(self) -> int:
        from sqlalchemy import text
        engine = await self._get_engine()
        async with engine.connect() as conn:
            row = (await conn.execute(text(f"SELECT COUNT(*) FROM {self._table}"))).fetchone()
        return row[0] if row else 0


# ── 工厂 ──────────────────────────────

_cached_memory_store: InMemoryVectorStore | None = None


def _get_memory_store(config: VectorStoreConfig | None = None) -> InMemoryVectorStore:
    global _cached_memory_store
    if _cached_memory_store is None:
        _cached_memory_store = InMemoryVectorStore(config)
    return _cached_memory_store


def get_vector_store(backend: str = "") -> VectorStore:
    config = load_vector_config()
    backend = backend or config.backend
    if backend == "pgvector":
        try:
            return PGVectorStore(config)
        except Exception as e:
            logger.warning("pgvector unavailable (%s), falling back to memory", e)
    return _get_memory_store(config)


# ── 距离计算 ──────────────────────────

def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x ** 2 for x in a) ** 0.5
    nb = sum(x ** 2 for x in b) ** 0.5
    return max(0.0, dot / (na * nb + 1e-10))


def _euclidean_score(a: list[float], b: list[float]) -> float:
    dist = sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5
    return 1.0 / (1.0 + dist)
