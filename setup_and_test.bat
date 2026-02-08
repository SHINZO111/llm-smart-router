@echo off
echo ============================================
echo LLM Smart Router - Setup & Test
echo ============================================

cd /d "%~dp0"

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/update dependencies
echo Installing dependencies...
pip install -q -r requirements.txt

REM Run tests
echo.
echo Running tests...
python tests\test_suite.py

echo.
echo ============================================
echo Setup complete!
echo To run the application:
echo   run_gui.bat
echo ============================================
pause
