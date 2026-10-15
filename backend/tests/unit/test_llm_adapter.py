import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from llm.adapter import LLMAdapter, LLMConfig, ChatResponse, LLMTimeoutError, LLMAuthError, LLMRateLimitError


@pytest.fixture
def llm_config():
    return LLMConfig(
        provider="deepseek",
        model_name="deepseek-chat",
        base_url="https://api.deepseek.com/v1",
        api_key="test-key",
        temperature=0.3,
        max_tokens=4096,
        top_p=0.9,
    )


class MockChoice:
    def __init__(self, content, finish_reason="stop"):
        self.message = MagicMock(content=content)
        self.finish_reason = finish_reason


class MockUsage:
    prompt_tokens = 100
    completion_tokens = 50
    total_tokens = 150


class MockResponse:
    def __init__(self, content, model="deepseek-chat"):
        self.choices = [MockChoice(content)]
        self.usage = MockUsage()
        self.model = model


@pytest.mark.asyncio
async def test_chat_returns_chat_response_with_expected_fields(llm_config):
    adapter = LLMAdapter(config=llm_config)
    adapter.client = AsyncMock()
    adapter.client.chat.completions.create = AsyncMock(
        return_value=MockResponse("这是一条测试回复")
    )
    result = await adapter.chat([{"role": "user", "content": "你好"}])
    assert isinstance(result, ChatResponse)
    assert result.content == "这是一条测试回复"
    assert result.model == "deepseek-chat"
    assert result.token_usage["total_tokens"] == 150
    assert result.finish_reason == "stop"


@pytest.mark.asyncio
async def test_stream_chat_yields_tokens(llm_config):
    adapter = LLMAdapter(config=llm_config)

    class MockDelta:
        def __init__(self, content):
            self.content = content

    class MockStreamChunk:
        def __init__(self, content):
            self.choices = [MagicMock(delta=MockDelta(content))]

    class MockStream:
        def __init__(self):
            self._tokens = ["你", "好", "，", "世", "界"]
            self._idx = 0
        def __aiter__(self):
            return self
        async def __anext__(self):
            if self._idx >= len(self._tokens):
                raise StopAsyncIteration
            token = self._tokens[self._idx]
            self._idx += 1
            return MockStreamChunk(token)

    async def mock_stream(*args, **kwargs):
        return MockStream()

    adapter.client.chat.completions.create = mock_stream
    tokens = []
    async for token in adapter.stream_chat([{"role": "user", "content": "你好"}]):
        tokens.append(token)
    assert tokens == ["你", "好", "，", "世", "界"]


@pytest.mark.asyncio
async def test_chat_raises_llm_auth_error_on_401(llm_config):
    adapter = LLMAdapter(config=llm_config)
    adapter.client.chat.completions.create = AsyncMock(side_effect=Exception("401 Unauthorized"))
    with pytest.raises(LLMAuthError):
        await adapter.chat([{"role": "user", "content": "test"}])


@pytest.mark.asyncio
async def test_chat_raises_llm_rate_limit_error_on_429(llm_config):
    adapter = LLMAdapter(config=llm_config)
    adapter.client.chat.completions.create = AsyncMock(side_effect=Exception("429 rate limit exceeded"))
    with pytest.raises(LLMRateLimitError):
        await adapter.chat([{"role": "user", "content": "test"}])


@pytest.mark.asyncio
async def test_chat_raises_llm_timeout_error(llm_config):
    adapter = LLMAdapter(config=llm_config)
    adapter.client.chat.completions.create = AsyncMock(side_effect=Exception("request timeout"))
    with pytest.raises(LLMTimeoutError):
        await adapter.chat([{"role": "user", "content": "test"}])


@pytest.mark.asyncio
async def test_init_client_uses_config_base_url(llm_config):
    adapter = LLMAdapter(config=llm_config)
    assert str(adapter.client.base_url).rstrip("/") == "https://api.deepseek.com/v1"


def test_config_dataclass_defaults():
    config = LLMConfig(provider="openai", model_name="gpt-4o", base_url="https://api.openai.com/v1", api_key="key")
    assert config.temperature == 0.3
    assert config.max_tokens == 4096
    assert config.top_p == 0.9
