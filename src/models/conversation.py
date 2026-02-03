"""
会話モデル - CP1で定義されたデータモデル
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum
import uuid


class ConversationStatus(Enum):
    """会話ステータス"""
    ACTIVE = "active"      # 進行中
    PAUSED = "paused"      # 一時停止
    CLOSED = "closed"      # 終了
    ARCHIVED = "archived"  # アーカイブ


@dataclass
class Conversation:
    """
    会話セッションモデル
    
    Attributes:
        id: 一意のセッションID
        title: 会話タイトル
        user_id: ユーザーID
        status: 会話ステータス
        topic_id: トピックID（オプション）
        created_at: 作成日時
        updated_at: 最終更新日時
        message_count: メッセージ数
        summary: 会話サマリー
        metadata: 追加メタデータ
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    user_id: str = ""
    status: ConversationStatus = ConversationStatus.ACTIVE
    topic_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    message_count: int = 0
    summary: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """辞書形式に変換"""
        return {
            "id": self.id,
            "title": self.title,
            "user_id": self.user_id,
            "status": self.status.value,
            "topic_id": self.topic_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "message_count": self.message_count,
            "summary": self.summary,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Conversation":
        """辞書からインスタンスを作成"""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            title=data.get("title", ""),
            user_id=data.get("user_id", ""),
            status=ConversationStatus(data.get("status", "active")),
            topic_id=data.get("topic_id"),
            created_at=datetime.fromisoformat(data.get("created_at")) if data.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(data.get("updated_at")) if data.get("updated_at") else datetime.now(),
            message_count=data.get("message_count", 0),
            summary=data.get("summary"),
            metadata=data.get("metadata", {})
        )
    
    def update_timestamp(self):
        """更新日時を更新"""
        self.updated_at = datetime.now()


@dataclass
class Topic:
    """
    トピックモデル
    
    Attributes:
        id: 一意のトピックID
        name: トピック名
        description: 説明
        color: 表示色（カラーコード）
        parent_id: 親トピックID
        created_at: 作成日時
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: Optional[str] = None
    color: str = "#3B82F6"  # デフォルト: 青
    parent_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        """辞書形式に変換"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "color": self.color,
            "parent_id": self.parent_id,
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Topic":
        """辞書からインスタンスを作成"""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", ""),
            description=data.get("description"),
            color=data.get("color", "#3B82F6"),
            parent_id=data.get("parent_id"),
            created_at=datetime.fromisoformat(data.get("created_at")) if data.get("created_at") else datetime.now()
        )
