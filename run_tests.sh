#!/bin/bash
set -e

echo "Running LLM Smart Router Tests..."
echo ""

# Check if pytest is installed
if ! python -c "import pytest" 2>/dev/null; then
    echo "Installing pytest..."
    pip install pytest pytest-asyncio httpx
fi

# Run all tests
echo "Running API tests..."
python -m pytest src/tests/test_api.py -v

echo ""
echo "Running CLI tests..."
python -m pytest src/tests/test_cli.py -v

echo ""
echo "Running integration tests..."
python -m pytest src/tests/test_integration.py -v

echo ""
echo "All tests completed!"
