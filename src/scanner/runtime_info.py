"""
ランタイム・モデル情報データクラス

ローカルLLMランタイムと検出モデルの型定義
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class RuntimeType(Enum):
    """検出可能なローカルLLMランタイム"""
    LMSTUDIO = "lmstudio"
    OLLAMA = "ollama"
    LLAMACPP = "llamacpp"
    KOBOLDCPP = "koboldcpp"
    LOCALAI = "localai"
    JAN = "jan"
    GPT4ALL = "gpt4all"
    TEXTGEN_WEBUI = "textgen-webui"
    VLLM = "vllm"
    UNKNOWN = "unknown"


class ModelSource(Enum):
    """モデルの出自"""
    LOCAL_RUNTIME = "local_runtime"
    CLOUD_API = "cloud_api"


@dataclass
class RuntimeInfo:
    """検出されたローカルLLMランタイム情報"""
    runtime_type: RuntimeType
    endpoint: str
    port: int
    version: Optional[str] = None
    is_responding: bool = False
    response_time_ms: Optional[float] = None
    detected_at: Optional[str] = None  # ISO形式文字列
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "runtime_type": self.runtime_type.value,
            "endpoint": self.endpoint,
            "port": self.port,
            "version": self.version,
            "is_responding": self.is_responding,
            "response_time_ms": self.response_time_ms,
            "detected_at": self.detected_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuntimeInfo":
        return cls(
            runtime_type=RuntimeType(data.get("runtime_type", "unknown")),
            endpoint=data.get("endpoint", ""),
            port=data.get("port", 0),
            version=data.get("version"),
            is_responding=data.get("is_responding", False),
            response_time_ms=data.get("response_time_ms"),
            detected_at=data.get("detected_at"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class DiscoveredModel:
    """検出されたモデル情報"""
    id: str
    name: str
    source: ModelSource
    # ローカルランタイム情報（LOCAL_RUNTIMEの場合）
    runtime: Optional[RuntimeInfo] = None
    # クラウドプロバイダー（CLOUD_APIの場合）
    provider: Optional[str] = None
    api_key_env: Optional[str] = None
    api_key_present: bool = False
    # モデル属性
    endpoint: Optional[str] = None
    description: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    owned_by: str = "unknown"
    size: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "source": self.source.value,
            "runtime": self.runtime.to_dict() if self.runtime else None,
            "provider": self.provider,
            "api_key_env": self.api_key_env,
            "api_key_present": self.api_key_present,
            "endpoint": self.endpoint,
            "description": self.description,
            "capabilities": self.capabilities,
            "owned_by": self.owned_by,
            "size": self.size,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DiscoveredModel":
        runtime_data = data.get("runtime")
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            source=ModelSource(data.get("source", "local_runtime")),
            runtime=RuntimeInfo.from_dict(runtime_data) if runtime_data else None,
            provider=data.get("provider"),
            api_key_env=data.get("api_key_env"),
            api_key_present=data.get("api_key_present", False),
            endpoint=data.get("endpoint"),
            description=data.get("description"),
            capabilities=data.get("capabilities", []),
            owned_by=data.get("owned_by", "unknown"),
            size=data.get("size"),
        )

    def get_display_name(self) -> str:
        """GUI表示用の名前"""
        if self.runtime:
            return f"{self.name} ({self.runtime.runtime_type.value})"
        if self.provider:
            return f"{self.name} ({self.provider})"
        return self.name
