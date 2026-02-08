@echo off
REM ============================================================
REM LLM Smart Router - Auto-Launch Chain
REM ============================================================

echo.
echo ==================================================
echo   LLM Smart Router - Auto-Launch Chain
echo ==================================================
echo.

cd /d "%~dp0"

if exist venv\Scripts\activate.bat (
    echo   Activating virtual environment...
    call venv\Scripts\activate.bat
)

python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   [X] Python not found. Please check your PATH.
    pause
    exit /b 1
)

node --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   [!] Node.js not found. OpenClaw/Discord Bot stages will be skipped.
)

echo.
echo   Starting Auto-Launch Chain...
echo.
python -m launcher %*

echo.
echo   Press any key to exit...
pause >nul
