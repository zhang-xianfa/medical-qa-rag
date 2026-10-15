# 上线前问题修复 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复上线前审计发现的 15 个 BLOCKER + HIGH 问题，使项目达到可部署状态。

**Architecture:** 分四批：基础设施 → 安全配置 → 后端代码修复 → 前端补全。每批内部任务独立可并行。

**Tech Stack:** Python 3.11+ / FastAPI / LangGraph / PostgreSQL / Vue 3 / TypeScript / Docker / Nginx

---

## 第一批：基础设施（解除 BLOCKER #2 #3 #5 #6 #8 #21 #22）

### Task 1: 补齐 `requirements.txt` 缺失依赖

**Files:**
- 修改: `backend/requirements.txt`

- [ ] **Step 1: 读取当前 requirements.txt**

```bash
cat backend/requirements.txt
```

- [ ] **Step 2: 追加缺失的 4 个依赖**

在文件末尾追加：

```text
bcrypt>=4.0.0,<5.0.0
python-jose[cryptography]>=3.3.0
jinja2>=3.1.0
asyncpg>=0.29.0
```

- [ ] **Step 3: 验证安装**

```bash
cd backend && pip install -r requirements.txt --dry-run 2>&1 | tail -5
```

期望：无 "not found" 错误。

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "fix: add missing dependencies (bcrypt, python-jose, jinja2, asyncpg)"
```

---

### Task 2: 创建 `nginx.conf`

**Files:**
- 修改: `nginx.conf`（当前 0 字节）

- [ ] **Step 1: 写入生产级 nginx 配置**

```nginx
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate     /etc/ssl/certs/fullchain.pem;
    ssl_certificate_key /etc/ssl/private/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # 安全头
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self' data:; connect-src 'self' https://api.deepseek.com;" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # 速率限制
    limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/m;
    limit_req_zone $binary_remote_addr zone=api:10m rate=30r/m;

    # API 代理
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 支持
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;

        # 速率限制
        limit_req zone=api burst=10 nodelay;
    }

    location /api/v1/auth/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        limit_req zone=auth burst=3 nodelay;
    }

    # 前端静态文件
    location / {
        proxy_pass http://frontend:5173;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

- [ ] **Step 2: 验证语法**

```bash
nginx -t -c nginx.conf 2>&1 || echo "Will validate at deploy time"
```

- [ ] **Step 3: Commit**

```bash
git add nginx.conf
git commit -m "feat: add production nginx config with SSL, CSP, rate limiting, SSE support"
```

---

### Task 3: 创建 `docker-compose.yml`

**Files:**
- 修改: `docker-compose.yml`（当前 0 字节）

- [ ] **Step 1: 写入 docker-compose 编排**

```yaml
version: "3.9"

services:
  db:
    image: pgvector/pgvector:pg16
    container_name: medical-pgvector
    environment:
      POSTGRES_USER: ${DB_USER:-postgres}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: medical_qa
    ports:
      - "5433:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-postgres}"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: ./backend
    container_name: medical-backend
    environment:
      DATABASE_URL: postgresql+asyncpg://${DB_USER:-postgres}:${DB_PASSWORD}@db:5432/medical_qa
      JWT_SECRET: ${JWT_SECRET}
      DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY}
      EMBEDDING_API_KEY: ${EMBEDDING_API_KEY}
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}
      CORS_ORIGINS: '["https://your-domain.com"]'
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
    container_name: medical-frontend
    ports:
      - "5173:80"
    depends_on:
      - backend
    restart: unless-stopped

volumes:
  pgdata:
```

- [ ] **Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add docker-compose with db, backend, frontend services"
```

---

### Task 4: 创建前端 `Dockerfile`

**Files:**
- 修改: `frontend/Dockerfile`（当前 0 字节）

- [ ] **Step 1: 写入多阶段构建 Dockerfile**

```dockerfile
# Stage 1: Build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: Serve
FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx-frontend.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

- [ ] **Step 2: Commit**

```bash
git add frontend/Dockerfile
git commit -m "feat: add frontend multi-stage Dockerfile"
```

---

### Task 5: 创建 `.dockerignore`

**Files:**
- 创建: `.dockerignore`

- [ ] **Step 1: 写入**

```text
.env
.git
.gitignore
__pycache__
*.pyc
.idea
node_modules
dist
.pytest_cache
*.egg-info
```

- [ ] **Step 2: Commit**

```bash
git add .dockerignore
git commit -m "chore: add .dockerignore"
```

---

### Task 6: CORS 配置改为环境变量控制

**Files:**
- 修改: `backend/config/settings.py:34`

- [ ] **Step 1: 改 settings.py**

当前：
```python
CORS_ORIGINS: list[str] = ["*"]
```

改为：
```python
CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:8000"]
```

docker-compose 中通过环境变量 `CORS_ORIGINS` 覆盖为生产域名。开发环境默认允许 localhost。

- [ ] **Step 2: 验证**

```bash
python -m py_compile backend/config/settings.py && echo "OK"
```

- [ ] **Step 3: Commit**

```bash
git add backend/config/settings.py
git commit -m "fix(security): restrict CORS to localhost by default, configurable via env"
```

---

### Task 7: 补充 `safety_events.py` 鉴权

**Files:**
- 修改: `backend/api/routers/safety_events.py:7`

- [ ] **Step 1: 加 Depends(get_current_user)**

```python
from api.dependencies import get_current_user

@router.get("/sessions/{session_id}/safety")
async def list_safety_events(
    session_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    ...
):
```

- [ ] **Step 2: 验证**

```bash
python -m py_compile backend/api/routers/safety_events.py && echo "OK"
```

- [ ] **Step 3: Commit**

```bash
git add backend/api/routers/safety_events.py
git commit -m "fix(security): add auth to safety events endpoint"
```

---

## 第二批：安全配置（解除 BLOCKER #1 + HIGH #10 #12 #13 #14）

### Task 8: 安全加固 `.env` — 轮换密钥 + 创建 `.env.example`

**Files:**
- 修改: `backend/.env`
- 创建: `backend/.env.example`

- [ ] **Step 1: 生成随机密钥**

```bash
python -c "import secrets; print('JWT_SECRET=' + secrets.token_hex(64))"
python -c "import secrets; print('ENCRYPTION_KEY=' + secrets.token_hex(32))"
```

- [ ] **Step 2: 更新 `.env`**

将 `JWT_SECRET` 和 `ENCRYPTION_KEY` 替换为上面生成的值。

**重要：** `DEEPSEEK_API_KEY` 需在 DeepSeek 控制台轮换旧密钥，然后更新 `.env`。这一步需要人工操作。

- [ ] **Step 3: 创建 `.env.example`（不含真实密钥）**

```text
# LLM
DEEPSEEK_API_KEY=your-deepseek-api-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# Embedding
EMBEDDING_API_KEY=your-embedding-api-key-here

# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5433/medical_qa

# Security — 生成方式: python -c "import secrets; print(secrets.token_hex(64))"
JWT_SECRET=change-me-to-a-random-64-byte-hex-string
ENCRYPTION_KEY=change-me-to-a-random-32-byte-hex-string
```

- [ ] **Step 4: 确认 `.env` 在 `.gitignore`**

```bash
grep -q "\.env" .gitignore 2>/dev/null || echo ".env" >> .gitignore
```

- [ ] **Step 5: Commit**

```bash
git add backend/.env.example .gitignore
git commit -m "fix(security): create .env.example, ensure .env is gitignored"
```

---

### Task 9: 补充 `EMBEDDING_API_KEY` + BGE 本地回退

**Files:**
- 修改: `backend/.env`（人工操作）
- 修改: `backend/knowledge/retriever.py:60-77`

- [ ] **Step 1: 确保 BGE 本地模型路径可配**

查看 `BGE_MODEL_PATH` 环境变量是否已在 `settings.py` 中定义。如果未定义，让 EmbeddingConfig 优先使用 API key 配置，缺失时自动回退到本地 BGE-M3。

当前 `retriever.py:74-77` 已有零向量回退逻辑，但应该改为抛明确错误而非静默降级：

```python
if not self.api_key and not self.model_path:
    raise RuntimeError(
        "EMBEDDING_API_KEY or BGE_MODEL_PATH must be configured. "
        "Set EMBEDDING_API_KEY in .env for API-based embeddings, "
        "or BGE_MODEL_PATH for local BGE-M3."
    )
```

- [ ] **Step 2: 验证**

```bash
python -m py_compile backend/knowledge/retriever.py && echo "OK"
```

- [ ] **Step 3: Commit**

```bash
git add backend/knowledge/retriever.py
git commit -m "fix(embedding): raise clear error instead of silent zero-vector fallback"
```

---

### Task 10: JWT 过期时间缩短 + 登录速率限制

**Files:**
- 修改: `backend/api/routers/auth.py:19`

- [ ] **Step 1: 缩短 token 过期时间**

```python
# 当前
TOKEN_EXPIRE_HOURS = 72

# 改为
TOKEN_EXPIRE_HOURS = 24
```

- [ ] **Step 2: 添加失败的登录尝试计数（内存版，供 nginx 正式速率限制前的开发防护）**

在 `auth.py` 的 login 函数开头加：

```python
# 简单的内存速率限制（生产用 nginx limit_req 替代）
_login_attempts: dict[str, list[float]] = {}

def _check_rate_limit(phone: str, max_attempts: int = 5, window: int = 300) -> bool:
    now = time.time()
    attempts = _login_attempts.get(phone, [])
    attempts = [t for t in attempts if now - t < window]
    _login_attempts[phone] = attempts
    return len(attempts) < max_attempts

def _record_attempt(phone: str):
    _login_attempts.setdefault(phone, []).append(time.time())
```

在 `login` 函数中：
```python
if not _check_rate_limit(req.phone):
    raise HTTPException(status_code=429, detail="登录尝试过于频繁，请5分钟后再试")
# ... 验证密码 ...
_record_attempt(req.phone)
```

- [ ] **Step 3: 验证**

```bash
python -m py_compile backend/api/routers/auth.py && echo "OK"
```

- [ ] **Step 4: Commit**

```bash
git add backend/api/routers/auth.py
git commit -m "fix(security): reduce JWT expiry to 24h, add login rate limiting"
```

---

### Task 11: 修复 `list_sessions` user_id 泄露

**Files:**
- 修改: `backend/api/routers/sessions.py:55`

- [ ] **Step 1: 移除或强制匹配 user_id**

当前 `list_sessions` 接受任意 `user_id` 查询参数。改为强制使用已认证用户 ID：

```python
@router.get("/sessions")
async def list_sessions(
    status: str = None,
    limit: int = 20,
    offset: int = 0,
    user: dict = Depends(get_current_user),
):
    data, total = await list_sessions_from_db(
        status=status,
        user_id=user["user_id"],  # 强制使用认证用户 ID
        limit=limit,
        offset=offset,
    )
```

移除函数签名中的 `user_id: str = None` 参数。

- [ ] **Step 2: 验证**

```bash
python -m py_compile backend/api/routers/sessions.py && echo "OK"
```

- [ ] **Step 3: Commit**

```bash
git add backend/api/routers/sessions.py
git commit -m "fix(security): enforce authenticated user_id in list_sessions"
```

---

## 第三批：后端代码修复（解除 BLOCKER #4 + HIGH #9 #11 #15）

### Task 12: 删除 `print()` PII 泄漏

**Files:**
- 修改: `backend/workflow/nodes/expert_interview_node.py:60-89`
- 修改: `backend/workflow/diagnosis_agent.py:63-70`

- [ ] **Step 1: expert_interview_node.py**

将所有 `print(...)` 改为 `logger.debug(...)`：

```python
# 当前 (示例)
print(f"检索到 {len(results)} 条结果")
print(f"  {r['title']}: {r.get('content_excerpt', '')[:80]}")

# 改为
logger.debug("检索到 %d 条结果", len(results))
logger.debug("  %s: %.80s", r.get('title', ''), r.get('content_excerpt', ''))
```

- [ ] **Step 2: diagnosis_agent.py**

将所有 `print(...)` 改为 `logger.debug(...)`：

```python
# 当前
print("【患者信息】", json.dumps(collected_info, ensure_ascii=False, indent=2))

# 改为
logger.debug("【患者信息】%s", json.dumps(collected_info, ensure_ascii=False, indent=2))
```

- [ ] **Step 3: 验证**

```bash
python -m py_compile backend/workflow/nodes/expert_interview_node.py backend/workflow/diagnosis_agent.py && echo "OK"
```

- [ ] **Step 4: Commit**

```bash
git add backend/workflow/nodes/expert_interview_node.py backend/workflow/diagnosis_agent.py
git commit -m "fix(security): replace print() with logger.debug() to prevent PII in stdout"
```

---

### Task 13: `vector_store.py` SQL 参数化

**Files:**
- 修改: `backend/knowledge/vector_store.py:118,143-148,159-165,178-181`

- [ ] **Step 1: 表名白名单校验**

在 `PGVectorStore.__init__` 中：

```python
import re

def __init__(self, table_name: str = "knowledge_vectors"):
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
        raise ValueError(f"Invalid table name: {table_name}")
    self._table = table_name
```

- [ ] **Step 2: 向量搜索改用参数化查询**

当前用 f-string 拼向量值。pgvector 支持 `:vec::vector` 参数绑定。将：

```python
vec_str = f"'[{','.join(str(x) for x in vec)}]'"
result = await conn.execute(
    text(f"SELECT id, 1 - (embedding <=> {vec_str}::vector) AS score FROM {self._table} ...")
)
```

改为使用 `text()` 参数的显式类型转换：

```python
result = await conn.execute(
    text("SELECT id, 1 - (embedding <=> :vec::vector) AS score FROM " + self._table + " ..."),
    {"vec": f"[{','.join(str(x) for x in vec)}]"}
)
```

- [ ] **Step 3: 验证**

```bash
python -m py_compile backend/knowledge/vector_store.py && echo "OK"
```

- [ ] **Step 4: Commit**

```bash
git add backend/knowledge/vector_store.py
git commit -m "fix(security): parameterize vector SQL queries, validate table name"
```

---

### Task 14: 修复 `_sync_run` 阻塞 — 改用原生异步调用

**Files:**
- 修改: `backend/llm/real_llm_adapter.py:345-365,391-412,458`

- [ ] **Step 1: 将 `classify` 和 `generate_question` 改为 async**

`_sync_run` 的逻辑是：检测事件循环 → 如果存在则 `asyncio.run()` 在新线程中运行。既然所有调用者都在 async 上下文中（FastAPI + LangGraph），直接改为 `async def` + `await`：

```python
# classify: 改 async def + await
async def classify(self, user_message: str, ...):
    ...
    response = await self.client.chat.completions.create(...)  # 已经是 awaitable
    ...

# generate_question: 改 async def + await（当前第 440 行已经是 await，只需去掉 _sync_run 包装）
```

然后更新调用者：
- `basic_interview_node.py` — 调用已改为 `await adapter.generate_question(...)` 
- `expert_interview_node.py` — 同理

- [ ] **Step 2: 验证**

```bash
python -m py_compile backend/llm/real_llm_adapter.py && echo "OK"
```

检查调用链：
```bash
grep -rn "_sync_run\|generate_question\|\.classify(" backend/workflow/nodes/ backend/workflow/routes.py
```
确认所有调用处已使用 `await`。

- [ ] **Step 3: Commit**

```bash
git add backend/llm/real_llm_adapter.py
git commit -m "fix(llm): replace _sync_run blocking with native async/await"
```

---

## 第四批：前端补全（解除 HIGH #16 #17）

### Task 15: 添加 CSP + 移除 console.log

**Files:**
- 修改: `frontend/index.html`
- 修改: `frontend/src/stores/messageStore.ts:88`

- [ ] **Step 1: index.html 加 CSP meta 标签**

在 `<head>` 内追加：

```html
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self' data:; connect-src 'self' https://api.deepseek.com;">
```

- [ ] **Step 2: messageStore.ts 移除 console.log**

将：
```typescript
console.log('Request aborted for session:', sessionIdForThisRequest);
```

改为静默返回（`AbortError` 是正常流程，无需打日志）。

- [ ] **Step 3: 验证构建**

```bash
cd frontend && npm run build
```
期望：构建成功，无 console.log 残留。

- [ ] **Step 4: Commit**

```bash
git add frontend/index.html frontend/src/stores/messageStore.ts
git commit -m "fix(frontend): add CSP header, remove production console.log"
```

---

## 验证方案

全部完成后执行：

```bash
# 1. 后端语法检查
cd backend
python -m py_compile api/routers/*.py api/dependencies.py config/settings.py \
  persistence/session_store.py knowledge/vector_store.py knowledge/retriever.py \
  llm/real_llm_adapter.py workflow/nodes/expert_interview_node.py workflow/diagnosis_agent.py

# 2. 前端类型检查 + 构建
cd ../frontend
npx vue-tsc --noEmit && npm run build

# 3. 依赖检查
cd ../backend
pip install -r requirements.txt --dry-run

# 4. Docker 构建（如已安装 Docker）
cd ..
docker compose config 2>&1  # 验证 yaml 语法
```

---

## MEDIUM 问题（本计划不覆盖，择机处理）

| # | 问题 | 理由 |
|---|------|------|
| 18 | `messages` 表缺 `round_number` 索引 | 数据量小时无性能影响 |
| 19 | `session_state` 缺 `updated_at` 索引 | 同上 |
| 20 | 手机号格式校验 | 非阻塞，前端 pattern + 后端 regex 纯增量 |
| DB schema 统一 | ORM vs raw SQL 三套并存 | 需架构决策，单独一个计划 |
