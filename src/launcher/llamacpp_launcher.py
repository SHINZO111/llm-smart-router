"""
llama.cpp (llama-server) 自動検出・起動モジュール
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


class LlamaCppLauncher:
    """
    llama.cpp サーバー (llama-server) の自動検出・起動を管理するクラス

    探索順序:
    1. LLAMACPP_PATH 環境変数
    2. 一般的なビルド・インストール先
    3. PATH上の検索 (where / which)
    """

    WINDOWS_SEARCH_PATHS = [
        "%LOCALAPPDATA%\\llama.cpp\\llama-server.exe",
        "%PROGRAMFILES%\\llama.cpp\\llama-server.exe",
        "%USERPROFILE%\\llama.cpp\\build\\bin\\Release\\llama-server.exe",
        "%USERPROFILE%\\llama.cpp\\build\\bin\\llama-server.exe",
    ]

    UNIX_SEARCH_PATHS = [
        "/usr/local/bin/llama-server",
        "/usr/bin/llama-server",
        "$HOME/llama.cpp/build/bin/llama-server",
        "$HOME/.local/bin/llama-server",
    ]

    DEFAULT_ENDPOINT = "http://localhost:8080"

    def __init__(
        self,
        endpoint: Optional[str] = None,
        executable_path: Optional[str] = None,
        model_path: Optional[str] = None,
        port: int = 8080,
    ):
        self.endpoint = (endpoint or os.environ.get(
            "LLAMACPP_ENDPOINT", self.DEFAULT_ENDPOINT
        )).rstrip("/")
        self._executable_path = executable_path
        self._model_path = model_path or os.environ.get("LLAMACPP_MODEL")
        self._port = port
        self._stop_event = threading.Event()
        self._standalone_process = None

    def find_executable(self) -> Optional[str]:
        """llama-server実行ファイルを探索"""
        # 1. 明示的に指定されたパス
        if self._executable_path:
            path = Path(self._executable_path)
            if path.exists():
                logger.info(f"llama-server (指定パス): {path}")
                return str(path)
            logger.warning(f"指定パスが見つかりません: {path}")

        # 2. 環境変数 LLAMACPP_PATH
        env_path = os.environ.get("LLAMACPP_PATH")
        if env_path:
            path = Path(env_path)
            if path.exists():
                logger.info(f"llama-server (環境変数): {path}")
                return str(path)
            logger.warning(f"LLAMACPP_PATH が見つかりません: {env_path}")

        # 3. 一般的なインストール先を探索
        search_paths = self.WINDOWS_SEARCH_PATHS if sys.platform == "win32" else self.UNIX_SEARCH_PATHS

        for pattern in search_paths:
            expanded = os.path.expandvars(pattern)
            if expanded == pattern:
                continue
            path = Path(expanded)
            if path.exists():
                logger.info(f"llama-server (探索): {path}")
                return str(path)

        # 4. PATH上を検索
        exe_name = "llama-server.exe" if sys.platform == "win32" else "llama-server"
        found = shutil.which(exe_name)
        if found:
            logger.info(f"llama-server (PATH): {found}")
            return found

        logger.warning("llama-server実行ファイルが見つかりません")
        return None

    def is_api_ready(self, timeout: float = 3.0) -> bool:
        """llama.cpp APIが応答可能かチェック"""
        if not HAS_REQUESTS:
            return False
        try:
            response = requests.get(
                f"{self.endpoint}/v1/models",
                timeout=timeout,
            )
            return response.status_code == 200
        except Exception:
            return False

    def is_process_running(self) -> bool:
        """llama-serverプロセスが起動中かチェック"""
        if sys.platform == "win32":
            try:
                import subprocess
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq llama-server.exe", "/NH"],
                    capture_output=True, text=True, timeout=5,
                )
                return "llama-server.exe" in result.stdout.lower()
            except Exception:
                return False
        else:
            try:
                import subprocess
                result = subprocess.run(
                    ["pgrep", "-f", "llama-server"],
                    capture_output=True, timeout=5,
                )
                return result.returncode == 0
            except Exception:
                return False

    def launch(self, process_manager=None, wait_ready: bool = True,
               ready_timeout: float = 30.0, poll_interval: float = 2.0) -> bool:
        """
        llama-serverを起動

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
            logger.info("llama.cpp APIは既に応答可能です")
            return True

        exe_path = self.find_executable()
        if not exe_path:
            logger.error("llama-server実行ファイルが見つかりません")
            return False

        # コマンド構築
        command = [exe_path, "--host", "0.0.0.0", "--port", str(self._port)]
        if self._model_path:
            model_p = Path(self._model_path)
            if model_p.exists():
                command.extend(["--model", str(model_p)])
            else:
                logger.warning(f"モデルファイルが見つかりません: {self._model_path}")

        logger.info(f"llama-server起動中: {' '.join(command)}")

        if process_manager:
            success = process_manager.start(
                name="llamacpp",
                command=command,
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
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    **kwargs,
                )
                success = True
            except Exception as e:
                logger.error(f"llama-server起動失敗: {e}")
                success = False

        if not success:
            return False

        if wait_ready:
            return self.wait_for_api(timeout=ready_timeout, poll_interval=poll_interval)

        return True

    def stop(self, process_manager=None) -> bool:
        """
        llama-serverを停止

        Args:
            process_manager: ProcessManagerインスタンス

        Returns:
            停止成功ならTrue
        """
        self._stop_event.set()

        if process_manager:
            return process_manager.stop("llamacpp")

        if self._standalone_process:
            try:
                self._standalone_process.terminate()
                self._standalone_process.wait(timeout=10)
                self._standalone_process = None
                logger.info("llama-serverを停止しました")
                return True
            except Exception as e:
                logger.error(f"llama-server停止失敗: {e}")
                try:
                    self._standalone_process.kill()
                    self._standalone_process = None
                except Exception:
                    pass
                return False

        logger.warning("停止対象のllama-serverプロセスがありません")
        return False

    def request_stop(self) -> None:
        """待機中のポーリングを中断"""
        self._stop_event.set()

    def wait_for_api(self, timeout: float = 30.0, poll_interval: float = 2.0) -> bool:
        """llama.cpp APIが応答可能になるまで待機"""
        self._stop_event.clear()
        start = time.time()
        while time.time() - start < timeout:
            if self.is_api_ready():
                elapsed = time.time() - start
                logger.info(f"llama.cpp API応答確認 ({elapsed:.1f}秒)")
                return True
            if self._stop_event.wait(timeout=poll_interval):
                logger.info("API待機が中断されました")
                return False

        logger.error(f"llama.cpp API応答タイムアウト ({timeout}秒)")
        return False
