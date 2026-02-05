@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

REM ============================================================
REM LLM Smart Router - ワンクリック セットアップ
REM ダブルクリックするだけで全自動セットアップ完了
REM ============================================================

cd /d "%~dp0"

echo.
echo   ╔══════════════════════════════════════════════════════════════╗
echo   ║                                                              ║
echo   ║         LLM Smart Router - セットアップ                      ║
echo   ║                                                              ║
echo   ║     初回セットアップを自動で行います                          ║
echo   ║                                                              ║
echo   ╚══════════════════════════════════════════════════════════════╝
echo.

set "ERRORS=0"
set "WARNINGS=0"

REM ============================================================
REM ステップ 1: 前提チェック
REM ============================================================
echo   [1/6] 前提条件を確認中...
echo   ─────────────────────────────────────────────────
echo.

REM -- Python --
python --version > nul 2>&1
if errorlevel 1 (
    echo   X  Python が見つかりません
    echo      https://www.python.org/downloads/ からインストールしてください
    echo      インストール時に「Add Python to PATH」にチェックを入れてください
    echo.
    set /a ERRORS+=1
    goto :setup_failed
) else (
    for /f "tokens=*" %%a in ('python --version 2^>^&1') do echo   OK %%a
)

REM -- pip --
python -m pip --version > nul 2>&1
if errorlevel 1 (
    echo   X  pip が見つかりません
    set /a ERRORS+=1
) else (
    echo   OK pip 利用可能
)

REM -- Node.js --
node --version > nul 2>&1
if errorlevel 1 (
    echo   !  Node.js が見つかりません（オプション）
    echo      https://nodejs.org/ からインストールすると全機能が使えます
    echo      （Router / Discord Bot に必要。GUI のみなら不要）
    set /a WARNINGS+=1
    set "HAS_NODE=0"
) else (
    for /f "tokens=*" %%a in ('node --version 2^>^&1') do echo   OK Node.js %%a
    set "HAS_NODE=1"
)
echo.

REM ============================================================
REM ステップ 2: 仮想環境 + 依存関係インストール
REM ============================================================
echo   [2/6] 依存関係をインストール中...
echo   ─────────────────────────────────────────────────
echo.

REM -- 仮想環境 --
if not exist "venv" (
    echo   仮想環境を作成中...
    python -m venv venv
    if errorlevel 1 (
        echo   X  仮想環境の作成に失敗しました
        set /a ERRORS+=1
        goto :setup_failed
    )
    echo   OK 仮想環境を作成しました
) else (
    echo   OK 仮想環境は既に存在します
)

call venv\Scripts\activate.bat
if errorlevel 1 (
    echo   X  仮想環境の有効化に失敗しました
    set /a ERRORS+=1
    goto :setup_failed
)

REM -- Python パッケージ (コア) --
echo   Python パッケージをインストール中（コア）...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo   X  コアパッケージのインストールに失敗しました
    set /a ERRORS+=1
) else (
    echo   OK コアパッケージ インストール完了
)

REM -- Python パッケージ (GUI) --
echo   Python パッケージをインストール中（GUI）...
pip install -q -r requirements-gui.txt 2>nul
if errorlevel 1 (
    echo   !  GUIパッケージのインストールに失敗しました（GUIは使えませんがAPIは動作します）
    set /a WARNINGS+=1
) else (
    echo   OK GUIパッケージ インストール完了
)

REM -- Node.js パッケージ --
if "%HAS_NODE%"=="1" (
    if exist "package.json" (
        echo   Node.js パッケージをインストール中...
        npm install --silent 2>nul
        if errorlevel 1 (
            echo   !  Node.js パッケージのインストールに失敗しました
            set /a WARNINGS+=1
        ) else (
            echo   OK Node.js パッケージ インストール完了
        )
    )
)
echo.

REM ============================================================
REM ステップ 3: .env ファイル設定
REM ============================================================
echo   [3/6] API キーを設定中...
echo   ─────────────────────────────────────────────────
echo.

if exist ".env" (
    echo   OK .env ファイルは既に存在します（スキップ）
) else (
    if exist ".env.example" (
        copy ".env.example" ".env" > nul
        echo   OK .env ファイルを作成しました
    ) else (
        echo # LLM Smart Router 環境設定> ".env"
        echo:>> ".env"
        echo   OK .env ファイルを新規作成しました
    )

    echo:
    echo   APIキーを設定します。後で設定する場合はそのまま Enter を押してください。
    echo   （キーは .env ファイルに保存されます）
    echo   注意: 入力は画面に表示されます。周囲にご注意ください。
    echo:

    REM -- Anthropic --
    set "KEY_INPUT="
    set /p "KEY_INPUT=   Anthropic API Key (sk-ant-...): "
    if defined KEY_INPUT (
        echo ANTHROPIC_API_KEY=!KEY_INPUT!>> ".env"
        echo   OK Anthropic API Key を保存しました
    ) else (
        echo   -- スキップ
    )

    REM -- OpenAI --
    set "KEY_INPUT="
    set /p "KEY_INPUT=   OpenAI API Key (sk-...): "
    if defined KEY_INPUT (
        echo OPENAI_API_KEY=!KEY_INPUT!>> ".env"
        echo   OK OpenAI API Key を保存しました
    ) else (
        echo   -- スキップ
    )

    REM -- Google --
    set "KEY_INPUT="
    set /p "KEY_INPUT=   Google API Key: "
    if defined KEY_INPUT (
        echo GOOGLE_API_KEY=!KEY_INPUT!>> ".env"
        echo   OK Google API Key を保存しました
    ) else (
        echo   -- スキップ
    )

    REM -- OpenRouter --
    set "KEY_INPUT="
    set /p "KEY_INPUT=   OpenRouter API Key: "
    if defined KEY_INPUT (
        echo OPENROUTER_API_KEY=!KEY_INPUT!>> ".env"
        echo   OK OpenRouter API Key を保存しました
    ) else (
        echo   -- スキップ
    )
)
echo.

REM ============================================================
REM ステップ 4: ディレクトリ作成
REM ============================================================
echo   [4/6] ディレクトリを準備中...
echo   ─────────────────────────────────────────────────
echo.

if not exist "data" mkdir data
if not exist "logs" mkdir logs
if not exist "cache" mkdir cache
if not exist "queue" mkdir queue

echo   OK data/ logs/ cache/ queue/ を確認しました
echo.

REM ============================================================
REM ステップ 5: 初回モデルスキャン
REM ============================================================
echo   [5/6] LLM ランタイムをスキャン中...
echo   ─────────────────────────────────────────────────
echo.

REM .env があれば許可リストの環境変数のみ読み込む
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        set "KEY=%%A"
        set "VAL=%%B"
        REM 空行・コメント行をスキップ
        if defined KEY (
            if not "!KEY:~0,1!"=="#" (
                REM クオート除去（前後の " を削除）
                set "VAL=!VAL:"=!"
                REM 許可リストのキーのみ設定
                if "!KEY!"=="ANTHROPIC_API_KEY" set "ANTHROPIC_API_KEY=!VAL!"
                if "!KEY!"=="OPENAI_API_KEY" set "OPENAI_API_KEY=!VAL!"
                if "!KEY!"=="GOOGLE_API_KEY" set "GOOGLE_API_KEY=!VAL!"
                if "!KEY!"=="OPENROUTER_API_KEY" set "OPENROUTER_API_KEY=!VAL!"
                if "!KEY!"=="LM_STUDIO_ENDPOINT" set "LM_STUDIO_ENDPOINT=!VAL!"
                if "!KEY!"=="LOG_LEVEL" set "LOG_LEVEL=!VAL!"
                if "!KEY!"=="EXCHANGE_RATE" set "EXCHANGE_RATE=!VAL!"
            )
        )
    )
)

cd /d "%~dp0\src"
python -m scanner scan --timeout 3.0 2>nul
cd /d "%~dp0"

echo.

REM ============================================================
REM ステップ 6: 動作検証
REM ============================================================
echo   [6/6] インストールを検証中...
echo   ─────────────────────────────────────────────────
echo.

cd /d "%~dp0\src"
python -m healthcheck 2>nul
if errorlevel 1 (
    echo   !  一部のチェックが失敗しました（上の結果を確認してください）
)
cd /d "%~dp0"

echo.

REM ============================================================
REM 完了
REM ============================================================
echo   ╔══════════════════════════════════════════════════════════════╗
echo   ║                                                              ║
echo   ║         セットアップ完了！                                   ║
echo   ║                                                              ║
echo   ╚══════════════════════════════════════════════════════════════╝
echo.
echo   次のステップ:
echo.
echo     run_gui.bat        ... GUI アプリを起動
echo     auto_launch.bat    ... フルチェーン起動（LM Studio + Router + Discord）
echo     start_server.bat   ... API サーバーのみ起動
echo.
echo   APIキーを後で変更するには .env ファイルを編集してください。
echo   セットアップの再検証は  python -m healthcheck  で実行できます。
echo.

if %ERRORS% gtr 0 (
    echo   [!] %ERRORS% 個のエラーがあります。上のメッセージを確認してください。
)
if %WARNINGS% gtr 0 (
    echo   [i] %WARNINGS% 個の警告があります。
)

goto :done

:setup_failed
echo.
echo   X  セットアップに失敗しました。上のエラーメッセージを確認してください。
echo.

:done
call venv\Scripts\deactivate.bat > nul 2>&1
endlocal
pause
