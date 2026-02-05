"""
メッセージモデル - CP1で定義されたデータモデル
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import uuid


class MessageRole(Enum):
    """メッセージの役割"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageType(Enum):
    """メッセージタイプ"""
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    CODE = "code"
    MULTIMODAL = "multimodal"


@dataclass
class MessageContent:
    """
    メッセージ内容
    
    Attributes:
        type: コンテンツタイプ
        text: テキスト内容
        url: メディアURL
        mime_type: MIMEタイプ
        metadata: 追加情報
    """
    type: MessageType = MessageType.TEXT
    text: str = ""
    url: Optional[str] = None
    mime_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "text": self.text,
            "url": self.url,
            "mime_type": self.mime_type,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "MessageContent":
        try:
            msg_type = MessageType(data.get("type", "text"))
        except ValueError:
            msg_type = MessageType.TEXT

        return cls(
            type=msg_type,
            text=data.get("text", ""),
            url=data.get("url"),
            mime_type=data.get("mime_type"),
            metadata=data.get("metadata", {})
        )


@dataclass
class Message:
    """
    メッセージモデル
    
    Attributes:
        id: 一意のメッセージID
        conversation_id: 所属する会話ID
        role: メッセージの役割
        content: メッセージ内容
        created_at: 作成日時
        tokens: トークン数
        model: 使用モデル名
        metadata: 追加メタデータ
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str = ""
    role: MessageRole = MessageRole.USER
    content: MessageContent = field(default_factory=MessageContent)
    created_at: datetime = field(default_factory=datetime.now)
    tokens: Optional[int] = None
    model: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """辞書形式に変換"""
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role.value,
            "content": self.content.to_dict(),
            "created_at": self.created_at.isoformat(),
            "tokens": self.tokens,
            "model": self.model,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        """辞書からインスタンスを作成"""
        content_data = data.get("content", {})
        if isinstance(content_data, str):
            content_data = {"text": content_data, "type": "text"}

        # ロールのバリデーション
        try:
            role = MessageRole(data.get("role", "user"))
        except ValueError:
            role = MessageRole.USER

        # 日時のパース
        created_at_raw = data.get("created_at")
        try:
            created_at = datetime.fromisoformat(created_at_raw) if created_at_raw else datetime.now()
        except (ValueError, TypeError):
            created_at = datetime.now()

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            conversation_id=data.get("conversation_id", ""),
            role=role,
            content=MessageContent.from_dict(content_data),
            created_at=created_at,
            tokens=data.get("tokens"),
            model=data.get("model"),
            metadata=data.get("metadata", {})
        )
    
    def get_text(self) -> str:
        """テキスト内容を取得"""
        return self.content.text
    
    def set_text(self, text: str):
        """テキスト内容を設定"""
        self.content.text = text
