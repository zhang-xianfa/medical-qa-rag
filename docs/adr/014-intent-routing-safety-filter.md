# ADR-014: 意图路由与安全前置过滤规范

## 状态
已采纳

## 背景
ADR-012 定义了通用 Agent State，ADR-013 定义了场景配置规范，但多场景自动分发缺少统一的入口契约。若路由判断由 LLM 承担，存在以下风险：(1) 高危急诊请求可能被 LLM 语义误解而漏过；(2) 路由结果不可审计、不可复现；(3) 同一 LLM 同时负责路由与医疗建议生成违反安全分层原则。本 ADR 定义确定性的两级路由与安全前置过滤契约，确保路由层可审计、可干预、可回放。

## 决策
采用 **L0 确定性规则引擎 + L1 受控分类模型** 的两级路由架构。L0 为纯正则/关键词匹配，零 LLM 依赖，负责拦截高危请求并直接返回急诊指引。L1 使用独立 LLM 调用进行意图分类与场景匹配，受置信度阈值约束。两个层级均输出结构化 JSON，**路由 LLM 与后续医疗 Agent LLM 必须为独立上下文，禁止共享 Prompt 或 Session**。

```
用户输入
    │
    ▼
┌─────────────────────────────────┐
│ L0: 确定性规则引擎                │
│ - 急诊关键词正则匹配              │
│ - 自伤/自杀意图检测              │
│ - PII 脱敏                       │
│                                  │
│ 命中 → 直接返回急诊指引, 日志记录  │
│ 未命中 ↓                         │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ L1: 受控分类模型                  │
│ - 独立 LLM 调用 (与医疗 Agent 隔离)│
│ - 意图分类 → scenario_id          │
│ - 置信度评分                      │
│                                  │
│ 置信度 ≥ 阈值 → 注入 scenario_context │
│ 置信度 < 阈值 → 兜底流程           │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ Agent 运行时                      │
│ State.scenario_context ← 路由输出 │
│ State.collected_facts ← {}      │
│ State.conversation_stage ← init  │
└─────────────────────────────────┘
```

## L0 安全前置过滤规范

### 规则定义
L0 层规则必须是**纯字符串匹配或正则表达式**，不依赖任何模型推理。规则存储在 `config/safety_rules.yaml` 中，由 `backend/safety/red_flag_detector.py` 加载执行。

### 规则分类

| 类别 | 匹配方式 | 命中行为 | 是否可被后续对话恢复 |
|------|---------|---------|-------------------|
| 急诊体征 | 正则关键词 | 输出急诊指引 + `is_emergency=true` + `red_flag_level="CRITICAL"` | 否，会话标记为 `emergency_terminated` |
| 自伤/自杀意图 | 正则关键词 | 输出危机干预指引 + `is_emergency=true` + `red_flag_level="CRITICAL"` | 否 |
| 中毒/过量服药 | 正则关键词 | 输出中毒急救指引 + `is_emergency=true` + `red_flag_level="CRITICAL"` | 否 |
| 违法/违规请求 | 正则关键词 | 输出合规声明 + `red_flag_level="HIGH"`，终止会话 | 否 |
| 非医疗类闲聊 | 关键词白名单 | 礼貌引导至医疗场景 + `red_flag_level="MEDIUM"` | 是，引导后可继续 |
| PII 检测 | 正则匹配 | 自动脱敏后放行 | 是 |
<!-- AUDIT-FIX: TC-003 / 审计补充建议3a -->

### 规则维护机制
- 新增急诊关键词：临床顾问提交 → 安全团队审核 → 更新 `safety_rules.yaml` → 回归测试
- 关键词库版本化管理，每次变更记录 ADR 编号
- 每周抽检 L0 命中日志，防止过度拦截或漏拦截

### 场景规则注入 L0 机制
L0 规则引擎加载两类规则，按优先级合并执行：
1. **全局规则**：`config/safety_rules.yaml` 中定义，对所有场景生效，由安全团队维护
2. **场景特有规则**：位于各场景配置文件 `safety_rules.scenario_specific` 列表中引用的规则集，存储于 `config/safety_rules/{rule_set_id}.yaml`，由场景配置间接引用
3. **合并策略**：全局规则与已路由场景的场景特有规则取**并集**执行。全局规则始终生效；场景特有规则仅在 `scenario_context` 注入后激活。若全局规则与场景规则存在关键词重叠，取两者中更严格的匹配阈值（即任意一方命中即触发）
4. **未路由时**：L0 仅执行全局规则。L1 路由成功后，L2 Agent 初始化时加载对应场景的特有规则并补充到 L0 引擎的规则集缓存中（会话级）
<!-- AUDIT-FIX: TC-001 / 待澄清项A1 -->

### 规则生效机制
- **全局规则**（`config/safety_rules.yaml`）：启动时加载到内存。运行时通过文件监听（监听间隔 30s）热加载，无需重启服务。灰度期间若检测到热加载后异常率上升，自动回滚到上一版本规则快照并触发告警。
- **场景特有规则**（`config/safety_rules/{rule_set_id}.yaml`）：在 L1 路由成功、首次注入 `scenario_context` 时懒加载到会话级 L0 缓存。同一场景的后续消息复用缓存。场景规则变更后，新建会话使用新规则，已有会话沿用旧规则（会话级不可变性）。
<!-- AUDIT-FIX: TC-024 / 待澄清项A4 -->

### 命中后的强制响应模板

```
【系统自动安全响应 - 不可由用户指令覆盖】

检测到您描述的情况可能属于医疗急症。请立即采取以下行动：

1. 立即拨打 120 急救电话
2. 保持镇静，采取 [具体急救体位/行动]
3. 不要自行驾车就医，等待专业急救人员到达

本系统已自动终止当前咨询，请立即就医。

[系统记录：会话ID={session_id} | 触发规则={rule_id} | 时间={timestamp}]
```

### 日志记录要求
- 每次 L0 命中必须记录：`session_id`、`rule_id`、`matched_keyword`、`user_input_snippet`（脱敏后）、`timestamp`
- 日志写入 `audit_logs` 表，`event_type="safety_intercept"`，`red_flag_triggered=TRUE`
- L0 命中率作为独立 KPI 监控：`L0 命中次数 / 总会话数`

## L1 意图路由契约

### 输入 Schema

```json
{
  "user_message": "用户原始输入（经L0脱敏后）",
  "conversation_history": ["前序消息摘要（最近3轮）"],
  "available_scenarios": [
    {
      "scenario_id": "general_consultation",
      "display_name": "通用健康咨询",
      "description": "面向常见不适症状的通用问诊场景"
    }
  ],
  "routing_context": {
    "source": "direct_chat",
    "max_scenarios_to_return": 3
  }
}
```

### 输出 Schema

```json
{
  "primary_scenario": {
    "scenario_id": "pediatric_fever_care",
    "confidence": 0.92,
    "rationale": "用户提到'孩子'和'发烧'"
  },
  "alternative_scenarios": [
    {
      "scenario_id": "general_consultation",
      "confidence": 0.35,
      "rationale": "备选通用分诊"
    }
  ],
  "intent_category": "pediatric_care",
  "is_emergency": false,
  "requires_human_review": false
}
```

`intent_category` 为有限枚举值，取值如下：
| 值 | 含义 |
|----|------|
| `pediatric_care` | 儿童健康/护理相关 |
| `adult_general` | 成人通用健康咨询 |
| `elderly_care` | 老年健康相关 |
| `emergency` | 急诊/高危（通常已被 L0 拦截，L1 仅在 L0 漏过时触发兜底） |
| `non_medical` | 非医疗类输入（由 L0 放行后进入 L1 兜底） |
| `unclear` | 意图无法确定 |

<!-- AUDIT-FIX: TC-010 / 待澄清项A3 -->

### 混合意图处理
单条用户消息可能包含多个意图（如"头有点痛，另外这个APP怎么退出"）。处理规则：
1. **L0 优先**：若消息中任一部分命中 L0 规则，整条消息按 L0 拦截处理（安全优先级最高）
2. **医疗意图优先**：L0 放行后，L1 按最高置信度的**医疗场景**路由。非医疗子意图不影响路由决策，由 L2 场景 Agent 在回复中附带非医疗引导
3. **不可拆分**：禁止将单条用户消息拆分为多条独立路由请求。L1 仅输出一个 `primary_scenario`
<!-- AUDIT-FIX: TC-014 / 审计补充建议4b -->
```

### scenario_id 枚举管理机制

- 所有可路由的 `scenario_id` 必须在 `configs/scenarios/` 目录下有对应配置文件
- 新增场景时，`scenario_id` 同步注册到路由模型的 `available_scenarios` 列表
- 过期场景的配置文件移动至 `configs/scenarios/archived/`，路由模型自动排除
- 线上可路由场景列表可通过 `GET /api/v1/scenarios` 接口查询

### 置信度阈值与兜底策略

| 条件 | 行为 |
|------|------|
| `primary_scenario.confidence ≥ 0.80` | 直接路由至目标场景，注入 `scenario_context` |
| `0.50 ≤ confidence < 0.80` | 路由至目标场景 + 告知用户"系统匹配到以下场景，请确认是否准确" |
| `confidence < 0.50` | 触发兜底：路由至 `general_consultation` 通用分诊场景 |
| `requires_human_review == true` | 路由至 `general_consultation` + 标记为待人工审核 |
| 无可用场景匹配 | 返回通用健康建议 + 建议就医 |
| `intent_category == "non_medical"` | L0 已识别为非医疗但放行，L1 路由至 `general_consultation` 并由 L2 礼貌引导至医疗场景 | <!-- AUDIT-FIX: TC-012 / 高优问题3 -->

### 路由 LLM 隔离要求
| 约束项 | 说明 |
|--------|------|
| 独立 API Key | 路由模型调用必须使用独立的 API Key，与医疗 Agent LLM 隔离 |
| 独立 Session | 路由 LLM 的对话上下文不得与后续医疗 Agent 共享 |
| Prompt 最小化 | 路由 Prompt 仅包含分类指令 + 场景列表摘要，不包含医学知识 |
| 禁止生成 | 路由 LLM `max_tokens` 限制为 256，仅输出结构化 JSON，禁止生成自由文本 |
| 无状态 | 每次路由调用独立，不依赖前次路由结果 |
| 限频 | 路由调用频率限制与医疗 Agent 调用独立计算 |

## 与 ADR-012 State 的联动机制

### 字段映射

| 路由输出字段 | 映射目标 | 说明 |
|------------|---------|------|
| `primary_scenario.scenario_id` | `State.scenario_context.scenario_id` | 目标场景标识 |
| `primary_scenario.confidence` | `State.scenario_context.route_confidence` | 路由置信度 |
| `intent_category` | `State.scenario_context.intent_category` | 意图大类 |
| `is_emergency` | `State.is_emergency` | L1 层独立急诊判断（与 L0 互斥，L0 命中则不进 L1） |
| `alternative_scenarios` | `State.scenario_context.alternatives` | 备选场景列表 |
| `requires_human_review` | `State.scenario_context.human_review` | 是否需要人工审核 |

### 注入安全性保证

1. **注入前校验**：路由输出的 `scenario_id` 必须在 `available_scenarios` 白名单中存在，否则拒绝注入并触发兜底
2. **Schema 校验**：路由输出 JSON 必须通过 Pydantic 模型校验，字段类型不匹配则拒绝注入
3. **不可篡改标记**：`scenario_context.route_confidence` 注入后不可被后续 Agent 修改
4. **审计追踪**：每次路由决策记录完整 JSON 到 `audit_logs`，`event_type="route_decision"`

## 示例片段

### L0 拦截示例

```
输入: "我孩子发高烧还抽筋了嘴唇发紫"

L0 处理:
  关键词匹配: "抽筋"→匹配急诊体征规则 "惊厥/抽搐"
            "嘴唇发紫"→匹配急诊体征规则 "口唇发紫"
  结果: 命中 L0，is_emergency=true

输出:
{
  "routing_stage": "L0_INTERCEPT",
  "is_emergency": true,
  "rule_id": "PEDIATRIC_EMERGENCY_SIGNS",
  "matched_keywords": ["惊厥/抽搐", "口唇发紫"],
  "response": "【系统自动安全响应】检测到您描述的情况可能属于...",
  "session_status": "emergency_terminated"
}
```

### L1 路由成功示例

```
输入: "孩子两岁了，昨天开始发烧38.5度，精神还好，喝水正常"

L0 处理: 未命中
L1 处理:
  分类结果: scenario_id="pediatric_fever_care", confidence=0.94

输出:
{
  "routing_stage": "L1_ROUTED",
  "scenario_context": {
    "scenario_id": "pediatric_fever_care",
    "route_confidence": 0.94,
    "intent_category": "pediatric_care",
    "alternatives": [
      {"scenario_id": "general_consultation", "confidence": 0.28}
    ],
    "human_review": false
  },
  "is_emergency": false,
  "session_status": "routed"
}
```

### L1 路由兜底示例

```
输入: "我有点不舒服"

L0 处理: 未命中
L1 处理: 信息不足，多个场景匹配但置信度均 < 0.50

输出:
{
  "routing_stage": "L1_FALLBACK",
  "scenario_context": {
    "scenario_id": "general_consultation",
    "route_confidence": 0.0,
    "intent_category": "unclear",
    "alternatives": [],
    "human_review": false
  },
  "is_emergency": false,
  "fallback_reason": "low_confidence",
  "session_status": "routed_to_fallback"
}
```
