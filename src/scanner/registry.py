"""
モデルレジストリ

スキャン結果をJSONファイルに永続化し、GUI・router.js・APIから参照可能にする。
TTLベースのキャッシュ管理付き。
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from .runtime_info import DiscoveredModel, ModelSource

logger = logging.getLogger(__name__)

# デフォルト保存先（プロジェクトルート基準）
DEFAULT_REGISTRY_PATH = "./data/model_registry.json"
DEFAULT_CACHE_TTL = 300  # 5分


class ModelRegistry:
    """
    検出モデルの一元管理レジストリ

    - JSON永続化（router.jsからも読める）
    - TTLベースのキャッシュ判定
    - ローカル/クラウド別のアクセサー
    """

    def __init__(
        self,
        cache_path: str = DEFAULT_REGISTRY_PATH,
        cache_ttl: int = DEFAULT_CACHE_TTL,
    ):
        self.cache_path = Path(cache_path)
        self.cache_ttl = cache_ttl
        self._models: Dict[str, List[DiscoveredModel]] = {}
        self._last_scan: Optional[datetime] = None
        self._load_cache()

    def update(self, scan_results: Dict[str, List[DiscoveredModel]]) -> None:
        """スキャン結果でレジストリを更新"""
        self._models = scan_results
        self._last_scan = datetime.now()
        self._save_cache()
        total = self.get_total_count()
        logger.info(f"レジストリ更新: {total}モデル")

    def get_all_models(self) -> Dict[str, List[DiscoveredModel]]:
        """全モデルをグループ別に返す"""
        return self._models

    def get_flat_models(self) -> List[DiscoveredModel]:
        """全モデルをフラットリストで返す"""
        return [m for models in self._models.values() for m in models]

    def get_local_models(self) -> List[DiscoveredModel]:
        """ローカルランタイムのモデルのみ"""
        return [
            m
            for key, models in self._models.items()
            if key != "cloud"
            for m in models
        ]

    def get_cloud_models(self) -> List[DiscoveredModel]:
        """クラウドモデルのみ"""
        return [
            m
            for key, models in self._models.items()
            if key == "cloud"
            for m in models
        ]

    def get_total_count(self) -> int:
        return sum(len(v) for v in self._models.values())

    def is_cache_valid(self) -> bool:
        """キャッシュがTTL内か判定"""
        if self._last_scan is None:
            return False
        age = (datetime.now() - self._last_scan).total_seconds()
        return age < self.cache_ttl

    @property
    def last_scan_iso(self) -> Optional[str]:
        return self._last_scan.isoformat() if self._last_scan else None

    # ── 永続化 ──

    def _save_cache(self) -> None:
        """レジストリをJSONに保存"""
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "last_scan": self.last_scan_iso,
                "cache_ttl": self.cache_ttl,
                "models": {
                    key: [m.to_dict() for m in models]
                    for key, models in self._models.items()
                },
            }
            # アトミック書き込み: 一時ファイル → rename
            import tempfile
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=str(self.cache_path.parent),
                suffix=".tmp",
                prefix=".registry_",
            )
            try:
                with open(tmp_fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                import os
                os.replace(tmp_path, str(self.cache_path))
                logger.debug(f"レジストリ保存: {self.cache_path}")
            except Exception:
                # 一時ファイルのクリーンアップ
                try:
                    import os
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as e:
            logger.warning(f"レジストリ保存失敗: {e}")

    def _load_cache(self) -> None:
        """JSONからレジストリを復元"""
        if not self.cache_path.exists():
            return
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                logger.warning("レジストリ: 不正な構造（dictでない）")
                return

            last_scan_str = data.get("last_scan")
            if last_scan_str:
                try:
                    self._last_scan = datetime.fromisoformat(last_scan_str)
                except (ValueError, TypeError):
                    logger.warning(f"レジストリ: 不正な日時: {last_scan_str}")

            models_data = data.get("models", {})
            if not isinstance(models_data, dict):
                logger.warning("レジストリ: models が dict でない")
                return

            self._models = {}
            for key, model_dicts in models_data.items():
                if not isinstance(model_dicts, list):
                    logger.warning(f"レジストリ: {key} がリストでない、スキップ")
                    continue
                loaded = []
                for d in model_dicts:
                    try:
                        loaded.append(DiscoveredModel.from_dict(d))
                    except Exception as e:
                        logger.debug(f"レジストリ: モデル復元失敗: {e}")
                        continue
                self._models[key] = loaded

            logger.info(f"レジストリ読込: {self.get_total_count()}モデル (from {self.cache_path})")
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"レジストリ読込失敗: {e}")
