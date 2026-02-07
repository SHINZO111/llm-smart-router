#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Smart Router - Conversation History Tests
会話履歴管理のテストスイート

【テスト対象】
1. データ層 (db_manager.py) - SQLite CRUD操作
2. ロジック層 (conversation_manager.py) - 会話管理、タイトル生成

使用方法:
    python test_conversation.py
    python test_conversation.py -v  # 詳細出力
"""

import sys
import os
import json
import tempfile
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# パス設定
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
_src = str(Path(__file__).parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

import unittest
from typing import Optional, List, Dict, Any

# テスト対象モジュール
from conversation.db_manager import ConversationDB, get_db
from conversation.conversation_manager import ConversationManager
from models.conversation import Conversation, Topic, ConversationStatus
from models.message import Message, MessageRole, MessageContent, MessageType


# ============================================================
# モック: TitleGenerator
# ============================================================

class MockTitleGenerator:
    """テスト用タイトル生成器モック"""
    
    def generate(self, text: str) -> str:
        """最初の20文字をタイトルとして返す"""
        if not text:
            return "新規会話"
        title = text[:20].strip()
        if len(text) > 20:
            title += "..."
        return title


# ============================================================
# データ層テスト (ConversationDB)
# ============================================================

class TestConversationDB(unittest.TestCase):
    """ConversationDB のユニットテスト"""
    
    def setUp(self):
        """各テスト前に実行 - 一時DBを作成"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = ConversationDB(str(self.db_path))
    
    def tearDown(self):
        """各テスト後に実行 - クリーンアップ"""
        self.temp_dir.cleanup()
    
    # ---------- Topic CRUD Tests ----------
    
    def test_create_topic(self):
        """トピック作成テスト"""
        topic_id = self.db.create_topic("Test Topic")
        self.assertIsInstance(topic_id, int)
        self.assertGreater(topic_id, 0)
    
    def test_get_topics(self):
        """トピック一覧取得テスト"""
        # 初期状態はデフォルトトピックが存在
        topics = self.db.get_topics()
        self.assertGreaterEqual(len(topics), 3)  # General, Development, Research
        
        # 新規トピック追加
        self.db.create_topic("Custom Topic")
        topics = self.db.get_topics()
        topic_names = [t['name'] for t in topics]
        self.assertIn("Custom Topic", topic_names)
    
    def test_get_topic_by_name(self):
        """トピック名での取得テスト"""
        self.db.create_topic("Unique Topic")
        topic = self.db.get_topic_by_name("Unique Topic")
        self.assertIsNotNone(topic)
        self.assertEqual(topic['name'], "Unique Topic")
        
        # 存在しない場合
        not_found = self.db.get_topic_by_name("NonExistent")
        self.assertIsNone(not_found)
    
    def test_delete_topic(self):
        """トピック削除テスト"""
        topic_id = self.db.create_topic("ToDelete")
        self.assertTrue(self.db.delete_topic(topic_id))
        self.assertIsNone(self.db.get_topic_by_name("ToDelete"))
        
        # 存在しないIDを削除
        self.assertFalse(self.db.delete_topic(99999))
    
    # ---------- Conversation CRUD Tests ----------
    
    def test_create_conversation(self):
        """会話作成テスト"""
        conv_id = self.db.create_conversation("Test Conversation")
        self.assertIsInstance(conv_id, int)
        
        # トピック付きで作成
        topic_id = self.db.create_topic("Test Topic")
        conv_id2 = self.db.create_conversation("With Topic", topic_id=topic_id)
        conv = self.db.get_conversation(conv_id2)
        self.assertEqual(conv['topic_id'], topic_id)
    
    def test_get_conversation(self):
        """会話取得テスト"""
        conv_id = self.db.create_conversation("My Conversation")
        conv = self.db.get_conversation(conv_id)
        
        self.assertIsNotNone(conv)
        self.assertEqual(conv['title'], "My Conversation")
        self.assertIn('created_at', conv)
        self.assertIn('updated_at', conv)
        
        # 存在しない会話
        self.assertIsNone(self.db.get_conversation(99999))
    
    def test_get_conversations(self):
        """会話一覧取得テスト"""
        # 複数作成
        for i in range(5):
            self.db.create_conversation(f"Conversation {i}")
        
        convs = self.db.get_conversations(limit=3)
        self.assertEqual(len(convs), 3)
        
        # オフセット
        convs_offset = self.db.get_conversations(limit=3, offset=3)
        self.assertEqual(len(convs_offset), 2)
    
    def test_update_conversation(self):
        """会話更新テスト"""
        conv_id = self.db.create_conversation("Original Title")
        
        # タイトル更新
        self.assertTrue(self.db.update_conversation(conv_id, title="Updated Title"))
        conv = self.db.get_conversation(conv_id)
        self.assertEqual(conv['title'], "Updated Title")
        
        # トピック更新
        topic_id = self.db.create_topic("New Topic")
        self.db.update_conversation(conv_id, topic_id=topic_id)
        conv = self.db.get_conversation(conv_id)
        self.assertEqual(conv['topic_id'], topic_id)
    
    def test_delete_conversation(self):
        """会話削除テスト"""
        conv_id = self.db.create_conversation("To Delete")
        
        # 削除前にメッセージを追加
        self.db.add_message(conv_id, "user", "Test message")
        messages_before = self.db.get_messages(conv_id)
        self.assertEqual(len(messages_before), 1)
        
        # 会話を削除
        self.assertTrue(self.db.delete_conversation(conv_id))
        self.assertIsNone(self.db.get_conversation(conv_id))
        
        # メッセージも連動削除されることを確認（削除後は空）
        messages_after = self.db.get_messages(conv_id)
        self.assertEqual(len(messages_after), 0)
    
    # ---------- Message CRUD Tests ----------
    
    def test_add_message(self):
        """メッセージ追加テスト"""
        conv_id = self.db.create_conversation("Test")
        
        msg_id = self.db.add_message(conv_id, "user", "Hello", model="gpt-4")
        self.assertIsInstance(msg_id, int)
        
        # メッセージ取得
        messages = self.db.get_messages(conv_id)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['role'], "user")
        self.assertEqual(messages[0]['content'], "Hello")
        self.assertEqual(messages[0]['model'], "gpt-4")
    
    def test_get_messages_with_limit(self):
        """メッセージ取得（制限付き）テスト"""
        conv_id = self.db.create_conversation("Test")
        
        for i in range(10):
            self.db.add_message(conv_id, "user", f"Message {i}")
        
        messages = self.db.get_messages(conv_id, limit=5)
        self.assertEqual(len(messages), 5)
    
    def test_update_message(self):
        """メッセージ更新テスト"""
        conv_id = self.db.create_conversation("Test")
        msg_id = self.db.add_message(conv_id, "user", "Original")
        
        self.assertTrue(self.db.update_message(msg_id, "Updated"))
        msg = self.db.get_message(msg_id)
        self.assertEqual(msg['content'], "Updated")
    
    def test_delete_message(self):
        """メッセージ削除テスト"""
        conv_id = self.db.create_conversation("Test")
        msg_id = self.db.add_message(conv_id, "user", "To Delete")
        
        self.assertTrue(self.db.delete_message(msg_id))
        self.assertIsNone(self.db.get_message(msg_id))
    
    # ---------- Search Tests ----------
    
    def test_search_conversations(self):
        """会話検索テスト"""
        conv1 = self.db.create_conversation("Python Programming")
        conv2 = self.db.create_conversation("JavaScript Guide")
        
        self.db.add_message(conv1, "user", "Python is great")
        self.db.add_message(conv2, "user", "JavaScript basics")
        
        results = self.db.search_conversations("Python")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], "Python Programming")
    
    def test_search_messages(self):
        """メッセージ検索テスト"""
        conv_id = self.db.create_conversation("Test")
        self.db.add_message(conv_id, "user", "Search this keyword")
        self.db.add_message(conv_id, "assistant", "No match here")
        
        results = self.db.search_messages("keyword")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['role'], "user")
    
    def test_search_with_filters(self):
        """フィルタ付き検索テスト"""
        conv_id = self.db.create_conversation("Test")
        self.db.add_message(conv_id, "user", "User message test")
        self.db.add_message(conv_id, "assistant", "Assistant response")
        
        # ロールでフィルタ
        results = self.db.search_messages("test", role="user")
        self.assertEqual(len(results), 1)
        
        # 日付でフィルタ（広い範囲で検索）
        # タイミング問題を回避するため、実際の現在時刻を基準に余裕を持った範囲を設定
        now = datetime.now()
        future = now + timedelta(days=1)
        past = now - timedelta(days=1)
        
        results = self.db.search_messages("test", date_to=future, date_from=past)
        self.assertGreaterEqual(len(results), 1, 
            f"Expected at least 1 result with date range {past} to {future}")
    
    # ---------- Statistics Tests ----------
    
    def test_get_stats(self):
        """統計情報取得テスト"""
        # 初期状態
        stats = self.db.get_stats()
        self.assertIn('total_conversations', stats)
        self.assertIn('total_messages', stats)
        self.assertIn('total_topics', stats)
        self.assertIn('messages_by_role', stats)
        
        # データ追加後
        conv_id = self.db.create_conversation("Stats Test")
        self.db.add_message(conv_id, "user", "Test")
        self.db.add_message(conv_id, "assistant", "Response")
        
        stats = self.db.get_stats()
        self.assertGreaterEqual(stats['total_conversations'], 1)
        self.assertGreaterEqual(stats['total_messages'], 2)
        self.assertIn('user', stats['messages_by_role'])
        self.assertIn('assistant', stats['messages_by_role'])
    
    def test_get_conversation_with_messages(self):
        """会話とメッセージ一括取得テスト"""
        conv_id = self.db.create_conversation("Full Test")
        self.db.add_message(conv_id, "user", "Q1")
        self.db.add_message(conv_id, "assistant", "A1")
        self.db.add_message(conv_id, "user", "Q2")
        
        full = self.db.get_conversation_with_messages(conv_id)
        self.assertIsNotNone(full)
        self.assertEqual(len(full['messages']), 3)
        self.assertEqual(full['messages'][0]['role'], 'user')


# ============================================================
# ロジック層テスト (ConversationManager)
# ============================================================

class TestConversationManager(unittest.TestCase):
    """ConversationManager のユニットテスト"""
    
    def setUp(self):
        """各テスト前に実行"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage_path = Path(self.temp_dir.name) / "conversations"
        self.title_gen = MockTitleGenerator()
        self.manager = ConversationManager(
            storage_path=str(self.storage_path),
            title_generator=self.title_gen
        )
    
    def tearDown(self):
        """各テスト後に実行"""
        self.temp_dir.cleanup()
    
    # ---------- Session Management Tests ----------
    
    def test_create_conversation(self):
        """会話作成テスト"""
        conv = self.manager.create_conversation(
            user_id="user123",
            first_message="This is a test message about Python programming"
        )
        
        self.assertIsNotNone(conv)
        self.assertEqual(conv.user_id, "user123")
        self.assertEqual(conv.status, ConversationStatus.ACTIVE)
        self.assertEqual(conv.message_count, 1)  # 最初のメッセージ含む
        self.assertTrue(conv.title.startswith("This is a test messa"))
    
    def test_start_session(self):
        """セッション開始テスト"""
        conv = self.manager.start_session(
            user_id="user456",
            initial_message="Hello!"
        )
        
        self.assertIsNotNone(conv)
        self.assertEqual(conv.user_id, "user456")
        
        messages = self.manager.get_messages(conv.id)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].get_text(), "Hello!")
    
    def test_get_conversation(self):
        """会話取得テスト"""
        created = self.manager.create_conversation()
        fetched = self.manager.get_conversation(created.id)
        
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.id, created.id)
        
        # 存在しない会話
        self.assertIsNone(self.manager.get_conversation("non-existent-id"))
    
    def test_resume_session(self):
        """セッション再開テスト"""
        conv = self.manager.create_conversation()
        conv.status = ConversationStatus.PAUSED
        self.manager._save_conversation(conv)
        
        resumed = self.manager.resume_session(conv.id)
        self.assertIsNotNone(resumed)
        self.assertEqual(resumed.status, ConversationStatus.ACTIVE)
    
    def test_update_conversation(self):
        """会話更新テスト"""
        conv = self.manager.create_conversation(first_message="Old Title Conversation")
        
        updated = self.manager.update_conversation(
            conv.id,
            title="New Title",
            status=ConversationStatus.CLOSED
        )
        
        self.assertIsNotNone(updated)
        self.assertEqual(updated.title, "New Title")
        self.assertEqual(updated.status, ConversationStatus.CLOSED)
    
    # ---------- Message Management Tests ----------
    
    def test_add_message(self):
        """メッセージ追加テスト"""
        conv = self.manager.create_conversation()
        
        msg = self.manager.add_message(
            conv.id,
            role=MessageRole.ASSISTANT,
            text="This is a response",
            model="claude-3-opus",
            tokens=150
        )
        
        self.assertIsNotNone(msg)
        self.assertEqual(msg.role, MessageRole.ASSISTANT)
        self.assertEqual(msg.model, "claude-3-opus")
        self.assertEqual(msg.tokens, 150)
        
        # 会話のメッセージカウント更新確認
        updated_conv = self.manager.get_conversation(conv.id)
        self.assertEqual(updated_conv.message_count, 1)
    
    def test_get_messages(self):
        """メッセージ一覧取得テスト"""
        conv = self.manager.create_conversation()
        
        for i in range(5):
            self.manager.add_message(conv.id, MessageRole.USER, f"Q{i}")
            self.manager.add_message(conv.id, MessageRole.ASSISTANT, f"A{i}")
        
        messages = self.manager.get_messages(conv.id)
        self.assertEqual(len(messages), 10)
        
        # 制限付き取得
        limited = self.manager.get_messages(conv.id, limit=5)
        self.assertEqual(len(limited), 5)
    
    def test_get_message_history(self):
        """LLM用履歴取得テスト"""
        conv = self.manager.create_conversation()
        self.manager.add_message(conv.id, MessageRole.USER, "Hello")
        self.manager.add_message(conv.id, MessageRole.ASSISTANT, "Hi there!")
        self.manager.add_message(conv.id, MessageRole.USER, "How are you?")
        
        history = self.manager.get_message_history(conv.id)
        self.assertEqual(len(history), 3)
        self.assertIn("role", history[0])
        self.assertIn("content", history[0])
        self.assertEqual(history[0]["role"], "user")
    
    # ---------- Topic Management Tests ----------
    
    def test_create_topic(self):
        """トピック作成テスト"""
        topic = self.manager.create_topic(
            name="Programming",
            description="Coding related conversations",
            color="#FF5733"
        )
        
        self.assertIsNotNone(topic)
        self.assertEqual(topic.name, "Programming")
        self.assertEqual(topic.color, "#FF5733")
    
    def test_get_topic(self):
        """トピック取得テスト"""
        created = self.manager.create_topic(name="Test Topic")
        fetched = self.manager.get_topic(created.id)
        
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.id, created.id)
    
    def test_get_all_topics(self):
        """全トピック取得テスト"""
        initial_count = len(self.manager.get_all_topics())
        
        self.manager.create_topic("Topic 1")
        self.manager.create_topic("Topic 2")
        
        topics = self.manager.get_all_topics()
        self.assertEqual(len(topics), initial_count + 2)
    
    def test_update_topic(self):
        """トピック更新テスト"""
        topic = self.manager.create_topic(name="Old Name")
        
        updated = self.manager.update_topic(
            topic.id,
            name="New Name",
            color="#00FF00"
        )
        
        self.assertIsNotNone(updated)
        self.assertEqual(updated.name, "New Name")
        self.assertEqual(updated.color, "#00FF00")
    
    def test_delete_topic(self):
        """トピック削除テスト"""
        topic = self.manager.create_topic(name="ToDelete")
        topic_id = topic.id
        
        # 関連する会話を作成
        conv = self.manager.create_conversation(topic_id=topic_id)
        
        self.assertTrue(self.manager.delete_topic(topic_id))
        self.assertIsNone(self.manager.get_topic(topic_id))
        
        # 会話のtopic_idがクリアされていることを確認
        updated_conv = self.manager.get_conversation(conv.id)
        self.assertIsNone(updated_conv.topic_id)
    
    # ---------- Conversation Listing Tests ----------
    
    def test_list_conversations(self):
        """会話一覧取得テスト"""
        # テストデータ作成
        for i in range(5):
            self.manager.create_conversation(user_id="user1")
        
        convs = self.manager.list_conversations(user_id="user1")
        self.assertEqual(len(convs), 5)
    
    def test_list_conversations_with_filters(self):
        """フィルタ付き会話一覧テスト"""
        topic = self.manager.create_topic(name="Filtered Topic")
        
        # first_messageからタイトルが生成される
        conv1 = self.manager.create_conversation(
            first_message="Python Chat about programming",
            topic_id=topic.id
        )
        # タイトルを明示的に更新
        self.manager.update_conversation(conv1.id, title="Python Chat")
        
        conv2 = self.manager.create_conversation(
            first_message="JavaScript Chat"
        )
        self.manager.update_conversation(conv2.id, title="JavaScript Chat")
        
        # トピックでフィルタ
        filtered = self.manager.list_conversations(topic_id=topic.id)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].id, conv1.id)
        
        # 検索クエリでフィルタ
        searched = self.manager.list_conversations(search_query="Python")
        self.assertEqual(len(searched), 1)
        self.assertEqual(searched[0].title, "Python Chat")
    
    def test_list_conversations_sorting(self):
        """会話一覧ソートテスト"""
        conv1 = self.manager.create_conversation(first_message="A conversation")
        self.manager.update_conversation(conv1.id, title="A")
        
        conv2 = self.manager.create_conversation(first_message="B conversation")
        self.manager.update_conversation(conv2.id, title="B")
        
        conv3 = self.manager.create_conversation(first_message="C conversation")
        self.manager.update_conversation(conv3.id, title="C")
        
        # タイトル昇順
        sorted_asc = self.manager.list_conversations(
            sort_by="title",
            ascending=True
        )
        self.assertEqual(sorted_asc[0].title, "A")
        
        # タイトル降順
        sorted_desc = self.manager.list_conversations(
            sort_by="title",
            ascending=False
        )
        self.assertEqual(sorted_desc[0].title, "C")
    
    def test_get_recent_conversations(self):
        """最近の会話取得テスト"""
        # 7日以内の会話
        conv1 = self.manager.create_conversation()
        
        # 古い会話（手動で日付を変更）
        conv2 = self.manager.create_conversation()
        conv2.created_at = datetime.now() - timedelta(days=10)
        self.manager._save_conversation(conv2)
        
        recent = self.manager.get_recent_conversations(days=7)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].id, conv1.id)
    
    def test_search_conversations(self):
        """会話検索テスト"""
        conv1 = self.manager.create_conversation(first_message="Python Programming tutorial")
        self.manager.update_conversation(conv1.id, title="Python Programming")
        
        conv2 = self.manager.create_conversation(first_message="JavaScript Guide")
        self.manager.update_conversation(conv2.id, title="JavaScript Guide")
        
        conv3 = self.manager.create_conversation(first_message="Ruby Tutorial")
        self.manager.update_conversation(conv3.id, title="Ruby Tutorial")
        
        results = self.manager.search_conversations("Python")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Python Programming")
    
    # ---------- Statistics Tests ----------
    
    def test_get_stats(self):
        """統計情報取得テスト"""
        # データ作成
        conv = self.manager.create_conversation(user_id="user1")
        self.manager.add_message(conv.id, MessageRole.USER, "Q1")
        self.manager.add_message(conv.id, MessageRole.ASSISTANT, "A1")
        self.manager.add_message(conv.id, MessageRole.USER, "Q2")
        
        stats = self.manager.get_stats(user_id="user1")
        
        self.assertEqual(stats["total_conversations"], 1)
        self.assertEqual(stats["total_messages"], 3)
        self.assertEqual(stats["active_conversations"], 1)
        self.assertEqual(stats["today_conversations"], 1)
        self.assertEqual(stats["average_messages_per_conversation"], 3.0)
    
    # ---------- Session Lifecycle Tests ----------
    
    def test_close_conversation(self):
        """会話終了テスト"""
        conv = self.manager.create_conversation()
        
        closed = self.manager.close_conversation(conv.id)
        self.assertIsNotNone(closed)
        self.assertEqual(closed.status, ConversationStatus.CLOSED)
    
    def test_archive_conversation(self):
        """会話アーカイブテスト"""
        conv = self.manager.create_conversation()
        
        archived = self.manager.archive_conversation(conv.id)
        self.assertIsNotNone(archived)
        self.assertEqual(archived.status, ConversationStatus.ARCHIVED)
    
    def test_delete_conversation(self):
        """会話削除テスト"""
        conv = self.manager.create_conversation()
        conv_id = conv.id
        
        # メッセージ追加
        self.manager.add_message(conv_id, MessageRole.USER, "Test")
        
        self.assertTrue(self.manager.delete_conversation(conv_id))
        self.assertIsNone(self.manager.get_conversation(conv_id))
    
    # ---------- Callback Tests ----------
    
    def test_callbacks(self):
        """コールバック機能テスト"""
        conv_callback = Mock()
        msg_callback = Mock()
        
        self.manager.on_conversation_changed(conv_callback)
        self.manager.on_message_added(msg_callback)
        
        conv = self.manager.create_conversation()
        self.assertTrue(conv_callback.called)
        
        self.manager.add_message(conv.id, MessageRole.USER, "Test")
        self.assertTrue(msg_callback.called)


# ============================================================
# JSON Handler Tests
# ============================================================

class TestConversationJSONHandler(unittest.TestCase):
    """ConversationJSONHandler のテスト"""
    
    def setUp(self):
        """テスト前準備"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = ConversationDB(str(self.db_path))
        
        # テストデータ作成
        self.conv_id = self.db.create_conversation("Export Test")
        self.db.add_message(self.conv_id, "user", "Hello")
        self.db.add_message(self.conv_id, "assistant", "Hi!", model="gpt-4")
    
    def tearDown(self):
        """テスト後クリーンアップ"""
        self.temp_dir.cleanup()
    
    def test_export_conversation(self):
        """会話エクスポートテスト"""
        from conversation.json_handler import ConversationJSONHandler
        
        handler = ConversationJSONHandler(self.db)
        data = handler.export_conversation(self.conv_id)
        
        self.assertEqual(data["version"], "1.0")
        self.assertIn("conversation", data)
        self.assertEqual(data["conversation"]["title"], "Export Test")
        self.assertEqual(len(data["conversation"]["messages"]), 2)
        self.assertIn("metadata", data)
    
    def test_import_conversation(self):
        """会話インポートテスト"""
        from conversation.json_handler import ConversationJSONHandler
        
        handler = ConversationJSONHandler(self.db)
        
        # エクスポートしてからインポート
        export_data = handler.export_conversation(self.conv_id)
        
        new_id = handler.import_conversation(export_data)
        imported = self.db.get_conversation_with_messages(new_id)
        
        self.assertIsNotNone(imported)
        self.assertEqual(imported["title"], "Export Test")
        self.assertEqual(len(imported["messages"]), 2)
    
    def test_export_import_file(self):
        """ファイルエクスポート/インポートテスト"""
        from conversation.json_handler import ConversationJSONHandler
        
        handler = ConversationJSONHandler(self.db)
        export_path = Path(self.temp_dir.name) / "export.json"
        
        # エクスポート
        handler.export_to_file(export_path, conversation_ids=[self.conv_id])
        self.assertTrue(export_path.exists())
        
        # インポート
        imported_ids = handler.import_from_file(export_path)
        self.assertEqual(len(imported_ids), 1)


# ============================================================
# テスト実行エントリーポイント
# ============================================================

if __name__ == '__main__':
    # テストスイート作成
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # テストクラス追加
    suite.addTests(loader.loadTestsFromTestCase(TestConversationDB))
    suite.addTests(loader.loadTestsFromTestCase(TestConversationManager))
    suite.addTests(loader.loadTestsFromTestCase(TestConversationJSONHandler))
    
    # 実行
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 終了コード
    sys.exit(0 if result.wasSuccessful() else 1)
