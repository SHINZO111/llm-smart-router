"""
LM Studio CLI

コマンドラインインターフェースからLM Studioモデル検出機能を使用

Usage:
    python -m lmstudio detect     # モデル検出して表示
    python -m lmstudio update     # 検出してconfig更新
    python -m lmstudio status     # LM Studio状態確認
    python -m lmstudio list       # モデル一覧表示（テーブル形式）
"""

import sys
import argparse
import logging
from pathlib import Path
import io

# Windows環境でのエンコーディング対応
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from .model_detector import LMStudioModelDetector

# ロギング設定
def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s"
    )


def cmd_detect(args):
    """モデル検出コマンド"""
    detector = LMStudioModelDetector(endpoint=args.endpoint)
    
    print(f"LM Studio ({args.endpoint}) に接続中...")
    
    if not detector.is_running():
        print("❌ LM Studioが起動していないか、接続できません")
        print("   LM Studioを起動してモデルを読み込んでください")
        return 1
    
    print("✅ LM Studioに接続成功\n")
    
    try:
        models = detector.get_loaded_models()
        
        if not models:
            print("⚠️  モデルが読み込まれていません")
            print("   LM Studioでモデルを読み込んでください")
            return 1
        
        print(f"検出されたモデル: {len(models)}個\n")
        
        for i, model in enumerate(models, 1):
            default_mark = " ⭐ デフォルト" if i == 1 else ""
            print(f"{i}. {model.id}{default_mark}")
            if model.name and model.name != model.id:
                print(f"   名前: {model.name}")
            if model.description:
                print(f"   説明: {model.description}")
            print()
        
        return 0
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        return 1


def cmd_update(args):
    """設定更新コマンド"""
    detector = LMStudioModelDetector(endpoint=args.endpoint)
    
    # 設定ファイルパスの決定
    config_path = args.config or find_config_file()
    
    print(f"LM Studio ({args.endpoint}) に接続中...")
    
    if not detector.is_running():
        print("❌ LM Studioが起動していないか、接続できません")
        print("   既存の設定を維持します")
        return 1
    
    print("✅ LM Studioに接続成功\n")
    
    print(f"設定ファイル: {config_path}")
    
    result = detector.detect_and_update_config(config_path)
    
    if result["success"]:
        print(f"✅ 設定を更新しました")
        print(f"   検出モデル: {result['models_detected']}個")
        print(f"   デフォルトモデル: {result['default_model']}")
        
        if len(result["models"]) > 1:
            print(f"\n   追加されたモデル:")
            for i, model in enumerate(result["models"][1:], 2):
                print(f"     {i}. {model['id']}")
        
        return 0
    else:
        print("❌ 設定の更新に失敗しました")
        for error in result["errors"]:
            print(f"   - {error}")
        print("   既存の設定を維持します")
        return 1


def cmd_status(args):
    """状態確認コマンド"""
    detector = LMStudioModelDetector(endpoint=args.endpoint)
    
    print(f"LM Studio状態確認 ({args.endpoint})")
    print("-" * 50)
    
    is_running = detector.is_running()
    
    if is_running:
        print("✅ LM Studio: 起動中")
        
        try:
            models = detector.get_loaded_models()
            print(f"📦 読み込み済みモデル: {len(models)}個")
            
            if models:
                print(f"🎯 デフォルトモデル: {models[0].id}")
                for model in models[:3]:  # 最大3つまで表示
                    print(f"   - {model.id}")
                if len(models) > 3:
                    print(f"   ... 他 {len(models) - 3} 個")
            else:
                print("⚠️  モデルが読み込まれていません")
                
        except Exception as e:
            print(f"⚠️  モデル情報取得エラー: {e}")
    else:
        print("❌ LM Studio: 未起動または接続不可")
        print("   LM Studioを起動してください")
    
    return 0 if is_running else 1


def cmd_list(args):
    """モデル一覧表示（テーブル形式）"""
    detector = LMStudioModelDetector(endpoint=args.endpoint)
    
    if not detector.is_running():
        print("❌ LM Studioが起動していません")
        return 1
    
    print(detector.format_models_table())
    return 0


def find_config_file() -> str:
    """設定ファイルを探す"""
    # 優先順位: カレントディレクトリ > srcディレクトリ > 親ディレクトリ
    candidates = [
        "config.yaml",
        "src/config.yaml",
        "../config.yaml",
        "../../config.yaml",
    ]
    
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return str(path.resolve())
    
    # 見つからない場合はデフォルト
    return "config.yaml"


def main():
    """メインエントリーポイント"""
    parser = argparse.ArgumentParser(
        prog="python -m lmstudio",
        description="LM Studio Model Detector CLI"
    )
    
    parser.add_argument(
        "-e", "--endpoint",
        default="http://localhost:1234/v1",
        help="LM Studio APIエンドポイント (デフォルト: http://localhost:1234/v1)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="詳細なログ出力"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="コマンド")
    
    # detect コマンド
    detect_parser = subparsers.add_parser(
        "detect",
        help="モデルを検出して表示"
    )
    detect_parser.set_defaults(func=cmd_detect)
    
    # update コマンド
    update_parser = subparsers.add_parser(
        "update",
        help="検出してconfig.yamlを更新"
    )
    update_parser.add_argument(
        "-c", "--config",
        help="設定ファイルのパス"
    )
    update_parser.set_defaults(func=cmd_update)
    
    # status コマンド
    status_parser = subparsers.add_parser(
        "status",
        help="LM Studioの状態を確認"
    )
    status_parser.set_defaults(func=cmd_status)
    
    # list コマンド
    list_parser = subparsers.add_parser(
        "list",
        help="モデル一覧をテーブル形式で表示"
    )
    list_parser.set_defaults(func=cmd_list)
    
    # 引数がない場合はヘルプを表示
    if len(sys.argv) == 1:
        parser.print_help()
        return 0
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    if hasattr(args, "func"):
        return args.func(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
