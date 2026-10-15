import uuid
from persistence.models.audit_log import AuditLog


def test_audit_log_instantiation_with_all_fields():
    log = AuditLog(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        agent_name="diagnosis",
        event_type="diagnosis_generate",
        input_summary={"collected_info_keys": ["chief_complaint", "duration"]},
        output_summary={"diagnosis": "紧张性头痛"},
        token_usage={"prompt_tokens": 1024, "completion_tokens": 512, "total_tokens": 1536},
        latency_ms=3200,
        model_name="deepseek-chat",
        red_flag_triggered=False,
        safety_check={"content_filtered": False, "disclaimer_appended": True},
    )
    assert log.id is not None
    assert log.agent_name == "diagnosis"
    assert log.event_type == "diagnosis_generate"
    assert log.token_usage["total_tokens"] == 1536
    assert log.safety_check["disclaimer_appended"] is True


def test_audit_log_red_flag_triggered_default_is_false():
    log = AuditLog(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        agent_name="master",
        event_type="intent_detect",
        input_summary={},
        output_summary={},
        token_usage={"total_tokens": 100},
        latency_ms=100,
        model_name="deepseek-chat",
        red_flag_triggered=False,
    )
    assert log.red_flag_triggered is False


def test_audit_log_error_info_nullable():
    log = AuditLog(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        agent_name="search",
        event_type="search_execute",
        input_summary={},
        output_summary={},
        token_usage={"total_tokens": 200},
        latency_ms=500,
        model_name="deepseek-chat",
        error_info=None,
    )
    assert log.error_info is None


def test_audit_log_safety_check_default():
    log = AuditLog(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        agent_name="interview",
        event_type="question_generate",
        input_summary={},
        output_summary={},
        token_usage={"total_tokens": 300},
        latency_ms=200,
        model_name="deepseek-chat",
        safety_check={},
    )
    assert log.safety_check == {}
