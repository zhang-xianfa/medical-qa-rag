# 简化创建会话 API 计划

## 目标

将 `POST /api/v1/sessions` 改为无需传参，用户身份从 JWT 解析。

### 当前现状

```json
POST /api/v1/sessions
{
  "user_id": "string",       // ← 可从 JWT 获取，多余
  "max_rounds": 5,           // ← 固定 10 即可
  "metadata": {}             // ← 代码中从未使用，死字段
}
```

`metadata` 只在 `api/schemas/session.py:11` 定义，**全部生产代码没有消费它**。

### 改后效果

```json
POST /api/v1/sessions   (空 body，身份从 Authorization header 解析)
Authorization: Bearer <token>
              ↓
201  { "id": "...", "user_id": "uuid-from-jwt", "status": "active", ... }
```

---

## 文件变更

### Task 1: 修改 `api/schemas/session.py`

**删除** `CreateSessionRequest` 类（不再需要）。改为空请求体。

实际做法：保留 class 但去掉所有字段，或者直接用 `Body()` 默认值为空。最简单的：删掉 `CreateSessionRequest`，路由参数用 `Depends(get_current_user)` 即可。

如果 Pydantic model 被其他地方 import 导致删除会出错，则改为空 model：
```python
class CreateSessionRequest(BaseModel):
    pass
```

同时检查 `SessionResponse` 的 `user_id` 字段保留（响应中返回用户 ID 是合理的）。

### Task 2: 修改 `api/routers/sessions.py`

`create_session` 函数：
- 添加 `Depends(get_current_user)` 获取当前用户
- `user_id` 从 `user["user_id"]` 获取
- `max_rounds` 硬编码为 `10`

改动前后对比：

```python
# Before
@router.post("/sessions", status_code=201)
async def create_session(req: CreateSessionRequest):
    sid = str(uuid.uuid4())
    ...
    await save_state(sid, {
        "user_id": req.user_id,
        "max_rounds": req.max_rounds,
        ...
    })

# After
@router.post("/sessions", status_code=201)
async def create_session(user: dict = Depends(get_current_user)):
    sid = str(uuid.uuid4())
    ...
    await save_state(sid, {
        "user_id": user["user_id"],
        "max_rounds": 10,
        ...
    })
```

需要在 sessions.py 顶部添加导入：
```python
from api.dependencies import get_current_user
from fastapi import Depends
```

### Task 3: 清理 import 引用

确认 `api/schemas/session.py` 的 `CreateSessionRequest` 不再被其他模块导入（只被 `sessions.py` 引用）。如果 `__init__.py` 有 re-export，一并移除。

---

## 不动的部分

| 内容 | 原因 |
|------|------|
| `UpdateSessionRequest` | PATCH 接口仍需要 `max_rounds` 可选字段 |
| `SessionResponse` | 响应结构不变 |
| `list_sessions` | `user_id` 查询参数保留（筛选用途） |
| `safety_events.py` | 不受影响 |

---

## 验证

```bash
# 测试：无 token 应返回 401
curl -X POST http://127.0.0.1:8000/api/v1/sessions

# 测试：带 token 创建成功
curl -X POST http://127.0.0.1:8000/api/v1/sessions \
  -H "Authorization: Bearer <login_token>" \
  -H "Content-Type: application/json" -d '{}'
```
