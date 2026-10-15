# 测试套件实现差距报告

## 总览

| 指标 | 数值 |
|------|------|
| 测试用例总数 | 24 |
| 已自动化 | 24 |
| 跳过(mock不足) | 0 |
| 跳过(ADR未实现) | 0 |
| 实现率 | 100% |

## 测试覆盖矩阵

| 用例ID | 分类 | 测试文件 | 测试函数 | 状态 |
|--------|------|---------|---------|------|
| TC-001 | L0急诊 | test_l0_safety_filter.py | test_tc001_emergency_pediatric_seizure_and_cyanosis | ✅ |
| TC-002 | L0自伤 | test_l0_safety_filter.py | test_tc002_suicide_intent_triggers_critical | ✅ |
| TC-003 | L0中毒 | test_l0_safety_filter.py | test_tc003_overdose_triggers_poison_emergency | ✅ |
| TC-004 | L0阻断 | test_l0_safety_filter.py | test_tc004_emergency_session_blocked | ✅ |
| TC-005 | L0放行 | test_l0_safety_filter.py | test_tc005_pii_desensitize_and_release_to_l1 | ✅ |
| TC-006 | L1高置信 | test_l1_intent_router.py | test_tc006_high_confidence_pediatric_fever_routing | ✅ |
| TC-007 | L1高置信 | test_l1_intent_router.py | test_tc007_high_confidence_with_baby_keywords | ✅ |
| TC-008 | L1中置信 | test_l1_intent_router.py | test_tc008_medium_confidence_confirm_routing | ✅ |
| TC-009 | L1跨场景 | test_l1_intent_router.py | test_tc009_adult_fever_routes_to_general_consultation | ✅ |
| TC-010 | L1多关键词 | test_l1_intent_router.py | test_tc010_elderly_fever_routes_with_adult_general_category | ✅ |
| TC-011 | L1兜底 | test_l1_intent_router.py | test_tc011_low_confidence_fallback | ✅ |
| TC-012 | L1非医疗 | test_l1_intent_router.py | test_tc012_non_medical_routed_via_l1 | ✅ |
| TC-013 | L1兜底 | test_l1_intent_router.py | test_tc013_vague_input_triggers_fallback | ✅ |
| TC-014 | L1混合意图 | test_l1_intent_router.py | test_tc014_mixed_intent_routes_medical_priority | ✅ |
| TC-015 | L2采集 | test_l2_scenario_execution.py | test_tc015_first_round_collects_required_facts | ✅ |
| TC-016 | L2采集完成 | test_l2_scenario_execution.py | test_tc016_termination_when_all_required_facts_collected | ✅ |
| TC-017 | L2评估 | test_l2_scenario_execution.py | test_tc017_assessment_output_nursing_advice_and_disclaimer | ✅ |
| TC-018 | L2中途急诊 | test_l2_scenario_execution.py | test_tc018_mid_collection_emergency_intercepted | ✅ |
| TC-019 | L2最大轮次 | test_l2_scenario_execution.py | test_tc019_max_rounds_triggers_assessment | ✅ |
| TC-020 | L2安全校验 | test_l2_scenario_execution.py | test_tc020_safety_output_no_forbidden_content | ✅ |
| TC-021 | 审计日志 | test_cross_layer_integration.py | test_tc021_audit_log_complete_chain | ✅ |
| TC-022 | State隔离 | test_cross_layer_integration.py | test_tc022_state_isolation_between_sessions | ✅ |
| TC-023 | LLM隔离 | test_cross_layer_integration.py | test_tc023_routing_llm_isolation_properties | ✅ |
| TC-024 | 热加载 | test_cross_layer_integration.py | test_tc024_scene_rules_registration_and_clear | ✅ |

## 已知局限

### L1: 真实LLM路由未测试
当前 L1 使用 `_MockRouterLLM` 做关键词匹配，未验证真实 LLM 场景。TC-008 的"确认语句"验证仅在集成测试层面通过 Mock 实现。

### L2: PII NER模型未实现
`_mask_pii()` 仅支持正则匹配姓名（"我叫XXX"）和身份证号，不支持基于 NER 模型的姓名/地址识别。ADR-014 §L0 中列出的"地址"脱敏未覆盖。

### L3: 热加载监听未实现
TC-024 验证了规则注册/清除的会话级机制，但30秒文件监听的热加载逻辑未实现。

### L4: 混合意图拆分未实现
TC-014 验证了"医疗意图优先"路由策略，但 ADR-014 定义的"L2 Agent附带非医疗引导"未在 L2 场景中实现。

## 建议

- 待真实 LLM API Key 配置后，添加 `test_l1_live_routing.py` 验证真实路由精度
- 集成 `presidio-analyzer` 后补齐 PII NER 测试
- 添加文件监听集成测试（需 tmp_path fixture + 文件修改 + sleep）
