#!/bin/bash
clear

set -u

# Carica configurazione remota centralizzata
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/.remote_config"


echo "--------------------------------------------------"
echo "Configurazione Sincronizzazione:"
echo "  Remote Host: $REMOTE_HOST (User: $REMOTE_USER)"
echo "--------------------------------------------------"
sleep 3

ssh $REMOTE_HOST
