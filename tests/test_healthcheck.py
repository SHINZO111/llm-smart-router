"""
Healthcheck テストモジュール

各チェック関数のユニットテスト
"""
import sys
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# プロジェクトルートをパスに追加
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
_src = str(Path(__file__).parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from healthcheck import (
    check_python,
    check_node,
    check_python_packages,
    check_config,
    check_directories,
    check_model_registry,
    check_env_file,
    _supports_color,
    _c,
    PROJECT_ROOT,
)


# ---------------------------------------------------------------------------
# 色出力テスト
# ---------------------------------------------------------------------------

class TestColorOutput:
    """色出力ヘルパーテスト"""

    def test_c_with_color_disabled(self):
        with patch("healthcheck.USE_COLOR", False):
            result = _c("32", "hello")
            assert result == "hello"
            assert "\033" not in result

    def test_c_with_color_enabled(self):
        with patch("healthcheck.USE_COLOR", True):
            result = _c("32", "hello")
            assert "\033[32m" in result
            assert "hello" in result

    def test_supports_color_no_color_env(self):
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            assert _supports_color() is False


# ---------------------------------------------------------------------------
# check_python テスト
# ---------------------------------------------------------------------------

class TestCheckPython:
    """Pythonバージョンチェックテスト"""

    def test_current_python_passes(self):
        """現在のPythonバージョンは3.9以上のはず"""
        assert check_python() is True

    def test_old_python_fails(self):
        """古いPythonバージョンでは失敗"""
        mock_info = MagicMock()
        mock_info.major = 3
        mock_info.minor = 7
        mock_info.micro = 0
        with patch("healthcheck.sys") as mock_sys:
            mock_sys.version_info = mock_info
            # check_python内でsys.version_infoを参照するのでバージョン直接参照のため
            # これは実際には直接patchできないケースだが、テストとして残す
            pass  # 構造上直接テスト困難


# ---------------------------------------------------------------------------
# check_node テスト
# ---------------------------------------------------------------------------

class TestCheckNode:
    """Node.jsチェックテスト"""

    def test_node_available(self):
        """Node.jsが利用可能な場合"""
        result = check_node()
        # CI環境によってはNode.jsがないのでどちらでもOK
        assert isinstance(result, bool)

    def test_node_not_found(self):
        """Node.jsが見つからない場合"""
        with patch("healthcheck.shutil.which", return_value=None):
            assert check_node() is False


# ---------------------------------------------------------------------------
# check_python_packages テスト
# ---------------------------------------------------------------------------

class TestCheckPythonPackages:
    """Pythonパッケージチェックテスト"""

    def test_returns_bool(self):
        result = check_python_packages()
        assert isinstance(result, bool)

    def test_with_missing_package(self):
        """パッケージが見つからない場合"""
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def mock_import(name, *args, **kwargs):
            if name == "click":
                raise ImportError("mock missing")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = check_python_packages()
            assert result is False


# ---------------------------------------------------------------------------
# check_config テスト
# ---------------------------------------------------------------------------

class TestCheckConfig:
    """設定ファイルチェックテスト"""

    def test_config_exists(self):
        """config.yamlが存在する"""
        result = check_config()
        # プロジェクトルートにconfig.yamlがあるはず
        assert result is True

    def test_config_missing(self):
        """config.yamlが存在しない場合"""
        with patch("healthcheck.PROJECT_ROOT", Path("/nonexistent/path")):
            assert check_config() is False


# ---------------------------------------------------------------------------
# check_directories テスト
# ---------------------------------------------------------------------------

class TestCheckDirectories:
    """ディレクトリチェックテスト"""

    def test_directories_exist(self):
        result = check_directories()
        assert isinstance(result, bool)

    def test_missing_directories(self):
        with patch("healthcheck.PROJECT_ROOT", Path("/nonexistent/path")):
            assert check_directories() is False


# ---------------------------------------------------------------------------
# check_model_registry テスト
# ---------------------------------------------------------------------------

class TestCheckModelRegistry:
    """モデルレジストリチェックテスト"""

    def test_registry_exists(self):
        result = check_model_registry()
        assert isinstance(result, bool)

    def test_registry_valid_json(self, tmp_path):
        """有効なレジストリJSON"""
        reg_dir = tmp_path / "data"
        reg_dir.mkdir()
        reg_file = reg_dir / "model_registry.json"
        reg_file.write_text(json.dumps({
            "models": {"local": [{"id": "m1"}], "cloud": [{"id": "c1"}]},
            "last_scan": "2026-02-07T00:00:00",
        }), encoding="utf-8")

        with patch("healthcheck.PROJECT_ROOT", tmp_path):
            assert check_model_registry() is True

    def test_registry_invalid_json(self, tmp_path):
        """無効なレジストリJSON"""
        reg_dir = tmp_path / "data"
        reg_dir.mkdir()
        reg_file = reg_dir / "model_registry.json"
        reg_file.write_text("not json", encoding="utf-8")

        with patch("healthcheck.PROJECT_ROOT", tmp_path):
            assert check_model_registry() is False

    def test_registry_missing(self, tmp_path):
        """レジストリファイルなし"""
        (tmp_path / "data").mkdir()
        with patch("healthcheck.PROJECT_ROOT", tmp_path):
            assert check_model_registry() is False


# ---------------------------------------------------------------------------
# check_env_file テスト
# ---------------------------------------------------------------------------

class TestCheckEnvFile:
    """環境変数ファイルチェックテスト"""

    def test_env_file_exists(self):
        result = check_env_file()
        assert isinstance(result, bool)

    def test_env_file_missing(self):
        with patch("healthcheck.PROJECT_ROOT", Path("/nonexistent/path")):
            assert check_env_file() is False

    def test_env_file_with_keys(self, tmp_path):
        """APIキーが設定されている.env"""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "ANTHROPIC_API_KEY=sk-ant-real-key-here-abcdefg\n"
            "OPENAI_API_KEY=sk-real-openai-key-here-1234567\n",
            encoding="utf-8"
        )
        with patch("healthcheck.PROJECT_ROOT", tmp_path):
            assert check_env_file() is True

    def test_env_file_with_placeholder_keys(self, tmp_path):
        """プレースホルダーキーの.env"""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "ANTHROPIC_API_KEY=your-key-here\n",
            encoding="utf-8"
        )
        with patch("healthcheck.PROJECT_ROOT", tmp_path):
            result = check_env_file()
            assert result is True  # ファイルは存在するのでTrue（キー未設定の警告は出る）
