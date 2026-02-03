"""
LLM Smart Router - 例外クラスモジュール

エラーハンドリングを強化し、異なるエラータイプを区別して
適切な対応（リトライ、フォールバック、即停止）を可能にします。
"""

from typing import Optional, Dict, Any


class LLMRouterError(Exception):
    """
    LLM Smart Routerの基底例外クラス
    
    すべてのカスタム例外はこのクラスを継承します。
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        retryable: bool = False
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "ROUTER_ERROR"
        self.details = details or {}
        self.retryable = retryable
    
    def __str__(self) -> str:
        base_msg = f"[{self.error_code}] {self.message}"
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            base_msg += f" ({details_str})"
        return base_msg
    
    def to_dict(self) -> Dict[str, Any]:
        """エラーを辞書形式で返す（ログ・APIレスポンス用）"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "retryable": self.retryable,
            "type": self.__class__.__name__
        }


class APIError(LLMRouterError):
    """
    API関連エラー
    
    LLM APIからのエラーレスポンスや、API呼び出し失敗時に発生
    """
    
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        api_provider: Optional[str] = None,
        response_body: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        details.update({
            "status_code": status_code,
            "api_provider": api_provider,
            "response_body": response_body
        })
        
        # 5xxエラーはリトライ可能
        retryable = status_code is not None and 500 <= status_code < 600
        
        super().__init__(
            message=message,
            error_code="API_ERROR",
            details=details,
            retryable=retryable,
            **kwargs
        )
        self.status_code = status_code
        self.api_provider = api_provider


class ConnectionError(LLMRouterError):
    """
    接続エラー
    
    ネットワーク接続失敗、タイムアウト、DNS解決失敗など
    """
    
    def __init__(
        self,
        message: str,
        endpoint: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        details.update({
            "endpoint": endpoint,
            "timeout_seconds": timeout_seconds
        })
        
        super().__init__(
            message=message,
            error_code="CONNECTION_ERROR",
            details=details,
            retryable=True,  # 接続エラーは基本的にリトライ可能
            **kwargs
        )
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds


class RateLimitError(LLMRouterError):
    """
    レート制限エラー
    
    APIのレート制限に到達した場合
    """
    
    def __init__(
        self,
        message: str,
        retry_after_seconds: Optional[int] = None,
        limit: Optional[int] = None,
        remaining: Optional[int] = None,
        api_provider: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        details.update({
            "retry_after_seconds": retry_after_seconds,
            "limit": limit,
            "remaining": remaining,
            "api_provider": api_provider
        })
        
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_ERROR",
            details=details,
            retryable=True,  # レート制限は待機後リトライ可能
            **kwargs
        )
        self.retry_after_seconds = retry_after_seconds
        self.limit = limit
        self.remaining = remaining


class ModelUnavailableError(LLMRouterError):
    """
    モデル利用不可エラー
    
    指定されたモデルが利用できない、または応答しない場合
    """
    
    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        provider: Optional[str] = None,
        fallback_available: bool = True,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        details.update({
            "model_name": model_name,
            "provider": provider,
            "fallback_available": fallback_available
        })
        
        super().__init__(
            message=message,
            error_code="MODEL_UNAVAILABLE",
            details=details,
            retryable=True,  # フォールバックでリトライ可能
            **kwargs
        )
        self.model_name = model_name
        self.provider = provider
        self.fallback_available = fallback_available


class AuthenticationError(LLMRouterError):
    """
    認証エラー
    
    APIキー無効、権限不足など
    """
    
    def __init__(
        self,
        message: str,
        api_provider: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        details.update({
            "api_provider": api_provider
        })
        
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            details=details,
            retryable=False,  # 認証エラーはリトライ不可
            **kwargs
        )
        self.api_provider = api_provider


class ValidationError(LLMRouterError):
    """
    入力検証エラー
    
    リクエスト内容が無効な場合
    """
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        details.update({
            "field": field
        })
        
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details=details,
            retryable=False,  # 検証エラーはリトライ不可
            **kwargs
        )
        self.field = field


class AllModelsFailedError(LLMRouterError):
    """
    全モデル失敗エラー
    
    Primary, Secondary, Tertiaryすべてのモデルが失敗した場合
    """
    
    def __init__(
        self,
        message: str = "すべてのモデルで処理に失敗しました",
        errors: Optional[list] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        details.update({
            "failed_models": [e.get("model", "unknown") for e in (errors or [])],
            "error_count": len(errors or [])
        })
        
        super().__init__(
            message=message,
            error_code="ALL_MODELS_FAILED",
            details=details,
            retryable=False,  # 全モデル失敗はリトライ不可
            **kwargs
        )
        self.errors = errors or []


# エラータイプ判定用ヘルパー関数
def is_retryable_error(error: Exception) -> bool:
    """
    エラーがリトライ可能か判定
    
    Args:
        error: 判定する例外
        
    Returns:
        リトライ可能な場合True
    """
    if isinstance(error, LLMRouterError):
        return error.retryable
    
    # 標準的な例外の判定
    if isinstance(error, (ConnectionError, TimeoutError)):
        return True
    
    return False


def get_error_severity(error: Exception) -> str:
    """
    エラーの重大度を取得
    
    Args:
        error: 判定する例外
        
    Returns:
        "critical", "high", "medium", "low" のいずれか
    """
    if isinstance(error, AuthenticationError):
        return "critical"
    elif isinstance(error, AllModelsFailedError):
        return "critical"
    elif isinstance(error, APIError):
        if error.status_code and error.status_code >= 500:
            return "high"
        return "medium"
    elif isinstance(error, RateLimitError):
        return "medium"
    elif isinstance(error, (ConnectionError, ModelUnavailableError)):
        return "medium"
    elif isinstance(error, ValidationError):
        return "low"
    
    return "high"  # 未知のエラーは高重大度
