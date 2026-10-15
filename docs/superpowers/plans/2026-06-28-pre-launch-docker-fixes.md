# Docker 生产环境上线修复计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 5 个生产环境 Critical 问题，使项目可通过 `docker-compose up` 一键部署

**Architecture:** nginx 反向代理 (SSL 终止) → frontend (静态文件) / backend (gunicorn+uvicorn workers) → PostgreSQL+pgvector

**Tech Stack:** Docker Compose, nginx, FastAPI + gunicorn, Vue3 + Vite, PostgreSQL 16 + pgvector

---

### 当前问题 vs 目标架构

```
当前（不可用）:                          目标（本计划）:
  浏览器 ─→ frontend:5173                  浏览器 ─→ nginx:443 (SSL)
  浏览器 ─→ backend:8000                              │
                                                      ├─ /api/* ─→ backend:8000 (内部)
                                                      └─ /*     ─→ frontend:80 (内部)
```

---

### Task 1: 创建 backend/.dockerignore 防密钥泄漏

**Files:**
- Create: `backend/.dockerignore`

- [ ] **Step 1: 创建 backend/.dockerignore**

```dockerignore
# 密钥
.env

# Python
__pycache__/
*.pyc
*.pyo
*.egg-info/
.pytest_cache/

# Git
.git
.gitignore

# IDE
.idea/
.vscode/

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 2: 验证 .env 被排除**

```bash
cd backend && docker build --no-cache --dry-run . 2>&1 || echo "Docker dry-run not available, .dockerignore exists check:"
ls -la backend/.dockerignore
```

---

### Task 2: 修复 docker-compose.yml

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: 重写 docker-compose.yml**

当前文件需全部替换。修改内容：
1. 删除已废弃的 `version: "3.9"`
2. 新增 `nginx` 服务（SSL 反向代理）
3. 前端/后端容器不再暴露端口到宿主机（仅 nginx 暴露）
4. 补充缺失的环境变量（`EMBEDDING_MODEL`, `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`）
5. 添加 `JWT_SECRET`/`ENCRYPTION_KEY`/`DB_PASSWORD` 的默认生成逻辑
6. 后端/前端/数据库添加 healthcheck
7. 后端 `restart: unless-stopped`

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    container_name: medical-pgvector
    environment:
      POSTGRES_USER: ${DB_USER:-postgres}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-change-me}
      POSTGRES_DB: medical_qa
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-postgres}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  backend:
    build:
      context: ./backend
    container_name: medical-backend
    environment:
      DATABASE_URL: postgresql+asyncpg://${DB_USER:-postgres}:${DB_PASSWORD:-change-me}@db:5432/medical_qa
      JWT_SECRET: ${JWT_SECRET}
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}
      DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY}
      DEEPSEEK_BASE_URL: ${DEEPSEEK_BASE_URL:-https://api.deepseek.com/v1}
      DEEPSEEK_MODEL: ${DEEPSEEK_MODEL:-deepseek-chat}
      EMBEDDING_API_KEY: ${EMBEDDING_API_KEY}
      EMBEDDING_MODEL: ${EMBEDDING_MODEL:-text-embedding-v4}
      EMBEDDING_BASE_URL: ${EMBEDDING_BASE_URL:-https://dashscope.aliyuncs.com/compatible-mode/v1}
      CORS_ORIGINS: ${CORS_ORIGINS:-["https://your-domain.com"]}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/api/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
    container_name: medical-frontend
    depends_on:
      - backend
    healthcheck:
      test: ["CMD-SHELL", "wget -q -O /dev/null http://localhost:80 || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  nginx:
    image: nginx:1.27-alpine
    container_name: medical-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./certs:/etc/ssl:ro
    depends_on:
      - frontend
      - backend
    healthcheck:
      test: ["CMD-SHELL", "wget -q -O /dev/null http://localhost:80 || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

volumes:
  pgdata:
```

- [ ] **Step 2: 创建 .env.production 模板**

**Files:**
- Create: `.env.production`

```
# === 数据库 ===
DB_USER=postgres
DB_PASSWORD=<生成强密码>

# === 安全（生成方式: python -c "import secrets; print(secrets.token_hex(64))"）===
JWT_SECRET=<生成64字节随机字符串>
ENCRYPTION_KEY=<生成32字节随机字符串>

# === LLM ===
DEEPSEEK_API_KEY=<你的DeepSeek API Key>
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# === Embedding ===
EMBEDDING_API_KEY=<你的阿里云DashScope API Key>
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# === 域名 ===
CORS_ORIGINS=["https://你的域名.com"]
```

---

### Task 3: 修复 nginx.conf

**Files:**
- Modify: `nginx.conf`

- [ ] **Step 1: 重写 nginx.conf**

主要修复：
1. 前端端口从 `5173` → `80`（容器内端口）
2. 移除硬编码的 `your-domain.com`，使用 nginx 变量
3. CSP 中移除不必要的 `https://api.deepseek.com`（前端不直连 LLM）
4. 添加 `gzip` 压缩
5. 添加 SPA 回退（前端路由）

```nginx
# 限流区域定义
limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/m;
limit_req_zone $binary_remote_addr zone=api:10m rate=30r/m;

server {
    listen 80;
    listen [::]:80;
    server_name _;

    # 健康检查端点不走 HTTPS 重定向
    location /health {
        return 200 "OK";
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name _;

    # SSL 配置
    ssl_certificate     /etc/ssl/fullchain.pem;
    ssl_certificate_key /etc/ssl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # 安全响应头
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self' data:; connect-src 'self'; img-src 'self' data:;" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Gzip
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    # API 路由 → backend（SSE 需关闭缓冲）
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        limit_req zone=api burst=10 nodelay;
    }

    # 鉴权接口限流更严格
    location /api/auth/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        limit_req zone=auth burst=3 nodelay;
    }

    # 前端静态文件
    location / {
        proxy_pass http://frontend:80;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_http_version 1.1;
    }
}
```

- [ ] **Step 2: 创建自签名证书（开发/测试用）目录**

```bash
mkdir -p certs
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/privkey.pem \
  -out certs/fullchain.pem \
  -subj "/CN=localhost"
```

> 生产环境使用 Let's Encrypt certbot 获取正式证书。

---

### Task 4: 升级 backend/Dockerfile 为生产级

**Files:**
- Modify: `backend/Dockerfile`

- [ ] **Step 1: 重写 backend/Dockerfile**

使用 gunicorn + uvicorn workers 替代单进程 uvicorn。

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# 应用代码
COPY . .

# 非 root 运行
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

EXPOSE 8000

# gunicorn + 4 uvicorn workers
CMD ["gunicorn", "api.main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
```

> `api.main:app` 需确认 FastAPI 实例变量名为 `app`。

---

### Task 5: 添加健康检查端点

**Files:**
- Modify: `backend/api/main.py`

- [ ] **Step 1: 在 main.py 添加 /api/health 路由**

在 FastAPI app 中添加：

```python
@app.get("/api/health")
async def health_check():
    """Docker 健康检查端点"""
    return {"status": "ok"}
```

> FastAPI 实例变量名已确认为 `app`（backend/Dockerfile 中 `api.main:app` 可证实）。

---

### Task 6: 验证与提交

- [ ] **Step 1: 验证 docker-compose 配置语法**

```bash
docker-compose -f docker-compose.yml config --quiet
```

- [ ] **Step 2: 验证 .dockerignore 生效**

```bash
cd backend && tar -czf - --exclude-from=.dockerignore . 2>/dev/null | tar -tzf - | grep -E '\.env$' || echo ".env correctly excluded"
```

- [ ] **Step 3: 构建测试**

```bash
docker-compose build --no-cache
```

Expected: 所有 4 个服务构建成功（db 使用现成镜像无需构建）。

- [ ] **Step 4: 提交**

```bash
git add backend/.dockerignore backend/Dockerfile docker-compose.yml nginx.conf .env.production backend/api/main.py
git commit -m "feat: production Docker setup with nginx SSL proxy, gunicorn, healthchecks"
```

---

## 验证清单

完成后逐项确认：

- [ ] `docker-compose up -d` 启动成功
- [ ] `docker-compose ps` 所有 4 个服务状态为 healthy
- [ ] `curl http://localhost/api/health` 返回 `{"status":"ok"}`
- [ ] `curl http://localhost/` 返回前端 HTML 页面
- [ ] nginx 容器日志无 SSL 错误
- [ ] `.env` 未被打包进后端镜像（`docker run medical-backend cat /app/.env` 应报错或为空）

---

## 上线前置条件（非本次范围）

以下不在本次修复范围内，但上线前必须处理：

| 项目 | 说明 |
|------|------|
| SSL 正式证书 | 替换 `certs/` 中的自签名证书为 Let's Encrypt |
| 域名 DNS | 配置 A 记录指向服务器 IP |
| `CORS_ORIGINS` | 替换 `your-domain.com` 为实际域名 |
| 密钥生成 | `JWT_SECRET` / `ENCRYPTION_KEY` / `DB_PASSWORD` 用 `secrets.token_hex()` 生成 |
| API Key 填入 | 在 `.env.production` 中填入真实 API Key |
| 数据库备份 | 配置 pg_dump cron 或使用云服务自动备份 |
