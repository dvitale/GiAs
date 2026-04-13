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
echo "📊 Verifica data source..."
CONFIG_FILE="$PROJECT_ROOT/configs/config.json"

# Legge config e verifica DB in un'unica invocazione Python
DS_CHECK=$(python3 -c "
import json, sys
c = json.load(open('$CONFIG_FILE'))
ds = c.get('data_source', {})
ds_type = ds.get('type', 'csv')
if ds_type == 'postgresql':
    pg = ds.get('postgresql', {})
    host, db = pg.get('host', 'localhost'), pg.get('database', 'gias_db')
    print(f'TYPE=postgresql HOST={host} DB={db}', end=' ')
    try:
        import psycopg2
        conn = psycopg2.connect(host=pg['host'], port=pg.get('port',5432), dbname=pg['database'], user=pg['user'], password=pg['password'], connect_timeout=3)
        conn.close()
        print('REACHABLE=yes')
    except Exception:
        print('REACHABLE=no')
else:
    print(f'TYPE={ds_type}')
" 2>/dev/null)

if echo "$DS_CHECK" | grep -q "TYPE=postgresql"; then
    DB_HOST=$(echo "$DS_CHECK" | grep -oP 'HOST=\K\S+')
    DB_NAME=$(echo "$DS_CHECK" | grep -oP 'DB=\K\S+')
    echo "   📌 Data source: PostgreSQL ($DB_HOST/$DB_NAME)"
    if echo "$DS_CHECK" | grep -q "REACHABLE=yes"; then
        echo "   ✅ Database raggiungibile"
    else
        echo "   ⚠️  Database non raggiungibile (il server partira' comunque)"
    fi
else
    if [ -d "$PROJECT_ROOT/data/dataset.10" ]; then
        NUM_FILES=$(ls -1 "$PROJECT_ROOT/data/dataset.10"/*.csv 2>/dev/null | wc -l)
        echo "   📌 Data source: CSV ($NUM_FILES file)"
    else
        echo "   ⚠️  Directory dataset.10 non trovata"
    fi
fi

echo ""
echo "🤖 Verifica backend LLM..."

# Configurazione backend (priorita': env var > config.json > default ollama)
if [ -z "$GIAS_LLM_BACKEND" ]; then
    CONFIG_FILE="$PROJECT_ROOT/configs/config.json"
    if [ -f "$CONFIG_FILE" ]; then
        CONFIG_BACKEND=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE')).get('llm_backend', {}).get('type', 'ollama'))" 2>/dev/null)
        export GIAS_LLM_BACKEND="${CONFIG_BACKEND:-ollama}"
    else
        export GIAS_LLM_BACKEND="ollama"
    fi
else
    export GIAS_LLM_BACKEND
fi
echo "   📌 Backend LLM configurato: $GIAS_LLM_BACKEND"

# Configurazione Ollama host (solo per backend locali)
if [ "$GIAS_LLM_BACKEND" = "ollama" ] || [ "$GIAS_LLM_BACKEND" = "llamacpp" ]; then
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
fi

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

if [ "$GIAS_LLM_BACKEND" = "openai" ] || [ "$GIAS_LLM_BACKEND" = "anthropic" ] || [ "$GIAS_LLM_BACKEND" = "openai_compat" ] || [ "$GIAS_LLM_BACKEND" = "openrouter" ]; then
    # ═══════════════════════════════════════════════════════
    # Provider LLM esterno (OpenAI, Anthropic, Mistral, etc.)
    # ═══════════════════════════════════════════════════════
    CONFIG_FILE="$PROJECT_ROOT/configs/config.json"

    # Leggi modello e host dal config.json
    EXTERNAL_MODEL=$(python3 -c "import json; c=json.load(open('$CONFIG_FILE')); print(c.get('llm_backend',{}).get('$GIAS_LLM_BACKEND',{}).get('model','N/A'))" 2>/dev/null)
    EXTERNAL_HOST=$(python3 -c "import json; c=json.load(open('$CONFIG_FILE')); print(c.get('llm_backend',{}).get('$GIAS_LLM_BACKEND',{}).get('host','API cloud'))" 2>/dev/null)
    API_KEY_ENV=$(python3 -c "import json; c=json.load(open('$CONFIG_FILE')); print(c.get('llm_backend',{}).get('$GIAS_LLM_BACKEND',{}).get('api_key_env',''))" 2>/dev/null)

    echo "   🌐 Provider esterno: $GIAS_LLM_BACKEND"
    echo "   🤖 Modello: ${EXTERNAL_MODEL:-N/A}"
    [ -n "$EXTERNAL_HOST" ] && [ "$EXTERNAL_HOST" != "API cloud" ] && echo "   🔌 Host: $EXTERNAL_HOST"

    # Verifica API key
    if [ -n "$API_KEY_ENV" ]; then
        API_KEY_VALUE=$(eval echo "\$$API_KEY_ENV")
        if [ -n "$API_KEY_VALUE" ]; then
            # Mostra solo i primi 8 caratteri
            MASKED_KEY="${API_KEY_VALUE:0:8}..."
            echo "   🔑 API Key ($API_KEY_ENV): $MASKED_KEY"
        else
            echo "   ⚠️  API Key non trovata! Impostare la variabile ambiente: export $API_KEY_ENV=sk-..."
            echo "   ⏸️  Continuo comunque l'avvio (fallback su stub mode)"
        fi
    fi

    # Verifica GDPR gate
    GDPR_ALLOWED=$(python3 -c "import json; c=json.load(open('$CONFIG_FILE')); print(c.get('gdpr',{}).get('allow_external_llm',False))" 2>/dev/null)
    if [ "$GDPR_ALLOWED" = "True" ]; then
        echo "   ✅ GDPR gate: autorizzato (allow_external_llm=true)"
    else
        echo "   ⛔ GDPR gate: BLOCCATO (allow_external_llm=false in config.json)"
        echo "   💡 Impostare gdpr.allow_external_llm a true per usare provider esterni"
        echo "   ⏸️  Continuo comunque l'avvio (il backend Python gestira' l'errore)"
    fi

elif [ "$GIAS_LLM_BACKEND" = "llamacpp" ]; then
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

PYTHONUNBUFFERED=1 python3 "$PROJECT_ROOT/app/api.py" > "$API_LOG" 2>&1 &
API_PID=$!

echo $API_PID > "$PID_FILE"

sleep 2

if ps -p "$API_PID" > /dev/null 2>&1; then
    WAIT_SECONDS=180
    CHECK_INTERVAL=3
    ELAPSED=0
    READY=0
    echo "   ⏳ Avvio in corso, attendo risposta API..."
    while [ "$ELAPSED" -lt "$WAIT_SECONDS" ]; do
        if ! ps -p "$API_PID" > /dev/null 2>&1; then
            echo "   ❌ Il processo API è terminato durante l'avvio"
            echo "   Controlla il log: $API_LOG"
            rm -f "$PID_FILE"
            exit 1
        fi

        if curl -sSf "http://localhost:5005/status" > /dev/null 2>&1; then
            READY=1
            break
        fi

        echo "   ...avvio in corso (${ELAPSED}s)"
        sleep "$CHECK_INTERVAL"
        ELAPSED=$((ELAPSED + CHECK_INTERVAL))
    done

    if [ "$READY" -ne 1 ]; then
        echo "   ❌ Timeout (${WAIT_SECONDS}s) in attesa della risposta API"
        echo "   Il processo (PID: $API_PID) è ancora in esecuzione ma non risponde su :5005"
        echo "   Controlla il log: $API_LOG"
        echo "   Per terminarlo: ./stop_server.sh"
        exit 1
    fi

    echo "   ✅ API Server avviato (PID: $API_PID)"
    echo ""
    echo "📋 Endpoints disponibili:"
    echo "   - Chat V1:    http://localhost:5005/api/v1/chat"
    echo "   - Stream V1:  http://localhost:5005/api/v1/chat/stream"
    echo "   - Parse V1:   http://localhost:5005/api/v1/parse"
    echo "   - Status:     http://localhost:5005/status"
    echo "   - Health:     http://localhost:5005/"
    echo ""
    echo "🤖 Backend LLM configurato: $GIAS_LLM_BACKEND"
    if [ "$GIAS_LLM_BACKEND" = "ollama" ]; then
        echo "   - Ollama host: $OLLAMA_HOST"
        echo "   - Ollama model: ${OLLAMA_MODEL:-$GIAS_LLM_MODEL}"
    elif [ "$GIAS_LLM_BACKEND" = "llamacpp" ]; then
        echo "   - Llama.cpp host: $LLAMACPP_HOST"
    else
        echo "   - Provider: $GIAS_LLM_BACKEND (esterno)"
        echo "   - Model: ${EXTERNAL_MODEL:-da config.json}"
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
