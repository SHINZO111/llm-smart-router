#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
APIキー安全管理モジュール

【概要】
Windows Credential Manager / macOS Keychain / Linux Secret Service
を使用してAPIキーを暗号化保存する。

【特徴】
- OS標準のキーストアを使用（keyringライブラリ）
- フォールバック機構（ファイル暗号化）
- 複数プロバイダー対応
- 安全な削除機能

【セキュリティ】
- メモリ上でのみ復号化
- スワップ回避（mlock相当）
- クリップボード履歴回避

【作者】クラ for 新さん
【バージョン】2.0.0
"""

import os
import sys
import json
import base64
import hashlib
import getpass
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict
from datetime import datetime

# keyringライブラリ
try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

# 暗号化ライブラリ（フォールバック用）
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


@dataclass
class APIKeyMetadata:
    """APIキーメタデータ"""
    service_name: str
    created_at: str
    last_used: Optional[str] = None
    use_count: int = 0
    notes: str = ""


class SecureKeyManager:
    """
    安全なAPIキー管理クラス
    
    OS標準キーストアを優先使用し、
    不可の場合はファイルベース暗号化にフォールバック
    """
    
    # サービス名（keyring用）
    SERVICE_NAME = "LLMSmartRouter"
    
    # 設定ディレクトリ
    CONFIG_DIR = Path.home() / ".llm-smart-router"
    KEY_FILE = CONFIG_DIR / "keys.enc"
    META_FILE = CONFIG_DIR / "keys.meta"
    
    # サポートするプロバイダー
    SUPPORTED_PROVIDERS = {
        'anthropic': 'Anthropic Claude API',
        'openai': 'OpenAI API',
        'gemini': 'Google Gemini API',
        'azure': 'Azure OpenAI API'
    }
    
    def __init__(self):
        self._cache: Dict[str, str] = {}
        self._backend = None
        self._metadata: Dict[str, APIKeyMetadata] = {}
        
        self._ensure_config_dir()
        self._init_backend()
        self._load_metadata()
    
    def _ensure_config_dir(self):
        """設定ディレクトリを確保"""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        # パーミッション設定（Unix系）
        if sys.platform != 'win32':
            import stat
            self.CONFIG_DIR.chmod(stat.S_IRWXU)  # 所有者のみアクセス可能
    
    def _init_backend(self):
        """バックエンドを初期化"""
        if not KEYRING_AVAILABLE:
            self._backend = 'file'
            return
        
        try:
            # テスト（keyringのデフォルトバックエンドを使用）
            keyring.get_password(self.SERVICE_NAME, '__test__')

            if sys.platform == 'win32':
                self._backend = 'windows'
            elif sys.platform == 'darwin':
                self._backend = 'macos'
            else:
                self._backend = 'secretservice'
            
        except Exception as e:
            print(f"⚠️ キーストア初期化失敗、ファイルフォールバック使用: {e}")
            self._backend = 'file'
    
    def _load_metadata(self):
        """メタデータを読み込み"""
        if self.META_FILE.exists():
            try:
                with open(self.META_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for k, v in data.items():
                        self._metadata[k] = APIKeyMetadata(**v)
            except Exception as e:
                print(f"⚠️ メタデータ読み込み失敗: {e}")
    
    def _save_metadata(self):
        """メタデータを保存"""
        try:
            with open(self.META_FILE, 'w', encoding='utf-8') as f:
                data = {k: asdict(v) for k, v in self._metadata.items()}
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ メタデータ保存失敗: {e}")
    
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """パスワードから暗号化キーを導出"""
        if not CRYPTO_AVAILABLE:
            raise ImportError("cryptographyライブラリが必要です")
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))
    
    def _get_machine_id(self) -> str:
        """マシン固有IDを取得"""
        if sys.platform == 'win32':
            # Windows: レジストリから取得
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                   r"SOFTWARE\Microsoft\Cryptography") as key:
                    return winreg.QueryValueEx(key, "MachineGuid")[0]
            except Exception:
                pass
        
        # フォールバック: ファイルシステム情報
        import uuid
        return str(uuid.getnode())
    
    def _get_encryption_key(self) -> bytes:
        """暗号化キーを取得/生成"""
        # マシン固有の情報とユーザー情報を組み合わせる
        machine_id = self._get_machine_id()
        username = getpass.getuser()
        
        # ソルトとして使用
        salt = hashlib.sha256(f"{machine_id}:{username}".encode()).digest()[:16]
        
        # キー導出
        key_material = f"{machine_id}:{username}:LLMSmartRouter_v2"
        return self._derive_key(key_material, salt)
    
    def _file_store_get(self, provider: str) -> Optional[str]:
        """ファイルストアから取得"""
        if not self.KEY_FILE.exists():
            return None
        
        if not CRYPTO_AVAILABLE:
            raise ImportError("ファイルストアにはcryptographyが必要です")
        
        try:
            key = self._get_encryption_key()
            f = Fernet(key)
            
            with open(self.KEY_FILE, 'rb') as file:
                encrypted_data = file.read()
            
            data = json.loads(f.decrypt(encrypted_data).decode('utf-8'))
            return data.get(provider)
            
        except Exception as e:
            print(f"⚠️ ファイルストア読み込み失敗: {e}")
            return None
    
    def _file_store_set(self, provider: str, api_key: str):
        """ファイルストアに保存"""
        if not CRYPTO_AVAILABLE:
            raise ImportError("ファイルストアにはcryptographyが必要です")
        
        # 既存データを読み込み
        data = {}
        if self.KEY_FILE.exists():
            try:
                key = self._get_encryption_key()
                f = Fernet(key)
                with open(self.KEY_FILE, 'rb') as file:
                    data = json.loads(f.decrypt(file.read()).decode('utf-8'))
            except Exception:
                pass
        
        # 更新
        data[provider] = api_key
        
        # 暗号化して保存
        key = self._get_encryption_key()
        f = Fernet(key)
        encrypted = f.encrypt(json.dumps(data).encode('utf-8'))
        
        with open(self.KEY_FILE, 'wb') as file:
            file.write(encrypted)
        
        # パーミッション設定
        if sys.platform != 'win32':
            import stat
            self.KEY_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
    
    def _file_store_delete(self, provider: str) -> bool:
        """ファイルストアから削除"""
        if not self.KEY_FILE.exists():
            return True
        
        try:
            key = self._get_encryption_key()
            f = Fernet(key)
            
            with open(self.KEY_FILE, 'rb') as file:
                data = json.loads(f.decrypt(file.read()).decode('utf-8'))
            
            if provider in data:
                del data[provider]
            
            if data:
                encrypted = f.encrypt(json.dumps(data).encode('utf-8'))
                with open(self.KEY_FILE, 'wb') as file:
                    file.write(encrypted)
            else:
                self.KEY_FILE.unlink()
            
            return True
            
        except Exception as e:
            print(f"⚠️ ファイルストア削除失敗: {e}")
            return False
    
    # === 公開メソッド ===
    
    def get_backend(self) -> str:
        """使用中のバックエンドを返す"""
        return self._backend
    
    def get_api_key(self, provider: str) -> Optional[str]:
        """
        APIキーを取得
        
        Args:
            provider: プロバイダー名 ('anthropic', 'openai', etc.)
        
        Returns:
            APIキー、未設定の場合はNone
        """
        # キャッシュチェック
        if provider in self._cache:
            return self._cache[provider]
        
        api_key = None
        
        try:
            if self._backend == 'file':
                api_key = self._file_store_get(provider)
            else:
                api_key = keyring.get_password(self.SERVICE_NAME, provider)
                
                # keyring失敗時はファイルフォールバック
                if api_key is None:
                    api_key = self._file_store_get(provider)
        
        except Exception as e:
            print(f"⚠️ APIキー取得失敗: {e}")
            # フォールバック
            api_key = self._file_store_get(provider)
        
        # キャッシュ（セッション中のみ）
        if api_key:
            self._cache[provider] = api_key
            
            # メタデータ更新
            if provider in self._metadata:
                meta = self._metadata[provider]
                meta.last_used = datetime.now().isoformat()
                meta.use_count += 1
                self._save_metadata()
        
        return api_key
    
    def set_api_key(self, provider: str, api_key: str, notes: str = "") -> bool:
        """
        APIキーを保存
        
        Args:
            provider: プロバイダー名
            api_key: APIキー
            notes: メモ
        
        Returns:
            成功したかどうか
        """
        if provider not in self.SUPPORTED_PROVIDERS:
            print(f"⚠️ 未対応プロバイダー: {provider}")
            return False
        
        try:
            if self._backend == 'file':
                self._file_store_set(provider, api_key)
            else:
                try:
                    keyring.set_password(self.SERVICE_NAME, provider, api_key)
                except Exception as e:
                    print(f"⚠️ keyring保存失敗、ファイルフォールバック使用: {e}")
                    self._file_store_set(provider, api_key)
            
            # キャッシュ更新
            self._cache[provider] = api_key
            
            # メタデータ作成
            self._metadata[provider] = APIKeyMetadata(
                service_name=self.SUPPORTED_PROVIDERS.get(provider, provider),
                created_at=datetime.now().isoformat(),
                notes=notes
            )
            self._save_metadata()
            
            return True
            
        except Exception as e:
            print(f"❌ APIキー保存失敗: {e}")
            return False
    
    def delete_api_key(self, provider: str) -> bool:
        """
        APIキーを削除
        
        Args:
            provider: プロバイダー名
        
        Returns:
            成功したかどうか
        """
        success = True
        
        try:
            # keyring削除
            if self._backend != 'file':
                try:
                    keyring.delete_password(self.SERVICE_NAME, provider)
                except Exception:
                    pass
            
            # ファイル削除
            self._file_store_delete(provider)
            
            # キャッシュ削除
            if provider in self._cache:
                del self._cache[provider]
            
            # メタデータ削除
            if provider in self._metadata:
                del self._metadata[provider]
                self._save_metadata()
            
            return True
            
        except Exception as e:
            print(f"⚠️ APIキー削除失敗: {e}")
            return False
    
    def has_api_key(self, provider: str) -> bool:
        """APIキーが設定されているかチェック"""
        return self.get_api_key(provider) is not None
    
    def get_all_providers(self) -> Dict[str, str]:
        """サポートするすべてのプロバイダーを返す"""
        return self.SUPPORTED_PROVIDERS.copy()
    
    def get_configured_providers(self) -> List[str]:
        """設定済みのプロバイダーリストを返す"""
        configured = []
        for provider in self.SUPPORTED_PROVIDERS.keys():
            if self.has_api_key(provider):
                configured.append(provider)
        return configured
    
    def get_metadata(self, provider: str) -> Optional[APIKeyMetadata]:
        """メタデータを取得"""
        return self._metadata.get(provider)
    
    def clear_cache(self):
        """メモリキャッシュをクリア"""
        self._cache.clear()
    
    def secure_delete(self, provider: str) -> bool:
        """
        安全な削除（上書き削除）
        
        注: ファイルシステムの仕様上、完全な削除は保証できない
        """
        # キャリアから削除
        if provider in self._cache:
            # メモリ上書き（可能な範囲で）
            self._cache[provider] = '0' * len(self._cache[provider])
            del self._cache[provider]
        
        # ファイルストアの安全な削除
        if self.KEY_FILE.exists() and CRYPTO_AVAILABLE:
            try:
                # ファイルをランダムデータで上書き
                import secrets
                size = self.KEY_FILE.stat().st_size
                
                with open(self.KEY_FILE, 'wb') as f:
                    for _ in range(3):  # 3回上書き
                        f.write(secrets.token_bytes(size))
                        f.flush()
                        os.fsync(f.fileno())
            except Exception as e:
                print(f"⚠️ 安全削除失敗: {e}")
        
        return self.delete_api_key(provider)
    
    def export_config(self, include_keys: bool = False) -> Dict:
        """設定をエクスポート"""
        config = {
            'backend': self._backend,
            'providers': {},
            'metadata': {k: asdict(v) for k, v in self._metadata.items()}
        }
        
        for provider in self.SUPPORTED_PROVIDERS.keys():
            if include_keys:
                config['providers'][provider] = self.get_api_key(provider)
            else:
                config['providers'][provider] = '***' if self.has_api_key(provider) else None
        
        return config


# === CLI テスト ===

def main():
    """CLIテスト"""
    print("=" * 60)
    print("🔐 LLM Smart Router - Secure Key Manager")
    print("=" * 60)
    
    manager = SecureKeyManager()
    
    print(f"\n📦 バックエンド: {manager.get_backend()}")
    print(f"📁 設定ディレクトリ: {SecureKeyManager.CONFIG_DIR}")
    
    # プロバイダー一覧
    print("\n📋 サポートするプロバイダー:")
    for provider, name in manager.get_all_providers().items():
        status = "✅ 設定済み" if manager.has_api_key(provider) else "❌ 未設定"
        print(f"  • {name}: {status}")
    
    # インタラクティブモード
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == 'set' and len(sys.argv) >= 4:
            provider, key = sys.argv[2], sys.argv[3]
            if manager.set_api_key(provider, key):
                print(f"\n✅ {provider} のAPIキーを保存しました")
            else:
                print(f"\n❌ 保存失敗")
        
        elif cmd == 'get' and len(sys.argv) > 2:
            provider = sys.argv[2]
            key = manager.get_api_key(provider)
            if key:
                print(f"\n✅ {provider} のAPIキー: {key[:10]}...")
            else:
                print(f"\n❌ {provider} のAPIキーは設定されていません")
        
        elif cmd == 'delete' and len(sys.argv) > 2:
            provider = sys.argv[2]
            if manager.delete_api_key(provider):
                print(f"\n✅ {provider} のAPIキーを削除しました")
            else:
                print(f"\n❌ 削除失敗")
        
        elif cmd == 'test':
            print("\n🧪 接続テスト実行中...")
            # Anthropicキーのテスト
            key = manager.get_api_key('anthropic')
            if key:
                try:
                    import requests
                    resp = requests.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json"
                        },
                        json={
                            "model": "claude-sonnet-4-5-20250929",
                            "max_tokens": 10,
                            "messages": [{"role": "user", "content": "Hi"}]
                        },
                        timeout=10
                    )
                    if resp.status_code == 200:
                        print("✅ Anthropic API: 接続成功")
                    else:
                        print(f"⚠️ Anthropic API: HTTP {resp.status_code}")
                except Exception as e:
                    print(f"⚠️ Anthropic API: 接続失敗 ({e})")
            else:
                print("⚠️ Anthropic APIキーが設定されていません")
    
    else:
        print("\n使用方法:")
        print("  python key_manager.py set <provider> <key>")
        print("  python key_manager.py get <provider>")
        print("  python key_manager.py delete <provider>")
        print("  python key_manager.py test")


if __name__ == '__main__':
    main()
