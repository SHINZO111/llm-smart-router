"""
Auto-Launch Chain CLI エントリポイント

Usage:
    python -m launcher                  # フルチェーン実行
    python -m launcher --skip-discord   # Discord Bot スキップ
    python -m launcher --dry-run        # プレビュー
    python -m launcher -v               # 詳細ログ
"""

import sys
import argparse
import logging
from pathlib import Path

# プロジェクトルートをパスに追加（まだ追加されていない場合のみ）
PROJECT_ROOT = Path(__file__).parent.parent.parent
_src_path = str(PROJECT_ROOT / "src")
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

from launcher.orchestrator import LaunchOrchestrator, LaunchConfig, StageStatus


def setup_logging(verbose: bool = False) -> None:
    """ログ設定"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cli_progress(name: str, status: StageStatus, message: str) -> None:
    """CLI用の進捗表示"""
    icon = {
        StageStatus.RUNNING: ">>>",
        StageStatus.SUCCESS: "[OK]",
        StageStatus.FAILED: "[NG]",
        StageStatus.SKIPPED: "[--]",
        StageStatus.PENDING: "   ",
    }.get(status, "   ")
    print(f"  {icon} {name}: {message}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="LLM Smart Router Auto-Launch Chain",
        prog="python -m launcher",
    )
    parser.add_argument(
        "--skip-discord",
        action="store_true",
        help="Discord Botステージをスキップ",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="実行せずステージ構成をプレビュー",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="詳細ログを表示",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="設定ファイルパス（デフォルト: config.yaml）",
    )

    args = parser.parse_args()
    setup_logging(verbose=args.verbose)

    print("=" * 50)
    print("  LLM Smart Router - Auto-Launch Chain")
    print("=" * 50)
    print()

    # 設定読み込み
    config = LaunchConfig.from_yaml(args.config)

    # オーケストレーター起動
    orchestrator = LaunchOrchestrator(
        config=config,
        on_progress=cli_progress,
        dry_run=args.dry_run,
    )

    try:
        results = orchestrator.run(skip_discord=args.skip_discord)
    except KeyboardInterrupt:
        print("\n中断されました")
        orchestrator.shutdown()
        return 1

    # 終了コード: 全ステージ成功なら0、失敗があれば1
    has_failure = any(
        r.status == StageStatus.FAILED for r in results
    )
    return 1 if has_failure else 0


if __name__ == "__main__":
    sys.exit(main())
