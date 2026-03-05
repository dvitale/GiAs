#!/bin/bash
# ==============================================================================
# db_compare.sh - Confronto DDL e dati tra due database PostgreSQL
#
# Uso:
#   ./db_compare.sh                    # confronto completo (DDL + dati)
#   ./db_compare.sh --ddl-only         # solo confronto schema DDL
#   ./db_compare.sh --data-only        # solo confronto dati tabelle config
#   ./db_compare.sh --table intents    # confronto dati di una sola tabella
#
# Prerequisiti:
#   - pg_dump e psql installati localmente
#   - Accesso SSH al server remoto (consigliato: chiave SSH senza password)
#   - pg_dump e psql disponibili anche sul server remoto
# ==============================================================================

set -euo pipefail

# ==============================================================================
# CONFIGURAZIONE - Caricata da .remote_config
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOTE_CONFIG="${SCRIPT_DIR}/.remote_config"

if [[ ! -f "$REMOTE_CONFIG" ]]; then
    echo "ERRORE: file di configurazione non trovato: ${REMOTE_CONFIG}" >&2
    exit 1
fi

# shellcheck source=.remote_config
source "$REMOTE_CONFIG"

# --- Database locale ---
LOCAL_HOST="localhost"
LOCAL_PORT="${LOCAL_DBPORT:-5432}"
LOCAL_DB="${LOCAL_DB:-gias_db}"
LOCAL_USER="${LOCAL_DBUSER:-gisa_owner}"
LOCAL_PASSWORD="${LOCAL_DBPASSWORD:-}"
LOCAL_SCHEMA="public"

# --- Server remoto (connessione SSH) ---
REMOTE_SSH_USER="${REMOTE_USER}"
REMOTE_SSH_HOST="${REMOTE_HOST}"
REMOTE_SSH_PORT="${REMOTE_SSH_PORT:-22}"
# Opzionale: chiave SSH specifica
# REMOTE_SSH_KEY="~/.ssh/id_rsa_remote"

# --- Database remoto (credenziali sul server remoto) ---
REMOTE_HOST="localhost"       # dal punto di vista del server remoto
REMOTE_PORT="${REMOTE_DBPORT:-5432}"
REMOTE_DB="${REMOTE_DB:-gias_db}"
REMOTE_USER="${REMOTE_DBUSER}"
REMOTE_PASSWORD="${REMOTE_DBPASSWORD:-}"
REMOTE_SCHEMA="public"

# --- Tabelle da confrontare a livello dati ---
# Tutte le tabelle tranne quelle di log e monitoraggio
CONFIG_TABLES=(
    "_osa_mai_controllati"
    "comuni2asl"
    "cu_diff_programmati_eseguiti"
    "cu_eseguiti"
    "dpat_piani_attivita"
    "intent_examples"
    "intents"
    "masterlist"
    "ocse_isp_semp"
    "personale"
    "piani_monitoraggio"
    # Escluse: chat_log (log)
)

# --- Colonne di ordinamento per tabella ---
declare -A TABLE_ORDER_BY=(
    ["_osa_mai_controllati"]="id"
    ["comuni2asl"]="id"
    ["cu_diff_programmati_eseguiti"]="id"
    ["cu_eseguiti"]="id"
    ["dpat_piani_attivita"]="id"
    ["intent_examples"]="id"
    ["intents"]="intent"
    ["masterlist"]="id"
    ["ocse_isp_semp"]="id"
    ["personale"]="id"
    ["piani_monitoraggio"]="id"
)

# --- Colonne da escludere dal confronto dati (timestamp di sistema) ---
declare -A TABLE_EXCLUDE_COLS=(
    ["intents"]="updated_at"
    ["intent_examples"]="created_at"
)

# --- Directory output ---
OUTPUT_DIR="/tmp/db_compare_$(date +%Y%m%d_%H%M%S)"

# ==============================================================================
# FINE CONFIGURAZIONE
# ==============================================================================

# Colori output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Contatori differenze
DDL_DIFFS=0
DATA_DIFFS=0

# ------------------------------------------------------------------------------
# Funzioni utilita'
# ------------------------------------------------------------------------------

log_info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_title() { echo -e "\n${BOLD}=== $* ===${NC}"; }

usage() {
    echo "Uso: $0 [opzioni]"
    echo ""
    echo "Opzioni:"
    echo "  --ddl-only         Solo confronto schema DDL"
    echo "  --data-only        Solo confronto dati tabelle configurazione"
    echo "  --table NOME       Confronta dati di una sola tabella"
    echo "  --output DIR       Directory output (default: /tmp/db_compare_...)"
    echo "  --no-color         Disabilita colori output"
    echo "  --help             Mostra questo messaggio"
    exit 0
}

# Costruisce il comando SSH
ssh_cmd() {
    local ssh="ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new"
    ssh+=" -p ${REMOTE_SSH_PORT}"
    if [[ -n "${REMOTE_SSH_KEY:-}" ]]; then
        ssh+=" -i ${REMOTE_SSH_KEY}"
    fi
    ssh+=" ${REMOTE_SSH_USER}@${REMOTE_SSH_HOST}"
    echo "$ssh"
}

# Esegue psql locale
local_psql() {
    PGPASSWORD="${LOCAL_PASSWORD:-}" psql \
        -h "$LOCAL_HOST" -p "$LOCAL_PORT" -U "$LOCAL_USER" -d "$LOCAL_DB" \
        --no-psqlrc -q -t -A "$@"
}

# Esegue psql remoto via SSH
remote_psql() {
    $(ssh_cmd) "PGPASSWORD='${REMOTE_PASSWORD:-}' psql \
        -h '$REMOTE_HOST' -p '$REMOTE_PORT' -U '$REMOTE_USER' -d '$REMOTE_DB' \
        --no-psqlrc -q -t -A $*"
}

# Esegue pg_dump locale (solo schema)
local_pg_dump() {
    PGPASSWORD="${LOCAL_PASSWORD:-}" pg_dump \
        -h "$LOCAL_HOST" -p "$LOCAL_PORT" -U "$LOCAL_USER" -d "$LOCAL_DB" \
        --schema-only --no-owner --no-privileges --no-comments \
        --schema="$LOCAL_SCHEMA" \
        "$@"
}

# Esegue pg_dump remoto via SSH (solo schema)
remote_pg_dump() {
    $(ssh_cmd) "PGPASSWORD='${REMOTE_PASSWORD:-}' pg_dump \
        -h '$REMOTE_HOST' -p '$REMOTE_PORT' -U '$REMOTE_USER' -d '$REMOTE_DB' \
        --schema-only --no-owner --no-privileges --no-comments \
        --schema='$REMOTE_SCHEMA' \
        $*"
}

# Verifica connettivita'
check_connections() {
    log_title "Verifica connessioni"

    log_info "Test connessione database locale..."
    if local_psql -c "SELECT 1;" > /dev/null 2>&1; then
        local ver
        ver=$(local_psql -c "SELECT version();" 2>/dev/null | head -1)
        log_ok "Locale OK - ${ver:0:60}"
    else
        log_error "Impossibile connettersi al database locale"
        log_error "Verificare: host=$LOCAL_HOST port=$LOCAL_PORT db=$LOCAL_DB user=$LOCAL_USER"
        exit 1
    fi

    log_info "Test connessione database remoto via SSH..."
    if remote_psql "-c 'SELECT 1;'" > /dev/null 2>&1; then
        local ver
        ver=$(remote_psql "-c 'SELECT version();'" 2>/dev/null | head -1)
        log_ok "Remoto OK - ${ver:0:60}"
    else
        log_error "Impossibile connettersi al database remoto"
        log_error "Verificare SSH: ${REMOTE_SSH_USER}@${REMOTE_SSH_HOST}:${REMOTE_SSH_PORT}"
        log_error "Verificare DB:  host=$REMOTE_HOST port=$REMOTE_PORT db=$REMOTE_DB user=$REMOTE_USER"
        exit 1
    fi
}

# ------------------------------------------------------------------------------
# Confronto DDL (schema)
# ------------------------------------------------------------------------------

normalize_ddl() {
    # Rimuove righe variabili (commenti con timestamp, righe vuote multiple)
    # e ordina le definizioni per confronto deterministico
    sed -E \
        -e '/^--/d' \
        -e '/^SET /d' \
        -e '/^SELECT pg_catalog/d' \
        -e '/^\s*$/d' \
    | sort
}

compare_ddl() {
    log_title "Confronto DDL (schema completo)"

    local local_ddl="${OUTPUT_DIR}/ddl_local.sql"
    local remote_ddl="${OUTPUT_DIR}/ddl_remote.sql"
    local diff_file="${OUTPUT_DIR}/ddl_diff.txt"

    log_info "Dump DDL locale..."
    local_pg_dump | normalize_ddl > "$local_ddl"

    log_info "Dump DDL remoto..."
    remote_pg_dump | normalize_ddl > "$remote_ddl"

    log_info "Confronto..."
    if diff -u "$local_ddl" "$remote_ddl" > "$diff_file" 2>&1; then
        log_ok "Schema DDL identici"
        rm -f "$diff_file"
    else
        DDL_DIFFS=1
        local adds dels
        adds=$(grep -c '^+[^+]' "$diff_file" 2>/dev/null || true)
        dels=$(grep -c '^-[^-]' "$diff_file" 2>/dev/null || true)
        log_warn "Differenze trovate: +${adds} righe / -${dels} righe"
        log_info "Dettagli in: ${diff_file}"
    fi

    # Confronto dettagliato per oggetto
    compare_ddl_objects
}

compare_ddl_objects() {
    log_info "Confronto per tipo di oggetto..."

    local local_tables remote_tables
    local_tables=$(local_psql -c "
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = '$LOCAL_SCHEMA' AND table_type = 'BASE TABLE'
        ORDER BY table_name;")
    remote_tables=$(remote_psql "-c \"
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = '$REMOTE_SCHEMA' AND table_type = 'BASE TABLE'
        ORDER BY table_name;\"")

    # Tabelle presenti solo in locale
    local only_local
    only_local=$(comm -23 <(echo "$local_tables") <(echo "$remote_tables") || true)
    if [[ -n "$only_local" ]]; then
        DDL_DIFFS=1
        log_warn "Tabelle solo in LOCALE:"
        echo "$only_local" | sed 's/^/    /'
    fi

    # Tabelle presenti solo in remoto
    local only_remote
    only_remote=$(comm -13 <(echo "$local_tables") <(echo "$remote_tables") || true)
    if [[ -n "$only_remote" ]]; then
        DDL_DIFFS=1
        log_warn "Tabelle solo in REMOTO:"
        echo "$only_remote" | sed 's/^/    /'
    fi

    # Per ogni tabella in comune, confronta colonne
    local common_tables
    common_tables=$(comm -12 <(echo "$local_tables") <(echo "$remote_tables") || true)

    local col_diff_file="${OUTPUT_DIR}/ddl_columns_diff.txt"
    > "$col_diff_file"

    while IFS= read -r table; do
        [[ -z "$table" ]] && continue

        local local_cols remote_cols
        local_cols=$(local_psql -c "
            SELECT column_name || '|' || data_type || '|' || coalesce(character_maximum_length::text,'') || '|' || is_nullable || '|' || coalesce(column_default,'')
            FROM information_schema.columns
            WHERE table_schema = '$LOCAL_SCHEMA' AND table_name = '$table'
            ORDER BY ordinal_position;")
        remote_cols=$(remote_psql "-c \"
            SELECT column_name || '|' || data_type || '|' || coalesce(character_maximum_length::text,'') || '|' || is_nullable || '|' || coalesce(column_default,'')
            FROM information_schema.columns
            WHERE table_schema = '$REMOTE_SCHEMA' AND table_name = '$table'
            ORDER BY ordinal_position;\"")

        if [[ "$local_cols" != "$remote_cols" ]]; then
            DDL_DIFFS=1
            echo "--- Tabella: $table ---" >> "$col_diff_file"
            diff -u \
                <(echo "$local_cols" | sed 's/^/  /') \
                <(echo "$remote_cols" | sed 's/^/  /') \
                >> "$col_diff_file" 2>&1 || true
            echo "" >> "$col_diff_file"
            log_warn "Colonne diverse: ${table}"
        fi
    done <<< "$common_tables"

    if [[ -s "$col_diff_file" ]]; then
        log_info "Dettagli colonne in: ${col_diff_file}"
    else
        rm -f "$col_diff_file"
    fi

    # Confronto indici
    compare_indexes

    # Confronto constraint
    compare_constraints
}

compare_indexes() {
    log_info "Confronto indici..."

    local local_idx remote_idx
    local_idx=$(local_psql -c "
        SELECT indexname || '|' || indexdef
        FROM pg_indexes
        WHERE schemaname = '$LOCAL_SCHEMA'
        ORDER BY indexname;")
    remote_idx=$(remote_psql "-c \"
        SELECT indexname || '|' || indexdef
        FROM pg_indexes
        WHERE schemaname = '$REMOTE_SCHEMA'
        ORDER BY indexname;\"")

    local idx_diff="${OUTPUT_DIR}/ddl_indexes_diff.txt"
    if diff -u <(echo "$local_idx") <(echo "$remote_idx") > "$idx_diff" 2>&1; then
        log_ok "Indici identici"
        rm -f "$idx_diff"
    else
        DDL_DIFFS=1
        log_warn "Differenze indici trovate - dettagli in: ${idx_diff}"
    fi
}

compare_constraints() {
    log_info "Confronto vincoli (PK, FK, UNIQUE, CHECK)..."

    local local_con remote_con
    local_con=$(local_psql -c "
        SELECT tc.table_name || '|' || tc.constraint_name || '|' || tc.constraint_type || '|' ||
               coalesce(string_agg(kcu.column_name, ',' ORDER BY kcu.ordinal_position), '')
        FROM information_schema.table_constraints tc
        LEFT JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        WHERE tc.table_schema = '$LOCAL_SCHEMA'
        GROUP BY tc.table_name, tc.constraint_name, tc.constraint_type
        ORDER BY tc.table_name, tc.constraint_name;")
    remote_con=$(remote_psql "-c \"
        SELECT tc.table_name || '|' || tc.constraint_name || '|' || tc.constraint_type || '|' ||
               coalesce(string_agg(kcu.column_name, ',' ORDER BY kcu.ordinal_position), '')
        FROM information_schema.table_constraints tc
        LEFT JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        WHERE tc.table_schema = '$REMOTE_SCHEMA'
        GROUP BY tc.table_name, tc.constraint_name, tc.constraint_type
        ORDER BY tc.table_name, tc.constraint_name;\"")

    local con_diff="${OUTPUT_DIR}/ddl_constraints_diff.txt"
    if diff -u <(echo "$local_con") <(echo "$remote_con") > "$con_diff" 2>&1; then
        log_ok "Vincoli identici"
        rm -f "$con_diff"
    else
        DDL_DIFFS=1
        log_warn "Differenze vincoli trovate - dettagli in: ${con_diff}"
    fi
}

# ------------------------------------------------------------------------------
# Confronto DATI (tabelle di configurazione)
# ------------------------------------------------------------------------------

get_columns_for_table() {
    local table="$1"
    local source="$2"  # "local" o "remote"
    local exclude="${TABLE_EXCLUDE_COLS[$table]:-}"

    local where_exclude=""
    if [[ -n "$exclude" ]]; then
        # Costruisce clausola NOT IN per escludere colonne
        local in_list
        in_list=$(echo "$exclude" | sed "s/,/','/g" | sed "s/^/'/;s/$/'/")
        where_exclude="AND column_name NOT IN (${in_list})"
    fi

    local query="SELECT string_agg(column_name, ',' ORDER BY ordinal_position)
        FROM information_schema.columns
        WHERE table_schema = '${LOCAL_SCHEMA}' AND table_name = '${table}'
        ${where_exclude};"

    if [[ "$source" == "local" ]]; then
        local_psql -c "$query"
    else
        remote_psql "-c \"$(echo "$query" | sed "s/$LOCAL_SCHEMA/$REMOTE_SCHEMA/")\""
    fi
}

compare_table_data() {
    local table="$1"

    log_info "Confronto dati: ${table}"

    # Verifica esistenza tabella su entrambi i lati
    local local_exists remote_exists
    local_exists=$(local_psql -c "
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema = '$LOCAL_SCHEMA' AND table_name = '$table';")
    remote_exists=$(remote_psql "-c \"
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema = '$REMOTE_SCHEMA' AND table_name = '$table';\"")

    if [[ "$local_exists" -eq 0 ]]; then
        log_warn "  Tabella '$table' non esiste in LOCALE - skip"
        DATA_DIFFS=1
        return
    fi
    if [[ "$remote_exists" -eq 0 ]]; then
        log_warn "  Tabella '$table' non esiste in REMOTO - skip"
        DATA_DIFFS=1
        return
    fi

    # Determina colonne (escludendo quelle configurate)
    local columns
    columns=$(get_columns_for_table "$table" "local")

    # Determina ORDER BY
    local order_by="${TABLE_ORDER_BY[$table]:-1}"

    # Dump dati locale
    local local_data="${OUTPUT_DIR}/data_local_${table}.csv"
    local_psql -c "COPY (
        SELECT ${columns} FROM ${LOCAL_SCHEMA}.${table} ORDER BY ${order_by}
    ) TO STDOUT WITH CSV HEADER;" > "$local_data"

    # Dump dati remoto
    local remote_data="${OUTPUT_DIR}/data_remote_${table}.csv"
    remote_psql "-c \"COPY (
        SELECT ${columns} FROM ${REMOTE_SCHEMA}.${table} ORDER BY ${order_by}
    ) TO STDOUT WITH CSV HEADER;\"" > "$remote_data"

    # Confronto
    local diff_file="${OUTPUT_DIR}/data_diff_${table}.txt"
    if diff -u \
        --label "LOCALE: ${table}" "$local_data" \
        --label "REMOTO: ${table}" "$remote_data" \
        > "$diff_file" 2>&1; then
        local count
        count=$(wc -l < "$local_data")
        log_ok "  Dati identici ($(( count - 1 )) righe)"
        rm -f "$diff_file"
        # Rimuove dump se identici
        rm -f "$local_data" "$remote_data"
    else
        DATA_DIFFS=1
        local adds dels
        adds=$(grep -c '^+[^+]' "$diff_file" 2>/dev/null || true)
        dels=$(grep -c '^-[^-]' "$diff_file" 2>/dev/null || true)
        log_warn "  Differenze: +${adds} / -${dels} righe"
        log_info "  Diff:   ${diff_file}"
        log_info "  Locale: ${local_data}"
        log_info "  Remoto: ${remote_data}"
    fi
}

compare_data() {
    log_title "Confronto dati tabelle di configurazione"

    if [[ ${#CONFIG_TABLES[@]} -eq 0 ]]; then
        log_warn "Nessuna tabella di configurazione definita in CONFIG_TABLES"
        return
    fi

    log_info "Tabelle da confrontare: ${CONFIG_TABLES[*]}"
    echo ""

    for table in "${CONFIG_TABLES[@]}"; do
        compare_table_data "$table"
    done
}

# ------------------------------------------------------------------------------
# Report finale
# ------------------------------------------------------------------------------

generate_report() {
    local report="${OUTPUT_DIR}/REPORT.txt"

    {
        echo "=============================================="
        echo "  REPORT CONFRONTO DATABASE"
        echo "  Data: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "=============================================="
        echo ""
        echo "Locale: ${LOCAL_USER}@${LOCAL_HOST}:${LOCAL_PORT}/${LOCAL_DB}"
        echo "Remoto: ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PORT}/${REMOTE_DB}"
        echo "        (via SSH ${REMOTE_SSH_USER}@${REMOTE_SSH_HOST}:${REMOTE_SSH_PORT})"
        echo ""
        echo "----------------------------------------------"
        echo "  RISULTATO"
        echo "----------------------------------------------"

        if [[ $DDL_DIFFS -eq 0 ]] && [[ $DATA_DIFFS -eq 0 ]]; then
            echo "  ESITO: NESSUNA DIFFERENZA"
        else
            [[ $DDL_DIFFS -gt 0 ]] && echo "  DDL:  DIFFERENZE TROVATE (vedere file ddl_*)"
            [[ $DATA_DIFFS -gt 0 ]] && echo "  DATI: DIFFERENZE TROVATE (vedere file data_*)"
        fi

        echo ""
        echo "----------------------------------------------"
        echo "  FILE GENERATI"
        echo "----------------------------------------------"
        ls -1 "$OUTPUT_DIR"/ 2>/dev/null | sed 's/^/  /'
    } > "$report"

    echo ""
    log_title "Report"
    cat "$report"
    echo ""
    log_info "Tutti i file in: ${OUTPUT_DIR}/"
}

# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------

main() {
    local mode="all"
    local single_table=""

    # Parse argomenti
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --ddl-only)   mode="ddl";  shift ;;
            --data-only)  mode="data"; shift ;;
            --table)      mode="single_table"; single_table="$2"; shift 2 ;;
            --output)     OUTPUT_DIR="$2"; shift 2 ;;
            --no-color)   RED=""; GREEN=""; YELLOW=""; BLUE=""; NC=""; BOLD=""; shift ;;
            --help|-h)    usage ;;
            *)            log_error "Opzione sconosciuta: $1"; usage ;;
        esac
    done

    log_title "Confronto database PostgreSQL"
    log_info "Locale: ${LOCAL_USER}@${LOCAL_HOST}:${LOCAL_PORT}/${LOCAL_DB}"
    log_info "Remoto: ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PORT}/${REMOTE_DB} (via SSH)"
    log_info "Output: ${OUTPUT_DIR}"

    mkdir -p "$OUTPUT_DIR"

    # Verifica connessioni
    check_connections

    # Esegui confronti richiesti
    case "$mode" in
        ddl)
            compare_ddl
            ;;
        data)
            compare_data
            ;;
        single_table)
            if [[ -z "$single_table" ]]; then
                log_error "Specificare il nome della tabella con --table NOME"
                exit 1
            fi
            CONFIG_TABLES=("$single_table")
            compare_data
            ;;
        all)
            compare_ddl
            compare_data
            ;;
    esac

    # Report
    generate_report

    # Exit code
    if [[ $DDL_DIFFS -gt 0 ]] || [[ $DATA_DIFFS -gt 0 ]]; then
        exit 1
    fi
    exit 0
}

main "$@"
