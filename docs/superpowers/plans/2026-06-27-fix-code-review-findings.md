# 修复代码审查问题 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 2026-06-27 全栈审查中发现的 17 个待修问题（9 Critical + 8 Important），按优先级分三批执行。

**Architecture:** 不改动现有架构，只做局部修复。每批修改 2-5 个文件，集中在同一子系统内。

**Tech Stack:** Python 3.11+ / FastAPI / LangGraph / PostgreSQL + asyncpg / Vue 3 + TypeScript

---

## 已修复项（本次计划不重复）

| 审查编号 | 问题 | 状态 |
|---------|------|------|
| 前端 C1 | PII masker 未实现 | ✅ 已实现 `piiMasker.ts` 并集成到 Vue+JS |
| 前端 C2 | JS API_BASE 硬编码 localhost | ✅ 改为 `/api/v1` |
| 前端 C3 | currentSessionId 类型不一致 | ✅ 统一用 `session.session_id` |
| 前端 C4 | v-html XSS | ✅ 加 DOMPurify |
| 重要 I6 | isDiagnosisDone 用启发式 | ✅ 改用 `next_action` 权威信号 |
| 重要 I7 | 无 token 持久化/401 拦截 | ✅ sessionStorage + onUnauthorized |
| 重要 I8 | 无请求超时 | ✅ 120s 超时 |
| 会话路由 | session_id 无校验 | ✅ 改为 `uuid.UUID` |
| create_session | 缺少 session_id 字段 | ✅ 已补 |

---

## 第一批：安全红线（最高优先级）

### Task 1: 修复 PII 脱敏未写回 state → 原始 PII 流入 LLM

**文件:**
- 修改: `backend/workflow/nodes/safety_check_node.py:22-34`
- 参阅: `backend/safety/l0_filter.py:134-148`（`_mask_pii` 函数）

**问题：** `safety_check_node` 调用了 `_mask_pii(user_input)` 得到脱敏文本，但仅在紧急/阻塞情况下使用。正常流程下脱敏后的文本从不写回 `state["messages"]`，原始 PII 继续向下游 LLM 传播。

**修复方案：** 在非紧急、非阻塞路径中，用脱敏后的用户消息替换 `state["messages"]` 中最后一条 user 消息的 content。

- [ ] **Step 1: 阅读 `safety_check_node.py` 完整逻辑**

- [ ] **Step 2: 添加脱敏回写逻辑**

从 `l0_result.response`（已脱敏的文本）提取脱敏后的内容，替换 `state["messages"]` 中最后一条 role="user" 的消息：

```python
# 在 safety_check_node 的 return 之前、非紧急非阻塞路径中：
# 将脱敏后的用户输入写回 messages，防止原始 PII 流入下游 LLM
masked_content = l0_result.response or user_input  # _mask_pii 已处理
for i in range(len(messages) - 1, -1, -1):
    if messages[i].get("role") == "user":
        messages[i]["content"] = masked_content
        break
```

- [ ] **Step 3: 手动验证**

启动后端，发送含身份证号的测试消息（如 "我叫张三，身份证号110101199001011234"），查看日志确认 LLM 收到的 prompt 中身份证号已被替换为 `[身份证已隐藏]`。

- [ ] **Step 4: Commit**

```bash
git add backend/workflow/nodes/safety_check_node.py
git commit -m "fix(safety): write masked PII back to state messages"
```

---

### Task 2: 补齐 7 个 API 端点的鉴权

**文件:**
- 修改: `backend/api/routers/sessions.py:54,72,94,115`
- 修改: `backend/api/routers/messages.py:33,186,204`

**问题：** sessions 的 list/get/update/delete 和 messages 的 send/list/stream 全部缺少 `Depends(get_current_user)`，未登录用户可以访问任意会话数据。

**注意：** `create_session` (sessions.py:23) 已经有 `Depends(get_current_user)`，作为模板参考。

- [ ] **Step 1: sessions.py 三个端点加鉴权**

```python
# 第 54 行
async def list_sessions(status: str = None, user_id: str = None, ..., user: dict = Depends(get_current_user)):

# 第 72 行
async def get_session(session_id: uuid.UUID, user: dict = Depends(get_current_user)):

# 第 94 行
async def update_session(session_id: uuid.UUID, req: UpdateSessionRequest, user: dict = Depends(get_current_user)):

# 第 115 行
async def delete_session(session_id: uuid.UUID, user: dict = Depends(get_current_user)):
```

- [ ] **Step 2: messages.py 三个端点加鉴权**

```python
# 第 33 行
async def send_message(session_id: uuid.UUID, req: SendMessageRequest, user: dict = Depends(get_current_user)):

# 第 186 行
async def list_messages(session_id: uuid.UUID, ..., user: dict = Depends(get_current_user)):

# 第 204 行
async def stream_events(session_id: uuid.UUID, user: dict = Depends(get_current_user)):
```

- [ ] **Step 3: 验证**

用 curl 不带 token 请求 `GET /api/v1/sessions`，确认返回 401/403 而非 200。

- [ ] **Step 4: Commit**

```bash
git add backend/api/routers/sessions.py backend/api/routers/messages.py
git commit -m "fix(security): add auth to all session and message endpoints"
```

---

### Task 3: 修复 `list_sessions_from_db` user_id 过滤错误

**文件:**
- 修改: `backend/persistence/session_store.py:209`

**问题：** 第 209 行 `state_data->>'scenario_id' = :user_id` 错误地按 `scenario_id` 过滤，而不是 `user_id`。

- [ ] **Step 1: 改 SQL 过滤条件**

```python
# 第 208-209 行，将：
conditions.append("state_data->>'scenario_id' = :user_id")
# 改为：
conditions.append("state_data->>'user_id' = :user_id")
```

- [ ] **Step 2: Commit**

```bash
git add backend/persistence/session_store.py
git commit -m "fix(sessions): filter by user_id instead of scenario_id"
```

---

## 第二批：数据完整性

### Task 4: 修复 `save_state` 覆盖丢失字段

**文件:**
- 修改: `backend/persistence/session_store.py:79-92`
- 修改: `backend/api/routers/messages.py:120-135`

**问题：** `save_state` 用 `ON CONFLICT DO UPDATE SET state_data = EXCLUDED.state_data` 整体替换 JSONB 列。`messages.py` 调用时没传 `user_id`/`created_at`，导致第一条消息后这些字段丢失。

**修复方案：** 改为深度合并（`jsonb_set` 逐 key 更新），或让 `save_state` 先加载现有 state，合并后再写入。

- [ ] **Step 1: 改用合并策略**

在 `save_state` 中先 SELECT 现有 state_data，合并后再 UPDATE：

```python
async def save_state(session_id: str, state: dict) -> None:
    """保存（插入或合并更新）会话状态 — 不会覆盖未传入的 key"""
    engine = _get_engine()
    async with engine.begin() as conn:
        # 先查现有
        result = await conn.execute(
            text("SELECT state_data FROM session_state WHERE session_id = :sid"),
            {"sid": session_id},
        )
        row = result.fetchone()
        existing = row[0] if row else {}

        # 合并：新值覆盖旧值，但保留旧值中未被覆盖的 key
        merged = {**existing, **state}

        await conn.execute(
            text("""
                INSERT INTO session_state (session_id, state_data, updated_at)
                VALUES (:sid, :data, NOW())
                ON CONFLICT (session_id) DO UPDATE
                SET state_data = :data2, updated_at = NOW()
            """),
            {"sid": session_id, "data": json.dumps(merged, ensure_ascii=False),
             "data2": json.dumps(merged, ensure_ascii=False)},
        )
```

- [ ] **Step 2: 验证**

创建会话 → 发送消息 → 查询 `session_state` 表，确认 `user_id` 和 `created_at` 仍然存在。

- [ ] **Step 3: Commit**

```bash
git add backend/persistence/session_store.py
git commit -m "fix(persistence): merge state on save instead of overwriting"
```

---

### Task 5: 修复用户消息先于工作流成功持久化

**文件:**
- 修改: `backend/api/routers/messages.py:60,117-163`

**问题：** 用户消息在第 60 行就 `append_message` 入库了，工作流在第 117 行才执行。如果工作流中途崩溃，用户消息已入库但 AI 回复不存在，状态不一致。

**修复方案：** 把用户消息的持久化推迟到工作流成功后，或者把一整段包在 try/except 里，失败时回滚（把用户消息删掉）。

- [ ] **Step 1: 移到工作流成功后持久化**

把第 49-61 行（用户消息持久化）移到第 117 行 `graph.ainvoke` 之后、第 119 行 `save_state` 之前：

```python
# ---- 第3步：执行AI工作流 ----
result = await graph.ainvoke(state)

# ---- 第2.5步：工作流成功后才持久化用户消息 ----
user_msg = {
    "id": str(uuid.uuid4()),
    "session_id": sid,
    "round_number": prev.get("round_count", 0),
    "role": "user",
    "content": req.content,
    "content_type": req.content_type,
    "agent_source": None,
    "token_count": None,
    "created_at": datetime.now(timezone.utc),
}
await append_message(sid, user_msg)

# ---- 保存状态到 DB ----
await save_state(sid, {...})
```

- [ ] **Step 2: 验证**

模拟工作流失败（如断开 DB 连接），确认用户消息未入库。

- [ ] **Step 3: Commit**

```bash
git add backend/api/routers/messages.py
git commit -m "fix(messages): persist user message only after workflow success"
```

---

### Task 6: 修复 `basic_consultation.j2` 重复/矛盾的提示段落

**文件:**
- 修改: `backend/prompts/basic_consultation.j2:26-42`

**问题：** 有两个连续的 `## 提问规则` 段落，第一个要求 3-5 选项+含"其他"，第二个要求 4 选项+不含"其他"。LLM 收到矛盾指令，输出不稳定。

- [ ] **Step 1: 阅读完整文件，确认两段的差异**

- [ ] **Step 2: 合并为唯一的提问规则段落**

保留第一段的结构（3-5 选项），把第二段独有的约束（4 选项上限、不含"其他"）合并进去，统一为：

```
## 提问规则
- 必须生成选择题，4 个选项，最后一个可以是"其他（请描述）"
- 选项应为单选
```

- [ ] **Step 3: Commit**

```bash
git add backend/prompts/basic_consultation.j2
git commit -m "fix(prompts): remove duplicate conflicting question rules"
```

---

## 第三批：健壮性

### Task 7: 修复 `RealL2Adapter.generate_question` 未捕获 ValidationError

**文件:**
- 修改: `backend/llm/real_llm_adapter.py:450-465`

**问题：** LLM 返回非 JSON 时，`_extract_json` 返回 `{}`，`L2ResponseSchema.model_validate({})` 抛 `ValidationError` 未被捕获，直接返回 500。

- [ ] **Step 1: 加 try/except + 降级响应**

```python
# 在 generate_question() 的 return 语句外包 try/except
try:
    validated = L2ResponseSchema.model_validate(result)
    return validated.model_dump()
except ValidationError:
    logger.warning("LLM output failed schema validation, returning fallback")
    return {
        "response_text": "抱歉，我需要更多信息来帮助分析您的情况。请尝试用不同的方式描述您的症状。",
        "options": [
            {"index": 1, "label": "重新描述症状", "value": "重新描述"},
            {"index": 2, "label": "换个方式说", "value": "换种说法"},
        ],
        "next_action": "continue",
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/llm/real_llm_adapter.py
git commit -m "fix(llm): handle ValidationError in generate_question with fallback"
```

---

### Task 8: 清理 14 个空字节残留文件

**文件:**
- 删除以下 14 个 0 字节占位文件：
  - `frontend/src/components/ChatMessage.vue`
  - `frontend/src/components/EmergencyAlert.vue`
  - `frontend/src/components/SessionSidebar.vue`
  - `frontend/src/components/HumanReviewPanel.vue`
  - `frontend/src/api/messageApi.ts`
  - `frontend/src/api/sessionApi.ts`
  - `frontend/src/api/safetyApi.ts`
  - `frontend/src/stores/safetyStore.ts`
  - `frontend/src/utils/sseHandler.ts`
  - `frontend/src/utils/markdownRenderer.ts`
  - `frontend/src/views/ChatPage.vue`
  - `frontend/src/views/HistoryPage.vue`
  - `frontend/src/views/ReportPage.vue`
  - `frontend/src/styles/global.css`

**确认：** 这些文件每个都有对应的正确实现文件在不同路径下，删除它们不会影响功能。

- [ ] **Step 1: 逐个删除**

```bash
rm frontend/src/components/ChatMessage.vue
# ... 等 14 个文件
```

- [ ] **Step 2: 验证构建**

```bash
cd frontend && npm run build
```
预期：构建成功。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/
git commit -m "chore: remove 14 empty placeholder files"
```

---

### Task 9: 修复注册 TOCTOU 竞态条件

**文件:**
- 修改: `backend/api/routers/auth.py:29-57`

**问题：** 手机号查重 SELECT 和 INSERT 不在同一事务中，并发注册可能绕过唯一性检查，触发数据库 UNIQUE 约束报 500。

- [ ] **Step 1: 包在同一个事务中 + 捕获 UNIQUE 约束异常**

```python
async def register(...):
    engine = _get_engine()
    async with engine.begin() as conn:
        # 查重（事务内）
        result = await conn.execute(
            text("SELECT id FROM users WHERE phone = :phone"),
            {"phone": req.phone},
        )
        if result.fetchone():
            raise HTTPException(status_code=409, detail="手机号已注册")

        # 插入（同一事务）
        user_id = str(uuid.uuid4())
        await conn.execute(
            text("INSERT INTO users (id, phone, password_hash, nickname) VALUES (:id, :phone, :pw, :nick)"),
            {"id": user_id, "phone": req.phone, "pw": password_hash, "nick": req.nickname},
        )
    # ...
```

- [ ] **Step 2: Commit**

```bash
git add backend/api/routers/auth.py
git commit -m "fix(auth): wrap register in single transaction to prevent TOCTOU"
```

---

### Task 10: 修复 App.js 输入丢失问题

**文件:**
- 修改: `frontend/js/app.js:299-315`

**问题：** `sendMessage` 在创建会话**之前**就清掉了 `inputEl.value = ''`。如果 `createSession()` 失败，用户输入永久丢失。

- [ ] **Step 1: 把 inputEl.value = '' 移到创建会话之后**

当前顺序：
```javascript
inputEl.value = '';  // ← 先清空
// ...
if (!currentSessionId) {
    await api.createSession();  // 失败 → 输入已丢
}
```

改为：
```javascript
// 先读值，不清空
const text = inputEl.value.trim();
// ...
if (!currentSessionId) {
    const res = await api.createSession();  // 如果失败，text 还在
    if (!res) { sendBtn.disabled = false; return; }
    // 成功后再清空
}
inputEl.value = '';
```

- [ ] **Step 2: Commit**

```bash
git add frontend/js/app.js
git commit -m "fix(js): clear input only after session creation succeeds"
```

---

## 验证方案

每批结束后运行：
```bash
# 后端语法检查
cd backend && python -m py_compile api/routers/*.py persistence/*.py workflow/nodes/*.py

# 前端类型检查 + 构建
cd frontend && npx vue-tsc --noEmit && npm run build

# 端到端烟雾测试
# 1. 启动后端
# 2. 注册 → 登录 → 创建会话 → 发送含 PII 消息
# 3. 确认 LLM 日志中 PII 已脱敏
# 4. 确认诊断报告正常生成
# 5. curl 无 token → 确认 401
```

---

## 可选后续任务（下一轮）

这些影响较小，当前轮次不阻塞上线：

| 审查编号 | 问题 | 理由 |
|---------|------|------|
| C5 | routes.py 条件边内变异 state | LangGraph 当前版本容忍此行为，实测未出 bug |
| C8 | medical_records/audit_logs 表死代码 | 需要决定是删除还是实现，涉及架构决策 |
| I2 | profile medical_info 竞态 | 低频操作，mongodb-style 合并方式可接受 |
| I3 | retriever 全量向量搜索低效 | 知识库当前规模不大，性能影响有限 |
| I4 | vector_store f-string 嵌入向量 | 非用户可控输入，无实际注入风险 |
| I7 | content_filter 缺中药单位 | 覆盖率提升，非阻断性 |
| I8 | l0_filter 过量检测过宽 | 假阳性偏安全侧（宁可多报），符合医疗场景 |
