"""B1: LLM 抽象接口、工厂与实现 — 单元测试。"""

from __future__ import annotations

from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.libs.base.base_llm import BaseLLM, LLMResponse
from app.libs.factory import LLMFactory
from app.libs.llm import OpenAILLM, OllamaLLM, DeepSeekLLM


# =============================================================================
# B1.1 — BaseLLM 抽象接口
# =============================================================================


class TestBaseLLM:
    """测试 BaseLLM 抽象基类的公共方法。"""

    def test_build_messages_from_prompt(self):
        """prompt → 自动构造单条 user message。"""
        llm = _create_dummy_llm()
        msgs = llm._build_messages(prompt="Hello")
        assert msgs == [{"role": "user", "content": "Hello"}]

    def test_build_messages_from_messages(self):
        """messages 完整传入。"""
        llm = _create_dummy_llm()
        msgs = llm._build_messages(
            messages=[{"role": "system", "content": "You are a bot."}]
        )
        assert msgs == [{"role": "system", "content": "You are a bot."}]

    def test_build_messages_messages_priority(self):
        """messages 比 prompt 优先级高。"""
        llm = _create_dummy_llm()
        msgs = llm._build_messages(
            prompt="prompt",
            messages=[{"role": "user", "content": "msg"}],
        )
        assert msgs == [{"role": "user", "content": "msg"}]

    def test_build_messages_raises_on_empty(self):
        """prompt 和 messages 都未提供 → ValueError。"""
        llm = _create_dummy_llm()
        with pytest.raises(ValueError, match="prompt 或 messages"):
            llm._build_messages()

    def test_init_saves_model_and_kwargs(self):
        llm = _create_dummy_llm(model="test-model", api_key="sk-key")
        assert llm.model == "test-model"
        assert llm._kwargs.get("api_key") == "sk-key"


# =============================================================================
# B1.2 — LLMFactory 工厂
# =============================================================================


class TestLLMFactory:
    """测试 LLMFactory 的注册与创建。"""

    def test_create_openai(self):
        """openai provider → OpenAILLM。"""
        llm = LLMFactory.create("openai", "gpt-4o")
        assert isinstance(llm, OpenAILLM)
        assert llm.model == "gpt-4o"

    def test_create_azure(self):
        """azure provider → OpenAILLM（同一实现类）。"""
        llm = LLMFactory.create("azure", "gpt-4o")
        assert isinstance(llm, OpenAILLM)

    def test_create_deepseek(self):
        """deepseek provider → DeepSeekLLM（专用实现）。"""
        llm = LLMFactory.create("deepseek", "deepseek-v4-flash")
        assert isinstance(llm, DeepSeekLLM)
        assert llm.model == "deepseek-v4-flash"

    def test_create_ollama(self):
        """ollama provider → OllamaLLM。"""
        llm = LLMFactory.create("ollama", "qwen2.5:7b")
        assert isinstance(llm, OllamaLLM)
        assert llm.model == "qwen2.5:7b"

    def test_create_unknown_provider(self):
        """未知 provider → ValueError。"""
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            LLMFactory.create("unknown_provider", "model")

    def test_create_with_default_settings(self):
        """不传 provider，使用 settings 默认值。"""
        llm = LLMFactory.create()
        assert isinstance(llm, (OpenAILLM, OllamaLLM, DeepSeekLLM))

    def test_registry_is_singleton(self):
        """_registry 是类级别单例。"""
        assert "openai" in LLMFactory._registry
        assert "ollama" in LLMFactory._registry


# =============================================================================
# B7.1 — OpenAILLM 实现
# =============================================================================


class TestOpenAILLM:
    """测试 OpenAILLM 实现。"""

    @pytest.fixture
    def mock_openai_client(self):
        """Mock openai.AsyncClient 在 _get_client 中返回。"""
        with patch("app.libs.llm.openai.AsyncClient") as mock_cls:
            client = AsyncMock()
            mock_cls.return_value = client
            yield client

    @pytest.fixture
    def llm(self) -> OpenAILLM:
        return OpenAILLM(
            model="gpt-4o",
            api_key="sk-test",
            base_url="https://test.api.com/v1",
        )

    def test_init_no_client_created(self):
        """初始化时不创建 AsyncClient（延迟初始化）。"""
        llm = OpenAILLM(model="gpt-4o", api_key="sk-test")
        assert llm._client is None
        assert llm.model == "gpt-4o"
        assert llm._api_key == "sk-test"

    @pytest.mark.asyncio
    async def test_generate_basic(self, mock_openai_client, llm):
        """正常生成回答。"""
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello, world!"
        mock_choice.finish_reason = "stop"
        mock_usage = MagicMock()
        mock_usage.model_dump.return_value = {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        }

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4o"
        mock_response.usage = mock_usage

        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        result = await llm.generate(prompt="Hello")
        assert isinstance(result, LLMResponse)
        assert result.content == "Hello, world!"
        assert result.model == "gpt-4o"
        assert result.usage == {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        }
        assert result.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_generate_with_messages(self, mock_openai_client, llm):
        """使用 messages 格式调用。"""
        mock_choice = MagicMock()
        mock_choice.message.content = "Response via messages"
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4o"
        mock_response.usage = None

        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        result = await llm.generate(
            messages=[
                {"role": "system", "content": "You are a bot."},
                {"role": "user", "content": "Hi"},
            ]
        )
        assert result.content == "Response via messages"

    @pytest.mark.asyncio
    async def test_generate_stream(self, mock_openai_client, llm):
        """流式生成应逐个 yield chunk。"""
        chunks = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello "))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content="world!"))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=None))]),
        ]
        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=_async_iter(chunks)
        )

        collected = []
        async for token in llm.generate_stream(prompt="Hi"):
            collected.append(token)
        assert collected == ["Hello ", "world!"]

    @pytest.mark.asyncio
    async def test_count_tokens(self, llm):
        """Token 计数应合理。"""
        count = await llm.count_tokens("Hello world")
        assert isinstance(count, int)
        assert count > 0

    @pytest.mark.asyncio
    async def test_count_tokens_chinese(self, llm):
        """中文 Token 计数。"""
        count = await llm.count_tokens("你好世界")
        assert count >= 2


# =============================================================================
# B7.2 — OllamaLLM 实现
# =============================================================================


class TestOllamaLLM:
    """测试 OllamaLLM 实现。"""

    @pytest.fixture
    def mock_ollama_client(self):
        """Mock openai.AsyncClient in OllamaLLM。"""
        with patch("app.libs.llm.ollama.AsyncClient") as mock_cls:
            client = AsyncMock()
            mock_cls.return_value = client
            yield client

    @pytest.fixture
    def llm(self) -> OllamaLLM:
        return OllamaLLM(
            model="qwen2.5:7b",
            api_key="ollama",
            base_url="http://127.0.0.1:11434/v1",
        )

    def test_init_default_base_url(self):
        """无 base_url 时使用默认值。"""
        llm = OllamaLLM(model="llama3.2:3b")
        assert llm._base_url == "http://127.0.0.1:11434/v1"
        assert llm._client is None  # 延迟初始化

    @pytest.mark.asyncio
    async def test_generate_basic(self, mock_ollama_client, llm):
        """正常生成回答。"""
        mock_choice = MagicMock()
        mock_choice.message.content = "你好，我是助手"
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "qwen2.5:7b"
        mock_response.usage = None

        mock_ollama_client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        result = await llm.generate(prompt="你好")
        assert result.content == "你好，我是助手"
        assert result.model == "qwen2.5:7b"

    @pytest.mark.asyncio
    async def test_generate_stream(self, mock_ollama_client, llm):
        """流式生成。"""
        chunks = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content="你好"))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content="，我是"))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=None))]),
        ]
        mock_ollama_client.chat.completions.create = AsyncMock(
            return_value=_async_iter(chunks)
        )

        collected = []
        async for token in llm.generate_stream(prompt="你好"):
            collected.append(token)
        assert "".join(collected) == "你好，我是"

    @pytest.mark.asyncio
    async def test_count_tokens(self, llm):
        """Token 计数。"""
        count = await llm.count_tokens("Hello world")
        assert isinstance(count, int)
        assert count > 0

# =============================================================================
# B1.3 — DeepSeekLLM 实现
# =============================================================================


class TestDeepSeekLLM:
    """测试 DeepSeekLLM 实现。

    验证 DeepSeek 特有的：
    - reasoning_content 提取
    - usage 中的 cache 字段
    - 默认 base_url
    """

    @pytest.fixture
    def mock_deepseek_client(self):
        """Mock openai.AsyncClient in DeepSeekLLM。"""
        with patch("app.libs.llm.deepseek.AsyncClient") as mock_cls:
            client = AsyncMock()
            mock_cls.return_value = client
            yield client

    @pytest.fixture
    def llm(self) -> DeepSeekLLM:
        return DeepSeekLLM(
            model="deepseek-v4-flash",
            api_key="sk-deepseek-test",
            base_url="https://api.deepseek.com",
        )

    def test_init_default_base_url(self):
        """无 base_url 时使用官方的默认值。"""
        llm = DeepSeekLLM(model="deepseek-chat")
        assert llm._base_url == "https://api.deepseek.com"
        assert llm._client is None  # 延迟初始化

    def test_init_no_client_created(self):
        """初始化时不创建 AsyncClient。"""
        llm = DeepSeekLLM(model="deepseek-chat", api_key="sk-test")
        assert llm._client is None

    @pytest.mark.asyncio
    async def test_generate_with_usage(self, mock_deepseek_client, llm):
        """正常生成，验证 usage 包含 DeepSeek 扩展字段。"""
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello from DeepSeek!"
        mock_choice.finish_reason = "stop"

        # DeepSeek 扩展 usage（包含缓存字段）
        mock_usage = MagicMock()
        mock_usage.model_dump.return_value = {
            "prompt_tokens": 25,
            "completion_tokens": 10,
            "total_tokens": 35,
            "prompt_cache_hit_tokens": 10,
            "prompt_cache_miss_tokens": 15,
        }

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "deepseek-v4-flash"
        mock_response.usage = mock_usage

        mock_deepseek_client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        result = await llm.generate(prompt="Hello")
        assert isinstance(result, LLMResponse)
        assert result.content == "Hello from DeepSeek!"
        assert result.model == "deepseek-v4-flash"
        assert result.usage is not None
        assert result.usage["prompt_cache_hit_tokens"] == 10
        assert result.usage["prompt_cache_miss_tokens"] == 15
        assert result.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_generate_with_reasoning_content(self, mock_deepseek_client, llm):
        """DeepSeek-R1 等模型返回 reasoning_content。"""
        mock_message = MagicMock()
        mock_message.content = "Final answer"
        mock_message.reasoning_content = "思考中...逐步推理"

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "deepseek-reasoner"
        mock_response.usage = None

        mock_deepseek_client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        result = await llm.generate(prompt="思考一个问题")
        assert result.content == "Final answer"

    @pytest.mark.asyncio
    async def test_generate_with_messages(self, mock_deepseek_client, llm):
        """使用 messages 格式调用。"""
        mock_choice = MagicMock()
        mock_choice.message.content = "Response via messages"
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "deepseek-v4-flash"
        mock_response.usage = None

        mock_deepseek_client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        result = await llm.generate(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hi"},
            ]
        )
        assert result.content == "Response via messages"

    @pytest.mark.asyncio
    async def test_generate_stream(self, mock_deepseek_client, llm):
        """流式生成。"""
        chunks = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello "))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content="world!"))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=None))]),
        ]
        mock_deepseek_client.chat.completions.create = AsyncMock(
            return_value=_async_iter(chunks)
        )

        collected = []
        async for token in llm.generate_stream(prompt="Hi"):
            collected.append(token)
        assert collected == ["Hello ", "world!"]

    @pytest.mark.asyncio
    async def test_count_tokens(self, llm):
        """Token 计数。"""
        count = await llm.count_tokens("Hello world")
        assert isinstance(count, int)
        assert count > 0

    @pytest.mark.asyncio
    async def test_generate_usage_none(self, mock_deepseek_client, llm):
        """usage 为 None 时不应报错。"""
        mock_choice = MagicMock()
        mock_choice.message.content = "No usage data"
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "deepseek-v4-flash"
        mock_response.usage = None  # usage 为 None

        mock_deepseek_client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        result = await llm.generate(prompt="test")
        assert result.content == "No usage data"
        assert result.usage is None


# =============================================================================
# Helpers
# =============================================================================


class _DummyLLM(BaseLLM):
    """用于测试 BaseLLM 公共方法的虚拟实现。"""

    def __init__(self, model: str = "dummy", **kwargs):
        super().__init__(model, **kwargs)

    async def generate(self, **kwargs) -> LLMResponse:
        return LLMResponse(content="dummy", model="dummy")

    async def generate_stream(self, **kwargs) -> AsyncIterator[str]:
        yield "dummy"

    async def count_tokens(self, text: str) -> int:
        return len(text)


def _create_dummy_llm(model: str = "dummy", **kwargs) -> _DummyLLM:
    return _DummyLLM(model=model, **kwargs)


async def _async_iter(items):
    for item in items:
        yield item
