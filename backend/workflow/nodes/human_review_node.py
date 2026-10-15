from config.settings import Settings


settings = Settings()


async def human_review_node(state: dict) -> dict:
    fallback_output = "系统暂时无法给出具体建议。建议您及时就医咨询专业医生，以确保获得准确的诊断和治疗方案。如有紧急情况，请立即拨打120。"
    return {
        "messages": [{"role": "assistant", "content": fallback_output}],
        "current_stage": "done",
        "fallback_triggered": True,
        "diagnosis_result": {
            "primary_diagnosis": {"name": "待人工审核", "probability": "N/A", "rationale": "系统自动降级", "certainty_level": "low"},
            "differential_diagnosis": [],
            "risk_assessment": {"severity": "未确定", "urgency": "建议门诊", "warning_signs": []},
            "recommendations": [{"category": "就医建议", "content": "请及时就医咨询专业医生", "priority": 1}],
            "red_flags": [],
            "references": [],
            "disclaimer": settings.DISCLAIMER_TEXT,
        },
    }
