"""
SessionPool / EndpointPool / AsyncRouter テストモジュール

接続プール管理、非同期ルーティング、バッチ処理のテスト
"""
import sys
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# プロジェクトルートをパスに追加
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
_src = str(Path(__file__).parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from connection.session_pool import (
    PoolConfig,
    SessionPool,
    EndpointPool,
    get_pool,
    reset_pool,
    get_session,
)
from async_router.async_router import (
    TaskPriority,
    RoutingTask,
    TaskResult,
    AsyncRouter,
    BatchProcessor,
    SyncRouterWrapper,
    create_router,
)


# ---------------------------------------------------------------------------
# PoolConfig テスト
# ---------------------------------------------------------------------------

class TestPoolConfig:
    """プール設定テスト"""

    def test_default_values(self):
        cfg = PoolConfig()
        assert cfg.pool_size == 10
        assert cfg.pool_timeout == 30.0
        assert cfg.max_connections == 100
        assert cfg.max_connections_per_host == 10
        assert cfg.enable_ssl_verification is True

    def test_custom_values(self):
        cfg = PoolConfig(pool_size=5, max_connections=50)
        assert cfg.pool_size == 5
        assert cfg.max_connections == 50


# ---------------------------------------------------------------------------
# SessionPool テスト
# ---------------------------------------------------------------------------

class TestSessionPool:
    """セッションプールテスト"""

    def test_get_sync_session_singleton(self):
        pool = SessionPool()
        s1 = pool.get_sync_session()
        s2 = pool.get_sync_session()
        assert s1 is s2
        pool.close_sync()

    def test_sync_session_context_manager(self):
        pool = SessionPool()
        with pool.sync_session() as session:
            assert session is not None
        pool.close_sync()

    def test_close_sync(self):
        pool = SessionPool()
        pool.get_sync_session()
        pool.close_sync()
        assert pool._sync_session is None

    def test_close_sync_when_none(self):
        pool = SessionPool()
        pool.close_sync()  # エラーにならない

    def test_ssl_context_with_verification(self):
        pool = SessionPool(PoolConfig(enable_ssl_verification=True))
        ctx = pool._get_ssl_context()
        assert ctx.check_hostname is True

    def test_ssl_context_without_verification(self):
        pool = SessionPool(PoolConfig(enable_ssl_verification=False))
        ctx = pool._get_ssl_context()
        assert ctx.check_hostname is False


# ---------------------------------------------------------------------------
# EndpointPool テスト
# ---------------------------------------------------------------------------

class TestEndpointPool:
    """エンドポイントプールテスト"""

    def test_get_pool_creates_per_host(self):
        ep = EndpointPool()
        p1 = ep.get_pool("https://api.openai.com/v1/chat")
        p2 = ep.get_pool("https://api.openai.com/v1/models")
        assert p1 is p2  # 同じホスト

    def test_different_hosts_different_pools(self):
        ep = EndpointPool()
        p1 = ep.get_pool("https://api.openai.com/v1")
        p2 = ep.get_pool("https://api.anthropic.com/v1")
        assert p1 is not p2

    def test_close_all_sync(self):
        ep = EndpointPool()
        ep.get_pool("https://example.com")
        ep.close_all()
        assert len(ep._pools) == 0

    @pytest.mark.asyncio
    async def test_close_all_async(self):
        ep = EndpointPool()
        ep.get_pool("https://example.com")
        await ep.close_all_async()
        assert len(ep._pools) == 0

    def test_custom_config_per_pool(self):
        ep = EndpointPool()
        cfg = PoolConfig(pool_size=20)
        pool = ep.get_pool("https://example.com", config=cfg)
        assert pool.config.pool_size == 20


# ---------------------------------------------------------------------------
# グローバルプールテスト
# ---------------------------------------------------------------------------

class TestGlobalPool:
    """グローバルプールインスタンステスト"""

    def test_get_pool_singleton(self):
        reset_pool()
        p1 = get_pool()
        p2 = get_pool()
        assert p1 is p2
        reset_pool()

    def test_reset_pool(self):
        reset_pool()
        p1 = get_pool()
        reset_pool()
        p2 = get_pool()
        assert p1 is not p2
        reset_pool()

    def test_get_session_shortcut(self):
        reset_pool()
        session = get_session("https://example.com")
        assert session is not None
        reset_pool()


# ---------------------------------------------------------------------------
# TaskPriority / RoutingTask / TaskResult テスト
# ---------------------------------------------------------------------------

class TestRoutingDataClasses:
    """データクラステスト"""

    def test_task_priority_ordering(self):
        assert TaskPriority.CRITICAL.value < TaskPriority.HIGH.value
        assert TaskPriority.HIGH.value < TaskPriority.NORMAL.value
        assert TaskPriority.NORMAL.value < TaskPriority.LOW.value

    def test_routing_task_defaults(self):
        task = RoutingTask(id="t1", query="hello", model="gpt-4")
        assert task.priority == TaskPriority.NORMAL
        assert task.timeout == 60.0
        assert task.metadata == {}

    def test_task_result_success(self):
        result = TaskResult(task_id="t1", success=True, response="hello")
        assert result.success
        assert result.response == "hello"
        assert not result.from_cache

    def test_task_result_failure(self):
        result = TaskResult(task_id="t1", success=False, error="timeout")
        assert not result.success
        assert result.error == "timeout"


# ---------------------------------------------------------------------------
# AsyncRouter テスト
# ---------------------------------------------------------------------------

class TestAsyncRouter:
    """非同期ルーターテスト"""

    @pytest.mark.asyncio
    async def test_route_no_client_registered(self):
        router = AsyncRouter(enable_cache=False)
        result = await router.route("hello", "unknown_model")
        assert not result.success
        assert "No client registered" in result.error
        await router.close()

    @pytest.mark.asyncio
    async def test_register_and_route(self):
        router = AsyncRouter(enable_cache=False)
        client = AsyncMock(return_value="response text")
        router.register_model_client("test_model", client)
        result = await router.route("hello", "test_model")
        assert result.success
        assert result.response == "response text"
        assert result.model == "test_model"
        assert not result.from_cache
        await router.close()

    @pytest.mark.asyncio
    async def test_route_timeout(self):
        router = AsyncRouter(enable_cache=False)

        async def slow_client(query):
            await asyncio.sleep(5)
            return "late"

        router.register_model_client("slow", slow_client)
        result = await router.route("hello", "slow", timeout=0.1)
        assert not result.success
        assert "Timeout" in result.error
        await router.close()

    @pytest.mark.asyncio
    async def test_route_client_error(self):
        router = AsyncRouter(enable_cache=False)
        client = AsyncMock(side_effect=RuntimeError("boom"))
        router.register_model_client("broken", client)
        result = await router.route("hello", "broken")
        assert not result.success
        assert "boom" in result.error
        await router.close()

    @pytest.mark.asyncio
    async def test_stats_tracking(self):
        router = AsyncRouter(enable_cache=False)
        client = AsyncMock(return_value="ok")
        router.register_model_client("m", client)

        await router.route("q1", "m")
        await router.route("q2", "m")

        stats = router.get_stats()
        assert stats["total_requests"] == 2
        assert stats["successful_requests"] == 2
        assert stats["failed_requests"] == 0
        assert stats["success_rate"] == 1.0
        await router.close()

    @pytest.mark.asyncio
    async def test_stats_with_failures(self):
        """未登録モデルでは _execute_task が early return するため stats は更新されない"""
        router = AsyncRouter(enable_cache=False)
        result = await router.route("q", "nonexistent")
        assert not result.success
        # 未登録モデルの場合は _update_stats を呼ばずに早期リターン
        stats = router.get_stats()
        assert stats["total_requests"] == 0

        # クライアントエラーの場合は統計が更新される
        client = AsyncMock(side_effect=RuntimeError("boom"))
        router.register_model_client("err", client)
        await router.route("q", "err")
        stats = router.get_stats()
        assert stats["total_requests"] == 1
        assert stats["failed_requests"] == 1
        await router.close()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        async with AsyncRouter(enable_cache=False) as router:
            client = AsyncMock(return_value="ok")
            router.register_model_client("m", client)
            result = await router.route("q", "m")
            assert result.success


# ---------------------------------------------------------------------------
# route_multiple テスト
# ---------------------------------------------------------------------------

class TestRouteMultiple:
    """複数リクエスト並列処理テスト"""

    @pytest.mark.asyncio
    async def test_empty_queries(self):
        router = AsyncRouter(enable_cache=False)
        results = await router.route_multiple([])
        assert results == []
        await router.close()

    @pytest.mark.asyncio
    async def test_multiple_success(self):
        router = AsyncRouter(enable_cache=False)
        client = AsyncMock(return_value="response")
        router.register_model_client("m", client)

        queries = [
            {"query": "q1", "model": "m"},
            {"query": "q2", "model": "m"},
            {"query": "q3", "model": "m"},
        ]
        results = await router.route_multiple(queries)
        assert len(results) == 3
        assert all(r.success for r in results)
        await router.close()

    @pytest.mark.asyncio
    async def test_multiple_with_parallel_limit(self):
        router = AsyncRouter(enable_cache=False)
        call_count = 0

        async def counting_client(query):
            nonlocal call_count
            call_count += 1
            return f"result_{query}"

        router.register_model_client("m", counting_client)
        queries = [{"query": f"q{i}", "model": "m"} for i in range(5)]
        results = await router.route_multiple(queries, max_parallel=2)
        assert len(results) == 5
        assert call_count == 5
        await router.close()

    @pytest.mark.asyncio
    async def test_multiple_with_errors(self):
        router = AsyncRouter(enable_cache=False)
        results = await router.route_multiple([
            {"query": "q1", "model": "nonexistent"},
        ])
        assert len(results) == 1
        assert not results[0].success
        await router.close()


# ---------------------------------------------------------------------------
# BatchProcessor テスト
# ---------------------------------------------------------------------------

class TestBatchProcessor:
    """バッチ処理テスト"""

    @pytest.mark.asyncio
    async def test_batch_processing(self):
        router = AsyncRouter(enable_cache=False)
        client = AsyncMock(return_value="ok")
        router.register_model_client("m", client)

        processor = BatchProcessor(router, batch_size=3)
        items = [{"query": f"q{i}", "model": "m"} for i in range(7)]
        results = await processor.process(items)
        assert len(results) == 7
        await router.close()

    @pytest.mark.asyncio
    async def test_batch_with_progress_callback(self):
        router = AsyncRouter(enable_cache=False)
        client = AsyncMock(return_value="ok")
        router.register_model_client("m", client)

        progress_calls = []
        processor = BatchProcessor(router, batch_size=2)
        items = [{"query": f"q{i}", "model": "m"} for i in range(5)]
        await processor.process(items, progress_callback=lambda c, t: progress_calls.append((c, t)))
        assert len(progress_calls) == 3  # ceil(5/2) = 3 batches
        assert progress_calls[-1] == (5, 5)
        await router.close()


# ---------------------------------------------------------------------------
# SyncRouterWrapper テスト
# ---------------------------------------------------------------------------

class TestSyncRouterWrapper:
    """同期ラッパーテスト"""

    def test_sync_route(self):
        router = AsyncRouter(enable_cache=False)
        client = AsyncMock(return_value="sync result")
        router.register_model_client("m", client)
        wrapper = SyncRouterWrapper(router)
        result = wrapper.route("hello", "m")
        assert result.success
        assert result.response == "sync result"

    def test_sync_route_multiple(self):
        router = AsyncRouter(enable_cache=False)
        client = AsyncMock(return_value="ok")
        router.register_model_client("m", client)
        wrapper = SyncRouterWrapper(router)
        results = wrapper.route_multiple([
            {"query": "q1", "model": "m"},
            {"query": "q2", "model": "m"},
        ])
        assert len(results) == 2
        assert all(r.success for r in results)


# ---------------------------------------------------------------------------
# create_router ファクトリテスト
# ---------------------------------------------------------------------------

class TestCreateRouter:
    """ファクトリ関数テスト"""

    def test_create_default(self):
        router = create_router()
        assert isinstance(router, AsyncRouter)

    def test_create_sync_mode(self):
        router = create_router(sync_mode=True)
        assert isinstance(router, SyncRouterWrapper)

    def test_create_with_config(self):
        router = create_router(config={"max_concurrent": 10, "enable_cache": False})
        assert isinstance(router, AsyncRouter)
        assert router.max_concurrent == 10


# ---------------------------------------------------------------------------
# セマフォ制限テスト
# ---------------------------------------------------------------------------

class TestConcurrencyLimit:
    """同時接続制限テスト"""

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self):
        """セマフォが同時接続数を制限する"""
        max_concurrent = 2
        router = AsyncRouter(max_concurrent=max_concurrent, enable_cache=False)
        active = 0
        max_active = 0

        async def tracking_client(query):
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.05)
            active -= 1
            return "ok"

        router.register_model_client("m", tracking_client)
        queries = [{"query": f"q{i}", "model": "m"} for i in range(6)]
        await router.route_multiple(queries)
        assert max_active <= max_concurrent
        await router.close()
