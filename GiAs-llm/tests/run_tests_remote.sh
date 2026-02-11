#!/bin/bash
# Script per eseguire test con Ollama remoto
# Gestisce avvio backend, timeout e verifiche preliminari

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "═══════════════════════════════════════════════════════════════"
echo "  GiAs-llm Test Suite con Ollama Remoto"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Verifica configurazione Ollama
echo "📋 Verifica configurazione..."
OLLAMA_HOST=$(python3 -c "
import json, os
with open('$PROJECT_ROOT/configs/config.json') as f:
    config = json.load(f)
host = os.environ.get('OLLAMA_HOST') or config.get('llm_backend', {}).get('ollama', {}).get('host', 'localhost')
print(host)
")

echo "   Ollama host: $OLLAMA_HOST"

# Verifica raggiungibilità Ollama
echo ""
echo "🔌 Verifica connessione Ollama..."
if curl -s --max-time 5 "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
    echo "   ✅ Ollama raggiungibile"

    # Mostra modelli disponibili
    echo ""
    echo "🤖 Modelli disponibili:"
    curl -s "$OLLAMA_HOST/api/tags" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for m in data.get('models', []):
        size_mb = m.get('size', 0) // 1024 // 1024
        print(f\"   - {m['name']} ({size_mb}MB)\")
except:
    pass
" 2>/dev/null || echo "   (impossibile elencare modelli)"
else
    echo "   ❌ Ollama NON raggiungibile su $OLLAMA_HOST"
    echo ""
    echo "Verifica:"
    echo "  1. Il server Ollama è in esecuzione su paolonb?"
    echo "  2. La porta 11434 è accessibile dalla rete?"
    echo "  3. Firewall/router permettono la connessione?"
    echo ""
    read -p "Continuare comunque? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Verifica backend in esecuzione
echo ""
echo "🚀 Verifica backend GiAs-llm..."

if curl -s --max-time 3 http://localhost:5005/status > /dev/null 2>&1; then
    echo "   ✅ Backend in esecuzione"

    # Mostra info backend
    curl -s http://localhost:5005/status | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f\"   LLM: {data.get('llm', 'N/A')}\")
    print(f\"   Model loaded: {data.get('model_loaded', False)}\")
    dl = data.get('data_loaded', {})
    print(f\"   Piani: {dl.get('piani', 0):,}, Controlli: {dl.get('controlli', 0):,}\")
except:
    pass
" 2>/dev/null
else
    echo "   ⚠️  Backend NON in esecuzione"
    echo ""
    read -p "Avviare il backend ora? (Y/n) " -n 1 -r
    echo

    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        echo ""
        echo "Avvio backend con llama3.2:3b..."
        cd "$PROJECT_ROOT"

        # Avvia in background senza prompt interattivo
        GIAS_LLM_MODEL=llama3.2 scripts/server.sh start

        echo ""
        echo "⏳ Attesa caricamento modello (max 60s)..."

        # Attendi che backend sia pronto
        for i in {1..60}; do
            if curl -s --max-time 2 http://localhost:5005/status > /dev/null 2>&1; then
                STATUS=$(curl -s http://localhost:5005/status | python3 -c "import sys,json; print(json.load(sys.stdin).get('model_loaded', False))" 2>/dev/null)
                if [ "$STATUS" = "True" ]; then
                    echo "   ✅ Backend pronto dopo ${i}s"
                    break
                fi
            fi

            if [ $((i % 5)) -eq 0 ]; then
                echo "   ... ancora in caricamento (${i}s/$60s)"
            fi

            sleep 1
        done

        # Verifica finale
        if ! curl -s --max-time 3 http://localhost:5005/status > /dev/null 2>&1; then
            echo ""
            echo "❌ Backend non si è avviato correttamente"
            echo ""
            echo "Controlla i log:"
            echo "  tail -50 runtime/logs/api-server.log"
            exit 1
        fi
    else
        echo ""
        echo "❌ Test annullati (backend richiesto)"
        exit 1
    fi
fi

# Scegli modalità test
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Seleziona modalità test"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "1) Quick mode (solo test essenziali, ~2-3 min)"
echo "2) Full mode (tutti i test, ~10-15 min con Ollama remoto)"
echo "3) Verbose quick (mostra ogni test, utile per debug)"
echo "4) Annulla"
echo ""
read -p "Scegli modalità [1-4]: " mode

case $mode in
    1)
        echo ""
        echo "🏃 Esecuzione test in modalità QUICK..."
        cd "$SCRIPT_DIR"
        python3 test_server.py --quick
        ;;
    2)
        echo ""
        echo "⚠️  Modalità FULL con Ollama remoto può richiedere 10-15 minuti"
        read -p "Continuare? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo ""
            echo "🔬 Esecuzione test COMPLETI..."
            cd "$SCRIPT_DIR"
            python3 test_server.py
        else
            echo "Test annullati"
            exit 0
        fi
        ;;
    3)
        echo ""
        echo "🔍 Esecuzione test QUICK in modalità VERBOSE..."
        cd "$SCRIPT_DIR"
        python3 test_server.py --quick --verbose
        ;;
    *)
        echo "Test annullati"
        exit 0
        ;;
esac

EXIT_CODE=$?

echo ""
echo "═══════════════════════════════════════════════════════════════"
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Test completati con successo"
else
    echo "⚠️  Alcuni test sono falliti (exit code: $EXIT_CODE)"
    echo ""
    echo "Possibili cause:"
    echo "  • Ollama remoto troppo lento (considera timeout più alti)"
    echo "  • Problemi di rete verso $OLLAMA_HOST"
    echo "  • Classificazione intent errata (verifica temperatura=0)"
    echo ""
    echo "Vedi: tests/REMOTE_OLLAMA_SOLUTION.md per soluzioni"
fi
echo "═══════════════════════════════════════════════════════════════"

exit $EXIT_CODE
