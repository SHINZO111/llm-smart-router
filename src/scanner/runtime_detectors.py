"""
ランタイム固有の検出ロジック

各ローカルLLMランタイムのAPI差異を吸収し、統一インターフェースで検出する。
対応ランタイム: LM Studio, Ollama, 汎用OpenAI互換サーバー
"""

import time
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Tuple, Optional

import aiohttp

from .runtime_info import RuntimeInfo, RuntimeType, DiscoveredModel, ModelSource

logger = logging.getLogger(__name__)


_ALLOWED_HOSTS = {"localhost", "127.0.0.1", "::1"}
_MAX_RESPONSE_SIZE = 5 * 1024 * 1024  # 5MB


class BaseRuntimeDetector(ABC):
    """ランタイム検出器の基底クラス"""

    def __init__(self, host: str, port: int, timeout: float = 2.0):
        # SSRF防止: localhostのみ許可
        if host not in _ALLOWED_HOSTS:
            raise ValueError(f"ホスト '{host}' は許可されていません。localhostのみスキャン可能です。")
        self.host = host
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://{host}:{port}"
        self._cached_data: Optional[dict] = None

    @abstractmethod
    async def detect(self) -> Tuple[bool, Optional[RuntimeInfo]]:
        """ランタイムが稼働中か検出。(検出成功, ランタイム情報) を返す"""

    @abstractmethod
    async def get_models(self, runtime_info: RuntimeInfo) -> List[DiscoveredModel]:
        """稼働中ランタイムからモデル一覧を取得"""

    async def _get_json(self, url: str) -> Optional[dict]:
        """GETリクエストしてJSONレスポンスを返す。失敗時はNone。レスポンスサイズ制限付き"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as resp:
                    if resp.status == 200:
                        # Content-Type確認
                        ct = resp.headers.get("Content-Type", "")
                        if ct and "json" not in ct and "text" not in ct:
                            logger.debug(f"非JSONレスポンス: {ct} ({url})")
                            return None
                        # サイズ制限チェック
                        body = await resp.content.read(_MAX_RESPONSE_SIZE + 1)
                        if len(body) > _MAX_RESPONSE_SIZE:
                            logger.debug(f"レスポンスが大きすぎます: {url}")
                            return None
                        import json
                        return json.loads(body)
        except Exception as e:
            logger.debug(f"GET {url} 失敗: {e}")
        return None


class LMStudioDetector(BaseRuntimeDetector):
    """
    LM Studio検出器

    デフォルトポート: 1234
    API: OpenAI互換 /v1/models
    フィンガープリント: owned_by に "lmstudio" を含む、またはポート1234
    """

    async def detect(self) -> Tuple[bool, Optional[RuntimeInfo]]:
        start = time.monotonic()
        data = await self._get_json(f"{self.base_url}/v1/models")

        if data and "data" in data:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._cached_data = data  # get_models()で再利用
            runtime = RuntimeInfo(
                runtime_type=RuntimeType.LMSTUDIO,
                endpoint=f"{self.base_url}/v1",
                port=self.port,
                is_responding=True,
                response_time_ms=round(elapsed_ms, 1),
                detected_at=_now_iso(),
                metadata={"model_count": len(data.get("data", []))},
            )
            return True, runtime
        return False, None

    async def get_models(self, runtime_info: RuntimeInfo) -> List[DiscoveredModel]:
        data = self._cached_data or await self._get_json(f"{self.base_url}/v1/models")
        self._cached_data = None
        if not data or "data" not in data:
            return []

        models = []
        for m in data["data"]:
            model_id = m.get("id", "")
            models.append(DiscoveredModel(
                id=model_id,
                name=m.get("name") or model_id,
                source=ModelSource.LOCAL_RUNTIME,
                runtime=runtime_info,
                endpoint=runtime_info.endpoint,
                owned_by=m.get("owned_by", "lmstudio"),
                description=f"LM Studio: {model_id}",
            ))
        return models


class OllamaDetector(BaseRuntimeDetector):
    """
    Ollama検出器

    デフォルトポート: 11434
    ネイティブAPI: /api/tags (モデル一覧)
    OpenAI互換: /v1/models
    フィンガープリント: /api/tags レスポンスに "models" キー
    """

    async def detect(self) -> Tuple[bool, Optional[RuntimeInfo]]:
        start = time.monotonic()

        # ネイティブAPIで確実にフィンガープリント
        data = await self._get_json(f"{self.base_url}/api/tags")
        if data and "models" in data:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._cached_data = data  # get_models()で再利用
            runtime = RuntimeInfo(
                runtime_type=RuntimeType.OLLAMA,
                endpoint=f"{self.base_url}/v1",
                port=self.port,
                is_responding=True,
                response_time_ms=round(elapsed_ms, 1),
                detected_at=_now_iso(),
                metadata={"model_count": len(data.get("models", []))},
            )
            return True, runtime
        return False, None

    async def get_models(self, runtime_info: RuntimeInfo) -> List[DiscoveredModel]:
        # ネイティブAPIからモデル情報取得（キャッシュ優先）
        data = self._cached_data or await self._get_json(f"{self.base_url}/api/tags")
        self._cached_data = None
        if not data or "models" not in data:
            return []

        models = []
        for m in data["models"]:
            model_name = m.get("name", "")
            details = m.get("details", {})
            size = m.get("size")
            family = details.get("family", "")
            param_size = details.get("parameter_size", "")

            desc_parts = [f"Ollama: {family}"] if family else ["Ollama"]
            if param_size:
                desc_parts.append(param_size)

            models.append(DiscoveredModel(
                id=model_name,
                name=model_name,
                source=ModelSource.LOCAL_RUNTIME,
                runtime=runtime_info,
                endpoint=runtime_info.endpoint,
                owned_by="library",
                size=size,
                description=" ".join(desc_parts),
            ))
        return models


class GenericOpenAIDetector(BaseRuntimeDetector):
    """
    汎用OpenAI互換API検出器

    llama.cpp server, KoboldCpp, LocalAI, Jan, GPT4All, vLLM等
    共通: GET /v1/models が 200 + {"data": [...]} を返す
    runtime_type はコンストラクタで指定
    """

    def __init__(
        self,
        host: str,
        port: int,
        runtime_type: RuntimeType = RuntimeType.UNKNOWN,
        runtime_label: str = "OpenAI互換",
        timeout: float = 2.0,
    ):
        super().__init__(host, port, timeout)
        self._runtime_type = runtime_type
        self._runtime_label = runtime_label

    async def detect(self) -> Tuple[bool, Optional[RuntimeInfo]]:
        start = time.monotonic()
        data = await self._get_json(f"{self.base_url}/v1/models")

        if data and "data" in data:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._cached_data = data  # get_models()で再利用
            runtime = RuntimeInfo(
                runtime_type=self._runtime_type,
                endpoint=f"{self.base_url}/v1",
                port=self.port,
                is_responding=True,
                response_time_ms=round(elapsed_ms, 1),
                detected_at=_now_iso(),
                metadata={"model_count": len(data.get("data", []))},
            )
            return True, runtime
        return False, None

    async def get_models(self, runtime_info: RuntimeInfo) -> List[DiscoveredModel]:
        data = self._cached_data or await self._get_json(f"{self.base_url}/v1/models")
        self._cached_data = None
        if not data or "data" not in data:
            return []

        models = []
        for m in data["data"]:
            model_id = m.get("id", "")
            models.append(DiscoveredModel(
                id=model_id,
                name=m.get("name") or model_id,
                source=ModelSource.LOCAL_RUNTIME,
                runtime=runtime_info,
                endpoint=runtime_info.endpoint,
                owned_by=m.get("owned_by", "unknown"),
                description=f"{self._runtime_label}: {model_id}",
            ))
        return models


def _now_iso() -> str:
    """現在時刻をISO形式文字列で返す"""
    return datetime.now().isoformat()
