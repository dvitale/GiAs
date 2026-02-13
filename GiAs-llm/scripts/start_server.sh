#!/bin/bash

echo "=========================================="
echo "   GiAs-llm API Server Startup"
echo "=========================================="

SCRIPT_PATH="$(realpath "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
if [ "$(basename "$SCRIPT_DIR")" = "scripts" ]; then
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
    PROJECT_ROOT="$SCRIPT_DIR"
fi
cd "$PROJECT_ROOT"

# Activate Python virtual environment
if [ -f "/opt/lang-env/bin/activate" ]; then
    source /opt/lang-env/bin/activate
fi

LOG_DIR="$PROJECT_ROOT/runtime/logs"
mkdir -p "$LOG_DIR"

API_LOG="$LOG_DIR/api-server.log"
PID_FILE="$LOG_DIR/api-server.pid"

if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "⚠️  Server già in esecuzione (PID: $OLD_PID)"
        echo "   Usa ./stop_server.sh per fermarlo"
        exit 1
    else
        rm -f "$PID_FILE"
    fi
fi

echo ""
echo "📊 Verifica dataset..."
if [ -d "$PROJECT_ROOT/data/dataset.10" ]; then
    NUM_FILES=$(ls -1 "$PROJECT_ROOT/data/dataset.10"/*.csv 2>/dev/null | wc -l)
    echo "   ✅ Dataset trovato: $NUM_FILES file CSV"
else
    echo "   ⚠️  Directory dataset.10 non trovata"
fi

echo ""
echo "🤖 Verifica backend LLM..."

# Configurazione backend (default: ollama)
export GIAS_LLM_BACKEND="${GIAS_LLM_BACKEND:-ollama}"
echo "   📌 Backend LLM configurato: $GIAS_LLM_BACKEND"

# Configurazione Ollama host (env var > config.json > default localhost)
if [ -z "$OLLAMA_HOST" ]; then
    CONFIG_FILE="$PROJECT_ROOT/configs/config.json"
    if [ -f "$CONFIG_FILE" ]; then
        OLLAMA_HOST=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE')).get('llm_backend', {}).get('ollama', {}).get('host', 'localhost'))" 2>/dev/null)
        OLLAMA_HOST="${OLLAMA_HOST:-localhost}"
    else
        OLLAMA_HOST="localhost"
    fi
fi
export OLLAMA_HOST
echo "   📌 Ollama host: $OLLAMA_HOST"

# Funzione per selezione interattiva del modello
select_model_interactive() {
    local TIMEOUT=10
    echo ""
    echo "════════════════════════════════════════"
    echo "   Seleziona il modello LLM da usare"
    echo "════════════════════════════════════════"
    echo ""
    echo "1) llama3.2:3b       (default, veloce, 3GB RAM)"
    echo "2) falcon-gias:latest (personalizzato)"
    echo "3) velvet            (Almawave/Velvet:latest)"
    echo "4) mistral-nemo      (mistral-nemo:latest)"
    echo "5) ministral-3:3b    (compatto, efficiente)"
    echo ""
    echo "⏱️  Timeout: ${TIMEOUT}s (default: llama3.2)"
    echo ""

    choice=""
    if read -t $TIMEOUT -p "Scelta [1-5, default=1]: " choice; then
        : # Input ricevuto
    else
        echo ""
        echo "   ⏱️  Timeout scaduto, uso modello default"
    fi

    case "$choice" in
        2) export GIAS_LLM_MODEL="falcon" ;;
        3) export GIAS_LLM_MODEL="velvet" ;;
        4) export GIAS_LLM_MODEL="mistral-nemo" ;;
        5) export GIAS_LLM_MODEL="ministral" ;;
        *) export GIAS_LLM_MODEL="llama3.2" ;;
    esac

    echo ""
    echo "   ✅ Modello selezionato: $GIAS_LLM_MODEL"
    echo ""
}

if [ "$GIAS_LLM_BACKEND" = "llamacpp" ]; then
    # Llama.cpp backend
    LLAMACPP_PORT=11435
    LLAMACPP_HOST="http://localhost:$LLAMACPP_PORT"

    echo "   🔌 Verifica llama.cpp su porta $LLAMACPP_PORT..."

    if curl -sf "$LLAMACPP_HOST/health" > /dev/null 2>&1; then
        echo "   ✅ Llama.cpp server disponibile"

        # Verifica modello caricato
        MODEL_INFO=$(curl -s "$LLAMACPP_HOST/v1/models" | python3 -c "import sys,json; data=json.load(sys.stdin); print(data['data'][0]['id'] if data.get('data') else 'Unknown')" 2>/dev/null)
        if [ -n "$MODEL_INFO" ]; then
            echo "   🤖 Modello caricato: $MODEL_INFO"
        fi
    else
        echo "   ⚠️  Llama.cpp server non disponibile su $LLAMACPP_HOST"
        echo "   💡 Avvia il server con: ./start_llama-cpp.sh"
        echo "   ⏸️  Continuo comunque l'avvio (fallback su stub mode)"
    fi

else
    # Ollama backend (legacy)
    # Selezione interattiva se GIAS_LLM_MODEL non è impostato
    if [ -z "$GIAS_LLM_MODEL" ]; then
        select_model_interactive
    fi

    export GIAS_LLM_MODEL="${GIAS_LLM_MODEL:-llama3.2}"
    GIAS_MODEL="$GIAS_LLM_MODEL"
    echo "   📌 Modello Ollama: $GIAS_MODEL"

    # Costruisci URL Ollama completo
    if [[ "$OLLAMA_HOST" == http* ]]; then
        OLLAMA_URL="$OLLAMA_HOST"
    else
        OLLAMA_URL="http://${OLLAMA_HOST}:11434"
    fi
    echo "   🔌 Ollama URL: $OLLAMA_URL"

    if [ "$GIAS_MODEL" = "velvet" ]; then
        OLLAMA_MODEL="Almawave/Velvet:latest"
    elif [ "$GIAS_MODEL" = "mistral-nemo" ]; then
        OLLAMA_MODEL="mistral-nemo:latest"
    elif [ "$GIAS_MODEL" = "ministral" ]; then
        OLLAMA_MODEL="ministral-3:3b"
    elif [ "$GIAS_MODEL" = "llama3.1" ]; then
        OLLAMA_MODEL="llama3.1:8b"
    elif [ "$GIAS_MODEL" = "llama3.2" ]; then
        OLLAMA_MODEL="llama3.2:3b"
    elif [ "$GIAS_MODEL" = "falcon" ] || [ "$GIAS_MODEL" = "falcon-gias" ]; then
        OLLAMA_MODEL="falcon-gias:latest"
    else
        OLLAMA_MODEL="llama3.2:3b"
    fi

    echo "   🔧 Modello Ollama: $OLLAMA_MODEL"
    export OLLAMA_KEEP_ALIVE=-1

    # Verifica esistenza modello su Ollama
    echo "   🔍 Verifica disponibilità modello su $OLLAMA_URL..."
    AVAILABLE_MODELS=$(curl -s $OLLAMA_URL/api/tags 2>/dev/null | python3 -c "import sys,json; data=json.load(sys.stdin); print(' '.join([m['name'] for m in data.get('models',[])]))" 2>/dev/null)

    if [ -n "$AVAILABLE_MODELS" ]; then
        echo "   📋 Modelli disponibili su Ollama: $AVAILABLE_MODELS"

        # Verifica se il modello richiesto è disponibile
        if echo "$AVAILABLE_MODELS" | grep -q "$OLLAMA_MODEL"; then
            echo "   ✅ Modello $OLLAMA_MODEL trovato"
        else
            echo "   ⚠️  Modello $OLLAMA_MODEL NON trovato su Ollama"
            echo "   💡 Esegui 'ollama pull $OLLAMA_MODEL' sul server Ollama per scaricarlo"
        fi
    fi

    # Pre-caricamento Ollama
    echo "   ⏳ Pre-caricamento modello in memoria..."
    PRELOAD_OUTPUT=$(curl -s -X POST $OLLAMA_URL/api/generate \
      -H "Content-Type: application/json" \
      -d "{\"model\": \"$OLLAMA_MODEL\", \"prompt\": \"ready\", \"keep_alive\": -1}" 2>&1)

    if [ $? -eq 0 ] && [ -n "$PRELOAD_OUTPUT" ]; then
        # Verifica se la risposta contiene errori
        if echo "$PRELOAD_OUTPUT" | grep -q "error"; then
            ERROR_MSG=$(echo "$PRELOAD_OUTPUT" | python3 -c "import sys,json; data=json.load(sys.stdin); print(data.get('error','Unknown error'))" 2>/dev/null)
            echo "   ❌ Errore nel pre-caricamento: $ERROR_MSG"
            echo "   ⏸️  Continuo comunque l'avvio (fallback su stub mode)"
        else
            echo "   ✅ Modello $OLLAMA_MODEL caricato e mantenuto in memoria"
        fi
    else
        echo "   ⚠️  Impossibile caricare il modello $OLLAMA_MODEL su $OLLAMA_URL"
        echo "   ⏸️  Continuo comunque l'avvio (fallback su stub mode)"
    fi
fi

echo ""
echo "🚀 Avvio API server su porta 5005..."

python3 "$PROJECT_ROOT/app/api.py" > "$API_LOG" 2>&1 &
API_PID=$!

echo $API_PID > "$PID_FILE"

sleep 2

if ps -p "$API_PID" > /dev/null 2>&1; then
    WAIT_SECONDS=30
    CHECK_INTERVAL=1
    ELAPSED=0
    echo "   ⏳ Avvio in corso, attendo risposta API..."
    while true; do
        if ! ps -p "$API_PID" > /dev/null 2>&1; then
            echo "   ❌ Il processo API è terminato durante l'avvio"
            echo "   Controlla il log: $API_LOG"
            rm -f "$PID_FILE"
            exit 1
        fi

        if curl -sSf "http://localhost:5005/status" > /dev/null 2>&1; then
            break
        fi

        if [ "$ELAPSED" -ge "$WAIT_SECONDS" ]; then
            echo "   ⚠️  Timeout in attesa della risposta API"
            echo "   Controlla il log: $API_LOG"
            break
        fi

        echo "   ...avvio in corso (${ELAPSED}s)"
        sleep "$CHECK_INTERVAL"
        ELAPSED=$((ELAPSED + CHECK_INTERVAL))
    done

    echo "   ✅ API Server avviato (PID: $API_PID)"
    echo ""
    echo "📋 Endpoints disponibili:"
    echo "   - Webhook:    http://localhost:5005/webhooks/rest/webhook"
    echo "   - Stream:     http://localhost:5005/webhooks/rest/webhook/stream"
    echo "   - Parse NLU:  http://localhost:5005/model/parse"
    echo "   - Status:     http://localhost:5005/status"
    echo "   - Health:     http://localhost:5005/"
    echo ""
    echo "🤖 Backend LLM configurato: $GIAS_LLM_BACKEND"
    if [ "$GIAS_LLM_BACKEND" = "ollama" ]; then
        echo "   - Ollama host: $OLLAMA_HOST"
        echo "   - Ollama model: ${OLLAMA_MODEL:-$GIAS_LLM_MODEL}"
    else
        echo "   - Llama.cpp host: $LLAMACPP_HOST"
    fi
    echo ""
    echo "📝 Log file: $API_LOG"
    echo ""
    echo "🛑 Per fermare il server: ./stop_server.sh"
    echo ""
    echo "=========================================="
    echo "   Server pronto per ricevere richieste"
    echo "=========================================="
else
    echo "   ❌ Errore nell'avvio del server"
    echo "   Controlla il log: $API_LOG"
    rm -f "$PID_FILE"
    exit 1
fi
