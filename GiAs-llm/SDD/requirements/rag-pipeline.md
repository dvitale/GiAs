# Pipeline RAG (Retrieval-Augmented Generation)

**Componente**: Backend (GiAs-llm)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: `tools/procedure_tools.py`, `tools/rag_cache.py`, `tools/hybrid_search/bm25_scorer.py`

## Requisiti Funzionali

### RAG-001 Threshold dinamico per complessita' query
- **Pattern EARS**: QUANDO viene ricevuta una query RAG, il sistema DEVE calcolare un threshold di similarita' dinamico basato sulla complessita': query generica (score<=3) -> threshold 0.55, top_k 8, livello "low"; query media (score<=6) -> threshold 0.45, top_k 10, livello "medium"; query specifica (score<=9) -> threshold 0.40, top_k 12, livello "high"; query molto specifica (score>9) -> threshold 0.38, top_k 15, livello "very_high".
- **Status**: IMPLEMENTATO

### RAG-002 Score di complessita' multi-fattore
- **Pattern EARS**: Il sistema DEVE calcolare lo score di complessita' (0-10+) combinando 4 fattori: lunghezza query (1-7 punti per 1-3/4-6/7-10/11+ parole), termini di dominio GISA presenti (max +6 punti, 2 per termine), specificatori ("specifico", "dettaglio", "esatto", "preciso" = +2; "grave", "critico", "urgente", "importante" = +1), penalita' per query troppo generiche (pattern regex, -3 punti).
- **Status**: IMPLEMENTATO

### RAG-003 Termini di dominio GISA
- **Pattern EARS**: Il sistema DEVE mantenere un dizionario di circa 40 termini di dominio GISA (procedure, settori, entita', documenti, animali) per la valutazione della specificita' della query.
- **Status**: IMPLEMENTATO

### RAG-004 Query expansion via LLM
- **Pattern EARS**: QUANDO la complessita' della query e' "medium", "high" o "very_high", il sistema DEVE generare 2 riformulazioni della query tramite LLM con temperature 0.3, max_tokens 150, timeout 5 secondi, richiedendo output JSON con chiave "variants".
- **Status**: IMPLEMENTATO

### RAG-005 Fallback query expansion
- **Pattern EARS**: SE la query expansion via LLM fallisce (eccezione, timeout, parse error), il sistema DEVE procedere con la sola query originale senza varianti.
- **Status**: IMPLEMENTATO

### RAG-006 Arricchimento query con contesto conversazionale
- **Pattern EARS**: DOVE disponibile un conversation_context dalla sessione, il sistema DEVE preporre il contesto alla query di retrieval per la prima variante, formando una retrieval_query composta "{contesto} {query}".
- **Status**: IMPLEMENTATO

### RAG-007 Retrieval multi-variante con deduplicazione
- **Pattern EARS**: Il sistema DEVE eseguire il retrieval per ogni variante della query (originale + espansioni) e deduplicare i chunk risultanti usando i primi 80 caratteri del contenuto come chiave univoca.
- **Status**: IMPLEMENTATO

### RAG-008 BM25 + RRF re-ranking
- **Pattern EARS**: QUANDO il numero di chunk recuperati e' >= 3, il sistema DEVE applicare re-ranking ibrido: calcolare score BM25 sui contenuti dei chunk, combinare con score vettoriali tramite Reciprocal Rank Fusion (RRF) con parametro k=60, e riordinare per score RRF decrescente.
- **Status**: IMPLEMENTATO

### RAG-009 BM25 scoring con fallback TF
- **Pattern EARS**: QUANDO viene calcolato lo score BM25, il sistema DEVE usare la libreria rank-bm25 (BM25Okapi). SE rank-bm25 non e' disponibile, il sistema DEVE usare un fallback TF semplificato (match_count / total_tokens). SE anche il fallback fallisce, il sistema DEVE restituire score 0.0 per tutti i chunk.
- **Status**: IMPLEMENTATO

### RAG-010 Formula RRF
- **Pattern EARS**: Il sistema DEVE calcolare lo score RRF combinato come: RRF(d) = 1/(k + rank_vector(d)) + 1/(k + rank_bm25(d)), dove k=60 (standard) e rank 1 = migliore.
- **Status**: IMPLEMENTATO

### RAG-011 Post-filtering adattivo
- **Pattern EARS**: QUANDO ci sono piu' di 3 chunk dopo il re-ranking, il sistema DEVE applicare un filtro adattivo: per query "low" -> soglia minima = threshold + 0.10; per altre complessita' -> soglia minima = threshold + 0.05. Il filtro viene applicato solo se almeno 2 chunk superano la soglia.
- **Status**: IMPLEMENTATO

### RAG-012 Limite massimo chunk per contesto LLM
- **Pattern EARS**: Il sistema DEVE limitare a massimo 5 i chunk migliori passati come contesto al LLM per la generazione della risposta.
- **Status**: IMPLEMENTATO

### RAG-013 Deduplicazione contesto (100 caratteri)
- **Pattern EARS**: QUANDO assembla il contesto per il prompt LLM, il sistema DEVE deduplicare i chunk confrontando i primi 100 caratteri (lowercase, strip) del contenuto, saltando chunk con incipit quasi identico.
- **Status**: IMPLEMENTATO

### RAG-014 Citazioni inline [Fonte N]
- **Pattern EARS**: Il sistema DEVE istruire il LLM (via RAG_SYSTEM_PROMPT) ad aggiungere citazioni inline nel formato [Fonte N] dopo ogni affermazione chiave, e DEVE formattare il contesto con header "[Fonte N: titolo - sezione (pag. X)]" per ogni chunk.
- **Status**: IMPLEMENTATO

### RAG-015 Sezione fonti con titolo, file e pagina
- **Pattern EARS**: QUANDO la risposta RAG viene generata, il sistema DEVE appendere una sezione "**Fonti:**" con: lista deduplica per file+pagina ("- titolo (file, pag. N)"), e una sezione "**Documenti scaricabili:**" con link download per ogni file sorgente univoco nel formato "/gias/webchat/api/admin/documents/{filename_encoded}".
- **Status**: IMPLEMENTATO

### RAG-016 RAG Cache con TTL e dimensione massima
- **Pattern EARS**: Il sistema DEVE mantenere una cache delle risposte RAG con: chiave MD5 della query normalizzata (lowercase, strip), TTL 1800 secondi (30 minuti, configurabile), dimensione massima 200 entry (configurabile). La cache e' thread-safe (threading.Lock) e singleton.
- **Status**: IMPLEMENTATO

### RAG-017 Eviction cache per superamento dimensione
- **Pattern EARS**: QUANDO la cache supera max_size dopo un inserimento, il sistema DEVE rimuovere le entry piu' vecchie fino a raggiungere l'80% della capacita' massima (target = max_size * 0.8).
- **Status**: IMPLEMENTATO

### RAG-018 Statistiche cache RAG
- **Pattern EARS**: Il sistema DEVE tracciare e esporre statistiche della cache: hits, misses, total_requests, hit_rate_percent, cache_size, max_size, evictions, ttl_seconds.
- **Status**: IMPLEMENTATO

### RAG-019 Fallback chunk grezzi se LLM non disponibile
- **Pattern EARS**: SE la chiamata LLM per generare la risposta RAG fallisce o restituisce vuoto, il sistema DEVE restituire i chunk grezzi formattati come lista numerata con titolo, sezione e primi 300 caratteri del contenuto.
- **Status**: IMPLEMENTATO

### RAG-020 Risposta per nessun risultato RAG
- **Pattern EARS**: SE nessun chunk supera il threshold di similarita', il sistema DEVE restituire un messaggio di "no_results" con suggerimenti di riformulazione (3 esempi di domande).
- **Status**: IMPLEMENTATO

### RAG-021 Livello di confidenza risposta RAG
- **Pattern EARS**: Il sistema DEVE calcolare un livello di confidenza basato sullo score medio dei chunk: avg_score >= 0.65 -> "high", avg_score >= 0.50 -> "medium", altrimenti -> "low".
- **Status**: IMPLEMENTATO

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
