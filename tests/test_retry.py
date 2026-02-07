"""
RetryHandler テストモジュール

指数バックオフ、エラー分類、リトライ判定、同期/非同期実行のテスト
"""
import sys
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# プロジェクトルートをパスに追加
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
_src = str(Path(__file__).parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from src.exceptions import (
    LLMRouterError,
    APIError,
    ConnectionError as LLMConnectionError,
    RateLimitError,
    ModelUnavailableError,
    AuthenticationError,
    AllModelsFailedError,
    is_retryable_error,
    get_error_severity,
)
from src.retry.retry_handler import (
    RetryConfig,
    RetryHandler,
    with_retry,
    with_retry_sync,
    retry_with_fallback,
)


# ---------------------------------------------------------------------------
# RetryConfig テスト
# ---------------------------------------------------------------------------

class TestRetryConfig:
    """リトライ設定テスト"""

    def test_default_config(self):
        cfg = RetryConfig()
        assert cfg.max_retries == 3
        assert cfg.base_delay == 1.0
        assert cfg.max_delay == 60.0
        assert cfg.exponential_base == 2.0
        assert cfg.jitter is True

    def test_custom_config(self):
        cfg = RetryConfig(max_retries=5, base_delay=0.5, jitter=False)
        assert cfg.max_retries == 5
        assert cfg.base_delay == 0.5
        assert cfg.jitter is False

    def test_default_retryable_exceptions(self):
        cfg = RetryConfig()
        assert LLMConnectionError in cfg.retryable_exceptions
        assert RateLimitError in cfg.retryable_exceptions
        assert ModelUnavailableError in cfg.retryable_exceptions
        assert APIError in cfg.retryable_exceptions
        assert TimeoutError in cfg.retryable_exceptions


# ---------------------------------------------------------------------------
# calculate_delay テスト
# ---------------------------------------------------------------------------

class TestCalculateDelay:
    """遅延時間計算テスト"""

    def test_exponential_backoff(self):
        handler = RetryHandler(RetryConfig(jitter=False))
        d0 = handler.calculate_delay(0)
        d1 = handler.calculate_delay(1)
        d2 = handler.calculate_delay(2)
        assert d0 == pytest.approx(1.0)
        assert d1 == pytest.approx(2.0)
        assert d2 == pytest.approx(4.0)

    def test_max_delay_cap(self):
        handler = RetryHandler(RetryConfig(max_delay=10.0, jitter=False))
        d10 = handler.calculate_delay(10)
        assert d10 <= 10.0

    def test_jitter_adds_randomness(self):
        handler = RetryHandler(RetryConfig(jitter=True))
        delays = [handler.calculate_delay(0) for _ in range(20)]
        # ジッターがあるので全て同じではない
        assert len(set(delays)) > 1

    def test_jitter_within_range(self):
        handler = RetryHandler(RetryConfig(base_delay=1.0, jitter=True))
        for _ in range(100):
            d = handler.calculate_delay(0)
            assert 0.75 <= d <= 1.25  # ±25%


# ---------------------------------------------------------------------------
# should_retry テスト
# ---------------------------------------------------------------------------

class TestShouldRetry:
    """リトライ判定テスト"""

    def test_authentication_error_no_retry(self):
        handler = RetryHandler()
        err = AuthenticationError("invalid key")
        should, wait = handler.should_retry(err)
        assert should is False
        assert wait is None

    def test_non_retryable_llm_error_no_retry(self):
        handler = RetryHandler()
        err = LLMRouterError("error", retryable=False)
        should, wait = handler.should_retry(err)
        assert should is False

    def test_rate_limit_with_retry_after(self):
        handler = RetryHandler()
        err = RateLimitError("rate limited", retry_after_seconds=10)
        should, wait = handler.should_retry(err)
        assert should is True
        assert wait == 10

    def test_api_429_no_retry(self):
        """429はAPIError.retryable=Falseのため非リトライ（RateLimitErrorを使うべき）"""
        handler = RetryHandler()
        err = APIError("too many requests", status_code=429)
        should, wait = handler.should_retry(err)
        # APIError(429)はretryable=False（5xx以外）→ should_retryの
        # "LLMRouterError and not retryable" ブランチで即停止
        assert should is False

    def test_api_500_retry(self):
        handler = RetryHandler()
        err = APIError("server error", status_code=500)
        should, wait = handler.should_retry(err)
        assert should is True

    def test_api_502_retry(self):
        handler = RetryHandler()
        err = APIError("bad gateway", status_code=502)
        should, wait = handler.should_retry(err)
        assert should is True

    def test_api_400_no_retry(self):
        handler = RetryHandler()
        err = APIError("bad request", status_code=400)
        should, wait = handler.should_retry(err)
        assert should is False

    def test_api_404_no_retry(self):
        handler = RetryHandler()
        err = APIError("not found", status_code=404)
        should, wait = handler.should_retry(err)
        assert should is False

    def test_connection_error_retry(self):
        handler = RetryHandler()
        err = LLMConnectionError("connection refused")
        should, wait = handler.should_retry(err)
        assert should is True

    def test_timeout_error_retry(self):
        handler = RetryHandler()
        err = TimeoutError("timed out")
        should, wait = handler.should_retry(err)
        assert should is True

    def test_model_unavailable_retry(self):
        handler = RetryHandler()
        err = ModelUnavailableError("model down")
        should, wait = handler.should_retry(err)
        assert should is True

    def test_retryable_llm_error_retry(self):
        handler = RetryHandler()
        err = LLMRouterError("transient error", retryable=True)
        should, wait = handler.should_retry(err)
        assert should is True

    def test_unknown_error_retry(self):
        handler = RetryHandler()
        err = RuntimeError("something unexpected")
        should, wait = handler.should_retry(err)
        assert should is True


# ---------------------------------------------------------------------------
# execute_async テスト
# ---------------------------------------------------------------------------

class TestExecuteAsync:
    """非同期実行テスト"""

    @pytest.mark.asyncio
    async def test_success_first_attempt(self):
        handler = RetryHandler(operation_name="test")
        func = AsyncMock(return_value="success")
        result = await handler.execute_async(func)
        assert result == "success"
        assert func.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_then_success(self):
        handler = RetryHandler(
            RetryConfig(max_retries=3, base_delay=0.01, jitter=False),
            operation_name="test"
        )
        func = AsyncMock(side_effect=[
            LLMConnectionError("fail1"),
            LLMConnectionError("fail2"),
            "success"
        ])
        result = await handler.execute_async(func)
        assert result == "success"
        assert func.call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        handler = RetryHandler(
            RetryConfig(max_retries=2, base_delay=0.01, jitter=False),
            operation_name="test"
        )
        func = AsyncMock(side_effect=LLMConnectionError("always fail"))
        with pytest.raises(LLMConnectionError):
            await handler.execute_async(func)
        assert func.call_count == 3  # 1 initial + 2 retries

    @pytest.mark.asyncio
    async def test_non_retryable_error_stops_immediately(self):
        handler = RetryHandler(
            RetryConfig(max_retries=3, base_delay=0.01),
            operation_name="test"
        )
        func = AsyncMock(side_effect=AuthenticationError("bad key"))
        with pytest.raises(AuthenticationError):
            await handler.execute_async(func)
        assert func.call_count == 1  # 即停止

    @pytest.mark.asyncio
    async def test_retry_history(self):
        handler = RetryHandler(
            RetryConfig(max_retries=2, base_delay=0.01, jitter=False),
            operation_name="test"
        )
        errors = [
            LLMConnectionError("fail1"),
            LLMConnectionError("fail2"),
            LLMConnectionError("fail3"),
        ]
        func = AsyncMock(side_effect=errors)
        with pytest.raises(LLMConnectionError):
            await handler.execute_async(func)
        history = handler.get_retry_history()
        assert len(history) == 3


# ---------------------------------------------------------------------------
# execute_sync テスト
# ---------------------------------------------------------------------------

class TestExecuteSync:
    """同期実行テスト"""

    def test_sync_success(self):
        handler = RetryHandler(operation_name="test")
        func = MagicMock(return_value="ok")
        result = handler.execute_sync(func)
        assert result == "ok"
        assert func.call_count == 1

    def test_sync_retry_then_success(self):
        handler = RetryHandler(
            RetryConfig(max_retries=3, base_delay=0.01, jitter=False),
            operation_name="test"
        )
        func = MagicMock(side_effect=[
            LLMConnectionError("fail"),
            "success"
        ])
        result = handler.execute_sync(func)
        assert result == "success"
        assert func.call_count == 2

    def test_sync_max_retries(self):
        handler = RetryHandler(
            RetryConfig(max_retries=1, base_delay=0.01, jitter=False),
            operation_name="test"
        )
        func = MagicMock(side_effect=LLMConnectionError("fail"))
        with pytest.raises(LLMConnectionError):
            handler.execute_sync(func)
        assert func.call_count == 2  # 1 initial + 1 retry

    def test_sync_non_retryable(self):
        handler = RetryHandler(
            RetryConfig(max_retries=3, base_delay=0.01),
            operation_name="test"
        )
        func = MagicMock(side_effect=AuthenticationError("bad"))
        with pytest.raises(AuthenticationError):
            handler.execute_sync(func)
        assert func.call_count == 1


# ---------------------------------------------------------------------------
# デコレータテスト
# ---------------------------------------------------------------------------

class TestRetryDecorators:
    """リトライデコレータテスト"""

    @pytest.mark.asyncio
    async def test_with_retry_decorator(self):
        call_count = 0

        @with_retry(max_retries=2, base_delay=0.01)
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise LLMConnectionError("temporary")
            return "done"

        result = await flaky_func()
        assert result == "done"
        assert call_count == 2

    def test_with_retry_sync_decorator(self):
        call_count = 0

        @with_retry_sync(max_retries=2, base_delay=0.01)
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise LLMConnectionError("temporary")
            return "done"

        result = flaky_func()
        assert result == "done"
        assert call_count == 2


# ---------------------------------------------------------------------------
# retry_with_fallback テスト
# ---------------------------------------------------------------------------

class TestRetryWithFallback:
    """フォールバック付きリトライテスト"""

    @pytest.mark.asyncio
    async def test_primary_succeeds(self):
        primary = AsyncMock(return_value="primary result")
        fallback = AsyncMock(return_value="fallback result")
        result = await retry_with_fallback(
            primary, [fallback],
            config=RetryConfig(max_retries=0, base_delay=0.01)
        )
        assert result == "primary result"

    @pytest.mark.asyncio
    async def test_fallback_on_primary_failure(self):
        primary = AsyncMock(side_effect=LLMConnectionError("fail"))
        fallback = AsyncMock(return_value="fallback result")
        result = await retry_with_fallback(
            primary, [fallback],
            config=RetryConfig(max_retries=0, base_delay=0.01)
        )
        assert result == "fallback result"

    @pytest.mark.asyncio
    async def test_all_models_failed(self):
        primary = AsyncMock(side_effect=AuthenticationError("fail"))
        fb1 = AsyncMock(side_effect=AuthenticationError("fail"))
        with pytest.raises(AllModelsFailedError):
            await retry_with_fallback(
                primary, [fb1],
                config=RetryConfig(max_retries=0, base_delay=0.01)
            )


# ---------------------------------------------------------------------------
# is_retryable_error / get_error_severity テスト
# ---------------------------------------------------------------------------

class TestErrorHelpers:
    """エラーヘルパー関数テスト"""

    def test_retryable_connection_error(self):
        assert is_retryable_error(LLMConnectionError("fail"))

    def test_retryable_rate_limit(self):
        assert is_retryable_error(RateLimitError("limit"))

    def test_not_retryable_auth_error(self):
        assert not is_retryable_error(AuthenticationError("bad"))

    def test_not_retryable_all_models_failed(self):
        assert not is_retryable_error(AllModelsFailedError())

    def test_severity_auth_critical(self):
        assert get_error_severity(AuthenticationError("bad")) == "critical"

    def test_severity_all_failed_critical(self):
        assert get_error_severity(AllModelsFailedError()) == "critical"

    def test_severity_api_500_high(self):
        assert get_error_severity(APIError("err", status_code=500)) == "high"

    def test_severity_api_400_medium(self):
        assert get_error_severity(APIError("err", status_code=400)) == "medium"

    def test_severity_rate_limit_medium(self):
        assert get_error_severity(RateLimitError("limit")) == "medium"

    def test_severity_unknown_high(self):
        assert get_error_severity(RuntimeError("unknown")) == "high"
