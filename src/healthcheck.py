"""
LLM Smart Router ヘルスチェック

セットアップの検証を行い、結果をカラー表示する。

Usage:
    python -m healthcheck
"""

import sys
import os
import subprocess
import shutil
from pathlib import Path

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent


# ── 色付き出力 ──

def _supports_color():
    if os.getenv("NO_COLOR"):
        return False
    if sys.platform == "win32":
        os.system("")  # ANSIエスケープ有効化
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

USE_COLOR = _supports_color()

def _c(code, text):
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text

def ok(msg):
    print(f"  {_c('32', 'OK')}  {msg}")

def warn(msg):
    print(f"  {_c('33', '!')}   {msg}")

def fail(msg):
    print(f"  {_c('31', 'X')}   {msg}")

def info(msg):
    print(f"  {_c('36', '-')}   {msg}")


# ── チェック関数 ──

def check_python():
    """Pythonバージョン確認"""
    v = sys.version_info
    version_str = f"Python {v.major}.{v.minor}.{v.micro}"
    if (v.major, v.minor) >= (3, 9):
        ok(version_str)
        return True
    else:
        fail(f"{version_str} (3.9以上が必要)")
        return False


def check_node():
    """Node.js確認"""
    node = shutil.which("node")
    if not node:
        warn("Node.js が見つかりません（Router / Discord Bot に必要）")
        return False
    try:
        result = subprocess.run(
            ["node", "--version"], capture_output=True, text=True, timeout=5
        )
        ok(f"Node.js {result.stdout.strip()}")
        return True
    except Exception:
        warn("Node.js バージョン取得失敗")
        return False


def check_python_packages():
    """主要Pythonパッケージの確認"""
    packages = {
        "fastapi": "FastAPI",
        "uvicorn": "Uvicorn",
        "pydantic": "Pydantic",
        "aiohttp": "aiohttp",
        "yaml": "PyYAML",
        "requests": "Requests",
        "click": "Click",
        "rich": "Rich",
    }
    gui_packages = {
        "PySide6": "PySide6 (GUI)",
    }

    all_ok = True
    for module, name in packages.items():
        try:
            __import__(module)
            ok(name)
        except ImportError:
            fail(f"{name} がインストールされていません")
            all_ok = False

    for module, name in gui_packages.items():
        try:
            __import__(module)
            ok(name)
        except ImportError:
            warn(f"{name} がインストールされていません（GUIを使わなければ不要）")

    return all_ok


def check_node_packages():
    """Node.jsパッケージの確認"""
    node_modules = PROJECT_ROOT / "node_modules"
    if not node_modules.exists():
        warn("node_modules/ が見つかりません（npm install が必要）")
        return False

    packages = ["axios", "@anthropic-ai/sdk", "js-yaml", "discord.js"]
    all_ok = True
    for pkg in packages:
        pkg_dir = node_modules / pkg
        if pkg_dir.exists():
            ok(f"npm: {pkg}")
        else:
            warn(f"npm: {pkg} がインストールされていません")
            all_ok = False
    return all_ok


def check_env_file():
    """環境変数ファイルの確認"""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        fail(".env ファイルが見つかりません（setup.bat を実行してください）")
        return False

    ok(".env ファイルあり")

    # APIキーの確認
    keys = {
        "ANTHROPIC_API_KEY": "Anthropic (Claude)",
        "OPENAI_API_KEY": "OpenAI (GPT-4o)",
        "GOOGLE_API_KEY": "Google (Gemini)",
        "OPENROUTER_API_KEY": "OpenRouter (Kimi)",
    }

    # .env を読み込み
    env_vars = {}
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    env_vars[k.strip()] = v.strip()
    except Exception:
        pass

    has_any_key = False
    for env_key, display_name in keys.items():
        # 環境変数 or .envファイルから
        value = os.getenv(env_key) or env_vars.get(env_key, "")
        # プレースホルダーは無視
        if value and "your-key" not in value and "your_key" not in value and len(value) > 5:
            ok(f"{display_name}: 設定済み")
            has_any_key = True
        else:
            info(f"{display_name}: 未設定")

    if not has_any_key:
        warn("APIキーが1つも設定されていません。.env ファイルを編集してください")

    return True


def check_config():
    """設定ファイルの確認"""
    config_path = PROJECT_ROOT / "config.yaml"
    if config_path.exists():
        ok("config.yaml あり")
        return True
    else:
        fail("config.yaml が見つかりません")
        return False


def check_directories():
    """必要ディレクトリの確認"""
    dirs = ["data", "logs", "cache", "queue"]
    all_ok = True
    for d in dirs:
        p = PROJECT_ROOT / d
        if p.exists():
            ok(f"{d}/")
        else:
            warn(f"{d}/ が見つかりません")
            all_ok = False
    return all_ok


def check_model_registry():
    """モデルレジストリの確認"""
    registry_path = PROJECT_ROOT / "data" / "model_registry.json"
    if registry_path.exists():
        try:
            import json
            with open(registry_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            models = data.get("models", {})
            total = sum(len(v) for v in models.values())
            last_scan = data.get("last_scan", "不明")
            ok(f"モデルレジストリ: {total}モデル検出済み (最終スキャン: {last_scan})")
            return True
        except Exception:
            warn("モデルレジストリの読み込みに失敗")
            return False
    else:
        info("モデルレジストリ未作成（python -m scanner scan で作成）")
        return False


# ── メイン ──

def main():
    print()
    print(f"  {_c('1;36', 'LLM Smart Router ヘルスチェック')}")
    print(f"  {'─' * 50}")
    print()

    results = []

    print(f"  {_c('1', 'ランタイム')}")
    results.append(check_python())
    results.append(check_node())
    print()

    print(f"  {_c('1', 'Python パッケージ')}")
    results.append(check_python_packages())
    print()

    print(f"  {_c('1', 'Node.js パッケージ')}")
    results.append(check_node_packages())
    print()

    print(f"  {_c('1', '設定ファイル')}")
    results.append(check_env_file())
    results.append(check_config())
    print()

    print(f"  {_c('1', 'ディレクトリ')}")
    results.append(check_directories())
    print()

    print(f"  {_c('1', 'モデル検出')}")
    results.append(check_model_registry())
    print()

    # サマリー
    print(f"  {'─' * 50}")
    if all(results):
        print(f"  {_c('32', '全チェック通過！ セットアップは正常です。')}")
        return 0
    else:
        failed = results.count(False)
        print(f"  {_c('33', f'{failed}個の項目に対応が必要です。')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
