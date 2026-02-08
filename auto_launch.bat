@echo off
chcp 65001 > nul
REM ============================================================
REM LLM Smart Router - Auto-Launch Chain
REM ============================================================

echo.
echo ==================================================
echo   LLM Smart Router - Auto-Launch Chain
echo ==================================================
echo.

REM プロジェクトディレクトリに移動
cd /d "%~dp0"

REM Python仮想環境があれば有効化
if exist venv\Scripts\activate.bat (
    echo   仮想環境を有効化中...
    call venv\Scripts\activate.bat
)

REM Pythonが利用可能か確認
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   [X] Python が見つかりません。PATH を確認してください。
    pause
    exit /b 1
)

REM Node.jsが利用可能か確認（OpenClaw/Discord Botステージで必要）
node --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   [!] Node.js が見つかりません。OpenClaw/Discord Bot ステージはスキップされます。
)

REM Python起動チェーン実行
echo.
echo   Auto-Launch Chain を開始します...
echo.
python -m launcher %*

echo.
echo   終了するにはキーを押してください...
pause >nul
