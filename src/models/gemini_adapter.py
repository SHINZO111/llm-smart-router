"""
Gemini Model Adapter - google/gemini-pro
Google AI Studio / Vertex AI経由で利用
"""

import os
import asyncio
import aiohttp
import base64
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


class GeminiAdapter(BaseModelAdapter):
    """
    Gemini (gemini-pro) アダプター
    
    特徴:
    - 長文脈対応（1Mトークン）
    - マルチモーダル対応
    - コスト効率が良い
    """
    
    DEFAULT_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta"
    DEFAULT_MODEL = "gemini-pro"
    
    # コスト設定（USD per 1K tokens）
    COST_INPUT = 0.001
    COST_OUTPUT = 0.003
    
    def __init__(self, config: Optional[ModelConfig] = None):
        if config is None:
            config = self._create_default_config()
        super().__init__(config)
        self.session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()

    def _create_default_config(self) -> ModelConfig:
        """デフォルト設定を作成"""
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        return ModelConfig(
            provider="google",
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
                "Google APIキーが必要です。GOOGLE_API_KEY または GEMINI_API_KEY を設定してください。"
            )
        return True

    async def _get_session(self) -> aiohttp.ClientSession:
        """HTTPセッションを取得（遅延初期化、スレッドセーフ）"""
        async with self._session_lock:
            if self.session is None or self.session.closed:
                self.session = aiohttp.ClientSession()
            return self.session
    
    def _build_url(self, action: str = "generateContent") -> str:
        """API URLを構築"""
        return f"{self.config.endpoint}/models/{self.config.model}:{action}?key={self.config.api_key}"
    
    def _convert_messages_to_gemini_format(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        OpenAI形式のメッセージをGemini形式に変換
        
        Geminiの形式:
        {
            "systemInstruction": {"role": "system", "parts": [{"text": "..."}]},
            "contents": [
                {"role": "user", "parts": [{"text": "..."}]},
                {"role": "model", "parts": [{"text": "..."}]}
            ]
        }
        """
        result: Dict[str, Any] = {}
        
        # システムプロンプト
        if system_prompt:
            result["systemInstruction"] = {
                "role": "system",
                "parts": [{"text": system_prompt}]
            }
        
        # コンテンツ（履歴 + 現在のプロンプト）
        contents = []
        
        if history:
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": msg["content"]}]
                })
        
        # 現在のプロンプト
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })
        
        result["contents"] = contents
        
        return result
    
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
        
        # Gemini形式に変換
        body = self._convert_messages_to_gemini_format(prompt, system_prompt)
        
        # 生成設定
        generation_config: Dict[str, Any] = {}
        
        temperature = kwargs.get("temperature", self.config.temperature)
        if temperature is not None:
            generation_config["temperature"] = temperature
        
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
        if max_tokens:
            generation_config["maxOutputTokens"] = max_tokens
        
        if "top_p" in kwargs:
            generation_config["topP"] = kwargs["top_p"]
        if "top_k" in kwargs:
            generation_config["topK"] = kwargs["top_k"]
        
        if generation_config:
            body["generationConfig"] = generation_config
        
        # 安全性設定（オプション）
        if "safety_settings" in kwargs:
            body["safetySettings"] = kwargs["safety_settings"]
        
        try:
            async with session.post(
                self._build_url("generateContent"),
                json=body,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout / 1000)
            ) as response:
                
                if response.status == 400:
                    error_data = await response.json()
                    error_msg = error_data.get("error", {}).get("message", "")
                    if "API key not valid" in error_msg:
                        raise ModelAuthenticationError("APIキーが無効です")
                    raise ModelAdapterError(f"リクエストエラー: {error_msg}")
                elif response.status == 429:
                    raise ModelRateLimitError("レート制限に達しました")
                elif response.status == 413:
                    raise ModelContextLengthError("コンテキスト長が制限を超えています")
                elif response.status != 200:
                    error_text = await response.text()
                    raise ModelAdapterError(f"APIエラー: {response.status} - {error_text}")
                
                data = await response.json()
                
                # 応答を抽出
                candidates = data.get("candidates", [])
                if not candidates:
                    # ブロックされた場合
                    prompt_feedback = data.get("promptFeedback", {})
                    block_reason = prompt_feedback.get("blockReason", "Unknown")
                    raise ModelAdapterError(f"コンテンツがブロックされました: {block_reason}")
                
                content = candidates[0]["content"]["parts"][0]["text"]
                
                # トークン使用量（Geminiは必ずしも返さない）
                usage = data.get("usageMetadata", {})
                input_tokens = usage.get("promptTokenCount", 0)
                output_tokens = usage.get("candidatesTokenCount", 0)
                
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
                        "finish_reason": candidates[0].get("finishReason"),
                        "safety_ratings": candidates[0].get("safetyRatings"),
                        "total_token_count": usage.get("totalTokenCount", 0)
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
        
        body = self._convert_messages_to_gemini_format(prompt, system_prompt)
        
        generation_config = {}
        temperature = kwargs.get("temperature", self.config.temperature)
        if temperature is not None:
            generation_config["temperature"] = temperature
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
        if max_tokens:
            generation_config["maxOutputTokens"] = max_tokens
        
        if generation_config:
            body["generationConfig"] = generation_config
        
        try:
            async with session.post(
                self._build_url("streamGenerateContent"),
                json=body,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout / 1000)
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    raise ModelAdapterError(f"APIエラー: {response.status} - {error_text}")
                
                async for line in response.content:
                    line = line.decode("utf-8").strip()
                    if not line:
                        continue
                    
                    # GeminiのストリームはJSON配列形式
                    import json
                    try:
                        # 配列の要素としてパース
                        if line.startswith("["):
                            line = line[1:]
                        if line.startswith(","):
                            line = line[1:]
                        if line.endswith("]"):
                            line = line[:-1]
                        
                        chunk = json.loads(line)
                        candidates = chunk.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            for part in parts:
                                text = part.get("text", "")
                                if text:
                                    yield text
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                        
        except aiohttp.ClientError as e:
            raise ModelAdapterError(f"通信エラー: {str(e)}")
    
    async def generate_with_image(
        self,
        prompt: str,
        image_data: bytes,
        mime_type: str = "image/jpeg",
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> ModelResponse:
        """
        画像付きテキスト生成（マルチモーダル）
        
        Args:
            prompt: テキストプロンプト
            image_data: 画像バイナリデータ
            mime_type: 画像MIMEタイプ
            system_prompt: システムプロンプト
        """
        session = await self._get_session()
        
        # base64エンコード
        image_b64 = base64.b64encode(image_data).decode("utf-8")
        
        body: Dict[str, Any] = {}
        
        if system_prompt:
            body["systemInstruction"] = {
                "role": "system",
                "parts": [{"text": system_prompt}]
            }
        
        # マルチモーダルコンテンツ
        body["contents"] = [{
            "role": "user",
            "parts": [
                {"text": prompt},
                {
                    "inlineData": {
                        "mimeType": mime_type,
                        "data": image_b64
                    }
                }
            ]
        }]
        
        # 生成設定
        generation_config = {}
        temperature = kwargs.get("temperature", self.config.temperature)
        if temperature is not None:
            generation_config["temperature"] = temperature
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
        if max_tokens:
            generation_config["maxOutputTokens"] = max_tokens
        
        if generation_config:
            body["generationConfig"] = generation_config
        
        try:
            async with session.post(
                self._build_url("generateContent"),
                json=body,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout / 1000)
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    raise ModelAdapterError(f"APIエラー: {response.status} - {error_text}")
                
                data = await response.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    raise ModelAdapterError("コンテンツがブロックされました")
                
                content = candidates[0]["content"]["parts"][0]["text"]
                usage = data.get("usageMetadata", {})
                
                return ModelResponse(
                    content=content,
                    input_tokens=usage.get("promptTokenCount", 0),
                    output_tokens=usage.get("candidatesTokenCount", 0),
                    model_name=self.config.model,
                    provider=self.config.provider,
                    metadata={"finish_reason": candidates[0].get("finishReason")}
                )
                
        except aiohttp.ClientError as e:
            raise ModelAdapterError(f"通信エラー: {str(e)}")
    
    def count_tokens(self, text: str) -> int:
        """
        トークン数を概算
        GeminiはSentencePieceベースのトークナイザーを使用
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
            "long_context",
            "multimodal",
            "reasoning",
            "multilingual",
            "streaming"
        ]
    
    async def close(self):
        """セッションをクローズ"""
        if self.session and not self.session.closed:
            await self.session.close()
