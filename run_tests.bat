@echo off
echo Running LLM Smart Router Tests...
echo.

REM Check if pytest is installed
python -c "import pytest" 2>nul
if errorlevel 1 (
    echo Installing pytest...
    pip install pytest pytest-asyncio httpx
)

REM Run all tests
echo Running API tests...
python -m pytest tests/test_api.py -v

echo.
echo Running CLI tests...
python -m pytest tests/test_cli.py -v

echo.
echo Running integration tests...
python -m pytest tests/test_integration.py -v

echo.
echo All tests completed!
pause
