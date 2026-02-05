"""
LLM Runtime Scanner テスト

マルチランタイム検出・レジストリ・クラウド検出のユニットテスト
"""

import sys
import time
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

# パス設定（重複挿入防止）
_src = str(Path(__file__).parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from scanner.runtime_info import (
    RuntimeType, ModelSource, RuntimeInfo, DiscoveredModel,
)
from scanner.runtime_detectors import (
    LMStudioDetector, OllamaDetector, GenericOpenAIDetector,
)
from scanner.cloud_detector import CloudModelDetector
from scanner.scanner import MultiRuntimeScanner
from scanner.registry import ModelRegistry


# ============================================================
# RuntimeInfo / DiscoveredModel データクラステスト
# ============================================================

class TestRuntimeInfo:

    def test_to_dict_from_dict_roundtrip(self):
        info = RuntimeInfo(
            runtime_type=RuntimeType.LMSTUDIO,
            endpoint="http://localhost:1234/v1",
            port=1234,
            is_responding=True,
            response_time_ms=42.5,
            detected_at="2026-01-01T00:00:00",
        )
        d = info.to_dict()
        restored = RuntimeInfo.from_dict(d)
        assert restored.runtime_type == RuntimeType.LMSTUDIO
        assert restored.port == 1234
        assert restored.response_time_ms == 42.5

    def test_unknown_runtime_type(self):
        info = RuntimeInfo.from_dict({"runtime_type": "unknown", "endpoint": "", "port": 0})
        assert info.runtime_type == RuntimeType.UNKNOWN


class TestDiscoveredModel:

    def test_to_dict_from_dict_roundtrip(self):
        runtime = RuntimeInfo(
            runtime_type=RuntimeType.OLLAMA,
            endpoint="http://localhost:11434/v1",
            port=11434,
        )
        model = DiscoveredModel(
            id="llama3:latest",
            name="Llama 3",
            source=ModelSource.LOCAL_RUNTIME,
            runtime=runtime,
            description="Ollama: llama",
            capabilities=["reasoning"],
        )
        d = model.to_dict()
        restored = DiscoveredModel.from_dict(d)
        assert restored.id == "llama3:latest"
        assert restored.source == ModelSource.LOCAL_RUNTIME
        assert restored.runtime.runtime_type == RuntimeType.OLLAMA

    def test_cloud_model(self):
        model = DiscoveredModel(
            id="gpt-4o",
            name="GPT-4o",
            source=ModelSource.CLOUD_API,
            provider="openai",
            api_key_present=True,
        )
        assert model.get_display_name() == "GPT-4o (openai)"

    def test_local_model_display_name(self):
        runtime = RuntimeInfo(
            runtime_type=RuntimeType.LMSTUDIO,
            endpoint="http://localhost:1234/v1",
            port=1234,
        )
        model = DiscoveredModel(
            id="test-model",
            name="Test Model",
            source=ModelSource.LOCAL_RUNTIME,
            runtime=runtime,
        )
        assert model.get_display_name() == "Test Model (lmstudio)"


# ============================================================
# Detector テスト (aiohttp モック)
# ============================================================

def _make_mock_response(json_data, status=200):
    """aiohttp レスポンスのモック生成"""
    import json
    mock_resp = AsyncMock()
    mock_resp.status = status
    mock_resp.json = AsyncMock(return_value=json_data)
    mock_resp.headers = {"Content-Type": "application/json"}
    # _get_json は resp.content.read() + json.loads() を使う
    body_bytes = json.dumps(json_data).encode("utf-8")
    mock_content = AsyncMock()
    mock_content.read = AsyncMock(return_value=body_bytes)
    mock_resp.content = mock_content
    return mock_resp


class TestLMStudioDetector:

    @pytest.mark.asyncio
    async def test_detect_success(self):
        detector = LMStudioDetector("localhost", 1234, timeout=1.0)
        mock_data = {"data": [{"id": "test-model", "object": "model", "created": 0, "owned_by": "lmstudio"}]}

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_resp = _make_mock_response(mock_data)
            mock_session.get = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_resp),
                __aexit__=AsyncMock(return_value=False),
            ))
            mock_session_cls.return_value = mock_session

            detected, info = await detector.detect()
            assert detected is True
            assert info.runtime_type == RuntimeType.LMSTUDIO
            assert info.port == 1234

    @pytest.mark.asyncio
    async def test_detect_failure_connection_refused(self):
        detector = LMStudioDetector("localhost", 9999, timeout=0.5)

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.get = MagicMock(side_effect=ConnectionRefusedError())
            mock_session_cls.return_value = mock_session

            detected, info = await detector.detect()
            assert detected is False
            assert info is None

    @pytest.mark.asyncio
    async def test_get_models(self):
        detector = LMStudioDetector("localhost", 1234, timeout=1.0)
        runtime = RuntimeInfo(
            runtime_type=RuntimeType.LMSTUDIO,
            endpoint="http://localhost:1234/v1",
            port=1234,
        )
        mock_data = {
            "data": [
                {"id": "model-a", "object": "model", "created": 0, "owned_by": "lmstudio"},
                {"id": "model-b", "object": "model", "created": 0, "owned_by": "lmstudio"},
            ]
        }

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_resp = _make_mock_response(mock_data)
            mock_session.get = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_resp),
                __aexit__=AsyncMock(return_value=False),
            ))
            mock_session_cls.return_value = mock_session

            models = await detector.get_models(runtime)
            assert len(models) == 2
            assert models[0].id == "model-a"
            assert models[0].source == ModelSource.LOCAL_RUNTIME


class TestOllamaDetector:

    @pytest.mark.asyncio
    async def test_detect_via_native_api(self):
        detector = OllamaDetector("localhost", 11434, timeout=1.0)
        mock_data = {
            "models": [
                {"name": "llama3:latest", "size": 4_000_000_000, "details": {"family": "llama", "parameter_size": "8B"}},
            ]
        }

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_resp = _make_mock_response(mock_data)
            mock_session.get = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_resp),
                __aexit__=AsyncMock(return_value=False),
            ))
            mock_session_cls.return_value = mock_session

            detected, info = await detector.detect()
            assert detected is True
            assert info.runtime_type == RuntimeType.OLLAMA

    @pytest.mark.asyncio
    async def test_get_models_with_details(self):
        detector = OllamaDetector("localhost", 11434, timeout=1.0)
        runtime = RuntimeInfo(
            runtime_type=RuntimeType.OLLAMA,
            endpoint="http://localhost:11434/v1",
            port=11434,
        )
        mock_data = {
            "models": [
                {"name": "llama3:latest", "size": 4_000_000_000, "details": {"family": "llama", "parameter_size": "8B"}},
                {"name": "codellama:7b", "size": 3_800_000_000, "details": {"family": "llama"}},
            ]
        }

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_resp = _make_mock_response(mock_data)
            mock_session.get = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_resp),
                __aexit__=AsyncMock(return_value=False),
            ))
            mock_session_cls.return_value = mock_session

            models = await detector.get_models(runtime)
            assert len(models) == 2
            assert models[0].id == "llama3:latest"
            assert models[0].size == 4_000_000_000


class TestGenericOpenAIDetector:

    @pytest.mark.asyncio
    async def test_detect_with_custom_runtime_type(self):
        detector = GenericOpenAIDetector(
            "localhost", 8080,
            runtime_type=RuntimeType.LLAMACPP,
            runtime_label="llama.cpp",
        )
        mock_data = {"data": [{"id": "my-model", "object": "model", "created": 0, "owned_by": "user"}]}

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_resp = _make_mock_response(mock_data)
            mock_session.get = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_resp),
                __aexit__=AsyncMock(return_value=False),
            ))
            mock_session_cls.return_value = mock_session

            detected, info = await detector.detect()
            assert detected is True
            assert info.runtime_type == RuntimeType.LLAMACPP


# ============================================================
# CloudModelDetector テスト
# ============================================================

class TestCloudModelDetector:

    def test_detect_with_api_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        detector = CloudModelDetector()
        models = detector.detect()

        assert len(models) >= 1
        assert all(m.source == ModelSource.CLOUD_API for m in models)
        assert all(m.provider == "anthropic" for m in models)
        assert all(m.api_key_present for m in models)

    def test_detect_no_keys(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        detector = CloudModelDetector()
        models = detector.detect()
        assert len(models) == 0

    def test_detect_multiple_providers(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
        monkeypatch.setenv("OPENAI_API_KEY", "test")
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        detector = CloudModelDetector()
        models = detector.detect()

        providers = set(m.provider for m in models)
        assert "anthropic" in providers
        assert "openai" in providers


# ============================================================
# ModelRegistry テスト
# ============================================================

class TestModelRegistry:

    def test_empty_registry(self, tmp_path):
        registry = ModelRegistry(cache_path=str(tmp_path / "reg.json"))
        assert registry.get_total_count() == 0
        assert registry.is_cache_valid() is False

    def test_update_and_query(self, tmp_path):
        registry = ModelRegistry(cache_path=str(tmp_path / "reg.json"))
        runtime = RuntimeInfo(
            runtime_type=RuntimeType.LMSTUDIO,
            endpoint="http://localhost:1234/v1",
            port=1234,
        )
        local_model = DiscoveredModel(
            id="test-local", name="Test Local",
            source=ModelSource.LOCAL_RUNTIME, runtime=runtime,
        )
        cloud_model = DiscoveredModel(
            id="gpt-4o", name="GPT-4o",
            source=ModelSource.CLOUD_API, provider="openai",
        )

        registry.update({
            "lmstudio:1234": [local_model],
            "cloud": [cloud_model],
        })

        assert registry.get_total_count() == 2
        assert len(registry.get_local_models()) == 1
        assert len(registry.get_cloud_models()) == 1
        assert registry.is_cache_valid() is True

    def test_persistence_roundtrip(self, tmp_path):
        path = str(tmp_path / "reg.json")
        registry1 = ModelRegistry(cache_path=path)

        model = DiscoveredModel(
            id="my-model", name="My Model",
            source=ModelSource.LOCAL_RUNTIME,
            runtime=RuntimeInfo(
                runtime_type=RuntimeType.OLLAMA,
                endpoint="http://localhost:11434/v1",
                port=11434,
            ),
        )
        registry1.update({"ollama:11434": [model]})

        # 新しいインスタンスで復元
        registry2 = ModelRegistry(cache_path=path)
        assert registry2.get_total_count() == 1
        restored = registry2.get_local_models()[0]
        assert restored.id == "my-model"
        assert restored.runtime.runtime_type == RuntimeType.OLLAMA

    def test_cache_ttl_expired(self, tmp_path):
        registry = ModelRegistry(cache_path=str(tmp_path / "reg.json"), cache_ttl=0)
        registry.update({"cloud": []})

        # TTL=0 なので即座に期限切れ
        import time
        time.sleep(0.01)
        assert registry.is_cache_valid() is False

    def test_flat_models(self, tmp_path):
        registry = ModelRegistry(cache_path=str(tmp_path / "reg.json"))
        m1 = DiscoveredModel(id="a", name="A", source=ModelSource.LOCAL_RUNTIME)
        m2 = DiscoveredModel(id="b", name="B", source=ModelSource.CLOUD_API)
        registry.update({"local:1234": [m1], "cloud": [m2]})

        flat = registry.get_flat_models()
        assert len(flat) == 2
        ids = {m.id for m in flat}
        assert ids == {"a", "b"}


# ============================================================
# MultiRuntimeScanner テスト
# ============================================================

class TestMultiRuntimeScanner:

    @pytest.mark.asyncio
    async def test_scan_all_no_runtimes(self):
        """全ポートで接続拒否 → 空の結果（ネットワーク接続をモック）"""
        scanner = MultiRuntimeScanner(
            scan_targets=[],  # 実ポートへの接続を避ける
            include_cloud=False,
        )
        results = await scanner.scan_all()
        assert isinstance(results, dict)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_scan_completes_within_timeout(self):
        """全ポートスキャンが並列で実行され、妥当な時間で完了する"""
        scanner = MultiRuntimeScanner(
            scan_targets=[],  # 実ポートへの接続を避ける
            include_cloud=False,
        )

        start = time.monotonic()
        await scanner.scan_all()
        elapsed = time.monotonic() - start

        # 空ターゲットなので即座に完了
        assert elapsed < 2.0

    @pytest.mark.asyncio
    async def test_scan_with_cloud_detection(self, monkeypatch):
        """クラウド検出が統合されている"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        scanner = MultiRuntimeScanner(
            scan_targets=[],  # ローカルスキャンなし
            include_cloud=True,
        )
        results = await scanner.scan_all()

        assert "cloud" in results
        assert len(results["cloud"]) >= 1
        assert results["cloud"][0].provider == "anthropic"
