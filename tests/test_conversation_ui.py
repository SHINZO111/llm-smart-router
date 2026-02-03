#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Smart Router - Conversation UI Tests
会話履歴管理 UIコンポーネントのテストスイート

【テスト対象】
- ConversationListWidget
- ConversationSidebar
- MessageBubble
- ConversationToolbar

使用方法:
    python test_conversation_ui.py
    python test_conversation_ui.py -v  # 詳細出力

注意:
    このテストはPySide6を使用し、ヘッドレスモードで実行されます。
    CI環境ではDISPLAY環境変数が必要な場合があります。
"""

import sys
import os
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, call

# パス設定
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, 'F:\\llm-smart-router')
sys.path.insert(0, 'F:\\llm-smart-router\\src')

import unittest
from typing import Optional, List, Dict, Any

# Qtテスト用
os.environ['QT_QPA_PLATFORM'] = 'offscreen'  # ヘッドレスモード

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QPushButton, QLineEdit, QTextEdit, QLabel, QMenu,
    QListWidgetItem, QFrame, QScrollArea
)
from PySide6.QtCore import Qt, Signal, QObject, QPoint
from PySide6.QtTest import QTest
from PySide6.QtGui import QAction

# テスト対象モデル
from models.conversation import Conversation, Topic, ConversationStatus
from models.message import Message, MessageRole, MessageContent, MessageType


# ============================================================
# モック: データ層・ロジック層
# ============================================================

class MockConversationDB:
    """データベースマネージャーのモック"""
    
    def __init__(self):
        self.conversations = {}
        self.messages = {}
        self.topics = {}
        self._id_counter = 1
    
    def _next_id(self):
        id = self._id_counter
        self._id_counter += 1
        return id
    
    def create_conversation(self, title="New Conversation", topic_id=None):
        conv_id = self._next_id()
        self.conversations[conv_id] = {
            'id': conv_id,
            'title': title,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'topic_id': topic_id,
            'message_count': 0
        }
        self.messages[conv_id] = []
        return conv_id
    
    def get_conversations(self, topic_id=None, limit=100, offset=0):
        convs = list(self.conversations.values())
        if topic_id:
            convs = [c for c in convs if c['topic_id'] == topic_id]
        return sorted(convs, key=lambda x: x['updated_at'], reverse=True)[offset:offset+limit]
    
    def get_conversation(self, conv_id):
        return self.conversations.get(conv_id)
    
    def update_conversation(self, conv_id, title=None, topic_id=None):
        if conv_id in self.conversations:
            if title is not None:
                self.conversations[conv_id]['title'] = title
            if topic_id is not None:
                self.conversations[conv_id]['topic_id'] = topic_id
            self.conversations[conv_id]['updated_at'] = datetime.now().isoformat()
            return True
        return False
    
    def delete_conversation(self, conv_id):
        if conv_id in self.conversations:
            del self.conversations[conv_id]
            del self.messages[conv_id]
            return True
        return False
    
    def add_message(self, conv_id, role, content, model=None):
        if conv_id in self.messages:
            msg_id = self._next_id()
            self.messages[conv_id].append({
                'id': msg_id,
                'role': role,
                'content': content,
                'model': model,
                'timestamp': datetime.now().isoformat()
            })
            self.conversations[conv_id]['message_count'] = len(self.messages[conv_id])
            return msg_id
        return None
    
    def get_messages(self, conv_id, limit=None):
        msgs = self.messages.get(conv_id, [])
        if limit:
            msgs = msgs[-limit:]
        return msgs
    
    def search_conversations(self, query, date_from=None, date_to=None):
        results = []
        for conv in self.conversations.values():
            if query.lower() in conv['title'].lower():
                results.append(conv)
        return results
    
    def get_topics(self):
        return list(self.topics.values())
    
    def create_topic(self, name):
        topic_id = self._next_id()
        self.topics[topic_id] = {'id': topic_id, 'name': name}
        return topic_id


class MockConversationManager:
    """ConversationManager のモック"""
    
    def __init__(self):
        self.conversations = {}
        self.messages = {}
        self.topics = {}
        self._callbacks = []
    
    def create_conversation(self, user_id="", first_message=None, topic_id=None):
        conv = Conversation(
            user_id=user_id,
            title=first_message[:20] + "..." if first_message and len(first_message) > 20 else (first_message or "新規会話"),
            topic_id=topic_id
        )
        self.conversations[conv.id] = conv
        self.messages[conv.id] = []
        
        if first_message:
            self.add_message(conv.id, MessageRole.USER, first_message)
        
        return conv
    
    def get_conversation(self, conv_id):
        return self.conversations.get(conv_id)
    
    def list_conversations(self, **kwargs):
        convs = list(self.conversations.values())
        
        # フィルタ適用
        if kwargs.get('topic_id'):
            convs = [c for c in convs if c.topic_id == kwargs['topic_id']]
        if kwargs.get('search_query'):
            query = kwargs['search_query'].lower()
            convs = [c for c in convs if query in c.title.lower()]
        
        # ソート
        sort_by = kwargs.get('sort_by', 'updated_at')
        reverse = not kwargs.get('ascending', False)
        convs.sort(key=lambda c: getattr(c, sort_by), reverse=reverse)
        
        # ページネーション
        offset = kwargs.get('offset', 0)
        limit = kwargs.get('limit')
        if limit:
            convs = convs[offset:offset+limit]
        
        return convs
    
    def add_message(self, conv_id, role, text, model=None, tokens=None):
        msg = Message(
            conversation_id=conv_id,
            role=role,
            content=MessageContent(text=text),
            model=model,
            tokens=tokens
        )
        if conv_id not in self.messages:
            self.messages[conv_id] = []
        self.messages[conv_id].append(msg)
        
        if conv_id in self.conversations:
            self.conversations[conv_id].message_count = len(self.messages[conv_id])
        
        return msg
    
    def get_messages(self, conv_id, limit=None, offset=0):
        msgs = self.messages.get(conv_id, [])
        msgs = msgs[offset:]
        if limit:
            msgs = msgs[:limit]
        return msgs
    
    def delete_conversation(self, conv_id):
        if conv_id in self.conversations:
            del self.conversations[conv_id]
            if conv_id in self.messages:
                del self.messages[conv_id]
            return True
        return False
    
    def on_conversation_changed(self, callback):
        self._callbacks.append(callback)
    
    def create_topic(self, name, description=None, color=None):
        topic = Topic(name=name, description=description, color=color or "#3B82F6")
        self.topics[topic.id] = topic
        return topic
    
    def get_all_topics(self):
        return list(self.topics.values())


# ============================================================
# モック: UIコンポーネント
# ============================================================

class MockConversationItem(QWidget):
    """会話リストアイテムのモック"""
    
    clicked = Signal(str)  # conversation_id
    
    def __init__(self, conversation: Conversation, parent=None):
        super().__init__(parent)
        self.conversation = conversation
        self.conv_id = conversation.id
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        self.title_label = QLabel(self.conversation.title)
        layout.addWidget(self.title_label)
        
        self.delete_btn = QPushButton("×")
        self.delete_btn.setFixedSize(20, 20)
        layout.addWidget(self.delete_btn)
    
    def update_title(self, title: str):
        self.conversation.title = title
        self.title_label.setText(title)


class MockConversationListWidget(QWidget):
    """会話リストウィジェットのモック"""
    
    conversationSelected = Signal(str)  # conversation_id
    conversationDeleted = Signal(str)   # conversation_id
    
    def __init__(self, manager: MockConversationManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.items = {}
        self.setup_ui()
        self.load_conversations()
    
    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        
        # 検索ボックス
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("検索...")
        self.search_box.textChanged.connect(self.on_search)
        self.layout.addWidget(self.search_box)
        
        # 新規作成ボタン
        self.new_btn = QPushButton("+ 新規会話")
        self.new_btn.clicked.connect(self.on_new_conversation)
        self.layout.addWidget(self.new_btn)
        
        # リスト
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        self.layout.addWidget(self.list_widget)
    
    def load_conversations(self):
        """会話一覧をロード"""
        self.list_widget.clear()
        self.items = {}
        
        conversations = self.manager.list_conversations(limit=100)
        for conv in conversations:
            self.add_conversation_item(conv)
    
    def add_conversation_item(self, conv: Conversation):
        """会話アイテムを追加"""
        item = QListWidgetItem(conv.title)
        item.setData(Qt.UserRole, conv.id)
        self.list_widget.addItem(item)
        self.items[conv.id] = item
    
    def on_item_clicked(self, item: QListWidgetItem):
        """アイテムクリック時"""
        conv_id = item.data(Qt.UserRole)
        self.conversationSelected.emit(conv_id)
    
    def on_new_conversation(self):
        """新規会話作成"""
        conv = self.manager.create_conversation(first_message="新規会話")
        self.add_conversation_item(conv)
        self.conversationSelected.emit(conv.id)
    
    def on_search(self, text: str):
        """検索処理"""
        self.list_widget.clear()
        conversations = self.manager.list_conversations(search_query=text)
        for conv in conversations:
            self.add_conversation_item(conv)
    
    def update_conversation_title(self, conv_id: str, title: str):
        """タイトル更新"""
        if conv_id in self.items:
            self.items[conv_id].setText(title)
    
    def remove_conversation(self, conv_id: str):
        """会話を削除"""
        if conv_id in self.items:
            row = self.list_widget.row(self.items[conv_id])
            self.list_widget.takeItem(row)
            del self.items[conv_id]


class MockMessageBubble(QFrame):
    """メッセージバブルのモック"""
    
    def __init__(self, message: Message, parent=None):
        super().__init__(parent)
        self.message = message
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # ロール表示
        role_text = "🧑 あなた" if self.message.role == MessageRole.USER else "🤖 アシスタント"
        self.role_label = QLabel(role_text)
        layout.addWidget(self.role_label)
        
        # 内容
        self.content_label = QLabel(self.message.get_text())
        self.content_label.setWordWrap(True)
        layout.addWidget(self.content_label)
        
        # モデル情報
        if self.message.model:
            self.model_label = QLabel(f"Model: {self.message.model}")
            layout.addWidget(self.model_label)
        
        # スタイル設定
        if self.message.role == MessageRole.USER:
            self.setStyleSheet("background-color: #3B82F6; border-radius: 10px; padding: 10px;")
        else:
            self.setStyleSheet("background-color: #374151; border-radius: 10px; padding: 10px;")


class MockConversationView(QWidget):
    """会話表示ビューのモック"""
    
    messageSent = Signal(str, str)  # conversation_id, text
    
    def __init__(self, manager: MockConversationManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.current_conv_id = None
        self.setup_ui()
    
    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        
        # タイトル
        self.title_label = QLabel("会話を選択してください")
        self.layout.addWidget(self.title_label)
        
        # メッセージエリア
        self.scroll_area = QScrollArea()
        self.messages_widget = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.addStretch()
        self.scroll_area.setWidget(self.messages_widget)
        self.scroll_area.setWidgetResizable(True)
        self.layout.addWidget(self.scroll_area)
        
        # 入力エリア
        self.input_area = QTextEdit()
        self.input_area.setMaximumHeight(100)
        self.layout.addWidget(self.input_area)
        
        self.send_btn = QPushButton("送信")
        self.send_btn.clicked.connect(self.on_send)
        self.layout.addWidget(self.send_btn)
    
    def load_conversation(self, conv_id: str):
        """会話をロード"""
        self.current_conv_id = conv_id
        conv = self.manager.get_conversation(conv_id)
        
        if conv:
            self.title_label.setText(conv.title)
            
            # メッセージクリア
            while self.messages_layout.count() > 1:
                item = self.messages_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            # メッセージ追加
            messages = self.manager.get_messages(conv_id)
            for msg in messages:
                bubble = MockMessageBubble(msg)
                self.messages_layout.insertWidget(
                    self.messages_layout.count() - 1,
                    bubble
                )
    
    def on_send(self):
        """送信処理"""
        if not self.current_conv_id:
            return
        
        text = self.input_area.toPlainText().strip()
        if text:
            self.messageSent.emit(self.current_conv_id, text)
            self.input_area.clear()
            self.load_conversation(self.current_conv_id)  # 再ロード
    
    def add_message_bubble(self, message: Message):
        """メッセージバブルを追加"""
        bubble = MockMessageBubble(message)
        self.messages_layout.insertWidget(
            self.messages_layout.count() - 1,
            bubble
        )


class MockConversationToolbar(QWidget):
    """会話ツールバーのモック"""
    
    newConversation = Signal()
    exportConversation = Signal()
    importConversation = Signal()
    deleteConversation = Signal()
    searchRequested = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        
        self.new_btn = QPushButton("📝 新規")
        self.new_btn.clicked.connect(self.newConversation.emit)
        layout.addWidget(self.new_btn)
        
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("検索...")
        self.search_box.returnPressed.connect(
            lambda: self.searchRequested.emit(self.search_box.text())
        )
        layout.addWidget(self.search_box)
        
        self.export_btn = QPushButton("📤 エクスポート")
        self.export_btn.clicked.connect(self.exportConversation.emit)
        layout.addWidget(self.export_btn)
        
        self.import_btn = QPushButton("📥 インポート")
        self.import_btn.clicked.connect(self.importConversation.emit)
        layout.addWidget(self.import_btn)
        
        self.delete_btn = QPushButton("🗑️ 削除")
        self.delete_btn.clicked.connect(self.deleteConversation.emit)
        layout.addWidget(self.delete_btn)


# ============================================================
# UIテストクラス
# ============================================================

class TestConversationListWidget(unittest.TestCase):
    """ConversationListWidget のテスト"""
    
    @classmethod
    def setUpClass(cls):
        """テストクラス全体の前準備"""
        cls.app = QApplication.instance() or QApplication(sys.argv)
    
    def setUp(self):
        """各テスト前の準備"""
        self.manager = MockConversationManager()
        
        # テストデータ作成
        for i in range(5):
            conv = self.manager.create_conversation(
                first_message=f"Test conversation {i}"
            )
            self.manager.add_message(conv.id, MessageRole.USER, f"Hello {i}")
        
        self.widget = MockConversationListWidget(self.manager)
    
    def test_initial_load(self):
        """初期ロードテスト"""
        self.assertEqual(self.widget.list_widget.count(), 5)
    
    def test_conversation_selection(self):
        """会話選択テスト"""
        callback = Mock()
        self.widget.conversationSelected.connect(callback)
        
        # 最初のアイテムをクリック
        first_item = self.widget.list_widget.item(0)
        self.widget.list_widget.itemClicked.emit(first_item)
        
        callback.assert_called_once()
    
    def test_new_conversation(self):
        """新規会話作成テスト"""
        initial_count = self.widget.list_widget.count()
        
        callback = Mock()
        self.widget.conversationSelected.connect(callback)
        
        self.widget.on_new_conversation()
        
        self.assertEqual(self.widget.list_widget.count(), initial_count + 1)
        callback.assert_called_once()
    
    def test_search(self):
        """検索機能テスト"""
        self.widget.search_box.setText("conversation 1")
        self.widget.on_search("conversation 1")
        
        # 結果がフィルタされる
        self.assertLess(self.widget.list_widget.count(), 5)
    
    def test_update_title(self):
        """タイトル更新テスト"""
        first_item = self.widget.list_widget.item(0)
        conv_id = first_item.data(Qt.UserRole)
        
        self.widget.update_conversation_title(conv_id, "Updated Title")
        
        self.assertEqual(first_item.text(), "Updated Title")
    
    def test_remove_conversation(self):
        """会話削除テスト"""
        first_item = self.widget.list_widget.item(0)
        conv_id = first_item.data(Qt.UserRole)
        initial_count = self.widget.list_widget.count()
        
        self.widget.remove_conversation(conv_id)
        
        self.assertEqual(self.widget.list_widget.count(), initial_count - 1)
        self.assertNotIn(conv_id, self.widget.items)


class TestConversationView(unittest.TestCase):
    """ConversationView のテスト"""
    
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)
    
    def setUp(self):
        self.manager = MockConversationManager()
        self.conv = self.manager.create_conversation(first_message="Test")
        self.manager.add_message(self.conv.id, MessageRole.USER, "Hello")
        self.manager.add_message(self.conv.id, MessageRole.ASSISTANT, "Hi!")
        
        self.view = MockConversationView(self.manager)
    
    def test_load_conversation(self):
        """会話ロードテスト"""
        self.view.load_conversation(self.conv.id)
        
        self.assertEqual(self.view.current_conv_id, self.conv.id)
        self.assertEqual(self.view.title_label.text(), self.conv.title)
    
    def test_message_bubble_creation(self):
        """メッセージバブル作成テスト"""
        self.view.load_conversation(self.conv.id)
        
        # メッセージバブルが作成されている
        message_widgets = [
            self.view.messages_layout.itemAt(i).widget()
            for i in range(self.view.messages_layout.count() - 1)
        ]
        self.assertEqual(len(message_widgets), 2)
    
    def test_send_message(self):
        """メッセージ送信テスト"""
        self.view.load_conversation(self.conv.id)
        
        callback = Mock()
        self.view.messageSent.connect(callback)
        
        self.view.input_area.setPlainText("New message")
        self.view.on_send()
        
        callback.assert_called_once_with(self.conv.id, "New message")
    
    def test_send_empty_message(self):
        """空メッセージ送信テスト"""
        self.view.load_conversation(self.conv.id)
        
        callback = Mock()
        self.view.messageSent.connect(callback)
        
        self.view.input_area.setPlainText("   ")
        self.view.on_send()
        
        callback.assert_not_called()


class TestMessageBubble(unittest.TestCase):
    """MessageBubble のテスト"""
    
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)
    
    def test_user_message_display(self):
        """ユーザーメッセージ表示テスト"""
        msg = Message(
            conversation_id="test",
            role=MessageRole.USER,
            content=MessageContent(text="Hello")
        )
        
        bubble = MockMessageBubble(msg)
        
        self.assertIn("あなた", bubble.role_label.text())
        self.assertEqual(bubble.content_label.text(), "Hello")
    
    def test_assistant_message_display(self):
        """アシスタントメッセージ表示テスト"""
        msg = Message(
            conversation_id="test",
            role=MessageRole.ASSISTANT,
            content=MessageContent(text="Hi there!"),
            model="gpt-4"
        )
        
        bubble = MockMessageBubble(msg)
        
        self.assertIn("アシスタント", bubble.role_label.text())
        self.assertEqual(bubble.content_label.text(), "Hi there!")
        self.assertEqual(bubble.model_label.text(), "Model: gpt-4")
    
    def test_message_styling(self):
        """メッセージスタイルテスト"""
        user_msg = Message(role=MessageRole.USER, content=MessageContent(text="Test"))
        assistant_msg = Message(role=MessageRole.ASSISTANT, content=MessageContent(text="Test"))
        
        user_bubble = MockMessageBubble(user_msg)
        assistant_bubble = MockMessageBubble(assistant_msg)
        
        # スタイルが異なることを確認
        self.assertNotEqual(
            user_bubble.styleSheet(),
            assistant_bubble.styleSheet()
        )


class TestConversationToolbar(unittest.TestCase):
    """ConversationToolbar のテスト"""
    
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)
    
    def setUp(self):
        self.toolbar = MockConversationToolbar()
    
    def test_new_conversation_signal(self):
        """新規会話シグナルテスト"""
        callback = Mock()
        self.toolbar.newConversation.connect(callback)
        
        self.toolbar.new_btn.click()
        
        callback.assert_called_once()
    
    def test_export_signal(self):
        """エクスポートシグナルテスト"""
        callback = Mock()
        self.toolbar.exportConversation.connect(callback)
        
        self.toolbar.export_btn.click()
        
        callback.assert_called_once()
    
    def test_import_signal(self):
        """インポートシグナルテスト"""
        callback = Mock()
        self.toolbar.importConversation.connect(callback)
        
        self.toolbar.import_btn.click()
        
        callback.assert_called_once()
    
    def test_delete_signal(self):
        """削除シグナルテスト"""
        callback = Mock()
        self.toolbar.deleteConversation.connect(callback)
        
        self.toolbar.delete_btn.click()
        
        callback.assert_called_once()
    
    def test_search_signal(self):
        """検索シグナルテスト"""
        callback = Mock()
        self.toolbar.searchRequested.connect(callback)
        
        self.toolbar.search_box.setText("test query")
        self.toolbar.search_box.returnPressed.emit()
        
        callback.assert_called_once_with("test query")


class TestConversationIntegration(unittest.TestCase):
    """統合テスト"""
    
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)
    
    def setUp(self):
        self.manager = MockConversationManager()
        self.list_widget = MockConversationListWidget(self.manager)
        self.view = MockConversationView(self.manager)
        self.toolbar = MockConversationToolbar()
        
        # シグナル接続
        self.list_widget.conversationSelected.connect(self.view.load_conversation)
        self.toolbar.newConversation.connect(self.list_widget.on_new_conversation)
        self.toolbar.deleteConversation.connect(self._delete_current)
    
    def _delete_current(self):
        """現在の会話を削除"""
        if self.view.current_conv_id:
            self.manager.delete_conversation(self.view.current_conv_id)
            self.list_widget.remove_conversation(self.view.current_conv_id)
    
    def test_full_workflow(self):
        """完全なワークフローテスト"""
        # 1. 新規会話作成
        self.toolbar.new_btn.click()
        self.assertEqual(self.list_widget.list_widget.count(), 1)
        
        # 2. 会話選択（最初のものを取得）
        first_item = self.list_widget.list_widget.item(0)
        conv_id = first_item.data(Qt.UserRole)
        self.list_widget.list_widget.itemClicked.emit(first_item)
        
        self.assertEqual(self.view.current_conv_id, conv_id)
        
        # 3. メッセージ送信
        self.view.input_area.setPlainText("Test message")
        self.view.on_send()
        
        messages = self.manager.get_messages(conv_id)
        self.assertEqual(len(messages), 1)
    
    def test_search_and_select(self):
        """検索と選択の統合テスト"""
        # 複数の会話を作成
        for i in range(3):
            self.manager.create_conversation(first_message=f"Unique topic {i}")
        
        self.list_widget.load_conversations()
        initial_count = self.list_widget.list_widget.count()
        
        # 検索
        self.list_widget.search_box.setText("Unique topic 1")
        self.list_widget.on_search("Unique topic 1")
        
        # フィルタ結果が1件
        self.assertEqual(self.list_widget.list_widget.count(), 1)


# ============================================================
# テスト実行エントリーポイント
# ============================================================

if __name__ == '__main__':
    # テストスイート作成
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # テストクラス追加
    suite.addTests(loader.loadTestsFromTestCase(TestConversationListWidget))
    suite.addTests(loader.loadTestsFromTestCase(TestConversationView))
    suite.addTests(loader.loadTestsFromTestCase(TestMessageBubble))
    suite.addTests(loader.loadTestsFromTestCase(TestConversationToolbar))
    suite.addTests(loader.loadTestsFromTestCase(TestConversationIntegration))
    
    # 実行
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 終了コード
    sys.exit(0 if result.wasSuccessful() else 1)
