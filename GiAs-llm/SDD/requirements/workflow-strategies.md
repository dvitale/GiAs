# Workflow Strategies

**Componente**: Backend (GiAs-llm)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: `orchestrator/workflow_strategies.py`, `orchestrator/workflow_validator.py`

## Requisiti Funzionali

### WS-01 Strategie multi-turno per ask_suggest_controls
- **Pattern EARS**: QUANDO l'intent e' ask_suggest_controls, il sistema DEVE presentare 3 strategie: "dalla pianificazione" (mappa a ask_delayed_plans), "dall'analisi del rischio - non conformita'" (mappa a ask_top_risk_activities), "dall'analisi del rischio - mai controllati" (mappa a ask_risk_based_priority).
- **Status**: IMPLEMENTATO

### WS-02 Strategie multi-turno per ask_priority_establishment
- **Pattern EARS**: QUANDO l'intent e' ask_priority_establishment, il sistema DEVE presentare 2 strategie: "piani in ritardo" (mappa a ask_delayed_plans) e "rischio storico" (mappa a ask_risk_based_priority).
- **Status**: IMPLEMENTATO

### WS-03 Strategie multi-turno per ask_risk_based_priority
- **Pattern EARS**: QUANDO l'intent e' ask_risk_based_priority, il sistema DEVE presentare 2 strategie: "mai controllati" (stabilimenti senza controlli, ordinati per rischio attivita') e "con piu' sanzioni" (stabilimenti con piu' NC storiche), ciascuna con slot_value distinto.
- **Status**: IMPLEMENTATO

### WS-04 STRATEGY_TO_INTENT_MAP allowlist
- **Pattern EARS**: Il sistema DEVE mantenere un mapping esplicito STRATEGY_TO_INTENT_MAP che associa ogni strategy_id a un intent (strategy_planning -> ask_delayed_plans, strategy_risk_nc -> ask_top_risk_activities, strategy_risk_mai_controllati -> ask_risk_based_priority, priority_delayed -> ask_delayed_plans, priority_risk -> ask_risk_based_priority). Solo le strategie in questo mapping sono eseguibili.
- **Status**: IMPLEMENTATO

### WS-05 Validazione sicurezza nonce e workflow context
- **Pattern EARS**: Il sistema DEVE generare un token crittografico (secrets.token_urlsafe(32), 256 bit) per ogni workflow e validare che il nonce corrisponda. QUANDO viene ricevuto un workflow_context, il sistema DEVE validare: TTL non scaduto (max 300s), solo campi nella whitelist ALLOWED_WORKFLOW_FIELDS, workflow_type in ALLOWED_CONVERSATIONAL_INTENTS, workflow_stage valido (enum WorkflowStage), workflow_nonce presente. SE una validazione fallisce, il context DEVE essere invalidato.
- **Status**: IMPLEMENTATO
- **Accorpa**: WS-05, WS-06

### WS-07 Validazione filtri whitelist
- **Pattern EARS**: Il sistema DEVE validare e sanitizzare i filtri utente contro whitelist di dominio: comune contro VALID_COMUNI (~200 comuni su ~550 totali), ASL contro VALID_ASL (pattern [A-Z]{2}[0-9]), limit con bounds checking [1, 500], UOC con pattern alfanumerico (max 100 char), piano_code con pattern [A-Z]+[0-9]+(?:_[A-Z]+)?, tipo_attivita con sotto-campi alfanumerici (max 200 char), date in formato ISO YYYY-MM-DD, categoria contro set di NC valide.
- **Status**: IMPLEMENTATO
- **Note**: VALID_COMUNI contiene ~200 comuni campani su ~550 totali, annotato come "da completare prima del deployment".

### WS-08 Validazione strategy_id per workflow
- **Pattern EARS**: QUANDO viene selezionata una strategia in un workflow, il sistema DEVE verificare che lo strategy_id sia tra le strategie configurate per il workflow_type specifico, prevenendo l'esecuzione di strategie non autorizzate.
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### WS-NF01 Set intent conversazionali
- **Pattern EARS**: Il sistema DEVE mantenere un set CONVERSATIONAL_INTENTS di 6 intent che supportano workflow multi-turno: ask_suggest_controls, ask_priority_establishment, ask_risk_based_priority, ask_delayed_plans, ask_establishment_history, search_piani_by_topic. La funzione is_conversational_intent() verifica l'appartenenza.
- **Status**: IMPLEMENTATO

### WS-NF02 Pattern estrazione filtri e trust boundary
- **Pattern EARS**: Il sistema DEVE definire pattern regex per l'estrazione automatica di filtri dal testo utente: comune, ASL, limit, tipo_attivita con sotto-pattern. Il sistema DEVE trattare workflow_context come NON trusted anche se server-side, applicando whitelist campi, validazione tipo, TTL enforcement e nonce freshness.
- **Status**: IMPLEMENTATO
- **Accorpa**: WS-NF02, WS-NF03
