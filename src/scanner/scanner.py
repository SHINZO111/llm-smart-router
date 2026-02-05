"""
マルチランタイムスキャナー

ローカルLLMランタイムの既知ポートを並列スキャンし、
利用可能なモデルを自動検出する。クラウドAPIキーの検出も統合。
"""

import asyncio
import logging
from typing import List, Dict, Tuple, Type

from .runtime_info import RuntimeType, DiscoveredModel
from .runtime_detectors import (
    BaseRuntimeDetector,
    LMStudioDetector,
    OllamaDetector,
    GenericOpenAIDetector,
)
from .cloud_detector import CloudModelDetector

logger = logging.getLogger(__name__)

# スキャン対象ポート定義: (ポート, 検出器クラス, ランタイム種別, ラベル)
ScanTarget = Tuple[int, Type[BaseRuntimeDetector], RuntimeType, str]

DEFAULT_SCAN_TARGETS: List[ScanTarget] = [
    (1234, LMStudioDetector, RuntimeType.LMSTUDIO, "LM Studio"),
    (11434, OllamaDetector, RuntimeType.OLLAMA, "Ollama"),
    (8080, GenericOpenAIDetector, RuntimeType.LLAMACPP, "llama.cpp"),
    (5001, GenericOpenAIDetector, RuntimeType.KOBOLDCPP, "KoboldCpp"),
    (1337, GenericOpenAIDetector, RuntimeType.JAN, "Jan"),
    (4891, GenericOpenAIDetector, RuntimeType.GPT4ALL, "GPT4All"),
    (5000, GenericOpenAIDetector, RuntimeType.TEXTGEN_WEBUI, "text-gen-webui"),
    (8888, GenericOpenAIDetector, RuntimeType.VLLM, "vLLM"),
]


class MultiRuntimeScanner:
    """
    複数ランタイムの並列スキャンを行うオーケストレーター

    Usage:
        scanner = MultiRuntimeScanner()
        results = asyncio.run(scanner.scan_all())
        # results = {"lmstudio:1234": [DiscoveredModel, ...], "cloud": [...]}
    """

    def __init__(
        self,
        scan_targets: List[ScanTarget] = None,
        host: str = "localhost",
        timeout: float = 2.0,
        include_cloud: bool = True,
    ):
        self.scan_targets = scan_targets if scan_targets is not None else DEFAULT_SCAN_TARGETS
        self.host = host
        self.timeout = timeout
        self.include_cloud = include_cloud

    async def scan_all(self) -> Dict[str, List[DiscoveredModel]]:
        """
        全ターゲットを並列スキャンし、検出結果を返す

        Returns:
            {"lmstudio:1234": [models], "ollama:11434": [models], "cloud": [models]}
        """
        logger.info(f"マルチランタイムスキャン開始 ({len(self.scan_targets)}ポート)")

        # ローカルランタイムのスキャンタスクを生成
        tasks = []
        for port, detector_cls, runtime_type, label in self.scan_targets:
            tasks.append(self._scan_one(port, detector_cls, runtime_type, label))

        # クラウド検出タスク
        if self.include_cloud:
            tasks.append(self._scan_cloud())

        # 全タスクを並列実行
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 結果の集約
        all_models: Dict[str, List[DiscoveredModel]] = {}
        for result in raw_results:
            if isinstance(result, Exception):
                logger.warning(f"スキャンタスク例外: {result}")
                continue
            if result:
                all_models.update(result)

        total = sum(len(v) for v in all_models.values())
        logger.info(f"スキャン完了: {len(all_models)}ランタイム, {total}モデル")
        return all_models

    async def _scan_one(
        self,
        port: int,
        detector_cls: Type[BaseRuntimeDetector],
        runtime_type: RuntimeType,
        label: str,
    ) -> Dict[str, List[DiscoveredModel]]:
        """単一ランタイムのスキャン"""
        try:
            # GenericOpenAIDetector は追加引数が必要
            if detector_cls is GenericOpenAIDetector:
                detector = detector_cls(
                    self.host, port,
                    runtime_type=runtime_type,
                    runtime_label=label,
                    timeout=self.timeout,
                )
            else:
                detector = detector_cls(self.host, port, timeout=self.timeout)

            detected, runtime_info = await detector.detect()
            if not detected or runtime_info is None:
                logger.debug(f"{label}:{port} - 未検出")
                return {}

            rt_ms = runtime_info.response_time_ms or 0
            logger.info(f"{label}:{port} 検出 ({rt_ms:.0f}ms)")

            models = await detector.get_models(runtime_info)
            if models:
                key = f"{runtime_type.value}:{port}"
                logger.info(f"  {len(models)}個のモデル発見")
                return {key: models}
            return {}

        except Exception as e:
            logger.debug(f"{label}:{port} スキャン例外: {e}")
            return {}

    async def _scan_cloud(self) -> Dict[str, List[DiscoveredModel]]:
        """クラウドAPIキー検出"""
        try:
            detector = CloudModelDetector()
            models = detector.detect()
            if models:
                return {"cloud": models}
            return {}
        except Exception as e:
            logger.warning(f"クラウド検出例外: {e}")
            return {}
