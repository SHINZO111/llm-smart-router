"""
会話管理クラス - Conversation Manager

新規セッション開始、既存セッション継続、トピック管理、会話一覧取得を提供
"""
import json
import os
import re
import sys
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Callable
from pathlib import Path

logger = logging.getLogger(__name__)

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from models.conversation import Conversation, ConversationStatus, Topic
from models.message import Message, MessageRole, MessageContent, MessageType
from conversation.title_generator import TitleGenerator


class ConversationManager:
    """
    会話セッションを管理するクラス
    
    機能:
    - 新規セッション開始
    - 既存セッション継続
    - トピック作成・管理
    - 会話一覧取得（日付順、フィルタ対応）
    """
    
    def __init__(self, storage_path: Optional[str] = None, 
                 title_generator: Optional[TitleGenerator] = None):
        """
        ConversationManagerを初期化
        
        Args:
            storage_path: 会話データの保存先パス
            title_generator: タイトル生成器（指定しない場合はデフォルト使用）
        """
        self.storage_path = Path(storage_path) if storage_path else Path.home() / ".llm-router" / "conversations"
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.title_generator = title_generator or TitleGenerator()
        
        # メモリキャッシュ
        self._conversations: Dict[str, Conversation] = {}
        self._topics: Dict[str, Topic] = {}
        self._messages: Dict[str, List[Message]] = {}  # conversation_id -> messages
        
        # 変更検知コールバック
        self._on_conversation_changed: List[Callable[[Conversation], None]] = []
        self._on_message_added: List[Callable[[Message], None]] = []
        
        # データをロード
        self._load_all_data()
    
    # ========== コールバック登録 ==========
    
    def on_conversation_changed(self, callback: Callable[[Conversation], None]):
        """会話変更時のコールバックを登録"""
        self._on_conversation_changed.append(callback)
    
    def on_message_added(self, callback: Callable[[Message], None]):
        """メッセージ追加時のコールバックを登録"""
        self._on_message_added.append(callback)

    def remove_conversation_callback(self, callback: Callable[[Conversation], None]) -> bool:
        """会話変更コールバックを解除"""
        try:
            self._on_conversation_changed.remove(callback)
            return True
        except ValueError:
            return False

    def remove_message_callback(self, callback: Callable[[Message], None]) -> bool:
        """メッセージ追加コールバックを解除"""
        try:
            self._on_message_added.remove(callback)
            return True
        except ValueError:
            return False

    def clear_all_callbacks(self) -> None:
        """すべてのコールバックをクリア"""
        self._on_conversation_changed.clear()
        self._on_message_added.clear()

    def _notify_conversation_changed(self, conversation: Conversation):
        """会話変更を通知"""
        for callback in self._on_conversation_changed:
            try:
                callback(conversation)
            except Exception as e:
                logger.error(f"Conversation callback error: {e}", exc_info=True)
    
    def _notify_message_added(self, message: Message):
        """メッセージ追加を通知"""
        for callback in self._on_message_added:
            try:
                callback(message)
            except Exception as e:
                logger.error(f"Message callback error: {e}", exc_info=True)
    
    # ========== データ永続化 ==========

    _SAFE_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')

    def _validate_id(self, conversation_id: str) -> str:
        """IDのバリデーション（パストラバーサル防止）"""
        if not conversation_id or not self._SAFE_ID_PATTERN.match(conversation_id):
            raise ValueError(f"Invalid conversation ID: {conversation_id!r}")
        return conversation_id

    def _get_conversation_file(self, conversation_id: str) -> Path:
        """会話ファイルのパスを取得"""
        self._validate_id(conversation_id)
        return self.storage_path / f"{conversation_id}.json"

    def _get_messages_file(self, conversation_id: str) -> Path:
        """メッセージファイルのパスを取得"""
        self._validate_id(conversation_id)
        return self.storage_path / f"{conversation_id}_messages.json"
    
    def _get_topics_file(self) -> Path:
        """トピックファイルのパスを取得"""
        return self.storage_path / "topics.json"
    
    def _save_conversation(self, conversation: Conversation):
        """会話をファイルに保存"""
        file_path = self._get_conversation_file(conversation.id)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(conversation.to_dict(), f, ensure_ascii=False, indent=2)
    
    def _save_messages(self, conversation_id: str):
        """メッセージをファイルに保存"""
        if conversation_id not in self._messages:
            return
        file_path = self._get_messages_file(conversation_id)
        messages_data = [m.to_dict() for m in self._messages[conversation_id]]
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(messages_data, f, ensure_ascii=False, indent=2)
    
    def _save_topics(self):
        """トピックをファイルに保存"""
        file_path = self._get_topics_file()
        topics_data = [t.to_dict() for t in self._topics.values()]
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(topics_data, f, ensure_ascii=False, indent=2)
    
    def _load_all_data(self):
        """すべてのデータをロード"""
        # トピックをロード
        topics_file = self._get_topics_file()
        if topics_file.exists():
            try:
                with open(topics_file, "r", encoding="utf-8") as f:
                    topics_data = json.load(f)
                    for data in topics_data:
                        topic = Topic.from_dict(data)
                        self._topics[topic.id] = topic
            except Exception as e:
                logger.warning(f"Failed to load topics: {e}")
        
        # 会話をロード
        for file_path in self.storage_path.glob("*.json"):
            if file_path.name == "topics.json" or file_path.name.endswith("_messages.json"):
                continue
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    conversation = Conversation.from_dict(data)
                    self._conversations[conversation.id] = conversation
                    
                    # メッセージもロード
                    messages_file = self._get_messages_file(conversation.id)
                    if messages_file.exists():
                        with open(messages_file, "r", encoding="utf-8") as mf:
                            messages_data = json.load(mf)
                            self._messages[conversation.id] = [
                                Message.from_dict(m) for m in messages_data
                            ]
                    else:
                        self._messages[conversation.id] = []
            except Exception as e:
                logger.warning(f"Failed to load conversation {file_path}: {e}")
    
    # ========== 新規セッション開始 ==========
    
    def create_conversation(self, user_id: str = "", 
                           first_message: Optional[str] = None,
                           topic_id: Optional[str] = None) -> Conversation:
        """
        新規会話セッションを作成
        
        Args:
            user_id: ユーザーID
            first_message: 最初のユーザー入力（タイトル生成用）
            topic_id: 紐づけるトピックID
            
        Returns:
            作成されたConversationインスタンス
        """
        # タイトルを生成
        title = ""
        if first_message:
            title = self.title_generator.generate(first_message)
        
        # 会話を作成
        conversation = Conversation(
            user_id=user_id,
            title=title,
            topic_id=topic_id,
            status=ConversationStatus.ACTIVE
        )
        
        # キャッシュとファイルに保存
        self._conversations[conversation.id] = conversation
        self._messages[conversation.id] = []
        self._save_conversation(conversation)
        
        # 最初のメッセージがあれば追加
        if first_message:
            self.add_message(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                text=first_message
            )
        
        self._notify_conversation_changed(conversation)
        return conversation
    
    def start_session(self, user_id: str = "", 
                     initial_message: Optional[str] = None) -> Conversation:
        """
        新規セッションを開始（シンプルなインターフェース）
        
        Args:
            user_id: ユーザーID
            initial_message: 最初のメッセージ
            
        Returns:
            作成されたConversationインスタンス
        """
        return self.create_conversation(
            user_id=user_id,
            first_message=initial_message
        )
    
    # ========== 既存セッション継続 ==========
    
    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """
        指定IDの会話を取得
        
        Args:
            conversation_id: 会話ID
            
        Returns:
            Conversationインスタンス、存在しない場合はNone
        """
        return self._conversations.get(conversation_id)
    
    def resume_session(self, conversation_id: str) -> Optional[Conversation]:
        """
        既存セッションを再開
        
        Args:
            conversation_id: 再開する会話ID
            
        Returns:
            Conversationインスタンス、存在しない場合はNone
        """
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return None
        
        # ステータスをACTIVEに更新
        if conversation.status != ConversationStatus.ACTIVE:
            conversation.status = ConversationStatus.ACTIVE
            conversation.update_timestamp()
            self._save_conversation(conversation)
            self._notify_conversation_changed(conversation)
        
        return conversation
    
    def update_conversation(self, conversation_id: str, 
                           title: Optional[str] = None,
                           status: Optional[ConversationStatus] = None,
                           topic_id: Optional[str] = None) -> Optional[Conversation]:
        """
        会話情報を更新
        
        Args:
            conversation_id: 会話ID
            title: 新しいタイトル
            status: 新しいステータス
            topic_id: 新しいトピックID
            
        Returns:
            更新されたConversationインスタンス
        """
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return None
        
        if title is not None:
            conversation.title = title
        if status is not None:
            conversation.status = status
        if topic_id is not None:
            conversation.topic_id = topic_id
        
        conversation.update_timestamp()
        self._save_conversation(conversation)
        self._notify_conversation_changed(conversation)
        return conversation
    
    # ========== メッセージ管理 ==========
    
    def add_message(self, conversation_id: str,
                   role: MessageRole,
                   text: str,
                   model: Optional[str] = None,
                   tokens: Optional[int] = None) -> Optional[Message]:
        """
        メッセージを追加
        
        Args:
            conversation_id: 会話ID
            role: メッセージの役割
            text: メッセージテキスト
            model: 使用モデル名
            tokens: トークン数
            
        Returns:
            作成されたMessageインスタンス
        """
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return None
        
        # メッセージを作成
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=MessageContent(type=MessageType.TEXT, text=text),
            model=model,
            tokens=tokens
        )
        
        # キャッシュに追加
        if conversation_id not in self._messages:
            self._messages[conversation_id] = []
        self._messages[conversation_id].append(message)
        
        # 会話のメッセージ数を更新
        conversation.message_count = len(self._messages[conversation_id])
        conversation.update_timestamp()
        
        # 保存
        self._save_messages(conversation_id)
        self._save_conversation(conversation)
        
        self._notify_message_added(message)
        self._notify_conversation_changed(conversation)
        
        return message
    
    def get_messages(self, conversation_id: str, 
                    limit: Optional[int] = None,
                    offset: int = 0) -> List[Message]:
        """
        会話のメッセージ一覧を取得
        
        Args:
            conversation_id: 会話ID
            limit: 取得件数上限
            offset: スキップ件数
            
        Returns:
            Messageインスタンスのリスト
        """
        messages = self._messages.get(conversation_id, [])
        messages = messages[offset:]
        if limit:
            messages = messages[:limit]
        return messages
    
    def get_message_history(self, conversation_id: str,
                           max_messages: int = 20) -> List[Dict]:
        """
        LLM用のメッセージ履歴を取得（フォーマット済み）
        
        Args:
            conversation_id: 会話ID
            max_messages: 最大取得件数
            
        Returns:
            role/content形式の辞書リスト
        """
        messages = self.get_messages(conversation_id)
        recent_messages = messages[-max_messages:] if len(messages) > max_messages else messages
        
        return [
            {"role": m.role.value, "content": m.get_text()}
            for m in recent_messages
        ]
    
    # ========== トピック管理 ==========
    
    def create_topic(self, name: str, 
                    description: Optional[str] = None,
                    color: str = "#3B82F6",
                    parent_id: Optional[str] = None) -> Topic:
        """
        新規トピックを作成
        
        Args:
            name: トピック名
            description: 説明
            color: 表示色
            parent_id: 親トピックID
            
        Returns:
            作成されたTopicインスタンス
        """
        topic = Topic(
            name=name,
            description=description,
            color=color,
            parent_id=parent_id
        )
        
        self._topics[topic.id] = topic
        self._save_topics()
        
        return topic
    
    def get_topic(self, topic_id: str) -> Optional[Topic]:
        """
        指定IDのトピックを取得
        
        Args:
            topic_id: トピックID
            
        Returns:
            Topicインスタンス、存在しない場合はNone
        """
        return self._topics.get(topic_id)
    
    def get_all_topics(self) -> List[Topic]:
        """
        すべてのトピックを取得
        
        Returns:
            Topicインスタンスのリスト
        """
        return list(self._topics.values())
    
    def update_topic(self, topic_id: str,
                    name: Optional[str] = None,
                    description: Optional[str] = None,
                    color: Optional[str] = None) -> Optional[Topic]:
        """
        トピックを更新
        
        Args:
            topic_id: トピックID
            name: 新しい名前
            description: 新しい説明
            color: 新しい色
            
        Returns:
            更新されたTopicインスタンス
        """
        topic = self.get_topic(topic_id)
        if not topic:
            return None
        
        if name is not None:
            topic.name = name
        if description is not None:
            topic.description = description
        if color is not None:
            topic.color = color
        
        self._save_topics()
        return topic
    
    def delete_topic(self, topic_id: str) -> bool:
        """
        トピックを削除
        
        Args:
            topic_id: 削除するトピックID
            
        Returns:
            削除成功したかどうか
        """
        if topic_id not in self._topics:
            return False
        
        # 関連する会話のtopic_idをクリア
        for conversation in self._conversations.values():
            if conversation.topic_id == topic_id:
                conversation.topic_id = None
                self._save_conversation(conversation)
        
        del self._topics[topic_id]
        self._save_topics()
        return True
    
    # ========== 会話一覧取得 ==========

    _SORT_KEYS = {
        "created_at": lambda c: c.created_at,
        "updated_at": lambda c: c.updated_at,
        "title": lambda c: c.title.lower(),
        "message_count": lambda c: c.message_count,
    }

    def list_conversations(self,
                          user_id: Optional[str] = None,
                          topic_id: Optional[str] = None,
                          status: Optional[ConversationStatus] = None,
                          search_query: Optional[str] = None,
                          date_from: Optional[datetime] = None,
                          date_to: Optional[datetime] = None,
                          sort_by: str = "updated_at",
                          ascending: bool = False,
                          limit: Optional[int] = None,
                          offset: int = 0) -> List[Conversation]:
        """
        会話一覧を取得（フィルタ・ソート対応）

        Args:
            user_id: ユーザーIDでフィルタ
            topic_id: トピックIDでフィルタ
            status: ステータスでフィルタ
            search_query: タイトル検索
            date_from: 開始日でフィルタ
            date_to: 終了日でフィルタ
            sort_by: ソート項目（created_at/updated_at/title/message_count）
            ascending: 昇順ソート
            limit: 取得件数上限
            offset: スキップ件数

        Returns:
            フィルタ済みConversationインスタンスのリスト
        """
        conversations = list(self._conversations.values())

        # フィルタリング
        if user_id:
            conversations = [c for c in conversations if c.user_id == user_id]

        if topic_id is not None:  # Noneでない場合のみフィルタ（Noneは「トピックなし」として扱う）
            conversations = [c for c in conversations if c.topic_id == topic_id]

        if status:
            conversations = [c for c in conversations if c.status == status]

        if search_query:
            query = search_query.lower()
            conversations = [
                c for c in conversations
                if query in c.title.lower() or (c.summary and query in c.summary.lower())
            ]

        if date_from:
            conversations = [c for c in conversations if c.created_at >= date_from]

        if date_to:
            conversations = [c for c in conversations if c.created_at <= date_to]

        # ソート
        sort_func = self._SORT_KEYS.get(sort_by, self._SORT_KEYS["updated_at"])
        conversations.sort(key=sort_func, reverse=not ascending)

        # ページネーション
        conversations = conversations[offset:]
        if limit:
            conversations = conversations[:limit]

        return conversations
    
    def get_recent_conversations(self, 
                                user_id: Optional[str] = None,
                                days: int = 7,
                                limit: int = 10) -> List[Conversation]:
        """
        最近の会話を取得
        
        Args:
            user_id: ユーザーID
            days: 何日以内か
            limit: 取得件数上限
            
        Returns:
            Conversationインスタンスのリスト
        """
        date_from = datetime.now() - timedelta(days=days)
        return self.list_conversations(
            user_id=user_id,
            date_from=date_from,
            limit=limit
        )
    
    def search_conversations(self, query: str,
                            user_id: Optional[str] = None,
                            limit: int = 20) -> List[Conversation]:
        """
        会話を検索
        
        Args:
            query: 検索クエリ
            user_id: ユーザーID
            limit: 取得件数上限
            
        Returns:
            検索結果のConversationインスタンスのリスト
        """
        return self.list_conversations(
            user_id=user_id,
            search_query=query,
            limit=limit
        )
    
    # ========== 統計情報 ==========
    
    def get_stats(self, user_id: Optional[str] = None) -> Dict:
        """
        会話統計情報を取得
        
        Args:
            user_id: ユーザーID（指定時はそのユーザーのみ）
            
        Returns:
            統計情報の辞書
        """
        conversations = list(self._conversations.values())
        if user_id:
            conversations = [c for c in conversations if c.user_id == user_id]
        
        total_messages = sum(c.message_count for c in conversations)
        active_count = sum(1 for c in conversations if c.status == ConversationStatus.ACTIVE)
        
        today = datetime.now().date()
        today_count = sum(
            1 for c in conversations 
            if c.created_at.date() == today
        )
        
        return {
            "total_conversations": len(conversations),
            "active_conversations": active_count,
            "total_messages": total_messages,
            "today_conversations": today_count,
            "average_messages_per_conversation": total_messages / len(conversations) if conversations else 0
        }
    
    # ========== セッション管理 ==========
    
    def close_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """
        会話を終了
        
        Args:
            conversation_id: 会話ID
            
        Returns:
            更新されたConversationインスタンス
        """
        return self.update_conversation(
            conversation_id=conversation_id,
            status=ConversationStatus.CLOSED
        )
    
    def archive_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """
        会話をアーカイブ
        
        Args:
            conversation_id: 会話ID
            
        Returns:
            更新されたConversationインスタンス
        """
        return self.update_conversation(
            conversation_id=conversation_id,
            status=ConversationStatus.ARCHIVED
        )
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """
        会話を削除
        
        Args:
            conversation_id: 削除する会話ID
            
        Returns:
            削除成功したかどうか
        """
        if conversation_id not in self._conversations:
            return False
        
        # ファイルを削除
        conv_file = self._get_conversation_file(conversation_id)
        msg_file = self._get_messages_file(conversation_id)
        
        try:
            if conv_file.exists():
                conv_file.unlink()
            if msg_file.exists():
                msg_file.unlink()
        except Exception as e:
            logger.error(f"Failed to delete conversation files: {e}")
            return False
        
        # キャッシュから削除
        del self._conversations[conversation_id]
        if conversation_id in self._messages:
            del self._messages[conversation_id]
        
        return True
