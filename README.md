# AI智能问诊

基于 LLM + LangGraph 的 AI 健康咨询平台，采用**阶段性串行问诊架构**（安全检测 → 基础问诊 → 专家问诊 → 诊断报告）。

## 快速启动（Docker，推荐）

**macOS / Linux：**
```bash
mkdir -p certs
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/privkey.pem -out certs/fullchain.pem \
  -subj "/CN=localhost"

cp backend/.env.example backend/.env
# 编辑 backend/.env，填入 API Key

docker compose -p medical-qa --env-file backend/.env up -d --build
```

**Windows（PowerShell）：**
```powershell
# 1. 生成 SSL 证书（如果 certs 目录已存在可跳过 mkdir）
mkdir -Force certs
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout certs/privkey.pem -out certs/fullchain.pem -subj "//CN=localhost"

# 2. 配置环境变量
Copy-Item backend/.env.example backend/.env
# 编辑 backend/.env，填入 API Key

# 3. 一键启动
docker compose -p medical-qa --env-file backend/.env up -d --build
```

> 如果 PowerShell 中 `openssl` 不可用，可在 Git Bash 中执行第 1 步，或直接使用已生成的 `certs/` 目录。

浏览器打开 `https://localhost`（自签名证书，点击"继续访问"）。

## 本地开发启动

```bash
# 1. 启动 PostgreSQL + pgvector
docker run -d --name medical-pgvector \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=root \
  -e POSTGRES_DB=medical_qa \
  -p 5433:5432 \
  pgvector/pgvector:pg16

# 2. 启动后端
cd backend
pip install -r requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# 3. 启动前端
cd frontend
npm install
npm run dev        # http://localhost:5173，自动代理 /api → localhost:8000
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | — |
| `DEEPSEEK_MODEL` | LLM 模型 | `deepseek-chat` |
| `DEEPSEEK_BASE_URL` | LLM API 地址 | `https://api.deepseek.com/v1` |
| `EMBEDDING_API_KEY` | 阿里云 DashScope API 密钥 | — |
| `EMBEDDING_MODEL` | Embedding 模型 | `text-embedding-v4` |
| `EMBEDDING_BASE_URL` | Embedding API 地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `DATABASE_URL` | PostgreSQL 连接串 | `postgresql+asyncpg://...` |
| `JWT_SECRET` | JWT 签名密钥 | — |
| `ENCRYPTION_KEY` | 加密密钥 | — |
| `CORS_ORIGINS` | 允许的跨域来源 | `["http://localhost:5173"]` |
| `LOG_LEVEL` | 日志级别 | `INFO` |

> Embedding 支持 API 优先 + 本地 BGE-M3 降级：设置了 `EMBEDDING_API_KEY` 则调云端 API，API 失败或无密钥则自动使用本地模型。

## 架构概览

```
浏览器 → nginx:443 (SSL) → /api/* → backend:8000 (gunicorn)
                          → /*     → frontend:80  (静态文件)

工作流:
safety_check → basic_interview(循环) → expert_interview(循环) → response → END
                    │                          │
               纯 prompt 模板              RAG 知识增强
               (收集基本信息)              (知识库注入追问)
```

- **安全检测**：PII 脱敏（身份证/手机号）→ 危急重症关键词过滤 → 内容合规审核
- **基础问诊**：Jinja2 提示词模板驱动，选择题式交互，快速收集主诉、症状、病史
- **专家问诊**：同步检索 pgvector 知识库，将医学知识注入 prompt 生成鉴别诊断级别的追问
- **诊断报告**：综合对话历史 + 患者信息 + 知识库参考，生成安全合规的分析报告（含强制免责声明）

## 问诊阶段配置

在 `backend/api/routers/messages.py` 的 `_detect_scenario()` 中调整：

```python
"max_rounds": 10,          # 总轮次上限
"use_expert": True,        # 是否启用专家问诊阶段
"basic_max_rounds": 5,     # 基础阶段轮次上限
```

- 基础阶段：LLM 判断信息足够（`next_action="assess"`）或达到 `basic_max_rounds` → 结束
- 专家阶段：LLM 判断信息足够或达到 `max_rounds` → 进入诊断报告
- 诊断完成后：前端自动禁用输入，提示"诊断已完成，可新建会话继续"

## 鉴权

所有会话和消息端点均已接入 JWT 鉴权（`Depends(get_current_user)`）。未登录请求返回 401。

## 知识库导入

```bash
cd backend
python scripts/load_knowledge.py ../docs/医学参考文献.json
```

## 安全特性

| 层次 | 措施 |
|------|------|
| 前端输入 | `piiMasker.ts` / `maskPII()` 预脱敏（身份证/手机号） |
| 后端入口 | `safety_check_node` L0 过滤 + PII 脱敏回写 state |
| 工作流保护 | 紧急中断优先、LLM JSON 解析失败降级、Schema 校验兜底 |
| API 鉴权 | 所有会话/消息端点 JWT 认证 |
| 前端渲染 | DOMPurify 防护 v-html XSS |
| 数据传输 | TLS 1.2+ 加密（nginx SSL 终端） |
| 安全响应头 | CSP / X-Frame-Options / X-XSS-Protection / HSTS |
| 限流 | nginx 层 auth 5r/m + api 30r/m |
| 数据完整性 | save_state 原子 merge 写入、用户消息仅在工作流成功后持久化 |
| 并发安全 | 注册 TOCTOU 单事务修复、前端 AbortController + 会话 ID 校验 |
| Docker 安全 | `.dockerignore` 排除密钥、非 root 用户运行 |

## 技术栈

| 组件 | 选型 |
|------|------|
| LLM | DeepSeek（可切换） |
| Agent 框架 | LangGraph |
| Web 框架 | FastAPI + gunicorn |
| 数据库 | PostgreSQL + pgvector |
| 前端 | Vue 3 + Pinia + TailwindCSS 3 |
| 反向代理 | nginx（SSL + 限流 + Gzip） |
| 部署 | Docker Compose |

## 文档

- [技术要点与设计问答](docs/技术要点.md) —— 架构细节、安全护栏、检索管线、设计问答（实现细节速查）

## 项目结构

```
医疗智能问答系统/
├── backend/
│   ├── api/                          # FastAPI 路由 + Pydantic Schema
│   │   ├── routers/   (auth / sessions / messages / profile / safety_events)
│   │   ├── schemas/   (Pydantic 请求/响应模型)
│   │   └── dependencies.py
│   ├── workflow/                     # LangGraph 工作流
│   │   ├── nodes/     (safety_check / basic_interview / expert_interview / response / human_review)
│   │   ├── state.py / graph.py / routes.py
│   │   └── diagnosis_agent.py
│   ├── knowledge/                    # pgvector + BGE-M3 混合检索
│   ├── safety/                       # pii_detector / l0_filter / content_filter
│   ├── llm/                          # DeepSeek 适配
│   ├── persistence/                  # session_store / database / models
│   ├── prompts/                      # Jinja2 模板
│   └── config/                       # settings.py
├── frontend/
│   └── src/
│       ├── api/       (client / auth / messages / sessions / profile)
│       ├── stores/    (auth / session / message)
│       ├── components/ (auth / chat / common / layout / profile)
│       ├── views/     (HomePage.vue)
│       ├── composables/ (useScroll.ts)
│       └── utils/     (report / date / piiMasker / validate)
├── certs/                            # SSL 证书
├── docker-compose.yml                # 生产部署编排
├── nginx.conf                        # 反向代理 + SSL 配置
├── .env.production                   # 生产环境变量模板
├── CLAUDE.md
└── README.md
```
