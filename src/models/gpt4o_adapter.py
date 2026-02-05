"""
GPT-4o Model Adapter - openai/gpt-4o
OpenAI API経由で利用
"""

import os
import asyncio
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


class GPT4oAdapter(BaseModelAdapter):
    """
    GPT-4o アダプター
    
    特徴:
    - マルチモーダル対応（テキスト+画像）
    - 高速かつ高品質
    - JSONモード対応
    - 関数呼び出し対応
    """
    
    DEFAULT_ENDPOINT = "https://api.openai.com/v1"
    DEFAULT_MODEL = "gpt-4o"
    
    # コスト設定（USD per 1K tokens）
    COST_INPUT = 0.005
    COST_OUTPUT = 0.015
    
    def __init__(self, config: Optional[ModelConfig] = None):
        if config is None:
            config = self._create_default_config()
        super().__init__(config)
        self.session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()

    def _create_default_config(self) -> ModelConfig:
        """デフォルト設定を作成"""
        api_key = os.getenv("OPENAI_API_KEY")
        return ModelConfig(
            provider="openai",
            model=self.DEFAULT_MODEL,
            endpoint=self.DEFAULT_ENDPOINT,
            api_key=api_key,
            timeout=60000,
            max_tokens=4096,
            temperature=0.7
        )

    def validate_config(self) -> bool:
        """設定を検証"""
        if not self.config.api_key:
            raise ModelAuthenticationError(
                "OpenAI APIキーが必要です。OPENAI_API_KEY を設定してください。"
            )
        return True

    async def _get_session(self) -> aiohttp.ClientSession:
        """HTTPセッションを取得（遅延初期化、スレッドセーフ）"""
        async with self._session_lock:
            if self.session is None or self.session.closed:
                self.session = aiohttp.ClientSession(
                    headers={
                        "Authorization": f"Bearer {self.config.api_key}",
                        "Content-Type": "application/json"
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
            **kwargs: 
                - temperature: 温度パラメータ
                - max_tokens: 最大トークン数
                - json_mode: JSONモード有効化
                - response_format: 応答フォーマット
        """
        session = await self._get_session()
        
        messages = self.format_messages(prompt, system_prompt)
        
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens)
        }
        
        # JSONモード
        if kwargs.get("json_mode"):
            payload["response_format"] = {"type": "json_object"}
        elif "response_format" in kwargs:
            payload["response_format"] = kwargs["response_format"]
        
        # 関数呼び出し
        if "tools" in kwargs:
            payload["tools"] = kwargs["tools"]
        if "tool_choice" in kwargs:
            payload["tool_choice"] = kwargs["tool_choice"]
        
        # その他のパラメータ
        for param in ["top_p", "frequency_penalty", "presence_penalty", "seed"]:
            if param in kwargs:
                payload[param] = kwargs[param]
        
        try:
            async with session.post(
                f"{self.config.endpoint}/chat/completions",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout / 1000)
            ) as response:
                
                if response.status == 401:
                    raise ModelAuthenticationError("APIキーが無効です")
                elif response.status == 429:
                    retry_after = response.headers.get("Retry-After", "unknown")
                    raise ModelRateLimitError(f"レート制限に達しました。Retry-After: {retry_after}")
                elif response.status == 400:
                    error_data = await response.json()
                    error_msg = error_data.get("error", {}).get("message", "")
                    if "context length" in error_msg.lower():
                        raise ModelContextLengthError("コンテキスト長が制限を超えています")
                    raise ModelAdapterError(f"リクエストエラー: {error_msg}")
                elif response.status != 200:
                    error_text = await response.text()
                    raise ModelAdapterError(f"APIエラー: {response.status} - {error_text}")
                
                data = await response.json()
                
                choice = data["choices"][0]
                message = choice["message"]
                
                # コンテンツ抽出（ツール呼び出しの場合も対応）
                content = message.get("content", "")
                
                # トークン使用量
                usage = data.get("usage", {})
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)
                
                metadata = {
                    "finish_reason": choice.get("finish_reason"),
                    "response_id": data.get("id"),
                    "system_fingerprint": data.get("system_fingerprint")
                }
                
                # ツール呼び出し情報
                if "tool_calls" in message:
                    metadata["tool_calls"] = message["tool_calls"]
                
                return ModelResponse(
                    content=content,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    model_name=self.config.model,
                    provider=self.config.provider,
                    metadata=metadata
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
    
    async def generate_with_image(
        self,
        prompt: str,
        image_url: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> ModelResponse:
        """
        画像付きテキスト生成（マルチモーダル）
        
        Args:
            prompt: テキストプロンプト
            image_url: 画像URLまたはbase64データURL
            system_prompt: システムプロンプト
        """
        session = await self._get_session()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # マルチモーダルメッセージ
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
        })
        
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens)
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
                
                data = await response.json()
                choice = data["choices"][0]
                content = choice["message"]["content"]
                
                usage = data.get("usage", {})
                
                return ModelResponse(
                    content=content,
                    input_tokens=usage.get("prompt_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0),
                    model_name=self.config.model,
                    provider=self.config.provider,
                    metadata={"finish_reason": choice.get("finish_reason")}
                )
                
        except aiohttp.ClientError as e:
            raise ModelAdapterError(f"通信エラー: {str(e)}")
    
    def count_tokens(self, text: str) -> int:
        """
        トークン数を概算
        GPT-4oはcl100k_baseトークナイザーを使用
        簡易推定を行う
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
            "vision",
            "coding",
            "reasoning",
            "json_mode",
            "function_calling",
            "streaming",
            "multilingual"
        ]
    
    async def close(self):
        """セッションをクローズ"""
        if self.session and not self.session.closed:
            await self.session.close()
