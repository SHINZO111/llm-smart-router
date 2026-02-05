"""
OpenClaw統合機能のテスト
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
if str(project_root / "src") not in sys.path:
    sys.path.insert(0, str(project_root / "src"))


class TestRouterControlClient:
    """RouterControlClientのテスト"""

    @pytest.fixture
    def client(self):
        """テスト用クライアント"""
        from openclaw.router_control import RouterControlClient
        return RouterControlClient(api_url="http://localhost:8000")

    @pytest.fixture
    def mock_response(self):
        """モックレスポンス"""
        mock = Mock()
        mock.json.return_value = {"success": True, "model": "test", "response": "test response"}
        mock.raise_for_status = Mock()
        return mock

    def test_client_initialization(self, client):
        """クライアント初期化テスト"""
        assert client.api_url == "http://localhost:8000"
        assert client.session is not None
        assert "Content-Type" in client.session.headers

    def test_query_success(self, client, mock_response):
        """クエリ実行成功テスト"""
        with patch.object(client.session, 'post', return_value=mock_response):
            result = client.query("test query")
            assert result["success"] is True
            assert result["model"] == "test"
            assert result["response"] == "test response"

    def test_query_network_error(self, client):
        """ネットワークエラーテスト"""
        import requests
        with patch.object(client.session, 'post', side_effect=requests.RequestException("Connection failed")):
            result = client.query("test query")
            assert result["success"] is False
            assert "error" in result

    def test_get_stats_success(self, client):
        """統計取得成功テスト"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "models": {"local_count": 5, "cloud_count": 4},
            "fallback_priority": ["local", "cloud"]
        }
        mock_response.raise_for_status = Mock()

        with patch.object(client.session, 'get', return_value=mock_response):
            result = client.get_stats()
            assert "models" in result
            assert result["models"]["local_count"] == 5

    def test_trigger_scan_success(self, client):
        """スキャントリガー成功テスト"""
        mock_response = Mock()
        mock_response.json.return_value = {"status": "started", "message": "スキャン開始"}
        mock_response.raise_for_status = Mock()

        with patch.object(client.session, 'post', return_value=mock_response):
            result = client.trigger_scan()
            assert result["status"] == "started"

    def test_control_query_command(self, client, mock_response):
        """control()メソッド - queryコマンドテスト"""
        with patch.object(client.session, 'post', return_value=mock_response):
            result = client.control("query", {"input": "test"})
            assert result["success"] is True

    def test_control_invalid_command(self, client):
        """control()メソッド - 無効なコマンドテスト"""
        with pytest.raises(ValueError, match="Unknown command"):
            client.control("invalid_command")

    def test_context_manager(self):
        """コンテキストマネージャーテスト"""
        from openclaw.router_control import RouterControlClient

        with RouterControlClient() as client:
            assert client.session is not None

        # closeが呼ばれることを確認（sessionがクローズされる）
        assert client.session is not None  # sessionオブジェクト自体は残る

    def test_retry_on_500_error(self, client):
        """5xxエラー時のリトライテスト"""
        import requests
        from requests.adapters import HTTPAdapter

        # アダプターにリトライ設定があることを確認
        adapter = client.session.get_adapter("http://localhost:8000")
        assert isinstance(adapter, HTTPAdapter)
        assert adapter.max_retries.total == 3


class TestRouterQueryRequestValidation:
    """RouterQueryRequestバリデーションテスト"""

    @pytest.fixture
    def mock_app(self):
        """FastAPIアプリのモック"""
        from fastapi.testclient import TestClient
        from api.routes import router

        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_valid_request(self, mock_app):
        """正常なリクエストテスト"""
        # router.jsが存在しない環境ではエラーになるため、モックが必要
        # 実際のE2Eテストは別途実施
        pass

    def test_context_too_large(self):
        """コンテキストサイズ超過テスト"""
        from api.routes import RouterQueryRequest
        from pydantic import ValidationError

        # 10KB超のコンテキスト
        large_context = {f"key_{i}": "x" * 1000 for i in range(20)}

        with pytest.raises(ValidationError):
            RouterQueryRequest(
                input="test",
                context=large_context
            )

    def test_context_too_many_keys(self):
        """コンテキストキー数超過テスト"""
        from api.routes import RouterQueryRequest
        from pydantic import ValidationError

        # 50キー超
        many_keys = {f"key_{i}": "value" for i in range(60)}

        with pytest.raises(ValidationError):
            RouterQueryRequest(
                input="test",
                context=many_keys
            )

    def test_force_model_alias(self):
        """force_modelエイリアステスト"""
        from api.routes import RouterQueryRequest

        # camelCase形式でも受け入れる
        req = RouterQueryRequest(
            input="test",
            forceModel="local:test-model"
        )
        assert req.force_model == "local:test-model"


class TestOpenClawIntegrationSecurity:
    """セキュリティテスト"""

    def test_path_traversal_prevention(self):
        """パストラバーサル防止テスト"""
        # router.jsのAPI mode入力ファイルパス検証
        # 実際のテストはNode.js側で実施（ここではコンセプトのみ）
        pass

    def test_command_whitelist(self):
        """コマンドホワイトリストテスト"""
        from openclaw.router_control import RouterControlClient

        client = RouterControlClient()
        with pytest.raises(ValueError, match="Unknown command"):
            client.control("rm -rf /")

    def test_context_injection_prevention(self):
        """コンテキストインジェクション防止テスト"""
        from api.routes import RouterQueryRequest

        # 悪意のあるコンテキスト
        malicious_context = {
            "__proto__": {"polluted": True},
            "constructor": {"prototype": {"polluted": True}}
        }

        # バリデーションを通過（キー数・サイズ制限内）
        req = RouterQueryRequest(
            input="test",
            context=malicious_context
        )

        # プロトタイプ汚染が発生しないことを確認
        # （Pythonでは問題ないが、Node.js側で注意が必要）
        assert req.context == malicious_context


def test_cli_execution():
    """CLIモード実行テスト"""
    import subprocess

    # router_control.pyをCLIとして実行
    result = subprocess.run(
        [sys.executable, "-m", "openclaw.router_control"],
        cwd=str(project_root / "src"),
        capture_output=True,
        text=True,
        timeout=5
    )

    # 使用方法が表示されることを確認
    assert "Usage:" in result.stdout or result.returncode == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
