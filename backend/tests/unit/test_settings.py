import os
import pytest
from config.settings import Settings, load_safety_rules, LLMConfig, EmbeddingConfig


def test_settings_defaults():
    os.environ["DEEPSEEK_API_KEY"] = "test-key"
    s = Settings()
    assert s.MAX_INTERVIEW_ROUNDS == 5
    assert s.RED_FLAG_ENABLED is True
    assert s.PII_MASKING_ENABLED is True
    assert s.CONTENT_RAW_RETENTION_DAYS == 30
    assert s.LOG_LEVEL == "INFO"
    assert "不能替代专业医疗诊断" in s.DISCLAIMER_TEXT


def test_settings_env_override():
    os.environ["MAX_INTERVIEW_ROUNDS"] = "3"
    os.environ["DEEPSEEK_API_KEY"] = "test-key"
    s = Settings()
    assert s.MAX_INTERVIEW_ROUNDS == 3


def test_vector_store_backend_default():
    os.environ["DEEPSEEK_API_KEY"] = "test-key"
    s = Settings()
    assert s.VECTOR_STORE_BACKEND == "pgvector"


def test_load_safety_rules_returns_dict():
    rules = load_safety_rules()
    assert isinstance(rules, dict)
