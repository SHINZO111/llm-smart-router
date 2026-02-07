"""
Ollama 自動検出・起動モジュール
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

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    requests = None


class OllamaLauncher:
    """
    Ollamaの自動検出・起動を管理するクラス

    探索順序:
    1. OLLAMA_PATH 環境変数
    2. 一般的なインストール先
    3. PATH上の検索 (where / which)
    """

    WINDOWS_SEARCH_PATHS = [
        "%LOCALAPPDATA%\\Programs\\Ollama\\ollama.exe",
        "%LOCALAPPDATA%\\Ollama\\ollama.exe",
        "%PROGRAMFILES%\\Ollama\\ollama.exe",
        "%USERPROFILE%\\AppData\\Local\\Programs\\Ollama\\ollama.exe",
    ]

    UNIX_SEARCH_PATHS = [
        "/usr/local/bin/ollama",
        "/usr/bin/ollama",
        "$HOME/.ollama/bin/ollama",
    ]

    DEFAULT_ENDPOINT = "http://localhost:11434"

    def __init__(
        self,
        endpoint: Optional[str] = None,
        executable_path: Optional[str] = None,
    ):
        self.endpoint = (endpoint or os.environ.get(
            "OLLAMA_ENDPOINT", self.DEFAULT_ENDPOINT
        )).rstrip("/")
        self._executable_path = executable_path
        self._stop_event = threading.Event()
        self._standalone_process = None

    def find_executable(self) -> Optional[str]:
        """Ollama実行ファイルを探索"""
        # 1. 明示的に指定されたパス
        if self._executable_path:
            path = Path(self._executable_path)
            if path.exists():
                logger.info(f"Ollama (指定パス): {path}")
                return str(path)
            logger.warning(f"指定パスが見つかりません: {path}")

        # 2. 環境変数 OLLAMA_PATH
        env_path = os.environ.get("OLLAMA_PATH")
        if env_path:
            path = Path(env_path)
            if path.exists():
                logger.info(f"Ollama (環境変数): {path}")
                return str(path)
            logger.warning(f"OLLAMA_PATH が見つかりません: {env_path}")

        # 3. 一般的なインストール先を探索
        search_paths = self.WINDOWS_SEARCH_PATHS if sys.platform == "win32" else self.UNIX_SEARCH_PATHS

        for pattern in search_paths:
            expanded = os.path.expandvars(pattern)
            if expanded == pattern:
                continue
            path = Path(expanded)
            if path.exists():
                logger.info(f"Ollama (探索): {path}")
                return str(path)

        # 4. PATH上を検索
        exe_name = "ollama.exe" if sys.platform == "win32" else "ollama"
        found = shutil.which(exe_name)
        if found:
            logger.info(f"Ollama (PATH): {found}")
            return found

        logger.warning("Ollama実行ファイルが見つかりません")
        return None

    def is_api_ready(self, timeout: float = 3.0) -> bool:
        """Ollama APIが応答可能かチェック"""
        if not HAS_REQUESTS:
            return False
        try:
            response = requests.get(
                f"{self.endpoint}/api/tags",
                timeout=timeout,
            )
            return response.status_code == 200
        except Exception:
            return False

    def is_process_running(self) -> bool:
        """Ollamaプロセスが起動中かチェック"""
        if sys.platform == "win32":
            try:
                import subprocess
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq ollama.exe", "/NH"],
                    capture_output=True, text=True, timeout=5,
                )
                return "ollama.exe" in result.stdout.lower()
            except Exception:
                return False
        else:
            try:
                import subprocess
                result = subprocess.run(
                    ["pgrep", "-f", "ollama serve"],
                    capture_output=True, timeout=5,
                )
                return result.returncode == 0
            except Exception:
                return False

    def launch(self, process_manager=None, wait_ready: bool = True,
               ready_timeout: float = 30.0, poll_interval: float = 2.0) -> bool:
        """
        Ollamaサーバーを起動

        既に起動中（API応答可能）ならスキップする。

        Args:
            process_manager: ProcessManagerインスタンス
            wait_ready: API応答可能になるまで待つか
            ready_timeout: API待ちタイムアウト（秒）
            poll_interval: ポーリング間隔（秒）

        Returns:
            起動成功（またはスキップ）ならTrue
        """
        if self.is_api_ready():
            logger.info("Ollama APIは既に応答可能です")
            return True

        exe_path = self.find_executable()
        if not exe_path:
            logger.error("Ollama実行ファイルが見つかりません")
            return False

        logger.info(f"Ollama起動中: {exe_path} serve")

        if process_manager:
            success = process_manager.start(
                name="ollama",
                command=[exe_path, "serve"],
                detached=True,
                on_output=lambda name, line: logger.debug(f"[{name}] {line}"),
            )
        else:
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
                    [exe_path, "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    **kwargs,
                )
                success = True
            except Exception as e:
                logger.error(f"Ollama起動失敗: {e}")
                success = False

        if not success:
            return False

        if wait_ready:
            return self.wait_for_api(timeout=ready_timeout, poll_interval=poll_interval)

        return True

    def stop(self, process_manager=None) -> bool:
        """
        Ollamaサーバーを停止

        Args:
            process_manager: ProcessManagerインスタンス

        Returns:
            停止成功ならTrue
        """
        self._stop_event.set()

        if process_manager:
            return process_manager.stop("ollama")

        if self._standalone_process:
            try:
                self._standalone_process.terminate()
                self._standalone_process.wait(timeout=10)
                self._standalone_process = None
                logger.info("Ollamaを停止しました")
                return True
            except Exception as e:
                logger.error(f"Ollama停止失敗: {e}")
                try:
                    self._standalone_process.kill()
                    self._standalone_process = None
                except Exception:
                    pass
                return False

        logger.warning("停止対象のOllamaプロセスがありません")
        return False

    def request_stop(self) -> None:
        """待機中のポーリングを中断"""
        self._stop_event.set()

    def wait_for_api(self, timeout: float = 30.0, poll_interval: float = 2.0) -> bool:
        """Ollama APIが応答可能になるまで待機"""
        self._stop_event.clear()
        start = time.time()
        while time.time() - start < timeout:
            if self.is_api_ready():
                elapsed = time.time() - start
                logger.info(f"Ollama API応答確認 ({elapsed:.1f}秒)")
                return True
            if self._stop_event.wait(timeout=poll_interval):
                logger.info("API待機が中断されました")
                return False

        logger.error(f"Ollama API応答タイムアウト ({timeout}秒)")
        return False
