# Admin, Analytics e Monitor

**Componente**: Frontend (gchat)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: template/analytics.html, template/monitor.html, template/admin_rag.html

## Requisiti Funzionali

### AM-01 Dashboard analytics con metriche e grafici
- **Pattern EARS**: QUANDO la pagina analytics si carica, il sistema DEVE mostrare 6 card di riepilogo (Messaggi Totali, Errori, Tempo Medio, Sessioni, ASL Attive, P95), un selettore periodo (1/7/30/90 giorni con granularita' automatica hour/day), una tabella degli intent piu' frequenti con badge e barre di progresso, una tabella delle ASL piu' attive con badge verdi e barre di progresso, e gli ultimi 30 messaggi con filtro per ASL visualizzando domanda, risposta troncata, intent, tempo di risposta ed errori.
- **Status**: IMPLEMENTATO
- **Accorpa**: AM-01, AM-05, AM-06, AM-07, AM-08

### AM-02 Analytics Auto-Refresh 60s
- **Pattern EARS**: MENTRE la pagina analytics e' aperta, il sistema DEVE aggiornare automaticamente i dati ogni 60 secondi.
- **Status**: IMPLEMENTATO

### AM-03 Analytics Chiamate Dirette Backend
- **Pattern EARS**: La pagina analytics DEVE chiamare direttamente il backend Python (`backendUrl` iniettato dal template) senza passare dal proxy Go, per gli endpoint `/api/chat-log/*`.
- **Status**: IMPLEMENTATO

### AM-04 Analytics Timeline Bar Chart CSS
- **Pattern EARS**: Il sistema DEVE renderizzare un grafico a barre timeline usando div CSS con altezza proporzionale al conteggio messaggi, tooltip al hover con timestamp e conteggio, e gradiente blu/indaco.
- **Status**: IMPLEMENTATO

### AM-09 Monitor problemi e severita'
- **Pattern EARS**: Il sistema DEVE riconoscere e visualizzare 10 tipi di problema (fallback_loop, repeated_question, post_intent_fallback, ignored_slots, timeout, intent_pingpong, short_response, twophase_abandoned, long_session, llm_incoherence), classificarli in 4 livelli di severita' (critical rosso #f87171, high arancione #fb923c, medium giallo #fbbf24, low blu #3b82f6) con card colorate, e mostrare 4 card di riepilogo severita' con conteggio e bordo sinistro colorato. Il sistema DEVE inoltre mostrare la distribuzione dei tipi di problema in un pannello dedicato.
- **Status**: IMPLEMENTATO
- **Accorpa**: AM-09, AM-10, AM-11, AM-16

### AM-12 Monitor filtri e auto-refresh
- **Pattern EARS**: Il sistema DEVE fornire filtri per periodo (1/7/30/90 giorni), ASL (dropdown dinamico da API) e severita' minima (Low+/Medium+/High+/Solo Critical). MENTRE la pagina monitor e' aperta, il sistema DEVE aggiornare automaticamente i dati ogni 120 secondi.
- **Status**: IMPLEMENTATO
- **Accorpa**: AM-12, AM-13

### AM-14 Monitor visualizzazione card e dettagli
- **Pattern EARS**: Il sistema DEVE mostrare i problemi critici e alti come card con bordo sinistro colorato per severita', tipo, descrizione e metadata (sessione, ASL, data). DEVE mostrare un pannello di raccomandazioni con suggerimenti basati sui problemi rilevati. DEVE mostrare una tabella scrollabile (max 600px) con tutti i problemi, badge severita' e tipo, e card espandibili. DEVE mostrare una sezione riepilogo con sfondo gradiente blu/viola contenente statistiche aggregate.
- **Status**: IMPLEMENTATO
- **Accorpa**: AM-14, AM-15, AM-17, AM-18

### AM-19 Admin RAG CRUD e reindicizzazione
- **Pattern EARS**: La pagina admin_rag DEVE utilizzare esclusivamente il tema dark con la stessa palette delle altre pagine admin. DEVE permettere la gestione CRUD (creazione, lettura, cancellazione) delle domande RAG tramite form e tabella, mostrare la lista dei documenti PDF indicizzati con possibilita' di download, e permettere il lancio della reindicizzazione RAG con stato di avanzamento.
- **Status**: IMPLEMENTATO
- **Accorpa**: AM-19, AM-20, AM-21, AM-22

### AM-23 Nessuna Autenticazione Admin
- **Pattern EARS**: Le pagine admin (admin/rag) DEVONO essere accessibili senza autenticazione.
- **Status**: PARZIALE
- **Note**: La pagina admin_rag non richiede autenticazione ne' autorizzazione. Nessun controllo accesso e' implementato.

### AM-24 HTML Escape Dati Dinamici
- **Pattern EARS**: Il sistema DEVE eseguire l'escape HTML su tutti i dati dinamici inseriti nel DOM (titoli conversazioni, messaggi, nomi ASL, intent) per prevenire XSS.
- **Status**: IMPLEMENTATO

### AM-25 Navigazione Cross-Page
- **Pattern EARS**: Le pagine analytics, monitor e debug DEVONO mostrare un menu di navigazione orizzontale con link a Chat, Analytics, Monitor, Debug e LangGraph, preservando i queryParams.
- **Status**: IMPLEMENTATO

### AM-26 Analytics ASL Filter Dropdown
- **Pattern EARS**: Il sistema DEVE popolare dinamicamente il dropdown filtro ASL dalle API del backend e filtrare i messaggi recenti per ASL selezionata.
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### AM-NF01 Palette Dark Consistente
- **Pattern EARS**: Le pagine analytics, monitor e admin_rag DEVONO utilizzare la stessa palette dark con variabili CSS condivise (--bg-primary: #0f172a, --bg-secondary: #1e293b, etc.).
- **Status**: IMPLEMENTATO

### AM-NF02 Responsive Panels Grid
- **Pattern EARS**: Il sistema DEVE disporre i panel in griglia a 2 colonne sopra 1000px di larghezza e a singola colonna sotto 1000px.
- **Status**: IMPLEMENTATO

### AM-NF03 Scrollbar Personalizzata
- **Pattern EARS**: Le pagine admin DEVONO utilizzare scrollbar personalizzate con colori coerenti con il tema dark.
- **Status**: IMPLEMENTATO
