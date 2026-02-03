#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
統合テスト

機能間の連携をテスト
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
import json
from datetime import datetime, timedelta

from conversation.db_manager import ConversationDB
from conversation.conversation_manager import ConversationManager
from models.message import MessageRole


@pytest.mark.integration
class TestIntegrationDB:
    """DBレイヤー統合テスト"""
    
    def test_full_conversation_lifecycle(self, conversation_db, factory):
        """会話の完全ライフサイクル"""
        # 1. トピック作成
        topic_id = factory.create_topic("Test Topic")
        
        # 2. 会話作成
        conv_id = conversation_db.create_conversation("Test Conv", topic_id)
        
        # 3. メッセージ追加
        for i in range(5):
            role = "user" if i % 2 == 0 else "assistant"
            factory.add_message(conv_id, role, f"Message {i}")
        
        # 4. 検索
        results = conversation_db.search_messages("Message")
        assert len(results) == 5
        
        # 5. 統計確認
        stats = conversation_db.get_stats()
        assert stats['total_conversations'] >= 1
        assert stats['total_messages'] >= 5
        
        # 6. 削除
        conversation_db.delete_conversation(conv_id)
        
        # 7. 確認
        assert conversation_db.get_conversation(conv_id) is None
        assert len(conversation_db.get_messages(conv_id)) == 0
    
    def test_topic_cascade_behavior(self, conversation_db, factory):
        """トピック削除時のカスケード動作"""
        # トピックと関連会話を作成
        topic_id = factory.create_topic("Cascade Topic")
        conv_id1 = factory.create_conversation("Conv 1", topic_id)
        conv_id2 = factory.create_conversation("Conv 2", topic_id)
        
        # トピック削除
        conversation_db.delete_topic(topic_id)
        
        # 会話は残っているがtopic_idがNULLになっている
        conv1 = conversation_db.get_conversation(conv_id1)
        conv2 = conversation_db.get_conversation(conv_id2)
        
        assert conv1 is not None
        assert conv2 is not None
        assert conv1['topic_id'] is None
        assert conv2['topic_id'] is None
    
    def test_conversation_with_messages_delete(self, conversation_db, factory):
        """メッセージ付き会話の削除"""
        # 会話とメッセージ作成
        conv_id = factory.create_conversation()
        for i in range(10):
            factory.add_message(conv_id, "user", f"Msg {i}")
        
        # 削除前確認
        assert len(conversation_db.get_messages(conv_id)) == 10
        
        # 削除
        conversation_db.delete_conversation(conv_id)
        
        # メッセージも削除されている（外部キー制約）
        assert len(conversation_db.get_messages(conv_id)) == 0
    
    def test_search_with_multiple_filters(self, conversation_db, factory):
        """複数フィルタの組み合わせ検索"""
        # テストデータ作成
        conv_id = factory.create_conversation()
        factory.add_message(conv_id, "user", "Python question")
        factory.add_message(conv_id, "assistant", "Python answer")
        factory.add_message(conv_id, "user", "JavaScript question")
        factory.add_message(conv_id, "assistant", "JavaScript answer")
        
        # 複合フィルタ
        results = conversation_db.search_messages(
            "question",
            role="user"
        )
        assert len(results) == 2
        
        # 会話ID + ロールフィルタ
        results = conversation_db.search_messages(
            "Python",
            conversation_id=conv_id,
            role="user"
        )
        assert len(results) == 1
    
    def test_date_range_search_integration(self, conversation_db, factory):
        """日付範囲検索の統合テスト"""
        # 現在の会話
        conv_id = factory.create_conversation()
        factory.add_message(conv_id, "user", "Recent message")
        
        # 日付範囲検索（十分な余裕を持った範囲で）
        now = datetime.now()
        results = conversation_db.search_messages(
            "Recent",
            date_from=now - timedelta(days=1),  # 1日前から
            date_to=now + timedelta(days=1)      # 1日後まで
        )
        assert len(results) == 1
        
        # 過去の範囲（マッチしない）
        results = conversation_db.search_messages(
            "Recent",
            date_from=now - timedelta(days=7),  # 1週間前
            date_to=now - timedelta(days=2)     # 2日前（現在より前）
        )
        assert len(results) == 0


@pytest.mark.integration
class TestIntegrationManager:
    """Managerレイヤー統合テスト"""
    
    def test_full_session_workflow(self, conversation_manager):
        """完全なセッションワークフロー"""
        from models.conversation import ConversationStatus
        
        # 1. セッション開始
        conv = conversation_manager.start_session(
            user_id="user123",
            initial_message="Hello!"
        )
        assert conv is not None
        assert conv.status == ConversationStatus.ACTIVE
        
        # 2. メッセージ交換
        conversation_manager.add_message(
            conv.id,
            MessageRole.ASSISTANT,
            "Hi there!",
            model="gpt-4"
        )
        conversation_manager.add_message(
            conv.id,
            MessageRole.USER,
            "How are you?"
        )
        
        # 3. 履歴取得
        history = conversation_manager.get_message_history(conv.id)
        assert len(history) == 3
        
        # 4. 一時停止
        conversation_manager.update_conversation(
            conv.id,
            status=ConversationStatus.PAUSED
        )
        
        # 5. 再開
        resumed = conversation_manager.resume_session(conv.id)
        assert resumed.status == ConversationStatus.ACTIVE
        
        # 6. 終了
        conversation_manager.close_conversation(conv.id)
        
        # 確認
        final = conversation_manager.get_conversation(conv.id)
        assert final.status == ConversationStatus.CLOSED
        assert final.message_count == 3
    
    def test_topic_organization_workflow(self, conversation_manager):
        """トピック整理ワークフロー"""
        # 1. トピック作成
        topic = conversation_manager.create_topic(
            name="Programming",
            description="Coding topics",
            color="#FF5733"
        )
        
        # 2. トピック付き会話作成
        conv1 = conversation_manager.create_conversation(
            first_message="Python question",
            topic_id=topic.id
        )
        conv2 = conversation_manager.create_conversation(
            first_message="JavaScript question",
            topic_id=topic.id
        )
        
        # 3. トピック別一覧
        topic_convs = conversation_manager.list_conversations(topic_id=topic.id)
        assert len(topic_convs) == 2
        
        # 4. トピック変更
        new_topic = conversation_manager.create_topic(name="Web Development")
        conversation_manager.update_conversation(conv2.id, topic_id=new_topic.id)
        
        # 確認
        old_topic_convs = conversation_manager.list_conversations(topic_id=topic.id)
        new_topic_convs = conversation_manager.list_conversations(topic_id=new_topic.id)
        assert len(old_topic_convs) == 1
        assert len(new_topic_convs) == 1
        
        # 5. トピック削除（会話は残る）
        conversation_manager.delete_topic(new_topic.id)
        updated_conv = conversation_manager.get_conversation(conv2.id)
        assert updated_conv.topic_id is None
    
    def test_search_and_list_integration(self, conversation_manager):
        """検索と一覧の統合"""
        # テストデータ作成
        topic = conversation_manager.create_topic(name="AI")
        
        for i in range(10):
            conv = conversation_manager.create_conversation(
                first_message=f"AI topic discussion {i}",
                topic_id=topic.id if i % 2 == 0 else None
            )
            conversation_manager.update_conversation(
                conv.id,
                title=f"AI Chat {i}"
            )
        
        # 検索
        search_results = conversation_manager.search_conversations("AI")
        assert len(search_results) == 10
        
        # トピックフィルタ
        topic_results = conversation_manager.list_conversations(topic_id=topic.id)
        assert len(topic_results) == 5
        
        # ソート
        sorted_by_title = conversation_manager.list_conversations(
            sort_by="title",
            ascending=True
        )
        assert sorted_by_title[0].title < sorted_by_title[-1].title
    
    def test_conversation_persistence_integration(self, conversation_manager, temp_dir):
        """永続化統合テスト（エクスポート/インポート代替）"""
        # 1. 会話作成
        conv = conversation_manager.create_conversation(
            first_message="Persistence test"
        )
        conversation_manager.add_message(
            conv.id, MessageRole.ASSISTANT, "Response"
        )
        conv_id = conv.id
        
        # 2. 新しいManagerインスタンスで再読み込み（永続化テスト）
        new_manager = ConversationManager(
            storage_path=conversation_manager.storage_path
        )
        
        # 3. 確認（first_message + 追加メッセージ = 2件）
        reloaded_conv = new_manager.get_conversation(conv_id)
        assert reloaded_conv is not None
        assert reloaded_conv.title == conv.title
        messages = new_manager.get_messages(conv_id)
        assert len(messages) == 2  # first_message + add_message
    
    def test_callback_integration(self, conversation_manager):
        """コールバック統合テスト"""
        from unittest.mock import Mock
        
        conv_callback = Mock()
        msg_callback = Mock()
        
        conversation_manager.on_conversation_changed(conv_callback)
        conversation_manager.on_message_added(msg_callback)
        
        # 会話作成（コールバック呼び出し）
        conv = conversation_manager.create_conversation()
        assert conv_callback.call_count == 1
        
        # メッセージ追加（コールバック呼び出し）
        conversation_manager.add_message(conv.id, MessageRole.USER, "Test")
        assert msg_callback.call_count == 1
        assert conv_callback.call_count == 2  # メッセージ追加でも会話変更
    
    def test_statistics_integration(self, conversation_manager):
        """統計情報統合テスト"""
        from models.conversation import ConversationStatus
        
        # データ作成
        conv1 = conversation_manager.create_conversation(user_id="user1")
        conversation_manager.add_message(conv1.id, MessageRole.USER, "Msg1")
        conversation_manager.add_message(conv1.id, MessageRole.ASSISTANT, "Msg2")
        conversation_manager.close_conversation(conv1.id)
        
        conv2 = conversation_manager.create_conversation(user_id="user1")
        conversation_manager.add_message(conv2.id, MessageRole.USER, "Msg3")
        
        # 統計取得
        stats = conversation_manager.get_stats(user_id="user1")
        
        assert stats["total_conversations"] == 2
        assert stats["total_messages"] == 3
        assert stats["active_conversations"] == 1
        assert stats["average_messages_per_conversation"] == 1.5


@pytest.mark.integration
class TestCrossLayerIntegration:
    """レイヤー間統合テスト"""
    
    def test_manager_independent_storage(self, conversation_manager):
        """Managerの独立したストレージ動作確認"""
        # Manager経由で作成
        conv = conversation_manager.create_conversation(
            first_message="Test message"
        )
        
        # Managerから確認（ファイルベース）
        manager_conv = conversation_manager.get_conversation(conv.id)
        assert manager_conv is not None
        assert "Test message" in manager_conv.title
        
        # 新しいインスタンスで再読み込み確認
        new_manager = ConversationManager(
            storage_path=conversation_manager.storage_path
        )
        reloaded_conv = new_manager.get_conversation(conv.id)
        assert reloaded_conv is not None
        assert reloaded_conv.title == manager_conv.title
    
    def test_persistence_integrity(self, conversation_manager):
        """永続化の整合性"""
        # 会話作成
        conv = conversation_manager.create_conversation()
        conv_id = conv.id
        
        # メッセージ追加
        for i in range(5):
            conversation_manager.add_message(
                conv_id, MessageRole.USER, f"Message {i}"
            )
        
        # 新しいManagerインスタンス（再読み込み）
        new_manager = ConversationManager(
            storage_path=conversation_manager.storage_path
        )
        
        # データが復元されている
        restored_conv = new_manager.get_conversation(conv_id)
        assert restored_conv is not None
        assert restored_conv.message_count == 5
        
        messages = new_manager.get_messages(conv_id)
        assert len(messages) == 5
