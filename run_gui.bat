@echo off
chcp 65001 > nul
REM =====================================================
REM LLM Smart Router Pro - GUI Launcher
REM =====================================================
REM 
REM 【概要】
REM 世界最高峰のLLMルーターGUIアプリケーションを起動
REM 
REM 【機能】
REM - ローカルLLMとClaudeの自動切替
REM - APIキー暗号化保存
REM - 統計ダッシュボード
REM - 用途別プリセット
REM 
REM 【作者】クラ for 新さん
REM 【バージョン】2.0.0
REM =====================================================

echo.
echo   ╔══════════════════════════════════════════════════════════════╗
echo   ║                                                              ║
echo   ║           🤖 LLM Smart Router Pro v2.0 🤖                    ║
echo   ║                                                              ║
echo   ║     ローカルLLM × Claude インテリジェントルーティング        ║
echo   ║                                                              ║
echo   ╚══════════════════════════════════════════════════════════════╝
echo.

REM 作業ディレクトリ設定
set "ROUTER_DIR=%~dp0"
cd /d "%ROUTER_DIR%"

REM Pythonチェック
echo 🔍 Pythonを確認中...
python --version > nul 2>&1
if errorlevel 1 (
    echo ❌ Pythonが見つかりません
    echo 📥 https://python.org からインストールしてください
    pause
    exit /b 1
)

for /f "tokens=*" %%a in ('python --version 2^>^&1') do set PYTHON_VERSION=%%a
echo ✅ %PYTHON_VERSION%
echo.

REM 仮想環境チェック/作成
echo 🔧 仮想環境を確認中...
if not exist "venv" (
    echo 📦 仮想環境を作成中...
    python -m venv venv
    if errorlevel 1 (
        echo ❌ 仮想環境の作成に失敗しました
        pause
        exit /b 1
    )
)

call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ❌ 仮想環境の有効化に失敗しました
    pause
    exit /b 1
)
echo ✅ 仮想環境有効化完了
echo.

REM 依存関係チェック
echo 📦 依存関係を確認中...
python -c "import PySide6" > nul 2>&1
if errorlevel 1 (
    echo 📥 必要なパッケージをインストール中...
    pip install -q -r requirements-gui.txt
    if errorlevel 1 (
        echo ❌ インストールに失敗しました
        pause
        exit /b 1
    )
)
echo ✅ 依存関係確認完了
echo.

REM APIキー設定チェック
echo 🔐 設定を確認中...
python -c "from src.security.key_manager import SecureKeyManager; km = SecureKeyManager(); exit(0 if km.has_api_key('anthropic') else 1)" > nul 2>&1
if errorlevel 1 (
    echo ⚠️  APIキーが設定されていません
    echo 📝 初回起動時に設定ダイアログが表示されます
echo.
)

REM GUI起動
echo.
echo   🚀 GUIを起動中...
echo   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

python src\gui\main_window.py

REM 終了処理
echo.
echo   👋 アプリケーションを終了しました
echo.

REM 仮想環境無効化
call venv\Scripts\deactivate.bat > nul 2>&1

pause
