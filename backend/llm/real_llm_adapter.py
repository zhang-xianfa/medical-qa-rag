"""
# =============================================================================
# 真实 LLM API 集成层 — 统一入口
#
# 本模块是"看病的大脑"的完整实现，包含三类核心能力：
# 1. RealLLMAdapter: 通用 LLM 适配器（继承 LLMAdapter，加 retry/fallback/logging）
# 2. RealRouterLLM:  L1 路由分诊台（判断用户该挂哪个科）
# 3. RealL2Adapter:  L2 专科问诊医生（按模板追问并强制 JSON 输出）
#
# 受约束 ADR: ADR-012/013/014 (all revised)
# 修订版本: v1.0-unified-20260619
# =============================================================================
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

from jinja2 import BaseLoader, Environment, Template
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 1. 配置加载：从环境变量读取，支持多厂商切换
# ──────────────────────────────────────────────


@dataclass
class LLMProviderConfig:
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model_name: str = "gpt-4o-mini"


def load_provider_config() -> LLMProviderConfig:
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    configs: dict[str, LLMProviderConfig] = {
        "openai": LLMProviderConfig(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            model_name=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        ),
        "deepseek": LLMProviderConfig(
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            model_name=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        ),
        "anthropic": LLMProviderConfig(
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1"),
            model_name=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        ),
    }
    return configs.get(provider, configs["openai"])


# ──────────────────────────────────────────────
# 2. RealLLMAdapter: 通用 LLM 适配器
# ──────────────────────────────────────────────


class LLMError(Exception):
    pass


class LLMAPIError(LLMError):
    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


class LLMParseError(LLMError):
    pass


class LLMRateLimitError(LLMError):
    pass


class LLMTimeoutError(LLMError):
    pass


class RealLLMAdapter:
    """
    通用 LLM 适配器。
    封装 AsyncOpenAI 调用，附加自动重试、Token 追踪、兜底降级。
    """

    MAX_RETRIES = 3

    def __init__(self, config: LLMProviderConfig | None = None) -> None:
        self.config = config or load_provider_config()
        self._client: AsyncOpenAI | None = None
        self._total_tokens: dict[str, int] = {"prompt": 0, "completion": 0, "total": 0}

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            if not self.config.api_key:
                raise LLMAPIError(
                    f"Missing API key for provider '{os.getenv('LLM_PROVIDER', 'unknown')}'. "
                    "Set the corresponding *_API_KEY environment variable.",
                    status_code=401,
                )
            self._client = AsyncOpenAI(api_key=self.config.api_key, base_url=self.config.base_url)
        return self._client

    # ── 非流式调用 ──

    async def generate(
        self,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.3,
        top_p: float = 0.9,
        force_json: bool = False,
    ) -> dict:
        kwargs: dict = {}

        last_error = ""
        for attempt in range(self.MAX_RETRIES):
            try:
                response = await self.client.chat.completions.create(
                    model=self.config.model_name,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    **kwargs,
                )
                raw = response.choices[0].message.content or "{}"
                self._record_tokens(response)
                logger.info(
                    "LLM generate success model=%s tokens=%s attempt=%d",
                    self.config.model_name,
                    self._token_summary(response),
                    attempt + 1,
                )
                if force_json:
                    parsed = _extract_json(raw)
                    if not parsed or not any(parsed.values()):
                        last_error = f"Empty JSON (attempt {attempt + 1})"
                        logger.warning("LLM returned completely empty JSON: %s", raw[:100])
                        continue
                    return parsed
                return {"content": raw, "token_usage": self._token_summary(response)}

            except (json.JSONDecodeError, ValueError) as e:
                last_error = f"Parse error (attempt {attempt + 1}): {e}"
                logger.warning("LLM parse attempt %d failed: %s", attempt + 1, e)
            except Exception as e:
                error_str = str(e).lower()
                if "timeout" in error_str:
                    last_error = f"LLMTimeoutError (attempt {attempt + 1}): {e}"
                elif "429" in error_str or "rate" in error_str:
                    last_error = f"LLMRateLimitError (attempt {attempt + 1}): {e}"
                    await asyncio.sleep(2.0 * (attempt + 1))
                    continue
                elif "401" in error_str or "403" in error_str or "unauthorized" in error_str:
                    logger.critical("LLM auth failure, aborting: %s", e)
                    raise LLMAPIError(str(e), status_code=401)
                else:
                    last_error = f"API error (attempt {attempt + 1}): {type(e).__name__}: {e}"
                logger.error("LLM API attempt %d failed: %s", attempt + 1, e)
            await asyncio.sleep(0.5 * (attempt + 1))

        logger.error("LLM all %d retries exhausted, returning fallback", self.MAX_RETRIES)
        fallback = _build_fallback_response(messages, force_json)
        return fallback

    # ── 流式调用 ──

    async def generate_stream(
        self,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.3,
        top_p: float = 0.9,
    ) -> AsyncIterator[str]:
        for attempt in range(self.MAX_RETRIES):
            try:
                stream = await self.client.chat.completions.create(
                    model=self.config.model_name,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    stream=True,
                )
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                return
            except Exception as e:
                logger.error("LLM stream attempt %d failed: %s", attempt + 1, e)
                await asyncio.sleep(0.5 * (attempt + 1))

        yield "请更详细地描述您的症状。"

    # ── Token 追踪 ──

    def _record_tokens(self, response) -> None:
        if response.usage:
            self._total_tokens["prompt"] += response.usage.prompt_tokens or 0
            self._total_tokens["completion"] += response.usage.completion_tokens or 0
            self._total_tokens["total"] += response.usage.total_tokens or 0

    @staticmethod
    def _token_summary(response) -> dict:
        if response.usage:
            return {
                "prompt_tokens": response.usage.prompt_tokens or 0,
                "completion_tokens": response.usage.completion_tokens or 0,
                "total_tokens": response.usage.total_tokens or 0,
            }
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    @property
    def token_usage(self) -> dict:
        return dict(self._total_tokens)


# ──────────────────────────────────────────────
# 3. Prompt 模板加载
# ──────────────────────────────────────────────

_jinja_env = Environment(loader=BaseLoader(), autoescape=False)


def _load_prompt_template(template_name: str) -> Template:
    prompt_dir = os.path.join(os.path.dirname(__file__), "..", "prompts")
    template_path = os.path.join(prompt_dir, f"{template_name}.j2")
    with open(template_path, "r", encoding="utf-8") as f:
        return _jinja_env.from_string(f.read())


def _build_fallback_response(messages: list, force_json: bool) -> dict:
    # 注意：messages 是发给 LLM 的 system/user prompt，不是用户对话消息。
    # 不要从中提取"用户原文"——会泄露 prompt 模板文本到前端。
    if force_json:
        return {
            "response_text": "抱歉，AI 服务暂时不可用，请稍后重试或更详细地描述您的症状。",
            "options": [
                {"index": 1, "label": "疼痛", "value": "疼痛"},
                {"index": 2, "label": "不适", "value": "不适"},
                {"index": 3, "label": "肿胀", "value": "肿胀"},
                {"index": 4, "label": "其他症状", "value": "other"},
                {"index": 5, "label": "说不太清楚", "value": "unclear"},
            ],
            "extracted_facts": {},
            "severity_assessment": "mild",
            "is_emergency": False,
            "next_action": "continue",
        }
    return {"content": "请更详细地描述您的症状。", "token_usage": {"total_tokens": 0}}


def _extract_json(raw: str) -> dict:
    raw = raw.strip()

    # 清洗常见的 prompt 泄露：LLM 有时会在 JSON 前附上模板标题
    # 例如 "## 输出格式（仅JSON）\n{...}" 或 "```json\n{...}\n```"
    raw = re.sub(r'^##\s*\S*\s*输出格式.*?\n', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'^```(?:json)?\s*\n', '', raw)
    raw = re.sub(r'\n```\s*$', '', raw)
    raw = raw.strip()

    m = re.search(r"\{.*\}", raw, re.DOTALL)
    target = m.group() if m else raw
    try:
        result = json.loads(target)
    except json.JSONDecodeError:
        try:
            fixed = re.sub(r'"\s*\n\s*"', '",\n"', target)
            result = json.loads(fixed)
        except json.JSONDecodeError:
            try:
                fixed2 = re.sub(r'(?<=[}\]"\d])\s*\n\s*"(?=[a-z_])', ',\n"', fixed)
                result = json.loads(fixed2)
            except json.JSONDecodeError:
                logger.warning("_extract_json: all strategies failed, raw[:200]=%s", raw[:200])
                return {}
    if not isinstance(result, dict):
        return {}
    cleaned = {k: v for k, v in result.items() if v is not None}
    if "response_text" in cleaned and _contains_prompt_leak(cleaned["response_text"]):
        logger.warning("_extract_json: prompt leak detected in response_text")
        return {}
    return cleaned


_SYSTEM_KEYWORDS = ["你是AI健康助手", "禁止确诊", "禁止开药", "安全红线", "提取规则",
                    "输出格式", "仅输出JSON", "extracted_facts", "severity_assessment"]


def _contains_prompt_leak(text: str) -> bool:
    return any(kw in text for kw in _SYSTEM_KEYWORDS)


# ──────────────────────────────────────────────
# 4. Pydantic 输出校验 Schema
# ──────────────────────────────────────────────


class ExtractedFacts(BaseModel):
    child_age: str | None = None
    body_temperature: str | None = None
    temperature_measure_method: str | None = None
    fever_duration: str | None = None
    mental_status: str | None = None
    fluid_intake: str | None = None
    urine_output: str | None = None
    skin_condition: str | None = None
    feeding_status: str | None = None
    accompanying_manifestations: str | None = None
    caregiver_concern: str | None = None
    model_config = {"extra": "allow"}


class L2ResponseSchema(BaseModel):
    response_text: str
    options: list[dict] = Field(default_factory=list)
    extracted_facts: dict = Field(default_factory=dict)
    severity_assessment: str = "mild"
    is_emergency: bool = False
    next_action: str = "continue"
    disclaimer: str = ""
    model_config = {"extra": "allow"}


class L1RouteSchema(BaseModel):
    scenario_id: str
    confidence: float
    rationale: str


class L1RouteListSchema(BaseModel):
    routes: list[L1RouteSchema]



# ──────────────────────────────────────────────
# 5. L1 路由分诊台
# ──────────────────────────────────────────────


class RealRouterLLM:
    ROUTE_SYSTEM_PROMPT = (
        "你是一个医疗咨询路由系统。你的任务是分析用户的输入，将用户分配到最合适的问诊场景。"
        "你必须仅返回一个JSON对象，格式如下："
        '{"routes":[{"scenario_id":"<id>","confidence":<0.0-1.0>,"rationale":"<理由>"}]}'
        "\n"
        "可用场景：\n"
        "- general_consultation: 通用健康咨询（成人不适、老年人、或无法明确分类的输入）\n"
        "\n"
        "规则：\n"
        "1. 仅返回JSON，不要添加任何解释文本\n"
        "2. confidence取值范围0.0-1.0，精确到小数点后两位\n"
        "3. 优先匹配最具体的场景"
    )

    def __init__(self) -> None:
        self.adapter = RealLLMAdapter()

    async def classify(self, user_message: str) -> list[tuple[str, float, str]]:

        async def _run():
            return await self.adapter.generate(
                messages=[
                    {"role": "system", "content": self.ROUTE_SYSTEM_PROMPT},
                    {"role": "user", "content": f"用户输入: {user_message}"},
                ],
                max_tokens=256,
                temperature=0.1,
                force_json=True,
            )

        result = await asyncio.wait_for(_run(), timeout=15)

        if result.get("_fallback"):
            return [("general_consultation", 0.0, "LLM调用失败，降级兜底")]
        try:
            parsed = L1RouteListSchema.model_validate(result)
        except ValidationError:
            return [("general_consultation", 0.0, "LLM输出Schema校验失败")]
        return [(r.scenario_id, r.confidence, r.rationale) for r in parsed.routes]


# ──────────────────────────────────────────────
# 6. L2 专科问诊
# ──────────────────────────────────────────────


class RealL2Adapter:
    def __init__(self, scenario_config: dict | None = None) -> None:
        self.adapter = RealLLMAdapter()
        self.scenario_config = scenario_config or {}

    async def generate_question(
        self,
        collected_facts: dict,
        scenario_context: dict,
        messages: list[dict],
        round_count: int,
        max_rounds: int,
    ) -> dict:

        template_name = scenario_context.get("prompt_template", "basic_consultation")
        template = _load_prompt_template(template_name)

        prompt_str = template.render(
            scenario_context=scenario_context,
            collected_facts=collected_facts,
            messages=messages,
            round_count=round_count,
            max_rounds=max_rounds,
        )
        system_prompt, user_content = _split_system_user(prompt_str)

        async def _run():
            return await self.adapter.generate(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=1024,
                temperature=0.3,
                force_json=True,
            )

        result = await asyncio.wait_for(_run(), timeout=60)

        try:
            validated = L2ResponseSchema.model_validate(result)
            return validated.model_dump()
        except ValidationError:
            logger.warning("LLM output failed schema validation, returning fallback")
            return {
                "response_text": "抱歉，我需要更多信息来帮助分析您的情况。请尝试用不同的方式描述您的症状。",
                "options": [
                    {"index": 1, "label": "重新描述症状", "value": "重新描述"},
                    {"index": 2, "label": "换个方式说", "value": "换种说法"},
                ],
                "extracted_facts": {},
                "severity_assessment": "mild",
                "is_emergency": False,
                "next_action": "continue",
                "disclaimer": "",
            }


def _split_system_user(prompt_str: str) -> tuple[str, str]:
    parts = prompt_str.split("## 输出格式")
    system = parts[0].strip() if parts else prompt_str
    user_instruction = (
        "请严格按照上述安全红线和提问规则，基于当前已采集信息和场景配置，"
        "生成下一轮提问并输出符合JSON Schema的响应。"
        "仅输出JSON，不要附加任何其他文字。"
    )
    if len(parts) > 1:
        user_instruction = "## 输出格式" + parts[1] + "\n\n" + user_instruction
    return system, user_instruction