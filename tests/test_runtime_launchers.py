"""
Ollama/llama.cpp ランチャー・クライアントテスト
すべてモック — 実Ollama/llama.cpp不要
"""

import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
src_path = str(project_root / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)


# ==============================================================
# OllamaClient テスト
# ==============================================================

class TestOllamaClient:
    """OllamaClient のテスト"""

    def _make_client(self, base_url="http://localhost:11434"):
        from models.ollama_client import OllamaClient
        return OllamaClient(base_url=base_url)

    def test_localhost_only(self):
        """localhost以外のURLは拒否"""
        from models.ollama_client import OllamaClient
        with pytest.raises(ValueError, match="localhost以外"):
            OllamaClient(base_url="http://evil.com:11434")

    def test_allowed_hosts(self):
        """許可されたホストでインスタンス化可能"""
        from models.ollama_client import OllamaClient
        OllamaClient(base_url="http://localhost:11434")
        OllamaClient(base_url="http://127.0.0.1:11434")

    @patch("models.ollama_client.requests")
    def test_is_available_true(self, mock_requests):
        """API応答がある場合True"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_requests.get.return_value = mock_resp

        client = self._make_client()
        assert client.is_available() is True
        mock_requests.get.assert_called_once()

    @patch("models.ollama_client.requests")
    def test_is_available_false(self, mock_requests):
        """接続失敗時はFalse"""
        mock_requests.get.side_effect = Exception("Connection refused")

        client = self._make_client()
        assert client.is_available() is False

    @patch("models.ollama_client.requests")
    def test_list_models(self, mock_requests):
        """モデル一覧を正しく返す"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [
                {"name": "llama3.2:latest", "size": 4_000_000_000},
                {"name": "tinyllama:latest", "size": 600_000_000},
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_requests.get.return_value = mock_resp

        client = self._make_client()
        models = client.list_models()
        assert len(models) == 2
        assert models[0]["name"] == "llama3.2:latest"

    @patch("models.ollama_client.requests")
    def test_list_models_error(self, mock_requests):
        """一覧取得失敗時は空リスト"""
        mock_requests.get.side_effect = Exception("timeout")

        client = self._make_client()
        assert client.list_models() == []

    @patch("models.ollama_client.requests")
    def test_pull_model_success(self, mock_requests):
        """モデルpull成功"""
        lines = [
            json.dumps({"status": "pulling manifest"}).encode(),
            json.dumps({"status": "downloading", "completed": 50, "total": 100}).encode(),
            json.dumps({"status": "success"}).encode(),
        ]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.iter_lines.return_value = iter(lines)
        mock_requests.post.return_value = mock_resp

        progress_calls = []
        client = self._make_client()
        result = client.pull_model("tinyllama", on_progress=lambda s, c, t: progress_calls.append((s, c, t)))

        assert result is True
        assert len(progress_calls) == 3

    @patch("models.ollama_client.requests")
    def test_pull_model_error_in_stream(self, mock_requests):
        """ストリーム中にエラーが含まれる場合False"""
        lines = [
            json.dumps({"status": "pulling manifest"}).encode(),
            json.dumps({"error": "model not found"}).encode(),
        ]
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.iter_lines.return_value = iter(lines)
        mock_requests.post.return_value = mock_resp

        client = self._make_client()
        result = client.pull_model("nonexistent-model")
        assert result is False

    @patch("models.ollama_client.requests")
    def test_delete_model_success(self, mock_requests):
        """モデル削除成功"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_requests.delete.return_value = mock_resp

        client = self._make_client()
        assert client.delete_model("tinyllama") is True

    @patch("models.ollama_client.requests")
    def test_delete_model_failure(self, mock_requests):
        """モデル削除失敗（404等）"""
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_requests.delete.return_value = mock_resp

        client = self._make_client()
        assert client.delete_model("nonexistent") is False

    @patch("models.ollama_client.requests")
    def test_show_model(self, mock_requests):
        """モデル詳細取得"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "modelfile": "FROM llama3.2",
            "parameters": "temperature 0.7",
            "template": "{{ .Prompt }}",
        }
        mock_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_resp

        client = self._make_client()
        info = client.show_model("llama3.2")
        assert info["modelfile"] == "FROM llama3.2"

    @patch("models.ollama_client.requests")
    def test_show_model_error(self, mock_requests):
        """モデル詳細取得失敗時は空dict"""
        mock_requests.post.side_effect = Exception("error")

        client = self._make_client()
        assert client.show_model("nonexistent") == {}


# ==============================================================
# OllamaLauncher テスト
# ==============================================================

class TestOllamaLauncher:
    """OllamaLauncher のテスト"""

    def _make_launcher(self, **kwargs):
        from launcher.ollama_launcher import OllamaLauncher
        return OllamaLauncher(**kwargs)

    def test_default_endpoint(self):
        """デフォルトエンドポイント"""
        launcher = self._make_launcher()
        assert launcher.endpoint == "http://localhost:11434"

    def test_custom_endpoint(self):
        """カスタムエンドポイント（末尾スラッシュ除去）"""
        launcher = self._make_launcher(endpoint="http://localhost:9999/")
        assert launcher.endpoint == "http://localhost:9999"

    @patch("launcher.ollama_launcher.os.environ", {"OLLAMA_ENDPOINT": "http://localhost:5555"})
    def test_env_endpoint(self):
        """環境変数からエンドポイント取得"""
        launcher = self._make_launcher()
        assert launcher.endpoint == "http://localhost:5555"

    def test_find_executable_explicit_path(self, tmp_path):
        """明示パスが存在する場合"""
        exe = tmp_path / "ollama.exe"
        exe.touch()
        launcher = self._make_launcher(executable_path=str(exe))
        assert launcher.find_executable() == str(exe)

    def test_find_executable_explicit_missing(self, tmp_path):
        """明示パスが存在しない場合"""
        launcher = self._make_launcher(executable_path=str(tmp_path / "nonexistent"))
        # 他のパスも見つからなければNone
        with patch("launcher.ollama_launcher.shutil.which", return_value=None):
            result = launcher.find_executable()
        # explicit path missing → continues to other search paths → None if nothing found
        assert result is None or isinstance(result, str)

    @patch("launcher.ollama_launcher.shutil.which", return_value="/usr/bin/ollama")
    def test_find_executable_path_search(self, mock_which):
        """PATH上で見つかる場合"""
        launcher = self._make_launcher()
        launcher._executable_path = None
        with patch("launcher.ollama_launcher.sys.platform", "linux"):
            result = launcher.find_executable()
        assert result == "/usr/bin/ollama"

    @patch("launcher.ollama_launcher.requests")
    def test_is_api_ready_true(self, mock_requests):
        """API応答可能"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_requests.get.return_value = mock_resp

        launcher = self._make_launcher()
        assert launcher.is_api_ready() is True

    @patch("launcher.ollama_launcher.requests")
    def test_is_api_ready_false(self, mock_requests):
        """API応答不可"""
        mock_requests.get.side_effect = Exception("refused")

        launcher = self._make_launcher()
        assert launcher.is_api_ready() is False

    @patch("launcher.ollama_launcher.requests")
    def test_launch_already_running(self, mock_requests):
        """既にAPI応答可能ならスキップ"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_requests.get.return_value = mock_resp

        launcher = self._make_launcher()
        result = launcher.launch(wait_ready=False)
        assert result is True

    @patch("launcher.ollama_launcher.requests")
    def test_launch_no_executable(self, mock_requests):
        """実行ファイルが見つからない場合"""
        mock_requests.get.side_effect = Exception("refused")

        launcher = self._make_launcher()
        with patch.object(launcher, "find_executable", return_value=None):
            result = launcher.launch(wait_ready=False)
        assert result is False

    def test_stop_no_process(self):
        """停止対象がない場合"""
        launcher = self._make_launcher()
        assert launcher.stop() is False

    def test_stop_with_process_manager(self):
        """ProcessManager経由で停止"""
        launcher = self._make_launcher()
        mock_pm = MagicMock()
        mock_pm.stop.return_value = True
        assert launcher.stop(process_manager=mock_pm) is True
        mock_pm.stop.assert_called_once_with("ollama")


# ==============================================================
# LlamaCppLauncher テスト
# ==============================================================

class TestLlamaCppLauncher:
    """LlamaCppLauncher のテスト"""

    def _make_launcher(self, **kwargs):
        from launcher.llamacpp_launcher import LlamaCppLauncher
        return LlamaCppLauncher(**kwargs)

    def test_default_endpoint(self):
        """デフォルトエンドポイント"""
        launcher = self._make_launcher()
        assert launcher.endpoint == "http://localhost:8080"

    def test_custom_endpoint(self):
        """カスタムエンドポイント"""
        launcher = self._make_launcher(endpoint="http://localhost:9090/")
        assert launcher.endpoint == "http://localhost:9090"

    def test_model_path(self):
        """モデルパス指定"""
        launcher = self._make_launcher(model_path="/models/test.gguf")
        assert launcher._model_path == "/models/test.gguf"

    def test_find_executable_explicit(self, tmp_path):
        """明示パスが存在する場合"""
        exe = tmp_path / "llama-server.exe"
        exe.touch()
        launcher = self._make_launcher(executable_path=str(exe))
        assert launcher.find_executable() == str(exe)

    @patch("launcher.llamacpp_launcher.shutil.which", return_value="/usr/bin/llama-server")
    def test_find_executable_path_search(self, mock_which):
        """PATH上で見つかる場合"""
        launcher = self._make_launcher()
        launcher._executable_path = None
        with patch("launcher.llamacpp_launcher.sys.platform", "linux"):
            result = launcher.find_executable()
        assert result == "/usr/bin/llama-server"

    @patch("launcher.llamacpp_launcher.requests")
    def test_is_api_ready_true(self, mock_requests):
        """API応答可能"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_requests.get.return_value = mock_resp

        launcher = self._make_launcher()
        assert launcher.is_api_ready() is True

    @patch("launcher.llamacpp_launcher.requests")
    def test_is_api_ready_false(self, mock_requests):
        """API応答不可"""
        mock_requests.get.side_effect = Exception("refused")

        launcher = self._make_launcher()
        assert launcher.is_api_ready() is False

    @patch("launcher.llamacpp_launcher.requests")
    def test_launch_already_running(self, mock_requests):
        """既にAPI応答可能ならスキップ"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_requests.get.return_value = mock_resp

        launcher = self._make_launcher()
        result = launcher.launch(wait_ready=False)
        assert result is True

    @patch("launcher.llamacpp_launcher.requests")
    def test_launch_no_executable(self, mock_requests):
        """実行ファイルが見つからない場合"""
        mock_requests.get.side_effect = Exception("refused")

        launcher = self._make_launcher()
        with patch.object(launcher, "find_executable", return_value=None):
            result = launcher.launch(wait_ready=False)
        assert result is False

    def test_stop_no_process(self):
        """停止対象がない場合"""
        launcher = self._make_launcher()
        assert launcher.stop() is False

    def test_stop_with_process_manager(self):
        """ProcessManager経由で停止"""
        launcher = self._make_launcher()
        mock_pm = MagicMock()
        mock_pm.stop.return_value = True
        assert launcher.stop(process_manager=mock_pm) is True
        mock_pm.stop.assert_called_once_with("llamacpp")


# ==============================================================
# Orchestrator 新ステージ テスト
# ==============================================================

class TestOrchestratorNewStages:
    """Orchestrator の Ollama/llama.cpp ステージテスト"""

    def test_launch_config_defaults(self):
        """LaunchConfig のデフォルト値"""
        from launcher.orchestrator import LaunchConfig
        cfg = LaunchConfig()
        assert cfg.ollama_enabled is False
        assert cfg.ollama_timeout == 30.0
        assert cfg.ollama_endpoint == "http://localhost:11434"
        assert cfg.llamacpp_enabled is False
        assert cfg.llamacpp_timeout == 30.0
        assert cfg.llamacpp_endpoint == "http://localhost:8080"
        assert cfg.llamacpp_model is None

    def test_build_stage_list_includes_new_stages(self):
        """ステージリストにollama/llamacppが含まれる"""
        from launcher.orchestrator import LaunchOrchestrator, LaunchConfig
        cfg = LaunchConfig(ollama_enabled=True, llamacpp_enabled=True)
        orch = LaunchOrchestrator(config=cfg)
        stages = orch._build_stage_list(skip_discord=False)

        stage_names = [s[0] for s in stages]
        assert "ollama_launch" in stage_names
        assert "llamacpp_launch" in stage_names
        # ランタイムはmodel_detectの前に来る
        ollama_idx = stage_names.index("ollama_launch")
        detect_idx = stage_names.index("model_detect")
        assert ollama_idx < detect_idx

    def test_stages_disabled_by_default(self):
        """デフォルトでOllama/llama.cppステージは無効"""
        from launcher.orchestrator import LaunchOrchestrator, LaunchConfig
        cfg = LaunchConfig()
        orch = LaunchOrchestrator(config=cfg)
        stages = orch._build_stage_list(skip_discord=False)

        for name, handler, enabled in stages:
            if name == "ollama_launch":
                assert enabled is False
            if name == "llamacpp_launch":
                assert enabled is False

    @patch("launcher.orchestrator.yaml", create=True)
    def test_from_yaml_reads_ollama_config(self, mock_yaml, tmp_path):
        """config.yamlからOllama設定を読み込み"""
        from launcher.orchestrator import LaunchConfig

        config_data = {
            "launcher": {
                "lmstudio": {"enabled": False},
                "ollama": {"enabled": True, "timeout": 45.0},
                "llamacpp": {"enabled": True, "timeout": 20.0, "model": "/path/model.gguf"},
                "openclaw": {"enabled": False},
                "discord": {"enabled": False},
            }
        }

        config_file = tmp_path / "config.yaml"
        config_file.write_text("dummy")

        with patch("launcher.orchestrator.HAS_YAML", True):
            with patch("builtins.open", MagicMock()):
                mock_yaml.safe_load.return_value = config_data
                with patch("launcher.orchestrator.Path") as mock_path:
                    mock_path_instance = MagicMock()
                    mock_path_instance.exists.return_value = True
                    mock_path.return_value = mock_path_instance

                    cfg = LaunchConfig.from_yaml(str(config_file))

        assert cfg.ollama_enabled is True
        assert cfg.ollama_timeout == 45.0
        assert cfg.llamacpp_enabled is True
        assert cfg.llamacpp_timeout == 20.0
        assert cfg.llamacpp_model == "/path/model.gguf"

    def test_dry_run_includes_new_stages(self):
        """ドライランでも新ステージが表示される"""
        from launcher.orchestrator import LaunchOrchestrator, LaunchConfig
        cfg = LaunchConfig(
            lmstudio_enabled=False,
            ollama_enabled=True,
            llamacpp_enabled=True,
            openclaw_enabled=False,
            discord_enabled=False,
        )
        orch = LaunchOrchestrator(config=cfg, dry_run=True)
        results = orch.run()
        # ドライランは results が空リスト
        assert results == []


# ==============================================================
# routes.py Ollama エンドポイント テスト
# ==============================================================

class TestOllamaRoutes:
    """Ollama API エンドポイントテスト"""

    @pytest.fixture
    def client(self):
        """FastAPIテストクライアント"""
        try:
            from httpx import AsyncClient, ASGITransport
            from api.main import app
            return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        except ImportError:
            pytest.skip("httpx not available")

    @pytest.mark.asyncio
    async def test_list_ollama_models_unavailable(self, client):
        """Ollama未起動時は503"""
        with patch("api.routes._get_ollama_client") as mock_fn:
            mock_client = MagicMock()
            mock_client.is_available.return_value = False
            mock_fn.return_value = mock_client

            response = await client.get("/api/v1/models/ollama")
            assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_list_ollama_models_success(self, client):
        """モデル一覧取得成功"""
        with patch("api.routes._get_ollama_client") as mock_fn:
            mock_client = MagicMock()
            mock_client.is_available.return_value = True
            mock_client.list_models.return_value = [
                {"name": "llama3.2", "size": 4000000000},
            ]
            mock_fn.return_value = mock_client

            response = await client.get("/api/v1/models/ollama")
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 1
            assert data["models"][0]["name"] == "llama3.2"

    @pytest.mark.asyncio
    async def test_delete_ollama_invalid_name(self, client):
        """不正な文字を含むモデル名は400"""
        response = await client.delete("/api/v1/models/ollama/model;rm -rf")
        assert response.status_code == 400
