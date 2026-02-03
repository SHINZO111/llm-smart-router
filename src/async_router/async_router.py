"""
非同期ルーターモジュール
- asyncio対応ルーター
- 複数リクエストの並列処理
- セマフォで同時接続数制限（最大5）
"""
import asyncio
import time
from typing import List, Dict, Any, Optional, Callable, Coroutine
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
import logging

# ロガー設定
logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """タスク優先度"""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class RoutingTask:
    """ルーティングタスク"""
    id: str
    query: str
    model: str
    priority: TaskPriority = TaskPriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    timeout: float = 60.0


@dataclass
class TaskResult:
    """タスク実行結果"""
    task_id: str
    success: bool
    response: Optional[str] = None
    model: Optional[str] = None
    error: Optional[str] = None
    duration: float = 0.0
    from_cache: bool = False


class AsyncRouter:
    """
    非同期LLMルーター
    
    機能:
    - 並列リクエスト処理
    - セマフォによる同時接続制限
    - 優先度付きキュー
    - タイムアウト管理
    """
    
    def __init__(
        self,
        max_concurrent: int = 5,
        max_workers: int = 4,
        enable_cache: bool = True,
        cache_config: Optional[Dict] = None
    ):
        self.max_concurrent = max_concurrent
        self.max_workers = max_workers
        self.enable_cache = enable_cache
        self.cache_config = cache_config or {}
        
        # セマフォ（同時接続制限）
        self._semaphore = asyncio.Semaphore(max_concurrent)
        
        # スレッドプール（同期関数用）
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # タスクキュー
        self._task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        
        # キャッシュ
        self._cache = None
        if enable_cache:
            try:
                from src.cache.sqlite_cache import get_cache
                self._cache = get_cache(self.cache_config)
            except ImportError:
                logger.warning("Cache module not available")
        
        # モデルクライアント（動的に設定）
        self._model_clients: Dict[str, Callable] = {}
        
        # 実行統計
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "cached_requests": 0,
            "avg_latency": 0.0
        }
    
    def register_model_client(
        self,
        model: str,
        client: Callable[[str], Coroutine[Any, Any, str]]
    ) -> None:
        """
        モデルクライアントを登録
        
        Args:
            model: モデル名
            client: 非同期クライアント関数
        """
        self._model_clients[model] = client
        logger.info(f"Registered client for model: {model}")
    
    async def route(
        self,
        query: str,
        model: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: float = 60.0,
        use_cache: bool = True,
        metadata: Optional[Dict] = None
    ) -> TaskResult:
        """
        単一リクエストをルーティング
        
        Args:
            query: クエリ
            model: モデル名
            priority: 優先度
            timeout: タイムアウト（秒）
            use_cache: キャッシュを使用するか
            metadata: メタデータ
        
        Returns:
            TaskResult
        """
        task = RoutingTask(
            id=f"{model}_{int(time.time() * 1000)}",
            query=query,
            model=model,
            priority=priority,
            timeout=timeout,
            metadata=metadata or {}
        )
        
        return await self._execute_task(task, use_cache)
    
    async def route_multiple(
        self,
        queries: List[Dict[str, Any]],
        max_parallel: Optional[int] = None
    ) -> List[TaskResult]:
        """
        複数リクエストを並列処理
        
        Args:
            queries: クエリリスト [{'query': str, 'model': str, ...}, ...]
            max_parallel: 最大並列数（None=制限なし）
        
        Returns:
            TaskResultリスト
        """
        if not queries:
            return []
        
        # タスク作成
        tasks = []
        for q in queries:
            task = RoutingTask(
                id=q.get('id', f"batch_{int(time.time() * 1000)}_{len(tasks)}"),
                query=q['query'],
                model=q['model'],
                priority=q.get('priority', TaskPriority.NORMAL),
                timeout=q.get('timeout', 60.0),
                metadata=q.get('metadata', {})
            )
            tasks.append(task)
        
        # 並列実行
        if max_parallel:
            # セマフォで制限
            semaphore = asyncio.Semaphore(max_parallel)
            
            async def limited_execute(task):
                async with semaphore:
                    return await self._execute_task(
                        task,
                        use_cache=task.metadata.get('use_cache', True)
                    )
            
            results = await asyncio.gather(
                *[limited_execute(t) for t in tasks],
                return_exceptions=True
            )
        else:
            results = await asyncio.gather(
                *[self._execute_task(t, use_cache=t.metadata.get('use_cache', True)) 
                  for t in tasks],
                return_exceptions=True
            )
        
        # 例外処理
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(TaskResult(
                    task_id=tasks[i].id,
                    success=False,
                    error=str(result)
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _execute_task(
        self,
        task: RoutingTask,
        use_cache: bool = True
    ) -> TaskResult:
        """
        タスクを実行
        
        Args:
            task: ルーティングタスク
            use_cache: キャッシュを使用するか
        
        Returns:
            TaskResult
        """
        start_time = time.time()
        
        try:
            # キャッシュチェック
            if use_cache and self._cache and self.enable_cache:
                cached = self._cache.get(
                    query=task.query,
                    model=task.model,
                    use_similarity=True
                )
                
                if cached:
                    self._stats["cached_requests"] += 1
                    return TaskResult(
                        task_id=task.id,
                        success=True,
                        response=cached.response,
                        model=task.model,
                        duration=time.time() - start_time,
                        from_cache=True
                    )
            
            # モデルクライアント取得
            client = self._model_clients.get(task.model)
            
            if not client:
                return TaskResult(
                    task_id=task.id,
                    success=False,
                    error=f"No client registered for model: {task.model}",
                    duration=time.time() - start_time
                )
            
            # セマフォで同時接続制限
            async with self._semaphore:
                # タイムアウト付きで実行
                try:
                    response = await asyncio.wait_for(
                        client(task.query),
                        timeout=task.timeout
                    )
                except asyncio.TimeoutError:
                    return TaskResult(
                        task_id=task.id,
                        success=False,
                        error=f"Timeout after {task.timeout}s",
                        duration=time.time() - start_time
                    )
            
            # キャッシュに保存
            if use_cache and self._cache and self.enable_cache:
                self._cache.set(
                    query=task.query,
                    response=response,
                    model=task.model
                )
            
            # 統計更新
            self._update_stats(success=True, duration=time.time() - start_time)
            
            return TaskResult(
                task_id=task.id,
                success=True,
                response=response,
                model=task.model,
                duration=time.time() - start_time,
                from_cache=False
            )
            
        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            self._update_stats(success=False)
            
            return TaskResult(
                task_id=task.id,
                success=False,
                error=str(e),
                duration=time.time() - start_time
            )
    
    def _update_stats(self, success: bool, duration: float = 0.0) -> None:
        """統計を更新"""
        self._stats["total_requests"] += 1
        
        if success:
            self._stats["successful_requests"] += 1
        else:
            self._stats["failed_requests"] += 1
        
        # 移動平均
        n = self._stats["total_requests"]
        self._stats["avg_latency"] = (
            (self._stats["avg_latency"] * (n - 1) + duration) / n
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """実行統計を取得"""
        return {
            **self._stats,
            "success_rate": (
                self._stats["successful_requests"] / max(1, self._stats["total_requests"])
            ),
            "cache_hit_rate": (
                self._stats["cached_requests"] / max(1, self._stats["total_requests"])
            )
        }
    
    async def close(self) -> None:
        """リソースを解放"""
        self._executor.shutdown(wait=True)
        
        if self._cache:
            # キャッシュのクリーンアップ
            pass
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class BatchProcessor:
    """バッチ処理クラス"""
    
    def __init__(self, router: AsyncRouter, batch_size: int = 10):
        self.router = router
        self.batch_size = batch_size
    
    async def process(
        self,
        items: List[Dict[str, Any]],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[TaskResult]:
        """
        バッチ処理
        
        Args:
            items: 処理対象リスト
            progress_callback: 進捗コールバック(current, total)
        
        Returns:
            結果リスト
        """
        results = []
        total = len(items)
        
        for i in range(0, total, self.batch_size):
            batch = items[i:i + self.batch_size]
            batch_results = await self.router.route_multiple(batch)
            results.extend(batch_results)
            
            if progress_callback:
                progress_callback(min(i + self.batch_size, total), total)
        
        return results


# 同期API用ラッパー（既存コードとの互換性）
class SyncRouterWrapper:
    """非同期ルーターの同期ラッパー"""
    
    def __init__(self, async_router: AsyncRouter):
        self._async_router = async_router
        self._loop: Optional[asyncio.AbstractEventLoop] = None
    
    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """イベントループを取得"""
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop
    
    def route(
        self,
        query: str,
        model: str,
        timeout: float = 60.0,
        use_cache: bool = True
    ) -> TaskResult:
        """同期APIでルーティング"""
        loop = self._get_loop()
        
        coro = self._async_router.route(
            query=query,
            model=model,
            timeout=timeout,
            use_cache=use_cache
        )
        
        if loop.is_running():
            # 既にループが実行中の場合は別スレッドで実行
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(lambda: asyncio.run(coro))
                return future.result()
        else:
            return loop.run_until_complete(coro)
    
    def route_multiple(
        self,
        queries: List[Dict[str, Any]]
    ) -> List[TaskResult]:
        """複数リクエストを同期で処理"""
        loop = self._get_loop()
        coro = self._async_router.route_multiple(queries)
        return loop.run_until_complete(coro)


# ファクトリ関数
def create_router(
    config: Optional[Dict] = None,
    sync_mode: bool = False
) -> AsyncRouter:
    """
    ルーターを作成
    
    Args:
        config: 設定辞書
        sync_mode: 同期モードで使用する場合True
    
    Returns:
        AsyncRouter または SyncRouterWrapper
    """
    config = config or {}
    
    router = AsyncRouter(
        max_concurrent=config.get('max_concurrent', 5),
        max_workers=config.get('max_workers', 4),
        enable_cache=config.get('enable_cache', True),
        cache_config=config.get('cache', {})
    )
    
    if sync_mode:
        return SyncRouterWrapper(router)
    
    return router
