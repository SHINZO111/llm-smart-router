"""
Ollama REST API クライアント
モデル管理操作（pull/delete/list/show）を提供する。
ルーティングは既存のOpenAI互換エンドポイントを使用。
"""

import json
import logging
from typing import Callable, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    requests = None

# localhost のみ許可（SSRF防止）
_ALLOWED_HOSTS = {"localhost", "127.0.0.1", "::1"}

DEFAULT_TIMEOUT = 5.0


class OllamaClient:
    """
    Ollama REST API クライアント

    管理操作のみ:
    - list_models: モデル一覧取得
    - pull_model: モデルダウンロード（ストリーミング進捗）
    - delete_model: モデル削除
    - show_model: モデル詳細取得
    """

    def __init__(self, base_url: str = "http://localhost:11434"):
        parsed = urlparse(base_url)
        if parsed.hostname not in _ALLOWED_HOSTS:
            raise ValueError(f"localhost以外のホストは許可されていません: {parsed.hostname}")
        self.base_url = base_url.rstrip("/")

    def is_available(self, timeout: float = DEFAULT_TIMEOUT) -> bool:
        """Ollamaが応答可能かチェック"""
        if not HAS_REQUESTS:
            return False
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=timeout)
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self, timeout: float = DEFAULT_TIMEOUT) -> list:
        """
        利用可能なモデル一覧を取得

        Returns:
            モデル情報のリスト。各要素は name, size, modified_at 等を含む dict。
            エラー時は空リスト。
        """
        if not HAS_REQUESTS:
            logger.warning("requestsモジュール未インストール")
            return []

        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            return data.get("models", [])
        except Exception as e:
            logger.error(f"Ollamaモデル一覧取得失敗: {e}")
            return []

    def pull_model(
        self,
        name: str,
        on_progress: Optional[Callable] = None,
        timeout: float = 600.0,
    ) -> bool:
        """
        モデルをダウンロード

        Args:
            name: モデル名 (例: "llama3.2", "tinyllama:latest")
            on_progress: 進捗コールバック (status: str, completed: int, total: int)
            timeout: 全体タイムアウト（秒）。大モデルは時間がかかる。

        Returns:
            成功ならTrue
        """
        if not HAS_REQUESTS:
            logger.warning("requestsモジュール未インストール")
            return False

        try:
            resp = requests.post(
                f"{self.base_url}/api/pull",
                json={"name": name},
                stream=True,
                timeout=timeout,
            )
            resp.raise_for_status()

            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    progress = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue

                status = progress.get("status", "")
                completed = progress.get("completed", 0)
                total = progress.get("total", 0)

                if on_progress:
                    try:
                        on_progress(status, completed, total)
                    except Exception:
                        pass

                if progress.get("error"):
                    logger.error(f"Ollama pull エラー: {progress['error']}")
                    return False

            logger.info(f"モデル '{name}' のpull完了")
            return True

        except Exception as e:
            logger.error(f"Ollama pull失敗 ({name}): {e}")
            return False

    def delete_model(self, name: str, timeout: float = DEFAULT_TIMEOUT) -> bool:
        """
        モデルを削除

        Args:
            name: モデル名

        Returns:
            成功ならTrue
        """
        if not HAS_REQUESTS:
            return False

        try:
            resp = requests.delete(
                f"{self.base_url}/api/delete",
                json={"name": name},
                timeout=timeout,
            )
            if resp.status_code == 200:
                logger.info(f"モデル '{name}' を削除しました")
                return True
            logger.warning(f"モデル削除失敗 ({name}): HTTP {resp.status_code}")
            return False
        except Exception as e:
            logger.error(f"モデル削除失敗 ({name}): {e}")
            return False

    def show_model(self, name: str, timeout: float = DEFAULT_TIMEOUT) -> dict:
        """
        モデル詳細を取得

        Args:
            name: モデル名

        Returns:
            モデル情報 dict (modelfile, parameters, template 等)。エラー時は空 dict。
        """
        if not HAS_REQUESTS:
            return {}

        try:
            resp = requests.post(
                f"{self.base_url}/api/show",
                json={"name": name},
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"モデル情報取得失敗 ({name}): {e}")
            return {}
