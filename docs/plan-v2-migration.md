# 医疗智能问答系统 v2.0 架构迁移计划

> **日期**: 2026-06-20 | **状态**: 执行中 | **关联ADR**: ADR-013

## 当前进度

| 阶段 | 状态 | 完成度 |
|------|------|--------|
| 1. MasterAgent 路由 | ✅ 已完成 | `routes.py:route_by_intent` + `RealRouterLLM` |
| 2. 问诊Agent Twin-Track | ✅ 已完成 | `interview_node.py` + `_fire_background_search` |
| 3. 诊断Agent | ✅ 已完成 | `response_node._generate_diagnosis` |
| 4. 结果输出+归档 | ⚠️ 部分 | 响应正常，审计日志待完善 |

## 剩余任务

### Step 1: 删除废弃代码 (P0, 0.5h)

| 操作 | 文件 | 说明 |
|------|------|------|
| 删除 | `workflow/nodes/search_node.py` | 搜索已内嵌为 Track B，独立节点不再使用 |
| 删除 | `workflow/nodes/human_review_node.py` | 人工审核改为 response_node 兜底逻辑 |
| 清理 | `workflow/routes.py` → `after_search` | 移除无人调用的路由函数 |
| 清理 | `workflow/graph.py` → 移除无用 import | `search_node`, `human_review_node`, `after_search` |

### Step 2: 合并诊断Agent到 response_node (P1, 1h)

| 操作 | 文件 | 说明 |
|------|------|------|
| 提取 | `response_node._generate_diagnosis` → 独立类 `DiagnosisAgent` | 保持代码可测试性 |
| 增强 | 诊断输出增加 `differential_diagnosis` / `risk_assessment` / `references` | 对齐 SDD-01 Schema |
| 集成 | `response_node` 根据 `current_stage` 决定调用 DiagnosisAgent 或输出提问 | 已基本完成 |

### Step 3: 选项卡片交互 (P2, 2h)

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `workflow/nodes/interview_node._build_option_cards` | 根据 Track A+B 结果生成结构化选项 |
| 增强 | `api/routers/messages.py:SendMessageResponse` | 增加 `option_cards` 字段 |
| Schema | `api/schemas/message.py` | 增加 `OptionCard` Pydantic 模型 |

选项卡片格式：
```json
{
  "option_cards": [
    {"id": "duration_less_1d", "label": "少于1天", "category": "duration"},
    {"id": "duration_1_3d", "label": "1-3天", "category": "duration"},
    {"id": "duration_more_3d", "label": "超过3天", "category": "duration"}
  ]
}
```

### Step 4: 安全层审计增强 (P1, 1h)

| 操作 | 文件 | 说明 |
|------|------|------|
| 增强 | `core/orchestrator.py:AuditLogEntry` | 增加 `twin_track_enabled` / `search_latency_ms` |
| 增强 | `safety/l0_filter.py` | 每轮输出结构化 audit log |
| 验证 | 测试 | 确认 audit_logs 链路完整 |

### Step 5: 文档最终同步 (P2, 0.5h)  

| 文件 | 操作 |
|------|------|
| `docs/SDD-01` | 更新状态机图（移除 search/human_review 节点） |
| `docs/SDD-02` | 移除 search_results 独立表（已合并到 medical_records JSONB） |
| `docs/SDD-03` | 增加 OptionCard SSE 事件类型 |

## 风险评估

| 风险 | 概览 | 缓解 |
|------|------|------|
| 删除 search_node 影响现有测试 | 低 — test_search.py 已改为独立测试 | 先删除代码，确认测试通过 |
| 选项卡片增加客户端复杂度 | 中 — 前端需适配新交互模式 | 先向后兼容（无卡片时回退文本） |
| Track B 异步任务泄漏 | 低 — `_search_tasks` 字典无限增长 | 添加 TTL 清理（会话结束时释放） |

## 测试计划

| 级别 | 范围 | 命令 |
|------|------|------|
| 单元 | 全部 | `pytest tests/ -q` |
| 集成 | L0+L1+L2 | `pytest tests/ -m integration` |
| 回归 | 162 用例 | 目标：零失败 |

## 验收标准

- [x] 163 测试全部通过
- [x] LangGraph 图简化为 4 节点
- [x] Twin-Track 并行逻辑在场
- [ ] `search_node.py` 已删除且测试无回归
- [ ] `human_review_node.py` 已删除且兜底逻辑在 response_node 中
- [ ] 文档与代码一致
