#!/bin/bash
#
# GChat - Build, Stop, Run & Verify
#

clear
cd "$(dirname "$0")"

PORT=8080
MAX_WAIT=10

echo "=========================================="
echo "   GChat - Build & Deploy"
echo "=========================================="
echo ""

set -x
./stop.sh
./build.sh && ./run.sh
set +x

# Verifica finale: server in ascolto sulla porta
echo ""
echo "🔍 Verifica server su porta $PORT..."

WAIT=0
while [ $WAIT -lt $MAX_WAIT ]; do
    if curl -s --max-time 2 "http://localhost:$PORT/gias/webchat/" > /dev/null 2>&1; then
        echo "✅ Server attivo e in ascolto su porta $PORT"
        echo ""
        echo "📋 Endpoints:"
        echo "   - UI:     http://localhost:$PORT/gias/webchat/"
        echo "   - Chat:   http://localhost:$PORT/gias/webchat/chat"
        echo "   - Health: http://localhost:$PORT/gias/webchat/health"
        echo ""
        exit 0
    fi
    sleep 1
    WAIT=$((WAIT + 1))
    echo "   Attendo... ($WAIT/$MAX_WAIT)"
done

echo "❌ Server non risponde su porta $PORT dopo $MAX_WAIT secondi"
echo "   Controlla i log: log/err.txt"
exit 1
