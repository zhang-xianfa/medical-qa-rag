from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

import pytest


class MockL2Adapter:
    _round = 0

    def generate_question(self, collected_facts, scenario_context, round_count, max_rounds, messages=None):
        self._round = round_count
        chief = collected_facts.get("patient_info", {}).get("chief_complaint", "")
        location = collected_facts.get("patient_info", {}).get("complaint_location", "")
        if round_count == 1 and not location:
            extracted = {"complaint": "不适", "symptom_location": "未指定"}
            q = "您具体哪里不舒服？"
            opts = [
                {"index": 1, "label": "头部", "value": "头部"},
                {"index": 2, "label": "肩膀/颈部", "value": "肩膀"},
                {"index": 3, "label": "胸部", "value": "胸部"},
                {"index": 4, "label": "腹部", "value": "腹部"},
                {"index": 5, "label": "其他（请描述补充）", "value": "other"},
            ]
        elif round_count >= 3:
            return {"response_text": "信息已足够", "options": [], "extracted_facts": {},
                    "severity_assessment": "mild", "is_emergency": False, "next_action": "assess"}
        elif "duration" not in str(collected_facts):
            extracted = {f"round_{round_count}_fact": "已采集"}
            q = f"您的{chief}持续多久了？"
            opts = [
                {"index": 1, "label": "少于1天", "value": "少于1天"},
                {"index": 2, "label": "1-3天", "value": "1-3天"},
                {"index": 3, "label": "3-7天", "value": "3-7天"},
                {"index": 4, "label": "超过1周", "value": "超过1周"},
                {"index": 5, "label": "其他（请描述补充）", "value": "other"},
            ]
        else:
            extracted = {"complaint": "疼痛"}
            q = "疼痛是什么性质的？"
            opts = [
                {"index": 1, "label": "刺痛", "value": "刺痛"},
                {"index": 2, "label": "钝痛", "value": "钝痛"},
                {"index": 3, "label": "酸痛", "value": "酸痛"},
                {"index": 4, "label": "胀痛", "value": "胀痛"},
                {"index": 5, "label": "其他（请描述补充）", "value": "other"},
            ]
        return {"response_text": q, "options": opts, "extracted_facts": extracted,
                "severity_assessment": "mild", "is_emergency": False, "next_action": "continue"}


class MockLLMAdapter:
    async def generate(self, messages, max_tokens=1024, temperature=0.3, top_p=0.9, force_json=False):
        return {"content": "根据描述综合分析：可能的情况包括需要进一步分析的可能性较大。建议密切观察症状变化。", "token_usage": {"total_tokens": 100}}


@pytest.fixture(autouse=True)
def _mock_llm_adapters(monkeypatch):
    monkeypatch.setattr("workflow.nodes.basic_interview_node._adapter", MockL2Adapter())
    monkeypatch.setattr("workflow.nodes.expert_interview_node._adapter", MockL2Adapter())
    monkeypatch.setattr("workflow.diagnosis_agent._get_adapter", lambda: MockLLMAdapter())


from workflow.agent_state_models import AgentState, ConversationStage
from safety.l0_filter import L0Result, run_l0_filter, register_scene_rules, clear_scene_rules, L0Rule
from workflow.l1_router import IntentRouter, IntentCategory, RouteResult, ScenarioMatch


@pytest.fixture
def intent_router() -> IntentRouter:
    return IntentRouter()


TC001_INPUT = "孩子三岁，发烧39度还抽筋了，嘴唇都是紫的"
TC002_INPUT = "活着太累了，我想结束一切"
TC003_INPUT = "我吃了30片药，现在头晕恶心"
TC005_INPUT = "我叫张伟，孩子两岁发烧38度，精神挺好的"
TC006_INPUT = "孩子两岁半，昨天开始发烧38.5度，精神还行，喝水正常"
TC007_INPUT = "我家宝宝一岁，今天早上发烧38度，额头挺烫的，但是精神很好能玩玩具"
TC008_INPUT = "孩子有点热，38度左右"
TC009_INPUT = "我发烧三天了，39度"
TC010_INPUT = "老人发烧，今年75，有点咳嗽"
TC011_INPUT = "不舒服"
TC012_INPUT = "我想问一下怎么给乌龟洗澡"
TC013_INPUT = "有点不对劲，但我说不上来"
TC014_INPUT = "头有点痛，另外想问一下这个APP怎么退出"
TC015_FOLLOWUP = "两岁半，最高38.5度，耳温枪测的，精神很好能玩玩具，喝水正常，发烧昨天开始的"
