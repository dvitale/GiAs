# Performance Tuning - GiAs-llm

**Problema**: Sistema lento su server Debian cloud (6 GB RAM, 4 CPU)
**Data**: 2025-12-25

---

## 🔍 Diagnosi Lentezza

### 1. Verifica Utilizzo Risorse

```bash
# Installa htop se non presente
sudo apt install -y htop

# Monitor real-time
htop

# Verifica memoria
free -h

# Verifica CPU
top -n 1 | head -20

# Verifica I/O disk
iostat -x 1 5

# Verifica processi più pesanti
ps aux --sort=-%mem | head -10
ps aux --sort=-%cpu | head -10
```

**Cerca**:
- **RAM usage** > 90% → Problema memoria
- **CPU usage** > 80% costante → Problema CPU
- **iowait** > 20% → Problema I/O disk
- **Swap usage** > 0 MB → Sistema sta swappando (MALE)

---

## 🐌 Cause Comuni Lentezza

### Causa 1: Ollama Consuma Troppa RAM

**Problema**: LLaMA 3.1:8b richiede ~4-5 GB RAM solo per il modello

**Diagnosi**:
```bash
# Check memoria usata da Ollama
ps aux | grep ollama
# Guarda colonna %MEM e RSS

# Output tipico:
# ollama  1234  2.0 65.3 4200000 3980000 ?  Ssl  10:00  0:30 /usr/local/bin/ollama serve
#                ^^^^ 65% di 6GB = ~4GB
```

**Soluzione 1: Usa Modello Più Piccolo** (CONSIGLIATO)

```bash
# Ferma server
./stop_server.sh
sudo systemctl stop ollama

# Rimuovi modello 8b
ollama rm llama3.1:8b

# Scarica modello 3b (più piccolo, più veloce)
ollama pull llama3.1:3b

# Oppure usa llama3.2:3b (ancora più recente)
ollama pull llama3.2:3b

# Restart
sudo systemctl start ollama
./start_server.sh
```

**Impatto**:
- RAM: 4-5 GB → 2-3 GB (**-50%**)
- Latency: 2-4s → 1-2s (**-50%**)
- Accuracy: ~95% → ~90% (**-5%**, accettabile)

**Soluzione 2: Configura Ollama per Usare Meno RAM**

```bash
# Crea override systemd
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/override.conf > /dev/null <<EOF
[Service]
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_FLASH_ATTENTION=1"
EOF

# Reload e restart
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

**Impatto**:
- Carica solo 1 modello alla volta (default: 2+)
- Riduce parallelismo (1 richiesta per volta)
- RAM: -20-30%
- Latency: Nessun impatto se query sequenziali

---

### Causa 2: Sentence-Transformers Carica Modello a Ogni Query

**Problema**: Lazy initialization troppo lenta, ricarica modello

**Diagnosi**:
```bash
# Check log API
tail -100 logs/api-server.log | grep "SentenceTransformer"

# Se vedi ripetutamente "Load pretrained SentenceTransformer" → Problema!
```

**Soluzione: Pre-carica al Startup**

```python
# Modifica app/api.py

# Aggiungi dopo imports:
from agents.data_agent import DataRetriever

# Aggiungi startup event:
@app.on_event("startup")
async def startup_event():
    """Pre-carica modelli per evitare latency prima query"""
    import logging
    logger = logging.getLogger(__name__)

    logger.info("🔄 Pre-caricamento Qdrant + embedding model...")
    try:
        DataRetriever._initialize_qdrant()
        logger.info("✅ Qdrant pre-caricato")
    except Exception as e:
        logger.warning(f"⚠️  Qdrant pre-load fallito: {e}")
```

**Applica modifica**:

```bash
cd /opt/lang-env/GiAs-llm
source venv/bin/activate

# Backup file originale
cp app/api.py app/api.py.backup

# Modifica manualmente o usa questo script
cat >> app/api.py.patch <<'EOF'
--- a/app/api.py
+++ b/app/api.py
@@ -10,6 +10,7 @@ from typing import Dict, Any, List, Optional
 from orchestrator.graph import ConversationGraph
 from orchestrator.router import Router
+from agents.data_agent import DataRetriever

 app = FastAPI(
     title="GiAs-llm API",
@@ -17,6 +18,18 @@ app = FastAPI(
     description="LangGraph-based conversational AI per monitoraggio veterinario"
 )

+@app.on_event("startup")
+async def startup_event():
+    """Pre-carica modelli per evitare latency prima query"""
+    import logging
+    logger = logging.getLogger(__name__)
+
+    logger.info("🔄 Pre-caricamento Qdrant + embedding model...")
+    try:
+        DataRetriever._initialize_qdrant()
+        logger.info("✅ Qdrant pre-caricato")
+    except Exception as e:
+        logger.warning(f"⚠️  Qdrant pre-load fallito: {e}")
+
 @app.get("/status")
 async def health_check():
EOF

# Restart server
./stop_server.sh
./start_server.sh

# Verifica log startup
tail -30 logs/api-server.log | grep -E "(Pre-caricamento|Qdrant)"
# Output atteso: "✅ Qdrant pre-caricato"
```

**Impatto**:
- Startup: +10-15s (una tantum)
- Prima query: 13s → 2-3s (**-80%**)
- RAM: +120 MB costante (modello sempre in memoria)

---

### Causa 3: CPU Troppo Lenta per Embeddings

**Problema**: Sentence-transformers usa CPU per calcolare embeddings (384 dims)

**Diagnosi**:
```bash
# Durante query con semantic search, monitor CPU
htop

# Guarda processo Python: se CPU usage > 150-200%, è normale
# Se CPU è vecchia/lenta (< 2 GHz), embedding sarà lento
```

**Soluzione 1: Riduci Dimensioni Embedding** (Modello Più Piccolo)

```python
# Modifica agents/agents/data_agent.py

# Cerca:
cls._embedding_model = SentenceTransformer(
    'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'  # 384 dims
)

# Sostituisci con modello più piccolo:
cls._embedding_model = SentenceTransformer(
    'sentence-transformers/paraphrase-MiniLM-L3-v2'  # 128 dims, 3x più veloce
)
```

**⚠️ IMPORTANTE**: Dopo modifica, **devi re-indicizzare**:

```bash
cd /opt/lang-env/GiAs-llm
source venv/bin/activate

# Backup vecchio storage
mv qdrant_storage qdrant_storage.backup

# Re-indicizza con nuovo modello
python3 tools/indexing/build_qdrant_index.py

# Restart
./stop_server.sh
./start_server.sh
```

**Impatto**:
- Embedding speed: **3x più veloce**
- Query time: 2-3s → 1-1.5s
- Accuracy: ~95% → ~88% (**-7%**, trade-off accettabile)

**Soluzione 2: Cache Embeddings Query Frequenti** (Redis)

```bash
# Installa Redis
sudo apt install -y redis-server

# Verifica Redis attivo
systemctl status redis-server

# Installa client Python
pip install redis
```

```python
# Modifica agents/agents/data_agent.py

import redis
import hashlib
import json

class DataRetriever:
    _redis_client = None

    @classmethod
    def _get_redis(cls):
        if cls._redis_client is None:
            try:
                cls._redis_client = redis.Redis(host='localhost', port=6379, db=0)
                cls._redis_client.ping()
            except:
                cls._redis_client = None
        return cls._redis_client

    @classmethod
    def search_piani_semantic(cls, query: str, top_k: int = 10, score_threshold: float = 0.3):
        # Check cache
        redis_client = cls._get_redis()
        if redis_client:
            cache_key = f"sem:{hashlib.md5(f'{query}_{top_k}_{score_threshold}'.encode()).hexdigest()}"
            cached = redis_client.get(cache_key)
            if cached:
                print(f"✅ Cache hit per '{query}'")
                return json.loads(cached)

        # ... [codice esistente per semantic search]

        # Store in cache (TTL 1h = 3600s)
        if redis_client and matches:
            redis_client.setex(cache_key, 3600, json.dumps(matches))

        return matches
```

**Impatto**:
- Query ripetute: 2-3s → <50ms (**-95%**)
- Cache hit rate tipico: 30-50%
- RAM extra: ~50-100 MB (Redis)

---

### Causa 4: Disk I/O Lento (Storage Qdrant)

**Problema**: Cloud storage lento (network-attached storage)

**Diagnosi**:
```bash
# Test velocità disco
sudo apt install -y fio

# Test read
fio --name=read --rw=read --bs=4k --size=100M --numjobs=1 --runtime=10 --directory=/opt/lang-env/GiAs-llm/qdrant_storage/

# Guarda IOPS e bandwidth
# Se IOPS < 1000 → Disco lento
```

**Soluzione 1: Usa tmpfs per Qdrant** (RAM Disk)

```bash
# Crea mount tmpfs (usa RAM come disco)
sudo mkdir -p /mnt/qdrant-tmpfs
sudo mount -t tmpfs -o size=100M tmpfs /mnt/qdrant-tmpfs

# Copia storage Qdrant
sudo cp -r /opt/lang-env/GiAs-llm/qdrant_storage/* /mnt/qdrant-tmpfs/

# Symlink
cd /opt/lang-env/GiAs-llm
mv qdrant_storage qdrant_storage.backup
ln -s /mnt/qdrant-tmpfs qdrant_storage

# Restart
./stop_server.sh
./start_server.sh
```

**⚠️ ATTENZIONE**: tmpfs è volatile! Ricreare al reboot:

```bash
# Aggiungi a /etc/fstab per persistenza
echo "tmpfs /mnt/qdrant-tmpfs tmpfs size=100M 0 0" | sudo tee -a /etc/fstab

# Script restore al boot
sudo tee /etc/rc.local > /dev/null <<'EOF'
#!/bin/bash
cp -r /opt/lang-env/GiAs-llm/qdrant_storage.backup/* /mnt/qdrant-tmpfs/
exit 0
EOF
sudo chmod +x /etc/rc.local
```

**Impatto**:
- Query time: -20-30% (I/O velocissimo)
- RAM usage: +100 MB (storage in RAM)

**Soluzione 2: Upgrade Storage Tier**

Se su cloud provider (AWS, GCP, Azure):
- Passa da HDD → SSD
- Passa da "standard" → "provisioned IOPS"
- Tipicamente: 3000+ IOPS consigliato

---

### Causa 5: Troppi Background Processes

**Diagnosi**:
```bash
# Lista processi attivi
ps aux | wc -l

# Se > 200 processi, può rallentare
```

**Soluzione**:
```bash
# Disabilita servizi inutili
sudo systemctl disable bluetooth cups
sudo systemctl stop bluetooth cups

# Pulisci cron jobs non necessari
crontab -l
sudo crontab -l
```

---

## ⚡ Ottimizzazioni Consigliate (Priorità)

### Priorità 1: CRITICA (Fare Subito)

#### 1.1. Cambia Modello LLaMA → 3b

```bash
./stop_server.sh
sudo systemctl stop ollama
ollama rm llama3.1:8b
ollama pull llama3.1:3b
sudo systemctl start ollama
./start_server.sh
```

**Impatto**: **-50% RAM, -50% latency**

#### 1.2. Configura Ollama Limits

```bash
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/override.conf > /dev/null <<EOF
[Service]
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_FLASH_ATTENTION=1"
EOF
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

**Impatto**: **-30% RAM Ollama**

### Priorità 2: ALTA (Fare Entro 1 Giorno)

#### 2.1. Pre-carica Qdrant al Startup

Modifica `app/api.py` come mostrato sopra.

**Impatto**: **-80% latency prima query**

#### 2.2. Installa Redis Cache

```bash
sudo apt install -y redis-server
pip install redis
# Modifica data_agent.py per caching
```

**Impatto**: **-95% latency query ripetute**

### Priorità 3: MEDIA (Opzionale)

#### 3.1. Usa Modello Embedding Più Piccolo

Cambia a `paraphrase-MiniLM-L3-v2` (128 dims invece di 384).

**Impatto**: **3x più veloce embedding**

#### 3.2. tmpfs per Qdrant

Solo se disco è il bottleneck (verificare con `iostat`).

**Impatto**: **-20-30% I/O latency**

---

## 📊 Benchmark Attesi

### Prima Ottimizzazioni (Baseline)

| Metrica | Valore |
|---------|--------|
| **RAM totale usata** | 5.5 GB / 6 GB (92%) |
| **Ollama RAM** | 4 GB |
| **GiAs-llm RAM** | 1.2 GB |
| **Prima query** | 13-15s |
| **Query successive** | 3-5s |
| **Query semantic search** | 2-4s |
| **Test suite 10/10** | 45-60s totale |

### Dopo Ottimizzazioni (Target)

| Metrica | Valore | Miglioramento |
|---------|--------|---------------|
| **RAM totale usata** | 3.5 GB / 6 GB (58%) | **-36%** |
| **Ollama RAM** | 2 GB | **-50%** |
| **GiAs-llm RAM** | 1.3 GB | +8% (pre-load) |
| **Prima query** | 2-3s | **-80%** |
| **Query successive** | 1-2s | **-60%** |
| **Query semantic search** | 1-1.5s | **-50%** |
| **Query cached** | <50ms | **-98%** |
| **Test suite 10/10** | 20-30s totale | **-50%** |

---

## 🔧 Script Ottimizzazione Automatica

```bash
#!/bin/bash
# optimize_gias.sh - Script ottimizzazione automatica

set -e

echo "🚀 Ottimizzazione GiAs-llm per Cloud Server"
echo "============================================"

# 1. Stop servizi
echo "⏸️  Stop servizi..."
cd /opt/lang-env/GiAs-llm
./stop_server.sh
sudo systemctl stop ollama

# 2. Cambia modello LLaMA
echo "🔄 Cambio modello LLaMA 8b → 3b..."
ollama rm llama3.1:8b 2>/dev/null || true
ollama pull llama3.1:3b

# 3. Configura Ollama limits
echo "⚙️  Configurazione Ollama..."
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/override.conf > /dev/null <<EOF
[Service]
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_FLASH_ATTENTION=1"
EOF

sudo systemctl daemon-reload

# 4. Installa Redis
echo "💾 Installazione Redis..."
sudo apt update
sudo apt install -y redis-server

# 5. Attiva virtual env
source venv/bin/activate

# 6. Installa redis-py
echo "📦 Installazione redis-py..."
pip install redis

# 7. Backup api.py
echo "💾 Backup app/api.py..."
cp app/api.py app/api.py.backup

# 8. Aggiungi startup event (se non già presente)
if ! grep -q "on_event.*startup" app/api.py; then
    echo "✏️  Aggiunta startup event..."
    # Inserisci dopo imports
    sed -i '/from orchestrator.graph import ConversationGraph/a from agents.data_agent import DataRetriever' app/api.py

    # Inserisci dopo creazione app
    sed -i '/^app = FastAPI(/a\\n@app.on_event("startup")\nasync def startup_event():\n    """Pre-carica modelli"""\n    import logging\n    logger = logging.getLogger(__name__)\n    logger.info("🔄 Pre-caricamento Qdrant...")\n    try:\n        DataRetriever._initialize_qdrant()\n        logger.info("✅ Qdrant pre-caricato")\n    except Exception as e:\n        logger.warning(f"⚠️  Pre-load fallito: {e}")\n' app/api.py
fi

# 9. Restart servizi
echo "🔄 Restart servizi..."
sudo systemctl start ollama
sleep 5
./start_server.sh

echo ""
echo "✅ Ottimizzazione completata!"
echo ""
echo "📊 Verifica con:"
echo "  htop              # Monitor risorse"
echo "  free -h           # Memoria"
echo "  curl http://localhost:5005/status"
echo ""
echo "🧪 Test performance:"
echo "  python3 test_all_predefined_questions.py"
```

**Uso**:
```bash
cd /opt/lang-env/GiAs-llm
chmod +x optimize_gias.sh
./optimize_gias.sh
```

---

## 🎯 Monitoring Performance

### Script Monitor Continuo

```bash
#!/bin/bash
# monitor_performance.sh

while true; do
    clear
    echo "=== GiAs-llm Performance Monitor ==="
    date
    echo ""

    # RAM
    echo "📊 MEMORIA:"
    free -h | grep -E "(Mem|Swap)"
    echo ""

    # Processi top
    echo "🔝 TOP PROCESSI (RAM):"
    ps aux --sort=-%mem | head -6
    echo ""

    # CPU
    echo "⚙️  CPU USAGE:"
    top -bn1 | grep "Cpu(s)" | awk '{print "  User: "$2" | System: "$4" | Idle: "$8}'
    echo ""

    # Disk I/O
    echo "💾 DISK I/O:"
    iostat -x 1 1 | grep -E "(Device|sda|vda|nvme)" | tail -2
    echo ""

    # Network
    echo "🌐 NETWORK:"
    ss -s | head -3
    echo ""

    # Servizi
    echo "🔧 SERVIZI:"
    systemctl is-active ollama gias-llm redis-server | awk '{if($1=="active") print "  ✅ "$1; else print "  ❌ "$1}'

    sleep 5
done
```

**Uso**:
```bash
chmod +x monitor_performance.sh
./monitor_performance.sh
```

---

## 📝 Checklist Ottimizzazione

- [ ] **Cambiato LLaMA 8b → 3b**
- [ ] **Configurato Ollama limits** (NUM_PARALLEL=1, MAX_LOADED_MODELS=1)
- [ ] **Pre-caricamento Qdrant al startup**
- [ ] **Installato Redis**
- [ ] **Implementato caching query** (opzionale)
- [ ] **Verificato RAM usage < 70%**
- [ ] **Verificato query time < 2s**
- [ ] **Test suite 10/10 passa in < 30s**
- [ ] **Monitoring continuo attivo**

---

## 🆘 Se Ancora Lento

### Ultima Risorsa: Disabilita Semantic Search

Se anche dopo ottimizzazioni è troppo lento, disabilita temporaneamente semantic search:

```python
# Modifica tools/search_tools.py

@tool("search_piani")
def search_piani_by_topic(query: str, similarity_threshold: float = 0.4):
    # FORCE fallback to keyword (bypass semantic)
    matches = DataRetriever.search_piani_by_keyword(query, similarity_threshold)
    # ... resto del codice
```

**Impatto**:
- Query time: -70% (no embedding calculation)
- Accuracy: -25% (torna a keyword matching)

**Usa solo se**:
- Server troppo limitato
- Performance critiche
- Temporaneo fino a upgrade hardware

---

## 📈 Upgrade Hardware Consigliato

Se ottimizzazioni non bastano, considera upgrade:

| Componente | Minimo | Consigliato | Optimal |
|------------|--------|-------------|---------|
| **RAM** | 6 GB | **8 GB** | 16 GB |
| **CPU** | 4 cores @ 2 GHz | **4 cores @ 3 GHz** | 8 cores @ 3+ GHz |
| **Storage** | HDD | **SSD (SATA)** | NVMe SSD |
| **IOPS** | 500 | **3000** | 10000+ |

**Cloud pricing tipico**:
- 6 GB RAM, 4 CPU: ~$30-40/mese
- 8 GB RAM, 4 CPU: ~$40-50/mese (+25%)
- 16 GB RAM, 8 CPU: ~$80-100/mese (+150%)

---

**Autore**: GiAs-llm Development Team
**Data**: 2025-12-25
**Versione**: 1.0
