import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from knowledge.vector_store import get_vector_store
from knowledge.retriever import EmbeddingEncoder


async def main():
    store = get_vector_store()
    count = await store.count()
    print(f"知识库条目总数: {count}")

    if count == 0:
        print("知识库为空")
        return

    print("\n=== 全文搜索 ===")
    query = sys.argv[1] if len(sys.argv) > 1 else "病历"
    print(f"查询: {query}")

    encoder = EmbeddingEncoder()
    vectors = await encoder.encode([query])
    results = await store.search(vectors[0], top_k=5)

    print(f"搜索结果: {len(results)} 条")
    for i, r in enumerate(results):
        meta = r.get("metadata", {})
        print(f"\n--- 结果 {i+1} (相似度: {r['score']:.4f}) ---")
        print(f"标题: {meta.get('title', 'N/A')}")
        print(f"来源: {meta.get('source', 'N/A')}")
        print(f"类型: {meta.get('source_type', 'N/A')}, 年份: {meta.get('publish_year', 'N/A')}")
        print(f"权威分: {meta.get('authority_score', 'N/A')}, 时效分: {meta.get('freshness_score', 'N/A')}")
        content = meta.get("content", "")
        print(f"内容预览: {content[:200]}...")


if __name__ == "__main__":
    asyncio.run(main())
