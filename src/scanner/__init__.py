"""
LLM Runtime Scanner Package

ローカルLLMランタイム（LM Studio, Ollama, llama.cpp等）を自動検出し、
利用可能なモデルを一元管理する。

Usage:
    import asyncio
    from scanner.scanner import MultiRuntimeScanner
    from scanner.registry import ModelRegistry

    scanner = MultiRuntimeScanner()
    results = asyncio.run(scanner.scan_all())

    registry = ModelRegistry()
    registry.update(results)

Note:
    runtime_info のみ即座インポート（純粋データクラス、外部依存なし）。
    scanner, registry, cloud_detector は遅延インポート（aiohttp等の重い依存を回避）。
"""

# runtime_info は純粋データクラスのみ - 即座にインポートしても安全
from .runtime_info import (
    RuntimeType,
    ModelSource,
    RuntimeInfo,
    DiscoveredModel,
)

__version__ = "1.0.0"
__all__ = [
    "RuntimeType",
    "ModelSource",
    "RuntimeInfo",
    "DiscoveredModel",
    "MultiRuntimeScanner",
    "ModelRegistry",
    "CloudModelDetector",
]


def __getattr__(name):
    """遅延インポート: aiohttp等の重い依存はアクセス時にのみロード"""
    if name == "MultiRuntimeScanner":
        from .scanner import MultiRuntimeScanner
        return MultiRuntimeScanner
    if name == "ModelRegistry":
        from .registry import ModelRegistry
        return ModelRegistry
    if name == "CloudModelDetector":
        from .cloud_detector import CloudModelDetector
        return CloudModelDetector
    raise AttributeError(f"module 'scanner' has no attribute {name!r}")
