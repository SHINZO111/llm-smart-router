"""
モデルアダプター結合テスト

APIキーがある場合は実通信テスト、ない場合はモックテスト。
"""

import os
import sys
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_src_root = str(Path(__file__).parent.parent / "src")
if _src_root not in sys.path:
    sys.path.insert(0, _src_root)

from models.base_model import (
    BaseModelAdapter,
    ModelConfig,
    ModelResponse,
    ModelAdapterError,
    ModelAuthenticationError,
    ModelRateLimitError,
    ModelContextLengthError,
)

# aiohttp が利用可能かチェック（環境によってはimportがハングする）
_aiohttp_available = False
try:
    import subprocess as _sp
    _proc = _sp.run(
        [sys.executable, "-c", "import aiohttp; print('ok')"],
        capture_output=True, text=True, timeout=5,
    )
    _aiohttp_available = _proc.returncode == 0 and "ok" in _proc.stdout
except Exception:
    pass

_skip_aiohttp = pytest.mark.skipif(
    not _aiohttp_available,
    reason="aiohttp not available or import hangs",
)


# ---------------------------------------------------------------------------
# BaseModelAdapter テスト
# ---------------------------------------------------------------------------

class TestModelResponse:
    """ModelResponseデータクラスのテスト"""

    def test_create_response(self):
        resp = ModelResponse(
            content="Hello",
            input_tokens=10,
            output_tokens=5,
            model_name="test-model",
            provider="test",
        )
        assert resp.content == "Hello"
        assert resp.input_tokens == 10
        assert resp.output_tokens == 5
        assert resp.model_name == "test-model"
        assert resp.provider == "test"
        assert resp.metadata is None

    def test_response_with_metadata(self):
        resp = ModelResponse(
            content="Hi",
            input_tokens=1,
            output_tokens=1,
            model_name="m",
            provider="p",
            metadata={"finish_reason": "stop"},
        )
        assert resp.metadata["finish_reason"] == "stop"


class TestModelConfig:
    """ModelConfig データクラスのテスト"""

    def test_defaults(self):
        cfg = ModelConfig(provider="test", model="m", endpoint="http://localhost")
        assert cfg.timeout == 60000
        assert cfg.max_tokens == 4096
        assert cfg.temperature == 0.7
        assert cfg.api_key is None

    def test_custom_values(self):
        cfg = ModelConfig(
            provider="openai",
            model="gpt-4o",
            endpoint="https://api.openai.com/v1",
            api_key="sk-test",
            timeout=30000,
            max_tokens=2048,
            temperature=0.3,
        )
        assert cfg.api_key == "sk-test"
        assert cfg.timeout == 30000


class TestTokenEstimation:
    """簡易トークン推定のテスト"""

    def test_english_text(self):
        # 英語: ~4文字/トークン
        adapter = _make_dummy_adapter()
        tokens = adapter._estimate_tokens_simple("Hello world test")
        assert tokens > 0
        assert tokens < 20

    def test_japanese_text(self):
        # 日本語: ~1.5文字/トークン
        adapter = _make_dummy_adapter()
        tokens = adapter._estimate_tokens_simple("日本語テスト文字列")
        assert tokens > 0

    def test_mixed_text(self):
        adapter = _make_dummy_adapter()
        tokens = adapter._estimate_tokens_simple("Hello 世界 test テスト")
        assert tokens > 0

    def test_empty_string(self):
        adapter = _make_dummy_adapter()
        tokens = adapter._estimate_tokens_simple("")
        assert tokens == 1  # +1 for safety margin


class TestFormatMessages:
    """メッセージフォーマットのテスト"""

    def test_simple_prompt(self):
        adapter = _make_dummy_adapter()
        msgs = adapter.format_messages("Hello")
        assert len(msgs) == 1
        assert msgs[0] == {"role": "user", "content": "Hello"}

    def test_with_system_prompt(self):
        adapter = _make_dummy_adapter()
        msgs = adapter.format_messages("Hello", system_prompt="You are helpful")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"

    def test_with_history(self):
        adapter = _make_dummy_adapter()
        history = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
        ]
        msgs = adapter.format_messages("Q2", history=history)
        assert len(msgs) == 3
        assert msgs[0]["content"] == "Q1"
        assert msgs[2]["content"] == "Q2"


class TestExceptionHierarchy:
    """例外階層のテスト"""

    def test_adapter_error_is_retryable(self):
        err = ModelAdapterError("test")
        assert err.retryable is True

    def test_auth_error_not_retryable(self):
        err = ModelAuthenticationError("invalid key")
        assert err.retryable is False

    def test_rate_limit_retryable(self):
        err = ModelRateLimitError("429")
        assert err.retryable is True

    def test_context_length_not_retryable(self):
        err = ModelContextLengthError("too long")
        assert err.retryable is False

    def test_all_inherit_from_adapter_error(self):
        assert issubclass(ModelAuthenticationError, ModelAdapterError)
        assert issubclass(ModelRateLimitError, ModelAdapterError)
        assert issubclass(ModelContextLengthError, ModelAdapterError)


class TestCostEstimation:
    """コスト見積もりのテスト"""

    def test_base_cost_is_zero(self):
        adapter = _make_dummy_adapter()
        assert adapter.estimate_cost(100, 50) == 0.0


# ---------------------------------------------------------------------------
# Kimi Adapter テスト
# ---------------------------------------------------------------------------

@_skip_aiohttp
class TestKimiAdapter:
    """Kimiアダプターのテスト"""

    def test_default_config(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            from models.kimi_adapter import KimiAdapter
            adapter = KimiAdapter()
            assert adapter.config.provider == "openrouter"
            assert adapter.config.model == "kimi-coding/k2p5"
            assert adapter.config.api_key == "test-key"

    def test_missing_api_key_raises(self):
        from models.kimi_adapter import KimiAdapter
        env = {k: v for k, v in os.environ.items()
               if k not in ("OPENROUTER_API_KEY", "KIMI_API_KEY")}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ModelAuthenticationError):
                KimiAdapter()

    def test_custom_config(self):
        cfg = ModelConfig(
            provider="openrouter",
            model="custom-model",
            endpoint="https://openrouter.ai/api/v1",
            api_key="sk-test",
        )
        from models.kimi_adapter import KimiAdapter
        adapter = KimiAdapter(cfg)
        assert adapter.model_name == "custom-model"

    def test_cost_estimation(self):
        cfg = ModelConfig(
            provider="openrouter",
            model="test",
            endpoint="https://openrouter.ai/api/v1",
            api_key="sk-test",
        )
        from models.kimi_adapter import KimiAdapter
        adapter = KimiAdapter(cfg)
        cost = adapter.estimate_cost(1000, 500)
        assert cost > 0

    def test_capabilities(self):
        cfg = ModelConfig(
            provider="openrouter",
            model="test",
            endpoint="https://openrouter.ai/api/v1",
            api_key="sk-test",
        )
        from models.kimi_adapter import KimiAdapter
        adapter = KimiAdapter(cfg)
        caps = adapter.get_capabilities()
        assert isinstance(caps, list)
        assert "coding" in caps

    @pytest.mark.asyncio
    async def test_generate_mock(self):
        """モックHTTPレスポンスでgenerate()をテスト"""
        cfg = ModelConfig(
            provider="openrouter",
            model="test",
            endpoint="https://openrouter.ai/api/v1",
            api_key="sk-test",
        )
        from models.kimi_adapter import KimiAdapter
        adapter = KimiAdapter(cfg)

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "id": "chatcmpl-123",
            "choices": [{"message": {"content": "Test response"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        })
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post = MagicMock(return_value=mock_resp)

        adapter.session = mock_session

        result = await adapter.generate("Hello")
        assert isinstance(result, ModelResponse)
        assert result.content == "Test response"
        assert result.input_tokens == 10
        assert result.output_tokens == 5


# ---------------------------------------------------------------------------
# GPT-4o Adapter テスト
# ---------------------------------------------------------------------------

@_skip_aiohttp
class TestGPT4oAdapter:
    """GPT-4oアダプターのテスト"""

    def test_default_config(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            from models.gpt4o_adapter import GPT4oAdapter
            adapter = GPT4oAdapter()
            assert adapter.config.provider == "openai"
            assert "gpt-4o" in adapter.config.model
            assert adapter.config.api_key == "test-key"

    def test_missing_api_key_raises(self):
        from models.gpt4o_adapter import GPT4oAdapter
        env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ModelAuthenticationError):
                GPT4oAdapter()

    def test_capabilities_include_vision(self):
        cfg = ModelConfig(
            provider="openai",
            model="gpt-4o",
            endpoint="https://api.openai.com/v1",
            api_key="sk-test",
        )
        from models.gpt4o_adapter import GPT4oAdapter
        adapter = GPT4oAdapter(cfg)
        caps = adapter.get_capabilities()
        assert "vision" in caps

    def test_cost_estimation(self):
        cfg = ModelConfig(
            provider="openai",
            model="gpt-4o",
            endpoint="https://api.openai.com/v1",
            api_key="sk-test",
        )
        from models.gpt4o_adapter import GPT4oAdapter
        adapter = GPT4oAdapter(cfg)
        cost = adapter.estimate_cost(1000, 500)
        assert cost > 0

    @pytest.mark.asyncio
    async def test_generate_mock(self):
        """モックHTTPレスポンスでgenerate()をテスト"""
        cfg = ModelConfig(
            provider="openai",
            model="gpt-4o",
            endpoint="https://api.openai.com/v1",
            api_key="sk-test",
        )
        from models.gpt4o_adapter import GPT4oAdapter
        adapter = GPT4oAdapter(cfg)

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "id": "chatcmpl-456",
            "choices": [{"message": {"content": "GPT response"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 15, "completion_tokens": 8},
            "system_fingerprint": "fp_abc",
        })
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post = MagicMock(return_value=mock_resp)

        adapter.session = mock_session

        result = await adapter.generate("Hello", system_prompt="Be helpful")
        assert isinstance(result, ModelResponse)
        assert result.content == "GPT response"
        assert result.input_tokens == 15

    @pytest.mark.asyncio
    async def test_generate_401_raises_auth_error(self):
        """401レスポンスでModelAuthenticationErrorが発生"""
        cfg = ModelConfig(
            provider="openai",
            model="gpt-4o",
            endpoint="https://api.openai.com/v1",
            api_key="invalid-key",
        )
        from models.gpt4o_adapter import GPT4oAdapter
        adapter = GPT4oAdapter(cfg)

        mock_resp = AsyncMock()
        mock_resp.status = 401
        mock_resp.text = AsyncMock(return_value="Unauthorized")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post = MagicMock(return_value=mock_resp)

        adapter.session = mock_session

        with pytest.raises(ModelAuthenticationError):
            await adapter.generate("Hello")

    @pytest.mark.asyncio
    async def test_generate_429_raises_rate_limit(self):
        """429レスポンスでModelRateLimitErrorが発生"""
        cfg = ModelConfig(
            provider="openai",
            model="gpt-4o",
            endpoint="https://api.openai.com/v1",
            api_key="sk-test",
        )
        from models.gpt4o_adapter import GPT4oAdapter
        adapter = GPT4oAdapter(cfg)

        mock_resp = AsyncMock()
        mock_resp.status = 429
        mock_resp.text = AsyncMock(return_value="Rate limited")
        mock_resp.headers = {"Retry-After": "5"}
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post = MagicMock(return_value=mock_resp)

        adapter.session = mock_session

        with pytest.raises(ModelRateLimitError):
            await adapter.generate("Hello")


# ---------------------------------------------------------------------------
# Gemini Adapter テスト
# ---------------------------------------------------------------------------

@_skip_aiohttp
class TestGeminiAdapter:
    """Geminiアダプターのテスト"""

    def test_default_config(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            from models.gemini_adapter import GeminiAdapter
            adapter = GeminiAdapter()
            assert adapter.config.provider == "google"
            assert "gemini" in adapter.config.model
            assert adapter.config.api_key == "test-key"

    def test_missing_api_key_raises(self):
        from models.gemini_adapter import GeminiAdapter
        env = {k: v for k, v in os.environ.items()
               if k not in ("GOOGLE_API_KEY", "GEMINI_API_KEY")}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ModelAuthenticationError):
                GeminiAdapter()

    def test_capabilities(self):
        cfg = ModelConfig(
            provider="google",
            model="gemini-pro",
            endpoint="https://generativelanguage.googleapis.com/v1beta",
            api_key="test-key",
        )
        from models.gemini_adapter import GeminiAdapter
        adapter = GeminiAdapter(cfg)
        caps = adapter.get_capabilities()
        assert isinstance(caps, list)
        assert "long_context" in caps

    def test_cost_estimation(self):
        cfg = ModelConfig(
            provider="google",
            model="gemini-pro",
            endpoint="https://generativelanguage.googleapis.com/v1beta",
            api_key="test-key",
        )
        from models.gemini_adapter import GeminiAdapter
        adapter = GeminiAdapter(cfg)
        cost = adapter.estimate_cost(1000, 500)
        assert cost > 0

    @pytest.mark.asyncio
    async def test_generate_mock(self):
        """モックHTTPレスポンスでgenerate()をテスト"""
        cfg = ModelConfig(
            provider="google",
            model="gemini-pro",
            endpoint="https://generativelanguage.googleapis.com/v1beta",
            api_key="test-key",
        )
        from models.gemini_adapter import GeminiAdapter
        adapter = GeminiAdapter(cfg)

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "candidates": [{
                "content": {"parts": [{"text": "Gemini response"}]},
                "finishReason": "STOP",
                "safetyRatings": [],
            }],
            "usageMetadata": {
                "promptTokenCount": 12,
                "candidatesTokenCount": 6,
            },
        })
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post = MagicMock(return_value=mock_resp)

        adapter.session = mock_session

        result = await adapter.generate("Hello")
        assert isinstance(result, ModelResponse)
        assert result.content == "Gemini response"
        assert result.input_tokens == 12
        assert result.output_tokens == 6


# ---------------------------------------------------------------------------
# 実API結合テスト（APIキーがある場合のみ実行）
# ---------------------------------------------------------------------------

@_skip_aiohttp
@pytest.mark.integration
@pytest.mark.slow
class TestLiveKimi:
    """Kimi実API結合テスト"""

    @pytest.fixture(autouse=True)
    def skip_if_no_key(self):
        if not (os.getenv("OPENROUTER_API_KEY") or os.getenv("KIMI_API_KEY")):
            pytest.skip("OPENROUTER_API_KEY not set")

    @pytest.mark.asyncio
    async def test_live_generate(self):
        from models.kimi_adapter import KimiAdapter
        adapter = KimiAdapter()
        try:
            result = await adapter.generate("Say 'hello' in one word")
            assert isinstance(result, ModelResponse)
            assert len(result.content) > 0
            assert result.input_tokens > 0
        finally:
            if adapter.session:
                await adapter.session.close()


@_skip_aiohttp
@pytest.mark.integration
@pytest.mark.slow
class TestLiveGPT4o:
    """GPT-4o実API結合テスト"""

    @pytest.fixture(autouse=True)
    def skip_if_no_key(self):
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")

    @pytest.mark.asyncio
    async def test_live_generate(self):
        from models.gpt4o_adapter import GPT4oAdapter
        adapter = GPT4oAdapter()
        try:
            result = await adapter.generate("Say 'hello' in one word")
            assert isinstance(result, ModelResponse)
            assert len(result.content) > 0
            assert result.input_tokens > 0
        finally:
            if adapter.session:
                await adapter.session.close()


@_skip_aiohttp
@pytest.mark.integration
@pytest.mark.slow
class TestLiveGemini:
    """Gemini実API結合テスト"""

    @pytest.fixture(autouse=True)
    def skip_if_no_key(self):
        if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
            pytest.skip("GOOGLE_API_KEY not set")

    @pytest.mark.asyncio
    async def test_live_generate(self):
        from models.gemini_adapter import GeminiAdapter
        adapter = GeminiAdapter()
        try:
            result = await adapter.generate("Say 'hello' in one word")
            assert isinstance(result, ModelResponse)
            assert len(result.content) > 0
            assert result.input_tokens > 0
        finally:
            if adapter.session:
                await adapter.session.close()


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def _make_dummy_adapter():
    """テスト用ダミーアダプター"""

    class DummyAdapter(BaseModelAdapter):
        def __init__(self):
            super().__init__(ModelConfig(
                provider="test",
                model="test",
                endpoint="http://localhost",
                api_key="dummy",
            ))

        async def generate(self, prompt, system_prompt=None, **kwargs):
            return ModelResponse(
                content="dummy",
                input_tokens=0,
                output_tokens=0,
                model_name="test",
                provider="test",
            )

        async def generate_stream(self, prompt, system_prompt=None, **kwargs):
            yield "dummy"

        def count_tokens(self, text):
            return self._estimate_tokens_simple(text)

        def validate_config(self):
            return True

    return DummyAdapter()
