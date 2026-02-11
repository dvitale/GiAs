# Fix Timeout Test con Ollama Remoto

## Problema Identificato

I test in `test_server.py` fallivano quando Ollama era configurato su un host remoto (es. `http://paolonb:11434`) a causa di **timeout insufficienti** che non consideravano la latenza di rete.

### Catena di Timeout Originale

```
Test (30s cached / 120s uncached)
  ↓
Backend API Server
  ↓
LLM Client (60s timeout da config.json)
  ↓
Ollama Remoto (paolonb:11434)
  ↓
Latenza rete + Inferenza LLM
```

**Problema**: Con Ollama remoto, la latenza di rete si somma al tempo di inferenza. Se una richiesta impiega 50s, il test con timeout di 30s fallisce prematuramente.

### Configurazione Ollama nel Config

```json
{
  "llm_backend": {
    "ollama": {
      "host": "http://paolonb:11434",
      "timeout_seconds": 60
    }
  }
}
```

## Soluzione Implementata

### Modifiche a `test_server.py`

1. **Rilevamento automatico Ollama remoto** (righe 83-118):
   ```python
   def is_ollama_remote() -> bool:
       """Verifica se Ollama è configurato come remoto (non localhost)"""
       # Legge config.json e verifica se host != localhost/127.0.0.1
   ```

2. **Timeout dinamici** (righe 120-123):
   ```python
   IS_OLLAMA_REMOTE = is_ollama_remote()
   TIMEOUT_CACHED = 90 if IS_OLLAMA_REMOTE else 30      # 30s → 90s per remoto
   TIMEOUT_UNCACHED = 180 if IS_OLLAMA_REMOTE else 120  # 120s → 180s per remoto
   ```

3. **Log della configurazione** (riga 337-358):
   - Mostra all'avvio se Ollama è remoto
   - Mostra i timeout applicati
   - Mostra l'host Ollama configurato

### Timeout Adattati

| Scenario | CACHED (prima) | CACHED (dopo) | UNCACHED (prima) | UNCACHED (dopo) |
|----------|----------------|---------------|------------------|-----------------|
| **Ollama locale** | 30s | 30s | 120s | 120s |
| **Ollama remoto** | 30s | **90s** (+200%) | 120s | **180s** (+50%) |

## Test della Soluzione

### 1. Verifica rilevamento configurazione

```bash
cd /opt/lang-env/GiAs-llm/tests
python3 -c "
from test_server import is_ollama_remote, TIMEOUT_CACHED, TIMEOUT_UNCACHED, IS_OLLAMA_REMOTE
print(f'Ollama remoto: {IS_OLLAMA_REMOTE}')
print(f'Timeout CACHED: {TIMEOUT_CACHED}s')
print(f'Timeout UNCACHED: {TIMEOUT_UNCACHED}s')
"
```

**Output atteso con config corrente (paolonb)**:
```
Ollama remoto: True
Timeout CACHED: 90s
Timeout UNCACHED: 180s
```

### 2. Esegui test suite completa

```bash
cd /opt/lang-env/GiAs-llm
scripts/server.sh test
```

All'avvio dovresti vedere:
```
======================================================================
⏱️  Configurazione Timeout Test
======================================================================
   Ollama remoto rilevato: SÌ
   Host Ollama: http://paolonb:11434
   Timeout CACHED: 90s (richieste veloci)
   Timeout UNCACHED: 180s (richieste ML/predictor)
======================================================================
```

### 3. Test rapido con quick mode

```bash
cd /opt/lang-env/GiAs-llm/tests
python3 test_server.py --quick
```

## Override Manuale Timeout

Se anche i timeout aumentati non sono sufficienti (es. rete molto lenta), puoi forzarli via variabili d'ambiente:

```bash
# Modifica temporanea per test singolo
cd /opt/lang-env/GiAs-llm/tests
python3 -c "
import test_server
test_server.TIMEOUT_CACHED = 120
test_server.TIMEOUT_UNCACHED = 240
" && python3 test_server.py --quick
```

Oppure modifica direttamente il file:
```python
# Riga 120-123 in test_server.py
TIMEOUT_CACHED = 120   # Forza 120s
TIMEOUT_UNCACHED = 300 # Forza 5 minuti
```

## Configurazione Ollama Host

Il rilevamento verifica:

1. **Variabile d'ambiente** `OLLAMA_HOST` (priorità massima)
2. **config.json** → `llm_backend.ollama.host`
3. **Fallback** a `localhost`

Hostname considerati **locali** (non attivano timeout aumentati):
- `localhost`
- `127.0.0.1`
- `0.0.0.0`
- `::1` (IPv6 localhost)

Qualsiasi altro hostname/IP attiva i timeout aumentati.

## Cambiare Host Ollama

### Via Environment Variable (temporaneo)

```bash
export OLLAMA_HOST=http://192.168.1.100:11434
cd /opt/lang-env/GiAs-llm
scripts/server.sh restart
```

### Via Config File (permanente)

Modifica `GiAs-llm/configs/config.json`:

```json
{
  "llm_backend": {
    "ollama": {
      "host": "http://192.168.1.100:11434",  // ← Cambia qui
      "timeout_seconds": 60
    }
  }
}
```

Poi riavvia:
```bash
cd /opt/lang-env/GiAs-llm
scripts/server.sh restart
```

## Verifica Fix Applicato

```bash
cd /opt/lang-env/GiAs-llm/tests

# Verifica presenza funzione is_ollama_remote
grep -A5 "def is_ollama_remote" test_server.py

# Verifica timeout dinamici
grep "TIMEOUT_CACHED = " test_server.py
# Output atteso: TIMEOUT_CACHED = 90 if IS_OLLAMA_REMOTE else 30

# Verifica log configurazione
grep -A10 "Log configurazione timeout" test_server.py
```

## Rollback (se necessario)

Se le modifiche causano problemi, puoi ripristinare il file originale:

```bash
cd /opt/lang-env/GiAs-llm/tests
git checkout test_server.py
```

Oppure forza timeout fissi nel file:

```python
# Sostituisci righe 120-123 con:
TIMEOUT_CACHED = 30
TIMEOUT_UNCACHED = 120
IS_OLLAMA_REMOTE = False  # Disabilita rilevamento
```

## Test Specifici che Beneficiano del Fix

Questi test sono quelli più critici con Ollama remoto:

1. **test_intent_classification()** - Sezione 2
   - 25-30 query LLM in serie
   - Usa `TIMEOUT_CACHED` per ogni richiesta
   - **Falliva** se anche una singola richiesta superava 30s

2. **test_clarification_rules()** - Sezione 12
   - ~15 chiamate a `/model/parse`
   - Ogni chiamata fa classification LLM
   - **Falliva** in batch

3. **test_true_intent_classification()** - Sezione 14
   - ~20 query a `/model/parse`
   - Verifica intent reale via LLM
   - **Falliva** dopo poche iterazioni

4. **test_two_phase_flow()** - Sezione 11
   - Query pesanti con `TIMEOUT_UNCACHED` (ML predictor)
   - **Falliva** su stabilimenti ad alto rischio con latenza

## Monitoraggio Latenza Ollama

Per verificare la latenza verso Ollama remoto:

```bash
# Ping semplice
ping paolonb

# Test API Ollama
time curl http://paolonb:11434/api/tags

# Test inferenza veloce
time curl -X POST http://paolonb:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model":"llama3.2:3b","prompt":"test","stream":false}'
```

Se la latenza base è >5s, considera:
- Verificare connessione di rete
- Controllare carico del server Ollama
- Valutare di spostare Ollama in locale per i test

## Riferimenti

- Issue: Test falliscono con Ollama remoto
- File modificato: `GiAs-llm/tests/test_server.py`
- Config: `GiAs-llm/configs/config.json`
- Script server: `GiAs-llm/scripts/server.sh`
- Documentazione LLM client: `GiAs-llm/llm/client.py`

## Changelog

- **2026-02-02**: Fix iniziale con rilevamento automatico e timeout dinamici
  - Aggiunta funzione `is_ollama_remote()`
  - Timeout aumentati: 30s→90s (cached), 120s→180s (uncached)
  - Log configurazione all'avvio test
