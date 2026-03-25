# Risposta Two-Phase

**Componente**: Backend (GiAs-llm)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: `orchestrator/two_phase.py`, `orchestrator/tool_nodes.py`

## Requisiti Funzionali

### TP-001 Attivazione two-phase per soglia con suffisso
- **Pattern EARS**: Il sistema DEVE applicare soglie two-phase specifiche per intent: ask_establishment_history=3, ask_risk_based_priority=3, ask_priority_establishment=3, ask_suggest_controls=3, search_piani_by_topic=3, ask_piano_stabilimenti=3, ask_nearby_priority=10 (default 5). QUANDO il numero di item supera la soglia, il sistema DEVE salvare la risposta completa in detail_context (con formatted_response, intent, item_count), sostituire formatted_response con il testo di sommario, appendere il suffisso "\n\n---\n**Vuoi vedere tutti i dettagli?** (rispondi *si* o *no*)", e impostare has_more_details=True.
- **Status**: IMPLEMENTATO
- **Accorpa**: TP-001, TP-002, TP-003

### TP-004 Detail context con risposta completa
- **Pattern EARS**: QUANDO un tool fornisce full_formatted_response (risposta senza limiti di display), il sistema DEVE salvare quella nel detail_context al posto di result["formatted_response"] che potrebbe essere troncata.
- **Status**: IMPLEMENTATO

### TP-005 Risposta conferma, rifiuto e sessione scaduta
- **Pattern EARS**: QUANDO l'utente conferma (intent confirm_show_details) e detail_context e' presente, il sistema DEVE restituire la formatted_response salvata. QUANDO l'utente rifiuta (intent decline_show_details), il sistema DEVE restituire "Va bene! Se hai altre domande, sono qui per aiutarti." con confirmed=False. SE l'utente conferma ma detail_context non e' presente (sessione scaduta), il sistema DEVE restituire un messaggio informativo con 3 esempi di domande.
- **Status**: IMPLEMENTATO
- **Accorpa**: TP-005, TP-006, TP-007

### TP-008 Non-attivazione sotto soglia
- **Pattern EARS**: QUANDO il numero di item e' inferiore o uguale alla soglia dell'intent, il sistema DEVE restituire la risposta completa senza attivare il meccanismo two-phase (has_more_details=False).
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### TP-NF-001 Modifica in-place
- **Pattern EARS**: Il sistema DEVE modificare lo state in-place (has_more_details, detail_context) e restituire result potenzialmente modificato, senza creare copie inutili degli oggetti.
- **Status**: IMPLEMENTATO
