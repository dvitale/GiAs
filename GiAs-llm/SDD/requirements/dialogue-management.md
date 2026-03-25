# Gestione Dialogo

**Componente**: Backend (GiAs-llm)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: `orchestrator/dialogue_manager.py`, `orchestrator/dialogue_state.py`, `orchestrator/workflow_strategies.py`

## Requisiti Funzionali

### DM-001 Soglie confidence adattive per modello
- **Pattern EARS**: Il sistema DEVE configurare soglie confidence diverse per modello LLM: llama3.2 (high=0.60, min=0.35, delta=0.15), velvet (high=0.80, min=0.50, delta=0.20), mistral-nemo (high=0.80, min=0.50, delta=0.20), llama3.1 (high=0.75, min=0.45, delta=0.20), ministral (high=0.65, min=0.40, delta=0.18), falcon (high=0.65, min=0.40, delta=0.18), google/gemini-2.5-flash (high=0.80, min=0.50, delta=0.20), con default (high=0.80, min=0.50, delta=0.20).
- **Status**: IMPLEMENTATO

### DM-002 Regole 0-1: slot continuation e intent chiaro
- **Pattern EARS**: QUANDO il DialogueState ha un confirmed_intent con missing_slots e l'utente fornisce slot estratti che riempiono quelli mancanti, il sistema DEVE eseguire direttamente il tool associato senza ri-classificare (Regola 0). QUANDO la confidence del candidato top e' >= CONFIDENCE_HIGH e tutti gli slot obbligatori sono presenti (o l'intent e' self-sufficient), il sistema DEVE eseguire direttamente il tool corrispondente (Regola 1).
- **Status**: IMPLEMENTATO
- **Accorpa**: DM-002, DM-003

### DM-004 Regole 1bis-3: proposta strategia, slot mancanti, ambiguita'
- **Pattern EARS**: QUANDO l'intent e' in CONVERSATIONAL_INTENTS, ha strategie configurate, non ha gia' una strategia confermata, e il messaggio e' vago, il sistema DEVE proporre la domanda di scelta strategia (Regola 1bis). QUANDO la confidence e' >= CONFIDENCE_HIGH ma mancano slot obbligatori, il sistema DEVE salvare l'intent come confirmed_intent, registrare i missing_slots, e chiedere all'utente con _build_slot_question (Regola 2). QUANDO ci sono >= 2 candidati, la confidence top e' >= CONFIDENCE_MIN, e la differenza tra top e secondo e' < CONFIDENCE_AMBIGUITY_DELTA, il sistema DEVE presentare un menu di disambiguazione con max 3 opzioni (Regola 3).
- **Status**: IMPLEMENTATO
- **Accorpa**: DM-004, DM-005, DM-006

### DM-007 Regole 4-5: nessun candidato e refinement
- **Pattern EARS**: QUANDO la confidence del candidato top e' < CONFIDENCE_MIN, il sistema DEVE attivare il fallback (Regola 4). QUANDO il messaggio e' un raffinamento (_is_refinement) e c'e' un last_tool_intent nel DialogueState, il sistema DEVE ri-eseguire il tool precedente con slot e filtri aggiornati (Regola 5).
- **Status**: IMPLEMENTATO
- **Accorpa**: DM-007, DM-008

### DM-009 Regole 6-7: conferma strategia e oppure cycling
- **Pattern EARS**: QUANDO il messaggio e' una conferma e il DialogueState ha confirmed_intent + confirmed_strategy_id, il sistema DEVE trovare la strategia corrispondente, mappare all'intent_mapping e eseguire il tool associato (Regola 6). QUANDO il messaggio e' "oppure?" e c'e' un confirmed_intent con strategie, il sistema DEVE ciclare alla strategia successiva e proporre l'alternativa (Regola 7). QUANDO il messaggio e' "oppure?" ma l'intent non ha strategie alternative, il sistema DEVE rispondere "Non ci sono alternative disponibili per questa richiesta."
- **Status**: IMPLEMENTATO
- **Accorpa**: DM-009, DM-010, DM-011

### DM-012 Default - confidence media
- **Pattern EARS**: QUANDO la confidence e' tra CONFIDENCE_MIN e CONFIDENCE_HIGH e nessuna altra regola si applica, il sistema DEVE tentare di eseguire il tool se gli slot sono completi, altrimenti chiedere slot mancanti.
- **Status**: IMPLEMENTATO

### DM-013 DialogueState con TTL 300s e creazione vuota
- **Pattern EARS**: QUANDO il DialogueState ha un timestamp piu' vecchio di 300 secondi (DIALOGUE_STATE_TTL), il sistema DEVE considerarlo invalido e crearne uno nuovo vuoto. Il sistema DEVE creare DialogueState vuoti con goal=None, intent_candidates=[], confirmed_intent=None, confirmed_strategy=None, confirmed_strategy_id=None, slots={}, missing_slots=[], filters={}, clarification_history=[], turn_count=0, last_tool_result=None, last_response_context=None, timestamp=time.time().
- **Status**: IMPLEMENTATO
- **Accorpa**: DM-013, DM-014

### DM-015 Slot merge, filter extraction e turn count
- **Pattern EARS**: Il sistema DEVE eseguire merge degli slot con priorita' ai nuovi valori (new override existing), ignorando valori None e stringa vuota. Il sistema DEVE estrarre filtri "comune" e "limit" dai messaggi utente tramite regex, con limit validato tra 1 e 500. QUANDO il dialogue_manager elabora un messaggio, il sistema DEVE incrementare turn_count e aggiornare il timestamp nel DialogueState.
- **Status**: IMPLEMENTATO
- **Accorpa**: DM-015, DM-016, DM-017

### DM-018 DialogueState backwards compatibility
- **Pattern EARS**: Il sistema DEVE supportare conversione bidirezionale tra formato DialogueState nuovo e campi sessione legacy tramite from_session() e to_session().
- **Status**: IMPLEMENTATO

### ~~DM-019, DM-020, DM-021~~ RIMOSSO — Duplicato di WS-01..WS-04, WS-NF01
- Vedi `workflow-strategies.md` per strategie workflow, intent conversazionali e validazione strategy_id.

### DM-022 Multi-candidate menu max 3
- **Pattern EARS**: QUANDO il sistema presenta un menu di disambiguazione, il sistema DEVE mostrare al massimo 3 opzioni con label e description da intent_metadata, con istruzione "Rispondi con il numero o riformula la domanda."
- **Status**: IMPLEMENTATO

### DM-023 Caso speciale ask_establishment_history slot
- **Pattern EARS**: QUANDO l'intent e' ask_establishment_history e mancano tutti gli slot identificativi, il sistema DEVE mostrare un messaggio specifico che chiede UNO tra num_registrazione, partita_iva, ragione_sociale con esempi.
- **Status**: IMPLEMENTATO

### DM-024 Pattern detection (vago, oppure, refinement)
- **Pattern EARS**: Il sistema DEVE rilevare messaggi vaghi tramite VAGUE_PATTERNS (come mi organizzo, cosa devo fare, da dove inizio, aiutami a capire, indicazioni, consigli). Il sistema DEVE rilevare varianti di "oppure?" tramite OPPURE_PATTERNS (oppure, alternative, altro modo, altrimenti, altra opzione/possibilita). Il sistema DEVE rilevare raffinamenti tramite REFINEMENT_PATTERNS (nel comune di, solo nel/per/a, rifai la ricerca, stessa ricerca ma, mostra solo, primi N, top N).
- **Status**: IMPLEMENTATO
- **Accorpa**: DM-024, DM-025, DM-026

## Requisiti Non Funzionali

### DM-NF-001 Rule-based senza LLM
- **Pattern EARS**: Il sistema DEVE eseguire tutte le regole del dialogue_manager senza chiamate LLM aggiuntive, usando solo logica rule-based per velocita'.
- **Status**: IMPLEMENTATO

### DM-NF-002 DialogueState serializzabile
- **Pattern EARS**: Il sistema DEVE garantire che DialogueState sia serializzabile in JSON per storage in sessione HTTP stateless.
- **Status**: IMPLEMENTATO
