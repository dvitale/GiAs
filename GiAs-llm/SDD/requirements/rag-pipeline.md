# Pipeline RAG (Retrieval-Augmented Generation)

**Componente**: Backend (GiAs-llm)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: `tools/procedure_tools.py`, `tools/rag_cache.py`, `tools/hybrid_search/bm25_scorer.py`

## Requisiti Funzionali

### RAG-001 Threshold e complessita' dinamici
- **Pattern EARS**: QUANDO viene ricevuta una query RAG, il sistema DEVE calcolare un threshold di similarita' dinamico basato sulla complessita': query generica (score<=3) -> threshold 0.55, top_k 8, livello "low"; query media (score<=6) -> threshold 0.45, top_k 10, livello "medium"; query specifica (score<=9) -> threshold 0.40, top_k 12, livello "high"; query molto specifica (score>9) -> threshold 0.38, top_k 15, livello "very_high". Lo score di complessita' (0-10+) combina 4 fattori: lunghezza query (1-7 punti), termini di dominio GISA (max +6, 2 per termine da dizionario di ~40 termini), specificatori (+1/+2 punti), penalita' per query generiche (-3 punti).
- **Status**: IMPLEMENTATO
- **Accorpa**: RAG-001, RAG-002, RAG-003

### RAG-004 Query expansion LLM con contesto
- **Pattern EARS**: QUANDO la complessita' della query e' "medium", "high" o "very_high", il sistema DEVE generare 2 riformulazioni della query tramite LLM con temperature 0.3, max_tokens 150, timeout 5 secondi, richiedendo output JSON con chiave "variants". SE la query expansion fallisce (eccezione, timeout, parse error), il sistema DEVE procedere con la sola query originale. DOVE disponibile un conversation_context dalla sessione, il sistema DEVE preporre il contesto alla query di retrieval per la prima variante.
- **Status**: IMPLEMENTATO
- **Accorpa**: RAG-004, RAG-005, RAG-006

### RAG-007 Retrieval multi-variante con deduplicazione
- **Pattern EARS**: Il sistema DEVE eseguire il retrieval per ogni variante della query (originale + espansioni) e deduplicare i chunk risultanti usando i primi 80 caratteri del contenuto come chiave univoca. QUANDO assembla il contesto per il prompt LLM, il sistema DEVE deduplicare i chunk confrontando i primi 100 caratteri (lowercase, strip) del contenuto, saltando chunk con incipit quasi identico.
- **Status**: IMPLEMENTATO
- **Accorpa**: RAG-007, RAG-013

### RAG-008 BM25 + RRF re-ranking
- **Pattern EARS**: QUANDO il numero di chunk recuperati e' >= 3, il sistema DEVE applicare re-ranking ibrido: calcolare score BM25 sui contenuti dei chunk (usando BM25Okapi con fallback TF semplificato se non disponibile, e score 0.0 come fallback finale), combinare con score vettoriali tramite Reciprocal Rank Fusion (RRF(d) = 1/(k + rank_vector(d)) + 1/(k + rank_bm25(d)), k=60), e riordinare per score RRF decrescente.
- **Status**: IMPLEMENTATO
- **Accorpa**: RAG-008, RAG-009, RAG-010

### RAG-011 Post-filtering adattivo
- **Pattern EARS**: QUANDO ci sono piu' di 3 chunk dopo il re-ranking, il sistema DEVE applicare un filtro adattivo: per query "low" -> soglia minima = threshold + 0.10; per altre complessita' -> soglia minima = threshold + 0.05. Il filtro viene applicato solo se almeno 2 chunk superano la soglia.
- **Status**: IMPLEMENTATO

### RAG-012 Limite massimo chunk per contesto LLM
- **Pattern EARS**: Il sistema DEVE limitare a massimo 5 i chunk migliori passati come contesto al LLM per la generazione della risposta.
- **Status**: IMPLEMENTATO

### RAG-014 Citazioni inline e fonti
- **Pattern EARS**: Il sistema DEVE istruire il LLM (via RAG_SYSTEM_PROMPT) ad aggiungere citazioni inline nel formato [Fonte N] dopo ogni affermazione chiave, formattando il contesto con header "[Fonte N: titolo - sezione (pag. X)]". QUANDO la risposta RAG viene generata, il sistema DEVE appendere una sezione "**Fonti:**" con lista deduplica per file+pagina e una sezione "**Documenti scaricabili:**" con link download per ogni file sorgente univoco.
- **Status**: IMPLEMENTATO
- **Accorpa**: RAG-014, RAG-015

### RAG-016 Cache RAG thread-safe con TTL e statistiche
- **Pattern EARS**: Il sistema DEVE mantenere una cache delle risposte RAG singleton e thread-safe (threading.Lock) con: chiave MD5 della query normalizzata, TTL 1800 secondi (configurabile), dimensione massima 200 entry (configurabile). QUANDO la cache supera max_size, il sistema DEVE rimuovere le entry piu' vecchie fino all'80% della capacita'. Il sistema DEVE tracciare e esporre statistiche: hits, misses, total_requests, hit_rate_percent, cache_size, max_size, evictions, ttl_seconds.
- **Status**: IMPLEMENTATO
- **Accorpa**: RAG-016, RAG-017, RAG-018

### RAG-019 Fallback, risposta vuota e confidenza
- **Pattern EARS**: SE la chiamata LLM per generare la risposta RAG fallisce o restituisce vuoto, il sistema DEVE restituire i chunk grezzi formattati come lista numerata con titolo, sezione e primi 300 caratteri. SE nessun chunk supera il threshold, il sistema DEVE restituire un messaggio "no_results" con 3 suggerimenti di riformulazione. Il sistema DEVE calcolare un livello di confidenza basato sullo score medio dei chunk: avg_score >= 0.65 -> "high", >= 0.50 -> "medium", altrimenti "low".
- **Status**: IMPLEMENTATO
- **Accorpa**: RAG-019, RAG-020, RAG-021

### RAG-022 Metadati chunk per suggerimenti dinamici
- **Pattern EARS**: Il sistema DEVE estrarre e restituire metadati leggeri dai chunk (title, section, source_file, page_num, score arrotondato a 3 decimali) nel campo `chunks_metadata` per alimentare i suggerimenti follow-up dinamici.
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### RAG-NF-001 Tokenizzazione BM25 semplificata
- **Pattern EARS**: Il sistema DEVE tokenizzare il testo per BM25 usando: conversione lowercase, estrazione token alfanumerici di almeno 2 caratteri tramite regex `\b\w{2,}\b`.
- **Status**: IMPLEMENTATO

### RAG-NF-002 Performance BM25 on-the-fly
- **Pattern EARS**: Il sistema DEVE calcolare BM25 on-the-fly sui chunk gia' recuperati (8-15 chunk) senza mantenere un indice BM25 globale persistente, con latenza target < 1ms.
- **Status**: IMPLEMENTATO

### RAG-NF-003 RAG System Prompt con regole fondamentali
- **Pattern EARS**: Il sistema DEVE istruire il LLM via RAG_SYSTEM_PROMPT a: rispondere solo con informazioni dal contesto, ignorare riferimenti a figure/immagini, usare liste numerate per passaggi, non mescolare procedure diverse, integrare fonti in risposta coerente, segnalare contraddizioni tra fonti, non inventare passaggi.
- **Status**: IMPLEMENTATO

### RAG-NF-004 Configurabilita' cache da config.json
- **Pattern EARS**: DOVE disponibile un file config.json con sezione `rag_documents`, il sistema DEVE leggere `cache_ttl_seconds` e `cache_max_size` dalla configurazione, usando 1800 e 200 come valori di default.
- **Status**: IMPLEMENTATO
