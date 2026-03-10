# Gestione Dialogo

**Componente**: Backend (GiAs-llm)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: `orchestrator/dialogue_manager.py`, `orchestrator/dialogue_state.py`, `orchestrator/workflow_strategies.py`

## Requisiti Funzionali

### DM-001 Soglie confidence adattive per modello
- **Pattern EARS**: Il sistema DEVE configurare soglie confidence diverse per modello LLM: llama3.2 (high=0.60, min=0.35, delta=0.15), velvet (high=0.80, min=0.50, delta=0.20), mistral-nemo (high=0.80, min=0.50, delta=0.20), llama3.1 (high=0.75, min=0.45, delta=0.20), ministral (high=0.65, min=0.40, delta=0.18), falcon (high=0.65, min=0.40, delta=0.18), google/gemini-2.5-flash (high=0.80, min=0.50, delta=0.20), con default (high=0.80, min=0.50, delta=0.20).
- **Status**: IMPLEMENTATO

### DM-002 Regola 0 - Slot continuation
- **Pattern EARS**: QUANDO il DialogueState ha un confirmed_intent con missing_slots e l'utente fornisce slot estratti che riempiono quelli mancanti, il sistema DEVE eseguire direttamente il tool associato senza ri-classificare.
- **Status**: IMPLEMENTATO

### DM-003 Regola 1 - Intent chiaro, slot completi
- **Pattern EARS**: QUANDO la confidence del candidato top e' >= CONFIDENCE_HIGH e tutti gli slot obbligatori sono presenti (o l'intent e' self-sufficient), il sistema DEVE eseguire direttamente il tool corrispondente.
- **Status**: IMPLEMENTATO

### DM-004 Regola 1 bis - Proposta strategia per intent vaghi
- **Pattern EARS**: QUANDO l'intent e' in CONVERSATIONAL_INTENTS, ha strategie configurate, non ha gia' una strategia confermata, e il messaggio e' vago, il sistema DEVE proporre la domanda di scelta strategia prima di eseguire.
- **Status**: IMPLEMENTATO

### DM-005 Regola 2 - Intent chiaro, slot mancanti
- **Pattern EARS**: QUANDO la confidence e' >= CONFIDENCE_HIGH ma mancano slot obbligatori, il sistema DEVE salvare l'intent come confirmed_intent, registrare i missing_slots, e chiedere all'utente con una domanda costruita da _build_slot_question.
- **Status**: IMPLEMENTATO

### DM-006 Regola 3 - Intent ambiguo
- **Pattern EARS**: QUANDO ci sono >= 2 candidati, la confidence top e' >= CONFIDENCE_MIN, e la differenza tra top e secondo e' < CONFIDENCE_AMBIGUITY_DELTA, il sistema DEVE presentare un menu di disambiguazione con max 3 opzioni (label e description da intent_metadata).
- **Status**: IMPLEMENTATO

### DM-007 Regola 4 - Nessun candidato valido
- **Pattern EARS**: QUANDO la confidence del candidato top e' < CONFIDENCE_MIN, il sistema DEVE attivare il fallback.
- **Status**: IMPLEMENTATO

### DM-008 Regola 5 - Refinement
- **Pattern EARS**: QUANDO il messaggio e' un raffinamento (_is_refinement) e c'e' un last_tool_intent nel DialogueState, il sistema DEVE ri-eseguire il tool precedente con slot e filtri aggiornati.
- **Status**: IMPLEMENTATO

### DM-009 Regola 6 - Conferma strategia pendente
- **Pattern EARS**: QUANDO il messaggio e' una conferma (_is_confirmation) e il DialogueState ha confirmed_intent + confirmed_strategy_id, il sistema DEVE trovare la strategia corrispondente, mappare all'intent_mapping e eseguire il tool associato.
- **Status**: IMPLEMENTATO

### DM-010 Regola 7 - "Oppure?" cycling
- **Pattern EARS**: QUANDO il messaggio e' una variante di "oppure?" (_is_oppure) e c'e' un confirmed_intent con strategie, il sistema DEVE ciclare alla strategia successiva (modulo lunghezza lista strategie) e proporre l'alternativa all'utente.
- **Status**: IMPLEMENTATO

### DM-011 "Oppure?" senza alternative
- **Pattern EARS**: QUANDO il messaggio e' "oppure?" ma l'intent non ha strategie alternative, il sistema DEVE rispondere "Non ci sono alternative disponibili per questa richiesta."
- **Status**: IMPLEMENTATO

### DM-012 Default - confidence media
- **Pattern EARS**: QUANDO la confidence e' tra CONFIDENCE_MIN e CONFIDENCE_HIGH e nessuna altra regola si applica, il sistema DEVE tentare di eseguire il tool se gli slot sono completi, altrimenti chiedere slot mancanti.
- **Status**: IMPLEMENTATO

### DM-013 DialogueState TTL
- **Pattern EARS**: QUANDO il DialogueState ha un timestamp piu' vecchio di 300 secondi (DIALOGUE_STATE_TTL), il sistema DEVE considerarlo invalido e crearne uno nuovo vuoto.
- **Status**: IMPLEMENTATO

### DM-014 DialogueState creazione vuoto
- **Pattern EARS**: Il sistema DEVE creare DialogueState vuoti con goal=None, intent_candidates=[], confirmed_intent=None, confirmed_strategy=None, confirmed_strategy_id=None, slots={}, missing_slots=[], filters={}, clarification_history=[], turn_count=0, last_tool_result=None, last_response_context=None, timestamp=time.time().
- **Status**: IMPLEMENTATO

### DM-015 Slot merge
- **Pattern EARS**: Il sistema DEVE eseguire merge degli slot con priorita' ai nuovi valori (new override existing), ignorando valori None e stringa vuota.
- **Status**: IMPLEMENTATO

### DM-016 Filter extraction
- **Pattern EARS**: Il sistema DEVE estrarre filtri "comune" e "limit" dai messaggi utente tramite regex, con limit validato tra 1 e 500.
- **Status**: IMPLEMENTATO

### DM-017 Turn count increment
- **Pattern EARS**: QUANDO il dialogue_manager elabora un messaggio, il sistema DEVE incrementare turn_count e aggiornare il timestamp nel DialogueState.
- **Status**: IMPLEMENTATO

### DM-018 DialogueState backwards compatibility
- **Pattern EARS**: Il sistema DEVE supportare conversione bidirezionale tra formato DialogueState nuovo e campi sessione legacy tramite from_session() e to_session().
- **Status**: IMPLEMENTATO

### DM-019 Workflow strategies configuration
- **Pattern EARS**: Il sistema DEVE supportare strategie workflow per ask_suggest_controls (3 strategie: planning, risk_nc, risk_mai_controllati), ask_priority_establishment (2 strategie: delayed, risk), ask_risk_based_priority (2 strategie: mai_controllati, con_sanzioni).
- **Status**: IMPLEMENTATO

### DM-020 Conversational intents set
- **Pattern EARS**: Il sistema DEVE riconoscere 6 intent conversazionali multi-turno: ask_suggest_controls, ask_priority_establishment, ask_risk_based_priority, ask_delayed_plans, ask_establishment_history, search_piani_by_topic.
- **Status**: IMPLEMENTATO

### DM-021 Strategy ID validation allowlist
- **Pattern EARS**: Il sistema DEVE validare strategy_id contro un'allowlist esplicita (STRATEGY_TO_INTENT_MAP) prima di eseguire il tool mappato, per prevenire esecuzione di strategie non autorizzate.
- **Status**: IMPLEMENTATO

### DM-022 Multi-candidate menu max 3
- **Pattern EARS**: QUANDO il sistema presenta un menu di disambiguazione, il sistema DEVE mostrare al massimo 3 opzioni con label e description da intent_metadata, con istruzione "Rispondi con il numero o riformula la domanda."
- **Status**: IMPLEMENTATO

### DM-023 Caso speciale ask_establishment_history slot
- **Pattern EARS**: QUANDO l'intent e' ask_establishment_history e mancano tutti gli slot identificativi, il sistema DEVE mostrare un messaggio specifico che chiede UNO tra num_registrazione, partita_iva, ragione_sociale con esempi.
- **Status**: IMPLEMENTATO

### DM-024 Rilevamento pattern vago
- **Pattern EARS**: Il sistema DEVE rilevare messaggi vaghi tramite VAGUE_PATTERNS (come mi organizzo, cosa devo fare, da dove inizio, aiutami a capire, indicazioni, consigli).
- **Status**: IMPLEMENTATO

### DM-025 Rilevamento pattern oppure
- **Pattern EARS**: Il sistema DEVE rilevare varianti di "oppure?" tramite OPPURE_PATTERNS (oppure, alternative, altro modo, altrimenti, altra opzione/possibilita).
- **Status**: IMPLEMENTATO

### DM-026 Rilevamento pattern refinement
- **Pattern EARS**: Il sistema DEVE rilevare raffinamenti tramite REFINEMENT_PATTERNS (nel comune di, solo nel/per/a, rifai la ricerca, stessa ricerca ma, mostra solo, primi N, top N).
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### DM-NF-001 Rule-based senza LLM
- **Pattern EARS**: Il sistema DEVE eseguire tutte le regole del dialogue_manager senza chiamate LLM aggiuntive, usando solo logica rule-based per velocita'.
- **Status**: IMPLEMENTATO

### DM-NF-002 DialogueState serializzabile
- **Pattern EARS**: Il sistema DEVE garantire che DialogueState sia serializzabile in JSON per storage in sessione HTTP stateless.
- **Status**: IMPLEMENTATO
