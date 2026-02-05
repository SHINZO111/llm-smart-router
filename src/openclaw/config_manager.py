"""
OpenClaw設定管理モジュール

OpenClawの設定ファイル（通常は~/.openclaw/config.json）を読み書きし、
LLM設定を自動更新する。
"""

import json
import logging
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class OpenClawConfigManager:
    """
    OpenClaw設定ファイルマネージャー

    Usage:
        manager = OpenClawConfigManager()
        manager.update_llm_endpoint('http://localhost:1234/v1', 'qwen3-4b')
    """

    # OpenClaw設定ファイルの候補パス
    DEFAULT_PATHS = [
        Path.home() / ".openclaw" / "config.json",
        Path.home() / ".config" / "openclaw" / "config.json",
        Path.cwd() / ".openclaw" / "config.json",
    ]

    def __init__(self, config_path: Optional[str] = None):
        """
        Args:
            config_path: OpenClaw設定ファイルのパス（Noneなら自動検出）
        """
        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = self._find_config_file()

        self.config: Optional[Dict[str, Any]] = None
        if self.config_path and self.config_path.exists():
            self.load()

    def _find_config_file(self) -> Optional[Path]:
        """OpenClaw設定ファイルを検索"""
        for path in self.DEFAULT_PATHS:
            if path.exists():
                logger.info(f"OpenClaw設定ファイル検出: {path}")
                return path
        logger.warning("OpenClaw設定ファイルが見つかりません")
        return None

    def exists(self) -> bool:
        """設定ファイルが存在するか"""
        return self.config_path is not None and self.config_path.exists()

    def load(self) -> Dict[str, Any]:
        """設定ファイルを読み込み"""
        if not self.exists():
            raise FileNotFoundError(f"OpenClaw設定ファイルが見つかりません: {self.config_path}")

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            logger.info(f"OpenClaw設定読み込み成功: {self.config_path}")
            return self.config
        except json.JSONDecodeError as e:
            logger.error(f"OpenClaw設定ファイルのJSON解析失敗: {e}")
            raise
        except Exception as e:
            logger.error(f"OpenClaw設定読み込みエラー: {e}")
            raise

    def save(self) -> None:
        """設定ファイルを保存（アトミック書き込み）"""
        if not self.config:
            raise ValueError("保存する設定がありません。先にload()を呼んでください")

        if not self.config_path:
            raise ValueError("設定ファイルパスが指定されていません")

        # 親ディレクトリ作成
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # アトミック書き込み
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=str(self.config_path.parent),
                suffix=".tmp"
            )
            try:
                with open(fd, 'w', encoding='utf-8') as f:
                    json.dump(self.config, f, ensure_ascii=False, indent=2)
                import os
                os.replace(tmp_path, str(self.config_path))
                logger.info(f"OpenClaw設定保存成功: {self.config_path}")
            except BaseException:
                try:
                    import os
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as e:
            logger.error(f"OpenClaw設定保存エラー: {e}")
            raise

    def update_llm_endpoint(self, endpoint: str, model_id: str) -> bool:
        """
        LLMエンドポイントとモデルIDを更新

        Args:
            endpoint: LLMエンドポイント（例: http://localhost:1234/v1）
            model_id: モデルID（例: qwen3-4b）

        Returns:
            更新成功したか
        """
        if not self.config:
            if not self.exists():
                logger.warning("OpenClaw設定ファイルが存在しないため、更新できません")
                return False
            self.load()

        # OpenClaw設定構造を想定（実際の構造に応じて調整）
        # 一般的な構造例:
        # {
        #   "llm": {
        #     "provider": "openai",
        #     "endpoint": "http://localhost:1234/v1",
        #     "model": "qwen3-4b"
        #   }
        # }

        if "llm" not in self.config:
            self.config["llm"] = {}

        self.config["llm"]["endpoint"] = endpoint
        self.config["llm"]["model"] = model_id
        self.config["llm"]["provider"] = "openai"  # OpenAI互換API
        self.config["llm"]["updated_at"] = datetime.now().isoformat()
        self.config["llm"]["updated_by"] = "llm-smart-router"

        try:
            self.save()
            logger.info(f"OpenClaw LLM設定更新: {model_id} @ {endpoint}")
            return True
        except Exception as e:
            logger.error(f"OpenClaw LLM設定更新失敗: {e}")
            return False

    def update_available_models(self, models: List[Dict[str, Any]]) -> bool:
        """
        利用可能なモデル一覧を更新

        Args:
            models: モデル情報のリスト
                [{"id": "qwen3-4b", "endpoint": "http://localhost:1234/v1", ...}, ...]

        Returns:
            更新成功したか
        """
        if not self.config:
            if not self.exists():
                return False
            self.load()

        # OpenClaw設定に利用可能モデルリストを追加
        if "llm" not in self.config:
            self.config["llm"] = {}

        self.config["llm"]["available_models"] = [
            {
                "id": m.get("id"),
                "name": m.get("name", m.get("id")),
                "endpoint": m.get("endpoint"),
                "runtime": m.get("runtime", {}).get("runtime_type") if "runtime" in m else None
            }
            for m in models
        ]
        self.config["llm"]["models_updated_at"] = datetime.now().isoformat()

        try:
            self.save()
            logger.info(f"OpenClaw利用可能モデル更新: {len(models)}モデル")
            return True
        except Exception as e:
            logger.error(f"OpenClaw利用可能モデル更新失敗: {e}")
            return False

    def get_current_llm(self) -> Optional[Dict[str, str]]:
        """現在のLLM設定を取得"""
        if not self.config:
            if not self.exists():
                return None
            self.load()

        llm_config = self.config.get("llm", {})
        return {
            "endpoint": llm_config.get("endpoint"),
            "model": llm_config.get("model"),
            "provider": llm_config.get("provider")
        }

    def create_default_config(self, path: Optional[Path] = None) -> bool:
        """
        デフォルト設定ファイルを作成

        Args:
            path: 作成先パス（Noneなら~/.openclaw/config.json）

        Returns:
            作成成功したか
        """
        if path:
            self.config_path = Path(path)
        elif not self.config_path:
            self.config_path = self.DEFAULT_PATHS[0]

        # デフォルト設定
        self.config = {
            "llm": {
                "provider": "openai",
                "endpoint": "http://localhost:1234/v1",
                "model": "default",
                "available_models": []
            },
            "created_at": datetime.now().isoformat(),
            "created_by": "llm-smart-router"
        }

        try:
            self.save()
            logger.info(f"OpenClawデフォルト設定作成: {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"OpenClawデフォルト設定作成失敗: {e}")
            return False
