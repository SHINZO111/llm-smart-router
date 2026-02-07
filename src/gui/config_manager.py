#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
統一設定マネージャー

config.yaml / .env / data/*.json を一元的に読み書きする。
GUIの設定ダイアログはこのクラスを通じて設定を永続化する。
"""

import json
import os
import re
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Any, Optional

import yaml


class ConfigManager:
    """config.yaml / .env / JSON を統一的に読み書きするファサード"""

    def __init__(self, project_root: Optional[Path] = None):
        if project_root is None:
            # src/gui/config_manager.py → src/gui → src → project_root
            project_root = Path(__file__).parent.parent.parent
        self.project_root = Path(project_root)
        self.config_yaml_path = self.project_root / "config.yaml"
        self.env_path = self.project_root / ".env"
        self.fallback_path = self.project_root / "data" / "fallback_priority.json"
        self.registry_path = self.project_root / "data" / "model_registry.json"
        self._config_cache: Optional[dict] = None

    # ────────────────────────────────────────────
    # config.yaml
    # ────────────────────────────────────────────

    def load_yaml(self) -> dict:
        """config.yaml を読み込んで辞書として返す"""
        if not self.config_yaml_path.exists():
            return {}
        with open(self.config_yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self._config_cache = data if isinstance(data, dict) else {}
        return self._config_cache

    def save_yaml(self, config: dict):
        """config.yaml にアトミック書き込み (.bak バックアップ付き)"""
        # バックアップ作成
        if self.config_yaml_path.exists():
            bak = self.config_yaml_path.with_suffix(".yaml.bak")
            shutil.copy2(self.config_yaml_path, bak)

        # アトミック書き込み
        dir_path = self.config_yaml_path.parent
        fd, tmp_path = tempfile.mkstemp(
            suffix=".yaml.tmp", dir=str(dir_path)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                yaml.dump(
                    config, f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                    width=120,
                )
            os.replace(tmp_path, str(self.config_yaml_path))
        except Exception:
            # クリーンアップ
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

        self._config_cache = config

    def get(self, dotted_path: str, default: Any = None) -> Any:
        """ドットパスで値を取得  例: 'routing.intelligent_routing.confidence_threshold'"""
        config = self._config_cache
        if config is None:
            config = self.load_yaml()

        keys = dotted_path.split(".")
        current = config
        for key in keys:
            if not isinstance(current, dict):
                return default
            current = current.get(key)
            if current is None:
                return default
        return current

    def set(self, dotted_path: str, value: Any):
        """ドットパスで値を設定して保存  例: set('default', 'cloud')"""
        config = self._config_cache
        if config is None:
            config = self.load_yaml()

        keys = dotted_path.split(".")
        current = config
        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value

        self.save_yaml(config)

    # ────────────────────────────────────────────
    # .env
    # ────────────────────────────────────────────

    def load_env(self) -> dict:
        """.env ファイルをパースして辞書として返す"""
        result = {}
        if not self.env_path.exists():
            return result
        with open(self.env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)=(.*)$', line)
                if match:
                    key = match.group(1)
                    value = match.group(2).strip().strip('"').strip("'")
                    result[key] = value
        return result

    def set_env(self, key: str, value: str):
        """.env ファイル内の特定キーを更新 (なければ追記)"""
        # キー名バリデーション
        if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', key):
            raise ValueError(f"不正な環境変数名: {key}")

        lines = []
        found = False
        if self.env_path.exists():
            with open(self.env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

        new_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(f"{key}="):
                new_lines.append(f"{key}={value}\n")
                found = True
            else:
                new_lines.append(line)

        if not found:
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines.append("\n")
            new_lines.append(f"{key}={value}\n")

        # アトミック書き込み
        dir_path = self.env_path.parent
        fd, tmp_path = tempfile.mkstemp(suffix=".env.tmp", dir=str(dir_path))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            os.replace(tmp_path, str(self.env_path))
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def get_env(self, key: str, default: str = "") -> str:
        """環境変数を取得 (プロセス環境 > .env ファイル)"""
        # まずプロセス環境を確認
        env_val = os.environ.get(key)
        if env_val is not None:
            return env_val
        # .env ファイルをフォールバック
        return self.load_env().get(key, default)

    # ────────────────────────────────────────────
    # data/fallback_priority.json
    # ────────────────────────────────────────────

    def load_fallback(self) -> list:
        """フォールバック優先順位リストを返す"""
        if not self.fallback_path.exists():
            return ["local", "cloud"]
        try:
            with open(self.fallback_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("priority", ["local", "cloud"])
        except (json.JSONDecodeError, OSError):
            return ["local", "cloud"]

    def save_fallback(self, priority: list):
        """フォールバック優先順位をアトミック書き込み"""
        data = {
            "priority": priority,
            "updated_at": datetime.now().isoformat(),
        }
        self.fallback_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            suffix=".json.tmp", dir=str(self.fallback_path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, str(self.fallback_path))
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    # ────────────────────────────────────────────
    # data/model_registry.json (読み取り専用)
    # ────────────────────────────────────────────

    def load_registry(self) -> dict:
        """モデルレジストリを読み取り専用で返す"""
        if not self.registry_path.exists():
            return {}
        try:
            with open(self.registry_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def get_detected_models(self) -> list:
        """検出済みローカルモデルのリストを返す"""
        registry = self.load_registry()
        models = []
        for runtime_data in registry.get("runtimes", {}).values():
            for model in runtime_data.get("models", []):
                model_id = model.get("id", "")
                if model_id:
                    models.append({
                        "id": model_id,
                        "runtime": runtime_data.get("runtime", "unknown"),
                        "endpoint": runtime_data.get("endpoint", ""),
                    })
        return models

    # ────────────────────────────────────────────
    # ユーティリティ
    # ────────────────────────────────────────────

    def invalidate_cache(self):
        """内部キャッシュをクリア"""
        self._config_cache = None
