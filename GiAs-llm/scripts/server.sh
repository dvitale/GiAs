#!/bin/bash

# ═══════════════════════════════════════════════════════════════════════════
# GiAs-llm Server Management Script
# Unified script for start, stop, restart, status operations
# Note: 'start' delegates to start_server.sh to avoid code duplication
# ═══════════════════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Activate Python virtual environment
if [ -f "/opt/lang-env/bin/activate" ]; then
    source /opt/lang-env/bin/activate
fi

# Configuration
LOG_DIR="$PROJECT_ROOT/runtime/logs"
API_LOG="$LOG_DIR/api-server.log"
PID_FILE="$LOG_DIR/api-server.pid"
PORT=5005

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ═══════════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════════

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

get_pid() {
    if [ -f "$PID_FILE" ]; then
        cat "$PID_FILE"
    else
        echo ""
    fi
}

is_running() {
    local pid=$(get_pid)
    if [ -n "$pid" ] && ps -p "$pid" > /dev/null 2>&1; then
        return 0
    fi
    return 1
}

# ═══════════════════════════════════════════════════════════════════════════
# Commands
# ═══════════════════════════════════════════════════════════════════════════

cmd_status() {
    echo ""
    echo -e "${BOLD}${CYAN}═══ GiAs-llm Server Status ═══${NC}"
    echo ""

    # Process status
    if is_running; then
        local pid=$(get_pid)
        log_success "Server running (PID: $pid)"

        # Memory & CPU
        local mem_kb=$(ps -p "$pid" -o rss= 2>/dev/null | tr -d ' ')
        local mem_mb=$((mem_kb / 1024))
        local cpu=$(ps -p "$pid" -o %cpu= 2>/dev/null | tr -d ' ')
        log_info "Memory: ${mem_mb} MB | CPU: ${cpu}%"
    else
        log_error "Server not running"
        [ -f "$PID_FILE" ] && rm -f "$PID_FILE"
        return 1
    fi

    # API status
    echo ""
    local status_response=$(curl -s --max-time 5 "http://localhost:$PORT/status" 2>/dev/null || echo "")
    if [ -n "$status_response" ] && echo "$status_response" | grep -q '"status"'; then
        log_success "API responding"
        echo ""
        echo "$status_response" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(f\"  Framework: {d.get('framework', 'N/A')}\")
    print(f\"  LLM: {d.get('llm', 'N/A')}\")
    print(f\"  Year: {d.get('current_year', 'N/A')}\")
    dl = d.get('data_loaded', {})
    print(f\"  Data: piani={dl.get('piani',0):,}, controlli={dl.get('controlli',0):,}, osa={dl.get('osa_mai_controllati',0):,}\")
except: pass
" 2>/dev/null
    else
        log_warning "API not responding (may still be starting)"
    fi

    echo ""
    echo -e "  Log: ${CYAN}$API_LOG${NC}"
    echo -e "  PID: ${CYAN}$PID_FILE${NC}"
    echo ""
}

cmd_stop() {
    # Delegate to stop_server.sh (single source of truth for shutdown logic)
    exec "$SCRIPT_DIR/stop_server.sh"
}

cmd_start() {
    # Check if already running
    if is_running; then
        local pid=$(get_pid)
        echo ""
        log_warning "Server already running (PID: $pid)"
        echo "  Use '$0 restart' to restart"
        echo "  Use '$0 stop' to stop"
        echo ""
        return 1
    fi

    # Delegate to start_server.sh (single source of truth for startup logic)
    exec "$SCRIPT_DIR/start_server.sh"
}

cmd_restart() {
    echo ""
    echo -e "${BOLD}${CYAN}═══ Restarting GiAs-llm Server ═══${NC}"
    # Call stop_server.sh (not exec, need to continue)
    "$SCRIPT_DIR/stop_server.sh"
    sleep 2
    # Delegate to start_server.sh
    exec "$SCRIPT_DIR/start_server.sh"
}

cmd_logs() {
    local lines="${1:-50}"
    echo ""
    echo -e "${BOLD}${CYAN}═══ Server Logs (last $lines lines) ═══${NC}"
    echo ""
    if [ -f "$API_LOG" ]; then
        tail -n "$lines" "$API_LOG"
    else
        log_warning "Log file not found: $API_LOG"
    fi
    echo ""
}

cmd_test() {
    echo ""
    echo -e "${BOLD}${CYAN}═══ Quick API Test ═══${NC}"
    echo ""

    if ! is_running; then
        log_error "Server not running"
        return 1
    fi

    # Test queries
    declare -a tests=(
        "ciao|Benvenuto"
        "aiuto|Come posso aiutarti"
        "che domande posso farti?|funzionalità"
    )

    local passed=0
    local failed=0

    for test in "${tests[@]}"; do
        local query="${test%%|*}"
        local expected="${test##*|}"

        local response=$(curl -s --max-time 30 -X POST "http://localhost:$PORT/webhooks/rest/webhook" \
            -H "Content-Type: application/json" \
            -d "{\"sender\": \"test\", \"message\": \"$query\"}" 2>/dev/null || echo "")

        if echo "$response" | grep -qi "$expected"; then
            echo -e "  ${GREEN}✓${NC} \"$query\""
            ((passed++))
        else
            echo -e "  ${RED}✗${NC} \"$query\" (expected: $expected)"
            ((failed++))
        fi
    done

    echo ""
    if [ $failed -eq 0 ]; then
        log_success "All tests passed ($passed/$passed)"
    else
        log_warning "Tests: $passed passed, $failed failed"
    fi
    echo ""
}

cmd_help() {
    echo ""
    echo -e "${BOLD}GiAs-llm Server Management${NC}"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  start     Start the server (delegates to start_server.sh)"
    echo "  stop      Stop the server"
    echo "  restart   Restart the server"
    echo "  status    Show server status"
    echo "  logs [n]  Show last n log lines (default: 50)"
    echo "  test      Run quick API tests"
    echo "  help      Show this help"
    echo ""
    echo "Environment variables:"
    echo "  GIAS_LLM_MODEL   Model to use (llama3.2|falcon|velvet|mistral-nemo|ministral)"
    echo "  GIAS_LLM_BACKEND Backend to use (ollama|llamacpp)"
    echo "  OLLAMA_HOST      Ollama server host (default: localhost or from config.json)"
    echo ""
    echo "Examples:"
    echo "  $0 start                          # Selezione interattiva del modello"
    echo "  GIAS_LLM_MODEL=falcon $0 start    # Avvio con Falcon (no prompt)"
    echo "  GIAS_LLM_MODEL=velvet $0 start    # Avvio con Velvet (no prompt)"
    echo "  $0 restart                        # Riavvia server"
    echo "  $0 logs 100                       # Ultimi 100 log"
    echo ""
}

# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

case "${1:-help}" in
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    restart) cmd_restart ;;
    status)  cmd_status ;;
    logs)    cmd_logs "${2:-50}" ;;
    test)    cmd_test ;;
    help|--help|-h) cmd_help ;;
    *)
        log_error "Unknown command: $1"
        cmd_help
        exit 1
        ;;
esac
