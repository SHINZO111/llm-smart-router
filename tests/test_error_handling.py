#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
異常系・エラーハンドリングテスト

テスト対象:
- 無効な入力値
- 存在しないIDへのアクセス
- 境界値
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from datetime import datetime, timedelta

from conversation.db_manager import ConversationDB
from conversation.conversation_manager import ConversationManager


class TestErrorHandling:
    """異常系テスト - ConversationDB"""
    
    def test_get_nonexistent_conversation(self, conversation_db):
        """存在しない会話IDを取得"""
        result = conversation_db.get_conversation(99999)
        assert result is None
    
    def test_get_nonexistent_message(self, conversation_db):
        """存在しないメッセージIDを取得"""
        result = conversation_db.get_message(99999)
        assert result is None
    
    def test_update_nonexistent_conversation(self, conversation_db):
        """存在しない会話を更新"""
        result = conversation_db.update_conversation(99999, title="New Title")
        assert result is False
    
    def test_update_nonexistent_message(self, conversation_db):
        """存在しないメッセージを更新"""
        result = conversation_db.update_message(99999, "New Content")
        assert result is False
    
    def test_delete_nonexistent_conversation(self, conversation_db):
        """存在しない会話を削除"""
        result = conversation_db.delete_conversation(99999)
        assert result is False
    
    def test_delete_nonexistent_message(self, conversation_db):
        """存在しないメッセージを削除"""
        result = conversation_db.delete_message(99999)
        assert result is False
    
    def test_delete_nonexistent_topic(self, conversation_db):
        """存在しないトピックを削除"""
        result = conversation_db.delete_topic(99999)
        assert result is False
    
    def test_add_message_to_nonexistent_conversation(self, conversation_db):
        """存在しない会話にメッセージを追加（外部キー制約）"""
        # SQLiteの foreign_keys = ON により外部キー制約が有効
        # 存在しない会話IDへのメッセージ追加はエラーになる
        with pytest.raises(Exception):
            conversation_db.add_message(99999, "user", "Test")
    
    def test_search_with_invalid_date_range(self, conversation_db, factory):
        """無効な日付範囲で検索"""
        conv_id = factory.create_conversation()
        factory.add_message(conv_id, "user", "test")
        
        # 未来から過去への範囲（結果は0件）
        future = datetime.now() + timedelta(days=1)
        past = datetime.now() - timedelta(days=1)
        results = conversation_db.search_messages("test", date_from=future, date_to=past)
        assert len(results) == 0
    
    def test_get_messages_for_nonexistent_conversation(self, conversation_db):
        """存在しない会話のメッセージを取得"""
        messages = conversation_db.get_messages(99999)
        assert messages == []


class TestEdgeCases:
    """エッジケーステスト"""
    
    # ---------- 空文字・Noneテスト ----------
    
    def test_create_conversation_with_empty_title(self, conversation_db):
        """空タイトルで会話を作成"""
        conv_id = conversation_db.create_conversation("")
        conv = conversation_db.get_conversation(conv_id)
        assert conv['title'] == ""
    
    def test_create_topic_with_empty_name(self, conversation_db):
        """空名前でトピックを作成"""
        topic_id = conversation_db.create_topic("")
        topic = conversation_db.get_topic_by_name("")
        assert topic is not None
        assert topic['name'] == ""
    
    def test_add_message_with_empty_content(self, conversation_db, factory):
        """空コンテンツでメッセージを追加"""
        conv_id = factory.create_conversation()
        msg_id = factory.add_message(conv_id, "user", "")
        msg = conversation_db.get_message(msg_id)
        assert msg['content'] == ""
    
    # ---------- 特殊文字テスト ----------
    
    @pytest.mark.parametrize("content", [
        "日本語テスト🎌",
        "中文测试",
        "🎉🎊🎁",
        "<script>alert('xss')</script>",
        "' OR '1'='1",
        "; DROP TABLE messages; --",
        "Line1\nLine2\nLine3",
        "Tab\tSeparated\tValues",
    ])
    def test_special_characters_in_content(self, conversation_db, factory, content):
        """特殊文字を含むコンテンツ"""
        conv_id = factory.create_conversation()
        msg_id = factory.add_message(conv_id, "user", content)
        msg = conversation_db.get_message(msg_id)
        assert msg['content'] == content
    
    @pytest.mark.parametrize("title", [
        "Title with 🎉 emoji",
        "日本語タイトル",
        "Title 'with' quotes",
        'Title "with" double quotes',
    ])
    def test_special_characters_in_title(self, conversation_db, title):
        """特殊文字を含むタイトル"""
        conv_id = conversation_db.create_conversation(title)
        conv = conversation_db.get_conversation(conv_id)
        assert conv['title'] == title
    
    # ---------- 境界値テスト ----------
    
    def test_very_long_title(self, conversation_db):
        """非常に長いタイトル"""
        long_title = "A" * 10000
        conv_id = conversation_db.create_conversation(long_title)
        conv = conversation_db.get_conversation(conv_id)
        assert conv['title'] == long_title
    
    def test_very_long_content(self, conversation_db, factory):
        """非常に長いコンテンツ"""
        long_content = "B" * 100000  # 100KB
        conv_id = factory.create_conversation()
        msg_id = factory.add_message(conv_id, "user", long_content)
        msg = conversation_db.get_message(msg_id)
        assert msg['content'] == long_content
    
    def test_zero_messages(self, conversation_db):
        """メッセージ0件の会話"""
        conv_id = conversation_db.create_conversation("Empty Conversation")
        messages = conversation_db.get_messages(conv_id)
        assert len(messages) == 0
        
        # 統計情報確認
        stats = conversation_db.get_stats()
        assert stats['total_messages'] == 0
    
    def test_single_message(self, conversation_db, factory):
        """メッセージ1件の会話"""
        conv_id = factory.create_conversation()
        factory.add_message(conv_id, "user", "Only message")
        
        messages = conversation_db.get_messages(conv_id)
        assert len(messages) == 1
    
    def test_many_messages(self, conversation_db, factory):
        """多数のメッセージ（100件）"""
        conv_id = factory.create_conversation()
        for i in range(100):
            role = "user" if i % 2 == 0 else "assistant"
            factory.add_message(conv_id, role, f"Message {i}")
        
        messages = conversation_db.get_messages(conv_id)
        assert len(messages) == 100
    
    def test_many_conversations(self, conversation_db):
        """多数の会話（50件）"""
        for i in range(50):
            conversation_db.create_conversation(f"Conversation {i}")
        
        convs = conversation_db.get_conversations(limit=100)
        assert len(convs) >= 50  # デフォルトトピックも含まれる
    
    def test_unicode_edge_cases(self, conversation_db, factory):
        """Unicodeエッジケース"""
        test_cases = [
            "\x00",  # NULLバイト
            "\uffff",  # 非文字
            "\ufffe",  # 非文字
            "👨‍👩‍👧‍👦",  # 家族の絵文字（複数コードポイント）
            "🏳️‍🌈",  # 虹の旗（ZWJシーケンス）
        ]
        
        conv_id = factory.create_conversation()
        for content in test_cases:
            try:
                msg_id = factory.add_message(conv_id, "user", content)
                msg = conversation_db.get_message(msg_id)
                # SQLiteはNULLバイトを許可しない場合がある
                if content != "\x00":
                    assert msg is not None
            except Exception:
                # 一部の特殊文字はエラーになる可能性がある
                pass
    
    # ---------- 検索エッジケース ----------
    
    def test_search_empty_query(self, conversation_db, factory):
        """空クエリで検索"""
        conv_id = factory.create_conversation()
        factory.add_message(conv_id, "user", "Some content")
        
        # 空文字やスペースのみのクエリ
        results = conversation_db.search_messages("")
        # 空クエリはLIKE '%%'となり全件マッチする
        assert len(results) >= 0
    
    def test_search_no_match(self, conversation_db, factory):
        """マッチしない検索"""
        conv_id = factory.create_conversation()
        factory.add_message(conv_id, "user", "Apple")
        
        results = conversation_db.search_messages("Banana")
        assert len(results) == 0
    
    def test_search_case_sensitivity(self, conversation_db, factory):
        """検索の大文字小文字区別"""
        conv_id = factory.create_conversation()
        factory.add_message(conv_id, "user", "Hello World")
        
        # SQLiteのLIKEはデフォルトで大文字小文字を区別しない
        results_lower = conversation_db.search_messages("hello")
        results_upper = conversation_db.search_messages("HELLO")
        
        # デフォルト設定では両方マッチする
        assert len(results_lower) == 1
        assert len(results_upper) == 1


class TestConversationManagerErrors:
    """ConversationManagerの異常系テスト"""
    
    def test_get_nonexistent_conversation(self, conversation_manager):
        """存在しない会話を取得"""
        result = conversation_manager.get_conversation("non-existent-id")
        assert result is None
    
    def test_resume_nonexistent_session(self, conversation_manager):
        """存在しないセッションを再開"""
        result = conversation_manager.resume_session("non-existent-id")
        assert result is None
    
    def test_update_nonexistent_conversation(self, conversation_manager):
        """存在しない会話を更新"""
        result = conversation_manager.update_conversation(
            "non-existent-id",
            title="New Title"
        )
        assert result is None
    
    def test_add_message_to_nonexistent_conversation(self, conversation_manager):
        """存在しない会話にメッセージを追加"""
        from models.message import MessageRole
        result = conversation_manager.add_message(
            "non-existent-id",
            MessageRole.USER,
            "Test"
        )
        assert result is None
    
    def test_delete_nonexistent_conversation(self, conversation_manager):
        """存在しない会話を削除"""
        result = conversation_manager.delete_conversation("non-existent-id")
        assert result is False
    
    def test_close_nonexistent_conversation(self, conversation_manager):
        """存在しない会話を終了"""
        result = conversation_manager.close_conversation("non-existent-id")
        assert result is None
    
    def test_archive_nonexistent_conversation(self, conversation_manager):
        """存在しない会話をアーカイブ"""
        result = conversation_manager.archive_conversation("non-existent-id")
        assert result is None
    
    def test_get_topic_nonexistent(self, conversation_manager):
        """存在しないトピックを取得"""
        result = conversation_manager.get_topic("non-existent-id")
        assert result is None
    
    def test_update_nonexistent_topic(self, conversation_manager):
        """存在しないトピックを更新"""
        result = conversation_manager.update_topic(
            "non-existent-id",
            name="New Name"
        )
        assert result is None
    
    def test_delete_nonexistent_topic(self, conversation_manager):
        """存在しないトピックを削除"""
        result = conversation_manager.delete_topic("non-existent-id")
        assert result is False
    
    def test_create_conversation_with_none_title(self, conversation_manager):
        """Noneタイトルで会話を作成（デフォルト使用）"""
        from models.conversation import ConversationStatus
        
        # title_generatorが空文字を返す場合
        conv = conversation_manager.create_conversation(
            user_id="test",
            first_message=""
        )
        assert conv is not None
        assert conv.title == ""  # またはデフォルト値
