#!/bin/bash
clear

set -u

# Carica configurazione remota centralizzata
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/.remote_config"

# Configurazione percorsi
GIAS_REMOTE_PATH="/opt/lang-env/GiAs-llm/"
GIAS_LOCAL_PATH="/opt/lang-env/GiAs-llm/"

GCHAT_REMOTE_PATH="/opt/lang-env/gchat/"
GCHAT_LOCAL_PATH="/opt/lang-env/gchat/"

echo "--------------------------------------------------"
echo "Configurazione Sincronizzazione:"
echo "  Remote Host: $REMOTE_HOST (User: $REMOTE_USER)"
echo "  GiAs-llm:    $GIAS_LOCAL_PATH <-> $GIAS_REMOTE_PATH"
echo "  gchat:       $GCHAT_LOCAL_PATH <-> $GCHAT_REMOTE_PATH"
echo "--------------------------------------------------"
echo

run_case() {
  local title="$1"
  local suggest_script="$2"
  shift
  shift
  local -a rsync_base=("$@")

  echo "== $title =="
  local out status
  out="$("${rsync_base[@]}" -n --itemize-changes --out-format='__RSYNC__%i %n' 2>&1)"
  status=$?
  if [[ $status -ne 0 ]]; then
    echo "Errore rsync (exit $status):"
    echo "$out"
    echo
    return 0
  fi

  local list
  list="$(printf '%s\n' "$out" | sed -n 's/^__RSYNC__//p' | awk 'substr($0,1,1)!="d"{print substr($0,13)}' | awk '$0!="" && $0!="." && $0!="./" && $0!~ /\/$/')"

  print_box() {
    local -a lines=("$@")
    local width=0
    local line
    for line in "${lines[@]}"; do
      if (( ${#line} > width )); then
        width=${#line}
      fi
    done
    local border="+"
    border+="$(printf '%*s' $((width + 2)) '' | tr ' ' '-')"
    border+="+"
    echo "$border"
    for line in "${lines[@]}"; do
      printf "| %-*s |\n" "$width" "$line"
    done
    echo "$border"
  }

  if [[ -z "$list" ]]; then
    echo "OK: Nessun aggiornamento pendente."
  else
    print_box \
      "ATTENZIONE: File da allineare" \
      "Script: $suggest_script"
    echo "$list"
  fi
  echo -e "==============================\n"
}

run_case "GiAs-llm: locale -> remoto" "aggiorna_verso_remoto_G.sh" \
  rsync -avzu -e ssh \
  --exclude=".*" \
  --exclude=".*/" \
  --exclude="runtime/logs/" \
  --exclude="__*/" \
  --exclude="qdrant*/" \
  --exclude="qdrant*" \
  --include="*/" \
  --include="*.py" \
  --include="*.sh" \
  --include="*.json" \
  --exclude="*" \
  --exclude="__*" \
  "$GIAS_LOCAL_PATH" \
  "$REMOTE_USER@$REMOTE_HOST:$GIAS_REMOTE_PATH"

run_case "GiAs-llm: remoto -> locale" "aggiorna_da_remoto_G.sh" \
  rsync -avzu \
  --exclude=".*" \
  --exclude=".*/" \
  --exclude="runtime/logs/" \
  --exclude="__*/" \
  --exclude="qdrant*/" \
  --exclude="qdrant*" \
  --include="*/" \
  --include="*.py" \
  --include="*.sh" \
  --include="*.json" \
  --include="*.md" \
  --exclude="*" \
  --exclude="__*" \
  "$REMOTE_USER@$REMOTE_HOST:$GIAS_REMOTE_PATH" \
  "$GIAS_LOCAL_PATH"

run_case "gchat: locale -> remoto" "aggiorna_verso_remoto_g.sh" \
  rsync -avzu \
  --exclude=".*" \
  --exclude=".*/" \
  --exclude="runtime/logs/" \
  --exclude="old/" \
  --exclude="bin/" \
  --exclude="log/" \
  --include="*/" \
  --include="*.go" \
  --include="*.html" \
  --include="*.js" \
  --include="*.css" \
  --include="*.sh" \
  --include="*.png" \
  --include="*.jp*" \
  --include="*.json" \
  "$GCHAT_LOCAL_PATH" \
  "$REMOTE_USER@$REMOTE_HOST:$GCHAT_REMOTE_PATH"

run_case "gchat: remoto -> locale" "aggiorna_da_remoto_g.sh" \
  rsync -avzu \
  --exclude=".*" \
  --exclude=".*/" \
  --exclude="runtime/logs/" \
  --exclude="old/" \
  --exclude="bin/" \
  --exclude="log/" \
  --include="*/" \
  --include="*.go" \
  --include="*.html" \
  --include="*.js" \
  --include="*.css" \
  --include="*.sh" \
  --include="*.png" \
  --include="*.jp*" \
  --include="*.json" \
  --include="*.md" \
  "$REMOTE_USER@$REMOTE_HOST:$GCHAT_REMOTE_PATH" \
  "$GCHAT_LOCAL_PATH"

echo -e "\n"
