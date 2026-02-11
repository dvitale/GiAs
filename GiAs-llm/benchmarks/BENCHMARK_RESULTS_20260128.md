# GiAs-llm Backend Comparison - Full Benchmark Results

**Data:** 2026-01-28 16:02-16:04
**Durata:** ~2 minuti
**Test Totali:** 258 (129 per backend)
**Configurazione:** 42 test cases × 3 iterazioni × 2 backends

---

## 📊 Executive Summary

### 🏆 Vincitori per Metrica

| Metrica | Vincitore | Valore | Delta | Valutazione |
|---------|-----------|--------|-------|-------------|
| **Accuratezza** | **Llama.cpp** | 97.67% | +2.32% | ⭐⭐⭐⭐⭐ |
| **Velocità Media** | **Ollama** | 126.30ms | 5x più veloce | ⭐⭐⭐⭐⭐ |
| **Stabilità (Std Dev)** | **Ollama** | 1137ms | 4.5x più stabile | ⭐⭐⭐⭐ |
| **Tempo Min** | 🟰 Pareggio | 0.01ms | - | ✅ |
| **Tempo Max** | **Ollama** | 12.8s vs 58.4s | 4.5x migliore | ⭐⭐⭐⭐ |
| **Errori** | 🟰 Pareggio | 0 | - | ✅ |

---

## 📈 Statistiche Complete

### Llama.cpp

```
Modello:         Llama-3.2-3B-Instruct-Q6_K_L.gguf
Backend:         Llama.cpp server (porta 11435)
API:             OpenAI-compatible (/v1/chat/completions)

Risultati:
✅ Test Totali:       129
✅ Corretti:          126
❌ Errati:            3
✅ Accuratezza:       97.67%

Performance:
⏱️  Tempo Medio:      611.16 ms
⚡ Tempo Minimo:      0.01 ms
🐌 Tempo Massimo:     58,367.96 ms (OUTLIER!)
📊 Deviazione Std:    5,185.95 ms
❌ Errori Runtime:    0

Distribuzione Tempi:
- 0-100ms:      92% dei test (heuristics)
- 100-1000ms:   5% dei test (LLM normale)
- 1000ms+:      3% dei test (LLM lento)
- Outlier:      1 test a 58 secondi (ask_risk_based_priority)
```

### Ollama

```
Modello:         llama3.2:3b
Backend:         Ollama server (porta 11434)
API:             Ollama native (/api/chat)

Risultati:
✅ Test Totali:       129
✅ Corretti:          123
❌ Errati:            6
✅ Accuratezza:       95.35%

Performance:
⏱️  Tempo Medio:      126.30 ms
⚡ Tempo Minimo:      0.01 ms
🐌 Tempo Massimo:     12,845.01 ms
📊 Deviazione Std:    1,137.68 ms
❌ Errori Runtime:    0

Distribuzione Tempi:
- 0-100ms:      94% dei test (molto consistente)
- 100-1000ms:   4% dei test (LLM)
- 1000ms+:      2% dei test (LLM complessi)
- Max:          12.8 secondi (ask_risk_based_priority)
```

---

## 🎯 Analisi per Intent

### ✅ Intent con 100% Accuratezza (Entrambi)

Questi intent funzionano **perfettamente** su entrambi i backend:

| Intent | Llama.cpp | Ollama | Tempo Medio (Llama.cpp) | Tempo Medio (Ollama) |
|--------|-----------|--------|-------------------------|----------------------|
| `greet` | 100% (9/9) | 100% (9/9) | 0.02ms | 0.02ms |
| `goodbye` | 100% (6/6) | 100% (6/6) | 0.01ms | 0.01ms |
| `ask_help` | 100% (9/9) | 100% (9/9) | 0.02ms | 0.02ms |
| `ask_piano_description` | 100% (9/9) | 100% (9/9) | 0.03ms | 0.03ms |
| `ask_piano_generic` | 100% (9/9) | 100% (9/9) | 0.04ms | 0.03ms |
| `ask_piano_stabilimenti` | 100% (9/9) | 100% (9/9) | 0.04ms | 0.04ms |
| `ask_piano_statistics` | 100% (9/9) | 100% (9/9) | 0.02ms | 0.02ms |
| `ask_priority_establishment` | 100% (9/9) | 100% (9/9) | 0.02ms | 0.02ms |
| `ask_suggest_controls` | 100% (9/9) | 100% (9/9) | 0.03ms | 0.02ms |
| `ask_top_risk_activities` | 100% (9/9) | 100% (9/9) | 0.04ms | 0.04ms |
| `ask_delayed_plans` | 100% (6/6) | 100% (6/6) | 0.03ms | 0.02ms |
| `check_if_plan_delayed` | 100% (6/6) | 100% (6/6) | 0.04ms | 0.04ms |
| `ask_establishment_history` | 100% (6/6) | 100% (6/6) | 0.04ms | 0.04ms |
| `search_piani_by_topic` | 100% (9/9) | 100% (9/9) | 0.03ms | 0.04ms |

**Total:** 14/16 intent con accuratezza perfetta!

---

### ⚠️ Intent Problematici

#### 1. **ask_risk_based_priority** - CRITICO

| Backend | Accuratezza | Tempo Medio | Note |
|---------|-------------|-------------|------|
| **Llama.cpp** | 100% (9/9) ✅ | 7,379.78ms 🐌 | Accuratezza perfetta ma **ESTREMAMENTE LENTO** |
| **Ollama** | 66.67% (6/9) ❌ | 1,647.67ms | Veloce ma **BASSA ACCURATEZZA** |

**Analisi:**
- Llama.cpp: Classifica correttamente ma impiega ~7 secondi per risposta (inaccettabile per produzione)
- Ollama: Veloce ma sbaglia 3 test su 9 (33% errori)

**Raccomandazione:**
- Migliorare gli heuristics per bypassare l'LLM su questo intent
- Aggiungere pattern regex più robusti per "stabilimenti a rischio"
- Considerare timeout configurabile per Llama.cpp

#### 2. **analyze_nc_by_category** - PROBLEMA COMUNE

| Backend | Accuratezza | Tempo Medio | Note |
|---------|-------------|-------------|------|
| **Llama.cpp** | 50% (3/6) ❌ | 2,069.79ms | Metà test falliti |
| **Ollama** | 50% (3/6) ❌ | 243.34ms | Metà test falliti |

**Analisi:**
- Entrambi i backend hanno **la stessa accuratezza** (50%)
- Problema non è il backend ma l'**intent stesso o il prompt**
- Llama.cpp è 8x più lento di Ollama

**Raccomandazione:**
- Analizzare i test falliti per capire il pattern
- Migliorare gli heuristics per categorie NC note
- Aggiungere esempi al prompt di classificazione
- Possibile problema con estrazione slot `categoria`

---

## 🔍 Analisi Approfondita

### Performance Distribution

#### Llama.cpp - Distribuzione Tempi

```
Percentile  | Tempo
------------|-------
P50 (median)| 0.03ms  (heuristics)
P75         | 0.04ms  (heuristics)
P90         | 15ms    (alcuni LLM calls)
P95         | 1200ms  (LLM complessi)
P99         | 7500ms  (outlier)
P99.9       | 58367ms (OUTLIER ESTREMO!)

Insight: Il 90% dei test è velocissimo (<15ms), ma il 10%
         più lento crea una media distorta (611ms)
```

#### Ollama - Distribuzione Tempi

```
Percentile  | Tempo
------------|-------
P50 (median)| 0.03ms  (heuristics)
P75         | 0.04ms  (heuristics)
P90         | 10ms    (alcuni LLM calls)
P95         | 250ms   (LLM)
P99         | 2000ms  (LLM complessi)
P99.9       | 12845ms (outlier massimo)

Insight: Molto più consistente, outlier contenuti.
         Anche i casi peggiori sono gestibili.
```

### Heuristics Effectiveness

Entrambi i backend usano lo stesso **Router ibrido** con layer heuristics:

```
Efficacia Heuristics: ~85-90%
- La maggior parte dei test viene risolta con pattern matching
- Solo 10-15% richiede effettivamente l'LLM
- Heuristics uguale = tempi simili per intent semplici

Tempi <0.1ms = Heuristics match
Tempi >100ms = LLM classification
```

---

## 💡 Insights Chiave

### 1. **Heuristics Dominano le Performance**

**85-90% dei test** viene risolto tramite pattern matching, senza chiamare l'LLM.

**Implicazioni:**
- I tempi misurati riflettono principalmente l'efficacia degli heuristics
- Le differenze emergono solo sui ~15% che richiedono LLM
- Ottimizzare gli heuristics ha impatto maggiore che cambiare backend

### 2. **Ollama è Più Veloce quando serve l'LLM**

Quando è necessaria la classificazione LLM:
- **Ollama**: 100-300ms per risposta
- **Llama.cpp**: 1000-7000ms per risposta

**Causa probabile:**
- Ollama ha ottimizzazioni specifiche per il modello llama3.2:3b
- Llama.cpp è più generico ma meno ottimizzato
- Differenze nell'implementazione del server

### 3. **Llama.cpp Ha Outlier Estremi**

**Tempo massimo**: 58.4 secondi (su `ask_risk_based_priority`)

**Possibili cause:**
1. Timeout interno del server
2. Query particolarmente complessa per l'LLM
3. Problema di contention/memory
4. Bug nel server llama.cpp

**Soluzione:** Configurare timeout client-side (es. 5-10 secondi)

### 4. **Accuratezza Molto Alta su Entrambi**

- **Llama.cpp**: 97.67% (produzione-ready)
- **Ollama**: 95.35% (produzione-ready)

Entrambi superano la soglia del 95% considerata ottima per produzione.

### 5. **Intent Problematici Sono Comuni**

`analyze_nc_by_category` fallisce al 50% su **entrambi** i backend.

**Conclusione:** Il problema non è il backend ma:
- Gli heuristics non coprono questo caso
- Il prompt LLM non è abbastanza chiaro
- Possibile ambiguità nell'intent stesso

---

## 🎯 Raccomandazioni

### Per Produzione Generale: **OLLAMA** ⚡

**Motivazioni:**
1. ✅ **5x più veloce** nella media (126ms vs 611ms)
2. ✅ **Molto più stabile** (std dev 1137ms vs 5185ms)
3. ✅ **Nessun outlier estremo** (max 12s vs 58s)
4. ✅ **95% accuratezza** è eccellente per produzione
5. ✅ **Tempi prevedibili** - importante per SLA

**Quando usare:**
- Sistema con utenti multipli concorrenti
- Requisiti di latenza stringenti (< 500ms)
- API pubbliche o chatbot real-time
- Budget computazionale limitato

### Per Massima Accuratezza: **LLAMA.CPP** 🎯

**Motivazioni:**
1. ✅ **97.67% accuratezza** (2.3% meglio)
2. ✅ **100% su ask_risk_based_priority** (critico)
3. ✅ **Meno errori totali** (3 vs 6)

**MA con questi accorgimenti:**
1. ⚠️ **Configurare timeout** (5-10 secondi massimo)
2. ⚠️ **Monitorare outlier** e retry su timeout
3. ⚠️ **Non adatto ad alto throughput**

**Quando usare:**
- Sistema single-user o basso volume
- Accuratezza critica (settore regolamentato)
- Latenza non è il fattore principale
- Intent `ask_risk_based_priority` molto usato

### Approccio Ibrido (Raccomandato!) 🔀

**Strategia migliore per GiAs-llm:**

```python
# Pseudocodice
if intent in ["ask_risk_based_priority", "critical_intents"]:
    backend = "llamacpp"  # Massima accuratezza
    timeout = 10_000  # 10 secondi
else:
    backend = "ollama"  # Velocità
    timeout = 2_000   # 2 secondi

try:
    result = backend.classify(message, timeout=timeout)
except TimeoutException:
    # Fallback su ollama se llama.cpp troppo lento
    result = ollama.classify(message, timeout=2_000)
```

**Vantaggi:**
- ✅ Accuratezza massima su intent critici
- ✅ Velocità su intent comuni
- ✅ Resilienza (fallback automatico)
- ✅ Ottimizzazione risorse

---

## 🔧 Azioni Immediate

### 1. **Priorità ALTA - Fix `analyze_nc_by_category`**

```python
# Aggiungere heuristics specifico in router.py
NC_CATEGORY_PATTERNS = re.compile(
    r'\b(NC|non\s*conformit[àa])\s*(categoria|per|HACCP|IGIENE)',
    re.IGNORECASE
)

# Migliorare estrazione categoria
VALID_CATEGORIES = [
    "HACCP", "IGIENE DEGLI ALIMENTI", "IGIENE",
    "CONDIZIONI DELLA STRUTTURA", "STRUTTURE",
    # ... altre categorie
]
```

### 2. **Priorità ALTA - Configurare Timeout**

```python
# In llm/client.py
DEFAULT_TIMEOUT = 5000  # 5 secondi
MAX_TIMEOUT = 10000     # 10 secondi max

# In configs/config.json
{
  "llm_backend": {
    "llamacpp": {
      "timeout_ms": 5000,
      "max_timeout_ms": 10000
    }
  }
}
```

### 3. **Priorità MEDIA - Ottimizza `ask_risk_based_priority`**

```python
# Aggiungere pattern più robusti
RISK_PATTERNS = re.compile(
    r'\b(stabiliment[io]|OSA)\s+.*\s*(a|ad|più)\s*rischio|'
    r'\brischios[io]\b|'
    r'\balto\s+rischio\b',
    re.IGNORECASE
)
```

### 4. **Priorità BASSA - Logging Outlier**

```python
# Aggiungere logging per tempi anomali
if response_time > 5000:  # > 5 secondi
    logger.warning(
        f"Slow LLM response: {response_time}ms, "
        f"backend={backend}, intent={intent}, message={message[:50]}"
    )
```

---

## 📊 Metriche di Successo

### KPI Target per Produzione

| Metrica | Target | Llama.cpp | Ollama | Status |
|---------|--------|-----------|--------|--------|
| Accuratezza | ≥ 95% | 97.67% ✅ | 95.35% ✅ | ✅ Entrambi OK |
| Tempo P50 | < 100ms | ~0.03ms ✅ | ~0.03ms ✅ | ✅ Entrambi OK |
| Tempo P95 | < 2000ms | ~1200ms ✅ | ~250ms ✅ | ✅ Entrambi OK |
| Tempo P99 | < 5000ms | ~7500ms ⚠️ | ~2000ms ✅ | ⚠️ Llama.cpp borderline |
| Errori | 0 | 0 ✅ | 0 ✅ | ✅ Entrambi OK |
| Stabilità (CV) | < 2.0 | 8.5 ❌ | 9.0 ❌ | ❌ Entrambi da migliorare |

**CV (Coefficient of Variation)** = Std Dev / Mean
- Llama.cpp: 5185 / 611 = 8.5
- Ollama: 1137 / 126 = 9.0

**Nota:** CV alto indica **alta variabilità** nei tempi di risposta, ma è normale dato che:
- 90% dei test sono <1ms (heuristics)
- 10% dei test sono 100-10000ms (LLM)
- La media è distorta dalla bimodalità

---

## 🎓 Conclusioni

### Verdict Finale

**Non esiste un vincitore assoluto** - dipende dal caso d'uso:

| Caso d'uso | Backend Raccomandato | Motivazione |
|------------|---------------------|-------------|
| **API Pubblica** | Ollama ⚡ | Velocità + stabilità |
| **Chatbot Real-time** | Ollama ⚡ | Latenza bassa |
| **Sistema Critico** | Llama.cpp 🎯 | Accuratezza massima |
| **Basso Volume** | Llama.cpp 🎯 | Accuratezza > velocità |
| **Alto Throughput** | Ollama ⚡ | Performance consistenti |
| **GiAs-llm (raccomandato)** | **Ibrido** 🔀 | Best of both worlds |

### Implementazione Consigliata per GiAs-llm

**Approccio Ibrido con Ollama come default:**

1. **Default**: Ollama (95% dei casi)
   - Veloce, stabile, accuratezza ottima

2. **Intent Critici**: Llama.cpp con timeout
   - `ask_risk_based_priority`
   - Altri intent mission-critical

3. **Fallback**: Ollama se timeout
   - Resilienza garantita

4. **Monitoring**: Log tempi anomali
   - Tracking outlier
   - Alert su P99 > 5s

---

## 📁 File di Riferimento

- **JSON Results**: `benchmark_20260128_160220.json` (102 KB)
- **HTML Report**: `benchmark_report_20260128_160220.html` (9.9 KB)
- **Questo Report**: `BENCHMARK_RESULTS_20260128.md`

---

**Generato:** 2026-01-28 16:04:30
**Tool:** GiAs-llm Backend Comparison Tool v1.0.0
**Autore:** GiAs-llm Development Team
