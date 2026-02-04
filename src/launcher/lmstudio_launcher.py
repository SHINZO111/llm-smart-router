"""
LM Studio 自動検出・起動モジュール
実行ファイルの探索、プロセス起動、APIヘルスチェックを行う
"""

import os
import sys
import time
import threading
import logging
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# requestsはオプション
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    requests = None


class LMStudioLauncher:
    """
    LM Studioの自動検出・起動を管理するクラス

    探索順序:
    1. LM_STUDIO_PATH 環境変数
    2. 一般的なインストール先 (%LOCALAPPDATA%, %PROGRAMFILES% 等)
    3. PATH上の検索 (where / which)
    """

    # Windows環境での一般的なインストールパス (%VAR% 形式 → os.path.expandvars で展開)
    WINDOWS_SEARCH_PATHS = [
        "%LOCALAPPDATA%\\LM Studio\\LM Studio.exe",
        "%LOCALAPPDATA%\\Programs\\LM Studio\\LM Studio.exe",
        "%PROGRAMFILES%\\LM Studio\\LM Studio.exe",
        "%PROGRAMFILES(X86)%\\LM Studio\\LM Studio.exe",
        "%USERPROFILE%\\AppData\\Local\\LM Studio\\LM Studio.exe",
    ]

    # macOS/Linux環境での一般的なパス
    UNIX_SEARCH_PATHS = [
        "/Applications/LM Studio.app/Contents/MacOS/LM Studio",
        "$HOME/.local/bin/lm-studio",
        "/usr/local/bin/lm-studio",
    ]

    DEFAULT_ENDPOINT = "http://localhost:1234/v1"

    def __init__(
        self,
        endpoint: Optional[str] = None,
        executable_path: Optional[str] = None,
    ):
        """
        Args:
            endpoint: LM Studio APIエンドポイント
            executable_path: 実行ファイルパス（指定時は探索をスキップ）
        """
        self.endpoint = (endpoint or os.environ.get(
            "LM_STUDIO_ENDPOINT", self.DEFAULT_ENDPOINT
        )).rstrip("/")
        self._executable_path = executable_path
        self._stop_event = threading.Event()
        self._standalone_process = None  # ProcessManager不使用時のPopen参照

    def find_executable(self) -> Optional[str]:
        """
        LM Studio実行ファイルを探索

        Returns:
            実行ファイルのパス。見つからない場合はNone
        """
        # 1. 明示的に指定されたパス
        if self._executable_path:
            path = Path(self._executable_path)
            if path.exists():
                logger.info(f"LM Studio (指定パス): {path}")
                return str(path)
            logger.warning(f"指定パスが見つかりません: {path}")

        # 2. 環境変数 LM_STUDIO_PATH
        env_path = os.environ.get("LM_STUDIO_PATH")
        if env_path:
            path = Path(env_path)
            if path.exists():
                logger.info(f"LM Studio (環境変数): {path}")
                return str(path)
            logger.warning(f"LM_STUDIO_PATH が見つかりません: {env_path}")

        # 3. 一般的なインストール先を探索
        search_paths = self.WINDOWS_SEARCH_PATHS if sys.platform == "win32" else self.UNIX_SEARCH_PATHS

        for pattern in search_paths:
            expanded = os.path.expandvars(pattern)
            if expanded == pattern:
                continue  # 変数が展開されなかった（未設定）
            path = Path(expanded)
            if path.exists():
                logger.info(f"LM Studio (探索): {path}")
                return str(path)

        # 4. PATH上を検索
        exe_name = "LM Studio.exe" if sys.platform == "win32" else "lm-studio"
        found = shutil.which(exe_name)
        if found:
            logger.info(f"LM Studio (PATH): {found}")
            return found

        logger.warning("LM Studio実行ファイルが見つかりません")
        return None

    def is_api_ready(self, timeout: float = 3.0) -> bool:
        """
        LM Studio APIが応答可能かチェック

        Args:
            timeout: 接続タイムアウト（秒）

        Returns:
            APIが応答可能ならTrue
        """
        if not HAS_REQUESTS:
            logger.warning("requestsモジュール未インストール")
            return False

        try:
            response = requests.get(
                f"{self.endpoint}/models",
                timeout=timeout,
            )
            return response.status_code == 200
        except Exception:
            return False

    def is_process_running(self) -> bool:
        """
        LM Studioプロセスが起動中かチェック（APIではなくプロセスレベル）

        Returns:
            プロセスが存在すればTrue
        """
        if sys.platform == "win32":
            try:
                import subprocess
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq LM Studio.exe", "/NH"],
                    capture_output=True, text=True, timeout=5,
                )
                return "LM Studio.exe" in result.stdout
            except Exception:
                return False
        else:
            try:
                import subprocess
                result = subprocess.run(
                    ["pgrep", "-f", "LM Studio"],
                    capture_output=True, timeout=5,
                )
                return result.returncode == 0
            except Exception:
                return False

    def launch(self, process_manager=None, wait_ready: bool = True,
               ready_timeout: float = 60.0, poll_interval: float = 2.0) -> bool:
        """
        LM Studioを起動

        既に起動中（API応答可能）ならスキップする。

        Args:
            process_manager: ProcessManagerインスタンス（None時はsubprocess直接起動）
            wait_ready: API応答可能になるまで待つか
            ready_timeout: API待ちタイムアウト（秒）
            poll_interval: ポーリング間隔（秒）

        Returns:
            起動成功（またはスキップ）ならTrue
        """
        # 既にAPI応答可能ならスキップ
        if self.is_api_ready():
            logger.info("LM Studio APIは既に応答可能です")
            return True

        # 実行ファイルを探索
        exe_path = self.find_executable()
        if not exe_path:
            logger.error("LM Studio実行ファイルが見つかりません")
            return False

        logger.info(f"LM Studio起動中: {exe_path}")

        # ProcessManager経由で起動
        if process_manager:
            success = process_manager.start(
                name="lmstudio",
                command=[exe_path],
                detached=True,
                on_output=lambda name, line: logger.debug(f"[{name}] {line}"),
            )
        else:
            # 直接起動（デタッチモード）
            import subprocess
            try:
                kwargs = {}
                if sys.platform == "win32":
                    kwargs["creationflags"] = (
                        subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                    )
                else:
                    kwargs["start_new_session"] = True

                self._standalone_process = subprocess.Popen(
                    [exe_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    **kwargs,
                )
                success = True
            except Exception as e:
                logger.error(f"LM Studio起動失敗: {e}")
                success = False

        if not success:
            return False

        # API応答を待つ
        if wait_ready:
            return self.wait_for_api(timeout=ready_timeout, poll_interval=poll_interval)

        return True

    def request_stop(self) -> None:
        """待機中のポーリングを中断"""
        self._stop_event.set()

    def wait_for_api(self, timeout: float = 60.0, poll_interval: float = 2.0) -> bool:
        """
        LM Studio APIが応答可能になるまで待機

        threading.Event を使用しており、request_stop() で中断可能。

        Args:
            timeout: 最大待ち時間（秒）
            poll_interval: ポーリング間隔（秒）

        Returns:
            APIが応答可能になればTrue
        """
        self._stop_event.clear()
        start = time.time()
        while time.time() - start < timeout:
            if self.is_api_ready():
                elapsed = time.time() - start
                logger.info(f"LM Studio API応答確認 ({elapsed:.1f}秒)")
                return True
            # Event.wait は signal で中断可能
            if self._stop_event.wait(timeout=poll_interval):
                logger.info("API待機が中断されました")
                return False

        logger.error(f"LM Studio API応答タイムアウト ({timeout}秒)")
        return False
