# 双通道问诊架构计划

> 日期: 2026-06-24 | 状态: ✅ 已完成 (实际实现与计划有调整)

## 实际实现与计划的差异

| 维度 | 原始计划 | 实际实现 |
|------|---------|---------|
| 路由方式 | 按轮次二选一 | **阶段性串行**：基础完成→自动进入专家 |
| 专家触发 | `route_interview_type` 根据 round 判断 | `check_basic_interview_complete` 根据 `current_stage` 判断 |
| 后台搜索 | 保留 Track B 异步 | **已删除**，专家节点改为同步 `await` |
| 轮次上限 | `max_rounds=5` | `max_rounds=10`, `basic_max_rounds=5` (各一半) |
| 图节点 | safety→route→basic/expert→response | safety→basic(loop)→expert(loop)→response |

## 最终架构

```
safety_check → basic_interview(循环) → expert_interview(循环) → response → END
                   │                          │
              纯 prompt 模板              RAG 知识增强
              basic_max_rounds=5         max_rounds=10 (总)
```

## 文件变更清单

| 操作 | 文件 |
|------|------|
| 新建 | `workflow/nodes/_shared.py` |
| 新建 | `workflow/nodes/basic_interview_node.py` |
| 新建 | `workflow/nodes/expert_interview_node.py` |
| 新建 | `prompts/expert_consultation.j2` |
| 删除 | `workflow/nodes/interview_node.py` |
| 修改 | `workflow/routes.py` (+check_basic/expert_complete) |
| 修改 | `workflow/graph.py` (+双节点+阶段边) |
| 修改 | `api/routers/messages.py` (scenario_config) |
| 修改 | `tests/conftest.py` (mock路径) |
| 修改 | `tests/unit_nodes/test_interview.py` (导入路径) |
| 修改 | `tests/unit/test_routes.py` (新路由测试) |

## 配置

```python
# messages.py:_detect_scenario
{
    "max_rounds": 10,
    "use_expert": True,
    "basic_max_rounds": 5,
}
```
