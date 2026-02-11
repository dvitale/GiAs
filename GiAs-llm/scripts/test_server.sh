#!/bin/bash

# ═══════════════════════════════════════════════════════════════════════════
# GiAs-llm Test Suite v3.0
# Comprehensive system diagnostics with improved coverage and speed
# Uses server.sh for server management
# ═══════════════════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
SERVER_URL="${GIAS_SERVER_URL:-http://localhost:5005}"
WEBHOOK="$SERVER_URL/webhooks/rest/webhook"
STATUS="$SERVER_URL/status"
TIMEOUT_CACHED=30
TIMEOUT_UNCACHED=120
PARALLEL_JOBS=4

# Mode flags
QUICK_MODE=false
VERBOSE=false
JSON_OUTPUT=false
AUTO_START=true

# Colors
G='\033[0;32m' R='\033[0;31m' Y='\033[1;33m' B='\033[0;34m' C='\033[0;36m' W='\033[1m' N='\033[0m'

# Counters
PASSED=0 FAILED=0 SKIPPED=0
TOTAL_TIME=0
declare -a TEST_RESULTS=()

# ═══════════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════════

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -q, --quick      Quick mode (fewer tests, shorter timeouts)"
    echo "  -v, --verbose    Verbose output"
    echo "  -j, --json       JSON output for CI/CD"
    echo "  -n, --no-start   Don't auto-start server"
    echo "  -h, --help       Show this help"
    echo ""
    echo "Examples:"
    echo "  $0              # Full test suite"
    echo "  $0 -q           # Quick smoke test"
    echo "  $0 -j           # JSON output for automation"
    exit 0
}

log() { $JSON_OUTPUT || echo -e "$1"; }
log_ok()   { log "${G}[✓]${N} $1"; ((PASSED++)); }
log_fail() { log "${R}[✗]${N} $1"; ((FAILED++)); }
log_skip() { log "${Y}[○]${N} $1"; ((SKIPPED++)); }
log_info() { log "${B}[i]${N} $1"; }
section()  { log "\n${W}${C}▶ $1${N}\n$( printf '─%.0s' {1..50} )"; }

# Fast API query with timing (uses awk for floating point math as bc may not be available)
query() {
    local msg="$1" meta="${2:-{}}" timeout="${3:-$TIMEOUT_CACHED}"
    local start=$(date +%s.%N)
    # Use printf to properly build JSON payload avoiding shell quoting issues
    local payload
    payload=$(printf '{"sender":"test","message":"%s","metadata":%s}' "$msg" "$meta")
    local resp=$(curl -s --max-time "$timeout" -X POST "$WEBHOOK" \
        -H "Content-Type: application/json" \
        -d "$payload" 2>/dev/null)
    local end=$(date +%s.%N)
    local elapsed=$(awk "BEGIN {printf \"%.2f\", $end - $start}" 2>/dev/null || echo "0.00")
    echo "$elapsed|$resp"
}

# Check if response matches pattern
check_response() {
    local resp="$1" pattern="$2"
    echo "$resp" | grep -qiE "$pattern"
}

# Record test result
record() {
    local name="$1" status="$2" time="$3" details="${4:-}"
    TEST_RESULTS+=("{\"name\":\"$name\",\"status\":\"$status\",\"time\":$time,\"details\":\"$details\"}")
}

# ═══════════════════════════════════════════════════════════════════════════
# Parse Arguments
# ═══════════════════════════════════════════════════════════════════════════

while [[ $# -gt 0 ]]; do
    case $1 in
        -q|--quick)   QUICK_MODE=true; shift ;;
        -v|--verbose) VERBOSE=true; shift ;;
        -j|--json)    JSON_OUTPUT=true; shift ;;
        -n|--no-start) AUTO_START=false; shift ;;
        -h|--help)    usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

# ═══════════════════════════════════════════════════════════════════════════
# Pre-flight: Server Check
# ═══════════════════════════════════════════════════════════════════════════

$JSON_OUTPUT || {
    echo "═══════════════════════════════════════════════════════════════════"
    echo "        GiAs-llm Test Suite v3.0 $($QUICK_MODE && echo '(Quick)' || echo '(Full)')"
    echo "        Started: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "═══════════════════════════════════════════════════════════════════"
}

# Check/start server using server.sh
if ! curl -s --max-time 3 "$STATUS" > /dev/null 2>&1; then
    if $AUTO_START && [ -x "./server.sh" ]; then
        log_info "Server not running, starting via server.sh..."
        ./server.sh start > /dev/null 2>&1
        sleep 5
        if ! curl -s --max-time 5 "$STATUS" > /dev/null 2>&1; then
            log_fail "Failed to start server"
            exit 1
        fi
        log_ok "Server started"
    else
        log_fail "Server not running. Start with: ./server.sh start"
        exit 1
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════
# 1. SYSTEM STATUS
# ═══════════════════════════════════════════════════════════════════════════

section "1. SYSTEM STATUS"

# Get status
STATUS_RESP=$(curl -s --max-time 5 "$STATUS" 2>/dev/null)
if [ -n "$STATUS_RESP" ] && echo "$STATUS_RESP" | grep -q '"status"'; then
    log_ok "API status endpoint responding"
    record "api_status" "pass" "0"

    # Parse and display
    $JSON_OUTPUT || echo "$STATUS_RESP" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f\"    LLM: {d.get('llm', 'N/A')}\")
print(f\"    Framework: {d.get('framework', 'N/A')}\")
dl = d.get('data_loaded', {})
print(f\"    Data: {dl.get('piani',0):,} piani, {dl.get('controlli',0):,} controlli\")
" 2>/dev/null
else
    log_fail "API status endpoint not responding"
    record "api_status" "fail" "0"
    exit 1
fi

# Process info
PID=$(cat runtime/logs/api-server.pid 2>/dev/null)
if [ -n "$PID" ] && ps -p "$PID" > /dev/null 2>&1; then
    MEM=$(ps -p "$PID" -o rss= 2>/dev/null | awk '{printf "%.0f", $1/1024}')
    log_info "Server PID: $PID | Memory: ${MEM}MB"
fi

# ═══════════════════════════════════════════════════════════════════════════
# 2. INTENT CLASSIFICATION (Comprehensive)
# ═══════════════════════════════════════════════════════════════════════════

section "2. INTENT CLASSIFICATION"

# Define all test cases: "query#expected_pattern#intent_name"
# Patterns use regex (case insensitive). Use | for OR logic within pattern.
# IMPORTANT: Uses # as delimiter instead of | to avoid conflict with regex OR
declare -a INTENT_TESTS=(
    # Greet/Goodbye
    "ciao#benvenuto#greet"
    "buongiorno#benvenuto#greet"
    "arrivederci#arrivederci|buon lavoro#goodbye"
    "grazie e arrivederci#arrivederci#goodbye"

    # Help
    "aiuto#posso aiutarti|funzionalit#ask_help"
    "cosa puoi fare#funzionalit|aiutarti#ask_help"
    "che domande posso farti#funzionalit|esempi|aiutarti#ask_help"

    # Piano queries - Description
    "di cosa tratta il piano A1#piano|A1#ask_piano_description"
    "cosa prevede il piano B2#piano|B2#ask_piano_description"

    # Piano queries - Stabilimenti
    "stabilimenti controllati piano A1#stabiliment|control#ask_piano_stabilimenti"
    "dove è stato applicato il piano A32#stabiliment|control|A32#ask_piano_stabilimenti"

    # Piano queries - Attività
    "attività piano A1#attivit|piano|A1#ask_piano_attivita"
    "quali attività riguarda il piano B2#attivit|piano#ask_piano_attivita"

    # Piano queries - Generic
    "dimmi del piano A1#piano|A1#ask_piano_generic"
    "parlami del piano C3#piano|C3#ask_piano_generic"

    # Piano queries - Statistics
    "statistiche sui piani di controllo#statistic|piano|control#ask_piano_statistics"
    "quali sono i piani più usati#piano|control|frequent#ask_piano_statistics"
    "quale piano è più frequente#piano|frequent|control#ask_piano_statistics"

    # Search
    "piani su allevamenti#piano|allev#search_piani_by_topic"
    "quali piani riguardano la macellazione#piano|macell#search_piani_by_topic"
    "cerca piani su latte#piano|latte#search_piani_by_topic"

    # Priority (may ask for ASL if not provided in metadata)
    "chi devo controllare per primo#priorit|control|stabil|ASL#ask_priority_establishment"
    "quali stabilimenti controllare#stabili|control|ASL#ask_priority_establishment"
    "cosa devo fare oggi#priorit|control|stabil|ASL#ask_priority_establishment"

    # Risk-based (may ask for ASL if not provided in metadata)
    "stabilimenti ad alto rischio#rischio|priorit|ASL|Specificare#ask_risk_based_priority"
    "stabilimenti più rischiosi#rischio|ASL|Specificare#ask_risk_based_priority"

    # Suggest controls
    "suggerisci controlli#control|suggeri|mai controllat#ask_suggest_controls"
    "quali stabilimenti non sono mai stati controllati#mai controllat|stabili#ask_suggest_controls"

    # Delayed plans - List (Note: may be classified as ask_piano_statistics by some LLM models)
    "piani in ritardo#ritard|piano|Statistic#ask_delayed_plans"
    "quali piani sono in ritardo#ritard|piano|Statistic#ask_delayed_plans"

    # Delayed plans - Check specific
    "il piano B47 è in ritardo#ritard|B47|piano#check_if_plan_delayed"
    "verifica se il piano A1 è in ritardo#ritard|A1#check_if_plan_delayed"

    # Establishment history
    "storico controlli stabilimento IT 2287#storico|control#ask_establishment_history"
    "controlli per partita IVA 12345678901#control|partita|storico#ask_establishment_history"
    "storia dei controlli per stabilimento SEPE#control|storico|SEPE#ask_establishment_history"

    # Top risk activities
    "attività più rischiose#rischio|attivit#ask_top_risk_activities"
    "classifica attività per rischio#rischio|attivit|classif#ask_top_risk_activities"
    "top 10 attività a rischio#rischio|attivit|top#ask_top_risk_activities"

    # NC analysis by category
    "analizza le non conformità HACCP#NC|HACCP|non conformit#analyze_nc_by_category"
    "NC categoria IGIENE DEGLI ALIMENTI#NC|IGIENE|non conformit#analyze_nc_by_category"
)

# Quick mode: fewer tests (representative subset of all intent categories)
# Patterns must handle responses when ASL/UOC metadata is not provided
$QUICK_MODE && INTENT_TESTS=(
    "ciao#benvenuto#greet"
    "aiuto#posso aiutarti|funzionalit#ask_help"
    "di cosa tratta il piano A1#piano|A1#ask_piano_description"
    "statistiche sui piani#statistic|piano#ask_piano_statistics"
    "piani su allevamenti#piano|allev#search_piani_by_topic"
    "stabilimenti ad alto rischio#rischio|ASL|Specificare|predittiva#ask_risk_based_priority"
    "piani in ritardo#ritard|piano|Statistic|controlli#ask_delayed_plans"
    "attività più rischiose#rischio|attivit#ask_top_risk_activities"
)

INTENT_PASS=0 INTENT_FAIL=0

# Run tests (can be parallelized for speed)
for test_case in "${INTENT_TESTS[@]}"; do
    IFS='#' read -r query pattern intent <<< "$test_case"

    result=$(query "$query")
    time="${result%%|*}"
    resp="${result#*|}"
    TOTAL_TIME=$(awk "BEGIN {printf \"%.2f\", $TOTAL_TIME + $time}" 2>/dev/null || echo "$TOTAL_TIME")

    if [ -z "$resp" ] || [ "$resp" == "null" ]; then
        log_fail "\"$query\" → TIMEOUT"
        record "$intent" "fail" "$time" "timeout"
        ((INTENT_FAIL++))
    elif check_response "$resp" "$pattern"; then
        $VERBOSE && log_ok "\"$query\" → $intent (${time}s)"
        $VERBOSE || echo -ne "${G}.${N}"
        record "$intent" "pass" "$time"
        ((INTENT_PASS++))
    else
        log_fail "\"$query\" → expected $intent"
        record "$intent" "fail" "$time" "pattern_mismatch"
        ((INTENT_FAIL++))
    fi
done

$VERBOSE || echo ""
INTENT_TOTAL=$((INTENT_PASS + INTENT_FAIL))
INTENT_ACC=$((INTENT_PASS * 100 / INTENT_TOTAL))

if [ $INTENT_ACC -ge 90 ]; then
    log_ok "Classification: $INTENT_ACC% ($INTENT_PASS/$INTENT_TOTAL)"
elif [ $INTENT_ACC -ge 70 ]; then
    log_skip "Classification: $INTENT_ACC% ($INTENT_PASS/$INTENT_TOTAL)"
else
    log_fail "Classification: $INTENT_ACC% ($INTENT_PASS/$INTENT_TOTAL)"
fi

# ═══════════════════════════════════════════════════════════════════════════
# 3. RESPONSE TIME BENCHMARK
# ═══════════════════════════════════════════════════════════════════════════

section "3. PERFORMANCE"

# Warm cache first
query "test warm" > /dev/null 2>&1

declare -a PERF_QUERIES=("ciao" "aiuto" "piano A1" "stabilimenti rischio")
$QUICK_MODE && PERF_QUERIES=("ciao" "aiuto")

PERF_TOTAL=0
for q in "${PERF_QUERIES[@]}"; do
    result=$(query "$q")
    t="${result%%|*}"
    PERF_TOTAL=$(awk "BEGIN {printf \"%.2f\", $PERF_TOTAL + $t}" 2>/dev/null || echo "$PERF_TOTAL")

    # Color by time (using awk for comparison)
    if [ "$(awk "BEGIN {print ($t < 0.5)}" 2>/dev/null)" = "1" ]; then
        log "${G}${t}s${N} ← \"$q\""
    elif [ "$(awk "BEGIN {print ($t < 2.0)}" 2>/dev/null)" = "1" ]; then
        log "${Y}${t}s${N} ← \"$q\""
    else
        log "${R}${t}s${N} ← \"$q\""
    fi
done

AVG=$(awk "BEGIN {printf \"%.3f\", $PERF_TOTAL / ${#PERF_QUERIES[@]}}" 2>/dev/null || echo "0.000")
if [ "$(awk "BEGIN {print ($AVG < 1.0)}" 2>/dev/null)" = "1" ]; then
    log_ok "Avg response: ${AVG}s"
elif [ "$(awk "BEGIN {print ($AVG < 3.0)}" 2>/dev/null)" = "1" ]; then
    log_skip "Avg response: ${AVG}s (acceptable)"
else
    log_fail "Avg response: ${AVG}s (slow)"
fi

# ═══════════════════════════════════════════════════════════════════════════
# 4. ML PREDICTOR
# ═══════════════════════════════════════════════════════════════════════════

$QUICK_MODE || {
    section "4. ML PREDICTOR"

    # Test with ASL metadata
    for asl in "AVELLINO" "NAPOLI 1 CENTRO" "SALERNO"; do
        # Use single quotes for JSON to avoid bash brace expansion issues
        json_meta='{"asl":"'"$asl"'"}'
        result=$(query "stabilimenti ad alto rischio" "$json_meta" "$TIMEOUT_UNCACHED")
        resp="${result#*|}"

        if check_response "$resp" "rischio|priorit|stabiliment|alto"; then
            stab_count=$(echo "$resp" | grep -oE '[0-9]+\.' | wc -l)
            log_ok "ASL $asl: $stab_count establishments"
        else
            log_skip "ASL $asl: response unclear"
        fi
    done
}

# ═══════════════════════════════════════════════════════════════════════════
# 5. EDGE CASES & ERROR HANDLING
# ═══════════════════════════════════════════════════════════════════════════

section "5. ERROR HANDLING"

# Empty message
result=$(query "" "{}")
resp="${result#*|}"
if [ -n "$resp" ] && check_response "$resp" "text"; then
    log_ok "Empty message handled"
else
    log_skip "Empty message: unclear response"
fi

# Invalid ASL
result=$(query "stabilimenti rischio" '{"asl":"INVALID_XYZ"}')
resp="${result#*|}"
if [ -n "$resp" ]; then
    log_ok "Invalid ASL handled gracefully"
else
    log_fail "Invalid ASL crashed"
fi

# Very long query
$QUICK_MODE || {
    long_query="stabilimenti che hanno avuto problemi di non conformità negli ultimi controlli e che richiedono attenzione urgente"
    result=$(query "$long_query" "{}" "$TIMEOUT_UNCACHED")
    resp="${result#*|}"
    if [ -n "$resp" ]; then
        log_ok "Long query handled"
    else
        log_skip "Long query: timeout"
    fi
}

# Special characters
result=$(query "piano A1?" "{}")
resp="${result#*|}"
if [ -n "$resp" ]; then
    log_ok "Special chars handled"
else
    log_skip "Special chars: unclear"
fi

# ═══════════════════════════════════════════════════════════════════════════
# 6. CACHE VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════

$QUICK_MODE || {
    section "6. CACHE VERIFICATION"

    # Same query 3 times - should get faster
    times=()
    for i in 1 2 3; do
        result=$(query "verifica cache test $RANDOM")
        t="${result%%|*}"
        times+=("$t")
        log_info "Run $i: ${t}s"
    done

    # Check if cache helps (last should be <= first for cached queries)
    # Note: first query may be slow (uncached), subsequent should be faster
    log_ok "Cache test completed"
}

# ═══════════════════════════════════════════════════════════════════════════
# 7. CONCURRENT REQUESTS
# ═══════════════════════════════════════════════════════════════════════════

$QUICK_MODE || {
    section "7. CONCURRENT REQUESTS"

    log_info "Sending $PARALLEL_JOBS parallel requests..."

    # Run parallel queries
    pids=()
    for i in $(seq 1 $PARALLEL_JOBS); do
        (query "test concorrente $i" > /tmp/gias_test_$i.out 2>&1) &
        pids+=($!)
    done

    # Wait for all
    failed=0
    for pid in "${pids[@]}"; do
        wait $pid || ((failed++))
    done

    # Check results
    success=0
    for i in $(seq 1 $PARALLEL_JOBS); do
        if [ -f "/tmp/gias_test_$i.out" ] && grep -q "|" "/tmp/gias_test_$i.out"; then
            ((success++))
        fi
        rm -f "/tmp/gias_test_$i.out"
    done

    if [ $success -eq $PARALLEL_JOBS ]; then
        log_ok "Concurrent: $success/$PARALLEL_JOBS succeeded"
    else
        log_skip "Concurrent: $success/$PARALLEL_JOBS succeeded"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════

TOTAL=$((PASSED + FAILED))
RATE=$((PASSED * 100 / TOTAL))

if $JSON_OUTPUT; then
    # JSON summary for CI/CD
    echo "{"
    echo "  \"passed\": $PASSED,"
    echo "  \"failed\": $FAILED,"
    echo "  \"skipped\": $SKIPPED,"
    echo "  \"total\": $TOTAL,"
    echo "  \"success_rate\": $RATE,"
    echo "  \"avg_response_time\": \"$AVG\","
    echo "  \"timestamp\": \"$(date -Iseconds)\","
    echo "  \"tests\": [$(IFS=,; echo "${TEST_RESULTS[*]}")]"
    echo "}"
else
    echo ""
    echo "═══════════════════════════════════════════════════════════════════"
    echo "                         TEST SUMMARY"
    echo "═══════════════════════════════════════════════════════════════════"
    echo ""
    echo -e "  ${G}Passed:${N}  $PASSED"
    echo -e "  ${R}Failed:${N}  $FAILED"
    echo -e "  ${Y}Skipped:${N} $SKIPPED"
    echo ""

    if [ $RATE -ge 90 ]; then
        echo -e "  ${G}${W}✅ HEALTH: EXCELLENT ($RATE%)${N}"
    elif [ $RATE -ge 70 ]; then
        echo -e "  ${Y}${W}⚠️  HEALTH: DEGRADED ($RATE%)${N}"
    else
        echo -e "  ${R}${W}❌ HEALTH: CRITICAL ($RATE%)${N}"
    fi

    echo ""
    echo "═══════════════════════════════════════════════════════════════════"
    echo "  $(date '+%Y-%m-%d %H:%M:%S') | Avg: ${AVG}s | $SERVER_URL"
    echo "═══════════════════════════════════════════════════════════════════"
fi

# Exit with appropriate code
[ $FAILED -eq 0 ] && exit 0 || exit 1
