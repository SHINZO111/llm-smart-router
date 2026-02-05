"""
セッションプール管理モジュール
- HTTPセッションの再利用
- 接続プール管理
"""
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None

import asyncio
import requests
from typing import Optional, Dict, Any, Union
from urllib.parse import urlparse
import ssl
import certifi
from dataclasses import dataclass
from contextlib import asynccontextmanager, contextmanager


@dataclass
class PoolConfig:
    """プール設定"""
    pool_size: int = 10
    pool_timeout: float = 30.0
    keepalive_timeout: float = 60.0
    max_connections: int = 100
    max_connections_per_host: int = 10
    enable_ssl_verification: bool = True


class SessionPool:
    """HTTPセッションプール管理クラス"""

    def __init__(self, config: Optional[PoolConfig] = None):
        self.config = config or PoolConfig()
        self._sync_session: Optional[requests.Session] = None
        self._async_session = None
        self._connector = None
        self._async_lock = asyncio.Lock()
    
    def _get_ssl_context(self):
        """SSLコンテキストを取得"""
        if self.config.enable_ssl_verification:
            return ssl.create_default_context(cafile=certifi.where())
        else:
            # 検証無効（開発用のみ）
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            return context
    
    def get_sync_session(self):
        """
        同期セッションを取得（シングルトン）
        
        Returns:
            requests.Session
        """
        if self._sync_session is None:
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=self.config.pool_size,
                pool_maxsize=self.config.max_connections,
                max_retries=3
            )
            
            session = requests.Session()
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            
            self._sync_session = session
        
        return self._sync_session
    
    async def get_async_session(self):
        """
        非同期セッションを取得（シングルトン、asyncio.Lockで排他制御）

        Returns:
            aiohttp.ClientSession or None
        """
        if not AIOHTTP_AVAILABLE:
            raise ImportError("aiohttp is required for async sessions")

        async with self._async_lock:
            if self._async_session is None or self._async_session.closed:
                self._connector = aiohttp.TCPConnector(
                    limit=self.config.max_connections,
                    limit_per_host=self.config.max_connections_per_host,
                    keepalive_timeout=self.config.keepalive_timeout,
                    ssl=self._get_ssl_context()
                )

                timeout = aiohttp.ClientTimeout(
                    total=300,
                    connect=self.config.pool_timeout
                )

                self._async_session = aiohttp.ClientSession(
                    connector=self._connector,
                    timeout=timeout
                )

            return self._async_session
    
    @contextmanager
    def sync_session(self):
        """
        同期セッションのコンテキストマネージャー
        
        Example:
            with pool.sync_session() as session:
                response = session.get(url)
        """
        session = self.get_sync_session()
        try:
            yield session
        finally:
            # セッションは維持（コネクションプールの利点）
            pass
    
    @asynccontextmanager
    async def async_session(self):
        """
        非同期セッションのコンテキストマネージャー
        
        Example:
            async with pool.async_session() as session:
                async with session.get(url) as response:
                    ...
        """
        session = await self.get_async_session()
        try:
            yield session
        finally:
            # セッションは維持
            pass
    
    def close_sync(self):
        """同期セッションを閉じる"""
        if self._sync_session:
            self._sync_session.close()
            self._sync_session = None
    
    async def close_async(self):
        """非同期セッションを閉じる"""
        if AIOHTTP_AVAILABLE and self._async_session and not self._async_session.closed:
            await self._async_session.close()
            self._async_session = None
        
        if self._connector:
            await self._connector.close()
            self._connector = None
    
    def close(self):
        """全セッションを閉じる（同期版）"""
        self.close_sync()
    
    async def close_all(self):
        """全セッションを閉じる（非同期版）"""
        await self.close_async()


class EndpointPool:
    """エンドポイント別セッションプール"""
    
    def __init__(self):
        self._pools: Dict[str, SessionPool] = {}
        self._default_config = PoolConfig()
    
    def get_pool(self, endpoint: str, config: Optional[PoolConfig] = None):
        """
        エンドポイント用のプールを取得
        
        Args:
            endpoint: エンドポイントURL
            config: プール設定
        
        Returns:
            SessionPool
        """
        # ホスト名でグループ化
        parsed = urlparse(endpoint)
        host_key = f"{parsed.scheme}://{parsed.netloc}"
        
        if host_key not in self._pools:
            self._pools[host_key] = SessionPool(config or self._default_config)
        
        return self._pools[host_key]
    
    def close_all(self):
        """全プールを閉じる"""
        for pool in self._pools.values():
            pool.close()
        self._pools.clear()
    
    async def close_all_async(self):
        """全プールを非同期で閉じる"""
        for pool in list(self._pools.values()):
            try:
                await pool.close_async()
            except Exception:
                pass
        self._pools.clear()


# グローバルプールインスタンス
_pool_instance: Optional[EndpointPool] = None


def get_pool():
    """グローバルプールインスタンスを取得"""
    global _pool_instance
    
    if _pool_instance is None:
        _pool_instance = EndpointPool()
    
    return _pool_instance


def reset_pool():
    """グローバルプールをリセット"""
    global _pool_instance
    
    if _pool_instance:
        _pool_instance.close_all()
    
    _pool_instance = None


# 便利なショートカット関数
def get_session(endpoint: str, config: Optional[PoolConfig] = None):
    """エンドポイント用の同期セッションを取得"""
    pool = get_pool().get_pool(endpoint, config)
    return pool.get_sync_session()


async def get_async_session(endpoint: str, config: Optional[PoolConfig] = None):
    """エンドポイント用の非同期セッションを取得"""
    if not AIOHTTP_AVAILABLE:
        raise ImportError("aiohttp is required")
    pool = get_pool().get_pool(endpoint, config)
    return await pool.get_async_session()
