"""
LLM Smart Router - リトライハンドラーモジュール

指数バックオフによるリトライ機能を提供し、エラー種別に応じて
リトライ/即停止を判定します。
"""

import asyncio
import logging
import random
from typing import Callable, TypeVar, Tuple, Optional, List
from functools import wraps

from ..exceptions import (
    LLMRouterError,
    APIError,
    ConnectionError,
    RateLimitError,
    ModelUnavailableError,
    AuthenticationError,
    is_retryable_error
)

# ロガー設定
logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryConfig:
    """リトライ設定クラス"""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Optional[Tuple[type, ...]] = None
    ):
        """
        リトライ設定
        
        Args:
            max_retries: 最大リトライ回数（デフォルト: 3）
            base_delay: 初回リトライの遅延秒数（デフォルト: 1.0）
            max_delay: 最大遅延秒数（デフォルト: 60.0）
            exponential_base: 指数バックオフの底（デフォルト: 2.0）
            jitter: ジッター（ランダム揺らぎ）を追加するか（デフォルト: True）
            retryable_exceptions: リトライ対象の例外タプル
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or (
            ConnectionError,
            RateLimitError,
            ModelUnavailableError,
            APIError,
            TimeoutError,
            ConnectionError  # Python標準のConnectionError
        )


class RetryHandler:
    """
    リトライハンドラー
    
    指数バックオフによるリトライを実行し、エラー種別に応じて
    リトライ/即停止を判定します。
    """
    
    def __init__(self, config: Optional[RetryConfig] = None, operation_name: str = "operation"):
        """
        リトライハンドラーの初期化
        
        Args:
            config: リトライ設定（Noneの場合デフォルト使用）
            operation_name: 操作名（ログ用）
        """
        self.config = config or RetryConfig()
        self.operation_name = operation_name
        self._retry_count = 0
        self._errors: List[Exception] = []
    
    def calculate_delay(self, attempt: int) -> float:
        """
        リトライ遅延時間を計算（指数バックオフ + ジッター）
        
        Args:
            attempt: リトライ試行回数（0-indexed）
            
        Returns:
            遅延秒数
        """
        # 指数バックオフ計算
        delay = self.config.base_delay * (self.config.exponential_base ** attempt)
        
        # 最大遅延時間で制限
        delay = min(delay, self.config.max_delay)
        
        # ジッター追加（±25%のランダム揺らぎ）
        if self.config.jitter:
            jitter_factor = random.uniform(0.75, 1.25)
            delay *= jitter_factor
        
        return delay
    
    def should_retry(self, error: Exception) -> Tuple[bool, Optional[float]]:
        """
        エラーに応じてリトライすべきか判定
        
        Args:
            error: 発生した例外
            
        Returns:
            (リトライすべきか, 待機秒数)
        """
        # 認証エラーは即停止
        if isinstance(error, AuthenticationError):
            logger.warning(f"[{self.operation_name}] 認証エラーのためリトライしません")
            return False, None
        
        # バリデーションエラーは即停止
        if isinstance(error, LLMRouterError) and not error.retryable:
            logger.warning(f"[{self.operation_name}] 非リトライ可能エラーのため停止")
            return False, None
        
        # レート制限エラーの場合はRetry-Afterを考慮
        if isinstance(error, RateLimitError):
            if error.retry_after_seconds:
                wait_time = error.retry_after_seconds
                logger.info(f"[{self.operation_name}] レート制限: {wait_time}秒待機後リトライ")
                return True, wait_time
        
        # APIエラーの場合、ステータスコードで判定
        if isinstance(error, APIError):
            if error.status_code == 429:  # Too Many Requests
                wait_time = self.calculate_delay(self._retry_count)
                logger.info(f"[{self.operation_name}] レート制限(429): {wait_time:.1f}秒待機後リトライ")
                return True, wait_time
            elif error.status_code and error.status_code >= 500:
                # サーバーエラーはリトライ
                wait_time = self.calculate_delay(self._retry_count)
                logger.info(f"[{self.operation_name}] サーバーエラー({error.status_code}): {wait_time:.1f}秒待機後リトライ")
                return True, wait_time
            elif error.status_code and error.status_code >= 400:
                # クライアントエラーはリトライ不可
                logger.warning(f"[{self.operation_name}] クライアントエラー({error.status_code}): リトライしません")
                return False, None
        
        # 接続エラー・タイムアウトはリトライ
        if isinstance(error, (ConnectionError, TimeoutError)):
            wait_time = self.calculate_delay(self._retry_count)
            logger.info(f"[{self.operation_name}] 接続エラー: {wait_time:.1f}秒待機後リトライ")
            return True, wait_time
        
        # モデル利用不可エラーはリトライ（フォールバック）
        if isinstance(error, ModelUnavailableError):
            wait_time = self.calculate_delay(self._retry_count)
            logger.info(f"[{self.operation_name}] モデル利用不可: {wait_time:.1f}秒待機後リトライ")
            return True, wait_time
        
        # LLMRouterErrorはretryableフラグで判定
        if isinstance(error, LLMRouterError):
            if error.retryable:
                wait_time = self.calculate_delay(self._retry_count)
                return True, wait_time
            return False, None
        
        # その他の例外はデフォルトでリトライ
        wait_time = self.calculate_delay(self._retry_count)
        logger.info(f"[{self.operation_name}] 不明なエラー: {wait_time:.1f}秒待機後リトライ")
        return True, wait_time
    
    async def execute_async(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """
        非同期関数をリトライ付きで実行
        
        Args:
            func: 実行する非同期関数
            *args: 関数の引数
            **kwargs: 関数のキーワード引数
            
        Returns:
            関数の戻り値
            
        Raises:
            最大リトライ回数を超えた場合、最後の例外を再raise
        """
        self._retry_count = 0
        self._errors = []
        
        while True:
            try:
                logger.debug(f"[{self.operation_name}] 実行試行 {self._retry_count + 1}/{self.config.max_retries + 1}")
                result = await func(*args, **kwargs)
                
                if self._retry_count > 0:
                    logger.info(f"[{self.operation_name}] リトライ成功（{self._retry_count}回目）")
                
                return result
                
            except Exception as e:
                self._errors.append(e)
                
                # リトライ判定
                should_retry, wait_time = self.should_retry(e)
                
                if not should_retry or self._retry_count >= self.config.max_retries:
                    # リトライ不可または最大回数到達
                    if self._retry_count >= self.config.max_retries:
                        logger.error(f"[{self.operation_name}] 最大リトライ回数({self.config.max_retries})に到達")
                    
                    # 最後の例外をraise
                    raise e
                
                # リトライ実行
                self._retry_count += 1
                logger.warning(
                    f"[{self.operation_name}] エラー発生（{self._retry_count}/{self.config.max_retries}）: {e}"
                )
                
                if wait_time:
                    logger.info(f"[{self.operation_name}] {wait_time:.1f}秒待機後リトライ...")
                    await asyncio.sleep(wait_time)
    
    def execute_sync(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """
        同期関数をリトライ付きで実行
        
        Args:
            func: 実行する同期関数
            *args: 関数の引数
            **kwargs: 関数のキーワード引数
            
        Returns:
            関数の戻り値
            
        Raises:
            最大リトライ回数を超えた場合、最後の例外を再raise
        """
        self._retry_count = 0
        self._errors = []
        
        while True:
            try:
                logger.debug(f"[{self.operation_name}] 実行試行 {self._retry_count + 1}/{self.config.max_retries + 1}")
                result = func(*args, **kwargs)
                
                if self._retry_count > 0:
                    logger.info(f"[{self.operation_name}] リトライ成功（{self._retry_count}回目）")
                
                return result
                
            except Exception as e:
                self._errors.append(e)
                
                # リトライ判定
                should_retry, wait_time = self.should_retry(e)
                
                if not should_retry or self._retry_count >= self.config.max_retries:
                    # リトライ不可または最大回数到達
                    if self._retry_count >= self.config.max_retries:
                        logger.error(f"[{self.operation_name}] 最大リトライ回数({self.config.max_retries})に到達")
                    
                    # 最後の例外をraise
                    raise e
                
                # リトライ実行
                self._retry_count += 1
                logger.warning(
                    f"[{self.operation_name}] エラー発生（{self._retry_count}/{self.config.max_retries}）: {e}"
                )
                
                if wait_time:
                    logger.info(f"[{self.operation_name}] {wait_time:.1f}秒待機後リトライ...")
                    import time
                    time.sleep(wait_time)
    
    def get_retry_history(self) -> List[Exception]:
        """リトライ履歴（発生したエラー一覧）を取得"""
        return self._errors.copy()


# デコレーターとして使用する場合
def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    operation_name: Optional[str] = None
):
    """
    リトライデコレーター（非同期関数用）
    
    Usage:
        @with_retry(max_retries=3)
        async def my_async_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        handler = RetryConfig(max_retries=max_retries, base_delay=base_delay)
        name = operation_name or func.__name__
        retry_handler = RetryHandler(handler, name)
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_handler.execute_async(func, *args, **kwargs)
        
        return wrapper
    return decorator


def with_retry_sync(
    max_retries: int = 3,
    base_delay: float = 1.0,
    operation_name: Optional[str] = None
):
    """
    リトライデコレーター（同期関数用）
    
    Usage:
        @with_retry_sync(max_retries=3)
        def my_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        handler = RetryConfig(max_retries=max_retries, base_delay=base_delay)
        name = operation_name or func.__name__
        retry_handler = RetryHandler(handler, name)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return retry_handler.execute_sync(func, *args, **kwargs)
        
        return wrapper
    return decorator


# ユーティリティ関数
async def retry_with_fallback(
    primary_func: Callable[..., T],
    fallback_funcs: List[Callable[..., T]],
    config: Optional[RetryConfig] = None
) -> T:
    """
    フォールバック付きリトライ実行
    
    Primaryが失敗したらSecondary、Tertiaryへ順次フォールバック
    
    Args:
        primary_func: 優先実行関数
        fallback_funcs: フォールバック関数リスト
        config: リトライ設定
        
    Returns:
        成功した関数の戻り値
        
    Raises:
        AllModelsFailedError: すべてのモデルが失敗した場合
    """
    all_funcs = [primary_func] + fallback_funcs
    all_errors = []
    
    for i, func in enumerate(all_funcs):
        model_name = ["Primary", "Secondary", "Tertiary"][i] if i < 3 else f"Fallback_{i}"
        handler = RetryHandler(config, f"{model_name}_model")
        
        try:
            logger.info(f"🔄 {model_name}モデルで実行試行...")
            return await handler.execute_async(func)
        except Exception as e:
            logger.warning(f"❌ {model_name}モデル失敗: {e}")
            all_errors.append({
                "model": model_name,
                "error": str(e),
                "type": type(e).__name__
            })
    
    # すべて失敗
    logger.error("🚨 すべてのモデルで処理に失敗しました")
    
    # AllModelsFailedErrorをraise（実際にはexceptionsモジュールからimport）
    from ..exceptions import AllModelsFailedError
    raise AllModelsFailedError(
        message="すべてのモデルで処理に失敗しました",
        errors=all_errors
    )
