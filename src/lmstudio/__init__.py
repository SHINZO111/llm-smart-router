"""
LM Studio Model Detector Package

⚠️ 非推奨: このパッケージは scanner パッケージに統合されました。
  from scanner import MultiRuntimeScanner, ModelRegistry
を使用してください。

後方互換性のため、既存のインポートは引き続き動作します。
"""

import warnings

warnings.warn(
    "lmstudio パッケージは非推奨です。scanner パッケージを使用してください。"
    " 例: from scanner import MultiRuntimeScanner",
    DeprecationWarning,
    stacklevel=2,
)

from .model_detector import (
    LMStudioModelDetector,
    ModelDetector,  # 後方互換性
    ModelInfo,
)

__version__ = "1.0.0"
__all__ = [
    "LMStudioModelDetector",
    "ModelDetector",
    "ModelInfo",
]

# 便利な短縮インポート用
detect = LMStudioModelDetector().get_loaded_models
default_model = LMStudioModelDetector().get_default_model
check_status = LMStudioModelDetector().is_running
