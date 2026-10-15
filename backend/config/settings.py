from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/medical_qa"
    DATABASE_SYNC_URL: str = "postgresql://postgres:postgres@localhost:5432/medical_qa"

    LLM_PROVIDER: str = "deepseek"
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    EMBEDDING_PROVIDER: str = "aliyun"
    EMBEDDING_API_KEY: Optional[str] = None
    EMBEDDING_MODEL: str = "text-embedding-v4"
    EMBEDDING_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    VECTOR_DIM: int = 1024
    VECTOR_STORE_BACKEND: str = "pgvector"

    MAX_INTERVIEW_ROUNDS: int = 5
    RED_FLAG_ENABLED: bool = True
    PII_MASKING_ENABLED: bool = True
    CONTENT_RAW_RETENTION_DAYS: int = 30

    ENCRYPTION_KEY: Optional[str] = None
    DISCLAIMER_TEXT: str = "本内容仅供参考，不能替代专业医疗诊断。如有不适，请及时就医。"

    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:8000"]
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@dataclass
class LLMConfig:
    provider: str
    model_name: str
    base_url: str
    api_key: str
    temperature: float = 0.3
    max_tokens: int = 4096
    top_p: float = 0.9
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbeddingConfig:
    provider: str
    model: str
    base_url: str
    api_key: str
    dimensions: int = 1536


def load_llm_config(config_path: Optional[str] = None) -> LLMConfig:
    if config_path is None:
        config_path = Path(__file__).parent / "llm.yaml"

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    settings = Settings()
    active = data.get("active", {})
    provider_name = active.get("provider", settings.LLM_PROVIDER)
    model_name = active.get("model", settings.DEEPSEEK_MODEL)

    providers = data.get("providers", {})
    provider_data = providers.get(provider_name, {})

    base_url = provider_data.get("base_url", settings.DEEPSEEK_BASE_URL)
    api_key = _resolve_api_key(provider_name, settings)

    params = active.get("parameters", {})
    return LLMConfig(
        provider=provider_name,
        model_name=model_name,
        base_url=base_url,
        api_key=api_key,
        temperature=params.get("temperature", 0.3),
        max_tokens=params.get("max_tokens", 4096),
        top_p=params.get("top_p", 0.9),
        extra_params=params.get("extra", {}),
    )


def load_embedding_config(config_path: Optional[str] = None) -> EmbeddingConfig:
    if config_path is None:
        config_path = Path(__file__).parent / "llm.yaml"

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    settings = Settings()
    embedding = data.get("embedding", {})
    provider_name = embedding.get("provider", settings.EMBEDDING_PROVIDER)
    model = embedding.get("model", settings.EMBEDDING_MODEL)

    providers = data.get("providers", {})
    provider_data = providers.get(provider_name, {})
    base_url = provider_data.get("embedding_base_url", settings.EMBEDDING_BASE_URL)
    api_key = _resolve_api_key(provider_name, settings)

    return EmbeddingConfig(
        provider=provider_name,
        model=model,
        base_url=base_url,
        api_key=api_key,
        dimensions=settings.VECTOR_DIM,
    )


def load_safety_rules(config_path: Optional[str] = None) -> dict:
    if config_path is None:
        config_path = Path(__file__).parent / "safety_rules.yaml"

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {}


def _resolve_api_key(provider_name: str, settings: Settings) -> str:
    key_map = {
        "deepseek": settings.DEEPSEEK_API_KEY,
        "aliyun": settings.EMBEDDING_API_KEY,
    }
    return key_map.get(provider_name, "") or ""
