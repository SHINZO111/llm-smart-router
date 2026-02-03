#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
パフォーマンス・負荷テスト

注意: これらのテストは実行に時間がかかる場合があります
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
import time
from datetime import datetime, timedelta

from conversation.db_manager import ConversationDB
from conversation.conversation_manager import ConversationManager


@pytest.mark.slow
class TestPerformance:
    """パフォーマンステスト"""
    
    # ---------- 大量データテスト ----------
    
    def test_large_message_count(self, conversation_db):
        """大量メッセージ（1000件）の処理"""
        conv_id = conversation_db.create_conversation("Large Conversation")
        
        start_time = time.time()
        for i in range(1000):
            role = "user" if i % 2 == 0 else "assistant"
            conversation_db.add_message(conv_id, role, f"Message {i}")
        insert_time = time.time() - start_time
        
        # 1000件の挿入は5秒以内
        assert insert_time < 5.0, f"Insert took {insert_time}s"
        
        # 取得時間の計測
        start_time = time.time()
        messages = conversation_db.get_messages(conv_id)
        fetch_time = time.time() - start_time
        
        assert len(messages) == 1000
        # 1000件の取得は1秒以内
        assert fetch_time < 1.0, f"Fetch took {fetch_time}s"
    
    def test_large_conversation_count(self, conversation_db):
        """大量会話（500件）の処理"""
        start_time = time.time()
        for i in range(500):
            conversation_db.create_conversation(f"Conversation {i}")
        insert_time = time.time() - start_time
        
        # 500件の挿入は3秒以内
        assert insert_time < 3.0, f"Insert took {insert_time}s"
        
        # 一覧取得
        start_time = time.time()
        convs = conversation_db.get_conversations(limit=1000)
        fetch_time = time.time() - start_time
        
        assert len(convs) >= 500
        # 取得は1秒以内
        assert fetch_time < 1.0, f"Fetch took {fetch_time}s"
    
    def test_search_performance(self, conversation_db):
        """検索パフォーマンス"""
        # 100会話、各10メッセージ = 1000メッセージ
        for i in range(100):
            conv_id = conversation_db.create_conversation(f"Conv {i}")
            for j in range(10):
                conversation_db.add_message(
                    conv_id, "user", f"Message content {i}-{j} keyword"
                )
        
        # 検索実行時間
        start_time = time.time()
        results = conversation_db.search_messages("keyword")
        search_time = time.time() - start_time
        
        assert len(results) == 1000
        # 1000件の検索は2秒以内
        assert search_time < 2.0, f"Search took {search_time}s"
    
    def test_pagination_performance(self, conversation_db):
        """ページネーションパフォーマンス"""
        # 1000会話作成
        for i in range(1000):
            conversation_db.create_conversation(f"Conv {i}")
        
        # ページネーション
        start_time = time.time()
        all_convs = []
        offset = 0
        limit = 100
        while True:
            convs = conversation_db.get_conversations(limit=limit, offset=offset)
            if not convs:
                break
            all_convs.extend(convs)
            offset += limit
        pagination_time = time.time() - start_time
        
        assert len(all_convs) >= 1000
        # ページネーションは3秒以内
        assert pagination_time < 3.0, f"Pagination took {pagination_time}s"
    
    def test_concurrent_reads(self, conversation_db):
        """並列読み取りテスト"""
        import threading
        
        # テストデータ作成
        conv_id = conversation_db.create_conversation("Test")
        for i in range(100):
            conversation_db.add_message(conv_id, "user", f"Message {i}")
        
        results = []
        errors = []
        
        def read_messages():
            try:
                msgs = conversation_db.get_messages(conv_id)
                results.append(len(msgs))
            except Exception as e:
                errors.append(str(e))
        
        # 10スレッドで同時読み取り
        threads = []
        start_time = time.time()
        for _ in range(10):
            t = threading.Thread(target=read_messages)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        elapsed = time.time() - start_time
        
        # エラーなし
        assert len(errors) == 0, f"Errors: {errors}"
        # 全スレッド成功
        assert len(results) == 10
        # 全て100件取得
        assert all(r == 100 for r in results)
        # 並列実行は1秒以内
        assert elapsed < 1.0, f"Concurrent read took {elapsed}s"
    
    def test_large_content_search(self, conversation_db):
        """大容量コンテンツの検索"""
        conv_id = conversation_db.create_conversation("Large Content")
        
        # 10KBのコンテンツを100件
        large_content = "X" * 10000 + "UNIQUE_KEYWORD"
        for i in range(100):
            conversation_db.add_message(conv_id, "user", large_content)
        
        start_time = time.time()
        results = conversation_db.search_messages("UNIQUE_KEYWORD")
        search_time = time.time() - start_time
        
        assert len(results) == 100
        # 大容量コンテンツの検索も2秒以内
        assert search_time < 2.0, f"Large content search took {search_time}s"


@pytest.mark.slow
class TestConversationManagerPerformance:
    """ConversationManagerのパフォーマンステスト"""
    
    def test_list_conversations_performance(self, conversation_manager):
        """会話一覧取得のパフォーマンス"""
        # 100会話作成
        for i in range(100):
            conversation_manager.create_conversation(
                user_id="test_user",
                first_message=f"Message {i}"
            )
        
        start_time = time.time()
        convs = conversation_manager.list_conversations(user_id="test_user")
        list_time = time.time() - start_time
        
        assert len(convs) == 100
        # 100件の一覧は1秒以内
        assert list_time < 1.0, f"List took {list_time}s"
    
    def test_search_conversations_performance(self, conversation_manager):
        """会話検索のパフォーマンス"""
        # 100会話作成
        for i in range(100):
            conv = conversation_manager.create_conversation(
                first_message=f"Test conversation number {i}"
            )
            conversation_manager.update_conversation(conv.id, title=f"Test {i}")
        
        start_time = time.time()
        results = conversation_manager.search_conversations("Test")
        search_time = time.time() - start_time
        
        assert len(results) == 100
        # 100件の検索は1秒以内
        assert search_time < 1.0, f"Search took {search_time}s"
    
    def test_get_recent_conversations_performance(self, conversation_manager):
        """最近の会話取得のパフォーマンス"""
        # 50会話作成
        for i in range(50):
            conversation_manager.create_conversation()
        
        start_time = time.time()
        recent = conversation_manager.get_recent_conversations(days=7, limit=50)
        fetch_time = time.time() - start_time
        
        assert len(recent) == 50
        # 取得は0.5秒以内
        assert fetch_time < 0.5, f"Fetch took {fetch_time}s"
    
    def test_message_history_performance(self, conversation_manager):
        """メッセージ履歴取得のパフォーマンス"""
        conv = conversation_manager.create_conversation()
        
        # 500メッセージ追加
        from models.message import MessageRole
        for i in range(500):
            role = MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT
            conversation_manager.add_message(conv.id, role, f"Message {i}")
        
        start_time = time.time()
        history = conversation_manager.get_message_history(conv.id, max_messages=100)
        fetch_time = time.time() - start_time
        
        assert len(history) == 100
        # 100件履歴取得は0.5秒以内
        assert fetch_time < 0.5, f"History fetch took {fetch_time}s"
    
    def test_stats_calculation_performance(self, conversation_manager):
        """統計計算のパフォーマンス"""
        # 複数の会話とメッセージを作成
        from models.message import MessageRole
        for i in range(20):
            conv = conversation_manager.create_conversation(user_id="perf_test")
            for j in range(50):
                conversation_manager.add_message(
                    conv.id, MessageRole.USER, f"Message {j}"
                )
        
        start_time = time.time()
        stats = conversation_manager.get_stats(user_id="perf_test")
        calc_time = time.time() - start_time
        
        assert stats["total_conversations"] == 20
        assert stats["total_messages"] == 1000
        # 統計計算は0.5秒以内
        assert calc_time < 0.5, f"Stats calculation took {calc_time}s"


class TestMemoryUsage:
    """メモリ使用量テスト"""
    
    @pytest.mark.slow
    def test_memory_with_many_conversations(self, conversation_db):
        """大量会話時のメモリ使用量"""
        import gc
        import sys
        
        gc.collect()
        initial_count = len(gc.get_objects())
        
        # 100会話作成
        for i in range(100):
            conv_id = conversation_db.create_conversation(f"Conv {i}")
            for j in range(10):
                conversation_db.add_message(conv_id, "user", f"Msg {j}")
        
        gc.collect()
        final_count = len(gc.get_objects())
        
        # オブジェクト数の増加が制限内
        increase = final_count - initial_count
        # 1000件のオブジェクト生成で10000オブジェクト以内
        assert increase < 10000, f"Object count increased by {increase}"
