# 医疗智能问答系统 — SDD 第二阶段：PostgreSQL 数据库 Schema 设计

> **版本：** v1.0
> **阶段：** SDD Phase 2 — 数据库设计
> **前置文档：** 系统架构设计文档 §9.4、SDD-01 领域建模
> **目标PG版本：** PostgreSQL 16+
> **日期：** 2026-06-19

---

## 目录

1. [设计总览](#1-设计总览)
2. [实体关系图（Mermaid ERD）](#2-实体关系图mermaid-erd)
3. [完整DDL语句](#3-完整ddl语句)
   - [3.0 扩展与配置](#30-扩展与配置)
   - [3.1 sessions — 会话表](#31-sessions--会话表)
   - [3.2 messages — 对话消息表](#32-messages--对话消息表)
   - [3.3 medical_records — 结构化病历表](#33-medical_records--结构化病历表)
   - [3.4 diagnosis_results — 诊断结果表](#34-diagnosis_results--诊断结果表)
   - [3.5 audit_logs — 审计日志表](#35-audit_logs--审计日志表)
   - [3.6 knowledge_entries — 知识库元数据表](#36-knowledge_entries--知识库元数据表)
   - [3.7 diagnosis_citations — 诊断引用关联表](#37-diagnosis_citations--诊断引用关联表)
   - [3.8 safety_events — 安全事件表](#38-safety_events--安全事件表)
4. [索引策略详解](#4-索引策略详解)
5. [触发器与自动化](#5-触发器与自动化)
6. [安全设计](#6-安全设计)
7. [设计决策说明](#7-设计决策说明)

---

## 1. 设计总览

### 1.1 表清单

| # | 表名 | 行级预估 | 增长模型 | 分区策略 |
|---|------|---------|---------|---------|
| 1 | `sessions` | 10K→1M | 线性 | 无需（按status索引） |
| 2 | `messages` | 100K→10M | 线性（~10条/会话） | 可选：按created_at月分区 |
| 3 | `medical_records` | 10K→1M | 线性（1:1 会话） | 无需 |
| 4 | `diagnosis_results` | 5K→500K | 线性 | 无需 |
| 5 | `audit_logs` | 500K→50M | **高速**（~5条/轮次 × N轮） | **强烈建议：按月分区** |
| 6 | `knowledge_entries` | 1K→100K | 逐步（预入库+增量） | 无需 |
| 7 | `diagnosis_citations` | 10K→1M | 线性（N:M 关联） | 无需 |
| 8 | `safety_events` | 1K→100K | 低频 | 无需 |

### 1.2 Schema 命名空间

```sql
-- 统一使用 public schema
-- 命名规范：
--   表名: snake_case 复数 (sessions, messages, ...)
--   主键: id (UUID)
--   外键: <referenced_table>_id (singular)
--   索引: idx_<table>_<column(s)>
--   唯一约束: uq_<table>_<column(s)>
--   检查约束: ck_<table>_<rule>
--   触发器: trg_<table>_<action>
```

### 1.3 扩展依赖

| 扩展 | 用途 | 版本要求 |
|------|------|---------|
| `pgcrypto` | UUID生成、加密函数 | PG 16 内置 |
| `pgvector` | 向量存储与相似度检索 | ≥ 0.7.0 |
| `pg_trgm` | 文本模糊搜索（知识库标签/标题） | PG 16 内置 |

---

## 2. 实体关系图（Mermaid ERD）

```mermaid
erDiagram
    sessions ||--o{ messages : "has"
    sessions ||--|| medical_records : "documents"
    sessions ||--|| diagnosis_results : "produces"
    sessions ||--o{ audit_logs : "traced_by"
    sessions ||--o{ safety_events : "triggers"

    medical_records ||--|| diagnosis_results : "derives"
    diagnosis_results ||--o{ diagnosis_citations : "referenced_by"
    knowledge_entries ||--o{ diagnosis_citations : "cited_in"

    sessions {
        UUID id PK "gen_random_uuid()"
        VARCHAR user_id "🔴PII:哈希匿名化"
        VARCHAR status "active|paused|completed|emergency_terminated|closed_timeout"
        VARCHAR intent "diagnosis|question|emergency|greeting|status"
        VARCHAR current_stage "init|collect|diagnose|done|emergency"
        BOOLEAN red_flag_raised "红旗触发标记"
        INTEGER round_count "当前问诊轮次"
        INTEGER max_rounds "最大轮次上限 [DEFAULT 5]"
        VARCHAR close_reason "completed|emergency|timeout|user_aborted"
        TIMESTAMP closed_at "关闭时间"
        JSONB metadata "扩展元数据"
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    messages {
        UUID id PK
        UUID session_id FK
        INTEGER round_number "所属轮次"
        VARCHAR role "user|assistant|system"
        TEXT content "🔴PII:已脱敏文本"
        BYTEA content_raw_encrypted "🔴PII:AES-256-GCM加密原始输入"
        VARCHAR content_type "text|question|diagnosis_report|emergency_guide|status_report"
        VARCHAR agent_source "master|interview|search|diagnosis|system"
        INTEGER token_count
        TIMESTAMP created_at
    }

    medical_records {
        UUID id PK
        UUID session_id FK_UNIQUE
        INTEGER version "每轮更新+1"
        JSONB record_data "结构化病历 [📋含REQUIRED_CORE字段]"
        VARCHAR completion_level "partial|core_complete|full"
        TEXT_ARRAY missing_core_fields "未采集核心字段列表"
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    diagnosis_results {
        UUID id PK "🔒IMMUTABLE"
        UUID session_id FK_UNIQUE
        UUID medical_record_id FK
        JSONB result_data "诊断报告完整JSON [Schema校验后存储]"
        VARCHAR schema_version "Schema版本 [DEFAULT '1.0']"
        BOOLEAN schema_validated "是否通过校验"
        BOOLEAN fallback_triggered "是否降级兜底"
        INTEGER citation_count "引用知识条目数"
        TIMESTAMP created_at "🔒IMMUTABLE"
    }

    knowledge_entries {
        UUID id PK
        VARCHAR title "标题"
        VARCHAR source "来源机构"
        VARCHAR source_type "guideline|consensus|textbook|review|case_report"
        INTEGER publish_year "发布年份"
        VARCHAR version "指南版本号"
        TEXT content "知识正文"
        VARCHAR content_hash "SHA256 [UNIQUE:去重]"
        VECTOR embedding "pgvector向量 [1536维]"
        FLOAT authority_score "权威性评分 [0.0-1.0]"
        FLOAT freshness_score "时效性评分 [自动计算]"
        TEXT_ARRAY tags "标签"
        BOOLEAN is_active "可用状态"
        VARCHAR reviewed_by "审核人"
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    diagnosis_citations {
        UUID id PK
        UUID diagnosis_result_id FK
        UUID knowledge_entry_id FK
        FLOAT relevance_score "相关度评分"
        VARCHAR evidence_role "supporting|contradicting|background"
        TEXT excerpt "引用片段摘要"
        TIMESTAMP created_at
    }

    audit_logs {
        UUID id PK "🔒IMMUTABLE"
        UUID session_id FK
        VARCHAR agent_name "master|interview|search|diagnosis"
        VARCHAR event_type "10种事件类型"
        JSONB input_summary "🔴PII:已脱敏输入摘要"
        JSONB output_summary "输出摘要"
        JSONB token_usage "{prompt_tokens,completion_tokens,total_tokens}"
        INTEGER latency_ms "执行耗时毫秒"
        VARCHAR model_name "LLM模型名"
        BOOLEAN red_flag_triggered
        JSONB safety_check "{content_filtered,disclaimer_appended,schema_validated}"
        JSONB error_info "异常信息 [NULL=正常]"
        TIMESTAMP created_at "🔒IMMUTABLE"
    }

    safety_events {
        UUID id PK "🔒IMMUTABLE"
        UUID session_id FK
        VARCHAR event_category "red_flag|pii_detected|content_filtered|fallback|schema_rejected"
        VARCHAR severity "info|warning|critical"
        TEXT description "事件描述"
        JSONB context_data "事件上下文(脱敏后)"
        VARCHAR action_taken "采取的响应动作"
        TIMESTAMP created_at "🔒IMMUTABLE"
    }
```

---

## 3. 完整DDL语句

### 3.0 扩展与配置

```sql
-- ============================================================
-- 0. 扩展启用
-- ============================================================

-- 加密函数支持 (AES-256-GCM 加密消息原始内容)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 向量存储与相似度检索 (pgvector (PostgreSQL 扩展)替代方案 / pgvector混合检索)
CREATE EXTENSION IF NOT EXISTS vector;

-- 三元组模糊匹配 (知识库标题/标签全文搜索)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================
-- 0. 自定义类型（领域枚举）
-- ============================================================

-- 会话状态枚举
DO $$ BEGIN
    CREATE TYPE session_status AS ENUM (
        'active',
        'paused',
        'completed',
        'emergency_terminated',
        'closed_timeout'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 会话意图枚举
DO $$ BEGIN
    CREATE TYPE session_intent AS ENUM (
        'diagnosis',
        'question',
        'emergency',
        'greeting',
        'status',
        'follow_up'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 工作流阶段枚举
DO $$ BEGIN
    CREATE TYPE workflow_stage AS ENUM (
        'init',
        'collect',
        'diagnose',
        'done',
        'emergency'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 消息角色枚举
DO $$ BEGIN
    CREATE TYPE message_role AS ENUM (
        'user',
        'assistant',
        'system'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 消息内容类型枚举
DO $$ BEGIN
    CREATE TYPE message_content_type AS ENUM (
        'text',
        'question',
        'diagnosis_report',
        'emergency_guide',
        'status_report'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Agent名称枚举
DO $$ BEGIN
    CREATE TYPE agent_name_enum AS ENUM (
        'master',
        'interview',
        'search',
        'diagnosis',
        'emergency',
        'system'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 审计事件类型枚举
DO $$ BEGIN
    CREATE TYPE audit_event_type AS ENUM (
        'intent_detect',
        'route_decision',
        'question_generate',
        'info_collected',
        'interview_complete',
        'search_execute',
        'search_rerank',
        'diagnosis_generate',
        'safety_intercept',
        'fallback_trigger'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 知识来源类型枚举
DO $$ BEGIN
    CREATE TYPE knowledge_source_type AS ENUM (
        'guideline',
        'consensus',
        'textbook',
        'review',
        'case_report'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 病历完成度枚举
DO $$ BEGIN
    CREATE TYPE completion_level_enum AS ENUM (
        'partial',
        'core_complete',
        'full'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 安全事件分类枚举
DO $$ BEGIN
    CREATE TYPE safety_event_category AS ENUM (
        'red_flag',
        'pii_detected',
        'content_filtered',
        'fallback',
        'schema_rejected'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 安全事件严重度枚举
DO $$ BEGIN
    CREATE TYPE safety_severity AS ENUM (
        'info',
        'warning',
        'critical'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 引用证据角色枚举
DO $$ BEGIN
    CREATE TYPE evidence_role_enum AS ENUM (
        'supporting',
        'contradicting',
        'background'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
```

---

### 3.1 sessions — 会话表

```sql
-- ============================================================
-- 1. sessions — 会话表
-- 职责: 管理单次用户咨询会话的完整生命周期
-- 增长: 线性 (~10K→1M)
-- ============================================================
CREATE TABLE sessions (
    -- 主键
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 用户标识 (🔴PII: 前端已做哈希匿名化处理，此字段存储匿名ID)
    user_id         VARCHAR(255) NOT NULL,

    -- 会话状态
    status          session_status NOT NULL DEFAULT 'active',

    -- 意图与阶段
    intent          session_intent NOT NULL DEFAULT 'greeting',
    current_stage   workflow_stage NOT NULL DEFAULT 'init',

    -- 安全标记
    red_flag_raised BOOLEAN NOT NULL DEFAULT FALSE,

    -- 问诊进度
    round_count     INTEGER NOT NULL DEFAULT 0
                    CONSTRAINT ck_sessions_round_count_positive CHECK (round_count >= 0),
    max_rounds      INTEGER NOT NULL DEFAULT 5
                    CONSTRAINT ck_sessions_max_rounds_range CHECK (max_rounds BETWEEN 1 AND 10),

    -- 关闭信息
    close_reason    VARCHAR(50)  -- completed | emergency | timeout | user_aborted
                    CONSTRAINT ck_sessions_close_reason CHECK (
                        close_reason IS NULL
                        OR close_reason IN ('completed','emergency','timeout','user_aborted')
                    ),
    closed_at       TIMESTAMP,

    -- 扩展元数据
    metadata        JSONB NOT NULL DEFAULT '{}',

    -- 时间戳
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_sessions_user_id        ON sessions(user_id);
CREATE INDEX idx_sessions_status         ON sessions(status) WHERE status IN ('active','paused');
CREATE INDEX idx_sessions_intent         ON sessions(intent);
CREATE INDEX idx_sessions_created_at     ON sessions(created_at);
CREATE INDEX idx_sessions_red_flag       ON sessions(red_flag_raised) WHERE red_flag_raised = TRUE;

-- 注释
COMMENT ON TABLE sessions IS '会话生命周期管理表';
COMMENT ON COLUMN sessions.user_id IS '🔴PII: 前端哈希匿名化后的用户标识，不可逆';
COMMENT ON COLUMN sessions.status IS 'active|paused|completed|emergency_terminated|closed_timeout';
COMMENT ON COLUMN sessions.intent IS 'MasterAgent识别的用户意图';
COMMENT ON COLUMN sessions.current_stage IS 'LangGraph工作流当前阶段';
COMMENT ON COLUMN sessions.red_flag_raised IS '是否触发红旗紧急中断';
COMMENT ON COLUMN sessions.close_reason IS 'completed|emergency|timeout|user_aborted';
COMMENT ON COLUMN sessions.metadata IS '扩展元数据: 客户端UA/来源渠道/自定义标签等';
```

---

### 3.2 messages — 对话消息表

```sql
-- ============================================================
-- 2. messages — 对话消息表
-- 职责: 记录会话中每一轮次的消息
-- 增长: 线性 (~10条/会话, 100K→10M)
-- PII策略: content(脱敏永久), content_raw_encrypted(AES加密,30天清除)
-- ============================================================
CREATE TABLE messages (
    -- 主键
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 所属会话
    session_id          UUID NOT NULL
                        CONSTRAINT fk_messages_session
                        REFERENCES sessions(id) ON DELETE CASCADE,

    -- 消息轮次 (问诊阶段: 1-N; 诊断/紧急: round_number=0)
    round_number        INTEGER NOT NULL DEFAULT 0
                        CONSTRAINT ck_messages_round_nonnegative CHECK (round_number >= 0),

    -- 消息角色
    role                message_role NOT NULL,

    -- 消息内容 (🔴PII: 已通过脱敏引擎处理——姓名→[姓名], 身份证→[身份证号], 手机→[手机号])
    content             TEXT NOT NULL,

    -- 原始消息加密存储 (🔴PII: AES-256-GCM加密, 30天后由定时任务清除)
    content_raw_encrypted BYTEA,

    -- 内容类型
    content_type        message_content_type NOT NULL DEFAULT 'text',

    -- 生成此消息的Agent
    agent_source        agent_name_enum,

    -- Token估算
    token_count         INTEGER,

    -- 时间戳
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_messages_session_id      ON messages(session_id);
CREATE INDEX idx_messages_session_round   ON messages(session_id, round_number);
CREATE INDEX idx_messages_created_at      ON messages(created_at);
CREATE INDEX idx_messages_agent_source    ON messages(agent_source) WHERE agent_source IS NOT NULL;

-- 注释
COMMENT ON TABLE messages IS '对话消息表, 记录会话中每一轮次的用户输入(脱敏后)和系统输出';
COMMENT ON COLUMN messages.content IS '🔴PII: 脱敏后的消息文本。PII字段已替换为占位符';
COMMENT ON COLUMN messages.content_raw_encrypted IS '🔴PII: AES-256-GCM加密的原始消息。用于审计追溯，30天自动清除。NULL=已清除';
COMMENT ON COLUMN messages.round_number IS '问诊轮次编号。非问诊阶段消息为0';
COMMENT ON COLUMN messages.content_type IS 'text|question|diagnosis_report|emergency_guide|status_report';
COMMENT ON COLUMN messages.agent_source IS 'master|interview|search|diagnosis|emergency|system';
```

---

### 3.3 medical_records — 结构化病历表

```sql
-- ============================================================
-- 3. medical_records — 结构化病历表
-- 职责: 存储问诊Agent多轮采集的结构化病历JSONB
-- 增长: 线性 (1:1会话)
-- 核心设计: JSONB record_data + 版本化 + 完成度追踪
-- ============================================================
CREATE TABLE medical_records (
    -- 主键
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 所属会话 (1:1 唯一)
    session_id          UUID NOT NULL UNIQUE
                        CONSTRAINT fk_medical_records_session
                        REFERENCES sessions(id) ON DELETE CASCADE,

    -- 版本号 (每轮问诊更新+1)
    version             INTEGER NOT NULL DEFAULT 1
                        CONSTRAINT ck_medical_records_version_positive CHECK (version >= 1),

    -- ============================================================
    -- 结构化病历 JSONB (📋 核心数据载体)
    -- Schema参考: SDD-01 §2.3 record_data JSONB内部结构
    --
    -- 顶层键:
    --   patient_info:         {age, gender, chief_complaint, complaint_duration,
    --                          complaint_location, severity}
    --   present_illness:      {onset, course, character, aggravating_factors[],
    --                          relieving_factors[]}
    --   accompanying_symptoms: string[]
    --   past_history:         {chronic_diseases[], surgeries[],
    --                          current_medications[]}
    --   allergy_history:      {drug_allergies[], food_allergies[]}
    --   personal_history:     {smoking, alcohol, occupation}
    --   family_history:       string[]
    --   standardized_terms:   {<口语>: <标准术语>, ...}
    --
    -- 📋 REQUIRED_CORE字段 (P0, 决定问诊终止条件):
    --   patient_info.chief_complaint     - 主诉
    --   patient_info.complaint_duration  - 持续时间
    --   patient_info.complaint_location  - 部位
    -- ============================================================
    record_data         JSONB NOT NULL,

    -- 采集完成度
    completion_level    completion_level_enum NOT NULL DEFAULT 'partial',

    -- 未采集的核心字段列表
    missing_core_fields TEXT[] NOT NULL DEFAULT '{}',

    -- 时间戳
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_medical_records_session_id    ON medical_records(session_id);
CREATE INDEX idx_medical_records_completion    ON medical_records(completion_level)
    WHERE completion_level IN ('partial', 'core_complete');
-- GIN索引: JSONB字段内的高频查询路径
CREATE INDEX idx_medical_records_chief_complaint ON medical_records
    USING GIN ((record_data->'patient_info'->>'chief_complaint') gin_trgm_ops);
-- GIN索引: JSONB整体内容 (用于全文检索病历摘要)
CREATE INDEX idx_medical_records_record_data_gin ON medical_records
    USING GIN (record_data jsonb_path_ops);

-- 注释
COMMENT ON TABLE medical_records IS '结构化病历表，问诊Agent多轮采集结果。一个会话仅一份病历，版本号递增';
COMMENT ON COLUMN medical_records.record_data IS '结构化病历JSONB。📋 P0核心字段: chief_complaint/duration/location 决定问诊终止';
COMMENT ON COLUMN medical_records.completion_level IS 'partial=部分采集 | core_complete=核心字段完整 | full=全部字段采集完成';
COMMENT ON COLUMN medical_records.missing_core_fields IS '尚未采集的REQUIRED_CORE字段路径列表，如 {patient_info.chief_complaint}';
```

---

### 3.4 diagnosis_results — 诊断结果表

```sql
-- ============================================================
-- 4. diagnosis_results — 诊断结果表
-- 职责: 存储诊断Agent生成的诊断报告 (🔒 IMMUTABLE)
-- 增长: 线性 (~5K→500K)
-- 核心设计: JSONB result_data + Schema校验标记 + 引用计数
-- ============================================================
CREATE TABLE diagnosis_results (
    -- 主键
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 所属会话 (1:1 唯一)
    session_id          UUID NOT NULL UNIQUE
                        CONSTRAINT fk_diagnosis_results_session
                        REFERENCES sessions(id) ON DELETE CASCADE,

    -- 关联病历
    medical_record_id   UUID NOT NULL
                        CONSTRAINT fk_diagnosis_results_medical_record
                        REFERENCES medical_records(id) ON DELETE RESTRICT,

    -- ============================================================
    -- 诊断报告 JSONB (🔒 IMMUTABLE, Schema校验后写入)
    -- Schema参考: 架构设计文档 §4.5.3
    --
    -- 顶层键:
    --   primary_diagnosis:     {name, probability, rationale, certainty_level}
    --   differential_diagnosis: [{name, probability, key_evidence, exclusion_criteria}]
    --   risk_assessment:       {severity, urgency, warning_signs[]}
    --   recommendations:       [{category, content, priority}]
    --   red_flags:             [{symptom, action}]
    --   references:            [{knowledge_entry_id, title, source, year,
    --                            url, relevance_score}]
    --   disclaimer:            "本内容仅供参考..."
    -- ============================================================
    result_data         JSONB NOT NULL,

    -- Schema版本
    schema_version      VARCHAR(20) NOT NULL DEFAULT '1.0',

    -- Schema校验标记
    schema_validated    BOOLEAN NOT NULL DEFAULT FALSE
                        CONSTRAINT ck_diagnosis_results_validated
                        CHECK (schema_validated = TRUE),  -- 强制必须校验通过

    -- 降级标记
    fallback_triggered  BOOLEAN NOT NULL DEFAULT FALSE,

    -- 引用知识条目数 (冗余计数, 与diagnosis_citations表保持一致)
    citation_count      INTEGER NOT NULL DEFAULT 0
                        CONSTRAINT ck_diagnosis_results_citation_count
                        CHECK (citation_count >= 0),

    -- 生成时间 (🔒 IMMUTABLE: 只有created_at, 无updated_at)
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_diagnosis_results_session_id    ON diagnosis_results(session_id);
CREATE INDEX idx_diagnosis_results_medical_rec   ON diagnosis_results(medical_record_id);
CREATE INDEX idx_diagnosis_results_created_at    ON diagnosis_results(created_at);
-- GIN索引: JSONB全文检索+路径查询
CREATE INDEX idx_diagnosis_results_data_gin       ON diagnosis_results
    USING GIN (result_data jsonb_path_ops);
-- 部分索引: 降级诊断 (用于监控降级率)
CREATE INDEX idx_diagnosis_results_fallback       ON diagnosis_results(fallback_triggered)
    WHERE fallback_triggered = TRUE;

-- 注释
COMMENT ON TABLE diagnosis_results IS '诊断结果表 🔒IMMUTABLE。生成后不可修改，仅追加审计记录';
COMMENT ON COLUMN diagnosis_results.result_data IS '诊断报告完整JSON。必须通过JSON Schema校验后才可写入';
COMMENT ON COLUMN diagnosis_results.schema_validated IS '必须为TRUE。schema_validated=FALSE的行不应存在(约束阻止)';
COMMENT ON COLUMN diagnosis_results.fallback_triggered IS 'Schema校验失败时触发降级，返回安全建议而非诊断报告';
COMMENT ON COLUMN diagnosis_results.citation_count IS '与diagnosis_citations表行数保持一致的冗余计数';
```

---

### 3.5 audit_logs — 审计日志表

```sql
-- ============================================================
-- 5. audit_logs — 审计日志表
-- 职责: 记录每次Agent调用的完整上下文 (🔒 IMMUTABLE)
-- 增长: 高速 (~500K→50M, 建议按月分区)
-- 核心设计: JSONB存储 + 分区策略 + 安全事件关联
-- ============================================================
CREATE TABLE audit_logs (
    -- 主键
    id                  UUID DEFAULT gen_random_uuid(),

    -- 所属会话
    session_id          UUID NOT NULL
                        CONSTRAINT fk_audit_logs_session
                        REFERENCES sessions(id) ON DELETE CASCADE,

    -- Agent信息
    agent_name          agent_name_enum NOT NULL,
    event_type          audit_event_type NOT NULL,

    -- 输入输出 (🔴PII: input_summary中PII字段已脱敏)
    input_summary       JSONB NOT NULL,
    output_summary      JSONB NOT NULL,

    -- Token消耗
    token_usage         JSONB NOT NULL,
    -- token_usage Schema: {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}

    -- 性能指标
    latency_ms          INTEGER NOT NULL
                        CONSTRAINT ck_audit_logs_latency_positive CHECK (latency_ms >= 0),
    model_name          VARCHAR(100) NOT NULL,

    -- 安全标记
    red_flag_triggered  BOOLEAN NOT NULL DEFAULT FALSE,
    safety_check        JSONB NOT NULL DEFAULT '{}',
    -- safety_check Schema: {"content_filtered": bool, "disclaimer_appended": bool, "schema_validated": bool}

    -- 异常信息
    error_info          JSONB,  -- NULL=正常执行

    -- 时间戳 (🔒 IMMUTABLE)
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),

    -- 复合主键: (created_at, id) 支持分区
    PRIMARY KEY (created_at, id)
) PARTITION BY RANGE (created_at);

-- 默认分区 (未匹配到具体分区时兜底)
CREATE TABLE audit_logs_default PARTITION OF audit_logs DEFAULT;

-- 索引 (在默认分区上创建, 后续分区自动继承或手动创建)
CREATE INDEX idx_audit_logs_session_id    ON audit_logs_default(session_id);
CREATE INDEX idx_audit_logs_agent_name    ON audit_logs_default(agent_name);
CREATE INDEX idx_audit_logs_event_type    ON audit_logs_default(event_type);
CREATE INDEX idx_audit_logs_created_at    ON audit_logs_default(created_at);
CREATE INDEX idx_audit_logs_red_flag      ON audit_logs_default(red_flag_triggered)
    WHERE red_flag_triggered = TRUE;
CREATE INDEX idx_audit_logs_session_time  ON audit_logs_default(session_id, created_at);
-- GIN索引: JSONB查询
CREATE INDEX idx_audit_logs_token_gin     ON audit_logs_default USING GIN (token_usage);
CREATE INDEX idx_audit_logs_input_gin     ON audit_logs_default USING GIN (input_summary jsonb_path_ops);

-- 注释
COMMENT ON TABLE audit_logs IS '审计日志表 🔒IMMUTABLE。每次Agent调用的完整审计记录，按月分区';
COMMENT ON COLUMN audit_logs.input_summary IS '🔴PII: 脱敏后的Agent输入摘要。原始PII不可出现在此字段';
COMMENT ON COLUMN audit_logs.token_usage IS 'JSON: {prompt_tokens, completion_tokens, total_tokens}';
COMMENT ON COLUMN audit_logs.safety_check IS 'JSON: {content_filtered, disclaimer_appended, schema_validated}';
COMMENT ON COLUMN audit_logs.error_info IS 'NULL=正常执行。异常时记录error类型/堆栈摘要';
```

---

### 3.6 knowledge_entries — 知识库元数据表

```sql
-- ============================================================
-- 6. knowledge_entries — 知识库元数据表
-- 职责: 存储医学知识条目, 管理pgvector (PostgreSQL 扩展)向量索引关联
-- 增长: 逐步 (~1K→100K)
-- 核心设计: pgvector向量列 + content_hash去重 + 权威/时效评分
-- ============================================================
CREATE TABLE knowledge_entries (
    -- 主键
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 基本信息
    title               VARCHAR(500) NOT NULL,
    source              VARCHAR(255) NOT NULL,
    source_type         knowledge_source_type NOT NULL,
    publish_year        INTEGER NOT NULL
                        CONSTRAINT ck_knowledge_entries_year_range
                        CHECK (publish_year BETWEEN 1900 AND 2100),
    version             VARCHAR(50),   -- 指南版本号 (教材/综述可为NULL)

    -- 知识正文
    content             TEXT NOT NULL,

    -- SHA256去重哈希
    content_hash        VARCHAR(64) NOT NULL UNIQUE,

    -- ============================================================
    -- pgvector 向量列 (与pgvector (PostgreSQL 扩展)并行或作为降级方案)
    --
    -- 维度说明:
    --   阿里 text-embedding-v3: 1536维
    --   BGE-M3: 1024维
    --   预留最大维度 2000 以兼容后续模型切换
    --
    -- 索引: 使用IVFFlat索引 (初期1K-10K条)，
    --       后期可切换为HNSW索引 (>10K条)
    -- ============================================================
    embedding           vector(2000),   -- 预留2000维, 实际维度<=此值

    -- pgvector (PostgreSQL 扩展)关联
    embedding_id        VARCHAR(255),   -- pgvector (PostgreSQL 扩展)中的向量ID (双写/同步策略)
    embedding_model     VARCHAR(100),   -- 使用的Embedding模型 (text-embedding-v3 / bge-m3)
    embedding_dim       INTEGER,        -- 实际使用的向量维度 (1536 / 1024)

    -- 评分
    authority_score     FLOAT NOT NULL DEFAULT 0.5
                        CONSTRAINT ck_knowledge_entries_authority_score
                        CHECK (authority_score >= 0.0 AND authority_score <= 1.0),
    freshness_score     FLOAT NOT NULL DEFAULT 1.0
                        CONSTRAINT ck_knowledge_entries_freshness_score
                        CHECK (freshness_score >= 0.0 AND freshness_score <= 1.0),

    -- 标签 (疾病/症状/药物/检查等)
    tags                TEXT[] NOT NULL DEFAULT '{}',

    -- 状态
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    reviewed_by         VARCHAR(100),   -- 审核人

    -- 时间戳
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

-- BTree索引
CREATE INDEX idx_knowledge_entries_source_type  ON knowledge_entries(source_type);
CREATE INDEX idx_knowledge_entries_publish_year ON knowledge_entries(publish_year);
CREATE INDEX idx_knowledge_entries_active_score ON knowledge_entries(is_active, freshness_score DESC)
    WHERE is_active = TRUE;
CREATE INDEX idx_knowledge_entries_content_hash ON knowledge_entries(content_hash);
CREATE INDEX idx_knowledge_entries_embedding_id ON knowledge_entries(embedding_id)
    WHERE embedding_id IS NOT NULL;

-- GIN索引: 标签数组
CREATE INDEX idx_knowledge_entries_tags ON knowledge_entries USING GIN (tags);

-- GIN索引: 标题+来源文本搜索 (pg_trgm模糊匹配)
CREATE INDEX idx_knowledge_entries_title_trgm ON knowledge_entries
    USING GIN (title gin_trgm_ops);
CREATE INDEX idx_knowledge_entries_source_trgm ON knowledge_entries
    USING GIN (source gin_trgm_ops);

-- 向量索引 (IVFFlat — 初期数据量<10K时使用)
-- 向量检索语法: SELECT * FROM knowledge_entries
--                ORDER BY embedding <-> query_vector LIMIT 10;
-- ⚠️ 此索引需在数据入库后创建，IVFFlat需要训练数据分布
-- CREATE INDEX idx_knowledge_entries_embedding_ivf ON knowledge_entries
--     USING ivfflat (embedding vector_cosine_ops)
--     WITH (lists = 100);  -- lists = sqrt(行数)

-- 注释
COMMENT ON TABLE knowledge_entries IS '医学知识库元数据表。向量存储在pgvector embedding列中，同时支持pgvector (PostgreSQL 扩展)同步';
COMMENT ON COLUMN knowledge_entries.content_hash IS 'SHA256(content)，用于去重检测';
COMMENT ON COLUMN knowledge_entries.embedding IS '预留给pgvector的向量列（最大2000维）。与pgvector (PostgreSQL 扩展)可并行使用或作为降级方案';
COMMENT ON COLUMN knowledge_entries.embedding_id IS 'pgvector (PostgreSQL 扩展)中的对应向量ID，用于双写/同步策略';
COMMENT ON COLUMN knowledge_entries.embedding_model IS '使用的Embedding模型名称: text-embedding-v3(1536) / bge-m3(1024)';
COMMENT ON COLUMN knowledge_entries.embedding_dim IS '实际向量维度 (1536或1024)，用于向量检索时裁剪维度';
COMMENT ON COLUMN knowledge_entries.authority_score IS '权威性评分 0.0-1.0: guideline=0.9 > consensus=0.75 > textbook=0.6 > review=0.5 > case_report=0.2';
COMMENT ON COLUMN knowledge_entries.freshness_score IS '时效性评分: max(0, 1.0-(current_year-publish_year)/10)。超过5年额外×0.7衰减';
COMMENT ON COLUMN knowledge_entries.tags IS '多维度标签数组，如 {高血压,心血管,慢性病}';
```

---

### 3.7 diagnosis_citations — 诊断引用关联表

```sql
-- ============================================================
-- 7. diagnosis_citations — 诊断引用关联表
-- 职责: N:M 关联诊断结果与知识库引用条目
-- 增长: 线性 (~3-5条引用/诊断, 10K→1M)
-- 核心设计: 记录引用片段的证伪角色(支持/反驳/背景)和相关度
-- ============================================================
CREATE TABLE diagnosis_citations (
    -- 主键
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 诊断结果
    diagnosis_result_id     UUID NOT NULL
                            CONSTRAINT fk_citations_diagnosis_result
                            REFERENCES diagnosis_results(id) ON DELETE CASCADE,

    -- 知识条目
    knowledge_entry_id      UUID NOT NULL
                            CONSTRAINT fk_citations_knowledge_entry
                            REFERENCES knowledge_entries(id) ON DELETE RESTRICT,

    -- 相关度评分
    relevance_score         FLOAT NOT NULL DEFAULT 0.5
                            CONSTRAINT ck_citations_relevance_score
                            CHECK (relevance_score >= 0.0 AND relevance_score <= 1.0),

    -- 证据角色
    evidence_role           evidence_role_enum NOT NULL DEFAULT 'supporting',

    -- 引用片段摘要 (用户可理解的中文摘要)
    excerpt                 TEXT,

    -- 时间戳
    created_at              TIMESTAMP NOT NULL DEFAULT NOW(),

    -- 唯一约束: 同一诊断中同一知识条目只引用一次
    UNIQUE (diagnosis_result_id, knowledge_entry_id)
);

-- 索引
CREATE INDEX idx_citations_diagnosis_id   ON diagnosis_citations(diagnosis_result_id);
CREATE INDEX idx_citations_knowledge_id   ON diagnosis_citations(knowledge_entry_id);
CREATE INDEX idx_citations_evidence_role  ON diagnosis_citations(evidence_role);

-- 注释
COMMENT ON TABLE diagnosis_citations IS '诊断结果↔知识条目 N:M 关联表。循证溯源的核心表';
COMMENT ON COLUMN diagnosis_citations.evidence_role IS 'supporting=支持诊断 | contradicting=反对/需排除 | background=背景知识';
COMMENT ON COLUMN diagnosis_citations.excerpt IS '该知识条目在本次诊断中引用的关键片段摘要';
```

---

### 3.8 safety_events — 安全事件表

```sql
-- ============================================================
-- 8. safety_events — 安全事件表
-- 职责: 独立记录所有安全相关事件 (红旗/脱敏/过滤/降级)
-- 增长: 低频 (~1K→100K)
-- 核心设计: 与audit_logs解耦，独立安全审计追溯
-- ============================================================
CREATE TABLE safety_events (
    -- 主键
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 所属会话
    session_id      UUID NOT NULL
                    CONSTRAINT fk_safety_events_session
                    REFERENCES sessions(id) ON DELETE CASCADE,

    -- 事件分类
    event_category  safety_event_category NOT NULL,

    -- 严重度
    severity        safety_severity NOT NULL DEFAULT 'warning',

    -- 事件描述
    description     TEXT NOT NULL,

    -- 事件上下文 (脱敏后)
    context_data    JSONB NOT NULL DEFAULT '{}',

    -- 采取的响应动作
    action_taken    VARCHAR(255) NOT NULL,

    -- 时间戳 (🔒 IMMUTABLE)
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_safety_events_session_id   ON safety_events(session_id);
CREATE INDEX idx_safety_events_category     ON safety_events(event_category);
CREATE INDEX idx_safety_events_severity     ON safety_events(severity)
    WHERE severity IN ('warning', 'critical');
CREATE INDEX idx_safety_events_created_at   ON safety_events(created_at);

-- 注释
COMMENT ON TABLE safety_events IS '安全事件独立记录表 🔒IMMUTABLE。与audit_logs解耦的安全审计追溯';
COMMENT ON COLUMN safety_events.event_category IS 'red_flag|pii_detected|content_filtered|fallback|schema_rejected';
COMMENT ON COLUMN safety_events.severity IS 'info=低风险 | warning=中等风险(红旗触发等) | critical=严重(PII泄露/内容违规)';
COMMENT ON COLUMN safety_events.context_data IS '事件上下文JSON(已脱敏): 触发词/脱敏数量/违规内容类型等';
COMMENT ON COLUMN safety_events.action_taken IS '系统自动执行的响应动作描述';
```

---

## 4. 索引策略详解

### 4.1 索引总览

```sql
-- ============================================================
-- 索引总览 (已在各表DDL中创建，此处统一说明策略)
-- ============================================================

-- ┌─────────────────────┬──────────────────────────────────┬──────────────┐
-- │ 表                   │ 索引                              │ 策略说明       │
-- ├─────────────────────┼──────────────────────────────────┼──────────────┤
-- │ sessions            │ user_id                          │ 用户会话列表   │
-- │                     │ status (WHERE active/paused)     │ 活跃会话监控   │
-- │                     │ intent                           │ 意图分布统计   │
-- │                     │ created_at                       │ 时间范围查询   │
-- │                     │ red_flag (WHERE TRUE)            │ 安全事件统计   │
-- ├─────────────────────┼──────────────────────────────────┼──────────────┤
-- │ messages            │ session_id                       │ 会话消息列表   │
-- │                     │ (session_id, round_number)       │ 轮次定位      │
-- │                     │ created_at                       │ 时间排序      │
-- │                     │ agent_source (WHERE NOT NULL)    │ Agent消息统计  │
-- ├─────────────────────┼──────────────────────────────────┼──────────────┤
-- │ medical_records     │ session_id (UNIQUE)              │ 1:1唯一关联   │
-- │                     │ completion_level (partial/core)  │ 进行中病历    │
-- │                     │ GIN: chief_complaint (trgm)      │ 主诉文本搜索   │
-- │                     │ GIN: record_data (jsonb_path)    │ JSONB路径查询  │
-- ├─────────────────────┼──────────────────────────────────┼──────────────┤
-- │ diagnosis_results   │ session_id (UNIQUE)              │ 1:1唯一关联   │
-- │                     │ medical_record_id                │ 病历→诊断回溯  │
-- │                     │ created_at                       │ 时间排序      │
-- │                     │ GIN: result_data (jsonb_path)    │ JSONB路径查询  │
-- │                     │ fallback (WHERE TRUE)            │ 降级率监控    │
-- ├─────────────────────┼──────────────────────────────────┼──────────────┤
-- │ audit_logs          │ session_id                       │ 会话审计追踪   │
-- │                     │ agent_name                       │ Agent调用统计  │
-- │                     │ event_type                       │ 事件类型统计   │
-- │                     │ created_at                       │ 时间范围查询   │
-- │                     │ red_flag (WHERE TRUE)            │ 安全事件筛选   │
-- │                     │ (session_id, created_at)         │ 会话时间线    │
-- │                     │ GIN: token_usage                 │ Token消耗分析  │
-- │                     │ GIN: input_summary (jsonb_path)  │ 输入内容搜索   │
-- ├─────────────────────┼──────────────────────────────────┼──────────────┤
-- │ knowledge_entries   │ source_type                      │ 来源类型筛选   │
-- │                     │ publish_year                     │ 年份范围查询   │
-- │                     │ (is_active, freshness_score)     │ 有效知识排序   │
-- │                     │ content_hash                     │ 去重查询      │
-- │                     │ embedding_id (WHERE NOT NULL)    │ pgvector (PostgreSQL 扩展)关联    │
-- │                     │ GIN: tags                        │ 标签搜索      │
-- │                     │ GIN: title (trgm)                │ 标题模糊搜索   │
-- │                     │ GIN: source (trgm)               │ 来源模糊搜索   │
-- │                     │ IVFFlat: embedding (vector)      │ 向量相似度    │
-- ├─────────────────────┼──────────────────────────────────┼──────────────┤
-- │ diagnosis_citations │ diagnosis_result_id              │ 诊断→引用回溯  │
-- │                     │ knowledge_entry_id               │ 知识→被引查询  │
-- │                     │ evidence_role                    │ 证伪角色筛选   │
-- ├─────────────────────┼──────────────────────────────────┼──────────────┤
-- │ safety_events       │ session_id                       │ 会话安全事件   │
-- │                     │ event_category                   │ 事件分类统计   │
-- │                     │ severity (warning/critical)      │ 严重事件告警   │
-- │                     │ created_at                       │ 时间范围查询   │
-- └─────────────────────┴──────────────────────────────────┴──────────────┘
```

### 4.2 索引设计原则

| 原则 | 说明 |
|------|------|
| **高频查询优先** | `session_id` 是最高频的查询维度，所有关联表均建立索引 |
| **部分索引减少体积** | `WHERE` 子句过滤仅索引关注的行（如 active 状态、red_flag=TRUE） |
| **GIN用于JSONB** | 所有 JSONB 列均建立 GIN 索引以支持 `@>` / `?` / `->` 操作符 |
| **pg_trgm用于文本** | 知识库标题/主诉等文本搜索使用三元组模糊匹配 |
| **复合索引覆盖** | `(session_id, round_number)` 复合索引避免回表 |
| **分区继承** | audit_logs 的索引在默认分区创建，新分区需手动创建或脚本自动化 |

### 4.3 向量索引策略（渐进式）

```sql
-- ============================================================
-- 向量索引渐进策略
-- ============================================================

-- 阶段1: 数据量 < 10K — 暴力搜索 (无需索引)
-- SELECT * FROM knowledge_entries
-- ORDER BY embedding <-> query_vector LIMIT K;

-- 阶段2: 数据量 10K-100K — IVFFlat索引 (需训练)
-- CREATE INDEX idx_knowledge_entries_embedding_ivf
-- ON knowledge_entries
-- USING ivfflat (embedding vector_cosine_ops)
-- WITH (lists = 100);
--
-- lists配置公式: lists = max(1, sqrt(row_count) / 10)
-- 100K行 → lists = 316 ≈ 300

-- 阶段3: 数据量 > 100K — HNSW索引 (无需训练，高召回)
-- DROP INDEX idx_knowledge_entries_embedding_ivf;
-- CREATE INDEX idx_knowledge_entries_embedding_hnsw
-- ON knowledge_entries
-- USING hnsw (embedding vector_cosine_ops)
-- WITH (m = 16, ef_construction = 200);
--
-- 检索时设置: SET hnsw.ef_search = 100;
```

---

## 5. 触发器与自动化

```sql
-- ============================================================
-- 5.1 updated_at 自动更新触发器
-- ============================================================
CREATE OR REPLACE FUNCTION update_modified_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- sessions
CREATE TRIGGER trg_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION update_modified_timestamp();

-- medical_records
CREATE TRIGGER trg_medical_records_updated_at
    BEFORE UPDATE ON medical_records
    FOR EACH ROW EXECUTE FUNCTION update_modified_timestamp();

-- knowledge_entries
CREATE TRIGGER trg_knowledge_entries_updated_at
    BEFORE UPDATE ON knowledge_entries
    FOR EACH ROW EXECUTE FUNCTION update_modified_timestamp();


-- ============================================================
-- 5.2 诊断生成后同步更新引用计数触发器
-- ============================================================
CREATE OR REPLACE FUNCTION sync_diagnosis_citation_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE diagnosis_results
        SET citation_count = (
            SELECT COUNT(*) FROM diagnosis_citations
            WHERE diagnosis_result_id = NEW.diagnosis_result_id
        )
        WHERE id = NEW.diagnosis_result_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE diagnosis_results
        SET citation_count = (
            SELECT COUNT(*) FROM diagnosis_citations
            WHERE diagnosis_result_id = OLD.diagnosis_result_id
        )
        WHERE id = OLD.diagnosis_result_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_citation_count
    AFTER INSERT OR DELETE ON diagnosis_citations
    FOR EACH ROW EXECUTE FUNCTION sync_diagnosis_citation_count();


-- ============================================================
-- 5.3 会话关闭时自动设置 closed_at 触发器
-- ============================================================
CREATE OR REPLACE FUNCTION set_session_closed_at()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status IN ('completed','emergency_terminated','closed_timeout')
       AND OLD.status NOT IN ('completed','emergency_terminated','closed_timeout') THEN
        NEW.closed_at = NOW();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_session_closed_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION set_session_closed_at();


-- ============================================================
-- 5.4 知识库条目时效性评分自动计算触发器
-- ============================================================
CREATE OR REPLACE FUNCTION compute_freshness_score()
RETURNS TRIGGER AS $$
DECLARE
    current_yr INTEGER := EXTRACT(YEAR FROM CURRENT_DATE);
    base_score FLOAT;
BEGIN
    -- 基础时效性: 每年衰减10%
    base_score := GREATEST(0.0, 1.0 - (current_yr - NEW.publish_year)::FLOAT / 10.0);
    -- 超过5年额外衰减30%
    IF (current_yr - NEW.publish_year) > 5 THEN
        base_score := base_score * 0.7;
    END IF;
    NEW.freshness_score := ROUND(base_score::NUMERIC, 4);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_knowledge_freshness_score
    BEFORE INSERT OR UPDATE OF publish_year ON knowledge_entries
    FOR EACH ROW EXECUTE FUNCTION compute_freshness_score();


-- ============================================================
-- 5.5 消息原始内容定期清除函数 (由pg_cron或应用层定时任务调用)
-- ============================================================
CREATE OR REPLACE FUNCTION purge_message_raw_content(retention_days INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    purged_count INTEGER;
BEGIN
    WITH purged AS (
        UPDATE messages
        SET content_raw_encrypted = NULL
        WHERE content_raw_encrypted IS NOT NULL
          AND created_at < NOW() - (retention_days || ' days')::INTERVAL
        RETURNING id
    )
    SELECT COUNT(*) INTO purged_count FROM purged;

    RAISE NOTICE 'Purged raw content from % messages (older than % days)', purged_count, retention_days;
    RETURN purged_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION purge_message_raw_content IS '清除超过保留期的消息原始内容。默认30天。由定时任务每日调用';
```

---

## 6. 安全设计

### 6.1 PII 数据映射

```
┌───────────────────────────────────────────────────────────────┐
│                    PII 数据存储策略                              │
│                                                                │
│  用户原始输入 (含PII)                                           │
│         │                                                      │
│         ▼                                                      │
│  ┌─────────────────┐                                           │
│  │  PII脱敏引擎      │  正则+NER → 姓名→[姓名], 手机→[手机号]     │
│  └────────┬────────┘                                           │
│           │                                                    │
│     ┌─────┴─────┐                                              │
│     ▼           ▼                                              │
│  ┌───────┐  ┌──────────┐                                      │
│  │脱敏文本│  │原始文本    │                                      │
│  │ content│  │          │                                      │
│  │(永久)  │  │AES-256   │                                      │
│  │       │  │GCM加密   │                                      │
│  │明文   │  │→ BYTEA  │                                      │
│  └───────┘  └────┬─────┘                                      │
│                  │                                              │
│                  ▼                                              │
│           ┌──────────────┐                                    │
│           │ content_raw_  │  30天后自动清除                      │
│           │ encrypted     │  (purge_message_raw_content)       │
│           └──────────────┘                                    │
│                                                                │
│  sessions.user_id: 前端哈希匿名化后存储，不可逆                   │
│  audit_logs.input_summary: 仅存储脱敏后摘要                     │
└───────────────────────────────────────────────────────────────┘
```

### 6.2 加密函数封装

```sql
-- ============================================================
-- 6.2 应用层加密/解密函数封装 (使用pgcrypto)
-- ============================================================

-- 加密函数 (应用层调用，密钥由环境变量注入)
-- ⚠️ 生产环境中密钥应通过Vault/KMS管理，不硬编码
CREATE OR REPLACE FUNCTION encrypt_message(
    plain_text TEXT,
    encryption_key TEXT
)
RETURNS BYTEA AS $$
BEGIN
    RETURN pgp_sym_encrypt(plain_text, encryption_key, 'compress-algo=2, cipher-algo=aes256');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 解密函数 (仅审计需要时调用，严格权限控制)
CREATE OR REPLACE FUNCTION decrypt_message(
    encrypted_data BYTEA,
    encryption_key TEXT
)
RETURNS TEXT AS $$
BEGIN
    RETURN pgp_sym_decrypt(encrypted_data, encryption_key);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ⚠️ 安全注意:
-- 1. pgcrypto的pgp_sym_encrypt/decrypt使用OpenSSL AES-256
-- 2. 密钥通过应用层环境变量注入，不存储在数据库中
-- 3. decrypt_message函数权限应严格限制 (仅DBA/安全审计角色)
-- 4. SECURITY DEFINER确保调用者无需直接访问密钥
```

### 6.3 数据库角色与权限

```sql
-- ============================================================
-- 6.3 数据库角色设计
-- ============================================================

-- 应用读写角色 (FastAPI连接)
-- CREATE ROLE medical_qa_app WITH LOGIN PASSWORD '<from_env>';
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO medical_qa_app;
-- REVOKE DELETE ON audit_logs, diagnosis_results, safety_events FROM medical_qa_app;

-- 只读分析角色 (Metabase/Grafana)
-- CREATE ROLE medical_qa_readonly WITH LOGIN PASSWORD '<from_env>';
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO medical_qa_readonly;

-- 安全审计角色 (合规审查, 可执行decrypt_message)
-- CREATE ROLE medical_qa_auditor WITH LOGIN PASSWORD '<from_env>';
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO medical_qa_auditor;
-- GRANT EXECUTE ON FUNCTION decrypt_message TO medical_qa_auditor;

-- 管理员角色 (DDL操作)
-- CREATE ROLE medical_qa_admin WITH LOGIN PASSWORD '<from_env>' SUPERUSER;
```

---

## 7. 设计决策说明

### 决策1: JSONB vs 关系列

| 数据 | 存储方式 | 理由 |
|------|---------|------|
| `medical_records.record_data` | **JSONB** | 病历字段因症状而异（头痛问部位/发烧不问），Schema灵活变化 |
| `diagnosis_results.result_data` | **JSONB** | 诊断输出嵌套深（鉴别诊断数组、引用数组），关系建模过度复杂 |
| `audit_logs.token_usage` | **JSONB** | 简单K-V，JSONB避免3列稀疏NULL |
| `audit_logs.safety_check` | **JSONB** | 安全校验维度可能动态扩展 |
| `sessions.metadata` | **JSONB** | 扩展元数据无固定Schema |

### 决策2: pgvector vs 纯pgvector (PostgreSQL 扩展)

- **策略：双轨并行。** pgvector (PostgreSQL 扩展) 为主要检索引擎，pgvector 作为降级方案和开发测试环境替代
- `knowledge_entries.embedding` 列预留2000维（兼容 text-embedding-v3 1536维 + BGE-M3 1024维）
- 生产环境：向量写入pgvector (PostgreSQL 扩展)，`embedding_id` 字段关联；pgvector列可为NULL
- 开发/测试环境：直接使用pgvector，无需部署pgvector (PostgreSQL 扩展)

### 决策3: 分区策略

- **audit_logs 强制按月分区。** 预期增长最快（50M+），分区防止单表过大
- 其他表数据量可控（<10M），暂不分区
- 分区创建脚本（月度自动化）：

```sql
-- 示例: 创建2026年7月分区
-- CREATE TABLE audit_logs_2026_07 PARTITION OF audit_logs
--     FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
```

### 决策4: 外键删除行为

| 外键 | ON DELETE | 理由 |
|------|-----------|------|
| messages → sessions | **CASCADE** | 删除会话时清除关联消息 |
| medical_records → sessions | **CASCADE** | 删除会话时清除病历 |
| diagnosis_results → sessions | **CASCADE** | 删除会话时清除诊断 |
| audit_logs → sessions | **CASCADE** | 删除会话时清除审计日志 |
| diagnosis_results → medical_records | **RESTRICT** | 有病历关联的诊断不允许删除病历 |
| diagnosis_citations → diagnosis_results | **CASCADE** | 删除诊断时清除引用记录 |
| diagnosis_citations → knowledge_entries | **RESTRICT** | 被引用的知识条目不允许删除（先标记is_active=false） |

### 决策5: content_raw_encrypted 清除策略

- 加密存储原始输入以满足合规审计需求
- 30天保留期平衡审计追溯与隐私最小化
- `purge_message_raw_content()` 由 pg_cron 或 FastAPI 后台任务每日调用
- 清除后 `content_raw_encrypted` 置为 NULL，`content` (脱敏版) 永久保留

### 决策6: 向量索引渐进策略

- **阶段1 (<10K):** 不建向量索引，暴力搜索
- **阶段2 (10K-100K):** 建IVFFlat索引（需`lists`参数训练）
- **阶段3 (>100K):** 切换HNSW索引（更高召回率，无需训练）

---

## 附录 A. 完整建表执行顺序

```
1. 启用扩展 (pgcrypto, vector, pg_trgm)
2. 创建自定义枚举类型
3. CREATE TABLE sessions
4. CREATE TABLE messages
5. CREATE TABLE medical_records
6. CREATE TABLE diagnosis_results
7. CREATE TABLE knowledge_entries
8. CREATE TABLE diagnosis_citations
9. CREATE TABLE audit_logs (分区表) + audit_logs_default
10. CREATE TABLE safety_events
11. 创建触发器函数
12. 创建触发器
13. 创建向量索引 (数据入库后)
```

## 附录 B. 与架构文档的追溯

| 架构文档 | 本设计 |
|---------|--------|
| §9.1 技术栈选型 | §1.3 扩展依赖 (pgvector) |
| §9.3 组件依赖关系 | §3 完整DDL (6表→8表增强) |
| §9.4 数据库Schema | §3 完整DDL (字段完整化 + 约束 + 注释) |
| §8 安全架构 | §6 安全设计 (PII映射 + 加密 + 角色) |
| §7 知识检索架构 | §3.6 pgvector向量列 + §4.3 向量索引策略 |
| §6.2 状态持久化策略 | §3.1-3.5 各表持久化策略适配 |
| SDD-01 §2 实体字段定义 | §3 各表DDL字段完整对齐 |

---

> **文档维护者：** 开发团队
> **最后更新：** 2026-06-19
> **下一阶段：** DDD — 聚合根、Repository接口与应用服务设计
