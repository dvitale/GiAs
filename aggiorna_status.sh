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

  # Separa file da copiare e file da cancellare
  local raw_list to_copy to_delete
  raw_list="$(printf '%s\n' "$out" | sed -n 's/^__RSYNC__//p')"

  # File da cancellare: iniziano con *deleting
  to_delete="$(printf '%s\n' "$raw_list" | awk '/^\*deleting/{print $2}' | awk '$0!="" && $0!="." && $0!="./" && $0!~ /\/$/')"

  # File da copiare: non directory (primo char != 'd') e non *deleting
  to_copy="$(printf '%s\n' "$raw_list" | awk 'substr($0,1,1)!="d" && !/^\*deleting/{print substr($0,13)}' | awk '$0!="" && $0!="." && $0!="./" && $0!~ /\/$/')"

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

  if [[ -z "$to_copy" && -z "$to_delete" ]]; then
    echo "OK: Nessun aggiornamento pendente."
  else
    print_box \
      "ATTENZIONE: File da allineare" \
      "Script: $suggest_script"

    if [[ -n "$to_copy" ]]; then
      echo -e "\033[32m[COPIA/AGGIORNA]\033[0m"
      echo "$to_copy"
    fi

    if [[ -n "$to_delete" ]]; then
      echo -e "\033[31m[CANCELLA]\033[0m"
      echo "$to_delete"
    fi
  fi
  echo -e "==============================\n"
}

run_case "GiAs-llm: locale -> remoto" "aggiorna_verso_remoto_G.sh" \
  rsync -avzu --delete -e ssh \
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
  --include="*.pdf" \
  --exclude="*" \
  --exclude="__*" \
  "$GIAS_LOCAL_PATH" \
  "$REMOTE_USER@$REMOTE_HOST:$GIAS_REMOTE_PATH"

run_case "GiAs-llm: remoto -> locale" "aggiorna_da_remoto_G.sh" \
  rsync -avzu --delete \
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
  --include="*.pdf" \
  --exclude="*" \
  --exclude="__*" \
  "$REMOTE_USER@$REMOTE_HOST:$GIAS_REMOTE_PATH" \
  "$GIAS_LOCAL_PATH"

run_case "gchat: locale -> remoto" "aggiorna_verso_remoto_g.sh" \
  rsync -avzu --delete \
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
  rsync -avzu --delete \
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
