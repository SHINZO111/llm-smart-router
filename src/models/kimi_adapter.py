"""
Kimi Model Adapter - kimi-coding/k2p5
OpenRouter経由または直接API経由で利用
"""

import os
import aiohttp
from typing import Optional, List, Dict, Any, AsyncGenerator

from .base_model import (
    BaseModelAdapter,
    ModelConfig,
    ModelResponse,
    ModelAuthenticationError,
    ModelRateLimitError,
    ModelContextLengthError,
    ModelAdapterError
)


class KimiAdapter(BaseModelAdapter):
    """
    Kimi (kimi-coding/k2p5) アダプター
    
    特徴:
    - コーディングに強い
    - 長文脈対応
    - 推論能力が高い
    """
    
    DEFAULT_ENDPOINT = "https://openrouter.ai/api/v1"
    DEFAULT_MODEL = "kimi-coding/k2p5"
    
    # コスト設定（USD per 1K tokens）
    COST_INPUT = 0.002
    COST_OUTPUT = 0.008
    
    def __init__(self, config: Optional[ModelConfig] = None):
        if config is None:
            config = self._create_default_config()
        super().__init__(config)
        self.session: Optional[aiohttp.ClientSession] = None
    
    def _create_default_config(self) -> ModelConfig:
        """デフォルト設定を作成"""
        api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("KIMI_API_KEY")
        return ModelConfig(
            provider="openrouter",
            model=self.DEFAULT_MODEL,
            endpoint=self.DEFAULT_ENDPOINT,
            api_key=api_key,
            timeout=60000,
            max_tokens=8192,
            temperature=0.7
        )
    
    def validate_config(self) -> bool:
        """設定を検証"""
        if not self.config.api_key:
            raise ModelAuthenticationError(
                "Kimi APIキーが必要です。OPENROUTER_API_KEY または KIMI_API_KEY を設定してください。"
            )
        if not self.config.endpoint:
            raise ValueError("エンドポイントURLが必要です")
        return True
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """HTTPセッションを取得（遅延初期化）"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://llm-smart-router.local",
                    "X-Title": "LLM Smart Router"
                }
            )
        return self.session
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> ModelResponse:
        """
        テキスト生成
        
        Args:
            prompt: ユーザープロンプト
            system_prompt: システムプロンプト
            **kwargs: temperature, max_tokens など
        """
        session = await self._get_session()
        
        messages = self.format_messages(prompt, system_prompt)
        
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens)
        }
        
        # OpenRouter固有の追加パラメータ
        if "top_p" in kwargs:
            payload["top_p"] = kwargs["top_p"]
        if "frequency_penalty" in kwargs:
            payload["frequency_penalty"] = kwargs["frequency_penalty"]
        
        try:
            async with session.post(
                f"{self.config.endpoint}/chat/completions",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout / 1000)
            ) as response:
                
                if response.status == 401:
                    raise ModelAuthenticationError("APIキーが無効です")
                elif response.status == 429:
                    raise ModelRateLimitError("レート制限に達しました")
                elif response.status == 413:
                    raise ModelContextLengthError("コンテキスト長が制限を超えています")
                elif response.status != 200:
                    error_text = await response.text()
                    raise ModelAdapterError(f"APIエラー: {response.status} - {error_text}")
                
                data = await response.json()
                
                choice = data["choices"][0]
                content = choice["message"]["content"]
                
                # トークン使用量
                usage = data.get("usage", {})
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)
                
                # 推定（usageがない場合）
                if input_tokens == 0:
                    input_tokens = self.count_tokens(prompt)
                    input_tokens += self.count_tokens(system_prompt) if system_prompt else 0
                if output_tokens == 0:
                    output_tokens = self.count_tokens(content)
                
                return ModelResponse(
                    content=content,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    model_name=self.config.model,
                    provider=self.config.provider,
                    metadata={
                        "finish_reason": choice.get("finish_reason"),
                        "response_id": data.get("id")
                    }
                )
                
        except aiohttp.ClientError as e:
            raise ModelAdapterError(f"通信エラー: {str(e)}")
    
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """ストリーミング生成"""
        session = await self._get_session()
        
        messages = self.format_messages(prompt, system_prompt)
        
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "stream": True
        }
        
        try:
            async with session.post(
                f"{self.config.endpoint}/chat/completions",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout / 1000)
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    raise ModelAdapterError(f"APIエラー: {response.status} - {error_text}")
                
                async for line in response.content:
                    line = line.decode("utf-8").strip()
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        # JSONパースしてコンテンツを抽出
                        import json
                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except (json.JSONDecodeError, KeyError):
                            continue
                            
        except aiohttp.ClientError as e:
            raise ModelAdapterError(f"通信エラー: {str(e)}")
    
    def count_tokens(self, text: str) -> int:
        """
        トークン数を概算
        Kimiは内部で独自のトークナイザーを使用
        ここでは簡易的な推定を行う
        """
        return self._estimate_tokens_simple(text)
    
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """コスト見積もり（USD）"""
        input_cost = (input_tokens / 1000) * self.COST_INPUT
        output_cost = (output_tokens / 1000) * self.COST_OUTPUT
        return input_cost + output_cost
    
    def get_capabilities(self) -> List[str]:
        """モデルの機能一覧"""
        return [
            "coding",
            "reasoning",
            "long_context",
            "instruction_following",
            "multilingual"
        ]
    
    async def close(self):
        """セッションをクローズ"""
        if self.session and not self.session.closed:
            await self.session.close()
