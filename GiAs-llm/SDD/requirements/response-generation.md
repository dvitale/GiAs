# Generazione Risposta

**Componente**: Backend (GiAs-llm)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: `orchestrator/response_node.py`, `orchestrator/followup_suggestions.py`

## Requisiti Funzionali

### RG-001 Bypass LLM per formatted_response e intent diretti
- **Pattern EARS**: QUANDO il tool_output contiene un campo `formatted_response` nel dizionario `data`, il sistema DEVE usare direttamente quel testo come risposta finale senza invocare il LLM. QUANDO l'intent e' uno tra `greet`, `goodbye`, `fallback`, `confirm_show_details`, `decline_show_details` oppure il tool_type e' `fallback`, il sistema DEVE restituire la `formatted_response` senza passaggio LLM.
- **Status**: IMPLEMENTATO
- **Accorpa**: RG-001, RG-002

### RG-003 Generazione risposta LLM con system prompt e pulizia
- **Pattern EARS**: QUANDO il tool_output non contiene `formatted_response` e l'intent non e' in DIRECT_RESPONSE_INTENTS, il sistema DEVE generare la risposta tramite chiamata LLM con system prompt (RESPONSE_SYSTEM_PROMPT) che istruisce a spiegare risultati, motivare priorita', fornire valore aggiunto, usare la formula Risk Score corretta, formattare con markdown. Il sistema DEVE popolare il template utente (RESPONSE_USER_TEMPLATE) con descrizione contesto, messaggio originale, tipo analisi e dati ottenuti. Il sistema DEVE rimuovere sequenze di 3 o piu' newline consecutive riducendole a massimo 2.
- **Status**: IMPLEMENTATO
- **Accorpa**: RG-003, RG-004, RG-005

### RG-006 Pulizia newline eccessive
- **Pattern EARS**: QUANDO la risposta viene generata (sia da formatted_response che da LLM), il sistema DEVE rimuovere sequenze di 3 o piu' newline consecutive riducendole a massimo 2.
- **Status**: IMPLEMENTATO

### RG-007 Gestione errore generazione LLM
- **Pattern EARS**: SE la chiamata LLM fallisce con eccezione, il sistema DEVE impostare la risposta finale a "Errore: {messaggio_errore}".
- **Status**: IMPLEMENTATO

### RG-008 Evento SSE status per response_generator
- **Pattern EARS**: QUANDO il nodo response_generator viene invocato con un event_callback attivo, il sistema DEVE emettere un evento SSE di tipo `status` con nodo `response_generator` e messaggio "Generando risposta...".
- **Status**: IMPLEMENTATO

### RG-009 Suggerimenti follow-up con esclusioni e limiti
- **Pattern EARS**: Il sistema DEVE NON appendere suggerimenti follow-up quando: two-phase attivo, intent in EXCLUDED_INTENTS (greet, goodbye, ask_help, confirm_show_details, decline_show_details, fallback), tool_output con errore, o risposta inferiore a 50 caratteri. Il sistema DEVE restituire al massimo 3 suggerimenti. Ogni suggerimento DEVE essere un dizionario con chiavi `text` e `query`, salvato nello state come lista strutturata nel campo `suggestions`. QUANDO viene generato un suggerimento, il sistema DEVE utilizzare un handler specifico per l'intent corrente (dispatch map con 13 handler).
- **Status**: IMPLEMENTATO
- **Accorpa**: RG-009, RG-010, RG-011, RG-012

### RG-013 Suggerimenti contestuali per intent e RAG
- **Pattern EARS**: QUANDO l'intent e' `info_procedure`, il sistema DEVE generare suggerimenti dinamici basati sui metadati dei chunk RAG (sezioni, titoli, documenti sorgente), filtrando sezioni generiche e aggiungendo documenti alternativi. SE non sono disponibili metadati chunk, il sistema DEVE restituire suggerimenti fallback statici: "Controllo ufficiale" e "Non conformita'".
- **Status**: IMPLEMENTATO
- **Accorpa**: RG-013, RG-016

### RG-014 Estrazione contesto risposta per risoluzione anaforica
- **Pattern EARS**: QUANDO il sistema genera una risposta, il sistema DEVE estrarre un breve contesto (~50-100 caratteri) dalla risposta combinando: info da slot, dati dal tool_output, pattern numerici dalla risposta testuale, e descrizione dell'intent. Il contesto viene salvato nel campo `response_context` dello state.
- **Status**: IMPLEMENTATO

### RG-015 Formattazione markdown suggerimenti
- **Pattern EARS**: QUANDO i suggerimenti vengono formattati come testo, il sistema DEVE utilizzare un header separatore ("---") seguito da "**Vuoi approfondire?** Ecco cosa posso fare:" e ogni suggerimento come lista markdown con link.
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### RG-NF-001 Risparmio latenza con bypass LLM
- **Pattern EARS**: DOVE disponibile una formatted_response, il sistema DEVE evitare la chiamata LLM risparmiando circa 800ms-1.5s su CPU.
- **Status**: IMPLEMENTATO

### RG-NF-002 Singleton engine follow-up
- **Pattern EARS**: Il sistema DEVE istanziare FollowUpSuggestionEngine come singleton a livello di modulo per evitare allocazioni ripetute.
- **Status**: IMPLEMENTATO
