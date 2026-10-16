#!/usr/bin/env bash
set -e

# AI Tech Consultant - One-Command Startup Script (Bash)
# Starts all three connected services and their web interfaces

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
STREAMLIT_BIN="$SCRIPT_DIR/.venv/bin/streamlit"

# Fallback if virtualenv is named differently
if [ ! -f "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
    STREAMLIT_BIN="streamlit"
fi

echo "========================================================"
echo "  AI Tech Consultant - Starting 3 Connected Systems"
echo "========================================================"
echo "1. Task 1 (Knowledge Brain API)    : http://localhost:8001"
echo "2. Task 1 (Knowledge Brain UI)     : http://localhost:8501"
echo "3. Task 2 (Inbox Agent Web App)    : http://localhost:3000"
echo "4. Task 3 (Meeting-to-Scope API)   : http://localhost:8002"
echo "5. Task 3 (Meeting-to-Scope UI)    : http://localhost:8502"
echo "========================================================"

# Launch background processes
(cd "$SCRIPT_DIR/task1-knowledge-brain" && "$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port 8001) &
PID_T1_API=$!

(cd "$SCRIPT_DIR/task1-knowledge-brain" && "$STREAMLIT_BIN" run streamlit_app.py --server.port 8501 --server.headless true) &
PID_T1_UI=$!

(cd "$SCRIPT_DIR/task3-meeting-to-scope" && "$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port 8002) &
PID_T3_API=$!

(cd "$SCRIPT_DIR/task3-meeting-to-scope" && "$STREAMLIT_BIN" run streamlit_app.py --server.port 8502 --server.headless true) &
PID_T3_UI=$!

(cd "$SCRIPT_DIR/task2-inbox-agent" && npm run dev -- -p 3000) &
PID_T2_WEB=$!

trap 'echo "Stopping services..."; kill $PID_T1_API $PID_T1_UI $PID_T3_API $PID_T3_UI $PID_T2_WEB 2>/dev/null' SIGINT SIGTERM EXIT

wait
