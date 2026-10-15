# 修复高优先级 + 中优先级代码问题 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复代码审查发现的 4 个高优先级 + 6 个中优先级问题

**Architecture:** 每个 Task 独立修复一个问题，按依赖顺序执行（先修 bug，再清理代码）

**Tech Stack:** Python 3.11+, LangGraph, SQLAlchemy, FastAPI

---

### Task 1: 修复 `real_llm_adapter.py:176` 日志格式化崩溃

**Files:**
- Modify: `backend/llm/real_llm_adapter.py:176`

- [ ] **Step 1: 修复格式化字符串**

```python
# Before
logger.error("LLM all %d retries exhausted, returning fallback")

# After — 补上 self.MAX_RETRIES 参数
logger.error("LLM all %d retries exhausted, returning fallback", self.MAX_RETRIES)
```

- [ ] **Step 2: 验证**

```bash
cd backend && python -m pytest tests/unit/test_llm_adapter.py -v
```

---

### Task 2: 修复 `check_basic_interview_complete` 缺少 emergency 检查

**Files:**
- Modify: `backend/workflow/routes.py:110`

- [ ] **Step 1: 补充 emergency 分支**

```python
# Before
if current_stage == "diagnose":

# After — 与 expert 路由保持一致
if current_stage == "diagnose" or current_stage == "emergency":
```

- [ ] **Step 2: 验证**

```bash
cd backend && python -m pytest tests/unit/test_routes.py -v
```

---

### Task 3: 修复专家节点 search_results 未写入 state

**Files:**
- Modify: `backend/workflow/nodes/expert_interview_node.py:121-127` 和 `129-137`

- [ ] **Step 1: 将本地 search_results 序列化为字典列表再写入 state**

现有 bug：`retrieve_for_symptoms()` 返回的是 `SearchResult` dataclass 对象，不能直接放 JSON。同时两处 return 都用 `state.get("search_results", [])` 丢弃了新检索的结果。

修复方案：将 `SearchResult` 对象转为 dict，与原有 `state.get("search_results", [])` 合并后写入返回的 state。

```python
# 在终止判断之前（line 117 之前）新增：格式化检索结果
# 将 SearchResult dataclass 转为可序列化的 dict
if search_results:
    new_results = []
    for r in search_results:
        if hasattr(r, "content"):
            new_results.append({
                "content": r.content, "source": r.source,
                "knowledge_entry_id": r.knowledge_entry_id,
                "relevance_score": r.relevance_score,
            })
        else:
            new_results.append(r)
else:
    new_results = []

# 合并新旧结果，去重
old_results = state.get("search_results", [])
old_ids = {r.get("knowledge_entry_id", "") for r in old_results if isinstance(r, dict)}
for r in new_results:
    rid = r.get("knowledge_entry_id", "")
    if rid and rid not in old_ids:
        old_ids.add(rid)
        old_results.append(r)
merged_results = old_results
```

然后在两处 return 中把 `state.get("search_results", [])` 替换为 `merged_results`。

- [ ] **Step 2: 验证**

```bash
cd backend && python -m pytest tests/unit/test_graph.py -v
```

---

### Task 4: 统一 Embedding 维度默认值

**Files:**
- Modify: `backend/knowledge/retriever.py:35`

- [ ] **Step 1: 将 retriever 默认维度与 vector_store 对齐**

```python
# Before
dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "1536")),

# After — 与 vector_store.py:22 和 .env 一致（BGE-M3 输出 1024 维）
dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "1024")),
```

- [ ] **Step 2: 验证**

```bash
cd backend && python -m pytest tests/unit/test_retriever.py tests/unit/test_vector_store.py -v
```

---

### Task 5: 清理 CLAUDE.md 和树结构中不存在的文件引用

**Files:**
- Modify: `CLAUDE.md`
- Modify: `backend/config/settings.py:23`
- Modify: `backend/api/main.py:54-57`

- [ ] **Step 1: CLAUDE.md — 删除不存在的 `red_flag_detector.py` 行**

删除或注释该行（实际实现在 `safety/l0_filter.py`）。

- [ ] **Step 2: settings.py — 删除 MILVUS_URI 字段**

```python
# 删除这一行
MILVUS_URI: str = "./data/milvus_lite.db"
```

- [ ] **Step 3: main.py — 修复 health check 中的 milvus 引用**

```python
# Before
"components": {
    "database": "up",
    "milvus": "not_configured",
    "llm": "up",
},

# After
"components": {
    "database": "up",
    "vector_store": "pgvector",
    "llm": "up",
},
```

- [ ] **Step 4: 验证**

```bash
cd backend && python -m pytest tests/unit/test_settings.py -v
python -c "from api.main import app; print('OK')"
```

---

### Task 6: 修复 BGE-M3 硬编码路径

**Files:**
- Modify: `backend/knowledge/retriever.py:49`

- [ ] **Step 1: 改为从环境变量读取，带合理默认值**

```python
# Before
self._bge_model = BGEM3FlagModel('C:/Users/29098/.cache/huggingface/hub/BAAI/bge-m3', use_fp16=False)

# After — 从环境变量读取，没设置则用 BGE-M3 的标准 HuggingFace 模型名
bge_path = os.getenv("BGE_MODEL_PATH", "BAAI/bge-m3")
self._bge_model = BGEM3FlagModel(bge_path, use_fp16=False)
```

同时在 `.env` 中加一行（可选，不设也能用默认值）：

```
BGE_MODEL_PATH=BAAI/bge-m3
```

> **说明**：`BAAI/bge-m3` 是 HuggingFace 标准模型名，`FlagEmbedding` 会自动下载缓存或从本地缓存加载。如果设置了 `HF_HUB_OFFLINE=1`，需确保模型已缓存。

- [ ] **Step 2: 验证**

```bash
cd backend && python -c "from knowledge.retriever import EmbeddingEncoder; print('OK')"
```

---

### Task 7: safety_check_node 复用 _shared.py 工具函数

**Files:**
- Modify: `backend/workflow/nodes/safety_check_node.py`

- [ ] **Step 1: 删除重复函数，改为导入**

```python
# 删除第 5-15 行的 _msg_content 和 _msg_role 函数定义

# 在文件顶部添加导入
from workflow.nodes._shared import msg_role, msg_content
```

- [ ] **Step 2: 更新函数调用**

文件中 `_msg_content(msg)` → `msg_content(msg)`，`_msg_role(msg)` → `msg_role(msg)`（共 2 处）。

- [ ] **Step 3: 验证**

```bash
cd backend && python -m pytest tests/unit/test_graph.py::test_graph_invoke_emergency_path -v
```

---

### Task 8: 替换 6 处 `datetime.utcnow()` 为时区安全的写法

**Files:**
- Modify: `backend/api/routers/messages.py:53, 142, 191`
- Modify: `backend/api/routers/sessions.py:38, 125`
- Modify: `backend/persistence/session_store.py:116`

- [ ] **Step 1: 统一替换**

```python
# Before
datetime.utcnow()

# After
datetime.now(timezone.utc)
```

同时在每个文件顶部添加导入：
```python
from datetime import datetime, timezone
```

> `messages.py` 和 `sessions.py` 已有 `from datetime import datetime`，只需加上 `timezone`。

- [ ] **Step 2: 验证**

```bash
cd backend && python -m pytest tests/unit/ -v
```

---

### Task 9: sessions.py 会话 CRUD 也接入 PostgreSQL

**Files:**
- Modify: `backend/api/routers/sessions.py`

- [ ] **Step 1: 在 session_store.py 新增 sessions 表的 CRUD**

在 `backend/persistence/session_store.py` 末尾添加：

```python
# ═══════════════════════════════════════════════════════════════
# 会话元数据（sessions 表）
# ═══════════════════════════════════════════════════════════════

async def list_sessions_from_db(limit: int = 50) -> list[dict]:
    engine = _get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT session_id, state_data->>'scenario_id' AS scenario,
                       state_data->>'current_stage' AS stage,
                       updated_at
                FROM session_state
                ORDER BY updated_at DESC
                LIMIT :limit
            """),
            {"limit": limit},
        )
        rows = result.fetchall()
        return [
            {
                "session_id": row[0],
                "scenario": row[1],
                "current_stage": row[2],
                "updated_at": row[3].isoformat() if row[3] else None,
            }
            for row in rows
        ]


async def delete_session_from_db(session_id: str) -> bool:
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM messages WHERE session_id = :sid"),
            {"sid": session_id},
        )
        result = await conn.execute(
            text("DELETE FROM session_state WHERE session_id = :sid"),
            {"sid": session_id},
        )
        return result.rowcount > 0
```

- [ ] **Step 2: 修改 sessions.py — 删除内存 dict，改用 DB 调用**

```python
# 删除 _sessions_store: dict[str, dict] = {}

# create_session: 不需要保存到 dict，session 的首次状态由 messages.py 管理
# list_sessions: 调用 list_sessions_from_db()
# get_session: 调用 load_state(session_id)  
# delete_session: 调用 delete_session_from_db(session_id)
```

注意：`ensure_tables()` 中需要新增 sessions 表的建表语句（或直接用 `session_state` 表替代 sessions 表的功能），或者扩展现有的 `session_state` 表。

实际上最简单的方案：**让 sessions.py 直接复用 `session_state` 表**，不再维护独立的 `sessions` 表。`list_sessions` 查询 `session_state` 表，`get_session` 用 `load_state()`，`delete_session` 级联删除 `session_state` + `messages`。

- [ ] **Step 3: 验证**

```bash
cd backend && python -m pytest tests/unit/ -v
```

---

### Task 10: 最终验证

- [ ] **Step 1: 运行全部测试**

```bash
cd backend && python -m pytest tests/unit/ -v --ignore=tests/unit/test_database.py
```

- [ ] **Step 2: 启动服务确认无运行时错误**

```bash
cd backend && python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "fix: resolve high and medium priority issues from code review"
```

---

## 自检清单

1. **覆盖度**：4 高优 + 6 中优 = 10/10 全覆盖 ✓
2. **空占位符**：无 "TBD" / "TODO" ✓
3. **类型一致性**：Task 7 改 `_msg_content` → `msg_content` 后，函数签名完全相同 ✓
4. **Task 3 的 search_results 合并逻辑**：SearchResult dataclass → dict 序列化 + 与 state 旧结果合并去重 ✓
5. **Task 9 sessions.py 迁移**：直接在 `session_state` 表上做 CRUD，不新增表，保持简洁 ✓
