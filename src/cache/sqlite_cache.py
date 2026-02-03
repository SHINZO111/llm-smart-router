"""
SQLiteベースキャッシュモジュール
- TTL設定（デフォルト1時間）
- 類似質問検索（ベクトル類似度）
"""
import sqlite3
import json
import hashlib
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
import re


@dataclass
class CacheEntry:
    """キャッシュエントリ"""
    key: str
    query: str
    response: str
    model: str
    metadata: Dict[str, Any]
    created_at: float
    expires_at: float
    access_count: int = 0
    last_accessed: float = 0


class SQLiteCache:
    """SQLiteベースのキャッシュ管理クラス"""
    
    def __init__(
        self,
        db_path: str = "./cache/llm_cache.db",
        default_ttl: int = 3600,  # デフォルト1時間
        max_entries: int = 10000,
        similarity_threshold: float = 0.85
    ):
        self.db_path = db_path
        self.default_ttl = default_ttl
        self.max_entries = max_entries
        self.similarity_threshold = similarity_threshold
        self._initialized = False
        
    def initialize(self) -> None:
        """データベース初期化"""
        if self._initialized:
            return
            
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    response TEXT NOT NULL,
                    model TEXT NOT NULL,
                    metadata TEXT,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    last_accessed REAL DEFAULT 0
                )
            """)
            
            # 類似検索用インデックス
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_query ON cache_entries(query)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires ON cache_entries(expires_at)
            """)
            
            conn.commit()
        
        self._initialized = True
    
    def _generate_key(self, query: str, model: str, params: Optional[Dict] = None) -> str:
        """クエリからキーを生成"""
        content = f"{query}:{model}:{json.dumps(params or {}, sort_keys=True)}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _clean_text(self, text: str) -> str:
        """テキスト正規化（類似検索用）"""
        # 空白正規化
        text = re.sub(r'\s+', ' ', text)
        # 記号削除
        text = re.sub(r'[^\w\s]', '', text)
        # 小文字化
        return text.lower().strip()
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        2つのテキストの類似度を計算（コサイン類似度ベース）
        シンプルなn-gramベースの実装
        """
        text1 = self._clean_text(text1)
        text2 = self._clean_text(text2)
        
        if not text1 or not text2:
            return 0.0
        
        # 単語ベースのベクトル化
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        # Jaccard類似度
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        if union == 0:
            return 0.0
        
        jaccard = intersection / union
        
        # 部分一致の重み付け
        len_ratio = min(len(text1), len(text2)) / max(len(text1), len(text2))
        
        return jaccard * (0.7 + 0.3 * len_ratio)
    
    def get(
        self,
        query: str,
        model: str,
        params: Optional[Dict] = None,
        use_similarity: bool = True
    ) -> Optional[CacheEntry]:
        """
        キャッシュから取得
        
        Args:
            query: 検索クエリ
            model: モデル名
            params: 追加パラメータ
            use_similarity: 類似検索を使用するか
        
        Returns:
            CacheEntry or None
        """
        if not self._initialized:
            self.initialize()
        
        key = self._generate_key(query, model, params)
        
        with sqlite3.connect(self.db_path) as conn:
            # 完全一致で検索
            cursor = conn.execute(
                """
                SELECT key, query, response, model, metadata, created_at, 
                       expires_at, access_count, last_accessed
                FROM cache_entries
                WHERE key = ? AND expires_at > ?
                """,
                (key, time.time())
            )
            
            row = cursor.fetchone()
            
            if row:
                # アクセス統計更新
                conn.execute(
                    """
                    UPDATE cache_entries 
                    SET access_count = access_count + 1, last_accessed = ?
                    WHERE key = ?
                    """,
                    (time.time(), key)
                )
                conn.commit()
                
                return CacheEntry(
                    key=row[0],
                    query=row[1],
                    response=row[2],
                    model=row[3],
                    metadata=json.loads(row[4] or '{}'),
                    created_at=row[5],
                    expires_at=row[6],
                    access_count=row[7] + 1,
                    last_accessed=time.time()
                )
            
            # 類似検索
            if use_similarity:
                return self._find_similar(conn, query, model, params)
        
        return None
    
    def _find_similar(
        self,
        conn: sqlite3.Connection,
        query: str,
        model: str,
        params: Optional[Dict] = None
    ) -> Optional[CacheEntry]:
        """類似エントリを検索"""
        
        # 有効なエントリを取得（最近のもの優先）
        cursor = conn.execute(
            """
            SELECT key, query, response, model, metadata, created_at, 
                   expires_at, access_count, last_accessed
            FROM cache_entries
            WHERE model = ? AND expires_at > ?
            ORDER BY created_at DESC
            LIMIT 100
            """,
            (model, time.time())
        )
        
        best_match = None
        best_score = 0.0
        
        for row in cursor:
            cached_query = row[1]
            similarity = self._calculate_similarity(query, cached_query)
            
            if similarity > self.similarity_threshold and similarity > best_score:
                best_score = similarity
                best_match = row
        
        if best_match:
            # アクセス統計更新
            conn.execute(
                """
                UPDATE cache_entries 
                SET access_count = access_count + 1, last_accessed = ?
                WHERE key = ?
                """,
                (time.time(), best_match[0])
            )
            conn.commit()
            
            return CacheEntry(
                key=best_match[0],
                query=best_match[1],
                response=best_match[2],
                model=best_match[3],
                metadata=json.loads(best_match[4] or '{}'),
                created_at=best_match[5],
                expires_at=best_match[6],
                access_count=best_match[7] + 1,
                last_accessed=time.time()
            )
        
        return None
    
    def set(
        self,
        query: str,
        response: str,
        model: str,
        params: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
        ttl: Optional[int] = None
    ) -> str:
        """
        キャッシュに保存
        
        Args:
            query: クエリ
            response: レスポンス
            model: モデル名
            params: パラメータ
            metadata: メタデータ
            ttl: TTL（秒）
        
        Returns:
            キャッシュキー
        """
        if not self._initialized:
            self.initialize()
        
        key = self._generate_key(query, model, params)
        now = time.time()
        expires = now + (ttl or self.default_ttl)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cache_entries
                (key, query, response, model, metadata, created_at, expires_at, access_count, last_accessed)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    key,
                    query,
                    response,
                    model,
                    json.dumps(metadata or {}),
                    now,
                    expires,
                    now
                )
            )
            conn.commit()
        
        # 古いエントリをクリーンアップ
        self._cleanup_old_entries()
        
        return key
    
    def delete(self, key: str) -> bool:
        """キャッシュエントリを削除"""
        if not self._initialized:
            return False
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
            conn.commit()
            return cursor.rowcount > 0
    
    def clear(self) -> int:
        """全キャッシュをクリア"""
        if not self._initialized:
            return 0
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM cache_entries")
            conn.commit()
            return cursor.rowcount
    
    def _cleanup_old_entries(self) -> None:
        """古いエントリをクリーンアップ"""
        with sqlite3.connect(self.db_path) as conn:
            # 期限切れエントリを削除
            conn.execute(
                "DELETE FROM cache_entries WHERE expires_at <= ?",
                (time.time(),)
            )
            
            # 最大エントリ数を超えたら古いものから削除
            conn.execute("""
                DELETE FROM cache_entries
                WHERE key IN (
                    SELECT key FROM cache_entries
                    ORDER BY last_accessed ASC
                    LIMIT (SELECT MAX(0, COUNT(*) - ?) FROM cache_entries)
                )
            """, (self.max_entries,))
            
            conn.commit()
    
    def get_stats(self) -> Dict[str, Any]:
        """キャッシュ統計を取得"""
        if not self._initialized:
            return {"initialized": False}
        
        with sqlite3.connect(self.db_path) as conn:
            # 総エントリ数
            total = conn.execute(
                "SELECT COUNT(*) FROM cache_entries"
            ).fetchone()[0]
            
            # 有効なエントリ数
            valid = conn.execute(
                "SELECT COUNT(*) FROM cache_entries WHERE expires_at > ?",
                (time.time(),)
            ).fetchone()[0]
            
            # 期限切れエントリ数
            expired = conn.execute(
                "SELECT COUNT(*) FROM cache_entries WHERE expires_at <= ?",
                (time.time(),)
            ).fetchone()[0]
            
            # アクセス統計
            access_stats = conn.execute(
                """
                SELECT 
                    SUM(access_count) as total_access,
                    AVG(access_count) as avg_access,
                    MAX(access_count) as max_access
                FROM cache_entries
                """
            ).fetchone()
            
            return {
                "initialized": True,
                "total_entries": total,
                "valid_entries": valid,
                "expired_entries": expired,
                "total_accesses": access_stats[0] or 0,
                "avg_accesses": round(access_stats[1] or 0, 2),
                "max_accesses": access_stats[2] or 0,
                "db_path": self.db_path,
                "default_ttl": self.default_ttl
            }


class CacheDecorator:
    """関数の結果をキャッシュするデコレータ"""
    
    def __init__(
        self,
        cache: SQLiteCache,
        key_func: Optional[callable] = None,
        ttl: Optional[int] = None
    ):
        self.cache = cache
        self.key_func = key_func
        self.ttl = ttl
    
    def __call__(self, func):
        def wrapper(*args, **kwargs):
            # キャッシュキー生成
            if self.key_func:
                cache_key = self.key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # キャッシュ検索
            entry = self.cache.get(
                query=cache_key,
                model="decorator",
                params={},
                use_similarity=False
            )
            
            if entry:
                return entry.response
            
            # 関数実行
            result = func(*args, **kwargs)
            
            # キャッシュ保存
            if isinstance(result, str):
                self.cache.set(
                    query=cache_key,
                    response=result,
                    model="decorator",
                    ttl=self.ttl
                )
            
            return result
        
        return wrapper


# グローバルキャッシュインスタンス
_cache_instance: Optional[SQLiteCache] = None


def get_cache(config: Optional[Dict] = None) -> SQLiteCache:
    """グローバルキャッシュインスタンスを取得"""
    global _cache_instance
    
    if _cache_instance is None:
        if config is None:
            config = {}
        
        _cache_instance = SQLiteCache(
            db_path=config.get("path", "./cache/llm_cache.db"),
            default_ttl=config.get("ttl", 3600),
            max_entries=config.get("max_entries", 10000),
            similarity_threshold=config.get("similarity_threshold", 0.85)
        )
        _cache_instance.initialize()
    
    return _cache_instance


def reset_cache() -> None:
    """グローバルキャッシュをリセット"""
    global _cache_instance
    _cache_instance = None
