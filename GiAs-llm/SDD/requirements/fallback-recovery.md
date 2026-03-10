# Fallback Recovery

**Componente**: Backend (GiAs-llm)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: `orchestrator/fallback_recovery.py`, `orchestrator/intent_metadata.py`

## Requisiti Funzionali

### FR-001 Engine a 3 fasi per recupero fallback
- **Pattern EARS**: QUANDO la classificazione intent fallisce, il sistema DEVE eseguire un engine a 3 fasi: (1) Keyword Matching veloce, (2) LLM Semantic Scoring per casi ambigui, (3) Menu Categorizzato a 2 livelli come ultima risorsa.
- **Status**: IMPLEMENTATO

### FR-002 Fase 1 - Keyword Matching con scoring ponderato
- **Pattern EARS**: QUANDO viene eseguita la Fase 1, il sistema DEVE calcolare uno score per ogni intent in INTENT_REGISTRY usando: +10 punti per ogni primary keyword trovata nel messaggio, +5 punti per ogni context keyword, -50 punti per ogni negative keyword. Gli intent con score >= threshold (default 15) vengono proposti.
- **Status**: IMPLEMENTATO

### FR-003 Esclusione intent interni dal keyword matching
- **Pattern EARS**: MENTRE calcola gli score keyword, il sistema DEVE escludere gli intent `fallback`, `confirm_show_details` e `decline_show_details` dalla lista candidati.
- **Status**: IMPLEMENTATO

### FR-004 Cache risultati keyword matching
- **Pattern EARS**: Il sistema DEVE mantenere una cache in-memory dei risultati keyword matching per messaggio normalizzato (lowercase, strip) per evitare ricalcoli su messaggi identici.
- **Status**: IMPLEMENTATO

### FR-005 Fase 2 - LLM Semantic Scoring
- **Pattern EARS**: QUANDO la Fase 1 produce 0 o 1 suggerimento e la fase LLM e' abilitata (enable_llm_phase=True, phase >= 2), il sistema DEVE invocare il LLM per scoring semantico con temperature 0.1, max_tokens 300, richiedendo un JSON array di max 3 intent ordinati per rilevanza.
- **Status**: PARZIALE
- **Note**: Il codice invoca `self.llm_client.chat()` ma il metodo del client LLM e' `query()`. Il metodo `chat()` non esiste nella classe LLMClient, causando un errore a runtime.

### FR-006 Timeout Fase LLM
- **Pattern EARS**: SE la chiamata LLM nella Fase 2 impiega piu' di 5 secondi (configurabile via `llm_timeout`), il sistema DEVE abbandonare i risultati LLM e procedere senza essi.
- **Status**: PARZIALE
- **Note**: Il timeout viene verificato dopo la risposta (post-hoc) anziche' come timeout di connessione. La chiamata potrebbe bloccare oltre il timeout configurato.

### FR-007 Merge suggerimenti keyword + LLM
- **Pattern EARS**: QUANDO sia la Fase 1 che la Fase 2 producono suggerimenti, il sistema DEVE combinarli rimuovendo duplicati (per intent_id) e ordinarli per score decrescente.
- **Status**: IMPLEMENTATO

### FR-008 Fase 3 - Menu categorizzato a 2 livelli
- **Pattern EARS**: QUANDO phase=3 o viene specificata una categoria, il sistema DEVE mostrare un menu strutturato: livello 1 mostra le categorie (6 categorie escluso "Altro"), livello 2 mostra gli intent della categoria selezionata con label, descrizione ed emoji.
- **Status**: IMPLEMENTATO

### FR-009 Suggerimenti con categorie appendate
- **Pattern EARS**: QUANDO la Fase 1 o 2 produce suggerimenti intent, il sistema DEVE appendere le categorie disponibili come opzioni aggiuntive dopo i suggerimenti (tipo "intent" + tipo "category").
- **Status**: IMPLEMENTATO

### FR-010 Parsing selezione utente numerica e testuale
- **Pattern EARS**: QUANDO l'utente risponde ai suggerimenti, il sistema DEVE riconoscere selezioni numeriche (es. "1", "opzione 2", "scegli 3", "numero 4", "scelta 5") e selezioni testuali (match per label esatto o parziale).
- **Status**: IMPLEMENTATO

### FR-011 Formattazione messaggio suggerimenti
- **Pattern EARS**: Il sistema DEVE formattare i suggerimenti con: messaggio introduttivo, sezione "Suggerimenti basati sulla tua richiesta" per intent (numerati con emoji), sezione "Scegli per categoria" per categorie, e istruzioni finali ("Rispondi con il numero 1-N o descrivi meglio").
- **Status**: IMPLEMENTATO

### FR-012 Limite massimo suggerimenti diretti
- **Pattern EARS**: Il sistema DEVE limitare a massimo 4 suggerimenti diretti di tipo intent (configurabile via max_suggestions).
- **Status**: IMPLEMENTATO

### FR-013 Registry intent con metadati strutturati
- **Pattern EARS**: Il sistema DEVE mantenere un registry (INTENT_REGISTRY) con metadati per ogni intent: intent_id, label, description, category, keywords, context_keywords, negative_keywords, examples, requires_slots, emoji, tool, graph_node, two_phase_threshold, is_direct_response, disambiguation_rules.
- **Status**: IMPLEMENTATO

### FR-014 Gerarchia categoriale con 7 categorie
- **Pattern EARS**: Il sistema DEVE organizzare gli intent in 7 categorie gerarchiche: Piano di Controllo (3 intent), Priorita' e Rischio (5 intent), Ricerca (1 intent), Ritardi e Monitoraggio (2 intent), Storico e Analisi (2 intent), Procedure Operative (1 intent), Altro (3 intent, escluso dal menu utente).
- **Status**: IMPLEMENTATO

### FR-015 Validazione registry al caricamento
- **Pattern EARS**: QUANDO il modulo intent_metadata viene caricato, il sistema DEVE eseguire una validazione automatica verificando: (a) tutti gli intent in CATEGORY_HIERARCHY esistono in INTENT_REGISTRY, (b) tutti gli intent in INTENT_REGISTRY (eccetto fallback) sono assegnati a una categoria. SE ci sono errori, il sistema DEVE emettere un warning.
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### FR-NF-001 Latenza target Fase 1 keyword matching
- **Pattern EARS**: La Fase 1 (keyword matching) DEVE completarsi in circa 50ms per garantire responsivita' anche senza LLM.
- **Status**: IMPLEMENTATO

### FR-NF-002 Configurabilita' engine
- **Pattern EARS**: Il sistema DEVE supportare override della configurazione default tramite dizionario config passato al costruttore, con valori di default per: enabled (True), keyword_threshold (15), max_suggestions (4), llm_timeout (5), max_consecutive_fallbacks (3), enable_llm_phase (True), enable_category_menu (True).
- **Status**: IMPLEMENTATO
