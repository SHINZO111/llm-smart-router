@echo off
REM =====================================================
REM LLM Smart Router - GUI Launcher
REM =====================================================

echo.
echo   ======================================================
echo     LLM Smart Router - GUI
echo   ======================================================
echo.

set "ROUTER_DIR=%~dp0"
cd /d "%ROUTER_DIR%"

echo   Checking Python...
python --version > nul 2>&1
if errorlevel 1 (
    echo   [X] Python not found.
    echo       Please install from https://python.org
    pause
    exit /b 1
)

for /f "tokens=*" %%a in ('python --version 2^>^&1') do set PYTHON_VERSION=%%a
echo   [OK] %PYTHON_VERSION%
echo.

echo   Checking virtual environment...
if not exist "venv" (
    echo   Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo   [X] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

call venv\Scripts\activate.bat
if errorlevel 1 (
    echo   [X] Failed to activate virtual environment.
    pause
    exit /b 1
)
echo   [OK] Virtual environment activated.
echo.

echo   Checking dependencies...
python -c "import PySide6" > nul 2>&1
if errorlevel 1 (
    echo   Installing required packages...
    pip install -q -r requirements-gui.txt
    if errorlevel 1 (
        echo   [X] Installation failed.
        pause
        exit /b 1
    )
)
echo   [OK] Dependencies ready.
echo.

echo   Checking configuration...
python -c "from src.security.key_manager import SecureKeyManager; km = SecureKeyManager(); exit(0 if km.has_api_key('anthropic') else 1)" > nul 2>&1
if errorlevel 1 (
    echo   [!] No API keys configured.
    echo       A settings dialog will appear on first launch.
    echo.
)

echo.
echo   Launching GUI...
echo   --------------------------------------------------------------
echo.

python src\gui\main_window.py

echo.
echo   Application closed.
echo.

call venv\Scripts\deactivate.bat > nul 2>&1

pause
