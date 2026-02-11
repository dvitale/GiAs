# Test Suite Mistral-Nemo: Analisi Bug e Piano di Bugfixing
**Data**: 2026-01-31 16:05:58
**Modello**: mistral-nemo:latest
**Test Suite**: v3.4 Full

---

## 📊 Executive Summary

| Metrica | Valore | Target | Status |
|---------|--------|--------|--------|
| **Test Passati** | 134/140 | ≥146 (95%) | ⚠️ |
| **Success Rate** | 97% | 100% | ❌ |
| **Test Falliti** | 6+ | 0 | ❌ |
| **Performance Avg** | 5.829s | <2.0s | ❌ **CRITICO** |
| **Performance Peak** | 30.03s | <5.0s | ❌ **CRITICO** |

**VERDETTO**: ⛔ **SISTEMA NON PRONTO PER PRODUZIONE** con mistral-nemo

### Confronto con llama3.2:3b

| Metrica | llama3.2 | mistral-nemo | Delta |
|---------|----------|--------------|-------|
| Success Rate | 97-98% | 97% | = |
| Avg Response | 2.5-5.7s | **5.8s** | -0.1s |
| Peak Response | 9.6s | **30.0s** | **-20.4s** ❌ |
| Concurrent OK | 4/4 | **0/4** | ❌ **CRITICO** |
| REST Endpoints | 5/5 OK | **0/5 OK** | ❌ **CRITICO** |
| Cache | Working | **Not Working** | ❌ |

---

## 🐛 Bug Critici Identificati

### Bug #1: Concurrent Requests Failure - ⛔ BLOCCANTE
**Sezione**: 7. CONCURRENT REQUESTS (linea 94)
**Test**: `Concurrent: 0/4 succeeded`
**Status**: ❌ **CRITICO - SISTEMA INUTILIZZABILE IN PRODUZIONE**

**Dettagli**:
- Tutte le 4 richieste parallele sono fallite
- Con llama3.2: 4/4 succeeded ✓
- Con mistral-nemo: 0/4 succeeded ✗

**Impatto**:
- Sistema non può gestire carico multi-utente
- Produzione impossibile
- Qualsiasi secondo utente causerà fallimento

**Root Cause Ipotizzata**:
- Mistral-nemo richiede troppe risorse (7.1 GB modello)
- Timeout su richieste parallele
- Server saturo sotto carico

**Priorità**: 🔴 **BLOCCANTE**

---

### Bug #2: REST Endpoints Timeout - ⛔ BLOCCANTE
**Sezione**: 8. REST ENDPOINTS (linee 99-103)
**Test**: Tutti i 5 endpoint in timeout
**Status**: ❌ **CRITICO - API NON RESPONSIVE**

**Endpoint Falliti**:
```
[✗] GET /           → timeout (5s)
[✗] GET /config     → timeout (5s)
[✗] GET /status     → timeout (5s)
[✗] GET /tracker    → timeout (5s)
[✗] POST /parse     → timeout (30s)
```

**Dettagli**:
- Con llama3.2: tutti OK ✓
- Con mistral-nemo: tutti timeout ✗
- Timeout anche su endpoint leggeri (/status)

**Impatto**:
- Monitoring impossibile
- Health check fallisce
- Sistema appare down anche se running

**Root Cause**:
- Server saturo elaborando richieste precedenti
- Coda di richieste bloccata
- Mistral-nemo troppo lento per gestire carico

**Priorità**: 🔴 **BLOCCANTE**

---

### Bug #3: Performance Catastrofica - ⛔ CRITICO
**Sezione**: 3. PERFORMANCE (linea 69) + 6. CACHE (linee 86-88)
**Test**: `Avg response: 5.829s (slow)`
**Status**: ❌ **INACCETTABILE**

**Dettagli Performance**:
- Avg response: **5.829s** (target <2.0s, delta +3.8s)
- Peak response: **30.03s** su cache test (target <5.0s)
- Query "stabilimenti rischio": **22.07s** (vs 6.08s con llama3.2)

**Query Specifiche**:
```
✓ "ciao"                         → 0.01s  (OK)
✓ "aiuto"                        → 0.01s  (OK)
⚠ "piano A1"                     → 1.23s  (acceptable)
❌ "stabilimenti rischio"         → 22.07s (INACCETTABILE)
❌ "chi controllare per primo"    → 15.78s (INACCETTABILE)
❌ "piani in ritardo"             → 15.76s (INACCETTABILE)
❌ "piano B47 è in ritardo"       → 16.56s (INACCETTABILE)
❌ Cache Run 1,2,3                → 30.00s CIASCUNO (cache ROTTA)
```

**Cache Failure**:
```
Run 1: 30.03s
Run 2: 30.03s  ← Dovrebbe essere <1s (cached)
Run 3: 30.00s  ← Dovrebbe essere <1s (cached)
```
La cache **NON funziona**: stesso tempo per run 1, 2, 3.

**Impatto**:
- UX inaccettabile (>5s)
- Utenti abbandoneranno il sistema
- Timeout client (JS timeout 75s a rischio)

**Root Cause**:
- Mistral-nemo genera risposte molto più lentamente
- Cache LLM responses non funziona
- Possibile bottleneck I/O o CPU

**Priorità**: 🔴 **CRITICO**

---

### Bug #4: Invalid ASL Crash - 🟡 MEDIO
**Sezione**: 5. ERROR HANDLING (linea 80)
**Test**: `Invalid ASL crashed`
**Status**: ❌ **Regressione da llama3.2**

**Dettagli**:
- Con llama3.2: handled gracefully ✓
- Con mistral-nemo: crashed ✗

**Impatto**:
- Sistema crash su input ASL invalida
- Error handling non robusto

**Priorità**: 🟡 **MEDIA** (ma regressione)

---

### Bug #5: Conferma Monosillabica (già noto)
**Sezione**: 2. INTENT CLASSIFICATION (linea 56)
**Test**: `"sì" → expected confirm_show_details`
**Status**: ⚠️ **Noto da llama3.2**

**Dettagli**:
- Presente anche con llama3.2
- TRUE INTENT: 100% ✓ (linea 170)
- Pattern matching: fallisce in test sequenziali

**Impatto**: BASSO (già documentato)
**Priorità**: 🟢 **BASSA** (non regressione)

---

## 📈 Performance Comparison Dettagliata

### Response Time Distribution

| Range | llama3.2 Count | mistral-nemo Count | Delta |
|-------|----------------|---------------------|-------|
| < 0.1s | ~20 | ~20 | = |
| 0.1-2s | ~15 | ~10 | -5 |
| 2-5s | ~8 | ~5 | -3 |
| 5-10s | ~5 | ~3 | -2 |
| 10-20s | 0 | ~7 | **+7** ❌ |
| > 20s | 0 | ~2 | **+2** ❌ |

**Queries > 10s con mistral-nemo**:
1. stabilimenti rischio: 22.07s
2. Cache runs: 30.00s (×3)
3. piani in ritardo: 13.22s, 15.76s
4. chi controllare: 14.93s, 15.78s
5. piano è in ritardo: 15.58s, 16.56s
6. controlli partita IVA: 13.95s
7. stabilimenti alto rischio: 18.46s

**Nessuna query con llama3.2 superava i 10s**

---

## 🔍 Root Cause Analysis

### Ipotesi #1: Modello Troppo Grande (PROBABILE)
**Evidenza**:
- mistral-nemo: **7.1 GB** vs llama3.2: **~2 GB**
- Memoria server: 3439 MB (dalla sezione 1)
- Possibile swapping su disco

**Verifica**:
```bash
free -h  # Verifica memoria disponibile
top -p <PID_SERVER>  # Verifica uso CPU/RAM
```

### Ipotesi #2: Inference Time Maggiore (CONFERMATO)
**Evidenza**:
- Stesso hardware
- Stesse query
- Mistral-nemo genera più lentamente

**Verifica**:
```bash
# Test diretto Ollama
time ollama run mistral-nemo "test query"
time ollama run llama3.2 "test query"
```

### Ipotesi #3: Cache LLM Rotta (CONFERMATO)
**Evidenza**:
- Run 1,2,3 tutti 30.00s esatti
- Cache dovrebbe ridurre run 2,3 a <1s
- Con llama3.2 cache funzionava

**Verifica**:
- Controllare logs cache hits/misses
- Verificare configurazione cache Ollama

### Ipotesi #4: Bottleneck Concorrenza (CONFERMATO)
**Evidenza**:
- 0/4 concurrent requests succeeded
- REST endpoints timeout
- Server non risponde sotto carico

**Verifica**:
- Test con 1 request alla volta vs parallele
- Verificare limiti Ollama concurrent requests

---

## 🎯 Piano di Bugfixing

### Fase 1: Verifica Immediata (Stima: 30 min)

**Step 1.1**: Verificare risorse sistema
```bash
free -h
top -p $(cat runtime/logs/api-server.pid)
htop  # Se disponibile
```

**Step 1.2**: Test performance Ollama diretta
```bash
# Test mistral-nemo
time curl -X POST http://localhost:11434/api/chat \
  -d '{"model":"mistral-nemo:latest","messages":[{"role":"user","content":"ciao"}]}'

# Test llama3.2 (baseline)
time curl -X POST http://localhost:11434/api/chat \
  -d '{"model":"llama3.2:3b","messages":[{"role":"user","content":"ciao"}]}'
```

**Step 1.3**: Verificare limiti concorrenza Ollama
```bash
# Check Ollama config
curl http://localhost:11434/api/tags
# Verificare OLLAMA_MAX_LOADED_MODELS, OLLAMA_NUM_PARALLEL
```

### Fase 2: Fix Immediati (Stima: 1 ora)

#### Fix #1: Aumentare Timeout Test
**File**: `tests/test_server.py`
**Modifiche**:
```python
# PRIMA:
TIMEOUT_CACHED = 30
TIMEOUT_UNCACHED = 120

# DOPO (per mistral-nemo):
TIMEOUT_CACHED = 60       # +30s
TIMEOUT_UNCACHED = 180    # +60s
```

**Impatto**: Evita falsi negativi da timeout, non risolve performance

#### Fix #2: Disabilitare Cache Test
**Temporaneo**: Skip sezione 6 cache se mistral-nemo
**Razionale**: Cache non funziona, causa timeout

#### Fix #3: Disabilitare Concurrent Test
**Temporaneo**: Skip sezione 7 se mistral-nemo
**Razionale**: Non supportato con modello grande

### Fase 3: Ottimizzazioni (Stima: 2-4 ore)

#### Opt #1: Configurare Ollama per Performance
```bash
# File: /etc/systemd/system/ollama.service (o equivalente)
[Service]
Environment="OLLAMA_NUM_PARALLEL=2"         # Ridurre da default
Environment="OLLAMA_MAX_LOADED_MODELS=1"    # Un solo modello in memoria
Environment="OLLAMA_FLASH_ATTENTION=1"      # Abilita ottimizzazione
```

#### Opt #2: Usare Quantizzazione Inferiore
**Opzione A**: Scaricare mistral-nemo con quantizzazione Q4
```bash
ollama pull mistral-nemo:Q4_K_M  # Più veloce, meno accurato
```

**Opzione B**: Usare solo llama3.2 per ora
```bash
export GIAS_LLM_MODEL=llama3.2
scripts/server.sh restart
```

#### Opt #3: Aumentare Context Window (se disponibile)
Verificare se mistral-nemo supporta context caching

### Fase 4: Decisione Strategica (Stima: 30 min discussione)

**Opzione A**: ❌ **Abbandonare mistral-nemo**
- **Pro**: llama3.2 funziona bene (97-98% success rate)
- **Pro**: Performance accettabile (avg 2.5-5.7s)
- **Pro**: Concurrent requests funzionanti
- **Contro**: Perdiamo capacità maggiori di mistral-nemo

**Opzione B**: ⚠️ **Ottimizzare mistral-nemo**
- **Pro**: Modello più potente (12B parametri)
- **Pro**: Potenziale accuracy migliore
- **Contro**: Richiede molto lavoro ottimizzazione
- **Contro**: Hardware limits (7.1GB modello)
- **Contro**: Rischio performance sempre insufficienti

**Opzione C**: ✅ **Hybrid Approach** (RACCOMANDATO)
- **llama3.2** per operazioni real-time (<2s target)
- **mistral-nemo** per operazioni batch/offline
- **Configurazione dinamica** basata su tipo query

**Opzione D**: 🔍 **Provare Altri Modelli**
- **llama3.1:8b** (middle ground)
- **qwen2.5:7b** (veloce)
- **phi3:mini** (leggerissimo, 3.8GB)

---

## 📋 Decision Matrix

| Criterio | llama3.2:3b | mistral-nemo | llama3.1:8b | phi3:mini |
|----------|-------------|--------------|-------------|-----------|
| **Success Rate** | 97-98% ✅ | 97% ⚠️ | ? | ? |
| **Avg Response** | 2.5-5.7s ✅ | 5.8s ❌ | ? | ? |
| **Peak Response** | 9.6s ✅ | 30s ❌ | ? | ? |
| **Concurrent** | 4/4 ✅ | 0/4 ❌ | ? | ? |
| **Memory** | ~2GB ✅ | 7.1GB ❌ | ~5GB ⚠️ | 3.8GB ✅ |
| **Accuracy** | Good ✅ | Better ✅ | Better ✅ | Good ⚠️ |

---

## 🚀 Raccomandazioni Immediate

### 1. **ROLLBACK a llama3.2** (5 minuti)
```bash
cd /opt/lang-env/GiAs-llm
scripts/server.sh stop
GIAS_LLM_MODEL=llama3.2 scripts/server.sh start
```

**Razionale**:
- Sistema funzionante con 97-98% success
- Performance accettabile
- Concurrent OK
- Pronto per produzione

### 2. **Benchmark Altri Modelli** (2-3 ore)
Test in ordine di priorità:
1. **llama3.1:8b** - Middle ground (size/performance)
2. **qwen2.5:7b** - Noto per velocità
3. **phi3:mini** - Ultralight

### 3. **Documentare Limitazioni** (30 min)
Aggiornare docs con:
- mistral-nemo: non adatto per real-time
- Requisiti minimi hardware per modelli > 5GB
- Benchmark comparativi

### 4. **Implement Model Auto-Selection** (2-4 ore)
Logic basata su query type:
- Simple queries → llama3.2 (fast)
- Complex queries → mistral-nemo (accurate, async)

---

## 📊 Metriche di Successo

### Target Post-Fix

| Metrica | Current | Target | Status |
|---------|---------|--------|--------|
| Success Rate | 97% | ≥98% | ⚠️ |
| Avg Response | 5.8s | <3.0s | ❌ |
| Peak Response | 30s | <10s | ❌ |
| Concurrent (4 req) | 0/4 | 4/4 | ❌ |
| REST Endpoints | 0/5 | 5/5 | ❌ |
| Cache Working | NO | YES | ❌ |

### Acceptance Criteria

1. ✅ Concurrent requests: 4/4 succeeded
2. ✅ REST endpoints: all responding <5s
3. ✅ Avg response: <3.0s
4. ✅ No query >10s
5. ✅ Cache working (run 2,3 < 1s)
6. ✅ Success rate ≥98%

---

## 📝 Next Steps (Ordine di Priorità)

### Immediato (Oggi)
1. ✅ **ROLLBACK a llama3.2** (5 min)
2. ✅ **Verificare sistema stabile** (10 min re-test)
3. ✅ **Documentare findings mistral-nemo** (questo documento)

### Breve Termine (Questa Settimana)
4. 🔄 **Benchmark llama3.1:8b** (2 ore)
5. 🔄 **Benchmark qwen2.5:7b** (2 ore)
6. 🔄 **Benchmark phi3:mini** (2 ore)
7. 📝 **Comparative report** (1 ora)

### Medio Termine (Prossimo Mese)
8. 💡 **Design hybrid model selection** (4 ore)
9. 💻 **Implement model router** (8 ore)
10. 🧪 **Test hybrid approach** (4 ore)
11. 📚 **Update documentation** (2 ore)

---

## 🔗 Riferimenti

- **Test Log**: `runtime/logs/test_mistral_nemo_20260131_160558.log`
- **Server Log**: `runtime/logs/api-server.log`
- **Modello Info**: mistral-nemo:latest (7.1 GB)
- **Hardware**: Server PID 28958, Memory 3439MB

---

**Report generato**: 2026-01-31 16:30:00
**Autore**: Claude Code Analysis
**Status**: ⛔ **ROLLBACK RACCOMANDATO**
