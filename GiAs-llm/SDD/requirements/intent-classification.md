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

### IC-006 Heuristic confirm esplicito
- **Pattern EARS**: QUANDO il messaggio matcha CONFIRM_EXPLICIT_PATTERNS (es. "si mostrami", "vediamo tutti"), il sistema DEVE classificare come confirm_show_details con confidence 0.99 senza richiedere detail_context.
- **Status**: IMPLEMENTATO

### IC-007 Heuristic confirm breve con detail_context
- **Pattern EARS**: QUANDO il messaggio matcha CONFIRM_SHORT_PATTERNS (es. "si", "ok", "vai") E esiste un detail_context attivo, il sistema DEVE classificare come confirm_show_details con confidence 0.99.
- **Status**: IMPLEMENTATO

### IC-008 Heuristic decline esplicito
- **Pattern EARS**: QUANDO il messaggio matcha DECLINE_EXPLICIT_PATTERNS (es. "no grazie", "basta", "va bene cosi"), il sistema DEVE classificare come decline_show_details con confidence 0.99 senza richiedere detail_context.
- **Status**: IMPLEMENTATO

### IC-009 Heuristic decline breve con detail_context
- **Pattern EARS**: QUANDO il messaggio matcha DECLINE_SHORT_PATTERNS (es. "no") E esiste un detail_context attivo, il sistema DEVE classificare come decline_show_details con confidence 0.99.
- **Status**: IMPLEMENTATO

### IC-010 Disambiguazione rischio - mai controllati
- **Pattern EARS**: QUANDO il messaggio matcha RE_RISK_TYPE_MAI_CONTROLLATI (es. "1", "mai controllati"), il sistema DEVE classificare come ask_risk_based_priority con slot tipo_analisi_rischio="mai_controllati" e confidence 0.99.
- **Status**: IMPLEMENTATO

### IC-011 Disambiguazione rischio - con sanzioni
- **Pattern EARS**: QUANDO il messaggio matcha RE_RISK_TYPE_CON_SANZIONI (es. "2", "con sanzioni", "con piu nc"), il sistema DEVE classificare come ask_risk_based_priority con slot tipo_analisi_rischio="con_sanzioni" e confidence 0.99.
- **Status**: IMPLEMENTATO

### IC-012 Regex estrazione piano_code
- **Pattern EARS**: Il sistema DEVE estrarre piano_code da pattern regex con formato 1-2 lettere + 1-3 numeri + opzionale suffisso _LETTERE (es. A1, B47, C3_F) e normalizzarlo a uppercase.
- **Status**: IMPLEMENTATO

### IC-013 Regex estrazione numero riconoscimento UE
- **Pattern EARS**: Il sistema DEVE estrarre numero_riconoscimento da pattern "UE IT" seguito da cifre e spazi, con priorita' su num_registrazione.
- **Status**: IMPLEMENTATO

### IC-014 Regex estrazione num_registrazione
- **Pattern EARS**: Il sistema DEVE estrarre num_registrazione da pattern "IT" (senza prefisso "UE") seguito da cifre e spazi, solo se numero_riconoscimento non e' gia' estratto.
- **Status**: IMPLEMENTATO

### IC-015 Regex estrazione partita_iva
- **Pattern EARS**: Il sistema DEVE estrarre partita_iva (10-11 cifre) SOLO quando il messaggio contiene esplicitamente "p.iva" o "partita iva".
- **Status**: IMPLEMENTATO

### IC-016 Regex estrazione topic
- **Pattern EARS**: Il sistema DEVE estrarre il topic da messaggi con pattern "piani su/per/riguardanti/che trattano [argomento]", rimuovendo articoli e punteggiatura finale.
- **Status**: IMPLEMENTATO

### IC-017 Regex estrazione location e radius_km
- **Pattern EARS**: QUANDO il messaggio contiene pattern di prossimita' (vicino a, nei dintorni di, entro X km da), il sistema DEVE estrarre location dal testo successivo e radius_km dal pattern numerico "X km", limitando il raggio tra 1.0 e 50.0 km.
- **Status**: IMPLEMENTATO

### IC-018 Regex estrazione categoria NC
- **Pattern EARS**: QUANDO il messaggio matcha NC_CATEGORY_PATTERNS, il sistema DEVE estrarre la categoria (HACCP, IGIENE, STRUTTURE, PULIZIA, SANIFICAZIONE, ETICHETTATURA, MOCA, RINTRACCIABILITA) e normalizzarla a uppercase.
- **Status**: IMPLEMENTATO

### IC-019 Regex estrazione tipo_analisi_rischio
- **Pattern EARS**: Il sistema DEVE estrarre tipo_analisi_rischio ("mai_controllati" o "con_sanzioni") da risposte brevi alla disambiguazione rischio.
- **Status**: IMPLEMENTATO

### IC-020 Regex estrazione ragione_sociale
- **Pattern EARS**: Il sistema DEVE estrarre ragione_sociale da messaggi con "stabilimento [NOME]" (escludendo IT, UE, piano) o in contesto "storico/storia controlli per/di [NOME]" quando nessun altro identificatore e' presente.
- **Status**: IMPLEMENTATO

### IC-021 Intent cache - TTL
- **Pattern EARS**: Il sistema DEVE implementare una cache intent con TTL di 3600 secondi (1 ora), rimuovendo automaticamente le entry scadute al momento dell'accesso.
- **Status**: IMPLEMENTATO

### IC-022 Intent cache - max size
- **Pattern EARS**: QUANDO la cache supera 1000 entry, il sistema DEVE eseguire cleanup rimuovendo il 20% delle entry piu' vecchie (keep_ratio=0.8).
- **Status**: IMPLEMENTATO

### IC-023 Intent cache - normalizzazione query
- **Pattern EARS**: Il sistema DEVE normalizzare le query per la cache tramite: lowercase, strip whitespace, encoding UTF-8, e hashing MD5.
- **Status**: IMPLEMENTATO

### IC-024 Intent cache - bypass per fallback
- **Pattern EARS**: Il sistema DEVE NON cachare classificazioni con intent "fallback" per evitare di persistere risultati non conclusivi.
- **Status**: IMPLEMENTATO

### IC-025 Intent cache - slot override
- **Pattern EARS**: QUANDO un risultato e' recuperato dalla cache, il sistema DEVE sovrascrivere gli slot con quelli estratti dalla query corrente (non quelli cached) per evitare contaminazione cross-sessione.
- **Status**: IMPLEMENTATO

### IC-026 Intent cache - context awareness
- **Pattern EARS**: Il sistema DEVE costruire la chiave cache includendo il contesto detail_context (prefisso "__ctx__:") per distinguere messaggi identici con/senza contesto two-phase attivo.
- **Status**: IMPLEMENTATO

### IC-027 Few-shot retriever - singleton
- **Pattern EARS**: Il sistema DEVE implementare FewShotRetriever come singleton con lazy init per minimizzare overhead a cold start.
- **Status**: IMPLEMENTATO

### IC-028 Few-shot retriever - parametri retrieve
- **Pattern EARS**: Il sistema DEVE recuperare fino a 6 esempi da Qdrant (top_k=6) con score_threshold adattivo e max 2 esempi per intent (diversity).
- **Status**: IMPLEMENTATO

### IC-029 Few-shot retriever - threshold adattivo
- **Pattern EARS**: Il sistema DEVE calcolare il threshold di similarita' in base alla lunghezza della query: 0.50 per <=2 parole, 0.45 per 3-5 parole, 0.40 per >5 parole.
- **Status**: IMPLEMENTATO

### IC-030 Few-shot retriever - cache LRU
- **Pattern EARS**: Il sistema DEVE cachare i risultati di retrieve in una OrderedDict LRU con max 100 entry, evitando ricerche ripetute per query identiche.
- **Status**: IMPLEMENTATO

### IC-031 Few-shot retriever - graceful degradation
- **Pattern EARS**: SE Qdrant non e' disponibile o la collection intent_examples non esiste, il sistema DEVE restituire una lista vuota senza generare errori.
- **Status**: IMPLEMENTATO

### IC-032 Few-shot retriever - condivisione risorse
- **Pattern EARS**: Il sistema DEVE riutilizzare il client Qdrant e il modello embedding (paraphrase-multilingual-MiniLM-L12-v2) come singleton condivisi con DataRetriever.
- **Status**: IMPLEMENTATO

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

### IC-038 Post-LLM semantic correction - search con piano_code
- **Pattern EARS**: QUANDO l'LLM classifica come search_piani_by_topic ma e' presente uno slot piano_code, il sistema DEVE correggere l'intent a ask_piano_stabilimenti e rimuovere lo slot topic.
- **Status**: IMPLEMENTATO

### IC-039 Post-LLM semantic correction - priority con rischio
- **Pattern EARS**: QUANDO l'LLM classifica come ask_priority_establishment ma il messaggio contiene "rischio", il sistema DEVE correggere l'intent a ask_risk_based_priority.
- **Status**: IMPLEMENTATO

### IC-040 Invalid slot filtering
- **Pattern EARS**: Il sistema DEVE filtrare slot con valori invalidi ("NULL", "null", "undefined", "none", "None", "", "N/A", "n/a") durante la post-validation.
- **Status**: IMPLEMENTATO

### IC-041 Slot key filtering
- **Pattern EARS**: Il sistema DEVE rimuovere qualsiasi slot con chiave non appartenente a VALID_SLOT_KEYS dalla risposta LLM per prevenire injection.
- **Status**: IMPLEMENTATO

### IC-042 Gibberish detection
- **Pattern EARS**: QUANDO un messaggio ha lunghezza <= 15 caratteri, non contiene DOMAIN_KEYWORDS, non e' un pattern sociale/saluto/conferma/rifiuto, non e' numerico, e contiene caratteri non-alfabetici, il sistema DEVE classificarlo come fallback senza invocare l'LLM.
- **Status**: IMPLEMENTATO

### IC-043 Gibberish bypass per pending slots
- **Pattern EARS**: QUANDO esiste un confirmed_intent con missing_slots nel dialogue_state, il sistema DEVE saltare il gibberish detection per permettere risposte pure (es. un indirizzo) che non contengono keyword di dominio.
- **Status**: IMPLEMENTATO

### IC-044 Pending slot fill - location con LLM
- **Pattern EARS**: QUANDO c'e' un confirmed_intent con missing_slots contenente "location", il sistema DEVE usare _extract_location_with_llm per estrarre l'indirizzo dal linguaggio naturale, con fallback a regex _clean_location_from_message.
- **Status**: IMPLEMENTATO

### IC-045 Pending slot fill - topic change guard
- **Pattern EARS**: QUANDO c'e' un pending slot fill attivo ma l'heuristic matcha un intent diverso dal confirmed_intent, il sistema DEVE annullare il slot filling e procedere con la classificazione normale (topic change).
- **Status**: IMPLEMENTATO

### IC-046 Local fallback per LLM-down
- **Pattern EARS**: SE l'LLM non e' disponibile (timeout, errore, risposta vuota), il sistema DEVE fornire un fallback locale minimale riconoscendo greet, goodbye e ask_help tramite pattern matching con confidence 0.90.
- **Status**: IMPLEMENTATO

### IC-047 Confidence clamping
- **Pattern EARS**: Il sistema DEVE clampare il valore di confidence tra 0.0 e 1.0, e usare 0.70 come default se il campo non e' presente o non e' numerico.
- **Status**: IMPLEMENTATO

### IC-048 Multi-candidate output
- **Pattern EARS**: QUANDO l'LLM restituisce alternatives, il sistema DEVE costruire una lista _candidates contenente l'intent principale e fino a 2 alternative valide (presenti in VALID_INTENTS) per il dialogue_manager.
- **Status**: IMPLEMENTATO

### IC-049 Intent metadata registry
- **Pattern EARS**: Il sistema DEVE mantenere un registry INTENT_REGISTRY con metadati completi per ogni intent: intent_id, label, description, category, keywords, context_keywords, negative_keywords, examples, requires_slots, emoji.
- **Status**: IMPLEMENTATO

### IC-050 Category hierarchy
- **Pattern EARS**: Il sistema DEVE organizzare gli intent in una gerarchia categoriale a 2 livelli (CATEGORY_HIERARCHY) con 7 categorie: Piano di Controllo, Priorita e Rischio, Ricerca, Ritardi e Monitoraggio, Storico e Analisi, Procedure Operative, Altro.
- **Status**: IMPLEMENTATO

### IC-051 Registry validation
- **Pattern EARS**: Il sistema DEVE validare al caricamento che tutti gli intent in CATEGORY_HIERARCHY esistano in INTENT_REGISTRY e viceversa, emettendo warnings in caso di inconsistenze.
- **Status**: IMPLEMENTATO

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

### IC-NF-001 Cache performance
- **Pattern EARS**: QUANDO un risultato e' presente in cache (HIT), il sistema DEVE restituirlo in ~0.001s senza invocazione LLM.
- **Status**: IMPLEMENTATO

### IC-NF-002 Few-shot retriever lazy loading
- **Pattern EARS**: Il sistema DEVE caricare Qdrant client e embedding model solo al primo utilizzo (lazy init), non al momento dell'import.
- **Status**: IMPLEMENTATO

### IC-NF-003 Thread safety cache
- **Pattern EARS**: Il sistema DEVE garantire operazioni thread-safe sulla cache intent tramite struttura dati dict di Python (GIL).
- **Status**: IMPLEMENTATO

### IC-NF-004 LLM location extraction timeout
- **Pattern EARS**: QUANDO l'LLM e' usato per estrarre location, il sistema DEVE imporre un timeout di 10 secondi e max_tokens=150 con fallback a regex.
- **Status**: IMPLEMENTATO
