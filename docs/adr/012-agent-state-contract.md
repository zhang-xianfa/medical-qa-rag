# ADR-012: 通用医疗问诊 Agent 运行时状态契约

## 状态
已采纳

## 背景
医疗智能问答系统需支撑多种问诊场景，不同场景的采集字段差异巨大。若将具体病种字段固化于 Agent State Schema 中，将导致 Schema 随场景频繁变更，破坏系统稳定性，并增加安全审计复杂度。为构建安全合规、可扩展的医疗问诊Agent，需定义一套与病种解耦的通用运行时状态结构。

## 决策
Agent State 仅保留通用元数据与安全护栏字段。具体病种的采集逻辑通过外部配置文件 + Prompt模板 + `scenario_context` 字段动态注入，不固化于 Schema 中。State 本身对病种零感知。

## 字段清单

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `session_id` | `string` | 是 | 会话唯一标识 |
| `messages` | `list[dict]` | 是 | 对话历史，由 LangGraph add_messages reducer 管理 |
| `chief_complaint` | `string \| null` | 否 | 用户主诉，首轮对话后由 LLM 提取填充。与具体病种解耦 |
| `severity` | `"mild" \| "moderate" \| "severe" \| "emergency"` | 否 | LLM 结构化输出的安全分级。`emergency` 时触发熔断 |
| `is_emergency` | `boolean` | 是 | 安全熔断标识。`true` 时强制终止当前对话流程并输出急诊指引 |
| `red_flag_level` | `"CRITICAL" \| "HIGH" \| "MEDIUM" \| null` | 否 | L0 安全规则命中后的分级信号。`CRITICAL` 对应急诊体征/自伤意图（触发熔断），`HIGH` 对应潜在危险但非即时威胁，`MEDIUM` 对应需关注但可继续采集。该字段由 L0 规则引擎写入，仅作为审计与日志分类依据，不参与 L1/L2 决策逻辑。L1/L2 层级仅依赖 `is_emergency` 和 `severity` 做路由与熔断判定 | <!-- AUDIT-FIX: TC-002 / 待澄清项A2 -->
| `conversation_stage` | `"init" \| "collecting" \| "assessing" \| "completed"` | 是 | 当前工作流阶段，控制路由决策 |
| `collected_facts` | `object` | 否 | 动态键值对，存储当前场景已采集的事实信息。字段名完全由外部 Prompt 模板决定，State Schema 不做约束 |
| `scenario_context` | `object \| null` | 否 | 当前问诊场景的配置元数据。由外部配置文件注入，包含场景ID、采集项定义、终止条件等。Agent 据此驱动 `collecting` 阶段的提问逻辑 |
| `safety_checks_passed` | `boolean` | 是 | 安全护栏校验是否通过。`false` 时禁止进入 `assessing` 阶段 |
| `round_count` | `integer` | 是 | 当前采集轮次计数。用于控制 `collecting` 阶段的最大轮次 |
| `max_rounds` | `integer` | 是 | 最大采集轮次上限。由 `scenario_context` 配置注入，默认值可在全局配置中设定 |
| `diagnosis_result` | `object \| null` | 否 | 综合评估输出。仅在 `completed` 阶段填充，内容结构由 Prompt 模板控制，禁止包含处方或确诊结论 |

## 扩展机制

- **新增问诊场景**：仅需添加场景配置文件 → 更新 Prompt 模板 → 设置 `scenario_context`。State Schema 本身零修改。
- **新增安全规则**：通过 `config/safety_rules.yaml` 动态加载，无需改动 State 结构。
- **调整采集策略**：修改 `scenario_context` 中的 `required_facts` 列表和 `max_rounds` 即可，不影响 State。

```
场景配置 → scenario_context ──→ Agent 运行时读取
                                  │
Prompt模板 → LLM 结构化输出 ──→ collected_facts（动态填充）
                                  │
安全护栏配置 ──────────────────→ is_emergency / severity（熔断判定）
L0 规则引擎 ────────────────────→ red_flag_level（审计分级）
```

## 安全约束

1. **熔断优先**：`is_emergency == true` 或 `severity == "emergency"` 时，系统必须立即中断当前 Agent 链，输出固定急诊指引模板，并拒绝后续对话输入。
2. **超范围禁止**：禁止在 `collected_facts` 或 `diagnosis_result` 中存储以下类型数据：
   - 确诊结论（如"确诊为XX病"）
   - 具体用药处方（含剂量、频次）
   - 未脱敏的 PII（姓名、身份证号、手机号等）
3. **降级兜底**：`safety_checks_passed == false` 时，系统必须降级返回安全就医建议，禁止生成任何形式的评估或建议输出。
4. **审计可追溯**：每次 `is_emergency` 翻转、`severity` 变更、`conversation_stage` 跳转、`red_flag_level` 赋值均需记录审计日志。`red_flag_level="CRITICAL"` 的审计记录需包含触发的 `rule_id` 与 `matched_keywords`。 <!-- AUDIT-FIX: TC-002 / 待澄清项A2 -->

## 后果

- State Schema 稳定性大幅提升：新增病种场景无需修改代码，仅需配置变更。
- 安全审计聚焦明确：`is_emergency` 和 `severity` 两个字段即可覆盖所有场景的安全熔断逻辑。
- 前端适配简化：只需理解通用字段结构，无需为每种场景开发不同的 State 解析逻辑。
- 风险：`collected_facts` 作为动态容器，其内容质量完全依赖 Prompt 设计和 LLM 输出能力。需通过 Prompt 工程和输出校验机制保障数据质量。
