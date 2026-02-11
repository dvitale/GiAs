#!/bin/bash
# Script di pulizia Ollama - scarica modelli non utilizzati dalla memoria

echo "========================================================================"
echo "  PULIZIA MODELLI OLLAMA"
echo "========================================================================"
echo ""

# Determina modello configurato
if [ -f "start_server.sh" ]; then
    EXPECTED_MODEL=$(grep 'export GIAS_LLM_MODEL' start_server.sh | cut -d'"' -f2)
else
    EXPECTED_MODEL="llama3.2"
fi

# Mappa al nome completo Ollama
if [ "$EXPECTED_MODEL" = "llama3.2" ]; then
    KEEP_MODEL="llama3.2:3b"
elif [ "$EXPECTED_MODEL" = "llama3.1" ]; then
    KEEP_MODEL="llama3.1:8b"
elif [ "$EXPECTED_MODEL" = "mistral-nemo" ]; then
    KEEP_MODEL="mistral-nemo:latest"
elif [ "$EXPECTED_MODEL" = "velvet" ]; then
    KEEP_MODEL="Almawave/Velvet:latest"
else
    KEEP_MODEL="$EXPECTED_MODEL"
fi

echo "📌 Modello configurato: $EXPECTED_MODEL ($KEEP_MODEL)"
echo ""

# Mostra modelli in memoria
echo "📊 Modelli attualmente in memoria:"
ollama ps
echo ""

# Conta modelli
MODEL_COUNT=$(ollama ps | tail -n +2 | wc -l)

if [ "$MODEL_COUNT" -eq 0 ]; then
    echo "ℹ️  Nessun modello in memoria"
    exit 0
fi

if [ "$MODEL_COUNT" -eq 1 ]; then
    LOADED=$(ollama ps | tail -n +2 | awk '{print $1}')
    if echo "$KEEP_MODEL" | grep -q "$LOADED"; then
        echo "✅ Solo il modello configurato ($LOADED) è in memoria"
        echo "   Nessuna pulizia necessaria"
        exit 0
    fi
fi

# Pulizia modelli non necessari
echo "🧹 Pulizia modelli non configurati..."
echo ""

CLEANED=0

while IFS= read -r line; do
    MODEL_NAME=$(echo "$line" | awk '{print $1}')

    # Salta se è il modello configurato
    if echo "$KEEP_MODEL" | grep -q "$MODEL_NAME"; then
        echo "  ⏭️  Mantengo: $MODEL_NAME (configurato)"
        continue
    fi

    # Scarica dalla memoria
    echo "  🗑️  Scaricamento: $MODEL_NAME..."

    curl -s -X POST http://localhost:11434/api/generate \
        -d "{\"model\": \"$MODEL_NAME\", \"keep_alive\": 0}" > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        echo "     ✅ Scaricato con successo"
        CLEANED=$((CLEANED + 1))
    else
        echo "     ⚠️  Errore nello scaricamento"
    fi

done < <(ollama ps | tail -n +2)

echo ""

# Risultato finale
echo "========================================================================"
echo "  RIEPILOGO"
echo "========================================================================"
echo ""

sleep 2  # Attendi che Ollama aggiorni lo stato

echo "📊 Modelli in memoria dopo pulizia:"
ollama ps
echo ""

FINAL_COUNT=$(ollama ps | tail -n +2 | wc -l)

echo "📈 Risultato:"
echo "   Prima:  $MODEL_COUNT modelli"
echo "   Dopo:   $FINAL_COUNT modelli"
echo "   Puliti: $CLEANED modelli"
echo ""

if [ "$FINAL_COUNT" -eq 1 ]; then
    echo "✅ Pulizia completata con successo"
elif [ "$FINAL_COUNT" -eq 0 ]; then
    echo "⚠️  Nessun modello in memoria (potrebbe essere normale)"
else
    echo "⚠️  Ci sono ancora $FINAL_COUNT modelli in memoria"
    echo "   Verifica manualmente con: ollama ps"
fi

echo ""
echo "========================================================================"
