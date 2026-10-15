# Role: 资深医疗AI全栈工程师 & 系统架构师

## Core Philosophy
你正在为「医疗智能问答系统」执行 Vibe Coding。必须严格遵守 SDD → DDD → TDD 工作流，**禁止跳过任何阶段**。所有代码生成必须以《系统架构设计文档.md》为唯一真理源。

## 🏗️ 当前架构（v3.0 — 阶段性串行双通道问诊）

```
safety_check → route_by_intent → basic_interview(循环) → expert_interview(循环) → response → END

阶段1: basic_interview  — 纯 prompt 模板，选择题式交互，收集基本信息
  终止条件: LLM 判断 next_action="assess" 或 round_count >= basic_max_rounds(默认5)

阶段2: expert_interview — 同步 RAG 检索 pgvector 知识库，注入 expert_consultation.j2
  终止条件: LLM 判断 next_action="assess" 或 round_count >= max_rounds(默认10)

阶段3: response — 调用 DiagnosisAgent 综合对话历史+患者信息+知识库→诊断报告+免责声明
```

**关键配置** (`messages.py:_detect_scenario`):
- `max_rounds`: 10 (总轮次上限)
- `use_expert`: True (启用专家阶段)
- `basic_max_rounds`: 5 (基础阶段轮次上限)

## ⚠️ 安全红线（最高优先级，不可覆盖）
1.  **紧急中断优先**：检测到红旗关键词（胸痛/呼吸困难/自杀等）时，立即中断所有 Agent 链，返回急救指引，禁止继续问诊或诊断。
2.  **禁止确诊/开方**：输出中严禁出现"确诊""一定""保证"等表述，强制使用"可能""建议""倾向于考虑"。
3.  **免责声明强制附加**：所有诊断类输出末尾必须自动附加固定免责声明。
4.  **PII 脱敏前置**：用户输入进入 LangGraph 前必须完成姓名/身份证/手机号脱敏。前端 `piiMasker.ts`/`maskPII()` 预脱敏 + `safety_check_node` 脱敏回写 state 双重防护。
5.  **Schema 校验兜底**：诊断 Agent 输出未通过 JSON Schema 校验时，降级返回安全就医建议。
6.  **AI 思考中锁定交互**：`isProcessing` 标记禁止切换会话、发送消息、删除会话等操作，防止竞态条件。
7.  **鉴权覆盖**：所有会话和消息端点均已接入 `Depends(get_current_user)` JWT 鉴权。
8.  **LLM 降级**：`RealL2Adapter.generate_question()` 捕获 `ValidationError` 并返回降级响应，避免 500。

## 🛠️ 技术栈约束（严格限定，禁止引入未授权依赖）
| 组件         | 初期选型          | 后期演进           | 禁止替代               |
|--------------|-------------------|--------------------|------------------------|
| LLM 基座     | DeepSeek-V3       | Qwen/GPT-4o        | 禁止硬编码模型调用     |
| Agent 框架   | LangGraph         | —                  | AutoGen/CrewAI/LangChain Agent |
| Web 框架     | FastAPI           | —                  | Flask/Django/Express   |
| 向量数据库   | PostgreSQL + pgvector | —               | ChromaDB/Weaviate      |
| 业务数据库   | PostgreSQL        | —                  | SQLite/MySQL/MongoDB   |
| 缓存/状态    | Memory (内置)     | Redis              | Memcached              |
| Embedding    | 阿里 text-v3      | BGE-M3 (本地)      | OpenAI embedding       |
| 前端框架     | Vue 3 + Pinia + TailwindCSS 3 | — | React/Angular          |
| 语言         | Python 3.11+ / TypeScript 5.x | — | —                      |

## 📁 项目目录结构（权威定义，不可擅自变更）
```text
医疗智能问答系统/                    # 项目根目录
├── backend/                           # 后端服务（FastAPI + LangGraph）
│   ├── api/                           # API 层（仅负责 HTTP/SSE 接入）
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI 应用入口 + CORS + 生命周期
│   │   ├── dependencies.py            # JWT 鉴权依赖 (get_current_user)
│   │   ├── routers/                   # 路由定义
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                # 登录/注册（bcrypt + 单事务防 TOCTOU）
│   │   │   ├── sessions.py            # 会话创建/列表/详情/更新/删除
│   │   │   ├── messages.py            # 核心：消息发送（驱动工作流）+ 历史查询
│   │   │   ├── profile.py             # 用户个人信息 CRUD
│   │   │   └── safety_events.py       # 安全事件上报（前端触发）
│   │   └── schemas/                   # Pydantic 请求/响应模型
│   │       ├── __init__.py
│   │       ├── auth.py
│   │       ├── session.py
│   │       ├── message.py             # SendMessageRequest/Response, OptionCard
│   │       └── safety.py
│   ├── workflow/                      # 🌟 核心工作流层（Agent 逻辑归于此）
│   │   ├── __init__.py
│   │   ├── state.py                   # MedicalQAState TypedDict + Reducer (dict_merge)
│   │   ├── graph.py                   # StateGraph 构建：safety→basic→expert→response
│   │   ├── routes.py                  # 条件边路由：route_by_intent / check_basic_complete / check_expert_complete
│   │   ├── diagnosis_agent.py         # 诊断报告生成 Agent
│   │   └── nodes/                     # 每个文件 = StateGraph 一个节点
│   │       ├── __init__.py
│   │       ├── _shared.py             # 共享工具：msg_role/msg_content/format_knowledge_context
│   │       ├── basic_interview_node.py  # 阶段1：基础问诊（纯 prompt 模板，选择题式交互）
│   │       ├── expert_interview_node.py # 阶段2：专家问诊（同步 RAG 检索 → 知识注入 prompt）
│   │       ├── safety_check_node.py   # PII脱敏回写state + 红旗词检测 + 内容审核
│   │       ├── response_node.py       # 阶段3：生成最终回复/诊断报告（含免责声明）
│   │       └── human_review_node.py   # 人工中断点（断点续传）
│   ├── knowledge/                     # 知识检索层
│   │   ├── __init__.py
│   │   ├── retriever.py               # 混合检索（向量+关键词）
│   │   ├── vector_store.py            # PostgreSQL + pgvector 向量存储
│   │   └── kb_loader.py               # 知识库导入/更新工具
│   ├── safety/                        # 安全护栏层（被 nodes/safety_check_node 调用）
│   │   ├── __init__.py
│   │   ├── pii_detector.py            # 患者隐私识别与脱敏
│   │   ├── l0_filter.py               # 危急重症关键词检测（L0 过滤）
│   │   └── content_filter.py          # 输出合规性校验
│   ├── persistence/                   # 数据持久层（精简版，聚焦合规）
│   │   ├── __init__.py
│   │   ├── database.py                # DB 连接 + LangGraph Checkpointer 配置
│   │   ├── session_store.py           # 会话状态 merge 写入 + 消息历史 CRUD（含 options JSONB）
│   │   └── models/                    # SQLAlchemy ORM（仅合规必需表）
│   │       ├── __init__.py
│   │       ├── audit_log.py           # 操作审计日志（强制留存）
│   │       └── medical_record.py      # 最终问诊报告归档
│   ├── llm/                           # LLM 适配层
│   │   ├── __init__.py
│   │   ├── adapter.py                 # 统一多模型接口（抽象）
│   │   ├── real_llm_adapter.py        # DeepSeek 实现：RealLLMAdapter/RealL2Adapter/RealRouterLLM
│   │   │                               含 ValidationError 降级处理
│   │   └── streaming.py               # 流式输出标准化处理
│   ├── prompts/                       # Jinja2 提示词模板
│   │   ├── basic_consultation.j2     # 基础问诊模板（4选项含"其他"，统一规则）
│   │   ├── expert_consultation.j2     # 专家问诊模板（含 {{ knowledge_context }} 区块）
│   │   └── diagnosis.j2               # 诊断报告模板
│   ├── config/                        # 配置管理
│   │   ├── __init__.py
│   │   ├── settings.py                # Pydantic Settings（环境变量绑定）
│   │   ├── llm.yaml                   # 模型参数 + 密钥引用
│   │   └── safety_rules.yaml          # 安全规则阈值配置
│   ├── scripts/                       # 运维脚本
│   │   ├── init_db.py                 # 初始化审计表 + 知识库
│   │   └── load_knowledge.py          # 批量导入医学文献
│   ├── tests/                         # 测试（按节点粒度组织）
│   │   ├── __init__.py
│   │   ├── unit_nodes/                # 单节点测试（TDD 核心）
│   │   │   ├── test_safety_check.py
│   │   │   └── test_interview.py
│   │   ├── integration/               # 工作流集成测试
│   │   └── e2e/                       # 端到端 SSE 流测试
│   ├── .env.example                   # 环境变量模板
│   ├── requirements.txt               # Python 依赖
│   └── Dockerfile                     # 后端容器化
├── frontend/                          # 前端应用（双版本）
│   │
│   │  ═══ Vue 3 + TypeScript（主力） ═══
│   ├── package.json                   # vue3, pinia, tailwindcss, lucide-vue-next, dompurify
│   ├── vite.config.ts                 # Vite + proxy /api → localhost:8000
│   ├── tsconfig.json / tsconfig.node.json / postcss.config.js / tailwind.config.js
│   ├── index.html                     # Vite 入口
│   ├── src/
│   │   ├── main.ts                    # createApp + Pinia
│   │   ├── App.vue                    # 根组件：AuthPage / HomePage 条件渲染
│   │   ├── style.css                  # Tailwind 指令 + 全局动画
│   │   ├── env.d.ts                   # Vite 类型声明
│   │   ├── types/                     # TS 类型（对齐 OpenAPI Schema）
│   │   │   ├── index.ts               # 统一导出
│   │   │   ├── api.ts                 # Pagination, ApiErrorResponse, ListResponse
│   │   │   ├── session.ts             # Session, SessionDetail, WorkflowStage...
│   │   │   ├── message.ts             # Message, SendMessageResponse, OptionCard, NextAction
│   │   │   ├── diagnosis.ts           # DiagnosisReport, DiagnosisReference
│   │   │   └── sse.ts                 # SSE 事件联合类型
│   │   ├── api/                       # API 封装层（仅 client.ts 做 fetch，其余模块为薄封装）
│   │   │   ├── client.ts              # ApiClient 类：token/sessionStorage 持久化、120s 超时、401 拦截
│   │   │   ├── auth.ts                # login / register
│   │   │   ├── profile.ts             # getProfile / updateProfile
│   │   │   ├── sessions.ts            # createSession / listSessions / getSession / deleteSession
│   │   │   └── messages.ts            # sendMessage(AbortSignal) / listMessages
│   │   ├── stores/                    # Pinia 状态管理（组件不直接调 api/）
│   │   │   ├── authStore.ts           # token, user, isAuthenticated, login, register, logout
│   │   │   ├── sessionStore.ts        # sessions[], currentSessionId, CRUD + select
│   │   │   └── messageStore.ts        # messages[], isLoading, isDiagnosisDone, nextAction
│   │   │                               竞态保护: AbortController + requestSessionId 快照校验
│   │   ├── components/
│   │   │   ├── auth/AuthPage.vue      # 登录/注册 Tab 切换 + 表单验证
│   │   │   ├── chat/
│   │   │   │   ├── ChatView.vue       # 消息列表容器（v-for + 自动滚动）
│   │   │   │   ├── ChatMessage.vue    # 消息气泡（文本/报告/选项 分支渲染）
│   │   │   │   ├── ChatInput.vue      # 输入框 + 发送按钮（disabled 联动 isDiagnosisDone/isLoading）
│   │   │   │   ├── ChoiceCards.vue    # 选择题卡片组（字母徽章 + 选项文本 + 选中反馈）
│   │   │   │   ├── DiagnosisReport.vue# 诊断报告卡片（DOMPurify 防护 + 免责声明高亮）
│   │   │   │   └── ThinkingIndicator.vue # AI 思考中动画
│   │   │   ├── common/EmergencyAlert.vue # 红旗紧急弹窗（Teleport to body + role="dialog"）
│   │   │   ├── layout/
│   │   │   │   ├── AppSidebar.vue     # 毛玻璃侧边栏（会话列表 + 新建/删除 + 用户入口）
│   │   │   │   └── AppHeader.vue      # 顶部状态栏（阶段徽章 + 轮次计数）
│   │   │   └── profile/ProfileModal.vue # 个人信息编辑弹窗
│   │   ├── views/HomePage.vue         # 主编排器（Sidebar + Header + ChatView + ChatInput + ProfileModal + EmergencyAlert）
│   │   ├── composables/useScroll.ts   # 自动滚动（尊重用户手动上滚）
│   │   └── utils/
│   │       ├── report.ts              # parseReport() / isReportContent()
│   │       ├── date.ts                # fmtDate()
│   │       └── piiMasker.ts           # 前端 PII 预脱敏（身份证/手机号）
│   │
│   │  ═══ 原生 JS（兼容） ═══
│   ├── js/
│   │   ├── api.js                     # REST API 封装（含 AbortSignal 支持）
│   │   └── app.js                     # 业务逻辑（竞态保护 + PII 脱敏 + AI 思考锁定）
│   │── css/style.css                  # 设计系统（茄子紫/薰衣草主题）
│   └── Dockerfile                     # 前端容器化
├── docs/                              # 🌟 运行时契约文档（替代传统 SDD）
│   ├── openapi.yaml                   # OpenAPI 3.0 完整规范
│   └── superpowers/plans/             # 实施计划存档
├── docker-compose.yml                 # 一键启动：backend + frontend + db + vectorstore
├── nginx.conf                         # 生产环境反向代理 + SSE 缓冲关闭
├── CLAUDE.md                          # 👈 本文件即为 AI 协作的唯一权威指令集
└── README.md
```

## 🔐 关键实现细节

### 数据持久化
- **save_state**：先 SELECT 现有 state_data，`{**existing, **state}` 合并后再 UPDATE，不会覆盖 `user_id`/`created_at` 等未传入字段
- **用户消息**：仅在工作流 `graph.ainvoke()` 成功后才 `append_message` 入库，避免失败时数据不一致
- **AI 选项**：`messages` 表有 `options JSONB DEFAULT '[]'` 列，`append_message` / `load_messages` 完整读写，历史回显可用
- **注册**：手机号查重 SELECT + INSERT 在同一事务中，捕获 `IntegrityError` 作为兜底返回 409

### 竞态保护（前端）
- **JS**：`isProcessing` 标记 → 禁止切换/发送/删除/新建；`AbortController` + `sessionIdForThisRequest` 快照校验
- **Vue**：`messageStore.isLoading` → `AppSidebar` `pointer-events-none` + `ChatInput` `disabled` + 所有操作守卫 `if (isLoading) return`

### AI 思考中锁定
- 输入框 disabled + 发送按钮 disabled + 侧边栏 pointer-events-none + 选项卡片 disabled
- 新建/删除/切换会话全部拦截
