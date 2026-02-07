"""
SecureKeyManager テストモジュール

APIキー管理の暗号化・復号化・メタデータ管理のテスト。
keyring/cryptographyはモック化して外部依存なしで実行。
"""
import sys
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

import pytest

# プロジェクトルートをパスに追加
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
_src = str(Path(__file__).parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from security.key_manager import SecureKeyManager, APIKeyMetadata


# ---------------------------------------------------------------------------
# APIKeyMetadata テスト
# ---------------------------------------------------------------------------

class TestAPIKeyMetadata:
    """APIKeyMetadata データクラスのテスト"""

    def test_creation(self):
        meta = APIKeyMetadata(service_name="Anthropic Claude API", created_at="2026-01-01T00:00:00")
        assert meta.service_name == "Anthropic Claude API"
        assert meta.created_at == "2026-01-01T00:00:00"
        assert meta.last_used is None
        assert meta.use_count == 0
        assert meta.notes == ""

    def test_with_optional_fields(self):
        meta = APIKeyMetadata(
            service_name="Test",
            created_at="2026-01-01",
            last_used="2026-02-01",
            use_count=5,
            notes="test note",
        )
        assert meta.use_count == 5
        assert meta.notes == "test note"


# ---------------------------------------------------------------------------
# SecureKeyManager 初期化テスト
# ---------------------------------------------------------------------------

class TestSecureKeyManagerInit:
    """初期化テスト（モック環境）"""

    @patch("security.key_manager.KEYRING_AVAILABLE", False)
    @patch("security.key_manager.CRYPTO_AVAILABLE", False)
    def test_file_backend_when_no_keyring(self, tmp_path):
        with patch.object(SecureKeyManager, "CONFIG_DIR", tmp_path):
            with patch.object(SecureKeyManager, "META_FILE", tmp_path / "keys.meta"):
                with patch.object(SecureKeyManager, "KEY_FILE", tmp_path / "keys.enc"):
                    mgr = SecureKeyManager()
                    assert mgr.get_backend() == "file"

    def test_supported_providers(self):
        providers = SecureKeyManager.SUPPORTED_PROVIDERS
        assert "anthropic" in providers
        assert "openai" in providers
        assert "gemini" in providers
        assert "azure" in providers

    def test_get_all_providers_returns_copy(self):
        with patch.object(SecureKeyManager, "CONFIG_DIR", Path("/tmp/test_km_copy")):
            with patch.object(SecureKeyManager, "META_FILE", Path("/tmp/test_km_copy/keys.meta")):
                with patch.object(SecureKeyManager, "KEY_FILE", Path("/tmp/test_km_copy/keys.enc")):
                    with patch.object(SecureKeyManager, "_init_backend"):
                        with patch.object(SecureKeyManager, "_load_metadata"):
                            with patch.object(SecureKeyManager, "_ensure_config_dir"):
                                mgr = SecureKeyManager()
                                p1 = mgr.get_all_providers()
                                p2 = mgr.get_all_providers()
                                assert p1 == p2
                                assert p1 is not p2  # コピーである


# ---------------------------------------------------------------------------
# メタデータ永続化テスト
# ---------------------------------------------------------------------------

class TestMetadataPersistence:
    """メタデータの保存・読み込みテスト"""

    def test_save_and_load_metadata(self, tmp_path):
        meta_file = tmp_path / "keys.meta"

        with patch.object(SecureKeyManager, "CONFIG_DIR", tmp_path):
            with patch.object(SecureKeyManager, "META_FILE", meta_file):
                with patch.object(SecureKeyManager, "KEY_FILE", tmp_path / "keys.enc"):
                    with patch.object(SecureKeyManager, "_init_backend"):
                        mgr = SecureKeyManager()
                        mgr._backend = "file"

                        # メタデータ設定
                        mgr._metadata["anthropic"] = APIKeyMetadata(
                            service_name="Anthropic",
                            created_at="2026-01-01",
                            use_count=3,
                        )
                        mgr._save_metadata()

                        # ファイルが作成された
                        assert meta_file.exists()

                        # 新インスタンスで読み込み
                        mgr2 = SecureKeyManager()
                        mgr2._backend = "file"
                        assert "anthropic" in mgr2._metadata
                        assert mgr2._metadata["anthropic"].use_count == 3

    def test_load_metadata_corrupt_file(self, tmp_path):
        meta_file = tmp_path / "keys.meta"
        meta_file.write_text("not json", encoding="utf-8")

        with patch.object(SecureKeyManager, "CONFIG_DIR", tmp_path):
            with patch.object(SecureKeyManager, "META_FILE", meta_file):
                with patch.object(SecureKeyManager, "KEY_FILE", tmp_path / "keys.enc"):
                    with patch.object(SecureKeyManager, "_init_backend"):
                        mgr = SecureKeyManager()
                        mgr._backend = "file"
                        # 壊れたファイルでもエラーにならない
                        assert mgr._metadata == {}

    def test_load_metadata_no_file(self, tmp_path):
        with patch.object(SecureKeyManager, "CONFIG_DIR", tmp_path):
            with patch.object(SecureKeyManager, "META_FILE", tmp_path / "nonexistent.meta"):
                with patch.object(SecureKeyManager, "KEY_FILE", tmp_path / "keys.enc"):
                    with patch.object(SecureKeyManager, "_init_backend"):
                        mgr = SecureKeyManager()
                        assert mgr._metadata == {}

    def test_get_metadata(self, tmp_path):
        with patch.object(SecureKeyManager, "CONFIG_DIR", tmp_path):
            with patch.object(SecureKeyManager, "META_FILE", tmp_path / "k.meta"):
                with patch.object(SecureKeyManager, "KEY_FILE", tmp_path / "k.enc"):
                    with patch.object(SecureKeyManager, "_init_backend"):
                        mgr = SecureKeyManager()
                        mgr._backend = "file"
                        mgr._metadata["openai"] = APIKeyMetadata(
                            service_name="OpenAI", created_at="2026-01-01"
                        )
                        assert mgr.get_metadata("openai") is not None
                        assert mgr.get_metadata("nonexistent") is None


# ---------------------------------------------------------------------------
# キャッシュテスト
# ---------------------------------------------------------------------------

class TestCache:
    """メモリキャッシュのテスト"""

    def _make_manager(self, tmp_path):
        with patch.object(SecureKeyManager, "CONFIG_DIR", tmp_path):
            with patch.object(SecureKeyManager, "META_FILE", tmp_path / "k.meta"):
                with patch.object(SecureKeyManager, "KEY_FILE", tmp_path / "k.enc"):
                    with patch.object(SecureKeyManager, "_init_backend"):
                        mgr = SecureKeyManager()
                        mgr._backend = "file"
                        return mgr

    def test_cache_hit(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        mgr._cache["anthropic"] = "sk-cached-key"
        key = mgr.get_api_key("anthropic")
        assert key == "sk-cached-key"

    def test_clear_cache(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        mgr._cache["anthropic"] = "sk-key"
        mgr.clear_cache()
        assert mgr._cache == {}

    def test_cache_populated_on_get(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        with patch.object(mgr, "_file_store_get", return_value="sk-from-file"):
            key = mgr.get_api_key("anthropic")
            assert key == "sk-from-file"
            assert mgr._cache["anthropic"] == "sk-from-file"


# ---------------------------------------------------------------------------
# set_api_key / delete_api_key テスト
# ---------------------------------------------------------------------------

class TestSetDeleteKey:
    """キー設定・削除テスト"""

    def _make_manager(self, tmp_path):
        with patch.object(SecureKeyManager, "CONFIG_DIR", tmp_path):
            with patch.object(SecureKeyManager, "META_FILE", tmp_path / "k.meta"):
                with patch.object(SecureKeyManager, "KEY_FILE", tmp_path / "k.enc"):
                    with patch.object(SecureKeyManager, "_init_backend"):
                        mgr = SecureKeyManager()
                        mgr._backend = "file"
                        return mgr

    def test_set_unsupported_provider(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        result = mgr.set_api_key("unsupported_provider", "key123")
        assert result is False

    def test_set_key_file_backend(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        with patch.object(mgr, "_file_store_set") as mock_store:
            result = mgr.set_api_key("anthropic", "sk-test-key", notes="test")
            assert result is True
            mock_store.assert_called_once_with("anthropic", "sk-test-key")
            assert mgr._cache["anthropic"] == "sk-test-key"
            assert "anthropic" in mgr._metadata
            assert mgr._metadata["anthropic"].notes == "test"

    def test_delete_key(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        mgr._cache["anthropic"] = "sk-key"
        mgr._metadata["anthropic"] = APIKeyMetadata(
            service_name="Anthropic", created_at="2026-01-01"
        )
        with patch.object(mgr, "_file_store_delete", return_value=True):
            result = mgr.delete_api_key("anthropic")
            assert result is True
            assert "anthropic" not in mgr._cache
            assert "anthropic" not in mgr._metadata

    def test_has_api_key_true(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        mgr._cache["openai"] = "sk-key"
        assert mgr.has_api_key("openai") is True

    def test_has_api_key_false(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        with patch.object(mgr, "_file_store_get", return_value=None):
            assert mgr.has_api_key("openai") is False

    def test_get_configured_providers(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        mgr._cache["anthropic"] = "sk-key1"
        mgr._cache["openai"] = "sk-key2"
        with patch.object(mgr, "_file_store_get", return_value=None):
            configured = mgr.get_configured_providers()
            assert "anthropic" in configured
            assert "openai" in configured
            assert "gemini" not in configured


# ---------------------------------------------------------------------------
# エクスポートテスト
# ---------------------------------------------------------------------------

class TestExportConfig:
    """設定エクスポートテスト"""

    def test_export_without_keys(self, tmp_path):
        with patch.object(SecureKeyManager, "CONFIG_DIR", tmp_path):
            with patch.object(SecureKeyManager, "META_FILE", tmp_path / "k.meta"):
                with patch.object(SecureKeyManager, "KEY_FILE", tmp_path / "k.enc"):
                    with patch.object(SecureKeyManager, "_init_backend"):
                        mgr = SecureKeyManager()
                        mgr._backend = "file"
                        mgr._cache["anthropic"] = "sk-secret"
                        config = mgr.export_config(include_keys=False)

                        assert config["backend"] == "file"
                        assert config["providers"]["anthropic"] == "***"

    def test_export_with_keys(self, tmp_path):
        with patch.object(SecureKeyManager, "CONFIG_DIR", tmp_path):
            with patch.object(SecureKeyManager, "META_FILE", tmp_path / "k.meta"):
                with patch.object(SecureKeyManager, "KEY_FILE", tmp_path / "k.enc"):
                    with patch.object(SecureKeyManager, "_init_backend"):
                        mgr = SecureKeyManager()
                        mgr._backend = "file"
                        mgr._cache["anthropic"] = "sk-secret"
                        config = mgr.export_config(include_keys=True)

                        assert config["providers"]["anthropic"] == "sk-secret"


# ---------------------------------------------------------------------------
# keyring バックエンドテスト
# ---------------------------------------------------------------------------

try:
    import keyring as _keyring_module
    HAS_KEYRING = True
except ImportError:
    HAS_KEYRING = False


@pytest.mark.skipif(not HAS_KEYRING, reason="keyring is not installed")
class TestKeyringBackend:
    """keyringバックエンド使用時のテスト（モック）"""

    @patch("security.key_manager.KEYRING_AVAILABLE", True)
    @patch("security.key_manager.keyring")
    def test_keyring_backend_windows(self, mock_keyring, tmp_path):
        mock_keyring.get_password.return_value = None

        with patch.object(SecureKeyManager, "CONFIG_DIR", tmp_path):
            with patch.object(SecureKeyManager, "META_FILE", tmp_path / "k.meta"):
                with patch.object(SecureKeyManager, "KEY_FILE", tmp_path / "k.enc"):
                    with patch("security.key_manager.sys") as mock_sys:
                        mock_sys.platform = "win32"
                        mgr = SecureKeyManager()
                        assert mgr.get_backend() == "windows"

    @patch("security.key_manager.KEYRING_AVAILABLE", True)
    @patch("security.key_manager.keyring")
    def test_keyring_get_key(self, mock_keyring, tmp_path):
        mock_keyring.get_password.return_value = "sk-from-keyring"

        with patch.object(SecureKeyManager, "CONFIG_DIR", tmp_path):
            with patch.object(SecureKeyManager, "META_FILE", tmp_path / "k.meta"):
                with patch.object(SecureKeyManager, "KEY_FILE", tmp_path / "k.enc"):
                    mgr = SecureKeyManager()
                    # init中のtest呼び出しをリセット
                    mock_keyring.get_password.reset_mock()
                    mock_keyring.get_password.return_value = "sk-from-keyring"
                    key = mgr.get_api_key("anthropic")
                    assert key == "sk-from-keyring"

    @patch("security.key_manager.KEYRING_AVAILABLE", True)
    @patch("security.key_manager.keyring")
    def test_keyring_set_key(self, mock_keyring, tmp_path):
        mock_keyring.get_password.return_value = None

        with patch.object(SecureKeyManager, "CONFIG_DIR", tmp_path):
            with patch.object(SecureKeyManager, "META_FILE", tmp_path / "k.meta"):
                with patch.object(SecureKeyManager, "KEY_FILE", tmp_path / "k.enc"):
                    mgr = SecureKeyManager()
                    result = mgr.set_api_key("anthropic", "sk-new-key")
                    assert result is True
                    mock_keyring.set_password.assert_called_once_with(
                        "LLMSmartRouter", "anthropic", "sk-new-key"
                    )

    @patch("security.key_manager.KEYRING_AVAILABLE", True)
    @patch("security.key_manager.keyring")
    def test_keyring_fallback_on_error(self, mock_keyring, tmp_path):
        # keyringが例外を投げる場合、ファイルフォールバック
        mock_keyring.get_password.side_effect = Exception("keyring error")

        with patch.object(SecureKeyManager, "CONFIG_DIR", tmp_path):
            with patch.object(SecureKeyManager, "META_FILE", tmp_path / "k.meta"):
                with patch.object(SecureKeyManager, "KEY_FILE", tmp_path / "k.enc"):
                    mgr = SecureKeyManager()
                    assert mgr.get_backend() == "file"


# ---------------------------------------------------------------------------
# secure_delete テスト
# ---------------------------------------------------------------------------

class TestSecureDelete:
    """安全な削除テスト"""

    def test_secure_delete_clears_cache(self, tmp_path):
        with patch.object(SecureKeyManager, "CONFIG_DIR", tmp_path):
            with patch.object(SecureKeyManager, "META_FILE", tmp_path / "k.meta"):
                with patch.object(SecureKeyManager, "KEY_FILE", tmp_path / "k.enc"):
                    with patch.object(SecureKeyManager, "_init_backend"):
                        mgr = SecureKeyManager()
                        mgr._backend = "file"
                        mgr._cache["anthropic"] = "sk-secret-key"
                        with patch.object(mgr, "delete_api_key", return_value=True):
                            result = mgr.secure_delete("anthropic")
                            assert result is True
                            assert "anthropic" not in mgr._cache


# ---------------------------------------------------------------------------
# マシンID テスト
# ---------------------------------------------------------------------------

class TestMachineId:
    """マシンID取得テスト"""

    def test_get_machine_id_returns_string(self, tmp_path):
        with patch.object(SecureKeyManager, "CONFIG_DIR", tmp_path):
            with patch.object(SecureKeyManager, "META_FILE", tmp_path / "k.meta"):
                with patch.object(SecureKeyManager, "KEY_FILE", tmp_path / "k.enc"):
                    with patch.object(SecureKeyManager, "_init_backend"):
                        mgr = SecureKeyManager()
                        mgr._backend = "file"
                        mid = mgr._get_machine_id()
                        assert isinstance(mid, str)
                        assert len(mid) > 0
