# 受约束ADR: ADR-012 (revised, AUDIT-FIX: TC-002 / 待澄清项A2)
# 受约束ADR: ADR-014 (revised, AUDIT-FIX: TC-001/003/012/014/024)
# 修订版本: v1.0-audit-fix-20260619

from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

"""
本模块定义了LangGraph工作流的核心状态模型(AgentState)及关联枚举/子模型。
所有工作流节点(interview/search/safety/response/human_review)均通过读写此状态进行协同，
禁止在节点间直接传递参数或引入额外的全局变量。
"""

class Severity(str, Enum):
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    EMERGENCY = "emergency"


class ConversationStage(str, Enum):
    INIT = "init"
    COLLECTING = "collecting"
    ASSESSING = "assessing"
    COMPLETED = "completed"


class RedFlagLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"


class ScenarioContext(BaseModel):
    scenario_id: str = ""
    display_name: str = ""
    description: str = ""
    required_facts: list[str] = Field(default_factory=list)
    optional_facts: list[str] = Field(default_factory=list)
    max_rounds: int = 5
    min_rounds: int = 2
    route_confidence: float = 0.0
    intent_category: str = "unclear"
    alternatives: list[dict] = Field(default_factory=list)
    human_review: bool = False
    termination_conditions: dict = Field(default_factory=dict)
    missing_fact_defaults: dict = Field(default_factory=dict)  # AUDIT-FIX: TC-019


class AgentState(BaseModel):
    session_id: str
    messages: list[dict] = Field(default_factory=list)
    chief_complaint: Optional[str] = None
    severity: Optional[Severity] = None
    is_emergency: bool = False
    red_flag_level: Optional[RedFlagLevel] = None  # AUDIT-FIX: TC-002
    conversation_stage: ConversationStage = ConversationStage.INIT
    collected_facts: dict = Field(default_factory=dict)
    scenario_context: Optional[ScenarioContext] = None
    safety_checks_passed: bool = True
    round_count: int = 0
    max_rounds: int = 5
    diagnosis_result: Optional[dict] = None
