"""
OpenClaw → LLM Smart Router 制御モジュール

OpenClawからPython経由でLLM Smart Routerを操作するためのクライアント
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
from typing import Optional, Dict, Any, Union
import os

logger = logging.getLogger(__name__)


class RouterControlClient:
    """
    LLM Smart Router APIクライアント

    OpenClawからこのアプリを操作するためのPythonインターフェース

    Usage:
        # Context manager (推奨)
        with RouterControlClient() as client:
            result = client.query("質問内容")

        # 直接使用
        client = RouterControlClient()
        result = client.query("質問内容")
        client.close()
    """

    def __init__(self, api_url: Optional[str] = None):
        """
        Args:
            api_url: APIベースURL（省略時は環境変数 LLM_ROUTER_API_URL または http://localhost:8000）
        """
        self.api_url = api_url or os.getenv("LLM_ROUTER_API_URL", "http://localhost:8000")
        self.session = requests.Session()

        # リトライ戦略を設定
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        self.session.headers.update({"Content-Type": "application/json"})

    def query(
        self,
        input_text: str,
        force_model: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        timeout: int = 120
    ) -> Dict[str, Any]:
        """
        クエリを実行（インテリジェントルーティング）

        Args:
            input_text: クエリテキスト
            force_model: モデル指定（省略時は自動判定）
            context: 追加コンテキスト
            timeout: タイムアウト秒数

        Returns:
            実行結果（success, model, response, metadata, errorフィールドを含む）
        """
        try:
            response = self.session.post(
                f"{self.api_url}/router/query",
                json={
                    "input": input_text,
                    "force_model": force_model,
                    "context": context or {}
                },
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"クエリ実行エラー: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_stats(self, timeout: int = 10) -> Dict[str, Any]:
        """
        ルーター統計を取得

        Args:
            timeout: タイムアウト秒数

        Returns:
            統計情報
        """
        try:
            response = self.session.get(
                f"{self.api_url}/router/stats",
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"統計取得エラー: {e}")
            return {"error": str(e)}

    def trigger_scan(self, timeout: int = 10) -> Dict[str, Any]:
        """
        モデルスキャンをトリガー

        Args:
            timeout: タイムアウト秒数

        Returns:
            スキャン結果
        """
        try:
            response = self.session.post(
                f"{self.api_url}/models/scan",
                json={},
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"モデルスキャンエラー: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_detected_models(self, timeout: int = 10) -> Dict[str, Any]:
        """
        検出済みモデル一覧を取得

        Args:
            timeout: タイムアウト秒数

        Returns:
            モデル一覧
        """
        try:
            response = self.session.get(
                f"{self.api_url}/models/detected",
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"モデル一覧取得エラー: {e}")
            return {"error": str(e)}

    def reload_config(self, timeout: int = 10) -> Dict[str, Any]:
        """
        ルーター設定をリロード

        Args:
            timeout: タイムアウト秒数

        Returns:
            リロード結果
        """
        try:
            response = self.session.post(
                f"{self.api_url}/router/config/reload",
                json={},
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"設定リロードエラー: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def control(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        統合コマンドインターフェース

        Args:
            command: コマンド名 (query/scan/stats/models/reload)
            params: パラメータ

        Returns:
            実行結果
            - query: {"success": bool, "model": str, "response": str, "metadata": dict, "error": str}
            - scan: {"status": str, "message": str}
            - stats: {"models": dict, "fallback_priority": list, "conversations": dict}
            - models: {"local": list, "cloud": list, "total": int, "last_scan": str, "cache_valid": bool}
            - reload: {"success": bool, "message": str, "models_loaded": int}

        Raises:
            ValueError: 不明なコマンド指定時
        """
        VALID_COMMANDS = ["query", "scan", "stats", "models", "reload"]

        if command not in VALID_COMMANDS:
            raise ValueError(f"Unknown command: {command}. Valid: {', '.join(VALID_COMMANDS)}")

        params = params or {}

        if command == "query":
            return self.query(
                params.get("input", ""),
                params.get("force_model"),
                params.get("context")
            )
        elif command == "scan":
            return self.trigger_scan()
        elif command == "stats":
            return self.get_stats()
        elif command == "models":
            return self.get_detected_models()
        elif command == "reload":
            return self.reload_config()
        else:
            # 到達不可（VALID_COMMENCHECKで検証済み）
            return {
                "success": False,
                "error": f"Unknown command: {command}"
            }

    def close(self):
        """セッションをクローズ"""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# CLI実行時
if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python -m openclaw.router_control <command> [params...]")
        print("")
        print("Commands:")
        print("  query <text>     - クエリ実行")
        print("  scan             - モデルスキャン")
        print("  stats            - 統計取得")
        print("  models           - モデル一覧")
        print("  reload           - 設定リロード")
        sys.exit(1)

    command = sys.argv[1]
    client = RouterControlClient()

    try:
        if command == "query":
            if len(sys.argv) < 3:
                print("Error: query requires text argument")
                sys.exit(1)
            result = client.query(" ".join(sys.argv[2:]))
        elif command == "scan":
            result = client.trigger_scan()
        elif command == "stats":
            result = client.get_stats()
        elif command == "models":
            result = client.get_detected_models()
        elif command == "reload":
            result = client.reload_config()
        else:
            result = {"success": False, "error": f"Unknown command: {command}"}

        print(json.dumps(result, indent=2, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}, indent=2))
        sys.exit(1)
    finally:
        client.close()
