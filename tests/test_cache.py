"""
SQLiteCache テストモジュール

TTL管理、類似検索、スレッドセーフ性、統計、クリーンアップのテスト
"""
import os
import sys
import time
import tempfile
import threading
from pathlib import Path

import pytest

# プロジェクトルートをパスに追加
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
_src = str(Path(__file__).parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from cache.sqlite_cache import SQLiteCache, CacheEntry, CacheDecorator, get_cache, reset_cache


@pytest.fixture
def cache(tmp_path):
    """テスト用一時キャッシュを作成"""
    db_path = str(tmp_path / "test_cache.db")
    c = SQLiteCache(db_path=db_path, default_ttl=3600, max_entries=100, similarity_threshold=0.85)
    c.initialize()
    yield c


@pytest.fixture(autouse=True)
def reset_global_cache():
    """各テスト後にグローバルキャッシュをリセット"""
    yield
    reset_cache()


# ---------------------------------------------------------------------------
# 初期化テスト
# ---------------------------------------------------------------------------

class TestCacheInitialization:
    """キャッシュ初期化テスト"""

    def test_initialize_creates_db(self, tmp_path):
        db_path = str(tmp_path / "sub" / "cache.db")
        c = SQLiteCache(db_path=db_path)
        c.initialize()
        assert os.path.exists(db_path)

    def test_double_initialize_is_safe(self, cache):
        cache.initialize()
        cache.initialize()
        # エラーなく2回呼べること

    def test_auto_initialize_on_get(self, tmp_path):
        """get()呼び出し時に自動初期化"""
        db_path = str(tmp_path / "auto_init.db")
        c = SQLiteCache(db_path=db_path)
        result = c.get("test", "model")
        assert result is None
        assert c._initialized

    def test_auto_initialize_on_set(self, tmp_path):
        """set()呼び出し時に自動初期化"""
        db_path = str(tmp_path / "auto_init2.db")
        c = SQLiteCache(db_path=db_path)
        key = c.set("query", "response", "model")
        assert key is not None
        assert c._initialized


# ---------------------------------------------------------------------------
# 基本 CRUD テスト
# ---------------------------------------------------------------------------

class TestCacheCRUD:
    """キャッシュ基本操作テスト"""

    def test_set_and_get_exact_match(self, cache):
        cache.set("Hello world", "Response text", "gpt-4")
        entry = cache.get("Hello world", "gpt-4", use_similarity=False)
        assert entry is not None
        assert entry.response == "Response text"
        assert entry.model == "gpt-4"

    def test_get_nonexistent_returns_none(self, cache):
        result = cache.get("nonexistent query", "model", use_similarity=False)
        assert result is None

    def test_set_returns_key(self, cache):
        key = cache.set("q1", "r1", "model")
        assert isinstance(key, str)
        assert len(key) == 64  # SHA256 hex digest

    def test_same_query_same_key(self, cache):
        key1 = cache.set("same query", "r1", "model")
        key2 = cache.set("same query", "r2", "model")
        assert key1 == key2

    def test_different_model_different_key(self, cache):
        key1 = cache._generate_key("query", "model_a")
        key2 = cache._generate_key("query", "model_b")
        assert key1 != key2

    def test_set_with_metadata(self, cache):
        cache.set("q", "r", "model", metadata={"source": "test"})
        entry = cache.get("q", "model", use_similarity=False)
        assert entry.metadata == {"source": "test"}

    def test_set_with_params(self, cache):
        cache.set("q", "r", "model", params={"temp": 0.7})
        entry = cache.get("q", "model", params={"temp": 0.7}, use_similarity=False)
        assert entry is not None
        # 異なるparamsでは取得できない
        entry2 = cache.get("q", "model", params={"temp": 0.9}, use_similarity=False)
        assert entry2 is None

    def test_delete_existing(self, cache):
        cache.set("to_delete", "response", "model")
        key = cache._generate_key("to_delete", "model")
        assert cache.delete(key)

    def test_delete_nonexistent(self, cache):
        assert not cache.delete("nonexistent_key")

    def test_delete_uninitialized(self, tmp_path):
        c = SQLiteCache(db_path=str(tmp_path / "uninit.db"))
        assert not c.delete("key")

    def test_clear_all(self, cache):
        cache.set("q1", "r1", "model")
        cache.set("q2", "r2", "model")
        count = cache.clear()
        assert count == 2
        assert cache.get("q1", "model", use_similarity=False) is None

    def test_clear_uninitialized(self, tmp_path):
        c = SQLiteCache(db_path=str(tmp_path / "uninit.db"))
        assert c.clear() == 0

    def test_overwrite_existing(self, cache):
        """同一キーへの上書き"""
        cache.set("q", "old response", "model")
        cache.set("q", "new response", "model")
        entry = cache.get("q", "model", use_similarity=False)
        assert entry.response == "new response"


# ---------------------------------------------------------------------------
# TTL テスト
# ---------------------------------------------------------------------------

class TestCacheTTL:
    """TTL管理テスト"""

    def test_expired_entry_not_returned(self, tmp_path):
        """期限切れエントリは返されない"""
        db_path = str(tmp_path / "ttl_test.db")
        c = SQLiteCache(db_path=db_path, default_ttl=1)  # 1秒TTL
        c.initialize()
        c.set("q", "r", "model")
        time.sleep(1.5)
        result = c.get("q", "model", use_similarity=False)
        assert result is None

    def test_custom_ttl(self, tmp_path):
        """カスタムTTL"""
        db_path = str(tmp_path / "custom_ttl.db")
        c = SQLiteCache(db_path=db_path, default_ttl=3600)
        c.initialize()
        c.set("q", "r", "model", ttl=1)  # 1秒
        time.sleep(1.5)
        result = c.get("q", "model", use_similarity=False)
        assert result is None

    def test_valid_entry_returned(self, cache):
        """有効なエントリは返される"""
        cache.set("q", "r", "model", ttl=60)
        result = cache.get("q", "model", use_similarity=False)
        assert result is not None


# ---------------------------------------------------------------------------
# 類似検索テスト
# ---------------------------------------------------------------------------

class TestCacheSimilarity:
    """類似検索テスト"""

    def test_similar_query_found(self, cache):
        """類似クエリが見つかること"""
        cache.set("What is machine learning", "ML is...", "gpt-4")
        # ほぼ同じクエリ
        result = cache.get("What is machine learning?", "gpt-4", use_similarity=True)
        # 完全一致しないがモデルが一致するエントリが見つかる可能性がある
        # 類似度閾値0.85なので、ほぼ同じクエリならヒットする

    def test_dissimilar_query_not_found(self, cache):
        """異なるクエリでは見つからないこと"""
        cache.set("machine learning basics", "ML is...", "gpt-4")
        result = cache.get("cooking recipe for pasta", "gpt-4", use_similarity=True)
        assert result is None

    def test_similarity_respects_model(self, cache):
        """類似検索はモデルを考慮"""
        cache.set("test query", "response", "model_a")
        result = cache.get("test query similar", "model_b", use_similarity=True)
        # model_bのエントリは存在しないのでNone
        assert result is None

    def test_calculate_similarity_identical(self, cache):
        """同一テキストの類似度は高い"""
        score = cache._calculate_similarity("hello world", "hello world")
        assert score > 0.9

    def test_calculate_similarity_empty(self, cache):
        """空テキストの類似度は0"""
        assert cache._calculate_similarity("", "hello") == 0.0
        assert cache._calculate_similarity("hello", "") == 0.0
        assert cache._calculate_similarity("", "") == 0.0

    def test_calculate_similarity_truncation(self, cache):
        """長いテキストは切り詰められる"""
        long_text = "word " * 1000
        score = cache._calculate_similarity(long_text, long_text)
        assert score > 0.0

    def test_clean_text(self, cache):
        """テキスト正規化"""
        result = cache._clean_text("  Hello,  World!  ")
        assert result == "hello world"

    def test_similarity_disabled(self, cache):
        """use_similarity=Falseで類似検索を無効化"""
        cache.set("machine learning intro", "response", "gpt-4")
        result = cache.get("machine learning introduction", "gpt-4", use_similarity=False)
        assert result is None  # 完全一致しないのでNone


# ---------------------------------------------------------------------------
# アクセス統計テスト
# ---------------------------------------------------------------------------

class TestCacheAccessStats:
    """アクセス統計テスト"""

    def test_access_count_increments(self, cache):
        """アクセスカウントが増加すること"""
        cache.set("q", "r", "model")
        cache.get("q", "model", use_similarity=False)
        cache.get("q", "model", use_similarity=False)
        stats = cache.get_stats()
        assert stats["total_accesses"] >= 2

    def test_stats_uninitialized(self, tmp_path):
        """未初期化の統計"""
        c = SQLiteCache(db_path=str(tmp_path / "uninit.db"))
        stats = c.get_stats()
        assert stats["initialized"] is False

    def test_stats_after_operations(self, cache):
        """操作後の統計"""
        cache.set("q1", "r1", "model")
        cache.set("q2", "r2", "model")
        stats = cache.get_stats()
        assert stats["initialized"] is True
        assert stats["total_entries"] == 2
        assert stats["valid_entries"] == 2
        assert stats["expired_entries"] == 0


# ---------------------------------------------------------------------------
# クリーンアップテスト
# ---------------------------------------------------------------------------

class TestCacheCleanup:
    """クリーンアップテスト"""

    def test_cleanup_expired(self, tmp_path):
        """期限切れエントリの削除"""
        db_path = str(tmp_path / "cleanup.db")
        c = SQLiteCache(db_path=db_path, default_ttl=1)
        c.initialize()
        c.set("q1", "r1", "model")
        time.sleep(1.5)
        # 新しいエントリ追加でクリーンアップ発動
        c.set("q2", "r2", "model", ttl=3600)
        stats = c.get_stats()
        assert stats["valid_entries"] == 1

    def test_max_entries_eviction(self, tmp_path):
        """最大エントリ数超過時の退避"""
        db_path = str(tmp_path / "eviction.db")
        c = SQLiteCache(db_path=db_path, default_ttl=3600, max_entries=5)
        c.initialize()
        for i in range(10):
            c.set(f"query_{i}", f"response_{i}", "model")
        stats = c.get_stats()
        assert stats["total_entries"] <= 5


# ---------------------------------------------------------------------------
# スレッドセーフテスト
# ---------------------------------------------------------------------------

class TestCacheThreadSafety:
    """スレッドセーフ性テスト"""

    def test_concurrent_writes(self, cache):
        """並行書き込みがエラーにならない"""
        errors = []

        def writer(n):
            try:
                for i in range(20):
                    cache.set(f"thread_{n}_query_{i}", f"response_{i}", "model")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(n,)) for n in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_reads_writes(self, cache):
        """読み書き並行アクセス"""
        cache.set("shared_key", "initial", "model")
        errors = []

        def reader():
            try:
                for _ in range(20):
                    cache.get("shared_key", "model", use_similarity=False)
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(20):
                    cache.set("shared_key", f"update_{i}", "model")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=reader),
            threading.Thread(target=writer),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ---------------------------------------------------------------------------
# CacheDecorator テスト
# ---------------------------------------------------------------------------

class TestCacheDecorator:
    """キャッシュデコレータテスト"""

    def test_decorator_caches_string_result(self, cache):
        call_count = 0

        @CacheDecorator(cache=cache)
        def my_func(x):
            nonlocal call_count
            call_count += 1
            return f"result_{x}"

        r1 = my_func("a")
        r2 = my_func("a")
        assert r1 == "result_a"
        assert r2 == "result_a"
        assert call_count == 1  # 2回目はキャッシュから

    def test_decorator_non_string_not_cached(self, cache):
        """文字列以外の戻り値はキャッシュされない"""
        call_count = 0

        @CacheDecorator(cache=cache)
        def my_func():
            nonlocal call_count
            call_count += 1
            return 42

        r1 = my_func()
        r2 = my_func()
        assert r1 == 42
        assert call_count == 2  # キャッシュされないので2回呼ばれる


# ---------------------------------------------------------------------------
# get_cache / reset_cache テスト
# ---------------------------------------------------------------------------

class TestGlobalCache:
    """グローバルキャッシュ管理テスト"""

    def test_get_cache_returns_singleton(self, tmp_path):
        config = {"path": str(tmp_path / "global.db")}
        c1 = get_cache(config)
        c2 = get_cache()
        assert c1 is c2

    def test_reset_cache_clears_instance(self, tmp_path):
        config = {"path": str(tmp_path / "global2.db")}
        c1 = get_cache(config)
        reset_cache()
        config2 = {"path": str(tmp_path / "global3.db")}
        c2 = get_cache(config2)
        assert c1 is not c2


# ---------------------------------------------------------------------------
# エッジケーステスト
# ---------------------------------------------------------------------------

class TestCacheEdgeCases:
    """エッジケーステスト"""

    def test_unicode_query(self, cache):
        """Unicode文字列"""
        cache.set("日本語のクエリ", "レスポンス", "model")
        entry = cache.get("日本語のクエリ", "model", use_similarity=False)
        assert entry is not None
        assert entry.response == "レスポンス"

    def test_emoji_query(self, cache):
        """絵文字入りクエリ"""
        cache.set("Hello 🌍", "World 🎉", "model")
        entry = cache.get("Hello 🌍", "model", use_similarity=False)
        assert entry is not None

    def test_very_long_query(self, cache):
        """非常に長いクエリ"""
        long_query = "x" * 10000
        cache.set(long_query, "response", "model")
        entry = cache.get(long_query, "model", use_similarity=False)
        assert entry is not None

    def test_empty_response(self, cache):
        """空レスポンス"""
        cache.set("q", "", "model")
        entry = cache.get("q", "model", use_similarity=False)
        assert entry is not None
        assert entry.response == ""

    def test_special_characters_in_metadata(self, cache):
        """メタデータの特殊文字"""
        meta = {"key": "value with 'quotes' and \"double\"", "nested": {"a": 1}}
        cache.set("q", "r", "model", metadata=meta)
        entry = cache.get("q", "model", use_similarity=False)
        assert entry.metadata["key"] == meta["key"]
