# Hybrid Search

**Componente**: Backend (GiAs-llm)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: `tools/hybrid_search/hybrid_engine.py`, `tools/hybrid_search/smart_router.py`, `tools/hybrid_search/query_analyzer.py`, `tools/hybrid_search/llm_reranker.py`

## Requisiti Funzionali

### HS-01 Tre modalita' di ricerca
- **Pattern EARS**: Il sistema DEVE supportare 3 strategie di ricerca: VECTOR_ONLY (priorita' velocita'), HYBRID (vector retrieval + LLM reranking) e LLM_ONLY (comprensione semantica). LLM_ONLY non viene piu' instradato direttamente: tutte le query non-vector vengono indirizzate a HYBRID.
- **Status**: IMPLEMENTATO

### HS-02 Smart routing - gate cpu_mode
- **Pattern EARS**: MENTRE cpu_mode e' attivo in config.json E il backend LLM e' locale (non cloud), il sistema DEVE forzare la strategia VECTOR_ONLY per tutte le query, disabilitando il reranking LLM.
- **Status**: IMPLEMENTATO

### HS-03 Smart routing - exact_code
- **Pattern EARS**: QUANDO il tipo di query e' "exact_code" (pattern ^[A-Z]\d+[_-]?\w*$, come codici piano A1, B23), il sistema DEVE selezionare VECTOR_ONLY per lookup rapido.
- **Status**: IMPLEMENTATO

### HS-04 Smart routing - alta complessita'
- **Pattern EARS**: QUANDO il complexity_score della query supera 0.7 (threshold_high), il sistema DEVE selezionare HYBRID per garantire sia recall che precision.
- **Status**: IMPLEMENTATO

### HS-05 Smart routing - bassa complessita'
- **Pattern EARS**: QUANDO il complexity_score e' inferiore a 0.3 (threshold_low) E non ci sono indicatori semantici, il sistema DEVE selezionare VECTOR_ONLY come ricerca semplice per keyword.
- **Status**: IMPLEMENTATO

### HS-06 Smart routing - alto carico sistema
- **Pattern EARS**: QUANDO il carico sistema supera 0.9, il sistema DEVE declassare HYBRID a VECTOR_ONLY. QUANDO supera 0.8, il sistema DEVE preferire strategie piu' leggere.
- **Status**: IMPLEMENTATO

### HS-07 Analisi complessita' query
- **Pattern EARS**: Il sistema DEVE analizzare ogni query calcolando: complexity_score (0-1 basato su pattern grammaticali, conteggio parole, parole-domanda, parole relazionali, termini dominio), query_type (exact_code, simple_keyword, question, semantic_relationship, domain_specific, general), domain_terms (da un vocabolario veterinario di ~100 termini italiani) e semantic_indicators (17 indicatori come "riguardano", "correlato", "simile").
- **Status**: IMPLEMENTATO

### HS-08 LLM reranker con timeout
- **Pattern EARS**: QUANDO la strategia HYBRID e' selezionata E ci sono almeno min_candidates_for_reranking (5) candidati dal vector retrieval, il sistema DEVE invocare l'LLM reranker con timeout configurabile (default 5000ms convertito in secondi), temperature 0.1, max_tokens 500 e json_mode=true.
- **Status**: IMPLEMENTATO

### HS-09 Fallback chain LLM reranker
- **Pattern EARS**: SE la chiamata LLM primaria fallisce, il sistema DEVE tentare un prompt semplificato come fallback. SE anche questo fallisce, il sistema DEVE restituire i candidati nell'ordine del vector search con confidence_score=0.6 e fallback_used=True.
- **Status**: IMPLEMENTATO

### HS-10 Validazione alias piani nei risultati
- **Pattern EARS**: QUANDO la ricerca restituisce risultati, il sistema DEVE validare ogni alias piano verificando che esista nel database tramite DataRetriever.get_piano_by_id(), filtrando gli alias allucinati dall'LLM. In caso di errore nella validazione, il match viene mantenuto (fail-open).
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### HS-NF01 Performance tracker
- **Pattern EARS**: Il sistema DEVE tracciare le performance di ogni ricerca (query, strategia, latenza, risultato) tramite PerformanceTracker e mantenere statistiche di routing (conteggi per strategia, ultime 100 decisioni, complessita' media, distribuzione tipi query).
- **Status**: IMPLEMENTATO

### HS-NF02 Emergency fallback
- **Pattern EARS**: SE tutte le strategie di ricerca falliscono con eccezione critica, il sistema DEVE tentare una ricerca keyword di base con threshold 0.2 limitata a 5 risultati. SE anche questa fallisce, DEVE restituire un messaggio "Sistema di ricerca temporaneamente non disponibile".
- **Status**: IMPLEMENTATO

### HS-NF03 Deduplicazione candidati
- **Pattern EARS**: QUANDO i risultati semantici e keyword vengono combinati nel primo stadio della ricerca hybrid, il sistema DEVE deduplicare per alias dando priorita' ai match semantici.
- **Status**: IMPLEMENTATO

### HS-NF04 Parsing JSON robusto LLM response
- **Pattern EARS**: Il sistema DEVE parsare la risposta LLM con una catena di fallback: 1) JSON diretto, 2) estrazione da blocchi ```json, 3) estrazione JSON bilanciato, 4) parsing fallback con estrazione alias tramite regex. Se manca reranked_plans, DEVE restituire None.
- **Status**: IMPLEMENTATO
