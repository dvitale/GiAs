# Soluzione Completa per Test con Ollama Remoto

## Problema Attuale

I test falliscono con Ollama remoto (`http://paolonb:11434`) per due motivi:

### 1. TIMEOUT - Query che richiedono tool pesanti
```
❌ "chi devo controllare per primo" → TIMEOUT
❌ "stabilimenti più rischiosi" → TIMEOUT
❌ "suggerisci controlli" → TIMEOUT
❌ "quali stabilimenti non sono mai stati controllati" → TIMEOUT
```

**Causa**: Questi intent richiedono tool che:
- Interrogano il database PostgreSQL
- Eseguono predizioni ML (risk predictor)
- Generano risposte con LLM
- **Latenza totale**: DB (5-10s) + ML (10-20s) + LLM remoto (20-30s) + rete (5-10s) = **40-70s**

Anche con timeout aumentati (90s/180s), se il server Ollama è occupato, superano il limite.

### 2. INTENT MISMATCH - Classificazione errata
```
❌ "sì" → expected confirm_show_details
❌ "quali stabilimenti controllare" → expected ask_priority_establishment
❌ "piani in ritardo" → expected ask_delayed_plans
❌ "quali piani sono in ritardo" → expected ask_delayed_plans
```

**Causa**:
- LLM remoto classifica diversamente (modello, temperatura, prompt)
- Alcuni intent ambigui non vengono riconosciuti correttamente

## Soluzioni Proposte

### ✅ Soluzione 1: Aumentare Timeout Ulteriormente (Conservativa)

Porta i timeout a livelli sicuri per Ollama remoto:

```python
# test_server.py righe 120-123
IS_OLLAMA_REMOTE = is_ollama_remote()
TIMEOUT_CACHED = 120 if IS_OLLAMA_REMOTE else 30      # 90s → 120s
TIMEOUT_UNCACHED = 300 if IS_OLLAMA_REMOTE else 120   # 180s → 300s (5min)
```

**Pro**:
- Semplice da implementare
- Copre quasi tutti i casi

**Contro**:
- Test molto lenti con Ollama remoto
- Se il server non risponde, aspetta 5 minuti prima di fallire

### ✅ Soluzione 2: Skip Test Pesanti con Ollama Remoto (Pragmatica)

Aggiungi flag per saltare test che richiedono ML/DB quando Ollama è remoto:

```python
def test_ml_predictor(ctx: TestContext):
    """Section 4: ML Predictor."""
    if ctx.quick_mode or IS_OLLAMA_REMOTE:  # ← AGGIUNGI QUI
        log_skip(ctx, "ML Predictor tests skipped (remote Ollama or quick mode)")
        return
    # ... resto del test
```

Applica a:
- `test_ml_predictor()` - Sezione 4
- `test_two_phase_flow()` - Sezione 11 (query pesanti)
- Query che usano `ask_risk_based_priority`, `ask_priority_establishment`, `ask_suggest_controls`

**Pro**:
- Test rapidi anche con Ollama remoto
- Evita timeout su query pesanti

**Contro**:
- Alcuni test non vengono eseguiti
- Copertura ridotta

### ✅ Soluzione 3: Pre-Check Backend Prima dei Test (Robusta)

Aggiungi verifica che backend sia raggiungibile e Ollama sia carico:

```python
def verify_backend_ready(max_wait: int = 30) -> bool:
    """Verifica che backend sia up e Ollama sia pronto"""
    print("Verifica disponibilità backend...")

    for i in range(max_wait):
        try:
            # Check status
            resp = requests.get(STATUS_URL, timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('model_loaded'):
                    print(f"✅ Backend pronto (LLM: {data.get('llm')})")
                    return True
                else:
                    print(f"⏳ Attesa caricamento modello... ({i+1}/{max_wait}s)")
        except:
            print(f"⏳ Attesa backend... ({i+1}/{max_wait}s)")

        time.sleep(1)

    print("❌ Backend non disponibile dopo 30s")
    return False

# In main():
if __name__ == "__main__":
    # ... parsing args ...

    if ctx.auto_start:
        if not is_server_running():
            print("Server non in esecuzione, tentativo di avvio...")
            if not start_server():
                print("❌ Impossibile avviare il server")
                sys.exit(1)

        # NUOVO: Verifica backend pronto
        if not verify_backend_ready():
            print("❌ Backend non pronto per i test")
            sys.exit(1)

    # ... esegui test ...
```

**Pro**:
- Evita di eseguire test se backend non è pronto
- Messaggio chiaro se Ollama è lento o non disponibile

**Contro**:
- Aggiunge tempo di warmup iniziale

### ✅ Soluzione 4: Retry Logic per Timeout (Aggressiva)

Riprova automaticamente query che vanno in timeout:

```python
def query_full_with_retry(message: str, metadata: dict = None,
                          timeout: int = TIMEOUT_CACHED, sender: str = "test",
                          max_retries: int = 2) -> QueryResult:
    """Query con retry automatico in caso di timeout"""

    for attempt in range(max_retries + 1):
        result = query_full(message, metadata, timeout, sender)

        if result.status_code != 0:  # Non è un timeout
            return result

        if attempt < max_retries:
            print(f"⚠️ Timeout, riprovo ({attempt+1}/{max_retries})...")
            time.sleep(2)  # Piccola pausa tra retry

    return result  # Ultimo tentativo fallito
```

**Pro**:
- Gestisce timeout temporanei (Ollama occupato)
- Migliora success rate

**Contro**:
- Test ancora più lenti se falliscono
- Maschera problemi reali

### ✅ Soluzione 5: Modalità "Stub" per Test Rapidi (Fallback)

Usa lo stub LLM quando Ollama remoto è troppo lento:

```bash
# Esegui test in modalità stub (senza chiamare Ollama)
GIAS_USE_STUB_LLM=1 python3 tests/test_server.py --quick
```

Modifica `llm/client.py`:

```python
def __init__(self, model: str = None, use_real_llm: bool = True):
    # Check env var per forzare stub
    if os.environ.get('GIAS_USE_STUB_LLM') == '1':
        use_real_llm = False
        print("⚠️ Modalità STUB attivata (GIAS_USE_STUB_LLM=1)")

    # ... resto del codice ...
```

**Pro**:
- Test ultra-rapidi (nessuna chiamata LLM)
- Utile per test di regressione rapidi

**Contro**:
- Non testa il vero LLM
- Stub potrebbe non riflettere comportamento reale

## 🎯 Soluzione Consigliata (Combinata)

Applica **Soluzione 1 + 2 + 3**:

1. **Aumenta timeout conservativi**:
   ```python
   TIMEOUT_CACHED = 120 if IS_OLLAMA_REMOTE else 30
   TIMEOUT_UNCACHED = 300 if IS_OLLAMA_REMOTE else 120
   ```

2. **Skip test pesanti con `--quick` o Ollama remoto**:
   ```python
   if ctx.quick_mode or (IS_OLLAMA_REMOTE and not ctx.force_all):
       log_skip(ctx, "Skipped (remote Ollama)")
       return
   ```

3. **Verifica backend pronto prima di iniziare**:
   ```python
   if not verify_backend_ready(max_wait=60):
       sys.exit(1)
   ```

Aggiungi flag `--force-all` per eseguire tutti i test anche con Ollama remoto:
```bash
python3 tests/test_server.py --force-all  # Esegue tutto anche se lento
```

## Implementazione Immediata

### Step 1: Aumenta timeout
```bash
cd /opt/lang-env/GiAs-llm/tests
# Già fatto! I timeout sono 90s/180s
```

### Step 2: Verifica backend prima dei test
Esegui manualmente:
```bash
# 1. Verifica backend in esecuzione
curl -s http://localhost:5005/status | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f'✅ Backend UP - {data.get(\"llm\")}')
    print(f'Model loaded: {data.get(\"model_loaded\")}')
except:
    print('❌ Backend DOWN')
    sys.exit(1)
"

# 2. Se DOWN, avvia
if [ $? -ne 0 ]; then
    echo "Avvio backend..."
    GIAS_LLM_MODEL=llama3.2 scripts/server.sh start
    sleep 10
fi

# 3. Esegui test
python3 tests/test_server.py --quick
```

### Step 3: Se ancora timeout, usa timeout più alti

Modifica `test_server.py` righe 120-123:
```python
# Timeout ancora più alti per Ollama remoto
TIMEOUT_CACHED = 150 if IS_OLLAMA_REMOTE else 30      # 2.5 minuti
TIMEOUT_UNCACHED = 360 if IS_OLLAMA_REMOTE else 120   # 6 minuti
```

## Diagnostica Problemi

### 1. Verifica latenza rete verso Ollama

```bash
# Ping
ping -c 5 paolonb

# Latenza API
time curl -s http://paolonb:11434/api/tags > /dev/null
# Dovrebbe essere < 1s
```

### 2. Verifica carico server Ollama

```bash
# Se hai accesso SSH a paolonb
ssh paolonb "ps aux | grep ollama"
ssh paolonb "nvidia-smi"  # Se GPU
```

### 3. Test query singola con timeout lungo

```bash
time curl -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "test_debug",
    "message": "stabilimenti ad alto rischio",
    "metadata": {"asl": "AVELLINO"}
  }' --max-time 300
# Vedi quanto impiega realmente
```

## Quando Usare Quale Modalità

### Ollama Locale (localhost)
```bash
# Test completi, timeout standard
python3 tests/test_server.py
```

### Ollama Remoto Veloce (<2s latenza)
```bash
# Test completi, timeout aumentati (già fatto automaticamente)
python3 tests/test_server.py
```

### Ollama Remoto Lento (>5s latenza)
```bash
# Solo test essenziali
python3 tests/test_server.py --quick
```

### Ollama Non Disponibile
```bash
# Modalità stub
GIAS_USE_STUB_LLM=1 python3 tests/test_server.py --quick
```

## Fix Intent Mismatch

Per i problemi di classificazione:

1. **Verifica temperatura router**:
   ```python
   # orchestrator/router.py
   CLASSIFICATION_TEMPERATURE = 0.0  # Deve essere 0 per determinismo
   ```

2. **Verifica prompt classificazione**:
   ```bash
   # Controlla che il prompt in router.py non sia cambiato
   grep -A20 "CLASSIFICATION_PROMPT" orchestrator/router.py
   ```

3. **Test classificazione singola**:
   ```bash
   curl -X POST http://localhost:5005/model/parse \
     -H "Content-Type: application/json" \
     -d '{"text": "piani in ritardo", "metadata": {}}'
   # Verifica intent restituito
   ```

## Riferimenti

- Timeout fix: `tests/TIMEOUT_FIX_README.md`
- Config: `configs/config.json`
- LLM client: `llm/client.py`
- Router: `orchestrator/router.py`
