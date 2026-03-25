# Requisiti Non Funzionali Trasversali

**Componente**: Backend (GiAs-llm)
**Provenienza**: Consolidamento da requisiti cross-file, 2026-03-16

## Requisiti Non Funzionali Trasversali

### XNF-BE-01 Singleton pattern lazy loading
- **Pattern EARS**: Il sistema DEVE implementare come singleton con lazy loading i seguenti componenti: QdrantClient, embedding model, SchemaCatalog, IntentMetadataService, GeocodingService, RAGCache, FewShotRetriever, FollowUpSuggestionEngine, Config loader. L'inizializzazione DEVE avvenire al primo utilizzo, non all'import.
- **Status**: IMPLEMENTATO
- **Accorpa pattern da**: QE-NF01 (qdrant-embeddings), API-NF03 (api-endpoints), CF-10 (configuration), GP-NF01 (geocoding-proximity), RG-NF-002 (response-generation)

### XNF-BE-02 Thread-safety tramite lock
- **Pattern EARS**: Il sistema DEVE garantire operazioni thread-safe sulle risorse condivise (sessioni, cache intent, cache RAG) tramite meccanismi di lock appropriati (threading.Lock per sessioni, Python GIL per dict).
- **Status**: IMPLEMENTATO
- **Accorpa pattern da**: SM-002 (session-management), IC-NF-003 (intent-classification)

### XNF-BE-03 Copia dati per isolamento
- **Pattern EARS**: Il sistema DEVE restituire copie dei dati di sessione (non riferimenti diretti) per evitare modifiche concorrenti non intenzionali.
- **Status**: IMPLEMENTATO
- **Accorpa pattern da**: SM-NF-001 (session-management)

### XNF-BE-04 Graceful degradation su errore
- **Pattern EARS**: QUANDO un componente non e' disponibile (LLM, Qdrant, ML predictor, hybrid search), il sistema DEVE degradare a un'alternativa funzionale (stub, lista vuota, rule-based, ILIKE testuale) senza generare errori non gestiti.
- **Status**: IMPLEMENTATO
- **Accorpa pattern da**: LC-005 (llm-client), RA-05 (risk-analysis), HS-NF02 (hybrid-search), QE-03 (qdrant-embeddings)

### XNF-BE-05 Logging strutturato con prefissi
- **Pattern EARS**: Il sistema DEVE utilizzare logging strutturato con prefissi specifici per componente ([Session], [Router], [Cache], [RAG], [LLM], etc.) per facilitare il debug e il monitoraggio.
- **Status**: IMPLEMENTATO
- **Accorpa pattern da**: SM-NF-002 (session-management), LC-NF-002 (llm-client)

### XNF-BE-06 Fallback recovery chain
- **Pattern EARS**: Il sistema DEVE implementare chain di fallback a cascata per i componenti critici: LLM (provider → stub), ricerca (hybrid → vector → ILIKE), predittore (ML → rule-based → emergenza), RAG (LLM sintesi → chunk grezzi).
- **Status**: IMPLEMENTATO
- **Accorpa pattern da**: pattern ricorrente in llm-client, risk-analysis, hybrid-search, rag-pipeline, fallback-recovery

### XNF-BE-07 JSON parsing robusto con fallback
- **Pattern EARS**: Il sistema DEVE parsare risposte JSON con chain di fallback: (1) json.loads diretto, (2) estrazione da blocchi ```json```, (3) parser a parentesi bilanciate. Questo si applica a: classificazione intent, LLM reranker, query builder.
- **Status**: IMPLEMENTATO
- **Accorpa pattern da**: IC-037 (intent-classification), HS-NF04 (hybrid-search)

### XNF-BE-08 Cache con TTL e eviction
- **Pattern EARS**: Il sistema DEVE implementare caching con TTL e politica di eviction per: intent cache (TTL 3600s, max 1000), RAG cache (TTL 1800s, max 200), keyword fallback cache, geocoding cache (LRU 500). L'eviction DEVE rimuovere il 20% delle entry piu' vecchie al raggiungimento della capacita' massima.
- **Status**: IMPLEMENTATO
- **Accorpa pattern da**: IC-021..022 (intent-classification), RAG-016..017 (rag-pipeline), FR-004 (fallback-recovery), GP-06 (geocoding-proximity)

### XNF-BE-09 Configurabilita' config.json con fallback
- **Pattern EARS**: Il sistema DEVE leggere i parametri di configurazione da config.json con fallback a valori default hardcoded. Ogni parametro DEVE avere un default funzionale che permette l'avvio senza config.json.
- **Status**: IMPLEMENTATO
- **Accorpa pattern da**: CF-01 (configuration), FR-NF-002 (fallback-recovery), RAG-NF-004 (rag-pipeline)

### XNF-BE-10 Precaricamento dati al startup
- **Pattern EARS**: Il sistema DEVE precaricare dati critici (DataFrame, metadati intent, catalogo schema) durante il lifecycle startup di FastAPI per ridurre la latenza della prima richiesta.
- **Status**: IMPLEMENTATO
- **Accorpa pattern da**: API-NF04 (api-endpoints), DL-10 (data-layer)
