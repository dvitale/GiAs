# Hybrid Search

**Componente**: Backend (GiAs-llm)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: `tools/hybrid_search/hybrid_engine.py`, `tools/hybrid_search/smart_router.py`, `tools/hybrid_search/query_analyzer.py`, `tools/hybrid_search/llm_reranker.py`

## Requisiti Funzionali

### HS-01 Tre modalita' di ricerca
- **Pattern EARS**: Il sistema DEVE supportare 3 strategie di ricerca: VECTOR_ONLY (priorita' velocita'), HYBRID (vector retrieval + LLM reranking) e LLM_ONLY (comprensione semantica). LLM_ONLY non viene piu' instradato direttamente: tutte le query non-vector vengono indirizzate a HYBRID.
- **Status**: IMPLEMENTATO

### HS-02 Smart routing rules con priorita'
- **Pattern EARS**: Il sistema DEVE applicare regole di routing con priorita': (1) MENTRE cpu_mode e' attivo E il backend LLM e' locale, forzare VECTOR_ONLY; (2) QUANDO il tipo di query e' "exact_code" (pattern codici piano), selezionare VECTOR_ONLY; (3) QUANDO il complexity_score supera 0.7, selezionare HYBRID; (4) QUANDO il complexity_score e' < 0.3 senza indicatori semantici, selezionare VECTOR_ONLY; (5) QUANDO il carico sistema supera 0.9, declassare HYBRID a VECTOR_ONLY; 0.8 preferire strategie leggere.
- **Status**: IMPLEMENTATO
- **Accorpa**: HS-02, HS-03, HS-04, HS-05, HS-06

### HS-07 Analisi complessita' query
- **Pattern EARS**: Il sistema DEVE analizzare ogni query calcolando: complexity_score (0-1 basato su pattern grammaticali, conteggio parole, parole-domanda, parole relazionali, termini dominio), query_type (exact_code, simple_keyword, question, semantic_relationship, domain_specific, general), domain_terms (da un vocabolario veterinario di ~100 termini italiani) e semantic_indicators (17 indicatori come "riguardano", "correlato", "simile").
- **Status**: IMPLEMENTATO

### HS-08 LLM reranker con timeout e fallback
- **Pattern EARS**: QUANDO la strategia HYBRID e' selezionata E ci sono almeno min_candidates_for_reranking (5) candidati, il sistema DEVE invocare l'LLM reranker con timeout configurabile (default 5000ms), temperature 0.1, max_tokens 500, json_mode=true. SE la chiamata LLM primaria fallisce, il sistema DEVE tentare un prompt semplificato; SE anche questo fallisce, DEVE restituire i candidati nell'ordine del vector search con confidence_score=0.6 e fallback_used=True.
- **Status**: IMPLEMENTATO
- **Accorpa**: HS-08, HS-09

### HS-10 Validazione alias piani nei risultati
- **Pattern EARS**: QUANDO la ricerca restituisce risultati, il sistema DEVE validare ogni alias piano verificando che esista nel database tramite DataRetriever.get_piano_by_id(), filtrando gli alias allucinati dall'LLM. In caso di errore nella validazione, il match viene mantenuto (fail-open).
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### HS-NF01 Performance tracker e emergency fallback
- **Pattern EARS**: Il sistema DEVE tracciare le performance di ogni ricerca (query, strategia, latenza, risultato) tramite PerformanceTracker e mantenere statistiche di routing. SE tutte le strategie falliscono, il sistema DEVE tentare una ricerca keyword di base con threshold 0.2 limitata a 5 risultati; SE anche questa fallisce, DEVE restituire "Sistema di ricerca temporaneamente non disponibile".
- **Status**: IMPLEMENTATO
- **Accorpa**: HS-NF01, HS-NF02

### HS-NF03 Deduplicazione e JSON parsing robusto
- **Pattern EARS**: QUANDO i risultati semantici e keyword vengono combinati, il sistema DEVE deduplicare per alias dando priorita' ai match semantici. Il sistema DEVE parsare la risposta LLM con catena di fallback: JSON diretto, estrazione da blocchi ```json, estrazione JSON bilanciato, parsing fallback con regex.
- **Status**: IMPLEMENTATO
- **Accorpa**: HS-NF03, HS-NF04
