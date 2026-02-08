@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM LLM Smart Router - One-Click Setup
REM ============================================================

cd /d "%~dp0"

echo.
echo   ======================================================
echo     LLM Smart Router - Setup
echo     Automated first-time setup
echo   ======================================================
echo.

set "ERRORS=0"
set "WARNINGS=0"

REM ============================================================
REM Step 1: Prerequisites
REM ============================================================
echo   [1/6] Checking prerequisites...
echo   ----------------------------------------------
echo.

REM -- Python --
python --version > nul 2>&1
if errorlevel 1 (
    echo   X  Python not found.
    echo      Please install from https://www.python.org/downloads/
    echo      Make sure to check "Add Python to PATH" during install.
    echo.
    set /a ERRORS+=1
    goto :setup_failed
) else (
    for /f "tokens=*" %%a in ('python --version 2^>^&1') do echo   OK %%a
)

REM -- pip --
python -m pip --version > nul 2>&1
if errorlevel 1 (
    echo   X  pip not found.
    set /a ERRORS+=1
) else (
    echo   OK pip available
)

REM -- Node.js --
node --version > nul 2>&1
if errorlevel 1 (
    echo   !  Node.js not found (optional)
    echo      Install from https://nodejs.org/ for full functionality.
    echo      (Required for Router / Discord Bot. Not needed for GUI only.)
    set /a WARNINGS+=1
    set "HAS_NODE=0"
) else (
    for /f "tokens=*" %%a in ('node --version 2^>^&1') do echo   OK Node.js %%a
    set "HAS_NODE=1"
)
echo.

REM ============================================================
REM Step 2: Virtual environment + dependencies
REM ============================================================
echo   [2/6] Installing dependencies...
echo   ----------------------------------------------
echo.

REM -- Virtual environment --
if not exist "venv" (
    echo   Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo   X  Failed to create virtual environment.
        set /a ERRORS+=1
        goto :setup_failed
    )
    echo   OK Virtual environment created.
) else (
    echo   OK Virtual environment already exists.
)

call venv\Scripts\activate.bat
if errorlevel 1 (
    echo   X  Failed to activate virtual environment.
    set /a ERRORS+=1
    goto :setup_failed
)

REM -- Python packages (core) --
echo   Installing Python packages (core)...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo   X  Core package installation failed.
    set /a ERRORS+=1
) else (
    echo   OK Core packages installed.
)

REM -- Python packages (GUI) --
echo   Installing Python packages (GUI)...
pip install -q -r requirements-gui.txt 2>nul
if errorlevel 1 (
    echo   !  GUI package installation failed. (GUI unavailable, but API will work.)
    set /a WARNINGS+=1
) else (
    echo   OK GUI packages installed.
)

REM -- Node.js packages --
if "%HAS_NODE%"=="1" (
    if exist "package.json" (
        echo   Installing Node.js packages...
        npm install --silent 2>nul
        if errorlevel 1 (
            echo   !  Node.js package installation failed.
            set /a WARNINGS+=1
        ) else (
            echo   OK Node.js packages installed.
        )
    )
)
echo.

REM ============================================================
REM Step 3: .env configuration
REM ============================================================
echo   [3/6] Configuring API keys...
echo   ----------------------------------------------
echo.

if exist ".env" (
    echo   OK .env file already exists (skipped).
) else (
    if exist ".env.example" (
        copy ".env.example" ".env" > nul
        echo   OK .env file created from template.
    ) else (
        echo # LLM Smart Router Configuration> ".env"
        echo:>> ".env"
        echo   OK .env file created.
    )

    echo:
    echo   Enter your API keys below. Press Enter to skip any key.
    echo   (Keys will be saved to the .env file.)
    echo   NOTE: Input will be visible on screen.
    echo:

    REM -- Anthropic --
    set "KEY_INPUT="
    set /p "KEY_INPUT=   Anthropic API Key (sk-ant-...): "
    if defined KEY_INPUT (
        echo ANTHROPIC_API_KEY=!KEY_INPUT!>> ".env"
        echo   OK Anthropic API Key saved.
    ) else (
        echo   -- Skipped
    )

    REM -- OpenAI --
    set "KEY_INPUT="
    set /p "KEY_INPUT=   OpenAI API Key (sk-...): "
    if defined KEY_INPUT (
        echo OPENAI_API_KEY=!KEY_INPUT!>> ".env"
        echo   OK OpenAI API Key saved.
    ) else (
        echo   -- Skipped
    )

    REM -- Google --
    set "KEY_INPUT="
    set /p "KEY_INPUT=   Google API Key: "
    if defined KEY_INPUT (
        echo GOOGLE_API_KEY=!KEY_INPUT!>> ".env"
        echo   OK Google API Key saved.
    ) else (
        echo   -- Skipped
    )

    REM -- OpenRouter --
    set "KEY_INPUT="
    set /p "KEY_INPUT=   OpenRouter API Key: "
    if defined KEY_INPUT (
        echo OPENROUTER_API_KEY=!KEY_INPUT!>> ".env"
        echo   OK OpenRouter API Key saved.
    ) else (
        echo   -- Skipped
    )
)
echo.

REM ============================================================
REM Step 4: Create directories
REM ============================================================
echo   [4/6] Preparing directories...
echo   ----------------------------------------------
echo.

if not exist "data" mkdir data
if not exist "logs" mkdir logs
if not exist "cache" mkdir cache
if not exist "queue" mkdir queue

echo   OK data/ logs/ cache/ queue/ verified.
echo.

REM ============================================================
REM Step 5: Initial model scan
REM ============================================================
echo   [5/6] Scanning LLM runtimes...
echo   ----------------------------------------------
echo.

REM Load allowed env vars from .env
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        set "KEY=%%A"
        set "VAL=%%B"
        if defined KEY (
            if not "!KEY:~0,1!"=="#" (
                set "VAL=!VAL:"=!"
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
REM Step 6: Health check
REM ============================================================
echo   [6/6] Verifying installation...
echo   ----------------------------------------------
echo.

cd /d "%~dp0\src"
python -m healthcheck 2>nul
if errorlevel 1 (
    echo   !  Some checks failed. See results above.
)
cd /d "%~dp0"

echo.

REM ============================================================
REM Done
REM ============================================================
echo   ======================================================
echo     Setup complete!
echo   ======================================================
echo.
echo   Next steps:
echo.
echo     run_gui.bat        ... Launch GUI application
echo     auto_launch.bat    ... Full chain (LM Studio + Router + Discord)
echo     start_server.bat   ... API server only
echo.
echo   To change API keys later, edit the .env file.
echo   To re-verify setup, run:  python -m healthcheck
echo.

if %ERRORS% gtr 0 (
    echo   [!] %ERRORS% error(s) found. Check messages above.
)
if %WARNINGS% gtr 0 (
    echo   [i] %WARNINGS% warning(s).
)

goto :done

:setup_failed
echo.
echo   X  Setup failed. Check error messages above.
echo.

:done
call venv\Scripts\deactivate.bat > nul 2>&1
endlocal
pause
