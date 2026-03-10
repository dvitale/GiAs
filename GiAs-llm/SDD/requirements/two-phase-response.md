# Risposta Two-Phase

**Componente**: Backend (GiAs-llm)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: `orchestrator/two_phase.py`, `orchestrator/tool_nodes.py`

## Requisiti Funzionali

### TP-001 Soglie per intent
- **Pattern EARS**: Il sistema DEVE applicare soglie two-phase specifiche per intent: ask_establishment_history=3, ask_risk_based_priority=3, ask_priority_establishment=3, ask_suggest_controls=3, search_piani_by_topic=3, ask_piano_stabilimenti=3, ask_nearby_priority=10. Per intent non elencati, il sistema DEVE usare la soglia default di 5.
- **Status**: IMPLEMENTATO

### TP-002 Attivazione two-phase
- **Pattern EARS**: QUANDO il numero di item nel risultato supera la soglia dell'intent, il sistema DEVE salvare la risposta completa in detail_context (con formatted_response, intent, item_count), sostituire formatted_response con il testo di sommario + suffisso two-phase, e impostare has_more_details=True nello state.
- **Status**: IMPLEMENTATO

### TP-003 Suffisso two-phase
- **Pattern EARS**: QUANDO la risposta two-phase e' attivata, il sistema DEVE appendere al sommario il testo: "\n\n---\n**Vuoi vedere tutti i dettagli?** (rispondi *si* o *no*)".
- **Status**: IMPLEMENTATO

### TP-004 Detail context con risposta completa
- **Pattern EARS**: QUANDO un tool fornisce full_formatted_response (risposta senza limiti di display), il sistema DEVE salvare quella nel detail_context al posto di result["formatted_response"] che potrebbe essere troncata.
- **Status**: IMPLEMENTATO

### TP-005 Conferma visualizzazione dettagli
- **Pattern EARS**: QUANDO l'utente conferma (intent confirm_show_details) e detail_context e' presente nel metadata, il sistema DEVE restituire la formatted_response salvata nel detail_context.
- **Status**: IMPLEMENTATO

### TP-006 Rifiuto visualizzazione dettagli
- **Pattern EARS**: QUANDO l'utente rifiuta (intent decline_show_details), il sistema DEVE restituire "Va bene! Se hai altre domande, sono qui per aiutarti." con confirmed=False.
- **Status**: IMPLEMENTATO

### TP-007 Sessione scaduta per conferma
- **Pattern EARS**: SE l'utente conferma ma detail_context non e' presente (sessione scaduta o contesto perso), il sistema DEVE restituire un messaggio informativo che invita a ripetere la domanda originale con 3 esempi di domande possibili.
- **Status**: IMPLEMENTATO

### TP-008 Non-attivazione sotto soglia
- **Pattern EARS**: QUANDO il numero di item e' inferiore o uguale alla soglia dell'intent, il sistema DEVE restituire la risposta completa senza attivare il meccanismo two-phase (has_more_details=False).
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### TP-NF-001 Modifica in-place
- **Pattern EARS**: Il sistema DEVE modificare lo state in-place (has_more_details, detail_context) e restituire result potenzialmente modificato, senza creare copie inutili degli oggetti.
- **Status**: IMPLEMENTATO
