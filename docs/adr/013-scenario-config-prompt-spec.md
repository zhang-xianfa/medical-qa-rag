# ADR-013: 场景配置与 Prompt 模板规范

## 状态
已采纳

## 背景
ADR-012 定义了与病种解耦的通用 Agent State，其中 `collected_facts` 与 `scenario_context` 通过外部动态注入实现多场景扩展。若缺乏统一的配置与 Prompt 规范，各场景的采集逻辑将碎片化，安全指令可能遗漏，输出格式将无法与 State 字段对齐。本 ADR 规范场景配置文件与 Prompt 模板的标准结构，确保多场景扩展的一致性与安全性。

## 决策
采用 **YAML** 定义场景配置，**Jinja2** 定义 Prompt 模板。两者通过 `scenario_context` 字段关联：Agent 启动时加载 YAML 配置 → 注入 State.scenario_context → Prompt 模板通过 `{{ scenario_context }}` 和 `{{ collected_facts }}` 占位符渲染 → LLM 输出结构化 JSON，由 Agent 校验后写入 `collected_facts`。

```
场景YAML配置 ──→ State.scenario_context ──→ Jinja2模板渲染 ──→ LLM调用 ──→ 输出JSON
                                                                              │
                                                        ┌─────────────────────┘
                                                        ▼
                                               校验通过 → State.collected_facts
                                               校验失败 → 安全降级
```

## 场景配置文件规范

### 文件命名与存放
- 路径：`config/scenarios/{scenario_id}.yaml`
- 编码：UTF-8
- `scenario_id` 规则：`[a-z][a-z0-9_]{2,31}`

### Schema 定义

```yaml
# config/scenarios/{scenario_id}.yaml
scenario_id: ""             # string, required, 全局唯一标识
display_name: ""            # string, required, 管理后台展示用
version: "1.0"              # string, required, 语义化版本
description: ""             # string, optional, 场景用途简述

required_facts:             # list[string], required, 必须采集的事实键名列表
  - ""                     # 键名规则: [a-z][a-z0-9_]{1,31}

optional_facts:             # list[string], optional, 可选采集的事实键名列表
  - ""

max_rounds: 5               # integer, required, 最大采集轮次，范围[2, 10]
min_rounds: 2               # integer, required, 最小采集轮次，范围[1, max_rounds]

termination_conditions:     # object, required
  min_facts_collected: 3    # integer, required, 最少采集事实数
  required_ratio: 0.7       # float, optional, 必填字段采集完成比例阈值[0.0, 1.0]
  allow_user_skip: true     # boolean, optional, 是否允许用户主动跳过
  missing_fact_defaults: {} # object, optional, 未采集字段的默认值映射。key为fact名称，value为默认值。
                            # 若某字段未配置默认值，则该字段不写入 collected_facts。
                            # 示例: {"severity_self_report": 5, "past_history_summary": "未提供"}
                            # <!-- AUDIT-FIX: TC-019 / 审计补充建议2 -->

safety_rules:               # object, required
  inherit_global: true      # boolean, 是否继承全局安全规则
  scenario_specific: []     # list[string], optional, 本场景额外安全规则引用

prompt_template: ""         # string, required, Prompt模板文件名(不含扩展名)

output_schema_version: "1.0"  # string, required, JSON Schema版本号
```

### 校验规则
- `required_facts` 与 `optional_facts` 的键名集合不可重叠
- `max_rounds` ≥ `min_rounds`
- `termination_conditions.min_facts_collected` ≤ `len(required_facts)` + `len(optional_facts)`
- 配置文件通过 YAML Schema 校验后方可被 Agent 加载

## Prompt 模板规范

### 文件命名与存放
- 路径：`config/prompts/{template_name}.j2`
- 编码：UTF-8
- 模板引擎：Jinja2（沙箱模式，禁用文件系统访问与任意代码执行）

### 模板结构（强制四区块）

```
{# Block 1: 角色设定 #}
你是一名AI健康助手。你的职责是...

{# Block 2: 安全指令（不可裁剪） #}
## 安全红线
- 以下情况必须立即终止当前流程并输出急诊指引：
  * 用户表达明确的自伤或自杀意图
  * 用户描述的严重症状（如不能呼吸、大出血、意识丧失等）
- 禁止做出确诊结论（如"你得了XX病"）
- 禁止给出具体用药剂量（如"每次服用XXmg"）
- 所有建议必须使用不确定表达（如"可能""建议排查""倾向于考虑"）
- 输出末尾必须附加免责声明："本内容仅供参考，不能替代专业医疗诊断。如有不适，请及时就医。"

{# Block 3: 采集项引导 #}
## 采集任务
根据以下场景配置，引导用户逐步提供信息：

场景：{{ scenario_context.display_name }}
描述：{{ scenario_context.description }}

需要采集的信息项（优先采集含 [*] 标记的必填项）：
{% for fact in scenario_context.required_facts %}
- [*] {{ fact }}
{% endfor %}
{% for fact in scenario_context.optional_facts %}
- [ ] {{ fact }}
{% endfor %}

当前已采集：{{ collected_facts | tojson }}

## 提问规则
- 每次最多提问3个，优先询问尚未采集的必填项
- 不要重复询问已采集的信息
- 根据已有信息动态调整后续问题

{# Block 4: 输出JSON Schema约束 #}
## 输出格式
每次回答必须按以下JSON格式输出（仅输出JSON，不要附加任何其他文字）：

{
  "response_text": "给用户看的自然语言回复",
  "extracted_facts": {
    "fact_key": "提取到的值"
  },
  "severity_assessment": "mild" | "moderate" | "severe" | "emergency",
  "is_emergency": false,
  "next_action": "continue" | "assess" | "emergency"
}

## 输出约束
- severity_assessment 为 "emergency" 时，is_emergency 必须为 true，next_action 必须为 "emergency"
- extracted_facts 仅包含本轮新提取的事实，不重复已有的
- 若本轮未提取到有效事实，extracted_facts 为空对象 {}
```

### 占位符使用规则

| 占位符 | 来源 | 说明 |
|--------|------|------|
| `{{ scenario_context }}` | State.scenario_context | 完整的场景配置对象 |
| `{{ collected_facts }}` | State.collected_facts | 当前已采集的事实键值对 |
| `{{ messages }}` | State.messages | 对话历史（可选注入） |
| `{{ round_count }}` | State.round_count | 当前轮次（可选注入） |

### 模板内禁止
- 硬编码具体病种名称
- 使用 Jinja2 的 `{% include %}` 或 `{% extends %}`
- 访问 Python 内置函数（已在沙箱中禁用）
- 执行文件 I/O 或网络请求

## 配置审核流程

```
开发提交 PR
    │
    ▼
┌─────────────────────┐
│ 1. 自动化格式校验    │  ← CI 流水线自动执行
│  - YAML Schema 校验  │
│  - required_facts 命名规则检查
│  - Prompt 模板沙箱安全检查
│  - JSON Schema 有效性校验
└──────────┬──────────┘
           │ 通过
           ▼
┌─────────────────────┐
│ 2. 临床专家审核      │  ← 人工审核
│  - 采集项医学合理性   │
│  - 提问逻辑临床正确性  │
│  - 终止条件安全性     │
└──────────┬──────────┘
           │ 通过
           ▼
┌─────────────────────┐
│ 3. 安全团队复核      │  ← 人工复核
│  - 安全指令完整性     │
│  - 红旗关键词覆盖     │
│  - 合规表述校验       │
└──────────┬──────────┘
           │ 通过
           ▼
┌─────────────────────┐
│ 4. 灰度上线          │  ← 渐进发布
│  - 5% 流量观察 2h    │
│  - 25% 流量观察 6h   │
│  - 全量上线          │
└──────────┬──────────┘
           │ 无异常
           ▼
┌─────────────────────┐
│ 5. 归档与审计        │
│  - 审核记录留存       │
│  - 配置版本标记       │
│  - 变更日志更新       │
└─────────────────────┘
```

### 审核通过标准
- 自动化校验 0 error
- 至少 1 名临床专家 Approved
- 至少 1 名安全团队成员 Approved
- 灰度期间 `is_emergency` 异常率 < 0.1%

## 示例片段

### YAML 配置示例

```yaml
scenario_id: "general_consultation"
display_name: "通用健康咨询"
version: "1.0"
description: "面向常见不适症状的通用问诊场景"

required_facts:
  - "chief_symptom"
  - "symptom_duration"
  - "symptom_location"
  - "severity_self_report"

optional_facts:
  - "accompanying_manifestations"
  - "past_history_summary"

max_rounds: 5
min_rounds: 2

termination_conditions:
  min_facts_collected: 4
  required_ratio: 1.0
  allow_user_skip: true

safety_rules:
  inherit_global: true
  scenario_specific: []

prompt_template: "general_consultation"
output_schema_version: "1.0"
```

### Prompt 模板示例

```
你是AI健康助手。你的任务是基于用户描述，按场景配置引导提问并提取结构化信息。

## 安全红线
- 以下情况必须立即终止并输出急诊指引：
  * 用户表达明确的自伤或自杀意图
  * 用户描述的严重症状
- 禁止做出确诊结论
- 禁止给出具体用药剂量
- 所有建议必须使用不确定表达
- 输出末尾必须附加免责声明

## 采集任务
场景：{{ scenario_context.display_name }}
描述：{{ scenario_context.description }}

需采集信息：
{% for fact in scenario_context.required_facts %}
- [*] {{ fact }}
{% endfor %}
{% for fact in scenario_context.optional_facts %}
- [ ] {{ fact }}
{% endfor %}

当前已采集：{{ collected_facts | tojson }}
当前轮次：{{ round_count }} / {{ scenario_context.max_rounds }}

## 提问规则
- 每次最多3个问题
- 不重复已采集项
- 优先询问必填项中缺失的字段
- 根据已有信息动态调整

## 输出格式
仅输出以下JSON，不要附加其他文字：

{
  "response_text": "",
  "extracted_facts": {},
  "severity_assessment": "mild",
  "is_emergency": false,
  "next_action": "continue"
}
```
