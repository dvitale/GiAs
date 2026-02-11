# GiAs-llm Backend Comparison Tool

Tool completo per confrontare le performance tra **Ollama** e **Llama.cpp** come backend LLM per GiAs-llm.

## 📋 Indice

- [Caratteristiche](#caratteristiche)
- [Prerequisiti](#prerequisiti)
- [Installazione](#installazione)
- [Utilizzo](#utilizzo)
- [Test Cases](#test-cases)
- [Output](#output)
- [Esempi](#esempi)
- [Interpretazione Risultati](#interpretazione-risultati)

---

## ✨ Caratteristiche

- ✅ **42+ test cases** coprendo tutti gli intent principali
- ✅ **Metriche multiple**: Accuratezza, tempo di risposta, stabilità
- ✅ **Report dettagliati**: Console, JSON, HTML interattivo
- ✅ **Statistiche aggregate**: Min, Max, Media, Deviazione Standard
- ✅ **Analisi per intent**: Performance granulare
- ✅ **Quick mode**: Test rapidi per verifiche veloci
- ✅ **Grafici interattivi**: Visualizzazione chiara dei risultati
- ✅ **Iterazioni multiple**: Risultati affidabili e riproducibili

---

## 📦 Prerequisiti

### 1. Backend LLM Attivi

**Ollama** (porta 11434):
```bash
# Verifica che Ollama sia in esecuzione
curl -s http://localhost:11434/api/tags

# Se non è attivo, avvialo
ollama serve
```

**Llama.cpp** (porta 11435):
```bash
# Verifica che llama.cpp sia in esecuzione
curl -s http://localhost:11435/health

# Se non è attivo, avvialo
cd /opt/lang-env/GiAs-llm
./start_llama-cpp.sh
```

### 2. Dipendenze Python

Il tool usa solo librerie standard Python 3:
- `json`, `time`, `statistics`, `argparse`, `dataclasses`

Nessuna installazione aggiuntiva richiesta!

---

## 🚀 Utilizzo

### Benchmark Completo (Consigliato)

Esegue tutti i 42 test cases con 3 iterazioni per backend:

```bash
cd /opt/lang-env/GiAs-llm/benchmarks
python3 compare_llm_backends.py
```

**Output:**
- Report dettagliato su console
- File JSON: `benchmark_results.json`

**Tempo stimato:** 5-10 minuti

---

### Quick Test (Veloce)

Esegue 10 test cases rappresentativi con 1 iterazione:

```bash
python3 compare_llm_backends.py --quick
```

**Output:**
- Report su console
- File JSON: `benchmark_results.json`

**Tempo stimato:** 1-2 minuti

Perfetto per verifiche rapide dopo modifiche al sistema!

---

### Test Singolo Backend

Testa solo Llama.cpp:

```bash
python3 compare_llm_backends.py --backends llamacpp
```

Testa solo Ollama:

```bash
python3 compare_llm_backends.py --backends ollama
```

---

### Configurazione Avanzata

```bash
python3 compare_llm_backends.py \
  --backends ollama llamacpp \
  --iterations 5 \
  --output my_benchmark.json \
  --quiet
```

**Opzioni:**
- `--backends`: Backend da testare (default: entrambi)
- `--iterations`: Numero di iterazioni per test (default: 3)
- `--output`: Nome file JSON output (default: benchmark_results.json)
- `--quick`: Quick mode (10 test, 1 iterazione)
- `--quiet`: Output minimale (solo report finale)

---

## 📊 Visualizzazione Risultati

### Report HTML Interattivo

Genera report HTML con grafici Chart.js:

```bash
python3 visualize_benchmark.py benchmark_results.json
```

**Output:**
- `benchmark_report.html` - Report interattivo con grafici

Apri il file nel browser per visualizzare:
- 📊 Grafici accuratezza e tempi
- 📋 Tabella statistiche dettagliate
- 🏆 Indicatori vincitore per metrica
- 📈 Analisi comparativa

### Summary Testuale

```bash
python3 visualize_benchmark.py benchmark_results.json --summary
```

Stampa solo il riepilogo testuale senza generare HTML.

---

## 🧪 Test Cases

Il benchmark include **42 test cases** organizzati in categorie:

### Categorie

| Categoria | Test Cases | Complessità |
|-----------|------------|-------------|
| **Saluti e Aiuto** | 8 | Simple |
| **Piani - Descrizione** | 3 | Medium |
| **Piani - Stabilimenti** | 3 | Medium-Complex |
| **Piani - Generic** | 3 | Medium |
| **Piani - Statistiche** | 3 | Medium |
| **Ricerca Piani** | 3 | Medium-Complex |
| **Priorità Controlli** | 3 | Medium |
| **Analisi Rischio** | 6 | Medium-Complex |
| **Mai Controllati** | 3 | Medium |
| **Piani in Ritardo** | 4 | Medium-Complex |
| **Storico Stabilimenti** | 2 | Complex |
| **Non Conformità** | 2 | Complex |

### Intent Testati

```
✅ greet, goodbye, ask_help
✅ ask_piano_description
✅ ask_piano_stabilimenti
✅ ask_piano_generic
✅ ask_piano_statistics
✅ search_piani_by_topic
✅ ask_priority_establishment
✅ ask_risk_based_priority
✅ ask_top_risk_activities
✅ ask_suggest_controls
✅ ask_delayed_plans
✅ check_if_plan_delayed
✅ ask_establishment_history
✅ analyze_nc_by_category
```

---

## 📄 Output

### 1. Report Console

```
================================================================================
                         BENCHMARK COMPARISON REPORT
================================================================================

📊 OVERALL STATISTICS
--------------------------------------------------------------------------------
Backend         Tests    Correct    Accuracy     Avg Time (ms)   Std Dev
--------------------------------------------------------------------------------
LLAMACPP        126      120        95.24%            842.35        127.45
OLLAMA          126      118        93.65%           1156.78        189.32
--------------------------------------------------------------------------------

🔍 DIRECT COMPARISON: LLAMACPP vs OLLAMA
--------------------------------------------------------------------------------
Accuracy:        LLAMACPP wins by 1.59%
Speed:           LLAMACPP is 314.43ms faster (27.2% improvement)

📋 ACCURACY BY INTENT
--------------------------------------------------------------------------------

greet:
  LLAMACPP        Accuracy:  100.00% (9/9)  Avg Time:  245.67ms
  OLLAMA          Accuracy:  100.00% (9/9)  Avg Time:  387.23ms

ask_piano_description:
  LLAMACPP        Accuracy:  100.00% (9/9)  Avg Time:  892.45ms
  OLLAMA          Accuracy:   88.89% (8/9)  Avg Time: 1234.12ms

...
```

### 2. File JSON

```json
{
  "timestamp": "2025-01-28T16:45:23.123456",
  "test_config": {
    "test_cases": 42,
    "iterations": 3,
    "backends": ["ollama", "llamacpp"]
  },
  "statistics": {
    "llamacpp": {
      "backend": "llamacpp",
      "total_tests": 126,
      "correct": 120,
      "accuracy": 95.24,
      "avg_response_time_ms": 842.35,
      ...
    }
  },
  "detailed_results": {
    "llamacpp": [
      {
        "backend": "llamacpp",
        "intent": "greet",
        "message": "ciao",
        "expected_intent": "greet",
        "predicted_intent": "greet",
        "correct": true,
        "response_time_ms": 245.67,
        ...
      }
    ]
  }
}
```

### 3. Report HTML

Report interattivo con:
- 📊 **Grafici a barre** per accuratezza e tempi
- 📋 **Tabella dettagliata** con tutte le statistiche
- 🏆 **Badge vincitore** per ogni metrica
- 🎨 **Design responsive** e professionale
- 📱 **Mobile-friendly**

---

## 📈 Interpretazione Risultati

### Metriche Chiave

#### 1. **Accuracy (%)**
- Percentuale di intent classificati correttamente
- **Target:** ≥ 95% per production
- **Buono:** 90-95%
- **Accettabile:** 85-90%
- **Problema:** < 85%

#### 2. **Avg Response Time (ms)**
- Tempo medio di classificazione
- **Eccellente:** < 500ms
- **Buono:** 500-1000ms
- **Accettabile:** 1000-2000ms
- **Lento:** > 2000ms

#### 3. **Std Dev (ms)**
- Stabilità delle performance
- **Stabile:** < 100ms
- **Medio:** 100-200ms
- **Instabile:** > 200ms

#### 4. **Min/Max Time (ms)**
- Range di variazione
- Indica outlier e worst-case

### Quando Preferire Llama.cpp

✅ **Velocità critica** (< 1s risposta)
✅ **Risorse limitate** (memoria/CPU)
✅ **Alto throughput** (molte richieste/sec)
✅ **Costo operativo** (minore consumo risorse)

### Quando Preferire Ollama

✅ **Accuratezza massima** (> 95%)
✅ **Modelli diversi** (facile switching)
✅ **Debugging** (migliori log e tools)
✅ **Ecosistema** (community e supporto)

---

## 🔧 Troubleshooting

### Errore: Backend non disponibile

```
⚠️ Warning: llamacpp not available (connection refused)
```

**Soluzione:**
```bash
# Verifica che il server sia attivo
curl http://localhost:11435/health  # Llama.cpp
curl http://localhost:11434/api/tags  # Ollama

# Se non risponde, avvia il server
./start_llama-cpp.sh  # per Llama.cpp
ollama serve           # per Ollama
```

### Errore: Import config

```
ImportError: No module named 'configs'
```

**Soluzione:**
```bash
# Esegui dalla directory corretta
cd /opt/lang-env/GiAs-llm/benchmarks
python3 compare_llm_backends.py
```

### Performance Inattese

Se i risultati sono molto diversi dal previsto:

1. **Warmup insufficiente**: Il primo test è sempre più lento
   - Soluzione: Usa `--iterations 3` o più

2. **Cache attiva**: I test successivi sono più veloci
   - Il tool disabilita la cache automaticamente

3. **Sistema carico**: Altri processi rallentano i test
   - Soluzione: Esegui su sistema dedicato o con carico basso

4. **Modello diverso**: Ollama potrebbe usare un modello diverso
   - Soluzione: Verifica configurazione in `config.json`

---

## 📚 Esempi Pratici

### Esempio 1: Test Rapido Prima di Deploy

```bash
# Quick test per verificare che tutto funzioni
python3 compare_llm_backends.py --quick --quiet

# Se OK, procedi con test completo
python3 compare_llm_backends.py --output pre-deploy.json
```

### Esempio 2: Ottimizzazione Backend

```bash
# Test solo Llama.cpp con molte iterazioni
python3 compare_llm_backends.py \
  --backends llamacpp \
  --iterations 10 \
  --output llamacpp-optimized.json

# Analizza risultati
python3 visualize_benchmark.py llamacpp-optimized.json
```

### Esempio 3: Confronto Dopo Aggiornamento

```bash
# Test PRIMA dell'aggiornamento
python3 compare_llm_backends.py --output before.json

# ... aggiorna il sistema ...

# Test DOPO l'aggiornamento
python3 compare_llm_backends.py --output after.json

# Confronta i due file JSON manualmente
```

### Esempio 4: Benchmark per Documentazione

```bash
# Test completo con 5 iterazioni per risultati affidabili
python3 compare_llm_backends.py \
  --iterations 5 \
  --output official-benchmark.json

# Genera report HTML professionale
python3 visualize_benchmark.py official-benchmark.json \
  --output official-report.html

# Condividi official-report.html nella documentazione
```

---

## 🎯 Best Practices

1. **Warmup**: I primi test sono sempre più lenti
   - Usa almeno 3 iterazioni

2. **Sistema Pulito**: Esegui su sistema non carico
   - Chiudi applicazioni pesanti
   - Evita altri processi LLM

3. **Ripetibilità**: Usa lo stesso numero di iterazioni
   - Default 3 è un buon compromesso

4. **Documentazione**: Salva i risultati con nomi descrittivi
   - `benchmark-v1.2-llamacpp.json`
   - `production-test-2025-01-28.json`

5. **Monitoraggio**: Esegui benchmark periodici
   - Dopo ogni aggiornamento major
   - Mensilmente per tracciare trend

---

## 📞 Supporto

Per problemi o domande:
- Verifica questo README
- Controlla i log dei server LLM
- Testa i backend individualmente
- Controlla la configurazione in `config.json`

---

## 🔄 Aggiornamenti

**Versione:** 1.0.0
**Data:** 2025-01-28
**Autore:** GiAs-llm Development Team

---

## 📝 Licenza

Parte del progetto GiAs-llm - Regione Campania
