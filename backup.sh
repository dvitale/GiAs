#!/bin/bash

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="/opt/lang-env/backups"

echo "=== BACKUP GiAs-llm e GChat ==="
echo "Data: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

mkdir -p "$BACKUP_DIR"

echo "Creazione backup GiAs-llm..."
tar -czf "$BACKUP_DIR/GiAs-llm-backup-$TIMESTAMP.tar.gz" \
    -C /opt/lang-env \
    --exclude='GiAs-llm/__pycache__' \
    --exclude='GiAs-llm/**/__pycache__' \
    --exclude='GiAs-llm/.pytest_cache' \
    --exclude='GiAs-llm/**/*.pyc' \
    --exclude='GiAs-llm/qdrant_storage' \
    --exclude='GiAs-llm/dataset' \
    --exclude='GiAs-llm/*.md' \
    GiAs-llm/

echo "Creazione backup gchat..."
tar -czf "$BACKUP_DIR/gchat-backup-$TIMESTAMP.tar.gz" \
    -C /opt/lang-env \
    --exclude='gchat/bin' \
    --exclude='gchat/doc' \
    --exclude='gchat/log/*.log' \
    --exclude='gchat/*.md' \
    gchat/

echo ""
echo "=== BACKUP COMPLETATO ==="
echo ""
echo "File creati:"
ls -lh "$BACKUP_DIR"/*$TIMESTAMP*.tar.gz
echo ""
echo "Percorso: $BACKUP_DIR/"
