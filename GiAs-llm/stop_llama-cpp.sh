#!/bin/bash

echo "==========================================="
echo "   Llama.cpp Server Shutdown"
echo "==========================================="

PID_FILE="/tmp/llama-server.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "❌ PID file non trovato: $PID_FILE"
    echo "   Il server non sembra essere in esecuzione"
    exit 1
fi

SERVER_PID=$(cat "$PID_FILE")

if ps -p "$SERVER_PID" > /dev/null 2>&1; then
    echo "🛑 Arresto llama.cpp server (PID: $SERVER_PID)..."
    kill "$SERVER_PID"

    # Attendi terminazione
    for i in {1..10}; do
        if ! ps -p "$SERVER_PID" > /dev/null 2>&1; then
            echo "✅ Server arrestato con successo"
            rm -f "$PID_FILE"
            exit 0
        fi
        sleep 1
    done

    # Force kill se non termina
    echo "⚠️  Server non risponde, forzo terminazione..."
    kill -9 "$SERVER_PID" 2>/dev/null
    rm -f "$PID_FILE"
    echo "✅ Server arrestato forzatamente"
else
    echo "⚠️  Processo non trovato (PID: $SERVER_PID)"
    echo "   Rimuovo PID file obsoleto"
    rm -f "$PID_FILE"
fi

echo ""
echo "==========================================="
echo "   Server terminato"
echo "==========================================="
