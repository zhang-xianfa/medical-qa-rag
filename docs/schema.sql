-- ============================================================
-- 医疗智能问答系统 - PostgreSQL Schema
-- 版本: v1.0
-- 生成日期: 2026-06-19
-- 目标数据库: PostgreSQL 16+
-- 依赖扩展: pgcrypto, vector, pg_trgm
--
-- 执行方式:
--   psql -U postgres -d medical_qa -f schema.sql
--
-- 包含表 (按依赖顺序):
--   1. sessions             会话生命周期管理
--   2. messages             对话消息 (脱敏后存储 + 加密原始数据)
--   3. medical_records      结构化病历 (JSONB)
--   4. diagnosis_results    诊断结果 (JSONB, IMMUTABLE)
--   5. knowledge_entries    知识库元数据 (pgvector向量)
--   6. diagnosis_citations  诊断引用关联 (N:M)
--   7. audit_logs           审计日志 (分区表, IMMUTABLE)
--   8. safety_events        安全事件 (独立安全审计)
--
-- 安全标注:
--   🔴PII = 个人身份信息字段，已脱敏或加密存储
--   🔒IMMUTABLE = 写入后不可修改
-- ============================================================

-- ============================================================
-- 0. 扩展启用
-- ============================================================
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================
-- 0. 自定义枚举类型
-- ============================================================
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

DO $$ BEGIN
    CREATE TYPE message_role AS ENUM (
        'user',
        'assistant',
        'system'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

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

DO $$ BEGIN
    CREATE TYPE completion_level_enum AS ENUM (
        'partial',
        'core_complete',
        'full'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

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

DO $$ BEGIN
    CREATE TYPE safety_severity AS ENUM (
        'info',
        'warning',
        'critical'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE evidence_role_enum AS ENUM (
        'supporting',
        'contradicting',
        'background'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================
-- 1. sessions — 会话生命周期管理表
-- ============================================================
CREATE TABLE sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         VARCHAR(255) NOT NULL,           -- 🔴PII: 前端哈希匿名化后的用户标识，不可逆
    status          session_status NOT NULL DEFAULT 'active',
    intent          session_intent NOT NULL DEFAULT 'greeting',
    current_stage   workflow_stage NOT NULL DEFAULT 'init',
    red_flag_raised BOOLEAN NOT NULL DEFAULT FALSE,
    round_count     INTEGER NOT NULL DEFAULT 0
                    CONSTRAINT ck_sessions_round_count_positive CHECK (round_count >= 0),
    max_rounds      INTEGER NOT NULL DEFAULT 5
                    CONSTRAINT ck_sessions_max_rounds_range CHECK (max_rounds BETWEEN 1 AND 10),
    close_reason    VARCHAR(50)
                    CONSTRAINT ck_sessions_close_reason CHECK (
                        close_reason IS NULL
                        OR close_reason IN ('completed','emergency','timeout','user_aborted')
                    ),
    closed_at       TIMESTAMP,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE sessions IS '会话生命周期管理表';
COMMENT ON COLUMN sessions.user_id IS '🔴PII: 前端哈希匿名化后的用户标识，不可逆';
COMMENT ON COLUMN sessions.status IS 'active|paused|completed|emergency_terminated|closed_timeout';
COMMENT ON COLUMN sessions.intent IS 'MasterAgent识别的用户意图';
COMMENT ON COLUMN sessions.current_stage IS 'LangGraph工作流当前阶段';
COMMENT ON COLUMN sessions.red_flag_raised IS '是否触发红旗紧急中断';
COMMENT ON COLUMN sessions.close_reason IS 'completed|emergency|timeout|user_aborted';
COMMENT ON COLUMN sessions.metadata IS '扩展元数据: 客户端UA/来源渠道/自定义标签等';

-- ============================================================
-- 2. messages — 对话消息表
-- ============================================================
CREATE TABLE messages (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id              UUID NOT NULL
                            CONSTRAINT fk_messages_session
                            REFERENCES sessions(id) ON DELETE CASCADE,
    round_number            INTEGER NOT NULL DEFAULT 0
                            CONSTRAINT ck_messages_round_nonnegative CHECK (round_number >= 0),
    role                    message_role NOT NULL,
    content                 TEXT NOT NULL,           -- 🔴PII: 已脱敏文本 (PII→占位符)
    content_raw_encrypted   BYTEA,                   -- 🔴PII: AES-256-GCM加密原始输入,30天自动清除
    content_type            message_content_type NOT NULL DEFAULT 'text',
    agent_source            agent_name_enum,
    token_count             INTEGER,
    created_at              TIMESTAMP NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE messages IS '对话消息表, 记录会话中每一轮次的用户输入(脱敏后)和系统输出';
COMMENT ON COLUMN messages.content IS '🔴PII: 脱敏后的消息文本。PII字段已替换为占位符';
COMMENT ON COLUMN messages.content_raw_encrypted IS '🔴PII: AES-256-GCM加密的原始消息。用于审计追溯，30天自动清除。NULL=已清除';
COMMENT ON COLUMN messages.round_number IS '问诊轮次编号。非问诊阶段消息为0';
COMMENT ON COLUMN messages.content_type IS 'text|question|diagnosis_report|emergency_guide|status_report';
COMMENT ON COLUMN messages.agent_source IS 'master|interview|search|diagnosis|emergency|system';

-- ============================================================
-- 3. medical_records — 结构化病历表
-- ============================================================
CREATE TABLE medical_records (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID NOT NULL UNIQUE
                        CONSTRAINT fk_medical_records_session
                        REFERENCES sessions(id) ON DELETE CASCADE,
    version             INTEGER NOT NULL DEFAULT 1
                        CONSTRAINT ck_medical_records_version_positive CHECK (version >= 1),
    record_data         JSONB NOT NULL,             -- 结构化病历JSON (📋 REQUIRED_CORE: chief_complaint/duration/location)
    completion_level    completion_level_enum NOT NULL DEFAULT 'partial',
    missing_core_fields TEXT[] NOT NULL DEFAULT '{}',
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE medical_records IS '结构化病历表，问诊Agent多轮采集结果。一个会话仅一份病历，版本号递增';
COMMENT ON COLUMN medical_records.record_data IS '结构化病历JSONB。📋 P0核心字段: chief_complaint/duration/location 决定问诊终止';
COMMENT ON COLUMN medical_records.completion_level IS 'partial=部分采集 | core_complete=核心字段完整 | full=全部字段采集完成';
COMMENT ON COLUMN medical_records.missing_core_fields IS '尚未采集的REQUIRED_CORE字段路径列表';

-- ============================================================
-- 4. diagnosis_results — 诊断结果表 (🔒IMMUTABLE)
-- ============================================================
CREATE TABLE diagnosis_results (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID NOT NULL UNIQUE
                        CONSTRAINT fk_diagnosis_results_session
                        REFERENCES sessions(id) ON DELETE CASCADE,
    medical_record_id   UUID NOT NULL
                        CONSTRAINT fk_diagnosis_results_medical_record
                        REFERENCES medical_records(id) ON DELETE RESTRICT,
    result_data         JSONB NOT NULL,             -- 诊断报告完整JSON (Schema校验后写入)
    schema_version      VARCHAR(20) NOT NULL DEFAULT '1.0',
    schema_validated    BOOLEAN NOT NULL DEFAULT FALSE
                        CONSTRAINT ck_diagnosis_results_validated CHECK (schema_validated = TRUE),
    fallback_triggered  BOOLEAN NOT NULL DEFAULT FALSE,
    citation_count      INTEGER NOT NULL DEFAULT 0
                        CONSTRAINT ck_diagnosis_results_citation_count CHECK (citation_count >= 0),
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()  -- 🔒IMMUTABLE: 无updated_at
);

COMMENT ON TABLE diagnosis_results IS '诊断结果表 🔒IMMUTABLE。生成后不可修改，仅追加审计记录';
COMMENT ON COLUMN diagnosis_results.result_data IS '诊断报告完整JSON。必须通过JSON Schema校验后才可写入';
COMMENT ON COLUMN diagnosis_results.schema_validated IS '必须为TRUE。schema_validated=FALSE的行不应存在(约束阻止)';
COMMENT ON COLUMN diagnosis_results.fallback_triggered IS 'Schema校验失败时触发降级，返回安全建议而非诊断报告';
COMMENT ON COLUMN diagnosis_results.citation_count IS '与diagnosis_citations表行数保持一致的冗余计数';

-- ============================================================
-- 5. knowledge_entries — 知识库元数据表
-- ============================================================
CREATE TABLE knowledge_entries (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title               VARCHAR(500) NOT NULL,
    source              VARCHAR(255) NOT NULL,
    source_type         knowledge_source_type NOT NULL,
    publish_year        INTEGER NOT NULL
                        CONSTRAINT ck_knowledge_entries_year_range CHECK (publish_year BETWEEN 1900 AND 2100),
    version             VARCHAR(50),
    content             TEXT NOT NULL,
    content_hash        VARCHAR(64) NOT NULL UNIQUE,
    embedding           vector(2000),               -- pgvector向量列 (预留2000维)
    embedding_id        VARCHAR(255),               -- 向量条目唯一标识
    embedding_model     VARCHAR(100),               -- text-embedding-v3 / bge-m3
    embedding_dim       INTEGER,                    -- 实际向量维度 (1536 / 1024)
    authority_score     FLOAT NOT NULL DEFAULT 0.5
                        CONSTRAINT ck_knowledge_entries_authority_score CHECK (authority_score >= 0.0 AND authority_score <= 1.0),
    freshness_score     FLOAT NOT NULL DEFAULT 1.0
                        CONSTRAINT ck_knowledge_entries_freshness_score CHECK (freshness_score >= 0.0 AND freshness_score <= 1.0),
    tags                TEXT[] NOT NULL DEFAULT '{}',
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    reviewed_by         VARCHAR(100),
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE knowledge_entries IS '医学知识库元数据表，向量存储在 pgvector embedding 列中';
COMMENT ON COLUMN knowledge_entries.content_hash IS 'SHA256(content)，用于去重检测';
COMMENT ON COLUMN knowledge_entries.embedding IS 'pgvector 向量列（最大2000维，默认1024）';
COMMENT ON COLUMN knowledge_entries.embedding_id IS '向量条目唯一标识，用于去重和关联';
COMMENT ON COLUMN knowledge_entries.embedding_model IS '使用的Embedding模型名称: text-embedding-v3(1536) / bge-m3(1024)';
COMMENT ON COLUMN knowledge_entries.embedding_dim IS '实际向量维度 (1536或1024)，用于向量检索时裁剪维度';
COMMENT ON COLUMN knowledge_entries.authority_score IS '权威性评分 0.0-1.0: guideline=0.9 > consensus=0.75 > textbook=0.6 > review=0.5 > case_report=0.2';
COMMENT ON COLUMN knowledge_entries.freshness_score IS '时效性评分: max(0, 1.0-(current_year-publish_year)/10)。超过5年额外×0.7衰减';
COMMENT ON COLUMN knowledge_entries.tags IS '多维度标签数组，如 {高血压,心血管,慢性病}';

-- ============================================================
-- 6. diagnosis_citations — 诊断引用关联表 (N:M)
-- ============================================================
CREATE TABLE diagnosis_citations (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    diagnosis_result_id     UUID NOT NULL
                            CONSTRAINT fk_citations_diagnosis_result
                            REFERENCES diagnosis_results(id) ON DELETE CASCADE,
    knowledge_entry_id      UUID NOT NULL
                            CONSTRAINT fk_citations_knowledge_entry
                            REFERENCES knowledge_entries(id) ON DELETE RESTRICT,
    relevance_score         FLOAT NOT NULL DEFAULT 0.5
                            CONSTRAINT ck_citations_relevance_score CHECK (relevance_score >= 0.0 AND relevance_score <= 1.0),
    evidence_role           evidence_role_enum NOT NULL DEFAULT 'supporting',
    excerpt                 TEXT,
    created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (diagnosis_result_id, knowledge_entry_id)
);

COMMENT ON TABLE diagnosis_citations IS '诊断结果↔知识条目 N:M 关联表。循证溯源的核心表';
COMMENT ON COLUMN diagnosis_citations.evidence_role IS 'supporting=支持诊断 | contradicting=反对/需排除 | background=背景知识';
COMMENT ON COLUMN diagnosis_citations.excerpt IS '该知识条目在本次诊断中引用的关键片段摘要';

-- ============================================================
-- 7. audit_logs — 审计日志表 (🔒IMMUTABLE, 按月分区)
-- ============================================================
CREATE TABLE audit_logs (
    id                  UUID DEFAULT gen_random_uuid(),
    session_id          UUID NOT NULL
                        CONSTRAINT fk_audit_logs_session
                        REFERENCES sessions(id) ON DELETE CASCADE,
    agent_name          agent_name_enum NOT NULL,
    event_type          audit_event_type NOT NULL,
    input_summary       JSONB NOT NULL,             -- 🔴PII: 脱敏后的Agent输入摘要
    output_summary      JSONB NOT NULL,
    token_usage         JSONB NOT NULL,             -- {prompt_tokens, completion_tokens, total_tokens}
    latency_ms          INTEGER NOT NULL
                        CONSTRAINT ck_audit_logs_latency_positive CHECK (latency_ms >= 0),
    model_name          VARCHAR(100) NOT NULL,
    red_flag_triggered  BOOLEAN NOT NULL DEFAULT FALSE,
    safety_check        JSONB NOT NULL DEFAULT '{}', -- {content_filtered, disclaimer_appended, schema_validated}
    error_info          JSONB,                      -- NULL=正常执行
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (created_at, id)
) PARTITION BY RANGE (created_at);

CREATE TABLE audit_logs_default PARTITION OF audit_logs DEFAULT;

COMMENT ON TABLE audit_logs IS '审计日志表 🔒IMMUTABLE。每次Agent调用的完整审计记录，按月分区';
COMMENT ON COLUMN audit_logs.input_summary IS '🔴PII: 脱敏后的Agent输入摘要。原始PII不可出现在此字段';
COMMENT ON COLUMN audit_logs.token_usage IS 'JSON: {prompt_tokens, completion_tokens, total_tokens}';
COMMENT ON COLUMN audit_logs.safety_check IS 'JSON: {content_filtered, disclaimer_appended, schema_validated}';
COMMENT ON COLUMN audit_logs.error_info IS 'NULL=正常执行。异常时记录error类型/堆栈摘要';

-- ============================================================
-- 8. safety_events — 安全事件表 (🔒IMMUTABLE)
-- ============================================================
CREATE TABLE safety_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL
                    CONSTRAINT fk_safety_events_session
                    REFERENCES sessions(id) ON DELETE CASCADE,
    event_category  safety_event_category NOT NULL,
    severity        safety_severity NOT NULL DEFAULT 'warning',
    description     TEXT NOT NULL,
    context_data    JSONB NOT NULL DEFAULT '{}',
    action_taken    VARCHAR(255) NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE safety_events IS '安全事件独立记录表 🔒IMMUTABLE。与audit_logs解耦的安全审计追溯';
COMMENT ON COLUMN safety_events.event_category IS 'red_flag|pii_detected|content_filtered|fallback|schema_rejected';
COMMENT ON COLUMN safety_events.severity IS 'info=低风险 | warning=中等风险(红旗触发等) | critical=严重(PII泄露/内容违规)';
COMMENT ON COLUMN safety_events.context_data IS '事件上下文JSON(已脱敏): 触发词/脱敏数量/违规内容类型等';
COMMENT ON COLUMN safety_events.action_taken IS '系统自动执行的响应动作描述';

-- ============================================================
-- 索引
-- ============================================================

-- sessions
CREATE INDEX idx_sessions_user_id        ON sessions(user_id);
CREATE INDEX idx_sessions_status         ON sessions(status) WHERE status IN ('active','paused');
CREATE INDEX idx_sessions_intent         ON sessions(intent);
CREATE INDEX idx_sessions_created_at     ON sessions(created_at);
CREATE INDEX idx_sessions_red_flag       ON sessions(red_flag_raised) WHERE red_flag_raised = TRUE;

-- messages
CREATE INDEX idx_messages_session_id      ON messages(session_id);
CREATE INDEX idx_messages_session_round   ON messages(session_id, round_number);
CREATE INDEX idx_messages_created_at      ON messages(created_at);
CREATE INDEX idx_messages_agent_source    ON messages(agent_source) WHERE agent_source IS NOT NULL;

-- medical_records
CREATE INDEX idx_medical_records_session_id    ON medical_records(session_id);
CREATE INDEX idx_medical_records_completion    ON medical_records(completion_level)
    WHERE completion_level IN ('partial', 'core_complete');
CREATE INDEX idx_medical_records_chief_complaint ON medical_records
    USING GIN ((record_data->'patient_info'->>'chief_complaint') gin_trgm_ops);
CREATE INDEX idx_medical_records_record_data_gin ON medical_records
    USING GIN (record_data jsonb_path_ops);

-- diagnosis_results
CREATE INDEX idx_diagnosis_results_session_id    ON diagnosis_results(session_id);
CREATE INDEX idx_diagnosis_results_medical_rec   ON diagnosis_results(medical_record_id);
CREATE INDEX idx_diagnosis_results_created_at    ON diagnosis_results(created_at);
CREATE INDEX idx_diagnosis_results_data_gin      ON diagnosis_results
    USING GIN (result_data jsonb_path_ops);
CREATE INDEX idx_diagnosis_results_fallback      ON diagnosis_results(fallback_triggered)
    WHERE fallback_triggered = TRUE;

-- knowledge_entries
CREATE INDEX idx_knowledge_entries_source_type  ON knowledge_entries(source_type);
CREATE INDEX idx_knowledge_entries_publish_year ON knowledge_entries(publish_year);
CREATE INDEX idx_knowledge_entries_active_score ON knowledge_entries(is_active, freshness_score DESC)
    WHERE is_active = TRUE;
CREATE INDEX idx_knowledge_entries_content_hash ON knowledge_entries(content_hash);
CREATE INDEX idx_knowledge_entries_tags         ON knowledge_entries USING GIN (tags);
CREATE INDEX idx_knowledge_entries_title_trgm   ON knowledge_entries
    USING GIN (title gin_trgm_ops);
CREATE INDEX idx_knowledge_entries_source_trgm  ON knowledge_entries
    USING GIN (source gin_trgm_ops);

-- diagnosis_citations
CREATE INDEX idx_citations_diagnosis_id   ON diagnosis_citations(diagnosis_result_id);
CREATE INDEX idx_citations_knowledge_id   ON diagnosis_citations(knowledge_entry_id);
CREATE INDEX idx_citations_evidence_role  ON diagnosis_citations(evidence_role);

-- audit_logs (在默认分区上创建)
CREATE INDEX idx_audit_logs_session_id    ON audit_logs_default(session_id);
CREATE INDEX idx_audit_logs_agent_name    ON audit_logs_default(agent_name);
CREATE INDEX idx_audit_logs_event_type    ON audit_logs_default(event_type);
CREATE INDEX idx_audit_logs_created_at    ON audit_logs_default(created_at);
CREATE INDEX idx_audit_logs_red_flag      ON audit_logs_default(red_flag_triggered)
    WHERE red_flag_triggered = TRUE;
CREATE INDEX idx_audit_logs_session_time  ON audit_logs_default(session_id, created_at);
CREATE INDEX idx_audit_logs_token_gin     ON audit_logs_default USING GIN (token_usage);
CREATE INDEX idx_audit_logs_input_gin     ON audit_logs_default USING GIN (input_summary jsonb_path_ops);

-- safety_events
CREATE INDEX idx_safety_events_session_id   ON safety_events(session_id);
CREATE INDEX idx_safety_events_category     ON safety_events(event_category);
CREATE INDEX idx_safety_events_severity     ON safety_events(severity)
    WHERE severity IN ('warning', 'critical');
CREATE INDEX idx_safety_events_created_at   ON safety_events(created_at);

-- ============================================================
-- 触发器函数
-- ============================================================

-- updated_at 自动更新
CREATE OR REPLACE FUNCTION update_modified_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION update_modified_timestamp();

CREATE TRIGGER trg_medical_records_updated_at
    BEFORE UPDATE ON medical_records
    FOR EACH ROW EXECUTE FUNCTION update_modified_timestamp();

CREATE TRIGGER trg_knowledge_entries_updated_at
    BEFORE UPDATE ON knowledge_entries
    FOR EACH ROW EXECUTE FUNCTION update_modified_timestamp();

-- 会话关闭时自动设置 closed_at
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

-- 诊断引用计数同步
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

-- 知识库时效性评分自动计算
CREATE OR REPLACE FUNCTION compute_freshness_score()
RETURNS TRIGGER AS $$
DECLARE
    current_yr INTEGER := EXTRACT(YEAR FROM CURRENT_DATE);
    base_score FLOAT;
BEGIN
    base_score := GREATEST(0.0, 1.0 - (current_yr - NEW.publish_year)::FLOAT / 10.0);
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

-- 消息原始内容清除函数 (由pg_cron或应用层定时任务调用)
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

-- ============================================================
-- 完成
-- ============================================================
-- 表创建顺序: sessions → messages → medical_records → diagnosis_results
--            → knowledge_entries → diagnosis_citations → audit_logs → safety_events
-- 总表数: 8
-- 总索引数: 33
-- 触发器数: 6
-- ============================================================
