"""
Auto-Launch Chain オーケストレーター
ステージごとにヘルスチェック・リトライ・タイムアウト・依存関係を管理する
"""

import os
import sys
import time
import atexit
import signal
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent.parent

# yaml はオプション
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

logger = logging.getLogger(__name__)


class StageStatus(Enum):
    """ステージ実行状態"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


# ステータスアイコンマッピング（サマリー・デフォルト進捗共通）
STATUS_ICONS = {
    StageStatus.PENDING: "...",
    StageStatus.RUNNING: ">>>",
    StageStatus.SUCCESS: "[OK]",
    StageStatus.FAILED: "[NG]",
    StageStatus.SKIPPED: "[--]",
}


@dataclass
class StageResult:
    """ステージ実行結果"""
    name: str
    status: StageStatus
    elapsed: float = 0.0
    message: str = ""
    error: Optional[str] = None


@dataclass
class LaunchConfig:
    """起動チェーン設定"""
    # LM Studio
    lmstudio_enabled: bool = True
    lmstudio_timeout: float = 60.0
    lmstudio_retry: int = 2
    lmstudio_endpoint: str = "http://localhost:1234/v1"
    lmstudio_path: Optional[str] = None

    # モデル検出
    model_detect_enabled: bool = True
    model_detect_timeout: float = 30.0

    # OpenClaw
    openclaw_enabled: bool = True
    openclaw_timeout: float = 15.0

    # Ollama
    ollama_enabled: bool = False
    ollama_timeout: float = 30.0
    ollama_endpoint: str = "http://localhost:11434"
    ollama_path: Optional[str] = None

    # llama.cpp
    llamacpp_enabled: bool = False
    llamacpp_timeout: float = 30.0
    llamacpp_endpoint: str = "http://localhost:8080"
    llamacpp_path: Optional[str] = None
    llamacpp_model: Optional[str] = None

    # Discord Bot
    discord_enabled: bool = True
    discord_timeout: float = 15.0
    discord_bot_path: Optional[str] = None

    @classmethod
    def from_yaml(cls, config_path: Optional[str] = None) -> "LaunchConfig":
        """config.yaml の launcher セクションから設定を読み込む"""
        if config_path is None:
            config_path = str(PROJECT_ROOT / "config.yaml")

        path = Path(config_path)
        if not path.exists() or not HAS_YAML:
            return cls()

        try:
            with open(path, "r", encoding="utf-8") as f:
                full_config = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"config.yaml 読み込みエラー: {e}")
            return cls()

        launcher = full_config.get("launcher", {})
        if not launcher:
            return cls()

        lm = launcher.get("lmstudio", {})
        ol = launcher.get("ollama", {})
        lc = launcher.get("llamacpp", {})
        oc = launcher.get("openclaw", {})
        dc = launcher.get("discord", {})

        return cls(
            lmstudio_enabled=bool(lm.get("enabled", True)),
            lmstudio_timeout=float(lm.get("timeout", 60.0)),
            lmstudio_retry=int(lm.get("retry", 2)),
            lmstudio_endpoint=str(lm.get("endpoint",
                                          os.environ.get("LM_STUDIO_ENDPOINT",
                                                          "http://localhost:1234/v1"))),
            lmstudio_path=lm.get("path") or os.environ.get("LM_STUDIO_PATH"),
            model_detect_enabled=bool(lm.get("model_detect", True)),
            model_detect_timeout=float(lm.get("model_detect_timeout", 30.0)),
            ollama_enabled=bool(ol.get("enabled", False)),
            ollama_timeout=float(ol.get("timeout", 30.0)),
            ollama_endpoint=str(ol.get("endpoint",
                                       os.environ.get("OLLAMA_ENDPOINT",
                                                       "http://localhost:11434"))),
            ollama_path=ol.get("path") or os.environ.get("OLLAMA_PATH"),
            llamacpp_enabled=bool(lc.get("enabled", False)),
            llamacpp_timeout=float(lc.get("timeout", 30.0)),
            llamacpp_endpoint=str(lc.get("endpoint",
                                          os.environ.get("LLAMACPP_ENDPOINT",
                                                          "http://localhost:8080"))),
            llamacpp_path=lc.get("path") or os.environ.get("LLAMACPP_PATH"),
            llamacpp_model=lc.get("model") or os.environ.get("LLAMACPP_MODEL"),
            openclaw_enabled=bool(oc.get("enabled", True)),
            openclaw_timeout=float(oc.get("timeout", 15.0)),
            discord_enabled=bool(dc.get("enabled", True)),
            discord_timeout=float(dc.get("timeout", 15.0)),
            discord_bot_path=dc.get("bot_path"),
        )


class LaunchOrchestrator:
    """
    Auto-Launch Chain オーケストレーター

    ステージ: lmstudio_launch → ollama_launch → llamacpp_launch → model_detect → openclaw → discord_bot
    各ステージにヘルスチェック・リトライ・タイムアウト・依存関係を持つ。
    on_progress コールバックで GUI/CLI 両対応。
    """

    def __init__(
        self,
        config: Optional[LaunchConfig] = None,
        on_progress: Optional[Callable[[str, StageStatus, str], None]] = None,
        dry_run: bool = False,
    ):
        """
        Args:
            config: 起動設定（Noneならconfig.yamlから読み込み）
            on_progress: 進捗コールバック (stage_name, status, message)
            dry_run: Trueならステージを実行せずプレビューのみ
        """
        self.config = config or LaunchConfig.from_yaml()
        self.on_progress = on_progress or self._default_progress
        self.dry_run = dry_run
        self.results: List[StageResult] = []

        # 内部コンポーネント（遅延初期化）
        self._process_manager = None
        self._lmstudio_launcher = None
        self._ollama_launcher = None
        self._llamacpp_launcher = None

        # シャットダウンフック登録
        self._shutdown_registered = False
        self._shutdown_done = False

    @property
    def process_manager(self):
        """ProcessManagerを遅延初期化"""
        if self._process_manager is None:
            from .process_manager import ProcessManager
            self._process_manager = ProcessManager()
        return self._process_manager

    @property
    def lmstudio_launcher(self):
        """LMStudioLauncherを遅延初期化"""
        if self._lmstudio_launcher is None:
            from .lmstudio_launcher import LMStudioLauncher
            self._lmstudio_launcher = LMStudioLauncher(
                endpoint=self.config.lmstudio_endpoint,
                executable_path=self.config.lmstudio_path,
            )
        return self._lmstudio_launcher

    @property
    def ollama_launcher(self):
        """OllamaLauncherを遅延初期化"""
        if self._ollama_launcher is None:
            from .ollama_launcher import OllamaLauncher
            self._ollama_launcher = OllamaLauncher(
                endpoint=self.config.ollama_endpoint,
                executable_path=self.config.ollama_path,
            )
        return self._ollama_launcher

    @property
    def llamacpp_launcher(self):
        """LlamaCppLauncherを遅延初期化"""
        if self._llamacpp_launcher is None:
            from .llamacpp_launcher import LlamaCppLauncher
            self._llamacpp_launcher = LlamaCppLauncher(
                endpoint=self.config.llamacpp_endpoint,
                executable_path=self.config.llamacpp_path,
                model_path=self.config.llamacpp_model,
            )
        return self._llamacpp_launcher

    def run(self, skip_discord: bool = False) -> List[StageResult]:
        """
        起動チェーンを実行

        Args:
            skip_discord: Discord Botステージをスキップするか

        Returns:
            各ステージの実行結果リスト
        """
        self.results = []
        self._register_shutdown()

        stages = self._build_stage_list(skip_discord)

        if self.dry_run:
            logger.info(f"=== ドライラン: {len(stages)}ステージ ===")
            for i, (name, _, enabled) in enumerate(stages, 1):
                status = "有効" if enabled else "スキップ"
                logger.info(f"  {i}. {name} [{status}]")
            return self.results

        logger.info(f"=== Auto-Launch Chain 開始 ({len(stages)}ステージ) ===")

        for name, handler, enabled in stages:
            if not enabled:
                result = StageResult(name=name, status=StageStatus.SKIPPED, message="無効化されています")
                self.results.append(result)
                self._safe_progress(name, StageStatus.SKIPPED, result.message)
                continue

            result = self._run_stage(name, handler)
            self.results.append(result)

            if result.status == StageStatus.FAILED:
                logger.info(f"[{name}] 失敗: {result.error}")
                # 依存関係チェック: LM Studio失敗ならmodel_detectもスキップ
                if name == "lmstudio_launch":
                    logger.info("LM Studio起動失敗のため後続ステージに影響があります")

        self._report_summary()
        return self.results

    def shutdown(self) -> None:
        """グレースフルシャットダウン: 管理プロセスをすべて停止"""
        if self._shutdown_done:
            return
        self._shutdown_done = True
        logger.info("シャットダウン中...")
        if self._process_manager:
            self._process_manager.stop_all(timeout=10.0)
        logger.info("シャットダウン完了")

    def _build_stage_list(self, skip_discord: bool):
        """実行ステージリストを構築"""
        return [
            ("lmstudio_launch", self._stage_lmstudio, self.config.lmstudio_enabled),
            ("ollama_launch", self._stage_ollama, self.config.ollama_enabled),
            ("llamacpp_launch", self._stage_llamacpp, self.config.llamacpp_enabled),
            ("model_detect", self._stage_model_detect, self.config.model_detect_enabled),
            ("openclaw", self._stage_openclaw, self.config.openclaw_enabled),
            ("discord_bot", self._stage_discord, self.config.discord_enabled and not skip_discord),
        ]

    def _safe_progress(self, name: str, status: StageStatus, message: str) -> None:
        """例外セーフな進捗コールバック呼び出し"""
        try:
            self.on_progress(name, status, message)
        except Exception as e:
            logger.warning(f"進捗コールバックエラー [{name}]: {e}")

    def _run_stage(self, name: str, handler: Callable) -> StageResult:
        """ステージを実行してリトライ・タイムアウトを管理"""
        self._safe_progress(name, StageStatus.RUNNING, "実行中...")
        start = time.time()

        try:
            success, message = handler()
            elapsed = time.time() - start

            if success:
                status = StageStatus.SUCCESS
                self._safe_progress(name, status, message)
                return StageResult(name=name, status=status, elapsed=elapsed, message=message)
            else:
                status = StageStatus.FAILED
                self._safe_progress(name, status, message)
                return StageResult(name=name, status=status, elapsed=elapsed, error=message)

        except Exception as e:
            elapsed = time.time() - start
            error_msg = f"例外: {e}"
            self._safe_progress(name, StageStatus.FAILED, error_msg)
            return StageResult(name=name, status=StageStatus.FAILED, elapsed=elapsed, error=error_msg)

    # ================================================================
    # ステージ実装
    # ================================================================

    def _stage_lmstudio(self) -> tuple:
        """LM Studio起動ステージ"""
        launcher = self.lmstudio_launcher
        retry = self.config.lmstudio_retry

        for attempt in range(1, retry + 1):
            logger.info(f"LM Studio起動 (試行 {attempt}/{retry})")

            success = launcher.launch(
                process_manager=self.process_manager,
                wait_ready=True,
                ready_timeout=self.config.lmstudio_timeout,
            )

            if success:
                return True, "LM Studio API応答確認"

            if attempt < retry:
                logger.info("リトライ待機中 (3秒)...")
                time.sleep(3)

        return False, f"LM Studio起動失敗 ({retry}回試行)"

    def _stage_ollama(self) -> tuple:
        """Ollama起動ステージ"""
        launcher = self.ollama_launcher
        logger.info("Ollama起動中...")

        success = launcher.launch(
            process_manager=self.process_manager,
            wait_ready=True,
            ready_timeout=self.config.ollama_timeout,
        )

        if success:
            return True, "Ollama API応答確認"
        return False, "Ollama起動失敗"

    def _stage_llamacpp(self) -> tuple:
        """llama.cpp起動ステージ"""
        launcher = self.llamacpp_launcher
        logger.info("llama.cpp起動中...")

        success = launcher.launch(
            process_manager=self.process_manager,
            wait_ready=True,
            ready_timeout=self.config.llamacpp_timeout,
        )

        if success:
            return True, "llama.cpp API応答確認"
        return False, "llama.cpp起動失敗"

    def _stage_model_detect(self) -> tuple:
        """モデル検出ステージ（マルチランタイム対応）"""
        import asyncio

        src_path = str(PROJECT_ROOT / "src")
        path_added = False
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
            path_added = True
        try:
            from scanner.scanner import MultiRuntimeScanner
            from scanner.registry import ModelRegistry
        except ImportError:
            return False, "scanner モジュールのインポートに失敗"
        finally:
            if path_added and src_path in sys.path:
                sys.path.remove(src_path)

        timeout = self.config.model_detect_timeout
        scanner = MultiRuntimeScanner(timeout=timeout)

        try:
            loop = asyncio.new_event_loop()
            try:
                scan_results = loop.run_until_complete(scanner.scan_all())
            finally:
                loop.close()
        except Exception as e:
            logging.exception("スキャン中に例外発生")
            return False, f"スキャンエラー: {type(e).__name__}"

        registry = ModelRegistry(
            cache_path=str(PROJECT_ROOT / "data" / "model_registry.json")
        )
        registry.update(scan_results)

        total_models = registry.get_total_count()
        runtime_count = len(scan_results)

        if total_models > 0:
            return True, f"{runtime_count}個のランタイムから{total_models}個のモデル検出"
        else:
            return False, "モデルが検出されませんでした"

    def _stage_openclaw(self) -> tuple:
        """OpenClaw接続確認ステージ"""
        openclaw_path = PROJECT_ROOT / "openclaw-integration.js"

        if not openclaw_path.exists():
            return False, "openclaw-integration.js が見つかりません"

        # Node.jsが利用可能か確認
        node_path = shutil.which("node")
        if not node_path:
            return False, "Node.jsが見つかりません"

        # node_modules/axios が存在するか確認
        node_modules = PROJECT_ROOT / "node_modules"
        if not node_modules.exists():
            logger.info("node_modules が見つかりません。npm install を実行してください")
            return False, "node_modules 未インストール"

        # 構文チェック (node --check)
        try:
            result = subprocess.run(
                [node_path, "--check", str(openclaw_path)],
                capture_output=True, text=True,
                timeout=self.config.openclaw_timeout,
                cwd=str(PROJECT_ROOT),
            )
            if result.returncode == 0:
                return True, "OpenClaw統合モジュール検証OK"
            else:
                return False, f"構文エラー: {result.stderr.strip()}"
        except subprocess.TimeoutExpired:
            return False, "OpenClaw検証タイムアウト"
        except Exception as e:
            return False, f"OpenClaw検証エラー: {e}"

    def _stage_discord(self) -> tuple:
        """Discord Bot起動ステージ"""
        token = os.environ.get("DISCORD_BOT_TOKEN")
        if not token:
            return False, "DISCORD_BOT_TOKEN が設定されていません"

        bot_path = self.config.discord_bot_path or str(PROJECT_ROOT / "discord-bot.js")
        if not Path(bot_path).exists():
            return False, f"discord-bot.js が見つかりません: {bot_path}"

        node_path = shutil.which("node")
        if not node_path:
            return False, "Node.jsが見つかりません"

        # Discord Botをバックグラウンドで起動
        success = self.process_manager.start(
            name="discord_bot",
            command=[node_path, bot_path],
            cwd=str(PROJECT_ROOT),
            on_output=lambda name, line: logger.info(f"[{name}] {line}"),
        )

        if success:
            # 少し待ってプロセスが生きているか確認
            time.sleep(2)
            if self.process_manager.is_alive("discord_bot"):
                return True, "Discord Bot起動完了"
            else:
                return False, "Discord Botが起動直後にクラッシュしました"

        return False, "Discord Bot起動失敗"

    # ================================================================
    # ユーティリティ
    # ================================================================

    def _register_shutdown(self) -> None:
        """シャットダウンフックを登録"""
        if self._shutdown_registered:
            return

        atexit.register(self.shutdown)

        def signal_handler(signum, frame):
            logger.info(f"シグナル {signum} 受信")
            self.shutdown()
            sys.exit(128 + signum)

        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except (OSError, ValueError):
            pass  # メインスレッド以外からの呼び出し時

        self._shutdown_registered = True

    def _report_summary(self) -> None:
        """実行結果サマリーを出力"""
        logger.info("=== 実行結果サマリー ===")
        total_time = sum(r.elapsed for r in self.results)

        for r in self.results:
            icon = STATUS_ICONS.get(r.status, "[??]")
            msg = r.message or r.error or ""
            logger.info(f"  {icon} {r.name}: {msg} ({r.elapsed:.1f}秒)")

        success_count = sum(1 for r in self.results if r.status == StageStatus.SUCCESS)
        total_count = len(self.results)
        logger.info(f"合計: {success_count}/{total_count} 成功 ({total_time:.1f}秒)")

    @staticmethod
    def _default_progress(name: str, status: StageStatus, message: str) -> None:
        """デフォルトの進捗コールバック（コンソール出力）"""
        icon = STATUS_ICONS.get(status, "   ")
        print(f"  {icon} {name}: {message}")
