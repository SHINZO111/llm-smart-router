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
"""

from .runtime_info import (
    RuntimeType,
    ModelSource,
    RuntimeInfo,
    DiscoveredModel,
)
from .scanner import MultiRuntimeScanner
from .registry import ModelRegistry
from .cloud_detector import CloudModelDetector

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
