#!/bin/bash

echo "==========================================="
echo "   Llama.cpp Server Startup"
echo "==========================================="

LLAMA_SERVER="/opt/llama.cpp/build/bin/llama-server"
MODEL_PATH="/opt/llama.cpp/models/Llama-3.2-3B-Instruct-Q6_K_L.gguf"
PORT=11435
PID_FILE="/tmp/llama-server.pid"

# Check if server already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "⚠️  Llama.cpp server già in esecuzione (PID: $OLD_PID)"
        echo "   Porta: $PORT"
        exit 1
    else
        rm -f "$PID_FILE"
    fi
fi

# Check binary exists
if [ ! -f "$LLAMA_SERVER" ]; then
    echo "❌ Errore: llama-server non trovato in $LLAMA_SERVER"
    exit 1
fi

# Check model exists
if [ ! -f "$MODEL_PATH" ]; then
    echo "❌ Errore: modello non trovato in $MODEL_PATH"
    exit 1
fi

echo ""
echo "🤖 Avvio llama.cpp server..."
echo "   📁 Modello: $(basename $MODEL_PATH)"
echo "   🔌 Porta: $PORT"
echo ""

# Start server in background
nohup "$LLAMA_SERVER" -m "$MODEL_PATH" --port "$PORT" > /tmp/llama-server.log 2>&1 &
SERVER_PID=$!

echo $SERVER_PID > "$PID_FILE"

# Wait for server to be ready
sleep 3

if ps -p "$SERVER_PID" > /dev/null 2>&1; then
    # Check if server responds
    for i in {1..10}; do
        if curl -sf http://localhost:$PORT/health > /dev/null 2>&1; then
            echo "✅ Llama.cpp server avviato (PID: $SERVER_PID)"
            echo ""
            echo "📋 Endpoints disponibili:"
            echo "   - Health:         http://localhost:$PORT/health"
            echo "   - Chat (OpenAI):  http://localhost:$PORT/v1/chat/completions"
            echo "   - Models:         http://localhost:$PORT/v1/models"
            echo ""
            echo "📝 Log file: /tmp/llama-server.log"
            echo "🛑 Per fermare: kill \$(cat $PID_FILE)"
            echo ""
            echo "==========================================="
            echo "   Server pronto per ricevere richieste"
            echo "==========================================="
            exit 0
        fi
        sleep 1
    done
    echo "⚠️  Server avviato ma non risponde su porta $PORT"
    echo "   Controlla il log: /tmp/llama-server.log"
else
    echo "❌ Errore nell'avvio del server"
    echo "   Controlla il log: /tmp/llama-server.log"
    rm -f "$PID_FILE"
    exit 1
fi
