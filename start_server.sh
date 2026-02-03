#!/bin/bash
# Start LLM Smart Router API Server

cd "$(dirname "$0")"

echo "Starting LLM Smart Router API Server..."
echo ""
echo "API will be available at: http://localhost:8000"
echo "Documentation: http://localhost:8000/docs"
echo ""

python -m api.main "$@"
