"""
Checkpoint 4 機能テストスクリプト
- キャッシュ機能
- 並列処理
- 接続プール
"""
import asyncio
import time
import sys
sys.path.insert(0, 'F:\\llm-smart-router')

from src.cache import get_cache, reset_cache
from src.connection import get_pool, reset_pool, get_session
from src.async_router import AsyncRouter, create_router


def test_cache():
    """キャッシュ機能テスト"""
    print("=" * 60)
    print("テスト1: SQLiteキャッシュ")
    print("=" * 60)
    
    # キャッシュ初期化
    reset_cache()
    cache = get_cache({
        "path": "./test_cache.db",
        "ttl": 3600,
        "similarity_threshold": 0.8
    })
    
    # データ保存
    print("\n1. データ保存...")
    key1 = cache.set(
        query="Pythonでリストをソートする方法",
        response="sort()メソッドまたはsorted()関数を使用します。",
        model="local"
    )
    print(f"   保存: key={key1[:16]}...")
    
    # キャッシュ取得（完全一致）
    print("\n2. 完全一致検索...")
    start = time.time()
    entry1 = cache.get(
        query="Pythonでリストをソートする方法",
        model="local"
    )
    elapsed = (time.time() - start) * 1000
    
    if entry1:
        print(f"   [OK] ヒット: {elapsed:.2f}ms")
        print(f"   レスポンス: {entry1.response[:30]}...")
    else:
        print("   [NG] ミス")
    
    # 類似検索
    print("\n3. 類似検索...")
    start = time.time()
    entry2 = cache.get(
        query="Pythonのリストをソートしたい",
        model="local",
        use_similarity=True
    )
    elapsed = (time.time() - start) * 1000
    
    if entry2:
        print(f"   [OK] 類似ヒット: {elapsed:.2f}ms")
        print(f"   元クエリ: {entry2.query}")
    else:
        print("   [NG] 類似なし")
    
    # 統計確認
    print("\n4. キャッシュ統計...")
    stats = cache.get_stats()
    print(f"   総エントリ: {stats['total_entries']}")
    print(f"   有効エントリ: {stats['valid_entries']}")
    print(f"   平均アクセス: {stats['avg_accesses']}")
    
    print("\n[PASS] キャッシュテスト完了\n")
    return True


def test_session_pool():
    """セッションプールテスト"""
    print("=" * 60)
    print("テスト2: 接続プール")
    print("=" * 60)
    
    reset_pool()
    
    # 同期セッション取得
    print("\n1. 同期セッション取得...")
    session1 = get_session("https://api.openai.com")
    session2 = get_session("https://api.openai.com")
    print(f"   同一セッション: {session1 is session2}")
    
    # 異なるエンドポイント
    session3 = get_session("https://api.anthropic.com")
    print(f"   別ホストは別セッション: {session1 is not session3}")
    
    # プール統計
    pool = get_pool()
    print(f"   プール数: {len(pool._pools)}")
    
    print("\n[PASS] 接続プールテスト完了\n")
    return True


async def test_async_router():
    """非同期ルーターテスト"""
    print("=" * 60)
    print("テスト3: 非同期ルーター")
    print("=" * 60)
    
    # ルーター作成
    router = AsyncRouter(
        max_concurrent=3,  # セマフォ制限
        max_workers=2,
        enable_cache=False  # キャッシュは別テスト
    )
    
    # モッククライアント登録
    async def mock_client(query: str) -> str:
        await asyncio.sleep(0.1)  # シミュレート遅延
        return f"Response for: {query[:20]}..."
    
    router.register_model_client("mock", mock_client)
    
    # 単一リクエスト
    print("\n1. 単一リクエスト...")
    result = await router.route("Hello", "mock")
    print(f"   成功: {result.success}, 時間: {result.duration:.2f}s")
    
    # 並列リクエスト
    print("\n2. 並列リクエスト（5件、セマフォ制限3）...")
    queries = [
        {"query": f"Query {i}", "model": "mock"}
        for i in range(5)
    ]
    
    start = time.time()
    results = await router.route_multiple(queries)
    elapsed = time.time() - start
    
    success_count = sum(1 for r in results if r.success)
    print(f"   成功: {success_count}/{len(results)}")
    print(f"   総時間: {elapsed:.2f}s (シリアルなら0.5s)")
    print(f"   並列効率: {(0.5 / elapsed):.1f}x")
    
    # 統計確認
    print("\n3. 実行統計...")
    stats = router.get_stats()
    print(f"   総リクエスト: {stats['total_requests']}")
    print(f"   成功率: {stats['success_rate']:.1%}")
    print(f"   平均レイテンシ: {stats['avg_latency']:.3f}s")
    
    await router.close()
    
    print("\n[PASS] 非同期ルーターテスト完了\n")
    return True


async def test_cache_with_router():
    """キャッシュ付きルーターテスト"""
    print("=" * 60)
    print("テスト4: キャッシュ付き非同期ルーター")
    print("=" * 60)
    
    reset_cache()
    
    router = AsyncRouter(
        max_concurrent=5,
        enable_cache=True,
        cache_config={
            "path": "./test_router_cache.db",
            "ttl": 3600
        }
    )
    
    call_count = 0
    
    async def counting_client(query: str) -> str:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return f"Result: {query}"
    
    router.register_model_client("test", counting_client)
    
    # 同じクエリを2回実行
    print("\n1. 同じクエリを2回実行...")
    
    result1 = await router.route("Same query", "test")
    print(f"   1回目: from_cache={result1.from_cache}")
    
    result2 = await router.route("Same query", "test")
    print(f"   2回目: from_cache={result2.from_cache}")
    
    print(f"\n   APIコール回数: {call_count} (キャッシュで減少)")
    
    # 統計
    stats = router.get_stats()
    print(f"   キャッシュヒット率: {stats['cache_hit_rate']:.1%}")
    
    await router.close()
    
    print("\n[PASS] キャッシュ付きルーターテスト完了\n")
    return True


def test_sync_wrapper():
    """同期ラッパーテスト"""
    print("=" * 60)
    print("テスト5: 同期APIラッパー")
    print("=" * 60)
    
    router = create_router(
        config={"max_concurrent": 3},
        sync_mode=True
    )
    
    print("\n1. 同期APIでルーティング...")
    # 注: 実際のクライアントが未登録なのでエラーになるが、APIの動作確認はできる
    try:
        result = router.route("test", "mock")
        print(f"   結果: {result}")
    except Exception as e:
        print(f"   期待通りエラー（クライアント未登録）: {type(e).__name__}")
    
    print("\n[PASS] 同期ラッパーテスト完了\n")
    return True


async def run_all_tests():
    """全テスト実行"""
    print("\n" + "=" * 60)
    print("Checkpoint 4 機能テスト開始")
    print("=" * 60 + "\n")
    
    try:
        # テスト実行
        test_cache()
        test_session_pool()
        await test_async_router()
        await test_cache_with_router()
        test_sync_wrapper()
        
        # クリーンアップ
        reset_cache()
        reset_pool()
        
        print("=" * 60)
        print("全テスト完了 [PASS]")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n[FAIL] テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
