# 受约束ADR: ADR-013 (revised, AUDIT-FIX: TC-019)
# 补充约束: ADR-012 (collected_facts动态键值对)
# 修订版本: v1.0-audit-fix-20260619

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from workflow.agent_state_models import AgentState, ScenarioContext

"""
问诊场景基类模板（标准模具）
定义所有医疗问诊场景的统一结构、终止规则与默认值填充逻辑，具体场景必须继承本类并实现问答生成方法。

核心职责：
1. 场景配置标准化：通过 ScenarioConfig 统一管理必填/选填事实、轮次限制、终止条件、缺失默认值等参数
2. 上下文构建：将静态配置 + 动态路由置信度封装为 ScenarioContext，供 L2 问诊节点使用
3. 智能终止判定：同时满足「最小轮次」+「必填事实收集率达标」或「达到最大轮次」时自动结束问诊
4. 缺失事实兜底：问诊结束时自动用预设默认值填充未收集到的必填事实，避免后续评估报错

关键约束：
- generate_first_question / generate_next_question 为抽象方法，子类必须实现，禁止在基类中提供默认实现
- 终止条件中的 required_ratio 阈值不得低于 0.5，防止信息不足时过早进入评估
- missing_fact_defaults 仅用于填充 required_facts 中缺失的字段，不可覆盖已收集的事实
- 所有配置字段必须可序列化，支持审计日志完整记录场景参数
"""

@dataclass
class ScenarioConfig:
    scenario_id: str = ""
    display_name: str = ""
    version: str = "1.0"
    description: str = ""
    required_facts: list[str] = field(default_factory=list)
    optional_facts: list[str] = field(default_factory=list)
    max_rounds: int = 5
    min_rounds: int = 2
    termination_conditions: dict = field(default_factory=dict)
    missing_fact_defaults: dict = field(default_factory=dict)  # AUDIT-FIX: TC-019
    safety_rules: dict = field(default_factory=dict)
    prompt_template: str = ""
    output_schema_version: str = "1.0"


class BaseScenario(ABC):
    def __init__(self, config: ScenarioConfig) -> None:
        self.config = config

    def build_scenario_context(self, route_confidence: float, intent_category: str) -> ScenarioContext:
        return ScenarioContext(
            scenario_id=self.config.scenario_id,
            display_name=self.config.display_name,
            description=self.config.description,
            required_facts=list(self.config.required_facts),
            optional_facts=list(self.config.optional_facts),
            max_rounds=self.config.max_rounds,
            min_rounds=self.config.min_rounds,
            route_confidence=route_confidence,
            intent_category=intent_category,
            termination_conditions=self.config.termination_conditions,
            missing_fact_defaults=self.config.missing_fact_defaults,
        )

    def check_termination(self, state: AgentState) -> bool:
        tc = self.config.termination_conditions
        min_facts = tc.get("min_facts_collected", 3)
        required_ratio = tc.get("required_ratio", 0.7)
        if state.round_count >= self.config.max_rounds:
            return True
        collected = len(state.collected_facts)
        if collected >= min_facts:
            required_collected = sum(
                1 for f in self.config.required_facts if f in state.collected_facts
            )
            ratio = required_collected / max(len(self.config.required_facts), 1)
            if ratio >= required_ratio:
                return True
        return False

    def fill_defaults(self, state: AgentState) -> AgentState:
        defaults = self.config.missing_fact_defaults
        for fact_name in self.config.required_facts:
            if fact_name not in state.collected_facts and fact_name in defaults:
                state.collected_facts[fact_name] = defaults[fact_name]
        return state

    @abstractmethod
    def generate_first_question(self, state: AgentState) -> str:
        ...

    @abstractmethod
    def generate_next_question(self, state: AgentState) -> str:
        ...
