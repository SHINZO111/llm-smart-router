"""
クラウドモデル検出

環境変数（APIキー）の有無をチェックし、利用可能なクラウドモデルを返す。
実際のAPI疎通は行わない（キーの存在のみ確認）。
"""

import os
import logging
from typing import List, Dict, Any

from .runtime_info import DiscoveredModel, ModelSource

logger = logging.getLogger(__name__)

# プロバイダー定義: APIキー環境変数名 → 代表モデル一覧
CLOUD_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "anthropic": {
        "env_var": "ANTHROPIC_API_KEY",
        "endpoint": "https://api.anthropic.com",
        "models": [
            {
                "id": "claude-sonnet-4-5-20250929",
                "name": "Claude Sonnet 4.5",
                "description": "Anthropic最新フラッグシップ",
                "capabilities": ["reasoning", "coding", "analysis", "vision"],
            },
            {
                "id": "claude-3-5-sonnet-20241022",
                "name": "Claude 3.5 Sonnet",
                "description": "バランス型高性能モデル",
                "capabilities": ["reasoning", "vision", "coding"],
            },
        ],
    },
    "openai": {
        "env_var": "OPENAI_API_KEY",
        "endpoint": "https://api.openai.com/v1",
        "models": [
            {
                "id": "gpt-4o",
                "name": "GPT-4o",
                "description": "マルチモーダルフラッグシップ",
                "capabilities": ["vision", "coding", "reasoning", "json_mode"],
            },
            {
                "id": "gpt-4o-mini",
                "name": "GPT-4o Mini",
                "description": "コスト効率型GPT-4クラス",
                "capabilities": ["vision", "coding", "json_mode"],
            },
        ],
    },
    "google": {
        "env_var": "GOOGLE_API_KEY",
        "endpoint": "https://generativelanguage.googleapis.com/v1beta",
        "models": [
            {
                "id": "gemini-2.0-flash",
                "name": "Gemini 2.0 Flash",
                "description": "高速・長文脈対応",
                "capabilities": ["long_context", "multimodal", "reasoning"],
            },
            {
                "id": "gemini-pro",
                "name": "Gemini Pro",
                "description": "長文脈・低コスト",
                "capabilities": ["long_context", "multimodal"],
            },
        ],
    },
    "openrouter": {
        "env_var": "OPENROUTER_API_KEY",
        "endpoint": "https://openrouter.ai/api/v1",
        "models": [
            {
                "id": "kimi-coding/k2p5",
                "name": "Kimi K2P5",
                "description": "コーディング特化",
                "capabilities": ["coding", "reasoning", "long_context"],
            },
        ],
    },
}


class CloudModelDetector:
    """環境変数ベースのクラウドモデル検出"""

    def __init__(self, providers: Dict[str, Dict[str, Any]] = None):
        self.providers = providers if providers is not None else CLOUD_PROVIDERS

    def detect(self) -> List[DiscoveredModel]:
        """
        APIキーが設定されているプロバイダーのモデルを返す

        Returns:
            利用可能なクラウドモデルのリスト
        """
        available: List[DiscoveredModel] = []

        for provider_name, config in self.providers.items():
            env_var = config["env_var"]
            api_key = os.getenv(env_var, "")

            if not api_key:
                logger.debug(f"{provider_name}: {env_var} 未設定")
                continue

            logger.info(f"{provider_name}: APIキー検出 ({env_var})")
            endpoint = config.get("endpoint", "")

            for model_def in config["models"]:
                available.append(DiscoveredModel(
                    id=model_def["id"],
                    name=model_def["name"],
                    source=ModelSource.CLOUD_API,
                    provider=provider_name,
                    api_key_env=env_var,
                    api_key_present=True,
                    endpoint=endpoint,
                    description=model_def.get("description", ""),
                    capabilities=model_def.get("capabilities", []),
                    owned_by=provider_name,
                ))

        logger.info(f"クラウドモデル: {len(available)}個検出")
        return available
