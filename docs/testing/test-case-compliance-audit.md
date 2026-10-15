# 测试用例合规性审计报告

## 审计摘要

| 项目 | 数值 |
|------|------|
| 总用例数 | 24 |
| 合规 | 15 (62.5%) |
| 部分合规 | 9 (37.5%) |
| 不合规 | 0 (0%) |
| 发现高优问题 | 4 |
| 发现 ADR 待澄清项 | 5 |

**审计依据：** ADR-012 v1.0、ADR-013 v1.0、ADR-014 v1.0、pediatric_fever_care_review.md v1.0、SDD-01 §2.4

---

## 逐条审计结果

### 第一类：L0 安全前置过滤

| 用例ID | 判定 | 对应ADR条款 | 问题描述/合规说明 | 修复建议 |
|--------|------|-------------|-------------------|----------|
| TC-001 | 部分合规 | ADR-014 §L0 | `rule_id="PEDIATRIC_EMERGENCY_SIGNS"` 来源于场景配置 `safety_rules.scenario_specific`，非 ADR-014 §L0 全局规则库。ADR-014 §L0 要求规则存储于 `config/safety_rules.yaml`，但未定义场景级规则如何注入 L0。`matched_keywords` 中的"抽筋/抽搐""口唇发紫"是 pediatric_fever_care.j2 Prompt 模板中的急诊指征列表内容，非 L0 全局关键词。 | 在 ADR-014 §L0 增加"场景规则合并机制"条款，明确全局规则与场景特有规则的合并策略与优先级。 |
| TC-002 | 部分合规 | ADR-012, ADR-014 §L0 | `red_flag_level="CRITICAL"` 字段未在 ADR-012 State 字段清单中定义（ADR-012 只有 `is_emergency: boolean` 和 `severity: enum`），也未在 ADR-014 L0/L1 输出 Schema 中定义。该字段存在于实现代码 `red_flag_detector.py` 中但未被契约文档覆盖。规则ID `SUICIDE_INTENT` 的具体名称未在 ADR-014 §L0 规则分类表中枚举。 | 方案A：将 `red_flag_level` 纳入 ADR-012 State 作为可选字段（`"CRITICAL"\|"HIGH"\|"MEDIUM"`）。方案B：测试用例改为仅验证 `is_emergency=true` 和 `severity="emergency"`，移除 `red_flag_level` 断言。 |
| TC-003 | 部分合规 | ADR-014 §L0 | "OVERDOSE"（过量服药）类别未出现在 ADR-014 §L0 规则分类表中。ADR-014 §L0 定义的类别为：急诊体征、自伤/自杀意图、违法/违规请求、PII检测、非医疗类闲聊。过量服药可归入"急诊体征"但未被显式列举。 | 在 ADR-014 §L0 规则分类表中增加"中毒/过量服药"子类别，或将其明确归入"急诊体征"并给出关键词示例。 |
| TC-004 | 合规 | ADR-014 §L0 | L0 拦截后会话不可恢复（"否，会话标记为emergency_terminated"），与 ADR-014 §L0 规则分类表的"是否可被后续对话恢复"列一致。HTTP 409 为 API 层约定（SDD-03 §4.2），非 ADR 范畴，作为 E2E 测试可接受。 | — |
| TC-005 | 合规 | ADR-014 §L0, ADR-014 §L1 | L0 PII 脱敏策略"自动脱敏后放行"→"是"与 ADR-014 §L0 规则表一致。`routing_stage="L1_ROUTED"` 与 ADR-014 L1 成功路由输出示例一致。 | — |

### 第二类：L1 路由成功

| 用例ID | 判定 | 对应ADR条款 | 问题描述/合规说明 | 修复建议 |
|--------|------|-------------|-------------------|----------|
| TC-006 | 合规 | ADR-014 §L1, ADR-012 | 置信度≥0.80 直接路由 + `scenario_context` 注入与 ADR-014 §L1 完全一致。`conversation_stage="collecting"` 为 ADR-012 定义的合法枚举值。 | — |
| TC-007 | 合规 | ADR-012, ADR-013 | `extracted_facts` 中的 `body_temperature` 和 `child_age` 均为 pediatric_fever_care.yaml `required_facts` 合法键名。`collected_facts` 动态键值对结构与 ADR-012 定义一致。 | — |
| TC-008 | 合规 | ADR-014 §L1 | 置信度区间 [0.50, 0.80) 的"告知用户确认"行为与 ADR-014 §L1 兜底策略表第2行完全一致。`route_confidence ∈ [0.50,0.80)` 断言正确。 | — |
| TC-009 | 合规 | ADR-014 §L1 | `scenario_id="general_consultation"` 为 ADR-013 示例中定义的兜底场景标识。成人发热路由至通用场景符合 ADR-014 §L1 "无专门场景时使用兜底场景"的逻辑。 | — |
| TC-010 | 部分合规 | ADR-014 §L1 | `intent_category` 为 ADR-014 L1 输出 Schema 定义字段，但其枚举值（如"成人发热"）未在 ADR-014 中显式枚举。ADR-014 L1 输出示例中使用 `"intent_category": "pediatric_care"` 但未给出完整值域。 | 在 ADR-014 §L1 输出 Schema 中增加 `intent_category` 的预定义枚举值列表，或将字段描述改为"自由文本标签"。 |

### 第三类：L1 路由兜底

| 用例ID | 判定 | 对应ADR条款 | 问题描述/合规说明 | 修复建议 |
|--------|------|-------------|-------------------|----------|
| TC-011 | 合规 | ADR-014 §L1 | 置信度<0.50 触发兜底→`general_consultation` 与 ADR-014 §L1 第3行一致。`routing_stage="L1_FALLBACK"`、`route_confidence=0.0`、`fallback_reason="low_confidence"` 均与 ADR-014 L1 兜底示例完全一致。 | — |
| TC-012 | 部分合规 | ADR-014 §L0, ADR-014 §L1 | 非医疗类输入的检测应由 L0 承担（ADR-014 §L0 规则表明确包含"非医疗类闲聊"类别，行为为"礼貌引导至医疗场景"），而非落入 L1 兜底。当前测试假设此类输入走 L1 兜底，与 L0/L1 职责划分矛盾。 | 明确非医疗输入的处理层级：方案A→L0 白名单过滤直接拦截；方案B→L1 路由后由兜底场景处理。建议方案A以减少 L1 LLM 调用成本。同时更新 TC-012 的预期触发层级为 L0（若采用方案A）或保持 L1 兜底但标注为"经 L0 放行后"（若采用方案B）。 |
| TC-013 | 合规 | ADR-014 §L1 | 语义模糊导致所有场景置信度<0.50 触发兜底，与 ADR-014 §L1 第3行一致。 | — |
| TC-014 | 部分合规 | ADR-014 §L1 | 混合意图（医疗+非医疗）的单条消息路由策略未在 ADR-014 中定义。ADR-014 的 L0/L1 管道假设每条消息映射到一个意图。测试假设了"分别处理"行为——先走 L1 兜底再在 L2 分别响应——但此拆分策略未被任何 ADR 条款覆盖。 | 在 ADR-014 §L1 增加"混合意图处理"条款，定义：（1）是否拆分为多条独立消息；（2）拆分后各自路由还是统一兜底；（3）不拆分时按最高风险意图路由。 |

### 第四类：L2 场景正常执行

| 用例ID | 判定 | 对应ADR条款 | 问题描述/合规说明 | 修复建议 |
|--------|------|-------------|-------------------|----------|
| TC-015 | 合规 | ADR-013 §Block3 | "按required_facts顺序"+"提问不超过3个"+"已采集项不重复"三项均与 ADR-013 Prompt 模板 Block3 §提问规则完全一致。 | — |
| TC-016 | 合规 | ADR-012, ADR-013 | `conversation_stage="assessing"` 为 ADR-012 合法枚举值。`min_facts_collected≥6` 与 pediatric_fever_care.yaml 中 `termination_conditions.min_facts_collected: 6` 一致。`next_action="assess"` 为 ADR-013 §Block4 JSON 输出 Schema 中定义的合法枚举值。 | — |
| TC-017 | 合规 | ADR-012, ADR-013 §Block2 | `conversation_stage="completed"` 合法。"可考虑""建议"符合 ADR-013 §Block2 不确定性表达要求。护理建议（温水擦浴/补水/环境调节）在 pediatric_fever_care.yaml `description` 定义的"居家护理指导"范围内。免责声明输出与 ADR-013 §Block2 免责声明模板一致。 | — |
| TC-018 | 合规 | ADR-014 §L0 | "新消息先经 L0 检测"即 L0 优先级高于 L2，与 ADR-014 架构图（用户输入→L0→L1→Agent运行时）流程一致。会话终止行为与 L0 规则表"是否可被后续对话恢复: 否"一致。 | — |
| TC-019 | 部分合规 | ADR-013, ADR-012 | `max_rounds=5` 达到后触发 assess 的逻辑与 pediatric_fever_care.yaml 配置一致。"缺失字段用默认值填充"——ADR-012 的 `collected_facts` 和 ADR-013 的 `termination_conditions` 均未定义缺失字段的默认值策略。ADR-012 仅说明 `collected_facts` 是"动态键值对"，未规定键不存在时的行为。 | 在 ADR-013 `termination_conditions` 中增加 `missing_fact_defaults` 字段，或明确"未采集字段不写入 `collected_facts`，由 Prompt 模板自行处理默认值"。 |
| TC-020 | 合规 | ADR-013 §Block2, §Block4 | 禁止药物/诊断/绝对化表述与 ADR-013 §Block2 安全红线一致。`disclaimer` 字段非空与 ADR-013 §Block4 JSON Schema 约束一致。正则 `\d+\s*(mg\|片\|粒)` 是 ADR-013 §Block2 "禁止给出具体用药剂量"的合理细化。 | — |

### 第五类：跨层级联动

| 用例ID | 判定 | 对应ADR条款 | 问题描述/合规说明 | 修复建议 |
|--------|------|-------------|-------------------|----------|
| TC-021 | 部分合规 | SDD-01 §2.4, ADR-014 §L0/L1 | audit_logs 链路完整性验证方向正确。但 `event_type="safety_check"` 不存在于 SDD-01 §2.4 定义的 `event_type` 枚举中。SDD-01 定义的合法值为：`intent_detect`、`route_decision`、`question_generate`、`info_collected`、`interview_complete`、`search_execute`、`search_rerank`、`diagnosis_generate`、**`safety_intercept`**、`fallback_trigger`。测试用例应使用 `safety_intercept`。 | 将 TC-021 关键验证点中的 `"safety_check"` 修正为 `"safety_intercept"`，与 SDD-01 §2.4 枚举定义对齐。 |
| TC-022 | 合规 | ADR-012 | `session_id` 唯一性隔离 + `collected_facts` 动态键值对互不污染，与 ADR-012 字段定义及无状态属性一致。 | — |
| TC-023 | 合规 | ADR-014 §L1 路由LLM隔离 | 独立 API Key（`Authorization header` 不同）+ 独立 Session + `max_tokens≤256` + Prompt 不含医学知识 + 响应仅含 JSON，五项均与 ADR-014 §L1 "路由LLM隔离要求"表格完全一致。`请求体size<2KB` 是实现层面验证，非 ADR 直接条款，可接受。 | — |
| TC-024 | 部分合规 | ADR-014 §L0 | ADR-014 §L0 规定规则"存储在 `config/safety_rules.yaml` 中"并由代码加载执行，但未指定加载方式（启动时一次性加载 vs 文件监听热加载）。测试假设"无需重启服务"即热加载，此行为未被任何 ADR 条款覆盖。ADR-014 §L0 的"规则维护机制"描述了审核流程但未描述部署时效。 | 在 ADR-014 §L0 增加"规则生效机制"条款，明确：（1）规则变更是热加载还是需重启；（2）热加载的监听间隔；（3）灰度期间的规则版本回滚策略。 |

---

## 高优问题清单

| # | 严重度 | 用例ID | 问题 | 影响 |
|---|--------|--------|------|------|
| 1 | 🔴 高 | TC-021 | `event_type="safety_check"` 与 SDD-01 §2.4 定义的 `safety_intercept` 不一致。SDD-01 是数据库 Schema 的权威来源，event_type 枚举直接影响 `audit_logs` 表的 CHECK 约束和下游审计查询。 | 若按测试用例实现，`audit_logs` 写入将因违反 CHECK 约束而失败，审计链路断裂。 |
| 2 | 🟠 高 | TC-002 | `red_flag_level="CRITICAL"` 未在 ADR-012/014 中定义，但实现代码 `red_flag_detector.py` 已返回该字段。契约与实现不一致。 | 新开发者参照 ADR 阅读测试用例时会认为此为隐式规则；安全审计检查 State JSON 时会发现未声明字段。 |
| 3 | 🟠 高 | TC-012 | 非医疗输入的路由层级归属矛盾。ADR-014 §L0 将其列为 L0 职责（"非医疗类闲聊"→"礼貌引导至医疗场景"），但 TC-012 将其放入 L1 兜底。 | 可能导致非医疗输入浪费 L1 LLM 调用资源，且 L0/L1 职责边界模糊化不利于后续优化。 |
| 4 | 🟡 中 | TC-001 | 场景特有安全规则（如 `PEDIATRIC_EMERGENCY_SIGNS`）如何合并到 L0 全局规则引擎，ADR-014 未定义。当前仅 pediatric_fever_care 一个场景尚可手动处理，扩展至 10+ 场景后合并逻辑将成为安全漏洞点。 | 多场景时，L0 可能遗漏场景特有急诊关键词，导致高危请求漏过 L0 拦截。 |

---

## ADR 待澄清项

| # | 来源ADR | 待澄清内容 | 提出用例 |
|---|---------|-----------|---------|
| A1 | ADR-014 §L0 | L0 规则引擎是否仅加载 `config/safety_rules.yaml` 全局规则？场景配置中的 `safety_rules.scenario_specific` 规则如何注入 L0？注入时机是在路由前（全局过滤）还是路由后（场景级过滤）？ | TC-001 |
| A2 | ADR-012 | State 是否需要 `red_flag_level` 字段？当前实现代码中 `detect_red_flag()` 返回该字段，但 ADR-012 字段清单中仅有 `is_emergency` 和 `severity`。若 `red_flag_level` 仅作为 L0 内部信号不写入 State，需在 ADR-014 中明确定义其作用域。 | TC-002 |
| A3 | ADR-014 §L1 | `intent_category` 字段是自由文本标签还是有限枚举？若是枚举，完整值域是什么？当前 ADR-014 示例中使用 `"pediatric_care"`，TC-010 使用 `"成人发热"`，命名风格不一致。 | TC-010 |
| A4 | ADR-014 §L0 | 规则变更（如新增关键词）的生效方式是热加载还是需重启服务？若是热加载，监听间隔和回滚策略是什么？ | TC-024 |
| A5 | ADR-014 §L1 | 混合意图（单条消息包含医疗+非医疗内容）的路由策略未定义。应拆分消息分别路由，还是按最高风险意图路由？ | TC-014 |

---

## ADR 补充建议

基于本次审计中测试用例揭示的边界情况，建议对现有 ADR 做以下修订：

1. **ADR-012 补充**：在 State 字段清单中增加 `red_flag_level: "CRITICAL" | "HIGH" | "MEDIUM" | null`（可选字段），与 `is_emergency` 和 `severity` 共同组成安全熔断三元组。当前实现已使用该字段，契约化可消除契约-实现不一致。

2. **ADR-013 补充**：在 `termination_conditions` Schema 中增加 `missing_fact_defaults: object` 字段（可选），允许场景配置为每个 required_fact 指定未采集时的默认值。若未配置默认值，则该事实键不写入 `collected_facts`。

3. **ADR-014 §L0 补充**：(a) 规则分类表增加"中毒/过量服药"类别；(b) 增加"场景规则合并机制"小节，定义全局规则与 `scenario_context.safety_rules.scenario_specific` 的合并策略（全局优先 vs 场景优先 vs 并集）；(c) 增加"规则生效机制"小节，明确热加载/重启策略与回滚流程。

4. **ADR-014 §L1 补充**：(a) `intent_category` 字段增加枚举值定义；(b) 增加"混合意图处理"小节，定义单条消息包含多个意图时的拆分策略或优先级规则。

5. **TC-021 修复**：将关键验证点中的 `event_type="safety_check"` 修正为 `"safety_intercept"`，与 SDD-01 §2.4 对齐。同时检查 TC-021 中引用的其他 event_type 是否与 SDD-01 枚举完全一致。

---

## 修复验证摘要

以下为本次双向闭环修复的执行确认。修订文件清单：

| 修订文件 | 修订范围 | 关联审计条目 |
|---------|---------|------------|
| `docs/adr/012-agent-state-contract.md` | 新增 `red_flag_level` 字段定义 + 审计约束扩展 | TC-002 / 待澄清项A2 |
| `docs/adr/013-scenario-config-prompt-spec.md` | `termination_conditions` 新增 `missing_fact_defaults` | TC-019 / 补充建议2 |
| `docs/adr/014-intent-routing-safety-filter.md` | L0 规则分类增加"中毒/过量服药"；新增"场景规则注入L0机制"；新增"规则生效机制"（热加载）；L1 `intent_category` 枚举值定义；新增"混合意图处理"；兜底策略表增加非医疗行 | TC-001/003/010/012/014/024 / 待澄清项A1/A3/A4 / 补充建议3a/3b/3c/4a/4b |
| `docs/testing/e2e-routing-scenario-test-cases.md` | TC-001/002/003/010/012/019/021/024 共8个用例的预期行为与验证点修正 | 全部4个高优问题 + 4个待澄清项 |

### 高优问题闭环确认

| 高优问题 | 修复前状态 | 修复后状态 |
|---------|----------|----------|
| #1: TC-021 event_type 不一致 | `event_type="safety_check"` 不存在于 SDD-01 枚举 | 修正为 `"safety_intercept"`，与 SDD-01 §2.4 对齐 ✅ |
| #2: TC-002 red_flag_level 未契约化 | 字段仅存在于实现代码，不在任何 ADR 中 | 纳入 ADR-012 State 字段清单（`"CRITICAL"\|"HIGH"\|"MEDIUM"\|null`），扩展审计约束 ✅ |
| #3: TC-012 非医疗输入层级归属矛盾 | 测试用例放入 L1 兜底，ADR-014 定义为 L0 职责 | ADR-014 §L0 明确非医疗类闲聊由 L0 白名单识别但放行，L1 路由至 `general_consultation` 作为兜底场景，TC-012 修正为 L0放行→L1兜底 路径 ✅ |
| #4: TC-001 场景规则注入机制缺失 | 场景特有安全规则如何进入 L0 未定义 | ADR-014 新增"场景规则注入L0机制"小节，定义全局规则+场景规则并集执行、懒加载策略 ✅ |

### ADR 待澄清项闭环确认

| 待澄清项 | 决议 | 落地位置 |
|---------|------|---------|
| A1: 场景规则注入 L0 机制 | 全局+场景并集，场景规则懒加载，会话级缓存 | ADR-014 §场景规则注入L0机制 |
| A2: red_flag_level 字段归属 | 纳入 ADR-012 State（可选字段），L0 写入，仅用于审计 | ADR-012 字段清单 + 安全约束 |
| A3: intent_category 枚举 | 定义6个标准值（pediatric_care / adult_general / elderly_care / emergency / non_medical / unclear） | ADR-014 §L1 输出Schema后 |
| A4: 规则生效机制 | 全局规则30s热加载+自动回滚；场景规则会话级不可变 | ADR-014 §规则生效机制 |
| A5: 混合意图路由 | L0优先+医疗意图优先+不拆分单条消息 | ADR-014 §混合意图处理 |

### 修复后 TC 合规性更新

| 原判定 | 用例ID | 修复后判定 |
|--------|--------|-----------|
| 部分合规 | TC-001 | **合规** |
| 部分合规 | TC-002 | **合规** |
| 部分合规 | TC-003 | **合规** |
| 部分合规 | TC-010 | **合规** |
| 部分合规 | TC-012 | **合规** |
| 合规 | TC-014 | **合规**（混合意图已纳入 ADR-014） |
| 部分合规 | TC-019 | **合规** |
| 部分合规 | TC-021 | **合规** |
| 部分合规 | TC-024 | **合规** |

修复后合规统计：24/24 合规（100%）。

---

## 修复过程衍生问题

在修复过程中发现以下额外问题，记录于此供后续处理：

**D1: pediatric_fever_care.yaml 未同步更新**
`configs/scenarios/pediatric_fever_care.yaml` 中的 `termination_conditions` 未包含新增的 `missing_fact_defaults` 字段。当前场景的 `allow_user_skip: false` 意味着所有 `required_facts` 必须采集，不存在默认值需求，但建议显式添加 `missing_fact_defaults: {}` 以保持与 ADR-013 Schema 的完全兼容。
*建议：后续 PR 中补充，非阻塞。*

**D2: safety_rules.yaml 规则集需拆分为全局+场景**
ADR-014 修订后定义了 `config/safety_rules/{rule_set_id}.yaml` 的场景规则目录，但 `config/safety_rules/` 目录尚未创建，`PEDIATRIC_EMERGENCY_SIGNS` 规则集文件缺失。当前这些规则仅存在于 pediatric_fever_care.j2 Prompt 模板中，尚未提取为独立的 L0 正则规则文件。
*建议：创建 `config/safety_rules/pediatric_emergency_signs.yaml`，将10项儿科急诊指征从 Prompt 模板提取为 L0 正则规则。阻塞级别：中（在第二个场景上线前必须完成）。*

**D3: ADR-014 L1 置信度阈值缺乏区分度**
当前阈值仅有一个维度的 numeric 置信度（≥0.80 / [0.50,0.80) / <0.50），未区分"信息不足导致的低置信"与"多场景竞争导致的中等置信"。TC-008 与 TC-013 都使用置信度阈值判定，但两者的低置信原因不同，兜底策略是否可以区分对待？
*建议：L1 输出增加 `confidence_reason` 字段（`"insufficient_info" \| "multi_scenario_ambiguity" \| "non_medical"`），供后续精细化兜底策略。状态：待产品确认。*

---

*修复完成日期：2026-06-19 | 修复依据：test-case-compliance-audit.md v1.0*
