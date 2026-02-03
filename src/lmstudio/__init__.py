"""
LM Studio Model Detector Package

LM StudioのOpenAI互換APIを使用してモデルを自動検出するパッケージ
"""

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
