"""
子プロセス管理モジュール
名前付きプロセスレジストリで起動・停止・状態管理を行う
"""

import subprocess
import threading
import logging
import sys
from typing import Dict, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ProcessStatus(Enum):
    """プロセス状態"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    FAILED = "failed"


@dataclass
class ManagedProcess:
    """管理対象プロセスの情報"""
    name: str
    command: list
    process: Optional[subprocess.Popen] = None
    status: ProcessStatus = ProcessStatus.STOPPED
    return_code: Optional[int] = None
    log_thread: Optional[threading.Thread] = None
    cwd: Optional[str] = None
    env: Optional[dict] = None


class ProcessManager:
    """
    名前付き子プロセスレジストリ

    プロセスの起動・停止・状態監視を管理する。
    Windows CREATE_NEW_PROCESS_GROUP 対応。
    """

    def __init__(self):
        self._processes: Dict[str, ManagedProcess] = {}
        self._lock = threading.RLock()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_all()
        return False

    def start(
        self,
        name: str,
        command: list,
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
        on_output: Optional[Callable[[str, str], None]] = None,
        detached: bool = False,
    ) -> bool:
        """
        名前付きプロセスを起動

        Args:
            name: プロセス識別名
            command: コマンドと引数のリスト（文字列のリスト）
            cwd: 作業ディレクトリ
            env: 環境変数（Noneの場合は現在の環境を継承）
            on_output: 出力コールバック (name, line) -> None
            detached: デタッチモードで起動するか

        Returns:
            bool: 起動成功ならTrue
        """
        # コマンドのバリデーション
        if not isinstance(command, list) or not all(isinstance(c, str) for c in command):
            logger.error(f"[{name}] command は文字列のリストである必要があります")
            return False

        if not command:
            logger.error(f"[{name}] command が空です")
            return False

        with self._lock:
            # 既に起動中ならスキップ
            if name in self._processes and self._processes[name].status == ProcessStatus.RUNNING:
                proc = self._processes[name].process
                if proc and proc.poll() is None:
                    logger.info(f"[{name}] 既に起動中 (PID: {proc.pid})")
                    return True

            managed = ManagedProcess(name=name, command=command, cwd=cwd, env=env)
            managed.status = ProcessStatus.STARTING
            self._processes[name] = managed

            try:
                # Windows固有: CREATE_NEW_PROCESS_GROUP でデタッチ
                creation_flags = 0
                if sys.platform == "win32" and detached:
                    creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

                kwargs = {
                    "stdout": subprocess.PIPE if on_output else subprocess.DEVNULL,
                    "stderr": subprocess.STDOUT if on_output else subprocess.DEVNULL,
                    "cwd": cwd,
                    "env": env,
                }
                if sys.platform == "win32":
                    kwargs["creationflags"] = creation_flags
                else:
                    if detached:
                        kwargs["start_new_session"] = True

                proc = subprocess.Popen(command, **kwargs)
                managed.process = proc
                managed.status = ProcessStatus.RUNNING

            except FileNotFoundError:
                logger.error(f"[{name}] コマンドが見つかりません: {command[0]}")
                managed.status = ProcessStatus.FAILED
                return False
            except Exception as e:
                logger.error(f"[{name}] 起動失敗: {e}")
                managed.status = ProcessStatus.FAILED
                return False

        # ロック内で取得したプロセス参照をローカル変数にキャプチャ
        proc = managed.process

        # stdout読み取りスレッド (ロック外で起動 - プロセスは既にRUNNING状態)
        if on_output and proc and proc.stdout:
            log_thread = threading.Thread(
                target=self._read_output,
                args=(name, proc, on_output),
                daemon=True,
            )
            log_thread.start()
            with self._lock:
                managed.log_thread = log_thread

        logger.info(f"[{name}] 起動完了 (PID: {proc.pid})")
        return True

    def stop(self, name: str, timeout: float = 10.0) -> bool:
        """
        名前付きプロセスを停止

        Args:
            name: プロセス識別名
            timeout: 終了待ちタイムアウト（秒）

        Returns:
            bool: 停止成功ならTrue
        """
        with self._lock:
            if name not in self._processes:
                return True
            managed = self._processes[name]
            proc = managed.process

            if proc is None or proc.poll() is not None:
                managed.status = ProcessStatus.STOPPED
                if proc is not None:
                    managed.return_code = proc.returncode
                return True

        # terminate/kill はロック外で実行（ブロック可能なため）
        try:
            logger.info(f"[{name}] 停止中... (PID: {proc.pid})")
            proc.terminate()
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                logger.warning(f"[{name}] terminate タイムアウト、kill を実行")
                proc.kill()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.error(f"[{name}] kill 後もプロセスが終了しません")
                    with self._lock:
                        managed.status = ProcessStatus.FAILED
                    return False

            with self._lock:
                managed.status = ProcessStatus.STOPPED
                managed.return_code = proc.returncode

            logger.info(f"[{name}] 停止完了 (returncode: {proc.returncode})")
            return True

        except Exception as e:
            logger.error(f"[{name}] 停止失敗: {e}")
            with self._lock:
                managed.status = ProcessStatus.FAILED
            return False

    def stop_all(self, timeout: float = 10.0) -> None:
        """全プロセスを停止"""
        with self._lock:
            names = list(self._processes.keys())

        for name in reversed(names):  # 後から起動したものを先に停止
            self.stop(name, timeout=timeout)

    def is_alive(self, name: str) -> bool:
        """プロセスが生存中かチェック"""
        with self._lock:
            if name not in self._processes:
                return False
            managed = self._processes[name]
            proc = managed.process

            if proc is None:
                return False

            alive = proc.poll() is None
            if not alive and managed.status == ProcessStatus.RUNNING:
                managed.status = ProcessStatus.STOPPED
                managed.return_code = proc.returncode
            return alive

    def get_pid(self, name: str) -> Optional[int]:
        """プロセスのPIDを取得"""
        with self._lock:
            if name not in self._processes:
                return None
            proc = self._processes[name].process
            return proc.pid if proc else None

    def get_status(self, name: str) -> Optional[ProcessStatus]:
        """プロセスの状態を取得"""
        # まず生存チェックで状態を更新
        self.is_alive(name)
        with self._lock:
            if name not in self._processes:
                return None
            return self._processes[name].status

    def get_all_status(self) -> Dict[str, ProcessStatus]:
        """全プロセスの状態を取得"""
        with self._lock:
            names = list(self._processes.keys())
        result = {}
        for name in names:
            status = self.get_status(name)
            if status is not None:
                result[name] = status
        return result

    def _read_output(
        self,
        name: str,
        proc: subprocess.Popen,
        callback: Callable[[str, str], None],
    ) -> None:
        """stdoutを読み取ってコールバックに渡すスレッド"""
        try:
            for line in iter(proc.stdout.readline, b""):
                try:
                    text = line.decode("utf-8", errors="replace").rstrip()
                except Exception:
                    text = str(line)
                if text:
                    try:
                        callback(name, text)
                    except Exception as cb_err:
                        logger.warning(f"[{name}] 出力コールバックエラー: {cb_err}")
        except Exception as e:
            logger.debug(f"[{name}] 出力読み取り終了: {e}")
        finally:
            try:
                if proc.stdout and not proc.stdout.closed:
                    proc.stdout.close()
            except OSError:
                pass
