#!/bin/bash
# =============================================================================
# Script per eseguire Intelligent Monitor automaticamente
#
# Usage:
#   ./run_intelligent_monitor.sh                    # Report giornaliero
#   ./run_intelligent_monitor.sh --weekly           # Report settimanale
#   ./run_intelligent_monitor.sh --suggestions      # Solo suggerimenti
#   ./run_intelligent_monitor.sh --health           # Solo health check
#
# Cron examples:
#   # Report giornaliero alle 6:00
#   0 6 * * * /path/to/scripts/run_intelligent_monitor.sh >> /var/log/gias_monitor.log 2>&1
#
#   # Report settimanale il lunedi' alle 7:00
#   0 7 * * 1 /path/to/scripts/run_intelligent_monitor.sh --weekly >> /var/log/gias_monitor_weekly.log 2>&1
#
#   # Health check ogni ora (solo alert)
#   0 * * * * /path/to/scripts/run_intelligent_monitor.sh --health --alert-only
# =============================================================================

set -e

# Configurazione
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
REPORT_DIR="${PROJECT_DIR}/runtime/reports"
LOG_FILE="${PROJECT_DIR}/runtime/logs/intelligent_monitor.log"
PYTHON_CMD="${PYTHON_CMD:-python3}"

# Parametri default
DAYS=7
MODE="full"
FORMAT="summary"
OUTPUT=""
USE_LLM=""
MIN_PRIORITY=2
ALERT_ONLY=""

# Funzione per mostrare l'help
show_help() {
    cat << 'EOF'
Intelligent Monitor - GIAS-AI
==============================

Strumento di analisi intelligente per rilevare bug, analizzare cause root,
e generare suggerimenti actionable per migliorare il sistema.

USAGE:
  ./run_intelligent_monitor.sh [OPTIONS]

OPTIONS:
  --health           Solo health check (veloce)
  --suggestions      Solo suggerimenti di miglioramento
  --daily            Report giornaliero breve
  --weekly           Report settimanale completo (JSON)
  --days N           Numero giorni da analizzare (default: 7)
  --min-priority N   Priorita' minima suggerimenti 1-5 (default: 2)
  --format FORMAT    Formato output: summary, json (default: summary)
  --output FILE      Salva output su file
  --use-llm          Abilita analisi semantica LLM (piu' lento)
  --alert-only       Output solo se ci sono alert critici
  --help             Mostra questo messaggio

ESEMPI:

  # Health check rapido
  ./run_intelligent_monitor.sh --health

  # Solo suggerimenti priorita' alta
  ./run_intelligent_monitor.sh --suggestions --min-priority 3

  # Report completo ultimi 14 giorni
  ./run_intelligent_monitor.sh --days 14

  # Report settimanale JSON (per cron)
  ./run_intelligent_monitor.sh --weekly

  # Salva su file
  ./run_intelligent_monitor.sh --health --format json --output report.json

  # Alert only (per cron - output solo se ci sono problemi critici)
  ./run_intelligent_monitor.sh --health --alert-only

CRON JOB:

  # Report giornaliero alle 6:00
  0 6 * * * /path/to/scripts/run_intelligent_monitor.sh >> /var/log/gias_monitor.log 2>&1

  # Health check ogni ora (solo alert)
  0 * * * * /path/to/scripts/run_intelligent_monitor.sh --health --alert-only

  # Report settimanale il lunedi alle 7:00
  0 7 * * 1 /path/to/scripts/run_intelligent_monitor.sh --weekly

EOF
}

# Mostra help se nessun parametro
if [[ $# -eq 0 ]]; then
    show_help
    exit 0
fi

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --weekly)
            DAYS=7
            MODE="full"
            FORMAT="json"
            OUTPUT="${REPORT_DIR}/weekly_$(date +%Y%m%d).json"
            shift
            ;;
        --daily)
            DAYS=1
            MODE="full"
            FORMAT="summary"
            shift
            ;;
        --suggestions)
            MODE="suggestions"
            shift
            ;;
        --health)
            MODE="health"
            shift
            ;;
        --use-llm)
            USE_LLM="--use-llm"
            shift
            ;;
        --days)
            DAYS="$2"
            shift 2
            ;;
        --format)
            FORMAT="$2"
            shift 2
            ;;
        --output)
            OUTPUT="$2"
            shift 2
            ;;
        --min-priority)
            MIN_PRIORITY="$2"
            shift 2
            ;;
        --alert-only)
            ALERT_ONLY="1"
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            echo "Errore: Opzione sconosciuta '$1'"
            echo ""
            show_help
            exit 1
            ;;
    esac
done

# Crea directory se non esistono
mkdir -p "$REPORT_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

# Timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Log function
log() {
    echo "[${TIMESTAMP}] $1" | tee -a "$LOG_FILE"
}

log "=== Intelligent Monitor Start ==="
log "Mode: $MODE, Days: $DAYS, Format: $FORMAT"

# Cambia directory
cd "$PROJECT_DIR"

# Costruisci comando
CMD="$PYTHON_CMD -m tools.intelligent_monitor --days $DAYS --min-priority $MIN_PRIORITY --format $FORMAT"

case $MODE in
    "full")
        # Report completo
        if [ -n "$USE_LLM" ]; then
            CMD="$CMD --use-llm"
        fi
        ;;
    "suggestions")
        CMD="$CMD --suggestions"
        ;;
    "health")
        CMD="$CMD --health"
        ;;
esac

if [ -n "$OUTPUT" ]; then
    CMD="$CMD --output $OUTPUT"
fi

log "Running: $CMD"

# Esegui comando
OUTPUT_TEXT=$($CMD 2>&1) || {
    log "ERROR: Command failed with exit code $?"
    log "$OUTPUT_TEXT"
    exit 1
}

# Se alert-only, controlla se ci sono alert critici
if [ -n "$ALERT_ONLY" ]; then
    # Cerca pattern di alert nel output
    if echo "$OUTPUT_TEXT" | grep -qiE "(CRIT|critical|error_spike)"; then
        log "ALERT: Critical issues detected!"
        echo "$OUTPUT_TEXT"
    else
        log "OK: No critical alerts"
    fi
else
    # Output normale
    if [ -z "$OUTPUT" ]; then
        echo "$OUTPUT_TEXT"
    else
        log "Report saved to: $OUTPUT"
    fi
fi

log "=== Intelligent Monitor End ==="
