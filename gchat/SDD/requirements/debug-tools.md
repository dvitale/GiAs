# Debug Tools

**Componente**: Frontend (gchat)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: statics/js/debug_langgraph.js, statics/js/debug_langgraph_visualizer.js, template/debug.html, template/debug_langgraph.html

## Requisiti Funzionali

### DT-01 Dual Call Parse + Chat
- **Pattern EARS**: QUANDO l'utente invia un messaggio nella pagina debug, il sistema DEVE inviare la richiesta a POST `/debug/chat` che esegue sia Parse NLU (`/api/v1/parse`) sia Chat (`/api/v1/chat`) e restituisce i risultati combinati.
- **Status**: IMPLEMENTATO

### DT-02 Pannello Intent Classification
- **Pattern EARS**: QUANDO una risposta debug arriva, il sistema DEVE mostrare nel pannello Intent: il nome dell'intent, una descrizione user-friendly, una barra di confidence percentuale e l'etichetta "(LLM Router)".
- **Status**: IMPLEMENTATO

### DT-03 Pannello Entities Estratte
- **Pattern EARS**: QUANDO una risposta debug contiene entities, il sistema DEVE elencarle come coppie nome-valore nel pannello Entities.
- **Status**: IMPLEMENTATO

### DT-04 Pannello Agents Eseguiti
- **Pattern EARS**: QUANDO una risposta debug arriva, il sistema DEVE mostrare gli agent eseguiti nel pannello Agents con badge colorati per categoria.
- **Status**: IMPLEMENTATO

### DT-05 Pannello Conversation State
- **Pattern EARS**: QUANDO una risposta debug arriva, il sistema DEVE mostrare i metadata (asl, asl_id, user_id, codice_fiscale, username con source "context") e gli slot estratti (piano_code, topic, etc. con source "extracted") nel pannello State.
- **Status**: IMPLEMENTATO

### DT-06 19 Intent Descriptions
- **Pattern EARS**: Il sistema DEVE mappare 19 intent a descrizioni italiane user-friendly: greet->Saluto, goodbye->Congedo, ask_help->Richiesta aiuto, ask_piano_stabilimenti, ask_piano_description, ask_piano_statistics, search_piani_by_topic, ask_priority_establishment, ask_risk_based_priority, ask_suggest_controls, ask_nearby_priority, ask_delayed_plans, check_if_plan_delayed, ask_establishment_history, ask_top_risk_activities, analyze_nc_by_category, info_procedure, confirm_show_details, decline_show_details, fallback.
- **Status**: IMPLEMENTATO

### DT-07 19 Tool-Agent Mappings con Categorie Colorate
- **Pattern EARS**: Il sistema DEVE mappare 19 tool backend a informazioni agent con categorie colorate: piano (#3b82f6), search (#10b981), priority (#f59e0b), risk (#ef4444), nc (#8b5cf6), history (#06b6d4), procedure (#14b8a6), proximity (#f97316), conversation (#6b7280).
- **Status**: IMPLEMENTATO

### DT-08 Execution Path Priorita'
- **Pattern EARS**: QUANDO si determinano gli agent eseguiti, il sistema DEVE usare in ordine di priorita': (1) `execution_path` dalla risposta, (2) `executed_actions` dal tracker, (3) mappatura intent->tool come fallback.
- **Status**: IMPLEMENTATO

### DT-09 Simulated Path Fallback
- **Pattern EARS**: SE il backend non fornisce un execution_path, il sistema Go DEVE generare un path simulato basato sull'intent tramite `determineExecutionPath` con nodi base [input, classify, dialogue_manager] + tool specifico + response_generator.
- **Status**: IMPLEMENTATO

### DT-10 Responsive Grid Debug
- **Pattern EARS**: MENTRE lo schermo e' piu' largo di 1200px, il sistema DEVE mostrare il layout debug in 2 colonne (chat area + debug panel 400px). Sotto 1200px, DEVE passare a layout a singola colonna.
- **Status**: IMPLEMENTATO

### DT-11 Query Params Preservazione
- **Pattern EARS**: Il sistema DEVE preservare i queryParams nei link di navigazione tra le pagine debug (Chat, Analytics, Monitor, Debug, LangGraph).
- **Status**: IMPLEMENTATO

### DT-12 Architecture Badge
- **Pattern EARS**: Il sistema DEVE mostrare un badge nell'header con framework e modello LLM nel formato "{framework} + {llmModel}", con fallback a "LangGraph + LLM" se non disponibili.
- **Status**: IMPLEMENTATO

### DT-13 Timeout 75s Debug
- **Pattern EARS**: QUANDO si invia un messaggio nella pagina debug, il sistema DEVE applicare un timeout di 75 secondi tramite AbortController.
- **Status**: IMPLEMENTATO

### DT-14 LangGraph SVG Visualizer
- **Pattern EARS**: La pagina debug_langgraph DEVE includere un visualizzatore SVG inline del workflow LangGraph con nodi interattivi.
- **Status**: IMPLEMENTATO

### DT-15 Tab System LangGraph
- **Pattern EARS**: La pagina debug_langgraph DEVE mostrare un sistema a tab con almeno: visualizzazione esecuzione, dettagli nodi e metriche.
- **Status**: IMPLEMENTATO

### DT-16 Query History LangGraph
- **Pattern EARS**: La pagina debug_langgraph DEVE mantenere uno storico delle query inviate durante la sessione.
- **Status**: IMPLEMENTATO

### DT-17 Sender ID Debug
- **Pattern EARS**: Il sistema DEVE generare un sender ID stabile per la sessione debug nel formato `debug_user_` + timestamp per supportare two-phase e memoria conversazionale.
- **Status**: IMPLEMENTATO

### DT-18 Initial State Loading
- **Pattern EARS**: QUANDO la pagina debug si carica, il sistema DEVE mostrare i metadata iniziali (dal queryParams) nel pannello Conversation State.
- **Status**: IMPLEMENTATO

### DT-19 User Context Display
- **Pattern EARS**: DOVE i dati utente sono disponibili, la pagina debug DEVE mostrare nome, cognome, ASL e User ID nell'header con icone.
- **Status**: IMPLEMENTATO

### DT-20 Dark Theme Debug Page
- **Pattern EARS**: La pagina debug DEVE supportare il tema dark con variabili CSS specifiche per background slate/indaco, testo chiaro e panel con bordi scuri.
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### DT-NF01 Tema Persistente
- **Pattern EARS**: Il sistema DEVE inizializzare il tema dark/light da localStorage su entrambe le pagine debug.
- **Status**: IMPLEMENTATO
