# 医疗智能问答系统 — API 契约设计 (OpenAPI 3.0)

> **版本：** v1.0
> **阶段：** SDD Phase 3 — API 契约
> **前置文档：** 系统架构设计文档、SDD-01 领域建模、SDD-02 数据库Schema
> **规范：** OpenAPI 3.0.3
> **日期：** 2026-06-19

---

## 目录

1. [API 设计总览](#1-api-设计总览)
2. [通用约定](#2-通用约定)
3. [OpenAPI 3.0 完整定义](#3-openapi-30-完整定义)
4. [接口详细说明](#4-接口详细说明)
   - [4.1 会话管理](#41-会话管理)
   - [4.2 消息与对话](#42-消息与对话)
   - [4.3 流式事件推送 (SSE)](#43-流式事件推送-sse)
   - [4.4 诊断管理](#44-诊断管理)
   - [4.5 安全事件](#45-安全事件)
   - [4.6 知识检索](#46-知识检索)
   - [4.7 健康检查](#47-健康检查)
5. [数据流示例](#5-数据流示例)
6. [安全设计](#6-安全设计)

---

## 1. API 设计总览

### 1.1 资源树

```
/api/v1/
├── /sessions                             会话管理
│   ├── POST     创建会话
│   ├── GET      会话列表
│   ├── /{session_id}
│   │   ├── GET       会话详情
│   │   ├── PATCH     更新会话状态
│   │   └── DELETE    删除会话
│   └── /{session_id}/stream
│       └── GET       SSE流式连接
│
├── /sessions/{session_id}/messages      消息管理
│   ├── POST     发送消息 (核心入口)
│   └── GET      消息历史
│
├── /sessions/{session_id}/diagnosis     诊断管理
│   └── GET      获取诊断报告
│
├── /sessions/{session_id}/safety        安全管理
│   └── GET      会话安全事件列表
│
├── /knowledge                           知识检索 (独立)
│   └── GET      知识库搜索
│
└── /health                              健康检查
    └── GET      服务状态
```

### 1.2 接口总览

| 方法 | 路径 | 描述 | 认证 | SSE |
|------|------|------|------|-----|
| POST | `/sessions` | 创建新会话 | — | — |
| GET | `/sessions` | 查询会话列表 | — | — |
| GET | `/sessions/{id}` | 获取会话详情 | — | — |
| PATCH | `/sessions/{id}` | 更新会话状态 | — | — |
| DELETE | `/sessions/{id}` | 删除会话 | — | — |
| **POST** | `/sessions/{id}/messages` | **发送用户消息（核心入口）** | — | — |
| GET | `/sessions/{id}/messages` | 获取消息历史 | — | — |
| **GET** | `/sessions/{id}/stream` | **SSE流式事件推送** | — | ✅ |
| GET | `/sessions/{id}/diagnosis` | 获取诊断报告 | — | — |
| GET | `/sessions/{id}/safety` | 安全事件列表 | — | — |
| GET | `/knowledge` | 知识库搜索 | — | — |
| GET | `/health` | 健康检查 | — | — |

---

## 2. 通用约定

### 2.1 URL 基础路径

```
开发环境:  http://localhost:8000/api/v1
生产环境:  https://medical-qa.example.com/api/v1
```

### 2.2 内容类型

| 场景 | Content-Type |
|------|-------------|
| 请求体 | `application/json; charset=utf-8` |
| 响应体 | `application/json; charset=utf-8` |
| SSE流 | `text/event-stream` |

### 2.3 日期时间格式

所有日期时间使用 **ISO 8601** 格式，UTC时区：

```
"2026-06-19T10:30:00.000Z"
```

### 2.4 通用错误响应

```json
{
  "error": "ERROR_CODE",
  "code": 400,
  "message": "人类可读的错误描述",
  "details": {},
  "timestamp": "2026-06-19T10:30:00.000Z"
}
```

### 2.5 分页约定

| 参数 | 类型 | 默认值 | 最大值 | 说明 |
|------|------|--------|--------|------|
| `limit` | integer | 20 | 100 | 每页返回条数 |
| `offset` | integer | 0 | — | 偏移量 (0-based) |

分页响应格式：

```json
{
  "data": [],
  "pagination": {
    "total": 150,
    "limit": 20,
    "offset": 0,
    "has_more": true
  }
}
```

---

## 3. OpenAPI 3.0 完整定义

```yaml
openapi: "3.0.3"
info:
  title: "医疗智能问答系统 API"
  description: >
    基于 Master-Agent 多智能体协作架构的医疗健康咨询系统 RESTful API。

    ## 核心特性
    - 多轮结构化问诊（InterviewAgent）
    - 异步循证知识检索（SearchAgent）
    - LLM综合推理诊断（DiagnosisAgent）
    - SSE流式事件推送
    - 红旗症状紧急中断

    ## 安全红线
    - 所有诊断输出含不确定性表达，**禁止AI确诊**
    - 红旗症状触发立即返回急救指引，**禁止继续问诊**
    - 用户PII信息在API入口层脱敏

    ## 免责声明
    本API返回的所有健康建议仅供参考，不能替代专业医疗诊断。
  version: "1.0.0"
  contact:
    name: "开发团队"
    email: "dev@medical-qa.local"

servers:
  - url: "http://localhost:8000/api/v1"
    description: "本地开发环境"
  - url: "https://medical-qa-staging.example.com/api/v1"
    description: "测试环境"
  - url: "https://medical-qa.example.com/api/v1"
    description: "生产环境"

tags:
  - name: Sessions
    description: "会话生命周期管理"
  - name: Messages
    description: "对话消息与问诊交互"
  - name: Streaming
    description: "SSE流式事件推送"
  - name: Diagnosis
    description: "诊断结果查询"
  - name: Safety
    description: "安全事件与红旗管理"
  - name: Knowledge
    description: "知识库检索"

# ============================================================
# 全局 Security Scheme
# ============================================================
security:
  - ApiKeyAuth: []

components:
  securitySchemes:
    ApiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key
      description: "API密钥（初期可选，生产环境必填）"

  # ============================================================
  # 通用 Schemas
  # ============================================================
  schemas:

    # --- 错误 ---
    ErrorResponse:
      type: object
      required: [error, code, message]
      properties:
        error:
          type: string
          description: "机器可读的错误码"
          example: "SESSION_NOT_FOUND"
        code:
          type: integer
          description: "HTTP状态码"
          example: 404
        message:
          type: string
          description: "人类可读的错误描述"
          example: "会话不存在或已被删除"
        details:
          type: object
          description: "附加错误详情"
        timestamp:
          type: string
          format: date-time
          example: "2026-06-19T10:30:00.000Z"

    # --- 分页 ---
    Pagination:
      type: object
      properties:
        total:
          type: integer
          description: "总记录数"
        limit:
          type: integer
        offset:
          type: integer
        has_more:
          type: boolean

    # --- 会话 ---
    SessionStatus:
      type: string
      enum: [active, paused, completed, emergency_terminated, closed_timeout]
      description: >
        active: 对话进行中
        paused: 用户超时暂停
        completed: 正常完成
        emergency_terminated: 红旗触发紧急终止
        closed_timeout: 长时间无活动关闭

    SessionIntent:
      type: string
      enum: [diagnosis, question, emergency, greeting, status, follow_up]

    WorkflowStage:
      type: string
      enum: [init, collect, diagnose, done, emergency]

    Session:
      type: object
      properties:
        id:
          type: string
          format: uuid
          example: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        user_id:
          type: string
          description: "🔴PII: 前端哈希匿名化后的用户标识"
          example: "anon_7f3a9b2c"
        status:
          $ref: "#/components/schemas/SessionStatus"
        intent:
          $ref: "#/components/schemas/SessionIntent"
        current_stage:
          $ref: "#/components/schemas/WorkflowStage"
        red_flag_raised:
          type: boolean
        round_count:
          type: integer
          minimum: 0
        max_rounds:
          type: integer
        close_reason:
          type: string
          nullable: true
          enum: [completed, emergency, timeout, user_aborted]
        closed_at:
          type: string
          format: date-time
          nullable: true
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time

    CreateSessionRequest:
      type: object
      properties:
        user_id:
          type: string
          description: "🔴PII: 前端已哈希匿名的用户标识"
          example: "anon_7f3a9b2c"
        max_rounds:
          type: integer
          minimum: 1
          maximum: 10
          default: 5
        metadata:
          type: object
          description: "扩展元数据（客户端信息、来源渠道等）"
      required: [user_id]

    UpdateSessionRequest:
      type: object
      properties:
        status:
          $ref: "#/components/schemas/SessionStatus"
        max_rounds:
          type: integer
          minimum: 1
          maximum: 10

    # --- 消息 ---
    MessageRole:
      type: string
      enum: [user, assistant, system]

    MessageContentType:
      type: string
      enum: [text, question, diagnosis_report, emergency_guide, status_report]

    Message:
      type: object
      properties:
        id:
          type: string
          format: uuid
        session_id:
          type: string
          format: uuid
        round_number:
          type: integer
        role:
          $ref: "#/components/schemas/MessageRole"
        content:
          type: string
          description: "🔴PII: 脱敏后的消息文本"
        content_type:
          $ref: "#/components/schemas/MessageContentType"
        agent_source:
          type: string
          enum: [master, interview, search, diagnosis, emergency, system]
        token_count:
          type: integer
        created_at:
          type: string
          format: date-time

    SendMessageRequest:
      type: object
      required: [content]
      properties:
        content:
          type: string
          description: "用户输入的原始消息（API入口层自动脱敏）"
          minLength: 1
          maxLength: 4096
          example: "我头痛两天了，前额位置，大概7分痛，还有点低烧"
        content_type:
          type: string
          enum: [text]
          default: text

    SendMessageResponse:
      type: object
      description: "发送消息的同步响应（含当前状态快照）"
      properties:
        message:
          $ref: "#/components/schemas/Message"
        session_status:
          $ref: "#/components/schemas/SessionStatus"
        current_stage:
          $ref: "#/components/schemas/WorkflowStage"
        red_flag_raised:
          type: boolean
        round_count:
          type: integer
        collected_fields_summary:
          type: object
          description: "当前已采集的核心字段摘要"
          example:
            chief_complaint: "头痛"
            duration: "2天"
            location: "前额"
            severity: 7
        next_action:
          type: string
          enum: [continue, diagnosis_ready, emergency_interrupted, completed]
          description: >
            continue: 继续问诊, 请连接SSE获取后续问题
            diagnosis_ready: 信息充足, 即将生成诊断 (连接SSE获取诊断结果)
            emergency_interrupted: 红旗触发, 会话已终止
            completed: 问答/诊断已完成

    # --- SSE事件类型 ---
    SSEEvent:
      type: object
      description: "SSE事件统一格式"
      required: [type]
      properties:
        type:
          type: string
          enum: [message, diagnosis_progress, diagnosis_complete, emergency, error, heartbeat]
          description: "事件类型标识"
      discriminator:
        propertyName: type
        mapping:
          message: "#/components/schemas/SSEMessageEvent"
          diagnosis_progress: "#/components/schemas/SSEDiagnosisProgressEvent"
          diagnosis_complete: "#/components/schemas/SSEDiagnosisCompleteEvent"
          emergency: "#/components/schemas/SSEEmergencyEvent"
          error: "#/components/schemas/SSEErrorEvent"
          heartbeat: "#/components/schemas/SSEHeartbeatEvent"

    SSEMessageEvent:
      type: object
      required: [type, role, content]
      properties:
        type:
          type: string
          enum: [message]
        role:
          type: string
          enum: [assistant, system]
        content:
          type: string
          description: "消息文本（流式增量拼接）"
        content_type:
          $ref: "#/components/schemas/MessageContentType"
        agent_source:
          type: string
        round_number:
          type: integer

    SSEDiagnosisProgressEvent:
      type: object
      required: [type, stage, progress]
      properties:
        type:
          type: string
          enum: [diagnosis_progress]
        stage:
          type: string
          enum: [evidence_matching, differential_gen, risk_assessment, recommendation, schema_validate]
          description: "当前诊断子阶段"
        progress:
          type: integer
          minimum: 0
          maximum: 100
          description: "诊断进度百分比"
        stage_description:
          type: string
          description: "中文阶段描述"

    SSEDiagnosisCompleteEvent:
      type: object
      required: [type, result]
      properties:
        type:
          type: string
          enum: [diagnosis_complete]
        result:
          $ref: "#/components/schemas/DiagnosisReport"

    SSEEmergencyEvent:
      type: object
      required: [type, action, guidance, red_flags]
      properties:
        type:
          type: string
          enum: [emergency]
        action:
          type: string
          enum: [call_120, immediate_er, urgent_appointment]
        guidance:
          type: string
          description: "急救指引文本"
        red_flags:
          type: array
          items:
            type: string
          description: "触发的红旗症状关键词"
        disclaimer:
          type: string

    SSEErrorEvent:
      type: object
      required: [type, code, message]
      properties:
        type:
          type: string
          enum: [error]
        code:
          type: string
          description: "错误码"
        message:
          type: string
          description: "错误描述"

    SSEHeartbeatEvent:
      type: object
      properties:
        type:
          type: string
          enum: [heartbeat]
        timestamp:
          type: string
          format: date-time

    # --- 诊断 ---
    DiagnosisReport:
      type: object
      required:
        - primary_diagnosis
        - differential_diagnosis
        - risk_assessment
        - recommendations
        - red_flags
        - references
        - disclaimer
      properties:
        primary_diagnosis:
          type: object
          properties:
            name:
              type: string
              description: "最可能的诊断名称"
              example: "紧张性头痛"
            probability:
              type: string
              description: "可能性百分比"
              example: "60%"
            rationale:
              type: string
              description: "推理依据"
              example: "前额压迫性头痛+工作压力诱因+无神经系统阳性体征，倾向于考虑紧张性头痛"
            certainty_level:
              type: string
              enum: [low, medium, high]
        differential_diagnosis:
          type: array
          items:
            type: object
            properties:
              name:
                type: string
                example: "偏头痛"
              probability:
                type: string
                example: "30%"
              key_evidence:
                type: string
              exclusion_criteria:
                type: string
        risk_assessment:
          type: object
          properties:
            severity:
              type: string
              enum: ["轻度", "中度", "重度", "危及生命"]
            urgency:
              type: string
              enum: ["可居家观察", "建议门诊", "尽快就医", "立即急诊"]
            warning_signs:
              type: array
              items:
                type: string
        recommendations:
          type: array
          items:
            type: object
            properties:
              category:
                type: string
                enum: ["居家护理", "用药建议", "就医建议", "生活方式", "监测建议"]
              content:
                type: string
              priority:
                type: integer
                minimum: 1
                maximum: 5
        red_flags:
          type: array
          items:
            type: object
            properties:
              symptom:
                type: string
              action:
                type: string
        references:
          type: array
          items:
            $ref: "#/components/schemas/DiagnosisReference"
        disclaimer:
          type: string
          description: "固定免责声明"

    DiagnosisReference:
      type: object
      properties:
        knowledge_entry_id:
          type: string
          format: uuid
          description: "知识库条目ID (追溯)"
        title:
          type: string
        source:
          type: string
        year:
          type: integer
        url:
          type: string
          nullable: true
        relevance_score:
          type: number

    # --- 安全事件 ---
    SafetyEvent:
      type: object
      properties:
        id:
          type: string
          format: uuid
        session_id:
          type: string
          format: uuid
        event_category:
          type: string
          enum: [red_flag, pii_detected, content_filtered, fallback, schema_rejected]
        severity:
          type: string
          enum: [info, warning, critical]
        description:
          type: string
        context_data:
          type: object
          description: "🔴PII: 事件上下文已脱敏"
        action_taken:
          type: string
        created_at:
          type: string
          format: date-time

    # --- 知识库 ---
    KnowledgeSearchResult:
      type: object
      properties:
        id:
          type: string
          format: uuid
        title:
          type: string
        source:
          type: string
        source_type:
          type: string
        publish_year:
          type: integer
        content_excerpt:
          type: string
          description: "匹配到的知识片段摘要"
        relevance_score:
          type: number
        authority_score:
          type: number

    # --- 健康检查 ---
    HealthResponse:
      type: object
      properties:
        status:
          type: string
          enum: [healthy, degraded, unhealthy]
        version:
          type: string
          example: "1.0.0"
        components:
          type: object
          properties:
            database:
              type: string
              enum: [up, down]
            pgvector:
              type: string
              enum: [up, down, not_configured]
            llm:
              type: string
              enum: [up, down]
        uptime_seconds:
          type: integer
          example: 86400

    # --- 病历摘要 ---
    MedicalRecordSummary:
      type: object
      properties:
        session_id:
          type: string
          format: uuid
        version:
          type: integer
        completion_level:
          type: string
          enum: [partial, core_complete, full]
        chief_complaint:
          type: string
        duration:
          type: string
        location:
          type: string
        severity:
          type: integer
        accompanying_symptoms:
          type: array
          items:
            type: string
        collected_fields:
          type: array
          items:
            type: string
          description: "已采集的字段路径列表"
        missing_core_fields:
          type: array
          items:
            type: string
          description: "尚未采集的核心字段"

  # ============================================================
  # 请求参数
  # ============================================================
  parameters:
    SessionIdParam:
      name: session_id
      in: path
      required: true
      schema:
        type: string
        format: uuid
      description: "会话ID"

    PaginationLimit:
      name: limit
      in: query
      schema:
        type: integer
        minimum: 1
        maximum: 100
        default: 20

    PaginationOffset:
      name: offset
      in: query
      schema:
        type: integer
        minimum: 0
        default: 0

  # ============================================================
  # 响应封装
  # ============================================================
  responses:
    400BadRequest:
      description: "请求参数无效"
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/ErrorResponse"
          example:
            error: "VALIDATION_ERROR"
            code: 400
            message: "content字段为必填项且长度1-4096字符"
            timestamp: "2026-06-19T10:30:00.000Z"

    401Unauthorized:
      description: "未认证"
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/ErrorResponse"
          example:
            error: "UNAUTHORIZED"
            code: 401
            message: "API密钥无效或已过期"
            timestamp: "2026-06-19T10:30:00.000Z"

    404NotFound:
      description: "资源不存在"
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/ErrorResponse"
          example:
            error: "SESSION_NOT_FOUND"
            code: 404
            message: "会话不存在或已被删除"
            timestamp: "2026-06-19T10:30:00.000Z"

    409Conflict:
      description: "状态冲突"
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/ErrorResponse"
          example:
            error: "SESSION_TERMINATED"
            code: 409
            message: "会话已紧急终止，无法继续操作"
            timestamp: "2026-06-19T10:30:00.000Z"

    500InternalError:
      description: "服务器内部错误"
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/ErrorResponse"
          example:
            error: "INTERNAL_ERROR"
            code: 500
            message: "系统繁忙，请稍后重试。如持续出现请就医。"
            timestamp: "2026-06-19T10:30:00.000Z"

# ============================================================
# API 路径定义
# ============================================================
paths:

  # ==========================================================
  # 健康检查
  # ==========================================================
  /health:
    get:
      tags: ["健康检查"]
      summary: "服务健康状态"
      description: "返回各组件连接状态和运行时长"
      security: []
      responses:
        "200":
          description: "服务状态"
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/HealthResponse"
              example:
                status: "healthy"
                version: "1.0.0"
                components:
                  database: "up"
                  pgvector: "up"
                  llm: "up"
                uptime_seconds: 86400

  # ==========================================================
  # 会话管理
  # ==========================================================
  /sessions:
    post:
      tags: [Sessions]
      summary: "创建新会话"
      description: |
        创建一次新的问诊/问答会话。返回会话ID供后续消息交互使用。
        
        **调用时机：** 用户首次进入系统或主动发起新咨询时。
      operationId: createSession
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/CreateSessionRequest"
            example:
              user_id: "anon_7f3a9b2c"
              max_rounds: 5
              metadata:
                client: "web"
                source: "direct"
      responses:
        "201":
          description: "会话创建成功"
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Session"
              example:
                id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
                user_id: "anon_7f3a9b2c"
                status: "active"
                intent: "greeting"
                current_stage: "init"
                red_flag_raised: false
                round_count: 0
                max_rounds: 5
                close_reason: null
                closed_at: null
                created_at: "2026-06-19T10:30:00.000Z"
                updated_at: "2026-06-19T10:30:00.000Z"
        "400":
          $ref: "#/components/responses/400BadRequest"

    get:
      tags: [Sessions]
      summary: "查询会话列表"
      description: "分页查询会话列表，可按状态筛选"
      operationId: listSessions
      parameters:
        - name: status
          in: query
          schema:
            $ref: "#/components/schemas/SessionStatus"
        - name: user_id
          in: query
          schema:
            type: string
          description: "按用户筛选"
        - $ref: "#/components/parameters/PaginationLimit"
        - $ref: "#/components/parameters/PaginationOffset"
      responses:
        "200":
          description: "会话列表"
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    type: array
                    items:
                      $ref: "#/components/schemas/Session"
                  pagination:
                    $ref: "#/components/schemas/Pagination"

  /sessions/{session_id}:
    get:
      tags: [Sessions]
      summary: "获取会话详情"
      description: "获取指定会话的完整信息，包含问诊进度、已采集字段摘要"
      operationId: getSession
      parameters:
        - $ref: "#/components/parameters/SessionIdParam"
      responses:
        "200":
          description: "会话详情"
          content:
            application/json:
              schema:
                allOf:
                  - $ref: "#/components/schemas/Session"
                  - type: object
                    properties:
                      medical_record_summary:
                        $ref: "#/components/schemas/MedicalRecordSummary"
                      message_count:
                        type: integer
                        example: 8
              example:
                id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
                user_id: "anon_7f3a9b2c"
                status: "active"
                intent: "diagnosis"
                current_stage: "collect"
                red_flag_raised: false
                round_count: 2
                max_rounds: 5
                medical_record_summary:
                  session_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
                  version: 3
                  completion_level: "partial"
                  chief_complaint: "头痛"
                  duration: "2天"
                  location: "前额"
                  severity: 7
                  accompanying_symptoms: ["低烧", "恶心"]
                  collected_fields:
                    - "patient_info.chief_complaint"
                    - "patient_info.complaint_duration"
                    - "patient_info.complaint_location"
                    - "patient_info.severity"
                    - "accompanying_symptoms"
                  missing_core_fields:
                    - "past_history.chronic_diseases"
                    - "allergy_history.drug_allergies"
                message_count: 8
                close_reason: null
                closed_at: null
                created_at: "2026-06-19T10:30:00.000Z"
                updated_at: "2026-06-19T10:32:00.000Z"
        "404":
          $ref: "#/components/responses/404NotFound"

    patch:
      tags: [Sessions]
      summary: "更新会话状态"
      description: |
        更新会话的状态或参数。

        **典型场景：**
        - 用户主动结束问诊：`{"status": "completed"}`
        - 用户暂停会话：`{"status": "paused"}`
        - 调整最大问诊轮次：`{"max_rounds": 3}`
      operationId: updateSession
      parameters:
        - $ref: "#/components/parameters/SessionIdParam"
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/UpdateSessionRequest"
            examples:
              pause:
                summary: "暂停会话"
                value:
                  status: "paused"
              complete:
                summary: "提前结束问诊"
                value:
                  status: "completed"
              adjust_rounds:
                summary: "调整最大轮次"
                value:
                  max_rounds: 3
      responses:
        "200":
          description: "更新后的会话"
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Session"
        "404":
          $ref: "#/components/responses/404NotFound"
        "409":
          $ref: "#/components/responses/409Conflict"

    delete:
      tags: [Sessions]
      summary: "删除会话"
      description: "删除指定会话及其关联的所有消息、病历、诊断数据（级联删除）"
      operationId: deleteSession
      parameters:
        - $ref: "#/components/parameters/SessionIdParam"
      responses:
        "204":
          description: "删除成功，无响应体"
        "404":
          $ref: "#/components/responses/404NotFound"

  # ==========================================================
  # 消息与对话
  # ==========================================================
  /sessions/{session_id}/messages:
    post:
      tags: [Messages]
      summary: "发送用户消息（核心交互入口）"
      description: |
        向指定会话发送用户消息，触发Agent链处理。返回同步响应 + 建议连接SSE获取后续内容。

        ## 处理流程
        1. 接收消息 → PII脱敏
        2. 红旗关键词检测
        3. 若触发红旗 → 返回 emergency_interrupted (code=200, red_flag_raised=true)
        4. 若未触发 → MasterAgent路由 → 问诊/问答/紧急
        5. 返回同步响应 + next_action

        ## next_action 说明
        | 值 | 含义 | 后续操作 |
        |----|------|---------|
        | continue | 问诊进行中 | 连接SSE获取下一个问题 |
        | diagnosis_ready | 信息充足 | 连接SSE获取诊断报告 |
        | emergency_interrupted | 红旗触发 | 会话已终止，读取emergency消息 |
        | completed | 问答/诊断完成 | 读取消息历史获取完整回答 |
      operationId: sendMessage
      parameters:
        - $ref: "#/components/parameters/SessionIdParam"
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/SendMessageRequest"
            examples:
              initial_symptom:
                summary: "初次症状描述"
                value:
                  content: "我头痛两天了，前额位置，大概7分痛，还有点低烧"
                  content_type: "text"
              follow_up:
                summary: "追问回答"
                value:
                  content: "没有呕吐，也没有高血压，就是对青霉素过敏"
                  content_type: "text"
              red_flag_example:
                summary: "🚩红旗症状（触发紧急中断）"
                value:
                  content: "我胸口剧痛，呼吸困难，左手臂发麻"
                  content_type: "text"
      responses:
        "200":
          description: "消息接收成功，返回处理结果快照"
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/SendMessageResponse"
              examples:
                diagnosis_continue:
                  summary: "问诊进行中"
                  value:
                    message:
                      id: "m1-uuid"
                      session_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
                      round_number: 1
                      role: "user"
                      content: "我头痛两天了，前额位置，大概7分痛，还有点低烧"
                      content_type: "text"
                      agent_source: null
                      token_count: null
                      created_at: "2026-06-19T10:30:05.000Z"
                    session_status: "active"
                    current_stage: "collect"
                    red_flag_raised: false
                    round_count: 1
                    collected_fields_summary:
                      chief_complaint: "头痛"
                      duration: "2天"
                      location: "前额"
                      severity: 7
                    next_action: "continue"
                emergency_interrupted:
                  summary: "🚩红旗触发"
                  value:
                    message:
                      id: "m2-uuid"
                      session_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
                      round_number: 0
                      role: "user"
                      content: "我胸口剧痛，呼吸困难，左手臂发麻"
                      content_type: "text"
                      agent_source: null
                      token_count: null
                      created_at: "2026-06-19T10:31:00.000Z"
                    session_status: "emergency_terminated"
                    current_stage: "emergency"
                    red_flag_raised: true
                    round_count: 0
                    collected_fields_summary: {}
                    next_action: "emergency_interrupted"
                diagnosis_ready:
                  summary: "信息充足，即将诊断"
                  value:
                    message:
                      id: "m3-uuid"
                      session_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
                      round_number: 3
                      role: "user"
                      content: "没有呕吐，就是对青霉素过敏"
                      content_type: "text"
                      agent_source: null
                      token_count: null
                      created_at: "2026-06-19T10:35:00.000Z"
                    session_status: "active"
                    current_stage: "diagnose"
                    red_flag_raised: false
                    round_count: 3
                    collected_fields_summary:
                      chief_complaint: "头痛"
                      duration: "2天"
                      location: "前额"
                      severity: 7
                      accompanying_symptoms: ["低烧"]
                      drug_allergies: ["青霉素"]
                    next_action: "diagnosis_ready"
        "400":
          $ref: "#/components/responses/400BadRequest"
        "404":
          $ref: "#/components/responses/404NotFound"
        "409":
          $ref: "#/components/responses/409Conflict"

    get:
      tags: [Messages]
      summary: "获取消息历史"
      description: "分页获取指定会话的对话消息历史，按时间正序排列"
      operationId: listMessages
      parameters:
        - $ref: "#/components/parameters/SessionIdParam"
        - name: round_number
          in: query
          schema:
            type: integer
          description: "按轮次筛选（可选）"
        - $ref: "#/components/parameters/PaginationLimit"
        - $ref: "#/components/parameters/PaginationOffset"
      responses:
        "200":
          description: "消息列表"
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    type: array
                    items:
                      $ref: "#/components/schemas/Message"
                  pagination:
                    $ref: "#/components/schemas/Pagination"
        "404":
          $ref: "#/components/responses/404NotFound"

  # ==========================================================
  # SSE 流式事件推送
  # ==========================================================
  /sessions/{session_id}/stream:
    get:
      tags: [Streaming]
      summary: "SSE流式事件推送"
      description: |
        建立 Server-Sent Events 长连接，接收该会话的实时事件流。

        ## 连接时机
        在 `POST /sessions/{id}/messages` 获得 `next_action` 后立即连接。

        ## 事件类型路由表
        | event.type | 触发条件 | 行为 |
        |------------|---------|------|
        | `heartbeat` | 每15秒无事件时 | 保持连接，无操作 |
        | `message` | 问诊Agent生成提问 / 直接回答 | 展示问题或回答（支持流式增量） |
        | `diagnosis_progress` | 诊断Agent开始推理 | 更新进度条 |
        | `diagnosis_complete` | 诊断完成+Schema校验通过 | 展示完整诊断报告 |
        | `emergency` | 任意阶段红旗触发 | **立即展示急救指引，关闭连接** |
        | `error` | 处理异常 | 展示错误信息，尝试重连 |

        ## 客户端示例 (JavaScript)
        ```javascript
        const evtSource = new EventSource(`/api/v1/sessions/${sessionId}/stream`);
        
        evtSource.addEventListener('message', (e) => {
          const data = JSON.parse(e.data);
          // 追加消息文本到对话界面
          appendMessage(data.content);
        });
        
        evtSource.addEventListener('diagnosis_progress', (e) => {
          const data = JSON.parse(e.data);
          // 更新诊断进度条: data.progress%
          updateProgress(data.stage_description, data.progress);
        });
        
        evtSource.addEventListener('diagnosis_complete', (e) => {
          const data = JSON.parse(e.data);
          // 渲染完整诊断报告
          renderDiagnosisReport(data.result);
          evtSource.close();
        });
        
        evtSource.addEventListener('emergency', (e) => {
          const data = JSON.parse(e.data);
          // 立即展示急救指引并锁定界面
          showEmergencyGuidance(data);
          evtSource.close();
        });
        
        evtSource.addEventListener('error', (e) => {
          const data = JSON.parse(e.data);
          showError(data.message);
        });
        ```
      operationId: streamEvents
      parameters:
        - $ref: "#/components/parameters/SessionIdParam"
      responses:
        "200":
          description: "SSE事件流"
          content:
            text/event-stream:
              schema:
                type: string
                description: "SSE事件流，每行格式: `event: {type}\\ndata: {json}\\n\\n`"
              examples:
                message_event:
                  summary: "问诊提问事件"
                  value: |
                    event: message
                    data: {"type":"message","role":"assistant","content":"您的头痛持续多久了？具体在哪个位置？","content_type":"question","agent_source":"interview","round_number":1}

                diagnosis_progress_event:
                  summary: "诊断进度事件"
                  value: |
                    event: diagnosis_progress
                    data: {"type":"diagnosis_progress","stage":"evidence_matching","progress":20,"stage_description":"正在匹配医学证据..."}

                    event: diagnosis_progress
                    data: {"type":"diagnosis_progress","stage":"differential_gen","progress":50,"stage_description":"生成鉴别诊断..."}

                    event: diagnosis_progress
                    data: {"type":"diagnosis_progress","stage":"recommendation","progress":90,"stage_description":"生成就医建议..."}

                diagnosis_complete_event:
                  summary: "诊断完成事件"
                  value: |
                    event: diagnosis_complete
                    data: {"type":"diagnosis_complete","result":{"primary_diagnosis":{"name":"紧张性头痛","probability":"60%","rationale":"前额压迫性头痛+工作压力诱因，倾向于考虑紧张性头痛","certainty_level":"medium"},"differential_diagnosis":[{"name":"偏头痛","probability":"30%","key_evidence":"中度疼痛+恶心","exclusion_criteria":"无搏动性+无先兆"}],"risk_assessment":{"severity":"中度","urgency":"建议门诊","warning_signs":["体温超过38.5℃","剧烈呕吐","颈部僵硬"]},"recommendations":[{"category":"居家护理","content":"适当休息，避免强光和噪音刺激","priority":1},{"category":"用药建议","content":"可考虑布洛芬等非处方止痛药（确认无禁忌症后使用）","priority":2},{"category":"就医建议","content":"如3天内无缓解，建议神经内科门诊","priority":3}],"red_flags":[{"symptom":"体温超过38.5℃伴剧烈头痛","action":"立即急诊就医"},{"symptom":"意识模糊或颈部僵硬","action":"立即拨打120"}],"references":[{"knowledge_entry_id":"ke-uuid-1","title":"紧张性头痛诊疗指南","source":"中华医学会神经病学分会","year":2023,"url":null,"relevance_score":0.92}],"disclaimer":"本内容仅供参考，不能替代专业医疗诊断。如有不适，请及时就医。"}}

                emergency_event:
                  summary: "🚩紧急事件"
                  value: |
                    event: emergency
                    data: {"type":"emergency","action":"call_120","guidance":"您描述的症状（胸痛、呼吸困难、左臂麻木）可能提示急性心肌梗死，请立即拨打120急救电话，保持安静，不要自行驾车就医。在等待救护车期间，如手边有阿司匹林可嚼服300mg（确认无过敏史）。","red_flags":["胸痛","呼吸困难","左臂麻木"],"disclaimer":"本系统为AI辅助工具，此急救指引为自动触发。请立即拨打120寻求专业急救。"}

                heartbeat_event:
                  summary: "心跳保活"
                  value: |
                    event: heartbeat
                    data: {"type":"heartbeat","timestamp":"2026-06-19T10:30:15.000Z"}

                error_event:
                  summary: "错误事件"
                  value: |
                    event: error
                    data: {"type":"error","code":"LLM_TIMEOUT","message":"AI服务响应超时，正在重试..."}

        "404":
          $ref: "#/components/responses/404NotFound"

  # ==========================================================
  # 诊断管理
  # ==========================================================
  /sessions/{session_id}/diagnosis:
    get:
      tags: [Diagnosis]
      summary: "获取诊断报告"
      description: |
        获取指定会话的诊断报告。仅当诊断已完成时返回结果。

        **注意：** 此接口仅返回已生成的诊断报告快照。实时诊断进度请通过SSE获取。
      operationId: getDiagnosis
      parameters:
        - $ref: "#/components/parameters/SessionIdParam"
      responses:
        "200":
          description: "诊断报告"
          content:
            application/json:
              schema:
                type: object
                properties:
                  session_id:
                    type: string
                    format: uuid
                  status:
                    type: string
                    enum: [not_available, in_progress, completed, emergency_interrupted]
                    description: >
                      not_available: 会话非诊断意图
                      in_progress: 诊断进行中 (建议连接SSE)
                      completed: 诊断完成
                      emergency_interrupted: 紧急中断 (使用诊断结果中的安全建议)
                  result:
                    $ref: "#/components/schemas/DiagnosisReport"
                  schema_version:
                    type: string
                  schema_validated:
                    type: boolean
                  fallback_triggered:
                    type: boolean
                  citation_count:
                    type: integer
                  created_at:
                    type: string
                    format: date-time
              examples:
                completed:
                  summary: "诊断已完成"
                  value:
                    session_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
                    status: "completed"
                    result:
                      primary_diagnosis:
                        name: "紧张性头痛"
                        probability: "60%"
                        rationale: "前额压迫性头痛+工作压力诱因，倾向于考虑紧张性头痛"
                        certainty_level: "medium"
                      differential_diagnosis:
                        - name: "偏头痛"
                          probability: "30%"
                          key_evidence: "中度疼痛+恶心"
                          exclusion_criteria: "无搏动性特征+无视觉先兆"
                      risk_assessment:
                        severity: "中度"
                        urgency: "建议门诊"
                        warning_signs:
                          - "体温超过38.5℃"
                          - "剧烈呕吐"
                          - "颈部僵硬"
                      recommendations:
                        - category: "居家护理"
                          content: "适当休息，避免强光和噪音刺激"
                          priority: 1
                        - category: "用药建议"
                          content: "可考虑布洛芬等非处方止痛药（确认无禁忌症后使用）"
                          priority: 2
                      red_flags:
                        - symptom: "体温超过38.5℃伴剧烈头痛"
                          action: "立即急诊就医"
                      references:
                        - knowledge_entry_id: "ke-uuid-1"
                          title: "紧张性头痛诊疗指南"
                          source: "中华医学会神经病学分会"
                          year: 2023
                          relevance_score: 0.92
                      disclaimer: "本内容仅供参考，不能替代专业医疗诊断。如有不适，请及时就医。"
                    schema_version: "1.0"
                    schema_validated: true
                    fallback_triggered: false
                    citation_count: 3
                    created_at: "2026-06-19T10:36:00.000Z"
                in_progress:
                  summary: "诊断进行中"
                  value:
                    session_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
                    status: "in_progress"
                    result: null
                    schema_version: null
                    schema_validated: null
                    fallback_triggered: null
                    citation_count: null
                    created_at: null
        "404":
          $ref: "#/components/responses/404NotFound"

  # ==========================================================
  # 安全管理
  # ==========================================================
  /sessions/{session_id}/safety:
    get:
      tags: [Safety]
      summary: "获取会话安全事件列表"
      description: "查询指定会话的所有安全相关事件（红旗触发、内容过滤、脱敏记录等）"
      operationId: listSafetyEvents
      parameters:
        - $ref: "#/components/parameters/SessionIdParam"
        - name: category
          in: query
          schema:
            type: string
            enum: [red_flag, pii_detected, content_filtered, fallback, schema_rejected]
          description: "按事件分类筛选"
        - $ref: "#/components/parameters/PaginationLimit"
        - $ref: "#/components/parameters/PaginationOffset"
      responses:
        "200":
          description: "安全事件列表"
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    type: array
                    items:
                      $ref: "#/components/schemas/SafetyEvent"
                  pagination:
                    $ref: "#/components/schemas/Pagination"
                  summary:
                    type: object
                    properties:
                      total_events:
                        type: integer
                      red_flag_count:
                        type: integer
                      pii_detection_count:
                        type: integer
        "404":
          $ref: "#/components/responses/404NotFound"

  # ==========================================================
  # 知识检索 (独立接口)
  # ==========================================================
  /knowledge:
    get:
      tags: [Knowledge]
      summary: "知识库搜索"
      description: |
        独立的知识库搜索接口，不依赖会话上下文。用于用户直接查询医学知识。

        **注意：** 此接口返回原始知识片段，不经过诊断Agent推理。
      operationId: searchKnowledge
      parameters:
        - name: q
          in: query
          required: true
          schema:
            type: string
            minLength: 1
            maxLength: 500
          description: "搜索查询"
          example: "紧张性头痛的诊断标准"
        - name: source_type
          in: query
          schema:
            type: string
            enum: [guideline, consensus, textbook, review, case_report]
          description: "按来源类型筛选"
        - name: min_authority
          in: query
          schema:
            type: number
            minimum: 0
            maximum: 1
            default: 0.0
          description: "最低权威性评分阈值"
        - $ref: "#/components/parameters/PaginationLimit"
        - $ref: "#/components/parameters/PaginationOffset"
      responses:
        "200":
          description: "搜索结果"
          content:
            application/json:
              schema:
                type: object
                properties:
                  query:
                    type: string
                    description: "原始查询词"
                  rewritten_query:
                    type: string
                    description: "标准化改写后的查询词"
                    example: "紧张性头痛 诊断标准 临床指南"
                  data:
                    type: array
                    items:
                      $ref: "#/components/schemas/KnowledgeSearchResult"
                  pagination:
                    $ref: "#/components/schemas/Pagination"
        "400":
          $ref: "#/components/responses/400BadRequest"
```

---

## 4. 接口详细说明

### 4.1 会话管理

#### POST /sessions — 创建会话

**功能：** 创建一次新的问诊/问答会话。

**调用时机：**
- 用户首次进入系统
- 用户主动发起新咨询
- 上一会话已完成/终止后开启新会话

**请求示例：**
```bash
curl -X POST http://localhost:8000/api/v1/sessions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d '{
    "user_id": "anon_7f3a9b2c",
    "max_rounds": 5,
    "metadata": {"client": "web", "source": "direct"}
  }'
```

**响应码：**
| 状态码 | 含义 |
|--------|------|
| 201 | 会话创建成功 |
| 400 | 请求参数无效 |

---

#### GET /sessions — 会话列表

**功能：** 分页查询会话列表，支持按状态和用户筛选。

**查询参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `status` | string | 否 | 按状态筛选 |
| `user_id` | string | 否 | 按用户筛选 |
| `limit` | integer | 否 | 每页条数 (默认20, 最大100) |
| `offset` | integer | 否 | 偏移量 (默认0) |

---

#### GET /sessions/{session_id} — 会话详情

**功能：** 获取会话完整信息 + 当前病历采集摘要。

**关键字段：**
- `medical_record_summary`：已采集字段摘要 + 缺失核心字段列表
- `message_count`：消息总数

---

#### PATCH /sessions/{session_id} — 更新会话

**功能：** 更新会话状态或参数。

**允许的状态转换：**

| 当前状态 | 可用操作 |
|---------|---------|
| `active` | → paused (暂停), → completed (用户主动结束) |
| `paused` | → active (app通过发消息自动恢复，无需手动PATCH) |
| `completed` | 不可变更 |
| `emergency_terminated` | 不可变更 |

---

#### DELETE /sessions/{session_id} — 删除会话

**功能：** 级联删除会话及所有关联数据。

**级联删除范围：**
- messages (ON DELETE CASCADE)
- medical_records (ON DELETE CASCADE)
- diagnosis_results (ON DELETE CASCADE)
- diagnosis_citations (ON DELETE CASCADE)
- audit_logs (ON DELETE CASCADE)
- safety_events (ON DELETE CASCADE)

---

### 4.2 消息与对话

#### POST /sessions/{session_id}/messages — 核心交互入口

**这是整个系统最关键的API接口。** 所有用户输入通过此接口进入系统。

**处理流水线：**

```
POST /sessions/{id}/messages
    │
    ▼
PII脱敏 (姓名/身份证/手机→占位符)
    │
    ▼
红旗关键词检测
    ├── 触发 → 返回 next_action="emergency_interrupted"
    │              会话标记 emergency_terminated
    │              后续SSE推送 emergency 事件
    │
    └── 未触发 → MasterAgent意图识别
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
    diagnosis   question    greeting/status
        │           │           │
        ▼           ▼           ▼
    启动问诊      搜索+回答    直接响应
    返回next_action="continue" / "diagnosis_ready" / "completed"
```

**next_action 客户端处理逻辑：**

```
next_action 值                   客户端行为
───────────────────────────────────────────────────
"continue"             → 连接SSE，监听 message 事件获取下一轮提问
"diagnosis_ready"      → 连接SSE，监听 diagnosis_progress + diagnosis_complete
"emergency_interrupted" → 读取消息历史获取 emergency_guide，锁定输入
"completed"            → 读取消息历史获取最终回答
```

---

#### GET /sessions/{session_id}/messages — 消息历史

**功能：** 分页拉取指定会话的所有消息。

**排序：** 按 `created_at` 正序（最早消息在前）

---

### 4.3 流式事件推送 (SSE)

#### GET /sessions/{session_id}/stream — SSE连接

**连接生命周期：**

```
客户端连接 SSE
    │
    ├── 每15秒: heartbeat 事件 (保活)
    │
    ├── 问诊阶段: message 事件 (1-N次，每次一个新提问)
    │
    ├── 诊断阶段: diagnosis_progress 事件 (多次，进度20%→50%→90%)
    │            diagnosis_complete 事件 (1次，最终报告)
    │
    ├── 任意时刻: emergency 事件 (红旗触发，连接关闭)
    │
    └── 异常:     error 事件 (错误通知，客户端决定重连)
```

**SSE 事件类型完整路由表：**

| event | 触发Agent | 触发时机 | payload | 客户端行为 |
|-------|----------|---------|---------|-----------|
| `heartbeat` | Server | 15秒无事件 | `{type, timestamp}` | 忽略，保活 |
| `message` | InterviewAgent / MasterAgent | 生成新提问或直接回答 | `{type, role, content, ...}` | 追加到对话界面 |
| `message` (流式) | InterviewAgent / MasterAgent | 流式增量token | `{type, role, content, ...}` | 追加/更新消息文本 |
| `diagnosis_progress` | DiagnosisAgent | 诊断子阶段变更 | `{type, stage, progress}` | 更新进度条UI |
| `diagnosis_complete` | DiagnosisAgent | 诊断完成+校验通过 | `{type, result: DiagnosisReport}` | 渲染报告，关闭连接 |
| `emergency` | MasterAgent | 任意阶段红旗触发 | `{type, action, guidance, red_flags}` | **展示急救指引，锁定界面** |
| `error` | Any | 处理异常 | `{type, code, message}` | 展示错误，可重连 |

---

### 4.4 诊断管理

#### GET /sessions/{session_id}/diagnosis — 获取诊断报告

**status字段说明：**

| status | 含义 | 说明 |
|--------|------|------|
| `not_available` | 不可用 | 当前会话非诊断意图(如纯问答) |
| `in_progress` | 生成中 | 诊断未完成，result=null，建议连接SSE |
| `completed` | 已完成 | 诊断就绪，result含完整报告 |
| `emergency_interrupted` | 紧急中断 | 红旗触发，诊断未生成，使用result中的安全建议 |

---

### 4.5 安全事件

#### GET /sessions/{session_id}/safety — 安全事件列表

**用途：** 合规审查、安全监控、问题追溯。

**响应summary统计：**
```json
{
  "total_events": 5,
  "red_flag_count": 0,
  "pii_detection_count": 2
}
```

---

### 4.6 知识检索

#### GET /knowledge — 知识库搜索

**独立于会话的知识检索接口**，用于用户直接查询医学知识。

**参数说明：**
| 参数 | 说明 |
|------|------|
| `q` | 必填，搜索查询词（口语亦可，接口内自动术语标准化） |
| `source_type` | 按来源类型筛选 |
| `min_authority` | 最低权威性评分阈值（0.0-1.0），默认0.0 |
| `limit` / `offset` | 分页参数 |

---

## 5. 数据流示例

### 5.1 完整问诊→诊断流程

```
时间轴 (客户端视角)
─────────────────────────────────────────────────────────→

[1] POST /sessions
    ──→ 201 { session_id: "s1" }

[2] POST /sessions/s1/messages  { content: "我头痛两天了" }
    ──→ 200 { next_action: "continue" }

[3] GET /sessions/s1/stream
    ──→ SSE: 
        event: message
        data: {"type":"message","role":"assistant","content":"您头痛的具体位置在哪里？","agent_source":"interview","round_number":1}

[4] POST /sessions/s1/messages  { content: "前额位置" }
    ──→ 200 { next_action: "continue" }

[5] (SSE继续接收)
        event: message
        data: {"type":"message","role":"assistant","content":"疼痛程度1-10分打几分？有没有发烧？","round_number":2}

[6] POST /sessions/s1/messages  { content: "7分，有点低烧37.8" }
    ──→ 200 { next_action: "continue" }

[7] (SSE继续接收)
        event: message
        data: {"type":"message","role":"assistant","content":"有没有恶心呕吐？有没有高血压或药物过敏？","round_number":3}

[8] POST /sessions/s1/messages  { content: "有点恶心，对青霉素过敏" }
    ──→ 200 { next_action: "diagnosis_ready" }

[9] (SSE接收诊断事件)
        event: diagnosis_progress
        data: {"type":"diagnosis_progress","stage":"evidence_matching","progress":20}

        event: diagnosis_progress
        data: {"type":"diagnosis_progress","stage":"differential_gen","progress":50}

        event: diagnosis_progress
        data: {"type":"diagnosis_progress","stage":"recommendation","progress":90}

        event: diagnosis_complete
        data: {"type":"diagnosis_complete","result":{...完整诊断报告...}}

[10] (SSE连接关闭 / 客户端主动关闭)

[11] GET /sessions/s1/diagnosis
     ──→ 200 (获取诊断报告快照，用于持久展示/分享)
```

### 5.2 紧急中断流程

```
[1] POST /sessions/s1/messages
    { content: "胸口剧痛，喘不上气，左手臂发麻" }
    
    ──→ 200 {
          "next_action": "emergency_interrupted",
          "red_flag_raised": true,
          "session_status": "emergency_terminated"
        }

[2] GET /sessions/s1/stream
    ──→ SSE:
        event: emergency
        data: {
          "type": "emergency",
          "action": "call_120",
          "guidance": "您描述的症状可能提示急性心肌梗死，请立即拨打120...",
          "red_flags": ["胸痛", "呼吸困难", "左臂麻木"],
          "disclaimer": "本系统为AI辅助工具..."
        }
    
    (连接自动关闭)

[3] 客户端锁定输入界面，展示急救指引
```

### 5.3 会话恢复流程

```
[1] GET /sessions/s1
    ──→ 200 { status: "paused", current_stage: "collect", round_count: 2 }

[2] POST /sessions/s1/messages  { content: "刚才断线了，我继续回答..." }
    ──→ 200 { next_action: "continue" }

[3] GET /sessions/s1/stream
    (恢复SSE连接，继续接收问诊事件)
```

---

## 6. 安全设计

### 6.1 认证

初期可选 `X-API-Key` 头部认证，生产环境必填。

```
X-API-Key: mqa_live_7f3a9b2c...
```

### 6.2 PII 处理保证

| 保证项 | 实现方式 |
|--------|---------|
| **输入脱敏前置** | `POST /messages` 入口层即完成PII检测与脱敏，脱敏后的文本才进入LangGraph |
| **数据库不存原始PII** | `messages.content` 存脱敏后文本；`messages.content_raw_encrypted` 加密存储，30天自动清除 |
| **审计日志不含PII** | `audit_logs.input_summary` 仅存储脱敏后摘要 |

### 6.3 红旗响应保证

- 红旗触发后，`session.status` 立即变为 `emergency_terminated`
- 后续对该会话的 `POST /messages` 请求返回 **409 Conflict**
- SSE 连接在推送 `emergency` 事件后**服务器主动关闭**

### 6.4 错误码清单

| 错误码 | HTTP状态 | 含义 |
|--------|---------|------|
| `VALIDATION_ERROR` | 400 | 请求参数校验失败 |
| `SESSION_NOT_FOUND` | 404 | 会话不存在 |
| `SESSION_TERMINATED` | 409 | 会话已终止(紧急/超时)，不可操作 |
| `DIAGNOSIS_NOT_READY` | 404 | 诊断尚未生成 |
| `RED_FLAG_BLOCKED` | 409 | 红旗触发，操作被拒绝 |
| `RATE_LIMITED` | 429 | 请求频率超限 |
| `LLM_TIMEOUT` | 502 | LLM调用超时 |
| `LLM_ERROR` | 502 | LLM调用异常 |
| `VECTOR_STORE_ERROR` | 502 | 向量数据库异常 |
| `INTERNAL_ERROR` | 500 | 内部错误 |

---

## 附录 A. 状态码速查

| 状态码 | 含义 | 使用场景 |
|--------|------|---------|
| 200 | OK | 请求成功，含响应体 |
| 201 | Created | 会话创建成功 |
| 204 | No Content | 删除成功，无响应体 |
| 400 | Bad Request | 参数校验失败 |
| 401 | Unauthorized | API密钥无效 |
| 404 | Not Found | 资源不存在 |
| 409 | Conflict | 状态冲突（会话已终止等） |
| 429 | Too Many Requests | 频率限制 |
| 500 | Internal Server Error | 服务器内部错误 |
| 502 | Bad Gateway | 上游服务异常(LLM/pgvector (PostgreSQL 扩展)) |

## 附录 B. 与架构文档的追溯

| 架构文档/PRD | 本API |
|-------------|-------|
| §3.1 用户交互模块 — 多轮对话 | POST /messages + SSE message事件 |
| §3.1 状态感知 — "收集了哪些信息" | GET /sessions/{id} → medical_record_summary |
| §3.1 紧急中断 | POST /messages → next_action=emergency_interrupted + SSE emergency事件 |
| §3.2 知识检索模块 | GET /knowledge |
| §3.3 诊断输出模块 | GET /sessions/{id}/diagnosis + SSE diagnosis_complete事件 |
| §3.4 会话持久化 | Session CRUD + GET /messages历史 |
| §4.3.3 流式输出 | SSE text/event-stream |
| §8 安全架构 | PII脱敏入口层 + 红旗检测 + 409阻断 |

---

> **文档维护者：** 开发团队
> **最后更新：** 2026-06-19
> **下一阶段：** DDD — 聚合根、Repository接口与应用服务设计
