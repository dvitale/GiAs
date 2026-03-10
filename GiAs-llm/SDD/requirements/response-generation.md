# Generazione Risposta

**Componente**: Backend (GiAs-llm)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: `orchestrator/response_node.py`, `orchestrator/followup_suggestions.py`

## Requisiti Funzionali

### RG-001 Bypass LLM per intent con formatted_response
- **Pattern EARS**: QUANDO il tool_output contiene un campo `formatted_response` nel dizionario `data`, il sistema DEVE usare direttamente quel testo come risposta finale senza invocare il LLM.
- **Status**: IMPLEMENTATO

### RG-002 Risposta diretta per intent semplici (DIRECT_RESPONSE_INTENTS)
- **Pattern EARS**: QUANDO l'intent e' uno tra `greet`, `goodbye`, `fallback`, `confirm_show_details`, `decline_show_details` oppure il tool_type e' `fallback`, il sistema DEVE restituire la `formatted_response` (o la stringa del dato) senza passaggio LLM.
- **Status**: IMPLEMENTATO

### RG-003 Generazione risposta LLM come fallback
- **Pattern EARS**: QUANDO il tool_output non contiene `formatted_response` e l'intent non e' in DIRECT_RESPONSE_INTENTS, il sistema DEVE generare la risposta tramite chiamata LLM con system prompt e user template strutturati.
- **Status**: IMPLEMENTATO

### RG-004 System prompt per generazione risposta
- **Pattern EARS**: Il sistema DEVE utilizzare un system prompt (RESPONSE_SYSTEM_PROMPT) che istruisce il LLM a: spiegare risultati, motivare priorita', fornire valore aggiunto, usare la formula Risk Score corretta (P(NC) x Impatto x 100), usare tono formale, non inventare dati, e formattare con markdown.
- **Status**: IMPLEMENTATO

### RG-005 Template utente contestualizzato per intent
- **Pattern EARS**: QUANDO il sistema genera la risposta LLM, il sistema DEVE popolare il template utente (RESPONSE_USER_TEMPLATE) con: descrizione contesto dall'intent (da INTENT_DESCRIPTIONS), messaggio originale, tipo di analisi (intent), e dati ottenuti (formatted_response o stringa raw).
- **Status**: IMPLEMENTATO

### RG-006 Pulizia newline eccessive
- **Pattern EARS**: QUANDO la risposta viene generata (sia da formatted_response che da LLM), il sistema DEVE rimuovere sequenze di 3 o piu' newline consecutive riducendole a massimo 2.
- **Status**: IMPLEMENTATO

### RG-007 Gestione errore generazione LLM
- **Pattern EARS**: SE la chiamata LLM fallisce con eccezione, il sistema DEVE impostare la risposta finale a "Errore: {messaggio_errore}".
- **Status**: IMPLEMENTATO

### RG-008 Evento SSE status per response_generator
- **Pattern EARS**: QUANDO il nodo response_generator viene invocato con un event_callback attivo, il sistema DEVE emettere un evento SSE di tipo `status` con nodo `response_generator` e messaggio "Generando risposta...".
- **Status**: IMPLEMENTATO

### RG-009 Condizioni di esclusione suggerimenti follow-up
- **Pattern EARS**: Il sistema DEVE NON appendere suggerimenti follow-up quando: (a) two-phase e' attivo (has_more_details=True), (b) l'intent e' in EXCLUDED_INTENTS (greet, goodbye, ask_help, confirm_show_details, decline_show_details, fallback), (c) il tool_output contiene un errore, (d) la risposta finale e' vuota o inferiore a 50 caratteri.
- **Status**: IMPLEMENTATO

### RG-010 Limite massimo suggerimenti follow-up
- **Pattern EARS**: Il sistema DEVE restituire al massimo 3 suggerimenti di follow-up per ogni risposta, troncando la lista se il generatore ne produce di piu'.
- **Status**: IMPLEMENTATO

### RG-011 Formato suggerimenti follow-up
- **Pattern EARS**: Il sistema DEVE formattare ogni suggerimento come dizionario con chiavi `text` (testo leggibile) e `query` (query da inviare al sistema), e salvarli nello state come lista strutturata nel campo `suggestions`.
- **Status**: IMPLEMENTATO

### RG-012 Suggerimenti contestuali per intent specifici
- **Pattern EARS**: QUANDO viene generato un suggerimento, il sistema DEVE utilizzare un handler specifico per l'intent corrente (dispatch map con 13 handler: ask_piano_description, ask_piano_stabilimenti, ask_piano_statistics, search_piani_by_topic, ask_priority_establishment, ask_risk_based_priority, ask_suggest_controls, ask_delayed_plans, check_if_plan_delayed, ask_establishment_history, ask_top_risk_activities, analyze_nc_by_category, info_procedure).
- **Status**: IMPLEMENTATO

### RG-013 Suggerimenti RAG dinamici da metadati chunk
- **Pattern EARS**: QUANDO l'intent e' `info_procedure`, il sistema DEVE generare suggerimenti dinamici basati sui metadati dei chunk RAG (sezioni, titoli, documenti sorgente), estraendo sezioni dal chunk 2-4 (skip primo), filtrando sezioni generiche (introduzione, premessa, indice, allegati, figure), e aggiungendo documenti alternativi se disponibili.
- **Status**: IMPLEMENTATO

### RG-014 Estrazione contesto risposta per risoluzione anaforica
- **Pattern EARS**: QUANDO il sistema genera una risposta, il sistema DEVE estrarre un breve contesto (~50-100 caratteri) dalla risposta combinando: info da slot (piano_code, topic, num_registrazione, ragione_sociale, categoria), dati dal tool_output (varianti, count, total, total_controls, unique_establishments), pattern numerici dalla risposta testuale, e descrizione dell'intent. Il contesto viene salvato nel campo `response_context` dello state.
- **Status**: IMPLEMENTATO

### RG-015 Formattazione markdown suggerimenti
- **Pattern EARS**: QUANDO i suggerimenti vengono formattati come testo, il sistema DEVE utilizzare un header separatore ("---") seguito da "**Vuoi approfondire?** Ecco cosa posso fare:" e ogni suggerimento come lista markdown con link: "- [{testo}]".
- **Status**: IMPLEMENTATO

### RG-016 Fallback suggerimenti per info_procedure senza metadati
- **Pattern EARS**: SE l'intent e' `info_procedure` e non sono disponibili metadati chunk, il sistema DEVE restituire suggerimenti fallback statici: "Controllo ufficiale" e "Non conformita'".
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### RG-NF-001 Risparmio latenza con bypass LLM
- **Pattern EARS**: DOVE disponibile una formatted_response, il sistema DEVE evitare la chiamata LLM risparmiando circa 800ms-1.5s su CPU.
- **Status**: IMPLEMENTATO

### RG-NF-002 Singleton engine follow-up
- **Pattern EARS**: Il sistema DEVE istanziare FollowUpSuggestionEngine come singleton a livello di modulo per evitare allocazioni ripetute.
- **Status**: IMPLEMENTATO
