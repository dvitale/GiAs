# Esecuzione Tool

**Componente**: Backend (GiAs-llm)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: `orchestrator/tool_nodes.py`, `tools/piano_tools.py`, `tools/priority_tools.py`, `tools/risk_tools.py`, `tools/risk_analysis_tools.py`, `tools/search_tools.py`, `tools/establishment_tools.py`, `tools/proximity_tools.py`, `tools/predictor_tools.py`

## Requisiti Funzionali

### TE-001 TOOL_REGISTRY
- **Pattern EARS**: Il sistema DEVE registrare 19 tool nel TOOL_REGISTRY: greet_tool, goodbye_tool, help_tool, piano_description_tool, piano_stabilimenti_tool, piano_statistics_tool, search_piani_tool, priority_establishment_tool, risk_predictor_tool, suggest_controls_tool, nearby_priority_tool, delayed_plans_tool, check_plan_delayed_tool, establishment_history_tool, top_risk_activities_tool, analyze_nc_tool, info_procedure_tool, query_data_tool, confirm_details_tool, decline_details_tool.
- **Status**: IMPLEMENTATO

### TE-002 INTENT_TO_TOOL mapping
- **Pattern EARS**: Il sistema DEVE mappare ogni intent a un tool specifico tramite INTENT_TO_TOOL: greet->greet_tool, goodbye->goodbye_tool, ask_help->help_tool, ask_piano_description->piano_description_tool, ask_piano_stabilimenti->piano_stabilimenti_tool, ask_piano_statistics->piano_statistics_tool, search_piani_by_topic->search_piani_tool, ask_priority_establishment->priority_establishment_tool, ask_risk_based_priority->risk_predictor_tool, ask_suggest_controls->suggest_controls_tool, ask_nearby_priority->nearby_priority_tool, ask_delayed_plans->delayed_plans_tool, check_if_plan_delayed->check_plan_delayed_tool, ask_establishment_history->establishment_history_tool, ask_top_risk_activities->top_risk_activities_tool, analyze_nc_by_category->analyze_nc_tool, info_procedure->info_procedure_tool, query_data->query_data_tool, confirm_show_details->confirm_details_tool, decline_show_details->decline_details_tool.
- **Status**: IMPLEMENTATO

### TE-003 greet_tool
- **Pattern EARS**: QUANDO l'intent e' greet, il sistema DEVE restituire un messaggio di benvenuto statico senza accesso al database.
- **Status**: IMPLEMENTATO

### TE-004 goodbye_tool
- **Pattern EARS**: QUANDO l'intent e' goodbye, il sistema DEVE restituire "Arrivederci! Buon lavoro." senza accesso al database.
- **Status**: IMPLEMENTATO

### TE-005 help_tool - DB con fallback hardcoded
- **Pattern EARS**: QUANDO l'intent e' ask_help, il sistema DEVE tentare di generare il contenuto help da IntentMetadataService (DB); SE il servizio non e' disponibile o restituisce stringa vuota, il sistema DEVE usare il testo _HARDCODED_HELP con domande di esempio organizzate per categoria.
- **Status**: IMPLEMENTATO

### TE-006 confirm_details_tool - contesto presente
- **Pattern EARS**: QUANDO l'intent e' confirm_show_details e detail_context e' presente nel metadata, il sistema DEVE restituire la formatted_response completa salvata nel detail_context.
- **Status**: IMPLEMENTATO

### TE-007 confirm_details_tool - sessione scaduta
- **Pattern EARS**: SE l'intent e' confirm_show_details ma detail_context non e' presente (sessione scaduta), il sistema DEVE restituire un messaggio che invita a ripetere la domanda originale con esempi.
- **Status**: IMPLEMENTATO

### TE-008 decline_details_tool
- **Pattern EARS**: QUANDO l'intent e' decline_show_details, il sistema DEVE restituire "Va bene! Se hai altre domande, sono qui per aiutarti." e confirmed=False.
- **Status**: IMPLEMENTATO

### TE-009 piano_description_tool
- **Pattern EARS**: QUANDO l'intent e' ask_piano_description, il sistema DEVE recuperare la descrizione del piano tramite DataRetriever.get_piano_by_id, estrarre descrizioni uniche con BusinessLogic.extract_unique_piano_descriptions, e formattare con ResponseFormatter.format_piano_description.
- **Status**: IMPLEMENTATO

### TE-010 piano_stabilimenti_tool con two-phase
- **Pattern EARS**: QUANDO l'intent e' ask_piano_stabilimenti, il sistema DEVE recuperare i controlli per piano tramite DataRetriever.get_controlli_by_piano, aggregare con BusinessLogic.aggregate_stabilimenti_by_piano, e applicare two-phase check se unique_establishments > 3.
- **Status**: IMPLEMENTATO

### TE-011 piano_statistics_tool - conteggio con ASL
- **Pattern EARS**: QUANDO l'intent e' ask_piano_statistics con piano_code e il messaggio contiene keyword di conteggio (quanti, quante, numero di, conta, totale controlli), il sistema DEVE mostrare totale regionale, totale per ASL dell'utente, e periodo dei controlli.
- **Status**: IMPLEMENTATO

### TE-012 piano_statistics_tool - statistiche aggregate
- **Pattern EARS**: QUANDO l'intent e' ask_piano_statistics senza piano_code, il sistema DEVE mostrare statistiche aggregate top-N piani tramite BusinessLogic.get_piano_statistics.
- **Status**: IMPLEMENTATO

### TE-013 search_piani_tool - hybrid search
- **Pattern EARS**: QUANDO l'intent e' search_piani_by_topic, il sistema DEVE tentare prima HybridSearchEngine; SE non disponibile o fallisce, il sistema DEVE usare DataRetriever.search_piani_by_db (ILIKE testuale).
- **Status**: IMPLEMENTATO

### TE-014 search_piani_tool con two-phase
- **Pattern EARS**: QUANDO search_piani_by_topic restituisce piu' di 3 risultati, il sistema DEVE applicare two-phase check con summary e risposta completa senza limiti per detail_context.
- **Status**: IMPLEMENTATO

### TE-015 priority_establishment_tool - UOC/UOS auto-detection
- **Pattern EARS**: QUANDO l'intent e' ask_priority_establishment e uoc/uos non sono nel metadata, il sistema DEVE tentare di recuperarli da user_id tramite get_uoc_from_user_id e get_uos_from_user_id.
- **Status**: IMPLEMENTATO

### TE-016 priority_establishment_tool con two-phase
- **Pattern EARS**: QUANDO priority_establishment restituisce piu' di 3 stabilimenti, il sistema DEVE applicare two-phase check con summary e risposta completa senza limiti per detail_context.
- **Status**: IMPLEMENTATO

### TE-017 risk_predictor_tool - disambiguazione
- **Pattern EARS**: QUANDO l'intent e' ask_risk_based_priority e tipo_analisi_rischio non e' specificato, il sistema DEVE mostrare un menu di disambiguazione con 2 opzioni: (1) mai controllati, (2) con piu' sanzioni, e impostare needs_clarification=True.
- **Status**: IMPLEMENTATO

### TE-018 risk_predictor_tool - mai controllati (ML o statistico)
- **Pattern EARS**: QUANDO tipo_analisi_rischio e' "mai_controllati", il sistema DEVE verificare RiskPredictorConfig.get_predictor_type(): se "ml" usa get_ml_risk_prediction, altrimenti usa risk_tool (statistico), e applicare two-phase check se total_risky > 3.
- **Status**: IMPLEMENTATO

### TE-019 risk_predictor_tool - con sanzioni
- **Pattern EARS**: QUANDO tipo_analisi_rischio e' "con_sanzioni", il sistema DEVE usare get_establishments_with_sanctions con limit=20 e applicare two-phase check se total > 3.
- **Status**: IMPLEMENTATO

### TE-020 suggest_controls_tool con two-phase
- **Pattern EARS**: QUANDO ask_suggest_controls restituisce piu' di 3 stabilimenti mai controllati, il sistema DEVE applicare two-phase check con summary dei primi 5.
- **Status**: IMPLEMENTATO

### TE-021 delayed_plans_tool
- **Pattern EARS**: QUANDO l'intent e' ask_delayed_plans, il sistema DEVE recuperare i piani in ritardo per la struttura dell'utente (ASL+UOC+UOS) tramite priority_tool con action="delayed_plans", mostrando top 10 piani ordinati per ritardo decrescente.
- **Status**: IMPLEMENTATO

### TE-022 check_plan_delayed_tool
- **Pattern EARS**: QUANDO l'intent e' check_if_plan_delayed, il sistema DEVE verificare se il piano specifico e' in ritardo per la struttura dell'utente, mostrando programmati vs eseguiti anche se il piano non e' in ritardo, e supportare matching sottopiani (es. AO24 matcha AO24_A, AO24_B).
- **Status**: IMPLEMENTATO

### TE-023 establishment_history_tool con two-phase
- **Pattern EARS**: QUANDO ask_establishment_history restituisce piu' di 3 controlli, il sistema DEVE applicare two-phase check con summary e risposta completa senza limiti per detail_context.
- **Status**: IMPLEMENTATO

### TE-024 establishment_history_tool - multi-identifier
- **Pattern EARS**: Il sistema DEVE supportare ricerca stabilimento per num_registrazione, numero_riconoscimento, partita_iva o ragione_sociale (ricerca parziale), cercando in entrambe le tabelle controlli_df e ocse_df, con limite 50 controlli piu' recenti.
- **Status**: IMPLEMENTATO

### TE-025 top_risk_activities_tool
- **Pattern EARS**: QUANDO l'intent e' ask_top_risk_activities, il sistema DEVE estrarre le top N (default 10) linee di attivita' con risk score piu' elevato dal dataset OCSE tramite RiskAnalyzer.calculate_risk_scores, con soglie calibrate (P90=6.6, P75=3.0, P50=0.66).
- **Status**: IMPLEMENTATO

### TE-026 analyze_nc_tool
- **Pattern EARS**: QUANDO l'intent e' analyze_nc_by_category, il sistema DEVE analizzare NC per la categoria specificata (default "HACCP"), validando la categoria contro VALID_NC_CATEGORIES, mostrando totale controlli, NC gravi/non gravi, stabilimenti coinvolti, e top 3 stabilimenti critici.
- **Status**: IMPLEMENTATO

### TE-027 info_procedure_tool - RAG
- **Pattern EARS**: QUANDO l'intent e' info_procedure, il sistema DEVE usare get_procedure_info con la query dell'utente e il contesto conversazionale dalla sessione per cercare informazioni su procedure operative documentate.
- **Status**: IMPLEMENTATO

### TE-028 nearby_priority_tool - geocodifica
- **Pattern EARS**: QUANDO l'intent e' ask_nearby_priority, il sistema DEVE geocodificare l'indirizzo tramite GeocodingService, gestendo errori specifici: AddressNotFoundError, GeocodingTimeoutError, GeocodingError.
- **Status**: IMPLEMENTATO

### TE-029 nearby_priority_tool - verifica territorio ASL
- **Pattern EARS**: QUANDO l'indirizzo geocodificato si trova in una provincia fuori dal territorio dell'ASL dell'utente, il sistema DEVE restituire un messaggio che spiega che la posizione e' fuori competenza e suggerisce alternative.
- **Status**: IMPLEMENTATO

### TE-030 nearby_priority_tool - filtro prossimita e rischio
- **Pattern EARS**: QUANDO ci sono stabilimenti nel raggio, il sistema DEVE arricchirli con punteggio rischio da RiskAnalyzer.calculate_risk_scores e ordinarli per distanza (primaria, crescente) + rischio (secondaria, decrescente), con limit default 50. SE il join con rischio fallisce, il sistema DEVE continuare senza.
- **Status**: IMPLEMENTATO

### TE-031 nearby_priority_tool con two-phase
- **Pattern EARS**: QUANDO ask_nearby_priority restituisce piu' di 10 stabilimenti, il sistema DEVE applicare two-phase check con summary e risposta completa senza limiti per detail_context.
- **Status**: IMPLEMENTATO

### TE-032 nearby_priority_tool - centro citta' fallback
- **Pattern EARS**: QUANDO l'indirizzo specifico non e' trovato ma il geocoder individua il centro citta', il sistema DEVE mostrare un warning "Indirizzo non trovato - uso il centro di [citta'] come riferimento" prima dei risultati.
- **Status**: IMPLEMENTATO

### TE-033 predictor_tools - ML con fallback rule-based
- **Pattern EARS**: QUANDO il predictor ML e' disponibile, il sistema DEVE usarlo per la predizione; SE ML non e' disponibile o fallisce, il sistema DEVE usare il fallback rule-based (risk_tools.get_risk_based_priority) adattando il formato al contratto ML.
- **Status**: IMPLEMENTATO

### TE-034 predictor_tools - emergency fallback
- **Pattern EARS**: SE sia ML che rule-based falliscono, il sistema DEVE restituire un messaggio di emergenza "Sistema Predittivo Non Disponibile" con possibili cause e azione richiesta.
- **Status**: IMPLEMENTATO

### TE-035 predictor_tools - normalizzazione score
- **Pattern EARS**: QUANDO si usa il fallback rule-based, il sistema DEVE normalizzare il punteggio rischio (0-100+) a probabilita' ML (0-1) con formula min(raw_score/100.0, 1.0) e categorizzare come ALTO (>0.7), MEDIO (>0.4), BASSO.
- **Status**: IMPLEMENTATO

### TE-036 risk_tools - analisi per piano senza ASL
- **Pattern EARS**: QUANDO ask_risk_based_priority e' invocato con piano_code ma senza ASL, il sistema DEVE analizzare le tipologie di stabilimenti controllati per quel piano con NC storiche tramite _analyze_controlled_establishments_risk.
- **Status**: IMPLEMENTATO

### TE-037 risk_tools - suggerimento categoria NC
- **Pattern EARS**: QUANDO un piano non ha controlli ma il codice corrisponde a una categoria NC valida (es. "HACCP"), il sistema DEVE suggerire all'utente di usare il formato "Analizza le non conformita [categoria]".
- **Status**: IMPLEMENTATO

### TE-038 SSE reasoning events per tool
- **Pattern EARS**: QUANDO event_callback e' presente, i tool piano_stabilimenti_tool, priority_establishment_tool, risk_predictor_tool e nearby_priority_tool DEVONO emettere eventi SSE di tipo "reasoning" con messaggi contestuali (es. "Consultando il database dei piani...", "Calcolando priorita' controlli...", "Analizzando rischio stabilimenti...", "Geocodificando indirizzo...").
- **Status**: IMPLEMENTATO

### TE-039 Tool unwrap LangChain decorator
- **Pattern EARS**: Il sistema DEVE gestire funzioni tool decorate con @tool di LangChain, estraendo la funzione raw tramite _unwrap_tool (attributo .func) prima dell'invocazione.
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### TE-040 query_data_tool - interrogazione dati su misura
- **Pattern EARS**: QUANDO l'intent e' query_data, il sistema DEVE chiamare build_query_with_llm per generare un Operation Descriptor JSON, validarlo con QueryDescriptor (Pydantic), eseguirlo con SafeQueryExecutor su DataFrame in memoria, e formattare il risultato come tabella markdown.
- **Status**: IMPLEMENTATO

### TE-041 query_data_tool - preprocessing filtri con alias colonne
- **Pattern EARS**: QUANDO un filtro contiene colonne concettuali (anno, asl, macroarea), il sistema DEVE tradurle a colonne reali del DataFrame tramite COLUMN_ALIASES (es. anno→data_inizio_controllo, asl→descrizione_asl) e gestire conversioni speciali (anno→range date, ASL→nome citta').
- **Status**: IMPLEMENTATO

### TE-042 query_data_tool - blacklist PII
- **Pattern EARS**: QUANDO una query tenta di accedere a colonne PII (codice_fiscale, partita_iva, ragione_sociale, nominativo_rappresentante), il sistema DEVE bloccare la query con un messaggio di errore che spiega la restrizione.
- **Status**: IMPLEMENTATO

### TE-043 piano_description_tool - fallback prefisso ATT per indicatori
- **Pattern EARS**: QUANDO il codice piano non viene trovato con match esatto su alias o alias_indicatore, il sistema DEVE tentare un match aggiungendo il prefisso "ATT " al codice (es. "AO5_A" → "ATT AO5_A"), poiche' gli alias_indicatore hanno formato "ATT {codice}".
- **Status**: IMPLEMENTATO

### TE-NF-001 Tool output standard
- **Pattern EARS**: Il sistema DEVE restituire tool_output in formato standard {"type": string, "data": dict} dove data contiene almeno "formatted_response" per il response_generator.
- **Status**: IMPLEMENTATO

### TE-NF-002 Radius clamping
- **Pattern EARS**: DOVE il proximity tool riceve radius_km, il sistema DEVE clampare il valore predefinito a 5.0 km e accettare valori tra 1.0 e 50.0 km.
- **Status**: IMPLEMENTATO

### TE-NF-003 Limit clamping predictor
- **Pattern EARS**: DOVE il predictor ML riceve un parametro limit, il sistema DEVE clampare il valore tra 1 e 100 per ragioni di performance.
- **Status**: IMPLEMENTATO
