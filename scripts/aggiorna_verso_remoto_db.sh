#!/usr/bin/env bash
# =============================================================================
# aggiorna_verso_remoto_db.sh
#
# Allinea un database PostgreSQL remoto a partire da uno locale.
# Esegue:
#   1. Backup del DB remoto (salvataggio di sicurezza)
#   2. Dump del DB locale
#   3. Drop + restore sul DB remoto
#
# Uso:
#   ./aggiorna_verso_remoto_db.sh [opzioni]
#   oppure con variabili d'ambiente (vedi sotto)
#
# Opzioni:
#   -h  Mostra questo help
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# COLORI
# -----------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# -----------------------------------------------------------------------------
# CONFIGURAZIONE — Override tramite variabili d'ambiente o modifica diretta
# -----------------------------------------------------------------------------

# DB Locale (sorgente)
LOCAL_HOST="${LOCAL_HOST:-localhost}"
LOCAL_PORT="${LOCAL_PORT:-5432}"
LOCAL_DB="${LOCAL_DB:-gias_db}"
LOCAL_DBUSER="${LOCAL_DBUSER:-gisa_owner}"
LOCAL_PASSWORD="${LOCAL_PASSWORD:-5XRe4g8Q5QSg}"          # lasciare vuoto se si usa .pgpass

# DB Remoto (destinazione)
REMOTE_HOST="${REMOTE_HOST:-}"
REMOTE_PORT="${REMOTE_PORT:-5432}"
REMOTE_DB="${REMOTE_DB:-gias_db}"
REMOTE_DBUSER="${REMOTE_DBUSER:-gisa_owner}"
REMOTE_PASSWORD="${REMOTE_PASSWORD:-5XRe4g8Q5QSg}"        # lasciare vuoto se si usa .pgpass

# Directory dove salvare i backup
BACKUP_DIR="${BACKUP_DIR:-/opt/pg_backups}"

# Numero massimo di backup da conservare (0 = nessun limite)
MAX_BACKUPS="${MAX_BACKUPS:-10}"

# Formato del dump: plain | custom | directory | tar
# "custom" è raccomandato: compresso e usabile con pg_restore
DUMP_FORMAT="${DUMP_FORMAT:-custom}"

# Carica configurazione remota (REMOTE_HOST, ecc.)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "${SCRIPT_DIR}/.remote_config" ]] && source "${SCRIPT_DIR}/.remote_config"

# .remote_config può definire REMOTE_DBUSER (utente DB) separato da REMOTE_USER (utente SSH)
[[ -n "${REMOTE_DBUSER:-}" ]] && REMOTE_USER="$REMOTE_DBUSER"

# -----------------------------------------------------------------------------
# HELP
# -----------------------------------------------------------------------------
usage() {
  grep '^#' "$0" | sed 's/^# \{0,1\}//' | head -30
  echo ""
  echo -e "${BOLD}Variabili d'ambiente disponibili:${RESET}"
  echo "  LOCAL_HOST, LOCAL_PORT, LOCAL_DB, LOCAL_DBUSER, LOCAL_PASSWORD"
  echo "  REMOTE_HOST, REMOTE_PORT, REMOTE_DB, REMOTE_DBUSER, REMOTE_PASSWORD"
  echo "  BACKUP_DIR, MAX_BACKUPS, DUMP_FORMAT"
  exit 0
}

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && usage

# -----------------------------------------------------------------------------
# FUNZIONI DI UTILITÀ
# -----------------------------------------------------------------------------
log()     { echo -e "${CYAN}[INFO]${RESET}  $*" >&2; }
ok()      { echo -e "${GREEN}[OK]${RESET}    $*" >&2; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*" >&2; }
err()     { echo -e "${RED}[ERROR]${RESET} $*" >&2; }
die()     { err "$*"; exit 1; }

timestamp() { date '+%Y%m%d_%H%M%S'; }

# Esporta password come variabile d'ambiente per evitare di passarle su CLI
set_pgpassword_local()  { export PGPASSWORD="${LOCAL_PASSWORD}"; }
set_pgpassword_remote() { export PGPASSWORD="${REMOTE_PASSWORD}"; }
clear_pgpassword()      { unset PGPASSWORD; }

# -----------------------------------------------------------------------------
# VERIFICA PREREQUISITI
# -----------------------------------------------------------------------------
check_prerequisites() {
  log "Verifica prerequisiti..."
  for cmd in pg_dump pg_restore psql; do
    command -v "$cmd" &>/dev/null || die "'$cmd' non trovato. Installare postgresql-client."
  done
  ok "Prerequisiti OK"
}

# -----------------------------------------------------------------------------
# TEST CONNESSIONI
# -----------------------------------------------------------------------------
test_connection() {
  local label="$1" host="$2" port="$3" db="$4" user="$5"
  log "Test connessione $label (${user}@${host}:${port}/${db})..."
  if ! psql \
      --host="$host" \
      --port="$port" \
      --username="$user" \
      --dbname="$db" \
      --no-password \
      --command="SELECT 1;" \
      &>/dev/null; then
    die "Impossibile connettersi a $label (${user}@${host}:${port}/${db})"
  fi
  ok "Connessione $label OK"
}

# -----------------------------------------------------------------------------
# BACKUP DB REMOTO
# -----------------------------------------------------------------------------
backup_remote() {
  local ts; ts=$(timestamp)
  local ext; ext=$([[ "$DUMP_FORMAT" == "plain" ]] && echo "sql" || echo "dump")
  local backup_file="${BACKUP_DIR}/backup_${REMOTE_DB}_${ts}.${ext}"

  mkdir -p "$BACKUP_DIR"

  log "Backup del DB remoto → ${backup_file}"
  set_pgpassword_remote
  pg_dump \
    --host="$REMOTE_HOST" \
    --port="$REMOTE_PORT" \
    --username="$REMOTE_DBUSER" \
    --dbname="$REMOTE_DB" \
    --format="$DUMP_FORMAT" \
    --no-password \
    --file="$backup_file"
  clear_pgpassword

  ok "Backup completato: ${backup_file}"

  # Rotazione backup
  if [[ "$MAX_BACKUPS" -gt 0 ]]; then
    local count
    count=$(ls -1 "${BACKUP_DIR}"/backup_${REMOTE_DB}_*.* 2>/dev/null | wc -l)
    if [[ "$count" -gt "$MAX_BACKUPS" ]]; then
      warn "Trovati $count backup, mantengo solo gli ultimi $MAX_BACKUPS"
      ls -1t "${BACKUP_DIR}"/backup_${REMOTE_DB}_*.* | tail -n +"$((MAX_BACKUPS + 1))" | xargs rm -f
    fi
  fi

  echo "$backup_file"
}

# -----------------------------------------------------------------------------
# DUMP DB LOCALE
# -----------------------------------------------------------------------------
dump_local() {
  local ts; ts=$(timestamp)
  local ext; ext=$([[ "$DUMP_FORMAT" == "plain" ]] && echo "sql" || echo "dump")
  local dump_file="/tmp/pg_sync_local_${LOCAL_DB}_${ts}.${ext}"

  log "Dump del DB locale → ${dump_file}"
  set_pgpassword_local
  pg_dump \
    --host="$LOCAL_HOST" \
    --port="$LOCAL_PORT" \
    --username="$LOCAL_DBUSER" \
    --dbname="$LOCAL_DB" \
    --format="$DUMP_FORMAT" \
    --no-password \
    --file="$dump_file"
  clear_pgpassword

  ok "Dump locale completato: ${dump_file}"
  echo "$dump_file"
}

# -----------------------------------------------------------------------------
# DROP + RESTORE SUL DB REMOTO
# -----------------------------------------------------------------------------
restore_remote() {
  local dump_file="$1"

  log "Drop del DB remoto '${REMOTE_DB}'..."
  set_pgpassword_remote

  # Termina eventuali connessioni attive prima del drop
  psql \
    --host="$REMOTE_HOST" \
    --port="$REMOTE_PORT" \
    --username="$REMOTE_DBUSER" \
    --dbname="postgres" \
    --no-password \
    --command="
      SELECT pg_terminate_backend(pid)
      FROM pg_stat_activity
      WHERE datname = '${REMOTE_DB}' AND pid <> pg_backend_pid();
    " &>/dev/null || true

  psql \
    --host="$REMOTE_HOST" \
    --port="$REMOTE_PORT" \
    --username="$REMOTE_DBUSER" \
    --dbname="postgres" \
    --no-password \
    --command="DROP DATABASE IF EXISTS \"${REMOTE_DB}\";"

  log "Creazione DB remoto '${REMOTE_DB}'..."
  psql \
    --host="$REMOTE_HOST" \
    --port="$REMOTE_PORT" \
    --username="$REMOTE_DBUSER" \
    --dbname="postgres" \
    --no-password \
    --command="CREATE DATABASE \"${REMOTE_DB}\";"

  log "Restore del dump sul DB remoto..."
  if [[ "$DUMP_FORMAT" == "plain" ]]; then
    # Filtra parametri di sessione non supportati da versioni PostgreSQL remote più vecchie
    sed '/SET transaction_timeout/d' "$dump_file" | \
    psql \
      --host="$REMOTE_HOST" \
      --port="$REMOTE_PORT" \
      --username="$REMOTE_DBUSER" \
      --dbname="$REMOTE_DB" \
      --no-password
  else
    # Converti custom dump in plain SQL, filtra parametri incompatibili
    # (es. SET transaction_timeout aggiunto da pg_dump >= 17, non supportato da PG < 17)
    pg_restore --no-owner -f - "$dump_file" | \
      sed '/SET transaction_timeout/d' | \
      psql \
        --host="$REMOTE_HOST" \
        --port="$REMOTE_PORT" \
        --username="$REMOTE_DBUSER" \
        --dbname="$REMOTE_DB" \
        --no-password
  fi

  clear_pgpassword
  ok "Restore completato su ${REMOTE_HOST}:${REMOTE_PORT}/${REMOTE_DB}"
}

# -----------------------------------------------------------------------------
# CLEANUP FILE TEMPORANEI
# -----------------------------------------------------------------------------
cleanup() {
  local dump_file="${1:-}"
  if [[ -n "$dump_file" && -f "$dump_file" ]]; then
    rm -f "$dump_file"
    log "File dump temporaneo rimosso: ${dump_file}"
  fi
}

# -----------------------------------------------------------------------------
# RIEPILOGO
# -----------------------------------------------------------------------------
print_summary() {
  echo ""
  echo -e "${BOLD}============================================================${RESET}"
  echo -e "${BOLD}  RIEPILOGO SYNC${RESET}"
  echo -e "${BOLD}============================================================${RESET}"
  echo -e "  Sorgente  : ${LOCAL_DBUSER}@${LOCAL_HOST}:${LOCAL_PORT}/${LOCAL_DB}"
  echo -e "  Dest.     : ${REMOTE_DBUSER}@${REMOTE_HOST}:${REMOTE_PORT}/${REMOTE_DB}"
  echo -e "  Backup    : ${BACKUP_DIR}/"
  echo -e "  Formato   : ${DUMP_FORMAT}"
  echo -e "${BOLD}============================================================${RESET}"
  echo ""
}

# Conferma interattiva
confirm() {
  echo ""
  warn "⚠️  ATTENZIONE: il DB remoto '${REMOTE_DB}' su '${REMOTE_HOST}' verrà"
  warn "   ELIMINATO e sovrascritto con il contenuto di '${LOCAL_DB}' locale."
  echo ""
  read -r -p "$(echo -e "${BOLD}Procedere? [s/N]: ${RESET}")" answer
  [[ "${answer,,}" == "s" ]] || die "Operazione annullata dall'utente."
}

# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
dump_file=""   # globale: usata dal trap EXIT (che esegue fuori dallo scope di main)

main() {
  echo ""
  echo -e "${BOLD}${CYAN}=== $0 ===${RESET}"
  echo ""

  check_prerequisites
  print_summary

  # Test connessioni
  set_pgpassword_local
  test_connection "LOCALE" "$LOCAL_HOST" "$LOCAL_PORT" "$LOCAL_DB" "$LOCAL_DBUSER"
  clear_pgpassword

  set_pgpassword_remote
  test_connection "REMOTO" "$REMOTE_HOST" "$REMOTE_PORT" "$REMOTE_DB" "$REMOTE_DBUSER"
  clear_pgpassword

  confirm

  # Globale (non local) perché il trap EXIT esegue nello scope globale
  dump_file=""
  trap 'cleanup "$dump_file"' EXIT

  # Backup del remoto
  local backup_file
  backup_file=$(backup_remote)

  # Dump del locale
  dump_file=$(dump_local)

  # Restore sul remoto
  restore_remote "$dump_file"

  echo ""
  ok "✅  Sync completato con successo!"
  echo -e "   Backup di sicurezza: ${YELLOW}${backup_file}${RESET}"
  echo ""
}

main "$@"
