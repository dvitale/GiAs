# Classificazione Intent

**Componente**: Backend (GiAs-llm)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: `orchestrator/router.py`, `orchestrator/intent_cache.py`, `orchestrator/few_shot_retriever.py`, `orchestrator/intent_metadata.py`

## Requisiti Funzionali

### IC-001 Pipeline a 6 livelli
- **Pattern EARS**: Il sistema DEVE classificare ogni messaggio attraverso una pipeline a 6 livelli in ordine: (0) gibberish detection, (1) pending slot fill, (2) heuristics, (3) pre-parse regex + (4) cache, (5) LLM few-shot, (6) local fallback.
- **Status**: IMPLEMENTATO

### IC-002 Valid intents
- **Pattern EARS**: Il sistema DEVE riconoscere esattamente 20+1 intent validi: greet, goodbye, ask_help, ask_piano_stabilimenti, ask_piano_description, ask_piano_statistics, search_piani_by_topic, ask_priority_establishment, ask_risk_based_priority, ask_suggest_controls, ask_nearby_priority, ask_delayed_plans, check_if_plan_delayed, ask_establishment_history, ask_top_risk_activities, analyze_nc_by_category, info_procedure, query_data, confirm_show_details, decline_show_details, fallback.
- **Status**: IMPLEMENTATO

### IC-003 Valid slot keys
- **Pattern EARS**: Il sistema DEVE accettare solo slot con chiavi appartenenti al set: piano_code, asl, topic, num_registrazione, numero_riconoscimento, partita_iva, ragione_sociale, categoria, location, radius_km, sezione, macroarea, aggregazione, anno, comune, table, operation, filters, group_by, order_by, limit.
- **Status**: IMPLEMENTATO

### IC-004 Required slots per intent
- **Pattern EARS**: Il sistema DEVE verificare la presenza di slot obbligatori: piano_code per ask_piano_description, ask_piano_stabilimenti, check_if_plan_delayed; topic per search_piani_by_topic; almeno uno tra num_registrazione/numero_riconoscimento/partita_iva/ragione_sociale per ask_establishment_history; categoria per analyze_nc_by_category; location per ask_nearby_priority.
- **Status**: IMPLEMENTATO

### IC-005 MINIMAL_HEURISTICS flag
- **Pattern EARS**: DOVE il flag MINIMAL_HEURISTICS e' True, il sistema DEVE delegare all'LLM tutte le classificazioni eccetto confirm/decline, disambiguazione rischio, e le heuristics essenziali.
- **Status**: IMPLEMENTATO
- **Note**: Flag attualmente impostato a True.

### IC-006 Heuristic confirm_show_details (esplicito e breve)
- **Pattern EARS**: QUANDO il messaggio matcha CONFIRM_EXPLICIT_PATTERNS (es. "si mostrami", "vediamo tutti"), il sistema DEVE classificare come confirm_show_details con confidence 0.99 senza richiedere detail_context. QUANDO il messaggio matcha CONFIRM_SHORT_PATTERNS (es. "si", "ok", "vai") E esiste un detail_context attivo, il sistema DEVE classificare come confirm_show_details con confidence 0.99.
- **Status**: IMPLEMENTATO
- **Accorpa**: IC-006, IC-007

### IC-008 Heuristic decline_show_details (esplicito e breve)
- **Pattern EARS**: QUANDO il messaggio matcha DECLINE_EXPLICIT_PATTERNS (es. "no grazie", "basta", "va bene cosi"), il sistema DEVE classificare come decline_show_details con confidence 0.99 senza richiedere detail_context. QUANDO il messaggio matcha DECLINE_SHORT_PATTERNS (es. "no") E esiste un detail_context attivo, il sistema DEVE classificare come decline_show_details con confidence 0.99.
- **Status**: IMPLEMENTATO
- **Accorpa**: IC-008, IC-009

### IC-010 Disambiguazione rischio - mai controllati
- **Pattern EARS**: QUANDO il messaggio matcha RE_RISK_TYPE_MAI_CONTROLLATI (es. "1", "mai controllati"), il sistema DEVE classificare come ask_risk_based_priority con slot tipo_analisi_rischio="mai_controllati" e confidence 0.99.
- **Status**: IMPLEMENTATO

### IC-011 Disambiguazione rischio - con sanzioni
- **Pattern EARS**: QUANDO il messaggio matcha RE_RISK_TYPE_CON_SANZIONI (es. "2", "con sanzioni", "con piu nc"), il sistema DEVE classificare come ask_risk_based_priority con slot tipo_analisi_rischio="con_sanzioni" e confidence 0.99.
- **Status**: IMPLEMENTATO

### IC-012 Regex estrazione slot piano/topic/location/categoria
- **Pattern EARS**: Il sistema DEVE estrarre tramite regex: (1) piano_code da pattern 1-2 lettere + 1-3 numeri + opzionale suffisso _LETTERE (es. A1, B47, C3_F), normalizzato a uppercase; (2) topic da messaggi con pattern "piani su/per/riguardanti/che trattano [argomento]", rimuovendo articoli e punteggiatura finale; (3) location e radius_km da pattern di prossimita' (vicino a, nei dintorni di, entro X km da), con raggio limitato tra 1.0 e 50.0 km; (4) categoria NC da NC_CATEGORY_PATTERNS, normalizzata a uppercase; (5) tipo_analisi_rischio ("mai_controllati" o "con_sanzioni") da risposte brevi alla disambiguazione rischio.
- **Status**: IMPLEMENTATO
- **Accorpa**: IC-012, IC-016, IC-017, IC-018, IC-019

### IC-013 Regex estrazione identificativi stabilimento (num_reg, num_ric, p.iva, ragione_sociale)
- **Pattern EARS**: Il sistema DEVE estrarre tramite regex: (1) numero_riconoscimento da pattern "UE IT" seguito da cifre e spazi, con priorita' su num_registrazione; (2) num_registrazione da pattern "IT" (senza prefisso "UE") seguito da cifre e spazi, solo se numero_riconoscimento non e' gia' estratto; (3) partita_iva (10-11 cifre) SOLO quando il messaggio contiene esplicitamente "p.iva" o "partita iva"; (4) ragione_sociale da messaggi con "stabilimento [NOME]" (escludendo IT, UE, piano) o in contesto "storico/storia controlli per/di [NOME]" quando nessun altro identificatore e' presente.
- **Status**: IMPLEMENTATO
- **Accorpa**: IC-013, IC-014, IC-015, IC-020

### IC-021 Cache intent con TTL, max size, normalizzazione e bypass
- **Pattern EARS**: Il sistema DEVE implementare una cache intent con: TTL di 3600 secondi (1 ora) con rimozione automatica delle entry scadute; dimensione massima 1000 entry con cleanup del 20% delle piu' vecchie al superamento; normalizzazione query tramite lowercase, strip, encoding UTF-8, hashing MD5; esclusione dalla cache delle classificazioni con intent "fallback" per evitare di persistere risultati non conclusivi.
- **Status**: IMPLEMENTATO
- **Accorpa**: IC-021, IC-022, IC-023, IC-024

### IC-025 Cache context-aware con slot override
- **Pattern EARS**: QUANDO un risultato e' recuperato dalla cache, il sistema DEVE sovrascrivere gli slot con quelli estratti dalla query corrente (non quelli cached) per evitare contaminazione cross-sessione. Il sistema DEVE costruire la chiave cache includendo il contesto detail_context (prefisso "__ctx__:") per distinguere messaggi identici con/senza contesto two-phase attivo.
- **Status**: IMPLEMENTATO
- **Accorpa**: IC-025, IC-026

### IC-027 Few-shot retriever con parametri e threshold adattivo
- **Pattern EARS**: Il sistema DEVE implementare FewShotRetriever come singleton con lazy init, che recupera fino a 6 esempi da Qdrant (top_k=6) con max 2 esempi per intent (diversity). Il threshold di similarita' DEVE essere adattivo in base alla lunghezza della query: 0.50 per <=2 parole, 0.45 per 3-5 parole, 0.40 per >5 parole.
- **Status**: IMPLEMENTATO
- **Accorpa**: IC-027, IC-028, IC-029

### IC-030 Few-shot cache, graceful degradation e condivisione risorse
- **Pattern EARS**: Il sistema DEVE cachare i risultati di retrieve in una OrderedDict LRU con max 100 entry. SE Qdrant non e' disponibile o la collection intent_examples non esiste, il sistema DEVE restituire una lista vuota senza generare errori. Il sistema DEVE riutilizzare il client Qdrant e il modello embedding (paraphrase-multilingual-MiniLM-L12-v2) come singleton condivisi con DataRetriever.
- **Status**: IMPLEMENTATO
- **Accorpa**: IC-030, IC-031, IC-032

### IC-033 LLM classification prompt V2
- **Pattern EARS**: Il sistema DEVE utilizzare un prompt di classificazione semi-dinamico con catalogo intent, regole disambiguazione ed esempi critici iniettati da IntentMetadataService (DB), con fallback a prompt hardcoded se il servizio non e' disponibile.
- **Status**: IMPLEMENTATO

### IC-034 LLM classification - confidence e alternatives
- **Pattern EARS**: QUANDO la confidence e' inferiore a 0.85, il sistema DEVE richiedere all'LLM fino a 2 alternative con intent, confidence e reasoning.
- **Status**: IMPLEMENTATO

### IC-035 LLM classification - session context injection
- **Pattern EARS**: QUANDO esiste una sessione precedente (_session_last_intent, _session_last_slots, _session_last_response_context), il sistema DEVE iniettarla nel prompt utente come contesto per risoluzione anaforica e topic change.
- **Status**: IMPLEMENTATO

### IC-036 LLM classification - few-shot injection
- **Pattern EARS**: QUANDO il FewShotRetriever restituisce esempi, il sistema DEVE iniettarli nel prompt utente prima del messaggio con formato "ESEMPI SIMILI: [text] -> [intent]".
- **Status**: IMPLEMENTATO

### IC-037 LLM response parsing
- **Pattern EARS**: Il sistema DEVE parsare la risposta LLM con chain di fallback: (1) json.loads diretto, (2) estrazione da blocchi ```json```, (3) parser a parentesi bilanciate per il primo JSON valido.
- **Status**: IMPLEMENTATO

### IC-038 Post-LLM validation: semantic correction, slot filtering
- **Pattern EARS**: Il sistema DEVE applicare post-validazione LLM: (1) QUANDO l'LLM classifica come search_piani_by_topic ma e' presente uno slot piano_code, correggere a ask_piano_stabilimenti e rimuovere lo slot topic; (2) QUANDO l'LLM classifica come ask_priority_establishment ma il messaggio contiene "rischio", correggere a ask_risk_based_priority; (3) filtrare slot con valori invalidi ("NULL", "null", "undefined", "none", "None", "", "N/A", "n/a"); (4) rimuovere qualsiasi slot con chiave non appartenente a VALID_SLOT_KEYS per prevenire injection.
- **Status**: IMPLEMENTATO
- **Accorpa**: IC-038, IC-039, IC-040, IC-041

### IC-042 Gibberish detection con bypass pending slots
- **Pattern EARS**: QUANDO un messaggio ha lunghezza <= 15 caratteri, non contiene DOMAIN_KEYWORDS, non e' un pattern sociale/saluto/conferma/rifiuto, non e' numerico, e contiene caratteri non-alfabetici, il sistema DEVE classificarlo come fallback senza invocare l'LLM. QUANDO esiste un confirmed_intent con missing_slots nel dialogue_state, il sistema DEVE saltare il gibberish detection per permettere risposte pure (es. un indirizzo) che non contengono keyword di dominio.
- **Status**: IMPLEMENTATO
- **Accorpa**: IC-042, IC-043

### IC-044 Pending slot fill con location LLM e topic change guard
- **Pattern EARS**: QUANDO c'e' un confirmed_intent con missing_slots contenente "location", il sistema DEVE usare _extract_location_with_llm per estrarre l'indirizzo dal linguaggio naturale, con fallback a regex _clean_location_from_message. QUANDO c'e' un pending slot fill attivo ma l'heuristic matcha un intent diverso dal confirmed_intent, il sistema DEVE annullare il slot filling e procedere con la classificazione normale (topic change).
- **Status**: IMPLEMENTATO
- **Accorpa**: IC-044, IC-045

### IC-046 Local fallback per LLM-down
- **Pattern EARS**: SE l'LLM non e' disponibile (timeout, errore, risposta vuota), il sistema DEVE fornire un fallback locale minimale riconoscendo greet, goodbye e ask_help tramite pattern matching con confidence 0.90.
- **Status**: IMPLEMENTATO

### IC-047 Confidence clamping
- **Pattern EARS**: Il sistema DEVE clampare il valore di confidence tra 0.0 e 1.0, e usare 0.70 come default se il campo non e' presente o non e' numerico.
- **Status**: IMPLEMENTATO

### IC-048 Multi-candidate output
- **Pattern EARS**: QUANDO l'LLM restituisce alternatives, il sistema DEVE costruire una lista _candidates contenente l'intent principale e fino a 2 alternative valide (presenti in VALID_INTENTS) per il dialogue_manager.
- **Status**: IMPLEMENTATO

### ~~IC-049, IC-050, IC-051~~ RIMOSSO — Duplicato di FR-013, FR-014, FR-015
- Vedi `fallback-recovery.md` per INTENT_REGISTRY, CATEGORY_HIERARCHY e registry validation.

### IC-052 Slot normalizzazione
- **Pattern EARS**: Il sistema DEVE normalizzare i valori slot: piano_code e asl in uppercase, categoria in uppercase, e filtrare valori None o stringa vuota.
- **Status**: IMPLEMENTATO

### IC-053 Self-sufficient intents
- **Pattern EARS**: Il sistema DEVE trattare greet, goodbye, ask_help, ask_priority_establishment, ask_risk_based_priority, ask_suggest_controls, ask_delayed_plans, ask_piano_statistics, ask_top_risk_activities, confirm_show_details, decline_show_details e fallback come intent auto-sufficienti che non richiedono slot obbligatori (needs_clarification=false).
- **Status**: IMPLEMENTATO

### IC-054 analyze_nc_by_category default
- **Pattern EARS**: QUANDO l'intent e' analyze_nc_by_category, il sistema DEVE impostare needs_clarification=false perche' il tool ha un default "HACCP" per la categoria.
- **Status**: IMPLEMENTATO

### IC-055 Router hot-reload
- **Pattern EARS**: Il sistema DEVE supportare il reload a caldo del router (reload()) che ricarica metadati intent da DB, ricostruisce il prompt e svuota la cache.
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### IC-NF-001 Performance cache e lazy loading thread-safe
- **Pattern EARS**: QUANDO un risultato e' presente in cache (HIT), il sistema DEVE restituirlo in ~0.001s senza invocazione LLM. Il sistema DEVE caricare Qdrant client e embedding model solo al primo utilizzo (lazy init), non al momento dell'import. Il sistema DEVE garantire operazioni thread-safe sulla cache intent tramite struttura dati dict di Python (GIL).
- **Status**: IMPLEMENTATO
- **Accorpa**: IC-NF-001, IC-NF-002, IC-NF-003

### IC-NF-004 LLM location extraction timeout
- **Pattern EARS**: QUANDO l'LLM e' usato per estrarre location, il sistema DEVE imporre un timeout di 10 secondi e max_tokens=150 con fallback a regex.
- **Status**: IMPLEMENTATO
