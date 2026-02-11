# Quick Start - Backend Comparison Tool

Guida rapida per eseguire i benchmark e confrontare Ollama vs Llama.cpp.

## 🚀 Esecuzione Rapida

### 1. Verifica Backend Attivi

```bash
# Llama.cpp (porta 11435)
curl http://localhost:11435/health
# Output atteso: {"status":"ok"}

# Ollama (porta 11434)
curl http://localhost:11434/api/tags
# Output atteso: {"models":[...]}
```

### 2. Esegui Benchmark Veloce (1-2 minuti)

```bash
cd /opt/lang-env/GiAs-llm/benchmarks
./run_quick_benchmark.sh
```

**Output atteso:**
```
===========================================
   GiAs-llm Quick Benchmark
===========================================

🔍 Checking backends availability...
   ✅ Llama.cpp is running (port 11435)
   ✅ Ollama is running (port 11434)

🚀 Running quick benchmark...
   Backends:  llamacpp ollama
   Test cases: 10 representative
   Iterations: 1

[Progress messages...]

===========================================
   Benchmark completed successfully!
===========================================

📊 Results saved to: quick_benchmark.json

📈 Generate HTML report:
   python3 visualize_benchmark.py quick_benchmark.json
```

### 3. Visualizza Report HTML

```bash
python3 visualize_benchmark.py quick_benchmark.json
```

Poi apri nel browser: `benchmark_report.html`

---

## 📊 Benchmark Completo (5-10 minuti)

```bash
./run_full_benchmark.sh
```

Esegue:
- ✅ 42 test cases (tutti gli intent)
- ✅ 3 iterazioni per affidabilità
- ✅ Genera JSON + HTML automaticamente

---

## 📈 Output di Esempio

### Console Report

```
================================================================================
                         BENCHMARK COMPARISON REPORT
================================================================================

📊 OVERALL STATISTICS
--------------------------------------------------------------------------------
Backend         Tests    Correct    Accuracy     Avg Time (ms)   Std Dev
--------------------------------------------------------------------------------
LLAMACPP        126      120        95.24%           842.35        127.45
OLLAMA          126      118        93.65%          1156.78        189.32
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

ask_risk_based_priority:
  LLAMACPP        Accuracy:  100.00% (9/9)  Avg Time:  756.23ms
  OLLAMA          Accuracy:   88.89% (8/9)  Avg Time: 1045.67ms

[... altri intent ...]

⏱️  RESPONSE TIME DETAILS
--------------------------------------------------------------------------------
Backend         Min (ms)     Max (ms)     Avg (ms)     Std Dev (ms)
--------------------------------------------------------------------------------
LLAMACPP        234.56       1456.78      842.35       127.45
OLLAMA          345.67       2134.89     1156.78       189.32
--------------------------------------------------------------------------------

✅ NO ERRORS FOUND

================================================================================
```

### HTML Report

Il report HTML include:

1. **Summary Cards**
   - Accuratezza con badge vincitore 🏆
   - Tempo medio con badge velocità ⚡

2. **Grafici Interattivi**
   - Grafico a barre: Accuratezza
   - Grafico a barre: Tempo di risposta

3. **Tabella Dettagliata**
   - Tutte le statistiche aggregate
   - Min, Max, Avg, Std Dev
   - Colori per livelli di accuratezza

4. **Design Professionale**
   - Gradient colorati
   - Responsive
   - Mobile-friendly

---

## 🎯 Interpretazione Veloce

### Accuratezza

| Range | Valutazione |
|-------|-------------|
| ≥ 95% | ✅ Eccellente (production-ready) |
| 90-95% | 🟢 Buono |
| 85-90% | 🟡 Accettabile |
| < 85% | 🔴 Problema |

### Tempo di Risposta

| Range | Valutazione |
|-------|-------------|
| < 500ms | ⚡ Eccellente |
| 500-1000ms | 🟢 Buono |
| 1000-2000ms | 🟡 Accettabile |
| > 2000ms | 🔴 Lento |

### Decisione Backend

**Scegli Llama.cpp se:**
- ✅ Velocità è prioritaria
- ✅ Risorse limitate
- ✅ Alto throughput necessario
- ✅ Accuratezza ≥ 90% è sufficiente

**Scegli Ollama se:**
- ✅ Accuratezza massima richiesta (> 95%)
- ✅ Flessibilità modelli importante
- ✅ Debugging e logging dettagliato
- ✅ Velocità non critica

---

## 🔧 Comandi Utili

### Test Singolo Backend

```bash
# Solo Llama.cpp
python3 compare_llm_backends.py --backends llamacpp --quick

# Solo Ollama
python3 compare_llm_backends.py --backends ollama --quick
```

### Benchmark Personalizzato

```bash
# 5 iterazioni, output custom
python3 compare_llm_backends.py \
  --iterations 5 \
  --output my_test.json

# Visualizza
python3 visualize_benchmark.py my_test.json --output my_report.html
```

### Solo Report Testuale

```bash
python3 visualize_benchmark.py benchmark_results.json --summary
```

---

## ❓ FAQ

### Q: Quanto tempo richiede il benchmark completo?
**A:** 5-10 minuti per entrambi i backend con 3 iterazioni.

### Q: Posso testare solo un backend?
**A:** Sì, usa `--backends llamacpp` o `--backends ollama`.

### Q: I risultati variano tra esecuzioni?
**A:** Sì, leggere variazioni sono normali. Usa 3+ iterazioni per risultati più stabili.

### Q: Posso aggiungere test personalizzati?
**A:** Sì, modifica l'array `TEST_CASES` in `compare_llm_backends.py`.

### Q: Come confronto risultati di epoche diverse?
**A:** Usa nomi file descrittivi (es. `before-update.json`, `after-update.json`) e confronta manualmente.

---

## 📞 Troubleshooting

### Backend non disponibile

```bash
# Verifica stato
curl http://localhost:11435/health  # Llama.cpp
curl http://localhost:11434/api/tags  # Ollama

# Avvia se necessario
./start_llama-cpp.sh  # Llama.cpp
ollama serve          # Ollama
```

### Errori di import

```bash
# Assicurati di essere nella directory corretta
cd /opt/lang-env/GiAs-llm/benchmarks
python3 compare_llm_backends.py --quick
```

### Performance molto basse

1. Verifica che il sistema non sia carico
2. Chiudi altre applicazioni pesanti
3. Usa `--iterations 5` per risultati più affidabili

---

## ✅ Checklist Pre-Benchmark

- [ ] Llama.cpp è in esecuzione (porta 11435)
- [ ] Ollama è in esecuzione (porta 11434) - opzionale
- [ ] Sistema non carico (< 70% CPU/RAM)
- [ ] Database PostgreSQL connesso
- [ ] Directory corretta: `GiAs-llm/benchmarks`

---

## 🎓 Esempi Pratici

### Esempio 1: Verifica Rapida

```bash
# Quick test prima di deploy
cd benchmarks
./run_quick_benchmark.sh

# Se OK, procedi con deploy
```

### Esempio 2: Documentazione Performance

```bash
# Benchmark ufficiale con 5 iterazioni
python3 compare_llm_backends.py --iterations 5 --output official.json

# Report HTML per documentazione
python3 visualize_benchmark.py official.json --output official_report.html

# Condividi official_report.html con il team
```

### Esempio 3: Debugging Performance

```bash
# Test solo Llama.cpp con molte iterazioni
python3 compare_llm_backends.py \
  --backends llamacpp \
  --iterations 10 \
  --output debug_llamacpp.json

# Analizza variabilità nei risultati (std dev)
python3 visualize_benchmark.py debug_llamacpp.json --summary
```

---

## 📚 File Generati

| File | Descrizione |
|------|-------------|
| `benchmark_results.json` | Risultati completi in JSON |
| `benchmark_report.html` | Report visuale interattivo |
| `quick_benchmark.json` | Risultati quick test |
| `benchmark_YYYYMMDD_HHMMSS.json` | Risultati con timestamp |

---

## 🎯 Next Steps

Dopo aver eseguito il benchmark:

1. **Analizza i risultati** nel report HTML
2. **Decidi quale backend usare** in base ai tuoi requisiti
3. **Configura il backend scelto** in `config.json`:
   ```json
   {
     "llm_backend": {
       "type": "llamacpp"  // o "ollama"
     }
   }
   ```
4. **Riavvia GiAs-llm** con `./start_server.sh`
5. **Monitora le performance** in produzione

---

**Creato:** 2025-01-28
**Versione:** 1.0.0
**GiAs-llm Development Team**
