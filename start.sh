#!/bin/bash
# Start script for Dealer Portal Backend and Frontend

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

echo "========================================"
echo "Dealer Portal Application Launcher"
echo "========================================"

# Check if virtual environment exists
if [ ! -d "$PROJECT_ROOT/.venv" ]; then
    echo "Error: Virtual environment not found at $PROJECT_ROOT/.venv"
    echo "Create it with: python -m venv .venv"
    exit 1
fi

# Check if frontend node_modules exists
if [ ! -d "$PROJECT_ROOT/src/frontend/node_modules" ]; then
    echo "Error: Frontend dependencies not installed"
    echo "Run: cd src/frontend && npm install"
    exit 1
fi

# Stop any existing services first
fuser -k 8000/tcp 2>/dev/null
fuser -k 5173/tcp 2>/dev/null
sleep 1

# Load environment variables
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
    echo "Environment loaded from .env"
else
    echo "Warning: No .env file found — using defaults (simulated mode)"
fi

# Start backend
echo "Starting Backend API..."
cd "$PROJECT_ROOT/src/api"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT"
"$PROJECT_ROOT/.venv/bin/uvicorn" app.main:app --host 0.0.0.0 --port 8000 --reload > "$LOG_DIR/backend.log" 2>&1 &
echo "Backend started (PID: $!)"

sleep 3

# Start frontend
echo "Starting Frontend App..."
cd "$PROJECT_ROOT/src/frontend"
npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
echo "Frontend started (PID: $!)"

sleep 3

echo ""
echo "========================================"
echo "Services started!"
echo "========================================"
echo ""
echo "Backend:  http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo "Frontend: http://localhost:5173"
echo ""
echo "Mode: $(if [ "$SIMULATED_MODE" = "false" ]; then echo 'LIVE (Azure)'; else echo 'SIMULATED (Mock Data)'; fi)"
echo "Agent: $(if [ "$AGENT_SERVICE" = "foundry" ]; then echo 'Foundry Agent Service'; else echo 'Agent Framework'; fi)"
echo "Agentic Retrieval: ${AGENTIC_RETRIEVAL_ENABLED:-false}"
echo ""
echo "View logs:"
echo "  tail -f $LOG_DIR/backend.log"
echo "  tail -f $LOG_DIR/frontend.log"
echo ""
echo "Stop: ./stop.sh"
