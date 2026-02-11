# GiAs-llm Test Report

**Data**: 2026-01-23 20:38:42
**Test Suite**: test_server.py v3.0
**Server**: http://localhost:5005

---

## Riepilogo Esecuzione

| Metrica | Valore |
|---------|--------|
| **Test Passati** | 51 |
| **Test Falliti** | 0 |
| **Test Skipped** | 1 |
| **Success Rate** | 100% |
| **Tempo Medio Risposta** | 2.208s |
| **Stato Sistema** | ✅ EXCELLENT |

---

## 1. System Status

| Componente | Stato |
|------------|-------|
| API Endpoint | ✅ Operativo |
| LLM Model | llama3.2:3b (real) |
| Framework | LangGraph |
| Piani Caricati | 730 |
| Controlli Caricati | 355,448 |
| Memoria Server | ~3758 MB |

---

## 2. Intent Classification (40/40 - 100%)

### Greet/Goodbye
| Query | Intent | Tempo | Stato |
|-------|--------|-------|-------|
| "ciao" | greet | 0.70s | ✅ |
| "buongiorno" | greet | 0.49s | ✅ |
| "arrivederci" | goodbye | 0.49s | ✅ |
| "grazie e arrivederci" | goodbye | 0.48s | ✅ |

### Help
| Query | Intent | Tempo | Stato |
|-------|--------|-------|-------|
| "aiuto" | ask_help | 0.49s | ✅ |
| "cosa puoi fare" | ask_help | 0.49s | ✅ |
| "che domande posso farti" | ask_help | 0.49s | ✅ |

### Piano Description
| Query | Intent | Tempo | Stato |
|-------|--------|-------|-------|
| "di cosa tratta il piano A1" | ask_piano_description | 1.50s | ✅ |
| "cosa prevede il piano B2" | ask_piano_description | 1.50s | ✅ |

### Piano Stabilimenti
| Query | Intent | Tempo | Stato |
|-------|--------|-------|-------|
| "stabilimenti controllati piano A1" | ask_piano_stabilimenti | 1.55s | ✅ |
| "dove è stato applicato il piano A32" | ask_piano_stabilimenti | 1.78s | ✅ |

### Piano Attività
| Query | Intent | Tempo | Stato |
|-------|--------|-------|-------|
| "attività piano A1" | ask_piano_attivita | 1.72s | ✅ |
| "quali attività riguarda il piano B2" | ask_piano_attivita | 1.75s | ✅ |

### Piano Generic
| Query | Intent | Tempo | Stato |
|-------|--------|-------|-------|
| "dimmi del piano A1" | ask_piano_generic | 1.54s | ✅ |
| "parlami del piano C3" | ask_piano_generic | 1.68s | ✅ |

### Piano Statistics
| Query | Intent | Tempo | Stato |
|-------|--------|-------|-------|
| "statistiche sui piani di controllo" | ask_piano_statistics | 2.04s | ✅ |
| "quali sono i piani più usati" | ask_piano_statistics | 2.53s | ✅ |
| "quale piano è più frequente" | ask_piano_statistics | 2.70s | ✅ |

### Search Piani
| Query | Intent | Tempo | Stato |
|-------|--------|-------|-------|
| "piani su allevamenti" | search_piani_by_topic | 0.95s | ✅ |
| "quali piani riguardano la macellazione" | search_piani_by_topic | 0.72s | ✅ |
| "cerca piani su latte" | search_piani_by_topic | 0.70s | ✅ |

### Priority Establishment
| Query | Intent | Tempo | Stato |
|-------|--------|-------|-------|
| "chi devo controllare per primo" | ask_priority_establishment | 9.05s | ✅ |
| "quali stabilimenti controllare" | ask_priority_establishment | 12.07s | ✅ |
| "cosa devo fare oggi" | ask_priority_establishment | 10.19s | ✅ |

### Risk-Based Priority
| Query | Intent | Tempo | Stato |
|-------|--------|-------|-------|
| "stabilimenti ad alto rischio" | ask_risk_based_priority | 2.39s | ✅ |
| "stabilimenti più rischiosi" | ask_risk_based_priority | 1.03s | ✅ |

### Suggest Controls
| Query | Intent | Tempo | Stato |
|-------|--------|-------|-------|
| "suggerisci controlli" | ask_suggest_controls | 10.61s | ✅ |
| "quali stabilimenti non sono mai stati controllati" | ask_suggest_controls | 2.07s | ✅ |

### Delayed Plans
| Query | Intent | Tempo | Stato |
|-------|--------|-------|-------|
| "piani in ritardo" | ask_delayed_plans | 6.62s | ✅ |
| "quali piani sono in ritardo" | ask_delayed_plans | 1.62s | ✅ |

### Check Plan Delayed
| Query | Intent | Tempo | Stato |
|-------|--------|-------|-------|
| "il piano B47 è in ritardo" | check_if_plan_delayed | 13.40s | ✅ |
| "verifica se il piano A1 è in ritardo" | check_if_plan_delayed | 11.15s | ✅ |

### Establishment History
| Query | Intent | Tempo | Stato |
|-------|--------|-------|-------|
| "storico controlli stabilimento IT 2287" | ask_establishment_history | 3.52s | ✅ |
| "controlli per partita IVA 12345678901" | ask_establishment_history | 2.24s | ✅ |
| "storia dei controlli per stabilimento SEPE" | ask_establishment_history | 3.14s | ✅ |

### Top Risk Activities
| Query | Intent | Tempo | Stato |
|-------|--------|-------|-------|
| "attività più rischiose" | ask_top_risk_activities | 1.43s | ✅ |
| "classifica attività per rischio" | ask_top_risk_activities | 1.00s | ✅ |
| "top 10 attività a rischio" | ask_top_risk_activities | 1.11s | ✅ |

### NC Analysis
| Query | Intent | Tempo | Stato |
|-------|--------|-------|-------|
| "analizza le non conformità HACCP" | analyze_nc_by_category | 6.81s | ✅ |
| "NC categoria IGIENE DEGLI ALIMENTI" | analyze_nc_by_category | 7.28s | ✅ |

---

## 3. Performance Benchmark

| Query | Tempo | Valutazione |
|-------|-------|-------------|
| "ciao" | ~1.1s | ⚠️ Acceptable |
| "aiuto" | ~0.9s | ✅ Good |
| "piano A1" | ~6.3s | ⚠️ Slow |
| "stabilimenti rischio" | ~1.6s | ⚠️ Acceptable |

**Media**: 2.208s (Acceptable)

---

## 4. ML Predictor

| ASL | Stabilimenti Identificati | Stato |
|-----|---------------------------|-------|
| AVELLINO | 26 | ✅ |
| NAPOLI 1 CENTRO | 27 | ✅ |
| SALERNO | 25 | ✅ |

---

## 5. Error Handling

| Test Case | Stato |
|-----------|-------|
| Empty message | ✅ Gestito |
| Invalid ASL | ✅ Gestito gracefully |
| Long query | ✅ Gestito |
| Special characters | ✅ Gestito |

---

## 6. Cache Verification

| Run | Tempo |
|-----|-------|
| 1 | 0.47s |
| 2 | 0.46s |
| 3 | 0.45s |

**Risultato**: ✅ Cache funzionante (tempi stabili)

---

## 7. Concurrent Requests

| Richieste Parallele | Successo |
|---------------------|----------|
| 4 | 4/4 (100%) |

---

## Correzioni Applicate

**Nessuna correzione necessaria** - Tutti i test sono passati con successo.

---

## Raccomandazioni Performance

Anche se tutti i test sono passati, si notano alcune aree di miglioramento:

1. **Query "piano A1"**: Tempo elevato (~6.3s). Potrebbe beneficiare di caching più aggressivo.
2. **Priority queries**: Tempi >10s per alcune query complesse. Normale per query che richiedono aggregazioni su grandi dataset.
3. **Check plan delayed**: Tempi >10s. Query che richiede calcoli complessi su programmazione vs esecuzione.

---

## Conclusioni

| Aspetto | Valutazione |
|---------|-------------|
| Funzionalità | ✅ 100% operativa |
| Classificazione Intent | ✅ 100% accuratezza |
| Error Handling | ✅ Robusto |
| Concorrenza | ✅ Stabile |
| Performance | ⚠️ Acceptable (2.2s avg) |

**STATO SISTEMA: ✅ EXCELLENT**

---

*Report generato automaticamente da test_server.py v3.0*
