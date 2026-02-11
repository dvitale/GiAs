#!/bin/bash

SERVERPORT=5005
_killport() { lsof -ti tcp:$1 | xargs kill -9; }; 

echo "=========================================="
echo "   GiAs-llm API Server Shutdown"
echo "=========================================="

SCRIPT_PATH="$(realpath "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
if [ "$(basename "$SCRIPT_DIR")" = "scripts" ]; then
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
    PROJECT_ROOT="$SCRIPT_DIR"
fi
LOG_DIR="$PROJECT_ROOT/runtime/logs"
PID_FILE="$LOG_DIR/api-server.pid"
echo "pid file: $PID_FILE"
if [ ! -f "$PID_FILE" ]; then
    echo "⚠️  Nessun spid server in esecuzione (file PID non trovato)"
    _killport 5005
    exit 0
fi


API_PID=$(cat "$PID_FILE")

if ps -p "$API_PID" > /dev/null 2>&1; then
    echo "🛑 Arresto server (PID: $API_PID)..."
    kill "$API_PID"

    sleep 2

    if ps -p "$API_PID" > /dev/null 2>&1; then
        echo "   ⚠️  Processo ancora attivo, forzo terminazione..."
        kill -9 "$API_PID"
        sleep 1
    fi

    if ps -p "$API_PID" > /dev/null 2>&1; then
        echo "   ❌ Impossibile terminare il processo"
        exit 1
    else
        echo "   ✅ Server arrestato con successo"
    fi
else
    echo "⚠️  Server non in esecuzione (PID $API_PID non trovato)"
fi

rm -f "$PID_FILE"

echo "=========================================="
echo "   Shutdown completato"
echo "=========================================="
