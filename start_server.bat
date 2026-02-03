@echo off
REM Start LLM Smart Router API Server
cd /d "%~dp0"

echo Starting LLM Smart Router API Server...
echo.
echo API will be available at: http://localhost:8000
echo Documentation: http://localhost:8000/docs
echo.

python -m api.main %*
