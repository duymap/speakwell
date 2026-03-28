#!/usr/bin/env bash
set -e

# SpeakWell — Start all services in order
# Usage: ./start.sh
# Stop:  Ctrl+C (kills all background processes)
#
# Creates isolated venvs for inference and server, installs deps,
# then starts all four services.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check OPENAI_API_KEY
if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${RED}Error: OPENAI_API_KEY is not set${NC}"
    echo "  export OPENAI_API_KEY=sk-..."
    exit 1
fi

# Cleanup on exit — kill all child processes
cleanup() {
    echo -e "\n${YELLOW}Shutting down all services...${NC}"
    kill 0 2>/dev/null
    wait 2>/dev/null
    echo -e "${GREEN}All services stopped.${NC}"
}
trap cleanup EXIT INT TERM

# Log directory
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

echo -e "${GREEN}=== SpeakWell Startup ===${NC}"
echo ""

# ---------------------------------------------------------------------------
# Setup venvs and install dependencies
# ---------------------------------------------------------------------------

# Inference venv (shared by STT and TTS servers)
INFERENCE_VENV="$SCRIPT_DIR/inference/.venv"
if [ ! -d "$INFERENCE_VENV" ]; then
    echo -e "${YELLOW}[setup] Creating inference venv...${NC}"
    python3 -m venv "$INFERENCE_VENV"
fi
echo -e "${YELLOW}[setup] Installing inference dependencies...${NC}"
"$INFERENCE_VENV/bin/pip" install --quiet --upgrade pip
"$INFERENCE_VENV/bin/pip" install --quiet -r "$SCRIPT_DIR/inference/requirements.txt"
echo -e "  ${GREEN}Inference venv ready${NC}"

# Server (pipeline) venv
SERVER_VENV="$SCRIPT_DIR/server/.venv"
if [ ! -d "$SERVER_VENV" ]; then
    echo -e "${YELLOW}[setup] Creating server venv...${NC}"
    python3 -m venv "$SERVER_VENV"
fi
echo -e "${YELLOW}[setup] Installing server dependencies...${NC}"
"$SERVER_VENV/bin/pip" install --quiet --upgrade pip
"$SERVER_VENV/bin/pip" install --quiet -r "$SCRIPT_DIR/server/requirements.txt"
echo -e "  ${GREEN}Server venv ready${NC}"

# Frontend node_modules
echo -e "${YELLOW}[setup] Installing frontend dependencies...${NC}"
cd "$SCRIPT_DIR/client"
npm install --silent
echo -e "  ${GREEN}Frontend dependencies ready${NC}"

echo ""

# ---------------------------------------------------------------------------
# Start services
# ---------------------------------------------------------------------------

# 1. STT Server
echo -e "${YELLOW}[1/4] Starting STT server (port 8001)...${NC}"
cd "$SCRIPT_DIR/inference"
"$INFERENCE_VENV/bin/python" stt_server.py > "$LOG_DIR/stt.log" 2>&1 &
STT_PID=$!

# 2. TTS Server
echo -e "${YELLOW}[2/4] Starting TTS server (port 8002)...${NC}"
"$INFERENCE_VENV/bin/python" tts_server.py > "$LOG_DIR/tts.log" 2>&1 &
TTS_PID=$!

# Wait for inference servers to load models
echo -e "${YELLOW}Waiting for inference servers to load models...${NC}"
for port in 8001 8002; do
    name="STT"; [ "$port" = "8002" ] && name="TTS"
    for i in $(seq 1 180); do
        if curl -sf "http://localhost:$port/health" > /dev/null 2>&1; then
            echo -e "  ${GREEN}$name server ready${NC}"
            break
        fi
        if [ "$i" = "180" ]; then
            echo -e "  ${RED}$name server failed to start (timeout 180s). Check $LOG_DIR/${name,,}.log${NC}"
            exit 1
        fi
        sleep 1
    done
done

# 3. Pipeline Server
echo -e "${YELLOW}[3/4] Starting pipeline server (port 7860)...${NC}"
cd "$SCRIPT_DIR/server"
"$SERVER_VENV/bin/uvicorn" bot:app --host 0.0.0.0 --port 7860 > "$LOG_DIR/pipeline.log" 2>&1 &
PIPELINE_PID=$!

sleep 2
if curl -sf "http://localhost:7860/api/health" > /dev/null 2>&1; then
    echo -e "  ${GREEN}Pipeline server ready${NC}"
else
    echo -e "  ${YELLOW}Pipeline server starting (check $LOG_DIR/pipeline.log)${NC}"
fi

# 4. Frontend
echo -e "${YELLOW}[4/4] Starting frontend dev server (port 5173)...${NC}"
cd "$SCRIPT_DIR/client"
npx vite > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!

sleep 3

echo ""
echo -e "${GREEN}=== All services started ===${NC}"
echo ""
echo "  STT server:       http://localhost:8001  (PID: $STT_PID)"
echo "  TTS server:       http://localhost:8002  (PID: $TTS_PID)"
echo "  Pipeline server:  http://localhost:7860  (PID: $PIPELINE_PID)"
echo "  Frontend:         http://localhost:5173  (PID: $FRONTEND_PID)"
echo ""
echo "  Logs: $LOG_DIR/"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"

# Keep script alive
wait
