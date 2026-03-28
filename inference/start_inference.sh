#!/usr/bin/env bash
set -e

# SpeakWell — Start inference servers (STT + TTS) only
# Usage: ./start_inference.sh
# Stop:  Ctrl+C (kills all background processes)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down inference servers...${NC}"
    kill 0 2>/dev/null
    wait 2>/dev/null
    echo -e "${GREEN}All inference servers stopped.${NC}"
}
trap cleanup EXIT INT TERM

# Log directory
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

echo -e "${GREEN}=== SpeakWell Inference Startup ===${NC}"
echo ""

# Setup venv
VENV="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV" ]; then
    echo -e "${YELLOW}[setup] Creating inference venv...${NC}"
    python3 -m venv "$VENV"
fi
echo -e "${YELLOW}[setup] Installing inference dependencies...${NC}"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$SCRIPT_DIR/requirements.txt"
echo -e "  ${GREEN}Inference venv ready${NC}"
echo ""

# 1. STT Server
echo -e "${YELLOW}[1/2] Starting STT server (port 8001)...${NC}"
"$VENV/bin/python" "$SCRIPT_DIR/stt_server.py" > "$LOG_DIR/stt.log" 2>&1 &
STT_PID=$!

# 2. TTS Server
echo -e "${YELLOW}[2/2] Starting TTS server (port 8002)...${NC}"
"$VENV/bin/python" "$SCRIPT_DIR/tts_server.py" > "$LOG_DIR/tts.log" 2>&1 &
TTS_PID=$!

# Wait for servers to be ready
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

echo ""
echo -e "${GREEN}=== Inference servers started ===${NC}"
echo ""
echo "  STT server:  http://localhost:8001  (PID: $STT_PID)"
echo "  TTS server:  http://localhost:8002  (PID: $TTS_PID)"
echo ""
echo "  Logs: $LOG_DIR/"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all servers${NC}"

# Keep script alive
wait
