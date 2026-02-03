"""
LM Studio Router Integration Example

router.jsとの連携用ユーティリティ
起動時に自動検出を実行し、検出したモデル情報をログ出力する
"""

import subprocess
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def detect_on_startup(config_path="./config.yaml", endpoint="http://localhost:1234/v1"):
    """
    起動時にLM Studioのモデルを自動検出
    
    router.jsの起動処理から呼び出すことを想定
    
    Args:
        config_path: 設定ファイルのパス
        endpoint: LM Studio APIエンドポイント
        
    Returns:
        dict: 検出結果
    """
    try:
        # Pythonモジュールを実行
        result = subprocess.run(
            [
                "python", "-m", "lmstudio", "detect",
                "--endpoint", endpoint
            ],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            logger.info("✅ LM Studioモデルを検出しました")
            logger.info(result.stdout)
            return {"success": True, "output": result.stdout}
        else:
            logger.warning("⚠️  LM Studioモデルの検出に失敗しました")
            logger.warning(result.stderr)
            return {"success": False, "error": result.stderr}
            
    except subprocess.TimeoutExpired:
        logger.warning("⏱️  LM Studio検出がタイムアウトしました")
        return {"success": False, "error": "timeout"}
    except FileNotFoundError:
        logger.warning("🐍 Pythonが見つかりません")
        return {"success": False, "error": "python not found"}
    except Exception as e:
        logger.error(f"❌ 予期しないエラー: {e}")
        return {"success": False, "error": str(e)}


def update_config_on_startup(config_path="./config.yaml", endpoint="http://localhost:1234/v1"):
    """
    起動時にLM Studioのモデルを検出してconfig.yamlを更新
    
    Args:
        config_path: 設定ファイルのパス
        endpoint: LM Studio APIエンドポイント
        
    Returns:
        dict: 更新結果
    """
    try:
        result = subprocess.run(
            [
                "python", "-m", "lmstudio", "update",
                "--config", config_path,
                "--endpoint", endpoint
            ],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            logger.info("✅ config.yamlを更新しました")
            logger.info(result.stdout)
            return {"success": True, "output": result.stdout}
        else:
            logger.warning("⚠️  config.yamlの更新に失敗しました")
            return {"success": False, "error": result.stderr}
            
    except Exception as e:
        logger.error(f"❌ エラー: {e}")
        return {"success": False, "error": str(e)}


def get_lmstudio_status(endpoint="http://localhost:1234/v1"):
    """
    LM Studioの状態を取得（JSON形式）
    
    Returns:
        dict: 状態情報
    """
    try:
        from lmstudio.model_detector import LMStudioModelDetector
        
        detector = LMStudioModelDetector(endpoint=endpoint)
        
        if not detector.is_running():
            return {
                "running": False,
                "models": [],
                "default_model": None
            }
        
        models = detector.get_loaded_models()
        default = detector.get_default_model()
        
        return {
            "running": True,
            "models": [m.to_dict() for m in models],
            "default_model": default,
            "model_count": len(models)
        }
        
    except Exception as e:
        return {
            "running": False,
            "error": str(e),
            "models": [],
            "default_model": None
        }


# 直接実行時のテスト
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("LM Studio Router Integration Test")
    print("=" * 60)
    
    # 状態確認
    status = get_lmstudio_status()
    print(f"\nLM Studio状態: {'✅ 起動中' if status['running'] else '❌ 未起動'}")
    
    if status['running']:
        print(f"モデル数: {status['model_count']}")
        print(f"デフォルトモデル: {status['default_model']}")
        print("\n検出されたモデル:")
        for model in status['models']:
            print(f"  - {model['id']}")
    
    # 検出テスト
    print("\n" + "-" * 60)
    print("モデル検出テスト:")
    print("-" * 60)
    result = detect_on_startup()
    print(result['output'] if result['success'] else result['error'])
