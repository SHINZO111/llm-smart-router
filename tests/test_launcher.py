"""
Auto-Launch Chain テスト
process_manager, lmstudio_launcher, orchestrator の単体テスト
"""

import os
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# プロジェクトルートをパスに追加
PROJECT_ROOT = Path(__file__).parent.parent
_src_path = str(PROJECT_ROOT / "src")
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

from launcher.process_manager import ProcessManager, ProcessStatus
from launcher.lmstudio_launcher import LMStudioLauncher
from launcher.orchestrator import (
    LaunchOrchestrator,
    LaunchConfig,
    StageStatus,
    StageResult,
)


# ============================================================
# Platform-dependent command fixtures
# ============================================================


@pytest.fixture
def long_running_cmd():
    """長時間実行コマンド（プラットフォーム依存）"""
    if sys.platform == "win32":
        return ["cmd", "/c", "ping", "localhost", "-n", "30"]
    return ["sleep", "30"]


@pytest.fixture
def echo_cmd():
    """echoコマンド（プラットフォーム依存）"""
    if sys.platform == "win32":
        return ["cmd", "/c", "echo", "hello"]
    return ["echo", "hello"]


@pytest.fixture
def echo_output_cmd():
    """出力コールバックテスト用echoコマンド（プラットフォーム依存）"""
    if sys.platform == "win32":
        return ["cmd", "/c", "echo", "test_output"]
    return ["echo", "test_output"]


# ============================================================
# ProcessManager テスト
# ============================================================


class TestProcessManager:
    """ProcessManager の単体テスト"""

    def test_init(self):
        pm = ProcessManager()
        assert pm.get_all_status() == {}

    def test_start_simple_command(self, echo_cmd):
        """簡単なコマンドの起動テスト"""
        pm = ProcessManager()
        result = pm.start("test_echo", echo_cmd)
        assert result is True
        # プロセスが登録されている
        assert pm.get_status("test_echo") is not None
        # クリーンアップ
        pm.stop("test_echo")

    def test_start_nonexistent_command(self):
        """存在しないコマンドの起動テスト"""
        pm = ProcessManager()
        result = pm.start("bad_cmd", ["__nonexistent_command_12345__"])
        assert result is False
        assert pm.get_status("bad_cmd") == ProcessStatus.FAILED

    def test_start_invalid_command_type(self):
        """不正なコマンド型の起動テスト"""
        pm = ProcessManager()
        result = pm.start("bad_type", "not a list")
        assert result is False

    def test_start_empty_command(self):
        """空コマンドの起動テスト"""
        pm = ProcessManager()
        result = pm.start("empty", [])
        assert result is False

    def test_stop_nonexistent(self):
        """存在しないプロセスの停止テスト"""
        pm = ProcessManager()
        result = pm.stop("nonexistent")
        assert result is True  # 存在しないなら成功扱い

    def test_is_alive(self):
        """生存チェックテスト"""
        pm = ProcessManager()
        assert pm.is_alive("nonexistent") is False

    def test_get_status_nonexistent(self):
        """存在しないプロセスの状態取得"""
        pm = ProcessManager()
        assert pm.get_status("nonexistent") is None

    def test_get_all_status(self):
        """全プロセス状態取得テスト"""
        pm = ProcessManager()
        status = pm.get_all_status()
        assert isinstance(status, dict)
        assert len(status) == 0

    def test_start_and_stop_long_running(self, long_running_cmd):
        """長時間プロセスの起動と停止テスト"""
        pm = ProcessManager()
        result = pm.start("long_proc", long_running_cmd)
        assert result is True
        assert pm.is_alive("long_proc") is True
        assert pm.get_status("long_proc") == ProcessStatus.RUNNING

        result = pm.stop("long_proc", timeout=5.0)
        assert result is True

    def test_stop_all(self, long_running_cmd):
        """全プロセス停止テスト"""
        pm = ProcessManager()
        pm.start("proc1", long_running_cmd)
        pm.start("proc2", long_running_cmd)

        pm.stop_all(timeout=5.0)

        assert pm.is_alive("proc1") is False
        assert pm.is_alive("proc2") is False

    def test_start_duplicate_skips(self, long_running_cmd):
        """既に起動中のプロセスはスキップされる"""
        pm = ProcessManager()
        pm.start("dup", long_running_cmd)
        pid1 = pm.get_pid("dup")

        # 2回目の起動はスキップされる
        result = pm.start("dup", long_running_cmd)
        assert result is True
        pid2 = pm.get_pid("dup")
        assert pid1 == pid2  # 同じPID

        pm.stop("dup")

    def test_context_manager(self, long_running_cmd):
        """コンテキストマネージャーテスト"""
        with ProcessManager() as pm:
            pm.start("ctx_proc", long_running_cmd)
            assert pm.is_alive("ctx_proc") is True

        # with ブロック終了後にプロセスが停止されている
        # (pm のスコープは残るが stop_all が呼ばれた)
        assert pm.is_alive("ctx_proc") is False

    def test_output_callback(self, echo_output_cmd):
        """出力コールバックテスト"""
        pm = ProcessManager()
        lines = []

        def on_output(name, line):
            lines.append((name, line))

        pm.start("echo_test", echo_output_cmd, on_output=on_output)
        time.sleep(1)  # 出力を待つ

        pm.stop("echo_test")
        # コールバックが呼ばれたかチェック
        assert any("test_output" in line for _, line in lines)


# ============================================================
# LMStudioLauncher テスト
# ============================================================


class TestLMStudioLauncher:
    """LMStudioLauncher の単体テスト"""

    def test_init_defaults(self):
        launcher = LMStudioLauncher()
        assert "localhost:1234" in launcher.endpoint

    def test_init_custom_endpoint(self):
        launcher = LMStudioLauncher(endpoint="http://myhost:5555/v1")
        assert launcher.endpoint == "http://myhost:5555/v1"

    def test_init_with_executable_path(self, tmp_path):
        fake_exe = tmp_path / "lmstudio"
        fake_exe.touch()
        launcher = LMStudioLauncher(executable_path=str(fake_exe))
        # find_executable should return the specified path
        assert launcher.find_executable() == str(fake_exe)

    @patch.dict("os.environ", {"LM_STUDIO_PATH": ""}, clear=False)
    def test_find_executable_no_env(self):
        """環境変数なし・パスなしの場合"""
        launcher = LMStudioLauncher()
        # 実際の環境に依存するのでNoneかパスが返る
        result = launcher.find_executable()
        # テスト環境では見つからない可能性が高い
        assert result is None or isinstance(result, str)

    def test_find_executable_explicit_path_exists(self, tmp_path):
        """明示パスが存在する場合"""
        fake_exe = tmp_path / "LM Studio.exe"
        fake_exe.touch()

        launcher = LMStudioLauncher(executable_path=str(fake_exe))
        result = launcher.find_executable()
        assert result == str(fake_exe)

    def test_find_executable_explicit_path_missing(self):
        """明示パスが存在しない場合"""
        launcher = LMStudioLauncher(executable_path="/nonexistent/path/lmstudio.exe")
        # フォールバック探索に進む
        result = launcher.find_executable()
        # 見つからないはず（テスト環境依存）
        assert result is None or isinstance(result, str)

    @patch("launcher.lmstudio_launcher.HAS_REQUESTS", True)
    @patch("launcher.lmstudio_launcher.requests")
    def test_is_api_ready_success(self, mock_requests):
        """API応答チェック: 成功"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response

        launcher = LMStudioLauncher()
        assert launcher.is_api_ready() is True

    @patch("launcher.lmstudio_launcher.HAS_REQUESTS", True)
    @patch("launcher.lmstudio_launcher.requests")
    def test_is_api_ready_failure(self, mock_requests):
        """API応答チェック: 接続失敗"""
        mock_requests.get.side_effect = Exception("Connection refused")

        launcher = LMStudioLauncher()
        assert launcher.is_api_ready() is False

    @patch("launcher.lmstudio_launcher.HAS_REQUESTS", False)
    def test_is_api_ready_no_requests(self):
        """requestsモジュールなし"""
        launcher = LMStudioLauncher()
        assert launcher.is_api_ready() is False

    @patch.object(LMStudioLauncher, "is_api_ready", return_value=True)
    def test_launch_already_running(self, mock_ready):
        """既にAPIが応答可能なら起動をスキップ"""
        launcher = LMStudioLauncher()
        result = launcher.launch()
        assert result is True

    @patch.object(LMStudioLauncher, "is_api_ready", return_value=False)
    @patch.object(LMStudioLauncher, "find_executable", return_value=None)
    def test_launch_no_executable(self, mock_find, mock_ready):
        """実行ファイルが見つからない場合"""
        launcher = LMStudioLauncher()
        result = launcher.launch(wait_ready=False)
        assert result is False


# ============================================================
# LaunchConfig テスト
# ============================================================


class TestLaunchConfig:
    """LaunchConfig の単体テスト"""

    def test_defaults(self):
        config = LaunchConfig()
        assert config.lmstudio_enabled is True
        assert config.discord_enabled is True
        assert config.lmstudio_timeout == 60.0

    def test_from_yaml_missing_file(self, tmp_path):
        """存在しないファイルからの読み込み"""
        config = LaunchConfig.from_yaml(str(tmp_path / "nonexistent.yaml"))
        assert config.lmstudio_enabled is True  # デフォルト値

    def test_from_yaml_with_launcher_section(self, tmp_path):
        """launcherセクション付きYAMLの読み込み"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "launcher:\n"
            "  lmstudio:\n"
            "    enabled: false\n"
            "    timeout: 120.0\n"
            "  discord:\n"
            "    enabled: true\n",
            encoding="utf-8",
        )
        config = LaunchConfig.from_yaml(str(config_file))
        assert config.lmstudio_enabled is False
        assert config.lmstudio_timeout == 120.0
        assert config.discord_enabled is True

    def test_from_yaml_empty_file(self, tmp_path):
        """空ファイルの読み込み"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("", encoding="utf-8")
        config = LaunchConfig.from_yaml(str(config_file))
        assert config.lmstudio_enabled is True  # デフォルト


# ============================================================
# LaunchOrchestrator テスト
# ============================================================


class TestLaunchOrchestrator:
    """LaunchOrchestrator の単体テスト"""

    def test_init(self):
        orch = LaunchOrchestrator()
        assert orch.results == []
        assert orch.dry_run is False

    def test_dry_run(self):
        """ドライランモードのテスト"""
        config = LaunchConfig()
        progress_calls = []

        def on_progress(name, status, msg):
            progress_calls.append((name, status, msg))

        orch = LaunchOrchestrator(
            config=config, on_progress=on_progress, dry_run=True
        )
        results = orch.run()
        # ドライランは結果を返さない（プレビューのみ）
        assert isinstance(results, list)

    def test_build_stage_list(self):
        """ステージリスト構築テスト"""
        config = LaunchConfig(
            lmstudio_enabled=True,
            model_detect_enabled=True,
            openclaw_enabled=False,
            discord_enabled=True,
        )
        orch = LaunchOrchestrator(config=config)
        stages = orch._build_stage_list(skip_discord=False)
        assert len(stages) == 4

        names = [s[0] for s in stages]
        assert names == ["lmstudio_launch", "model_detect", "openclaw", "discord_bot"]

        # openclaw は無効
        assert stages[2][2] is False
        # discord は有効
        assert stages[3][2] is True

    def test_build_stage_list_skip_discord(self):
        """Discord スキップテスト"""
        config = LaunchConfig(discord_enabled=True)
        orch = LaunchOrchestrator(config=config)
        stages = orch._build_stage_list(skip_discord=True)
        # discord_bot は skip_discord=True で無効化
        assert stages[3][2] is False

    def test_run_stage_success(self):
        """ステージ実行: 成功"""
        orch = LaunchOrchestrator()

        def success_handler():
            return True, "テスト成功"

        result = orch._run_stage("test_stage", success_handler)
        assert result.status == StageStatus.SUCCESS
        assert result.message == "テスト成功"
        assert result.elapsed >= 0

    def test_run_stage_failure(self):
        """ステージ実行: 失敗"""
        orch = LaunchOrchestrator()

        def fail_handler():
            return False, "テスト失敗"

        result = orch._run_stage("test_stage", fail_handler)
        assert result.status == StageStatus.FAILED
        assert result.error == "テスト失敗"

    def test_run_stage_exception(self):
        """ステージ実行: 例外"""
        orch = LaunchOrchestrator()

        def error_handler():
            raise RuntimeError("テストエラー")

        result = orch._run_stage("test_stage", error_handler)
        assert result.status == StageStatus.FAILED
        assert "テストエラー" in result.error

    def test_all_stages_disabled(self):
        """全ステージ無効時"""
        config = LaunchConfig(
            lmstudio_enabled=False,
            model_detect_enabled=False,
            openclaw_enabled=False,
            discord_enabled=False,
        )
        orch = LaunchOrchestrator(config=config)
        results = orch.run()
        assert all(r.status == StageStatus.SKIPPED for r in results)

    @patch.object(LaunchOrchestrator, "_stage_lmstudio", return_value=(True, "OK"))
    @patch.object(LaunchOrchestrator, "_stage_model_detect", return_value=(True, "OK"))
    @patch.object(LaunchOrchestrator, "_stage_openclaw", return_value=(True, "OK"))
    def test_run_without_discord(self, mock_oc, mock_md, mock_lm):
        """Discord なしの実行テスト"""
        config = LaunchConfig(discord_enabled=False)
        orch = LaunchOrchestrator(config=config)
        results = orch.run()

        assert len(results) == 4
        assert results[0].status == StageStatus.SUCCESS  # lmstudio
        assert results[1].status == StageStatus.SUCCESS  # model_detect
        assert results[2].status == StageStatus.SUCCESS  # openclaw
        assert results[3].status == StageStatus.SKIPPED  # discord

    def test_shutdown(self):
        """シャットダウンテスト"""
        orch = LaunchOrchestrator()
        # ProcessManagerがまだ初期化されていなければ何もしない
        orch.shutdown()

    def test_progress_callback(self):
        """進捗コールバックテスト"""
        progress_log = []

        def on_progress(name, status, message):
            progress_log.append((name, status, message))

        config = LaunchConfig(
            lmstudio_enabled=False,
            model_detect_enabled=False,
            openclaw_enabled=False,
            discord_enabled=False,
        )
        orch = LaunchOrchestrator(config=config, on_progress=on_progress)
        orch.run()

        # 各ステージで SKIPPED コールバックが呼ばれる
        assert len(progress_log) == 4
        assert all(status == StageStatus.SKIPPED for _, status, _ in progress_log)


# ============================================================
# StageResult テスト
# ============================================================


class TestStageResult:
    """StageResult の単体テスト"""

    def test_creation(self):
        result = StageResult(
            name="test",
            status=StageStatus.SUCCESS,
            elapsed=1.5,
            message="完了",
        )
        assert result.name == "test"
        assert result.status == StageStatus.SUCCESS
        assert result.elapsed == 1.5
        assert result.error is None


# ============================================================
# 統合テスト (モック使用)
# ============================================================


class TestIntegration:
    """モックを使った統合テスト"""

    @patch.object(LMStudioLauncher, "is_api_ready", return_value=True)
    @patch.object(LMStudioLauncher, "launch", return_value=True)
    def test_lmstudio_stage_already_running(self, mock_launch, mock_ready):
        """LM Studio が既に起動中の場合"""
        config = LaunchConfig(
            lmstudio_enabled=True,
            model_detect_enabled=False,
            openclaw_enabled=False,
            discord_enabled=False,
        )
        orch = LaunchOrchestrator(config=config)
        results = orch.run()
        assert results[0].status == StageStatus.SUCCESS

    def test_discord_stage_no_token(self):
        """DISCORD_BOT_TOKEN なしでDiscordステージ実行"""
        config = LaunchConfig(
            lmstudio_enabled=False,
            model_detect_enabled=False,
            openclaw_enabled=False,
            discord_enabled=True,
        )
        # トークンを確実にクリア
        with patch.dict("os.environ", {}, clear=False):
            if "DISCORD_BOT_TOKEN" in os.environ:
                del os.environ["DISCORD_BOT_TOKEN"]
            orch = LaunchOrchestrator(config=config)
            results = orch.run()

        discord_result = results[3]
        assert discord_result.status == StageStatus.FAILED
        assert "DISCORD_BOT_TOKEN" in discord_result.error
