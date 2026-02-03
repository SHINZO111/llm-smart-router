"""
LM Studio Model Detector
LM StudioのOpenAI互換APIを使って読み込まれているモデルを自動取得するモジュール
"""

import os
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import logging
import json

# requestsはオプション（モックテスト用）
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    requests = None

# yamlはオプション
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    yaml = None

# ロガー設定
logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """モデル情報を表すデータクラス"""
    id: str
    object: str
    created: int
    owned_by: str
    # LM Studio固有の拡張フィールド
    name: Optional[str] = None
    size: Optional[int] = None
    description: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelInfo":
        """OpenAI互換APIレスポンスからModelInfoを生成"""
        return cls(
            id=data.get("id", ""),
            object=data.get("object", "model"),
            created=data.get("created", 0),
            owned_by=data.get("owned_by", "unknown"),
            name=data.get("name"),
            size=data.get("size"),
            description=data.get("description")
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """ModelInfoを辞書に変換"""
        return {
            "id": self.id,
            "object": self.object,
            "created": self.created,
            "owned_by": self.owned_by,
            "name": self.name,
            "size": self.size,
            "description": self.description
        }
    
    def __str__(self) -> str:
        name_str = f" ({self.name})" if self.name else ""
        return f"{self.id}{name_str}"


class LMStudioModelDetector:
    """
    LM Studioのモデルを検出・管理するクラス
    
    OpenAI互換APIを使用して:
    - 読み込まれているモデル一覧の取得
    - デフォルトモデルの決定
    - config.yamlの自動更新
    """
    
    def __init__(self, endpoint: str = "http://localhost:1234/v1"):
        """
        LMStudioModelDetectorを初期化
        
        Args:
            endpoint: LM StudioのOpenAI互換APIエンドポイント
        """
        self.endpoint = endpoint.rstrip("/")
        self.models_endpoint = f"{self.endpoint}/models"
        self.timeout = 5  # 接続チェック用タイムアウト（短め）
        self.request_timeout = 30  # リクエスト用タイムアウト
    
    def is_running(self) -> bool:
        """
        LM Studioが起動しているかチェック
        
        Returns:
            bool: LM Studioに接続できればTrue
        """
        if not HAS_REQUESTS:
            logger.debug("requestsモジュールがインストールされていません")
            return False
            
        try:
            response = requests.get(
                self.models_endpoint,
                timeout=self.timeout
            )
            return response.status_code == 200
        except requests.exceptions.ConnectionError:
            logger.debug(f"LM Studioへの接続失敗: {self.models_endpoint}")
            return False
        except requests.exceptions.Timeout:
            logger.debug(f"LM Studioへの接続タイムアウト: {self.models_endpoint}")
            return False
        except Exception as e:
            logger.debug(f"LM Studio状態確認中にエラー: {e}")
            return False
    
    def get_loaded_models(self) -> List[ModelInfo]:
        """
        読み込み中のモデル一覧を取得
        
        Returns:
            List[ModelInfo]: 読み込まれているモデルのリスト
            
        Raises:
            ConnectionError: LM Studioに接続できない場合
            RuntimeError: APIレスポンスの解析に失敗した場合
        """
        if not HAS_REQUESTS:
            raise ConnectionError(
                "requestsモジュールがインストールされていません。"
                "'pip install requests' でインストールしてください。"
            )
            
        try:
            response = requests.get(
                self.models_endpoint,
                timeout=self.request_timeout
            )
            response.raise_for_status()
            
            data = response.json()
            models_data = data.get("data", [])
            
            models = []
            for model_data in models_data:
                try:
                    model_info = ModelInfo.from_dict(model_data)
                    models.append(model_info)
                except Exception as e:
                    logger.warning(f"モデルデータの解析に失敗: {e}")
                    continue
            
            logger.info(f"{len(models)}個のモデルを検出")
            return models
            
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(
                f"LM Studioに接続できません。LM Studioが起動しているか確認してください: {e}"
            )
        except requests.exceptions.Timeout:
            raise ConnectionError(
                "LM Studioへの接続がタイムアウトしました"
            )
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"LM Studio APIエラー: {e}")
        except (KeyError, TypeError) as e:
            raise RuntimeError(f"APIレスポンスの解析に失敗: {e}")
    
    def get_default_model(self) -> Optional[str]:
        """
        デフォルトモデル名を取得
        
        最初に見つかったモデルのIDを返す。
        モデルが見つからない場合はNoneを返す。
        
        Returns:
            Optional[str]: デフォルトモデル名、またはNone
        """
        try:
            models = self.get_loaded_models()
            if models:
                default = models[0].id
                logger.info(f"デフォルトモデル: {default}")
                return default
            return None
        except Exception as e:
            logger.warning(f"デフォルトモデルの取得に失敗: {e}")
            return None
    
    def detect_and_update_config(self, config_path: str) -> Dict[str, Any]:
        """
        モデルを検出してconfig.yamlを更新
        
        Args:
            config_path: 設定ファイルのパス
            
        Returns:
            Dict: 更新結果の情報
            
        Note:
            - 検出失敗時は既存設定を維持
            - 複数モデル対応（models.lmstudio_*として追加）
        """
        config_path = Path(config_path)
        result = {
            "success": False,
            "models_detected": 0,
            "config_updated": False,
            "default_model": None,
            "models": [],
            "errors": []
        }
        
        # 既存設定の読み込み
        config = self._load_config(config_path)
        
        try:
            # モデル検出
            models = self.get_loaded_models()
            result["models_detected"] = len(models)
            result["models"] = [m.to_dict() for m in models]
            
            if not models:
                result["errors"].append("モデルが検出されませんでした")
                logger.warning("LM Studioにモデルが読み込まれていません")
                return result
            
            # デフォルトモデルを設定
            default_model = models[0]
            result["default_model"] = default_model.id
            
            # config.yamlの更新
            config = self._update_config_models(config, models)
            
            # 設定ファイルの保存
            self._save_config(config_path, config)
            
            result["success"] = True
            result["config_updated"] = True
            logger.info(f"config.yamlを更新しました: {config_path}")
            
        except ConnectionError as e:
            result["errors"].append(f"接続エラー: {e}")
            logger.error(f"LM Studio接続エラー: {e}")
        except Exception as e:
            result["errors"].append(f"更新エラー: {e}")
            logger.error(f"設定更新中にエラー: {e}")
        
        return result
    
    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        """設定ファイルを読み込む（存在しない場合はデフォルトを返す）"""
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if HAS_YAML:
                        return yaml.safe_load(content) or {}
                    else:
                        # yamlがない場合はJSONとしてパースを試みる
                        return json.loads(content) or {}
            except Exception as e:
                logger.warning(f"設定ファイルの読み込みに失敗: {e}")
        
        # デフォルト設定
        return {
            "models": {
                "local": {
                    "endpoint": "http://localhost:1234/v1",
                    "model": "unknown",
                    "temperature": 0.7,
                    "max_tokens": 2048,
                    "timeout": 30000
                },
                "cloud": {
                    "model": "claude-3-sonnet-20240229",
                    "max_tokens": 4096,
                    "temperature": 0.7
                }
            },
            "fallback_chain": {
                "primary": {"model": "local", "name": "Local LLM"},
                "secondary": {"model": "cloud", "name": "Claude"},
                "tertiary": {"model": "cloud_backup", "name": "Claude Backup"}
            }
        }
    
    def _update_config_models(self, config: Dict[str, Any], models: List[ModelInfo]) -> Dict[str, Any]:
        """
        設定辞書を更新
        
        - models.local.model をデフォルトモデルに更新
        - 複数モデルを models.lmstudio_* として追加
        """
        if "models" not in config:
            config["models"] = {}
        
        # ローカルモデルの基本設定
        if "local" not in config["models"]:
            config["models"]["local"] = {}
        
        local_config = config["models"]["local"]
        local_config["endpoint"] = local_config.get("endpoint", self.endpoint)
        local_config["temperature"] = local_config.get("temperature", 0.7)
        local_config["max_tokens"] = local_config.get("max_tokens", 2048)
        local_config["timeout"] = local_config.get("timeout", 30000)
        
        # デフォルトモデルを設定
        default_model = models[0]
        local_config["model"] = default_model.id
        
        # 複数モデル対応: lmstudio_* として追加
        for i, model in enumerate(models):
            model_key = f"lmstudio_{i}" if i > 0 else "lmstudio"
            config["models"][model_key] = {
                "endpoint": self.endpoint,
                "model": model.id,
                "temperature": 0.7,
                "max_tokens": 2048,
                "timeout": 30000,
                "name": model.name or model.id,
                "description": model.description or f"LM Studio loaded model {i+1}"
            }
        
        # 検出されたモデル情報をメタデータとして保存
        if "lmstudio_meta" not in config:
            config["lmstudio_meta"] = {}
        
        config["lmstudio_meta"]["last_detected"] = default_model.id
        config["lmstudio_meta"]["detected_models"] = [m.id for m in models]
        config["lmstudio_meta"]["detected_at"] = str(Path().stat().st_mtime)  # 簡易タイムスタンプ
        
        return config
    
    def _save_config(self, config_path: Path, config: Dict[str, Any]) -> None:
        """設定ファイルを保存"""
        # 親ディレクトリが存在しない場合は作成
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, "w", encoding="utf-8") as f:
            if HAS_YAML:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            else:
                # yamlがない場合はJSONで保存
                json.dump(config, f, indent=2, ensure_ascii=False)
    
    def get_model_details(self, model_id: str) -> Optional[ModelInfo]:
        """
        特定のモデルの詳細を取得
        
        Args:
            model_id: モデルID
            
        Returns:
            Optional[ModelInfo]: モデル情報、見つからない場合はNone
        """
        try:
            models = self.get_loaded_models()
            for model in models:
                if model.id == model_id:
                    return model
            return None
        except Exception:
            return None
    
    def format_models_table(self) -> str:
        """
        モデル一覧をテーブル形式で整形
        
        Returns:
            str: 整形されたモデル一覧文字列
        """
        try:
            models = self.get_loaded_models()
            if not models:
                return "モデルが読み込まれていません"
            
            lines = ["読み込み中のモデル:", "-" * 60]
            
            for i, model in enumerate(models, 1):
                default_mark = " [デフォルト]" if i == 1 else ""
                lines.append(f"  {i}. {model.id}{default_mark}")
                if model.name and model.name != model.id:
                    lines.append(f"     名前: {model.name}")
                if model.description:
                    lines.append(f"     説明: {model.description}")
                if model.size:
                    size_mb = model.size / (1024 * 1024)
                    lines.append(f"     サイズ: {size_mb:.1f} MB")
                lines.append("")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"モデル一覧の取得に失敗: {e}"


# 後方互換性のためのエイリアス
ModelDetector = LMStudioModelDetector
