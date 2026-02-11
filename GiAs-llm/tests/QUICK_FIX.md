# Fix Rapido per Test con Ollama Remoto

## ✅ Cosa è stato fatto

### 1. Timeout aumentati (automatico)
- **CACHED**: 30s → **120s** (per Ollama remoto)
- **UNCACHED**: 120s → **300s** (per Ollama remoto)
- Rilevamento automatico da `configs/config.json`

### 2. Script helper creato
```bash
tests/run_tests_remote.sh
```

Gestisce automaticamente:
- Verifica connessione Ollama remoto
- Verifica backend in esecuzione
- Avvio automatico backend se necessario
- Scelta modalità test (quick/full/verbose)

### 3. Documentazione completa
- `TIMEOUT_FIX_README.md` - Dettagli timeout dinamici
- `REMOTE_OLLAMA_SOLUTION.md` - Soluzioni complete per Ollama remoto
- `QUICK_FIX.md` - Questo file

## 🚀 Come Eseguire i Test ORA

### Opzione 1: Script Helper (CONSIGLIATO)

```bash
cd /opt/lang-env/GiAs-llm
tests/run_tests_remote.sh
```

Lo script:
1. Verifica Ollama remoto (paolonb:11434)
2. Verifica backend in esecuzione
3. Avvia il backend se necessario
4. Chiede quale modalità test usare
5. Esegue i test con timeout corretti

### Opzione 2: Manuale

**Passo 1: Avvia il backend**
```bash
cd /opt/lang-env/GiAs-llm

# Scelta 1: Avvio interattivo (ti chiede quale modello)
scripts/server.sh start

# Scelta 2: Avvio automatico con llama3.2
GIAS_LLM_MODEL=llama3.2 scripts/server.sh start
```

**Passo 2: Verifica backend pronto**
```bash
curl -s http://localhost:5005/status | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'Status: {data.get(\"status\")}')
print(f'LLM: {data.get(\"llm\")}')
print(f'Model loaded: {data.get(\"model_loaded\")}')
"
```

Output atteso:
```
Status: ready
LLM: ollama
Model loaded: True
```

**Passo 3: Esegui test**

```bash
cd /opt/lang-env/GiAs-llm/tests

# Quick mode (consigliato con Ollama remoto)
python3 test_server.py --quick

# Full mode (10-15 min con Ollama remoto)
python3 test_server.py

# Verbose (mostra ogni singolo test)
python3 test_server.py --quick --verbose
```

## 📊 Timeout Applicati

La configurazione attuale rileva automaticamente Ollama remoto:

| Scenario | Host Rilevato | CACHED | UNCACHED |
|----------|---------------|--------|----------|
| **Attuale** | `http://paolonb:11434` (remoto) | **120s** | **300s** |
| Se fosse locale | `localhost` | 30s | 120s |

Verifica:
```bash
cd /opt/lang-env/GiAs-llm/tests
python3 -c "
from test_server import IS_OLLAMA_REMOTE, TIMEOUT_CACHED, TIMEOUT_UNCACHED
print(f'Ollama remoto: {IS_OLLAMA_REMOTE}')
print(f'Timeout CACHED: {TIMEOUT_CACHED}s')
print(f'Timeout UNCACHED: {TIMEOUT_UNCACHED}s')
"
```

## ⚠️ Se i Test Falliscono Ancora

### Caso 1: TIMEOUT su query pesanti

**Problema**: Anche 120s/300s non bastano (server Ollama molto lento o occupato)

**Soluzione**:
```bash
# Usa solo quick mode (salta test pesanti)
python3 tests/test_server.py --quick

# Oppure aumenta ancora i timeout
# Modifica tests/test_server.py righe 120-123:
TIMEOUT_CACHED = 180 if IS_OLLAMA_REMOTE else 30      # 3 minuti
TIMEOUT_UNCACHED = 600 if IS_OLLAMA_REMOTE else 120   # 10 minuti
```

### Caso 2: Intent Mismatch (classificazione errata)

**Problema**: Test come `"piani in ritardo" → expected ask_delayed_plans` falliscono

**Causa**: LLM remoto classifica diversamente

**Verifica**:
```bash
# Test classificazione singola
curl -X POST http://localhost:5005/model/parse \
  -H "Content-Type: application/json" \
  -d '{"text": "piani in ritardo", "metadata": {}}' | python3 -m json.tool

# Controlla campo "intent" → "name"
# Dovrebbe essere "ask_delayed_plans"
```

**Soluzione**:
1. Verifica temperatura sia 0 in `orchestrator/router.py`:
   ```bash
   grep "CLASSIFICATION_TEMPERATURE" orchestrator/router.py
   # Output atteso: CLASSIFICATION_TEMPERATURE = 0.0
   ```

2. Se temperatura è corretta ma classifica male, il modello remoto potrebbe essere diverso:
   ```bash
   # Verifica quale modello è in uso
   curl -s http://localhost:5005/status | python3 -c "
   import sys, json
   data = json.load(sys.stdin)
   print(f'Modello: {data.get(\"llm\")}')
   "

   # Verifica modello su Ollama remoto
   curl -s http://paolonb:11434/api/tags | python3 -c "
   import sys, json
   data = json.load(sys.stdin)
   for m in data.get('models', []):
       print(m['name'])
   "
   ```

3. Se il problema persiste, alcuni test potrebbero essere troppo stringenti per LLM remoto.
   Apri un issue specifico con:
   - Query che fallisce
   - Intent atteso vs ricevuto
   - Modello in uso

### Caso 3: Backend non si avvia

**Problema**: `Backend NON raggiungibile`

**Verifica**:
```bash
# Controlla se processo è attivo
ps aux | grep uvicorn

# Controlla log
tail -50 GiAs-llm/runtime/logs/api-server.log

# Controlla porta in uso
lsof -i :5005
```

**Soluzione**:
```bash
# Stop forzato + riavvio
cd /opt/lang-env/GiAs-llm
scripts/server.sh stop
sleep 2
GIAS_LLM_MODEL=llama3.2 scripts/server.sh start
```

## 📈 Performance Attese

### Ollama Remoto (paolonb) - Quick Mode

| Sezione | Test | Tempo Atteso |
|---------|------|--------------|
| 1. System Status | 1 | < 1s |
| 2. Intent Classification | 8 | 60-120s |
| 3. Performance | 2 | 10-20s |
| 8. REST Endpoints | 6 | 10-15s |
| **Totale Quick** | ~17 test | **2-3 minuti** |

### Ollama Remoto (paolonb) - Full Mode

| Sezione | Test | Tempo Atteso |
|---------|------|--------------|
| Tutti i test | ~150 | **10-15 minuti** |

Se impiega molto di più, probabilmente:
- Server Ollama occupato con altre richieste
- Latenza di rete alta (>100ms)
- Modello non precaricato in memoria

## 🔧 Diagnostica Avanzata

### Test latenza verso Ollama remoto

```bash
# Ping
ping -c 5 paolonb

# Latenza API
time curl -s http://paolonb:11434/api/tags > /dev/null

# Test inferenza semplice
time curl -X POST http://paolonb:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model":"llama3.2:3b","prompt":"test","stream":false}' \
  > /dev/null 2>&1
```

**Latenza attesa**:
- Ping: < 50ms
- API tags: < 500ms
- Inferenza: 2-10s (dipende dal carico)

Se latenza > 10s, contatta admin di paolonb.

### Verifica modello precaricato

```bash
# Il modello deve avere keep_alive=-1 per restare in memoria
curl -X POST http://paolonb:11434/api/generate \
  -d '{"model":"llama3.2:3b","prompt":"ready","keep_alive":-1}' \
  > /dev/null 2>&1

# Verifica che sia carico
curl -s http://paolonb:11434/api/ps | python3 -m json.tool
```

Output dovrebbe mostrare `llama3.2:3b` in memoria.

## 📞 Supporto

Se i problemi persistono:

1. **Raccogli info**:
   ```bash
   cd /opt/lang-env/GiAs-llm/tests
   ./run_tests_remote.sh > test_output.txt 2>&1
   ```

2. **Verifica config**:
   ```bash
   cat configs/config.json | grep -A5 "ollama"
   ```

3. **Salva log backend**:
   ```bash
   tail -200 runtime/logs/api-server.log > backend_log.txt
   ```

4. **Apri issue** con:
   - `test_output.txt`
   - Configurazione Ollama
   - `backend_log.txt`
   - Latenza misurata verso paolonb

## ✅ Checklist Pre-Test

Prima di eseguire i test, verifica:

- [ ] Ollama remoto raggiungibile: `curl http://paolonb:11434/api/tags`
- [ ] Backend in esecuzione: `curl http://localhost:5005/status`
- [ ] Modello caricato: `model_loaded: true` in status
- [ ] Timeout aumentati: `TIMEOUT_CACHED=120s, TIMEOUT_UNCACHED=300s`
- [ ] Latenza < 5s: `time curl http://paolonb:11434/api/tags`

Se tutto OK:
```bash
cd /opt/lang-env/GiAs-llm
tests/run_tests_remote.sh
```

Scegli modalità **Quick** per test rapidi!
