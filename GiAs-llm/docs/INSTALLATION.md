# Installazione GiAs-llm su Server Debian

**Versione**: 1.3.0
**Data**: 2025-12-25
**Prerequisiti**: Debian/Ubuntu con Python 3.10+

---

## 📋 Indice

1. [Requisiti di Sistema](#requisiti-di-sistema)
2. [Installazione Base](#installazione-base)
3. [Installazione Ollama](#installazione-ollama)
4. [Setup GiAs-llm](#setup-gias-llm)
5. [Configurazione](#configurazione)
6. [Avvio e Test](#avvio-e-test)
7. [Installazione GChat (Opzionale)](#installazione-gchat-opzionale)
8. [Troubleshooting](#troubleshooting)
9. [Manutenzione](#manutenzione)

---

## 💻 Requisiti di Sistema

### Hardware Minimo

| Componente | Requisito Minimo | Requisito Consigliato |
|------------|------------------|----------------------|
| **CPU** | 2 cores | 4+ cores |
| **RAM** | 4 GB | 8+ GB |
| **Disk** | 10 GB liberi | 20+ GB |
| **Network** | 10 Mbps | 100+ Mbps |

### Software Prerequisiti

- **OS**: Debian 11+ / Ubuntu 20.04+
- **Python**: 3.10+ (RICHIESTO)
- **User**: root o sudo access
- **Internet**: Per download dipendenze

### Porte Utilizzate

| Servizio | Porta | Descrizione |
|----------|-------|-------------|
| **GiAs-llm API** | 5005 | FastAPI server (Rasa-compatible) |
| **Ollama** | 11434 | LLM inference server |
| **GChat** (opzionale) | 8080 | Web UI (Golang) |

---

## 🚀 Installazione Base

### 1. Verifica Risorse Server

**⚠️ IMPORTANTE**: Prima di procedere, verifica la RAM disponibile per scegliere il modello LLM corretto.

```bash
# Verifica RAM totale
free -h

# Output esempio:
#               total        used        free      shared  buff/cache   available
# Mem:           5.8G        1.2G        3.1G         50M        1.5G        4.2G
# Swap:          2.0G          0B        2.0G

# Guarda la colonna 'total' sotto 'Mem:'
```

**Scelta Modello LLM Basata su RAM**:

| RAM Disponibile | Modello Consigliato | RAM Ollama | Performance |
|-----------------|---------------------|------------|-------------|
| **≤ 4 GB** | ❌ Non supportato | - | Sistema troppo limitato |
| **4-6 GB** | `llama3.2:1b` | ~1.5 GB | Sufficiente (accuracy ridotta) |
| **6-8 GB** | `llama3.2:3b` ✅ **CONSIGLIATO** | ~2-2.5 GB | Ottimo bilanciamento |
| **8-12 GB** | `llama3.1:8b` | ~4-5 GB | Massima accuracy |
| **12+ GB** | `llama3.1:8b` | ~4-5 GB | Ideale |

**⚠️ NOTA**: Questa guida usa `llama3.2:3b` come default (ottimale per 6 GB RAM).
Se hai RAM diversa, segui le istruzioni nella sezione [Installazione Ollama](#installazione-ollama).

```bash
# Salva RAM totale per riferimento
RAM_GB=$(free -g | awk '/^Mem:/{print $2}')
echo "RAM disponibile: ${RAM_GB} GB"

# Se < 6 GB, considera modello 1b
# Se >= 8 GB, puoi usare modello 8b
```

### 2. Verifica Python

```bash
# Verifica versione Python (deve essere >= 3.10)
python3 --version
# Output atteso: Python 3.10.x o superiore

# Se Python 3.10 non installato (solo se necessario)
sudo apt update
sudo apt install -y python3.10 python3.10-venv python3.10-dev
```

### 3. Installa Dipendenze Sistema

```bash
# Update package list
sudo apt update

# Installa build tools e dipendenze
sudo apt install -y \
    build-essential \
    curl \
    wget \
    git \
    ca-certificates \
    gnupg \
    lsb-release \
    software-properties-common

# Installa pip per Python 3.10
sudo apt install -y python3-pip

# Verifica pip
pip3 --version
# Output atteso: pip 23.x o superiore
```

### 4. Crea Directory di Lavoro

```bash
# Crea directory principale
sudo mkdir -p /opt/lang-env
sudo chown -R $USER:$USER /opt/lang-env
cd /opt/lang-env
```

---

## 🤖 Installazione Ollama

Ollama è il server LLM locale che esegue LLaMA 3.1 per:
- Intent classification (Router)
- Response generation

### 1. Download e Installazione

```bash
# Download installer ufficiale
curl -fsSL https://ollama.com/install.sh | sh

# Verifica installazione
ollama --version
# Output atteso: ollama version x.x.x
```

### 2. Avvio Servizio Ollama

```bash
# Ollama si avvia automaticamente come servizio systemd
# Verifica status
systemctl status ollama

# Se non attivo, avvia manualmente
sudo systemctl start ollama
sudo systemctl enable ollama  # Avvio automatico al boot
```

### 3. Download Modello LLM (Basato su RAM)

**⚠️ CRITICO**: Scegli il modello in base alla RAM verificata nello [Step 1](#1-verifica-risorse-server).

#### Opzione A: Server con 6-8 GB RAM (CONSIGLIATO)

```bash
# Download llama3.2:3b (2.0 GB) - BILANCIAMENTO OTTIMALE
ollama pull llama3.2:3b

# Verifica modello scaricato
ollama list
# Output atteso:
# NAME              ID              SIZE
# llama3.2:3b       xxx             2.0 GB
```

**Caratteristiche**:
- Size: 2.0 GB
- RAM usage: ~2-2.5 GB
- Accuracy: ~90-92%
- **✅ CONSIGLIATO per server cloud con 6 GB RAM**

#### Opzione B: Server con 4-6 GB RAM (LIMITATO)

```bash
# Download llama3.2:1b (1.3 GB) - ULTRA LEGGERO
ollama pull llama3.2:1b

# Verifica
ollama list
# Output atteso:
# NAME              ID              SIZE
# llama3.2:1b       xxx             1.3 GB
```

**Caratteristiche**:
- Size: 1.3 GB
- RAM usage: ~1.5 GB
- Accuracy: ~85% (ridotta ma accettabile)
- **⚠️ Solo se RAM < 6 GB**

#### Opzione C: Server con 8+ GB RAM (MASSIMA ACCURATEZZA)

```bash
# Download llama3.1:8b (4.7 GB) - MASSIMA PERFORMANCE
ollama pull llama3.1:8b

# Verifica
ollama list
# Output atteso:
# NAME              ID              SIZE
# llama3.1:8b       xxx             4.7 GB
```

**Caratteristiche**:
- Size: 4.7 GB
- RAM usage: ~4-5 GB
- Accuracy: ~95-97%
- **✅ Solo se RAM >= 8 GB**

**Tempo download**: ~5-30 minuti (dipende da connessione e size modello)

### 4. Configura GiAs-llm per Modello Scelto

**⚠️ IMPORTANTE**: Dopo aver scaricato il modello, configura GiAs-llm.

```bash
# Naviga alla directory GiAs-llm (se non già dentro)
cd /opt/lang-env/GiAs-llm

# Modifica llm/client.py per usare il modello scelto
# Opzione A: llama3.2:3b (DEFAULT - già configurato)
# Nessuna modifica necessaria se hai scaricato llama3.2:3b

# Opzione B: Se hai scaricato llama3.2:1b
sed -i 's/model: str = "llama3.2:3b"/model: str = "llama3.2:1b"/' llm/client.py

# Opzione C: Se hai scaricato llama3.1:8b
sed -i 's/model: str = "llama3.2:3b"/model: str = "llama3.1:8b"/' llm/client.py

# Verifica modifica
grep 'def __init__' llm/client.py | grep model
# Output atteso: def __init__(self, model: str = "llama3.2:3b", ...)
```

### 5. Test Ollama

```bash
# Test inference (usa il modello che hai scaricato)
# Se llama3.2:3b:
ollama run llama3.2:3b "Ciao, come stai? Rispondi in italiano"

# Se llama3.2:1b:
# ollama run llama3.2:1b "Ciao, come stai?"

# Se llama3.1:8b:
# ollama run llama3.1:8b "Ciao, come stai?"

# Output atteso: Risposta del modello in italiano
# Premi CTRL+D per uscire

# Test API
curl http://localhost:11434/api/tags
# Output atteso: JSON con lista modelli (deve includere il modello scaricato)
```

### 6. Ottimizza Configurazione Ollama (RACCOMANDATO)

Per ridurre ulteriormente l'uso di RAM:

```bash
# Configura limits Ollama
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/override.conf > /dev/null <<'EOF'
[Service]
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_FLASH_ATTENTION=1"
EOF

# Reload systemd
sudo systemctl daemon-reload

# Restart Ollama
sudo systemctl restart ollama

# Verifica status
systemctl status ollama
```

**Impatto**: -20-30% RAM usage Ollama

**⚠️ IMPORTANTE**: Ollama DEVE essere operativo prima di avviare GiAs-llm

---

## 📦 Setup GiAs-llm

### 1. Clone Repository

```bash
cd /opt/lang-env

# Opzione A: Clone da Git (se disponibile)
# git clone <repository-url> GiAs-llm

# Opzione B: Copia da backup/archivio esistente
# Assumendo che tu abbia un backup .tar.gz
# tar -xzf GiAs-llm-backup-YYYYMMDD-HHMMSS.tar.gz

# Per questa guida, assumiamo il codice già in /opt/lang-env/GiAs-llm
cd GiAs-llm
```

### 2. Crea Virtual Environment

```bash
# Crea venv con Python 3.10
python3 -m venv venv

# Attiva venv
source venv/bin/activate

# Verifica attivazione (dovresti vedere (venv) nel prompt)
which python3
# Output atteso: /opt/lang-env/GiAs-llm/venv/bin/python3
```

**⚠️ IMPORTANTE**: Tutte le operazioni successive vanno fatte con venv attivo

### 3. Upgrade pip

```bash
# Upgrade pip, setuptools, wheel
pip install --upgrade pip setuptools wheel
```

### 4. Installa PyTorch (CPU-only)

```bash
# Installa PyTorch CPU-only (più leggero, no GPU)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Verifica installazione
python3 -c "import torch; print(f'PyTorch {torch.__version__}')"
# Output atteso: PyTorch 2.5.1+cpu
```

**Tempo**: ~5-10 minuti (download ~800 MB)

### 5. Installa Dipendenze Python

```bash
# Installa tutte le dipendenze da requirements.txt
pip install -r requirements.txt

# Output atteso: Successfully installed fastapi uvicorn pandas numpy...
```

**Tempo**: ~10-15 minuti

**Dipendenze principali installate**:
- fastapi, uvicorn (API server)
- pandas, numpy (data processing)
- langgraph, langchain (workflow)
- ollama (LLM client)
- qdrant-client (vector DB)
- sentence-transformers (embeddings)

### 6. Verifica Installazione Dipendenze

```bash
# Check versioni chiave
pip list | grep -E "(fastapi|uvicorn|pandas|langgraph|qdrant|sentence-transformers|torch)"

# Output atteso:
# fastapi              0.115.5
# uvicorn              0.32.1
# pandas               2.2.3
# langgraph            0.2.53
# qdrant-client        1.12.1
# sentence-transformers 3.3.1
# torch                2.5.1+cpu
```

### 7. Verifica Struttura Dataset

```bash
# Verifica presenza file CSV
ls -lh dataset/

# File richiesti:
# - piani_monitoraggio.csv (730 piani)
# - Master list rev 11_filtered.csv (538 record)
# - vw_2025_eseguiti_filtered.csv (61K controlli)
# - osa_mai_controllati_con_linea_852-3_filtered.csv (154K stabilimenti)
# - OCSE_ISP_SEMP_2025_NC_definitivo_filtered.csv (101K non conformità)
# - vw_diff_programmati_eseguiti_2025_filtered.csv (3K diff)
# - personale_filtered.csv (1.8K utenti)
```

**⚠️ CRITICO**: Se mancano CSV, copia da backup o fonte originale

### 8. Indicizza Piani per Semantic Search

```bash
# Esegui script di indicizzazione Qdrant
python3 tools/indexing/build_qdrant_index.py

# Output atteso:
# ======================================================================
# QDRANT INDEXING - Piani di Monitoraggio
# ======================================================================
# 🔄 Caricamento modello embedding...
# ✅ Modello caricato: 384 dimensions
# 🔄 Connessione a Qdrant...
# ✅ Connesso a Qdrant
# 🔄 Creazione collection 'piani_monitoraggio'...
# ✅ Collection creata
# 🔄 Caricamento piani da CSV...
# ✅ Caricati 730 piani
# 🔄 Indicizzazione 730 piani...
#    Indicizzati 50/730 piani...
#    ...
# ✅ Indicizzazione completata!
# 🧪 Test semantic search...
# Query: 'benessere animale negli allevamenti'
# Top 3 risultati:
# 1. B56 - Docenze e attività formative (score: 80%)
# 2. A13 - Piano Nazionale  Benessere Animale (score: 76%)
# 3. b36 - Piano Benessere (score: 72%)
# ======================================================================
# ✅ INDICIZZAZIONE COMPLETATA
# ======================================================================
```

**Tempo**: ~45-60 secondi

**⚠️ IMPORTANTE**: Questo step DEVE completare con successo prima di avviare il server

### 9. Verifica Storage Qdrant

```bash
# Verifica creazione storage Qdrant
ls -lh qdrant_storage/

# Output atteso: directory con ~3.3 MB di file
du -sh qdrant_storage/
# Output atteso: 3.3M qdrant_storage/
```

---

## ⚙️ Configurazione

### 1. Verifica Configurazione LLM

```bash
# Verifica llm/client.py usa Ollama correttamente
grep -A5 "OLLAMA_URL" llm/client.py

# Output atteso: OLLAMA_URL = "http://localhost:11434"
```

### 2. Crea Directory Logs

```bash
# Crea directory per log (se non esiste)
mkdir -p logs
chmod 755 logs
```

### 3. Test Caricamento Dati

```bash
# Test caricamento dataset
python3 -c "
from agents.data import load_data
load_data()
print('✅ Dataset caricati correttamente')
"

# Output atteso:
# ✅ Dataset caricati correttamente
```

**Se ci sono errori**:
- Verifica presenza CSV in `dataset/`
- Verifica permessi lettura: `chmod 644 dataset/*.csv`
- Verifica encoding: devono essere UTF-8

---

## 🎯 Avvio e Test

### 1. Avvio Server (Manuale)

```bash
# Assicurati che venv sia attivo
source venv/bin/activate

# Avvia server FastAPI
python3 -m uvicorn app.api:app --host 0.0.0.0 --port 5005

# Output atteso:
# INFO:     Started server process [xxxxx]
# INFO:     Waiting for application startup.
# INFO:     Application startup complete.
# INFO:     Uvicorn running on http://0.0.0.0:5005 (Press CTRL+C to quit)
```

**Lascia il terminale aperto**, server in esecuzione in foreground

### 2. Test Health Check (Nuovo Terminale)

```bash
# Apri nuovo terminale
curl http://localhost:5005/status

# Output atteso:
# {"status":"ok","version":"1.3.0"}
```

### 3. Test Webhook Base

```bash
# Test query semplice
curl -s -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "test_install",
    "message": "ciao",
    "metadata": {}
  }' | python3 -c "import sys, json; print(json.load(sys.stdin)[0]['text'])"

# Output atteso: Messaggio di saluto in italiano
```

### 4. Test Semantic Search

```bash
# Test query con semantic search
curl -s -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "test_install",
    "message": "quali piani riguardano apicoltura?",
    "metadata": {"asl": "AVELLINO"}
  }' | python3 -c "import sys, json; print(json.load(sys.stdin)[0]['text'])"

# Output atteso: Lista piani rilevanti per apicoltura
```

### 5. Test Suite Completo

```bash
# Torna al terminale con venv attivo
cd /opt/lang-env/GiAs-llm
source venv/bin/activate

# Esegui test suite completo (in altro terminale, con server attivo)
python3 test_all_predefined_questions.py | tee logs/test_installation.log

# Output atteso:
# ======================================================================
# TEST SUITE: Tutte le domande predefinite GChat
# ======================================================================
# ...
# ✅ Tutti i test superati (10/10)!
```

**⚠️ IMPORTANTE**: Se test falliscono, NON procedere, debug prima

### 6. Avvio Server con Script (Produzione)

```bash
# Ferma server manuale (CTRL+C nel terminale con uvicorn)

# Usa script di avvio (background + logging)
./start_server.sh

# Output atteso:
# Server GiAs-llm avviato
# PID: xxxxx
# Logs: /opt/lang-env/GiAs-llm/logs/api-server.log
```

### 7. Verifica Server in Background

```bash
# Check processo
ps aux | grep uvicorn

# Check logs
tail -f logs/api-server.log

# Stop server
./stop_server.sh
```

### 8. Configurazione Systemd (Avvio Automatico)

```bash
# Crea file systemd service
sudo tee /etc/systemd/system/gias-llm.service > /dev/null <<EOF
[Unit]
Description=GiAs-llm API Server
After=network.target ollama.service
Requires=ollama.service

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/lang-env/GiAs-llm
Environment="PATH=/opt/lang-env/GiAs-llm/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/opt/lang-env/GiAs-llm/venv/bin/python3 -m uvicorn app.api:app --host 0.0.0.0 --port 5005
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
sudo systemctl daemon-reload

# Avvia servizio
sudo systemctl start gias-llm

# Verifica status
sudo systemctl status gias-llm

# Abilita avvio automatico
sudo systemctl enable gias-llm
```

**Vantaggi systemd**:
- ✅ Avvio automatico al boot
- ✅ Restart automatico se crash
- ✅ Gestione logs con journalctl

### 9. Verifica Avvio Automatico

```bash
# Riavvia server
sudo reboot

# Dopo reboot, verifica servizi
sudo systemctl status ollama
sudo systemctl status gias-llm

# Test API
curl http://localhost:5005/status
```

---

## 🌐 Installazione GChat (Opzionale)

GChat è l'interfaccia web Golang per interagire con GiAs-llm.

### 1. Installa Go

```bash
# Download Go 1.21+
wget https://go.dev/dl/go1.21.5.linux-amd64.tar.gz

# Estrai
sudo rm -rf /usr/local/go
sudo tar -C /usr/local -xzf go1.21.5.linux-amd64.tar.gz

# Aggiungi a PATH
echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
source ~/.bashrc

# Verifica
go version
# Output atteso: go version go1.21.5 linux/amd64
```

### 2. Setup GChat

```bash
cd /opt/lang-env

# Opzione A: Clone da repository
# git clone <gchat-repo-url> gchat

# Opzione B: Estrai da backup
# tar -xzf gchat-backup-YYYYMMDD-HHMMSS.tar.gz

cd gchat
```

### 3. Verifica Configurazione

```bash
# Verifica config/config.json
cat config/config.json | jq '.rasa.url'

# Output atteso: "http://localhost:5005"

# Se diverso, correggi:
jq '.rasa.url = "http://localhost:5005"' config/config.json > config/config.json.tmp
mv config/config.json.tmp config/config.json
```

**Dipendenza**: `jq` per parsing JSON
```bash
sudo apt install -y jq
```

### 4. Build GChat

```bash
# Build binario
go build -o bin/gchat app/*.go

# Verifica build
ls -lh bin/gchat
# Output atteso: file eseguibile ~10-15 MB
```

### 5. Avvia GChat

```bash
# Avvia server (porta 8080)
./bin/gchat

# Output atteso:
# [GIN-debug] Listening and serving HTTP on localhost:8080
```

### 6. Test GChat Web UI

```bash
# Apri browser
# URL: http://<server-ip>:8080/gias/webchat/

# Parametri query di test:
# http://localhost:8080/gias/webchat/?asl_id=202&user_id=42145&asl_name=AVELLINO
```

### 7. Systemd Service per GChat

```bash
# Crea service file
sudo tee /etc/systemd/system/gchat.service > /dev/null <<EOF
[Unit]
Description=GChat Web Interface
After=network.target gias-llm.service
Requires=gias-llm.service

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/lang-env/gchat
ExecStart=/opt/lang-env/gchat/bin/gchat
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload, start, enable
sudo systemctl daemon-reload
sudo systemctl start gchat
sudo systemctl enable gchat
sudo systemctl status gchat
```

---

## 🔧 Troubleshooting

### Problema 1: "Ollama connection refused"

**Sintomo**:
```
ERROR: Connection refused on http://localhost:11434
```

**Causa**: Ollama non avviato

**Soluzione**:
```bash
# Verifica status Ollama
systemctl status ollama

# Se non attivo
sudo systemctl start ollama

# Verifica API
curl http://localhost:11434/api/tags
```

### Problema 2: "ModuleNotFoundError: No module named 'fastapi'"

**Sintomo**:
```python
ModuleNotFoundError: No module named 'fastapi'
```

**Causa**: Virtual environment non attivato o dipendenze non installate

**Soluzione**:
```bash
# Attiva venv
cd /opt/lang-env/GiAs-llm
source venv/bin/activate

# Reinstalla dipendenze
pip install -r requirements.txt
```

### Problema 3: "Qdrant storage not found"

**Sintomo**:
```
⚠️  Qdrant storage not found: /opt/lang-env/GiAs-llm/qdrant_storage
```

**Causa**: Indicizzazione non eseguita

**Soluzione**:
```bash
cd /opt/lang-env/GiAs-llm
source venv/bin/activate
python3 tools/indexing/build_qdrant_index.py
```

### Problema 4: "Permission denied" sui CSV

**Sintomo**:
```
PermissionError: [Errno 13] Permission denied: 'dataset/piani_monitoraggio.csv'
```

**Causa**: Permessi file sbagliati

**Soluzione**:
```bash
# Fix permessi
cd /opt/lang-env/GiAs-llm
chmod 644 dataset/*.csv
chown -R $USER:$USER dataset/
```

### Problema 5: Port 5005 già in uso

**Sintomo**:
```
ERROR: [Errno 98] Address already in use
```

**Causa**: Processo già in ascolto sulla porta 5005

**Soluzione**:
```bash
# Trova processo
lsof -i:5005

# Kill processo
kill -9 <PID>

# Oppure usa script
./stop_server.sh
```

### Problema 6: Test falliscono (< 10/10)

**Sintomo**: Test suite restituisce < 10/10 passing

**Causa**: Possibili cause multiple

**Diagnosi**:
```bash
# Check logs dettagliati
tail -100 logs/api-server.log

# Check Ollama funzionante
curl -X POST http://localhost:11434/api/chat \
  -d '{"model":"llama3.1:8b","messages":[{"role":"user","content":"test"}]}'

# Check semantic search
python3 -c "
from agents.data_agent import DataRetriever
results = DataRetriever.search_piani_semantic('test', top_k=3)
print(f'Results: {len(results)}')
"
```

### Problema 7: Out of Memory

**Sintomo**: Server crash con "OOM Killed" nei log

**Causa**: RAM insufficiente per Ollama + sentence-transformers

**Soluzione**:
```bash
# Opzione 1: Aggiungi swap
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Rendi permanente
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Opzione 2: Usa modello LLaMA più piccolo (se disponibile)
# ollama pull llama3.1:4b  # Modello più leggero

# Opzione 3: Aggiungi RAM fisica (minimo 8 GB consigliato)
```

---

## 🔄 Manutenzione

### Backup Regolare

```bash
# Script di backup automatico
# Già presente: /opt/lang-env/backup.sh

# Esegui backup manuale
/opt/lang-env/backup.sh GiAs-llm

# Output: backup in /opt/lang-env/backups/
ls -lh /opt/lang-env/backups/

# Backup automatico giornaliero (cron)
sudo crontab -e

# Aggiungi:
# 0 2 * * * /opt/lang-env/backup.sh GiAs-llm >> /var/log/gias-backup.log 2>&1
```

### Aggiornamento Dipendenze

```bash
cd /opt/lang-env/GiAs-llm
source venv/bin/activate

# Update pip
pip install --upgrade pip

# Update requirements
pip install --upgrade -r requirements.txt

# Verifica nuove versioni
pip list --outdated
```

### Re-indicizzazione Qdrant (Dopo Update CSV)

```bash
# Se dataset/piani_monitoraggio.csv modificato
cd /opt/lang-env/GiAs-llm
source venv/bin/activate

# Re-indicizza (sovrascrive collection)
python3 tools/indexing/build_qdrant_index.py

# Restart server per applicare
sudo systemctl restart gias-llm
```

### Pulizia Logs

```bash
# Logs possono crescere, pulisci periodicamente
cd /opt/lang-env/GiAs-llm

# Backup logs vecchi
tar -czf logs/archive-$(date +%Y%m%d).tar.gz logs/*.log

# Pulisci logs correnti
> logs/api-server.log

# Oppure configura logrotate
sudo tee /etc/logrotate.d/gias-llm > /dev/null <<EOF
/opt/lang-env/GiAs-llm/logs/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
EOF
```

### Monitoraggio

```bash
# Check status servizi
systemctl status ollama gias-llm gchat

# Check logs in real-time
journalctl -u gias-llm -f

# Check risorse
htop
# Ollama: ~2-4 GB RAM
# GiAs-llm: ~500 MB - 1 GB RAM

# Check disk usage
df -h /opt/lang-env/
du -sh /opt/lang-env/GiAs-llm/
```

---

## 📊 Riepilogo Installazione

### Checklist Finale

- [ ] Python 3.10+ installato e verificato
- [ ] Ollama installato e servizio attivo
- [ ] Modello llama3.1:8b scaricato
- [ ] Virtual environment creato e attivato
- [ ] PyTorch CPU installato
- [ ] Dipendenze Python installate (`requirements.txt`)
- [ ] Dataset CSV presenti in `dataset/`
- [ ] Qdrant indicizzazione completata (730 piani)
- [ ] Storage `qdrant_storage/` creato (~3.3 MB)
- [ ] Server FastAPI avviato (porta 5005)
- [ ] Test suite 10/10 passing
- [ ] Systemd service configurato e abilitato
- [ ] (Opzionale) GChat installato e configurato
- [ ] Backup script testato

### Comandi di Verifica Rapida

```bash
# Verifica tutto in un colpo
cd /opt/lang-env/GiAs-llm

# 1. Check Python
python3 --version | grep -q "3.1[0-9]" && echo "✅ Python OK" || echo "❌ Python FAIL"

# 2. Check Ollama
systemctl is-active ollama && echo "✅ Ollama OK" || echo "❌ Ollama FAIL"

# 3. Check Ollama model
ollama list | grep -q llama3.1 && echo "✅ LLaMA OK" || echo "❌ LLaMA FAIL"

# 4. Check venv
source venv/bin/activate
python3 -c "import fastapi, uvicorn, pandas, langgraph, qdrant_client" && echo "✅ Dependencies OK" || echo "❌ Dependencies FAIL"

# 5. Check Qdrant
[ -d "qdrant_storage" ] && echo "✅ Qdrant storage OK" || echo "❌ Qdrant storage FAIL"

# 6. Check API
curl -s http://localhost:5005/status | grep -q "ok" && echo "✅ API OK" || echo "❌ API FAIL"

# 7. Check test
python3 test_all_predefined_questions.py 2>&1 | grep -q "10/10" && echo "✅ Tests OK" || echo "❌ Tests FAIL"
```

### Tempi Installazione Stimati

| Fase | Tempo | Note |
|------|-------|------|
| **Dipendenze sistema** | 5-10 min | apt install |
| **Ollama install** | 2-3 min | Script automatico |
| **Download LLaMA 3.1** | 10-30 min | 4.7 GB |
| **Virtual env + pip** | 2 min | Locale |
| **PyTorch CPU** | 5-10 min | 800 MB download |
| **Requirements.txt** | 10-15 min | Multiple packages |
| **Qdrant indexing** | 1 min | 730 piani |
| **Test suite** | 5 min | 10 query |
| **TOTALE** | **40-75 min** | Prima installazione |

**Re-installazioni successive**: ~20-30 min (cache pip, modello già scaricato)

---

## 📚 Riferimenti Aggiuntivi

- **README.md**: Overview generale del progetto
- **SEMANTIC_SEARCH.md**: Guida completa semantic search
- **BUGFIX_REPORT.md**: Problemi risolti e soluzioni
- **INTEGRATION_GCHAT.md**: Integrazione con GChat web UI
- **CLAUDE.md**: Istruzioni per development con Claude Code

---

## 🆘 Support

**Logs primari**:
- `/opt/lang-env/GiAs-llm/logs/api-server.log` (FastAPI)
- `journalctl -u ollama` (Ollama)
- `journalctl -u gias-llm` (Systemd service)

**Comandi debug**:
```bash
# Check completo sistema
systemctl status ollama gias-llm gchat
curl http://localhost:5005/status
curl http://localhost:11434/api/tags
tail -50 logs/api-server.log
```

**Se problemi persistono**:
1. Consulta sezione [Troubleshooting](#troubleshooting)
2. Verifica BUGFIX_REPORT.md per problemi noti
3. Check logs dettagliati con timestamp

---

**Autore**: GiAs-llm Development Team
**Versione documento**: 1.0
**Ultimo aggiornamento**: 2025-12-25
**Licenza**: Uso interno Regione Campania
