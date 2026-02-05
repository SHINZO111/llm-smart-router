"""
Base Model Adapter - 抽象基底クラス
新しいモデルを追加する際は、このクラスを継承してください
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

import sys
from pathlib import Path
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from exceptions import LLMRouterError


@dataclass
class ModelResponse:
    """モデル応答の標準フォーマット"""
    content: str
    input_tokens: int
    output_tokens: int
    model_name: str
    provider: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ModelConfig:
    """モデル設定の標準フォーマット"""
    provider: str
    model: str
    endpoint: str
    api_key: Optional[str] = None
    timeout: int = 60000
    max_tokens: int = 4096
    temperature: float = 0.7
    extra_params: Optional[Dict[str, Any]] = None


class BaseModelAdapter(ABC):
    """
    LLMモデルアダプターの抽象基底クラス
    
    新しいモデルを追加する際は、このクラスを継承し、
    以下のメソッドを実装してください：
    - generate(): テキスト生成
    - count_tokens(): トークン数カウント
    - validate_config(): 設定検証
    """
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self.provider = config.provider
        self.model_name = config.model
        self.validate_config()
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> ModelResponse:
        """
        テキスト生成のメインインターフェース
        
        Args:
            prompt: ユーザープロンプト
            system_prompt: システムプロンプト（オプション）
            **kwargs: モデル固有の追加パラメータ
            
        Returns:
            ModelResponse: 標準化された応答
        """
        pass
    
    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ):
        """
        ストリーミングテキスト生成
        
        Yields:
            str: 生成されたテキストチャンク
        """
        pass
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """
        テキストのトークン数をカウント
        
        Args:
            text: カウント対象のテキスト
            
        Returns:
            int: トークン数（概算）
        """
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """
        設定の妥当性を検証
        
        Returns:
            bool: 検証結果
            
        Raises:
            ValueError: 設定が無効な場合
        """
        pass
    
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        コスト見積もり（USD）
        
        サブクラスでオーバーライド可能
        """
        # デフォルト: 無料（ローカルモデルなど）
        return 0.0
    
    def get_capabilities(self) -> List[str]:
        """
        モデルの機能一覧を返す
        
        Returns:
            List[str]: サポート機能のリスト
        """
        return []
    
    def format_messages(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None
    ) -> List[Dict[str, str]]:
        """
        メッセージ形式に変換（共通ユーティリティ）
        
        Args:
            prompt: 現在のプロンプト
            system_prompt: システムプロンプト
            history: 会話履歴
            
        Returns:
            List[Dict[str, str]]: OpenAI互換メッセージ形式
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        if history:
            messages.extend(history)
        
        messages.append({"role": "user", "content": prompt})
        
        return messages
    
    def _estimate_tokens_simple(self, text: str) -> int:
        """
        簡易トークン数推定（日本語約1.5文字/トークン、英語約4文字/トークン）
        """
        import re
        
        # 日本語文字数
        jp_chars = len(re.findall(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]', text))
        # 英語・その他
        other_chars = len(text) - jp_chars
        
        # 日本語は約1.5文字/トークン、英語は約4文字/トークン
        estimated = (jp_chars / 1.5) + (other_chars / 4)
        
        return int(estimated) + 1  # +1 for safety margin


class ModelAdapterError(LLMRouterError):
    """モデルアダプター関連のエラー"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_code="MODEL_ADAPTER_ERROR", retryable=True, **kwargs)


class ModelAuthenticationError(ModelAdapterError):
    """認証エラー"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, **kwargs)
        self.error_code = "MODEL_AUTH_ERROR"
        self.retryable = False


class ModelRateLimitError(ModelAdapterError):
    """レート制限エラー"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, **kwargs)
        self.error_code = "MODEL_RATE_LIMIT"
        self.retryable = True


class ModelContextLengthError(ModelAdapterError):
    """コンテキスト長超過エラー"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, **kwargs)
        self.error_code = "MODEL_CONTEXT_LENGTH"
        self.retryable = False
