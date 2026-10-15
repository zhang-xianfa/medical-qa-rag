from typing import AsyncIterator, Optional
from dataclasses import dataclass

from openai import AsyncOpenAI

from config.settings import load_llm_config, LLMConfig


@dataclass
class ChatResponse:
    """
    LLM 统一响应结构体。

    屏蔽不同模型厂商返回格式的差异，确保上层业务始终通过
    content / token_usage / model / finish_reason 四个标准字段获取结果，
    避免各场景代码直接依赖特定 SDK 的响应对象。
    """
    content: str          # 模型生成的文本内容（空响应时默认为 ""）
    token_usage: dict     # Token 消耗明细: {prompt_tokens, completion_tokens, total_tokens}
    model: str            # 实际响应的模型标识（可能与请求模型不同，如 gpt-4o -> gpt-4o-2024-05-13）
    finish_reason: str    # 停止原因: stop / length / content_filter / unknown


class LLMTimeoutError(Exception):
    """LLM 请求超时异常。通常由网络抖动或服务端负载过高引起，建议上层做指数退避重试。"""
    pass


class LLMAuthError(Exception):
    """LLM 认证失败异常（401/403）。API Key 无效或权限不足，不应重试，需立即告警排查。"""
    pass


class LLMRateLimitError(Exception):
    """LLM 限流异常（429）。触发 RPM/TPM 上限，建议上层排队等待或降级处理。"""
    pass


class LLMAdapter:
    """
    LLM 统一适配层（AI 模型调用网关）。

    职责：
      1. 封装 AsyncOpenAI SDK，对上层提供稳定的 chat / stream_chat 接口；
      2. 将底层 HTTP 异常翻译为语义化的业务异常，便于差异化处理；
      3. 统一管理默认参数注入与 Token 用量提取；
      4. 解耦具体模型厂商，切换模型时仅需修改本类，上层场景代码零改动。

    注意：本适配器仅负责"调用"，不包含 Prompt 拼接、对话历史管理等业务逻辑，
    那些职责由各 Scenario 自行管理，保持适配层的纯粹性。
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        """
        初始化 LLM 适配器。

        Args:
            config: LLM 配置对象。传 None 时自动从配置文件加载，
                    方便测试时注入 Mock 配置。
        """
        if config is None:
            config = load_llm_config()
        self.config = config
        self.client = self._init_client(config)

    def _init_client(self, config: LLMConfig) -> AsyncOpenAI:
        """
        创建异步 OpenAI 客户端实例。

        通过 base_url 参数兼容所有 OpenAI 协议的服务（Azure、通义、本地 vLLM 等），
        无需为每个厂商编写独立的客户端初始化逻辑。
        """
        return AsyncOpenAI(api_key=config.api_key, base_url=config.base_url)

    async def chat(self, messages: list[dict], **kwargs) -> ChatResponse:
        """
        非流式 LLM 对话调用。

        Args:
            messages: OpenAI 格式的消息列表 [{"role": ..., "content": ...}]
            **kwargs: 可选覆盖参数 (temperature / max_tokens / top_p)，
                      未传入时使用 config 中的默认值。

        Returns:
            ChatResponse: 标准化的响应对象。

        Raises:
            LLMTimeoutError: 请求超时
            LLMAuthError: 认证失败
            LLMRateLimitError: 触发限流
            Exception: 其他未识别的原始异常（直接透传）
        """
        temperature = kwargs.get("temperature", self.config.temperature)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
        top_p = kwargs.get("top_p", self.config.top_p)
        try:
            response = await self.client.chat.completions.create(
                model=self.config.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
            )
        except Exception as e:
            # ⚠️ TODO: 字符串匹配方式脆弱，建议改为捕获 SDK 原生异常类型：
            #   from openai import APITimeoutError, AuthenticationError, RateLimitError
            error_str = str(e).lower()
            if "timeout" in error_str:
                raise LLMTimeoutError(f"LLM request timed out: {e}") from e
            if "401" in error_str or "unauthorized" in error_str or "403" in error_str:
                raise LLMAuthError(f"LLM authentication failed: {e}") from e
            if "429" in error_str or "rate" in error_str:
                raise LLMRateLimitError(f"LLM rate limited: {e}") from e
            raise

        choice = response.choices[0]
        return ChatResponse(
            content=choice.message.content or "",
            token_usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            model=response.model,
            finish_reason=choice.finish_reason or "unknown",
        )

    async def stream_chat(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        """
        流式 LLM 对话调用。

        将 SSE 流转换为 Python 异步迭代器，上层通过 async for 逐块消费文本，
        无需手动解析 chunk 结构或处理流结束信号。

        Args / kwargs: 同 chat() 方法。

        Yields:
            str: 每次产出一个增量文本片段。

        Note:
            当前仅 yield 文本内容，不携带 finish_reason / token_usage。
            如需流结束元信息，建议在末尾额外 yield 一个特殊标记对象。
        """
        temperature = kwargs.get("temperature", self.config.temperature)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
        top_p = kwargs.get("top_p", self.config.top_p)
        try:
            stream = await self.client.chat.completions.create(
                model=self.config.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                stream=True,
            )
        except Exception as e:
            error_str = str(e).lower()
            if "timeout" in error_str:
                raise LLMTimeoutError(f"LLM stream timed out: {e}") from e
            if "401" in error_str or "unauthorized" in error_str or "403" in error_str:
                raise LLMAuthError(f"LLM authentication failed: {e}") from e
            if "429" in error_str or "rate" in error_str:
                raise LLMRateLimitError(f"LLM rate limited: {e}") from e
            raise

        async for chunk in stream:
            # 防御性检查：部分厂商在流首尾会发送空 delta，需过滤避免 yield None
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content