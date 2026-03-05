#!/usr/bin/env bash
set -u

# Wrapper per la versione Python più ricca di informazioni.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$SCRIPT_DIR/ollama-monitor.py"

if [[ -x "$PY" ]]; then
  exec "$PY" -i "${1:-2}"
fi

echo "Errore: $PY non trovato o non eseguibile."
exit 1
