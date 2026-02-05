"""
Scanner CLI

コマンドラインからマルチランタイムスキャンを実行

Usage:
    python -m scanner scan          # 全ランタイムスキャン
    python -m scanner scan --no-cloud  # ローカルのみ
    python -m scanner status        # レジストリ表示
    python -m scanner detect        # レガシー互換（LM Studioのみ）
"""

import sys
import io
import argparse
import asyncio
import logging
from pathlib import Path

# Windows環境でのエンコーディング対応
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from .scanner import MultiRuntimeScanner
from .registry import ModelRegistry
from .runtime_info import ModelSource

# プロジェクトルート基準のレジストリパス (src/ の親)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_REGISTRY = str(_PROJECT_ROOT / "data" / "model_registry.json")


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def cmd_scan(args):
    """全ランタイムスキャン"""
    include_cloud = not args.no_cloud
    scanner = MultiRuntimeScanner(
        timeout=args.timeout,
        include_cloud=include_cloud,
    )

    print(f"スキャン中... (タイムアウト: {args.timeout}秒)")

    results = asyncio.run(scanner.scan_all())

    if not results:
        print("\n検出されたランタイムはありません")
        print("  LM Studio, Ollama 等を起動してください")
        return 1

    # レジストリに保存
    registry = ModelRegistry(cache_path=args.registry)
    registry.update(results)

    print(f"\n{'='*60}")
    print(f"スキャン結果: {registry.get_total_count()}モデル検出")
    print(f"{'='*60}")

    for runtime_key, models in results.items():
        icon = "☁️" if runtime_key == "cloud" else "💻"
        print(f"\n{icon} {runtime_key}: {len(models)}モデル")
        for model in models:
            print(f"  - {model.id}")
            if model.description:
                print(f"    {model.description}")

    print(f"\nレジストリ保存先: {args.registry}")
    return 0


def cmd_status(args):
    """レジストリの現在状態を表示"""
    registry = ModelRegistry(cache_path=args.registry)

    if registry.get_total_count() == 0:
        print("レジストリは空です。`python -m scanner scan` を実行してください")
        return 1

    valid = registry.is_cache_valid()
    print(f"最終スキャン: {registry.last_scan_iso or '不明'}")
    print(f"キャッシュ: {'有効' if valid else '期限切れ'}")
    print(f"{'='*60}")

    local_models = registry.get_local_models()
    cloud_models = registry.get_cloud_models()

    if local_models:
        print(f"\n💻 ローカルモデル: {len(local_models)}個")
        for m in local_models:
            rt = m.runtime.runtime_type.value if m.runtime else "?"
            port = m.runtime.port if m.runtime else "?"
            print(f"  [{rt}:{port}] {m.id}")

    if cloud_models:
        print(f"\n☁️ クラウドモデル: {len(cloud_models)}個")
        for m in cloud_models:
            key_status = "✓" if m.api_key_present else "✗"
            print(f"  [{m.provider} {key_status}] {m.id} - {m.name}")

    return 0


def cmd_detect(args):
    """レガシー互換: LM Studioのみ検出"""
    from .runtime_detectors import LMStudioDetector

    port = 1234
    detector = LMStudioDetector("localhost", port, timeout=args.timeout)

    print(f"LM Studio (localhost:{port}) に接続中...")

    async def _run():
        detected, runtime_info = await detector.detect()
        if not detected:
            return None, []
        models = await detector.get_models(runtime_info)
        return runtime_info, models

    runtime_info, models = asyncio.run(_run())

    if runtime_info is None:
        print("LM Studioが起動していないか、接続できません")
        return 1

    print(f"LM Studio検出 ({runtime_info.response_time_ms:.0f}ms)\n")

    if not models:
        print("モデルが読み込まれていません")
        return 1

    print(f"検出モデル: {len(models)}個\n")
    for i, model in enumerate(models, 1):
        default_mark = " [デフォルト]" if i == 1 else ""
        print(f"  {i}. {model.id}{default_mark}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="python -m scanner",
        description="LLM Runtime Scanner - ローカルLLMランタイム自動検出",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="詳細ログ")
    parser.add_argument(
        "--registry",
        default=_DEFAULT_REGISTRY,
        help="レジストリJSON保存先 (デフォルト: <project_root>/data/model_registry.json)",
    )

    subparsers = parser.add_subparsers(dest="command", help="コマンド")

    # scan
    scan_p = subparsers.add_parser("scan", help="全ランタイムスキャン")
    scan_p.add_argument("--timeout", type=float, default=2.0, help="ポートあたりタイムアウト(秒)")
    scan_p.add_argument("--no-cloud", action="store_true", help="クラウド検出をスキップ")
    scan_p.set_defaults(func=cmd_scan)

    # status
    status_p = subparsers.add_parser("status", help="レジストリ状態表示")
    status_p.set_defaults(func=cmd_status)

    # detect (レガシー)
    detect_p = subparsers.add_parser("detect", help="LM Studioモデル検出 (レガシー)")
    detect_p.add_argument("--timeout", type=float, default=5.0)
    detect_p.set_defaults(func=cmd_detect)

    if len(sys.argv) == 1:
        parser.print_help()
        return 1

    args = parser.parse_args()
    setup_logging(args.verbose)

    if hasattr(args, "func"):
        return args.func(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
