#!/bin/bash

# Carica configurazione remota centralizzata
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/.remote_config"

# Configurazione percorsi
REMOTE_PATH="/opt/lang-env/GiAs-llm/"
LOCAL_PATH="/opt/lang-env/GiAs-llm/"

clear

echo "--------------------------------------------------"
echo "Preparazione aggiornamento verso il server remoto:"
echo "  Remote Host: $REMOTE_HOST (User: $REMOTE_USER)"
echo "  Da:          $LOCAL_PATH"
echo "  A:           $REMOTE_PATH"
echo "  Include:     *.py *.sh *.json"
echo "--------------------------------------------------"
echo

echo "Analisi dei file da aggiornare..."
echo

# Dry-run per mostrare i file coinvolti
RSYNC_BASE='rsync -avzu -e ssh \
    --exclude=".*"\
    --exclude=".*/"\
    --exclude="runtime/logs/"\
    --exclude="__*/"\
    --exclude="qdrant*/"\
    --exclude="qdrant*"\
    --include="*/" \
    --include="*.py" \
    --include="*.sh" \
    --include="*.json" \
    --exclude="*" \
    --exclude="__*"\
    "$LOCAL_PATH" \
    "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH"'
RSYNC_DRY="$RSYNC_BASE -n --itemize-changes --out-format='__RSYNC__%i %n'"
RSYNC_RUN="$RSYNC_BASE"
RSYNC_DRY_OUT=$(eval "$RSYNC_DRY" | sed -n 's/^__RSYNC__//p' | awk 'substr($0,1,1)!="d"{print substr($0,13)}') #| sed '1,/^sending/d'
if [[ -z "$RSYNC_DRY_OUT" ]]; then
    echo "Tutti i file sono gia' aggiornati."
    exit 0
fi
echo "File da aggiornare:"
echo "$RSYNC_DRY_OUT"

echo
echo "Comando che verra' eseguito:"
echo "$RSYNC_RUN"
echo
read -p "Vuoi procedere con l'aggiornamento? (s/n): " conferma

if [[ "$conferma" != "s" && "$conferma" != "S" ]]; then
    echo "Operazione annullata."
    exit 1
fi

echo "Avvio sincronizzazione..."
eval "$RSYNC_RUN"

echo "Sincronizzazione completata."
