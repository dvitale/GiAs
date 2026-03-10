# Admin, Analytics e Monitor

**Componente**: Frontend (gchat)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: template/analytics.html, template/monitor.html, template/admin_rag.html

## Requisiti Funzionali

### AM-01 Analytics 6 Metriche Summary
- **Pattern EARS**: QUANDO la pagina analytics si carica, il sistema DEVE mostrare 6 card di riepilogo: Messaggi Totali, Errori, Tempo Medio (ms), Sessioni, ASL Attive, P95 (ms).
- **Status**: IMPLEMENTATO

### AM-02 Analytics Auto-Refresh 60s
- **Pattern EARS**: MENTRE la pagina analytics e' aperta, il sistema DEVE aggiornare automaticamente i dati ogni 60 secondi.
- **Status**: IMPLEMENTATO

### AM-03 Analytics Chiamate Dirette Backend
- **Pattern EARS**: La pagina analytics DEVE chiamare direttamente il backend Python (`backendUrl` iniettato dal template) senza passare dal proxy Go, per gli endpoint `/api/chat-log/*`.
- **Status**: IMPLEMENTATO

### AM-04 Analytics Timeline Bar Chart CSS
- **Pattern EARS**: Il sistema DEVE renderizzare un grafico a barre timeline usando div CSS con altezza proporzionale al conteggio messaggi, tooltip al hover con timestamp e conteggio, e gradiente blu/indaco.
- **Status**: IMPLEMENTATO

### AM-05 Analytics Period Selector
- **Pattern EARS**: Il sistema DEVE fornire un selettore periodo con opzioni: 1 giorno, 7 giorni (default), 30 giorni, 90 giorni, con granularita' automatica (hour per <=7 giorni, day per >7 giorni).
- **Status**: IMPLEMENTATO

### AM-06 Analytics Top Intent Panel
- **Pattern EARS**: Il sistema DEVE mostrare una tabella degli intent piu' frequenti con badge colorati e barre di progresso proporzionali.
- **Status**: IMPLEMENTATO

### AM-07 Analytics Top ASL Panel
- **Pattern EARS**: Il sistema DEVE mostrare una tabella delle ASL piu' attive con badge colorati verdi e barre di progresso proporzionali.
- **Status**: IMPLEMENTATO

### AM-08 Analytics Recent Messages
- **Pattern EARS**: Il sistema DEVE mostrare gli ultimi 30 messaggi con filtro per ASL, visualizzando domanda, risposta troncata, intent, tempo di risposta ed eventuali errori.
- **Status**: IMPLEMENTATO

### AM-09 Monitor Problem Types
- **Pattern EARS**: Il sistema DEVE riconoscere e visualizzare 10 tipi di problema: fallback_loop, repeated_question, post_intent_fallback, ignored_slots, timeout, intent_pingpong, short_response, twophase_abandoned, long_session, llm_incoherence.
- **Status**: IMPLEMENTATO

### AM-10 Monitor Severity 4 Livelli
- **Pattern EARS**: Il sistema DEVE classificare i problemi in 4 livelli di severita' (critical, high, medium, low) con card colorate: critical (rosso #f87171), high (arancione #fb923c), medium (giallo #fbbf24), low (blu #3b82f6).
- **Status**: IMPLEMENTATO

### AM-11 Monitor Severity Cards
- **Pattern EARS**: Il sistema DEVE mostrare 4 card di riepilogo severita' con conteggio e bordo sinistro colorato per livello.
- **Status**: IMPLEMENTATO

### AM-12 Monitor Filtri
- **Pattern EARS**: Il sistema DEVE fornire filtri per: periodo (1/7/30/90 giorni), ASL (dropdown dinamico da API), severita' minima (Low+/Medium+/High+/Solo Critical).
- **Status**: IMPLEMENTATO

### AM-13 Monitor Auto-Refresh 120s
- **Pattern EARS**: MENTRE la pagina monitor e' aperta, il sistema DEVE aggiornare automaticamente i dati ogni 120 secondi (2 minuti).
- **Status**: IMPLEMENTATO

### AM-14 Monitor Problem Cards
- **Pattern EARS**: Il sistema DEVE mostrare i problemi critici e alti come card con bordo sinistro colorato per severita', tipo di problema, descrizione, metadata (sessione, ASL, data).
- **Status**: IMPLEMENTATO

### AM-15 Monitor Raccomandazioni
- **Pattern EARS**: Il sistema DEVE mostrare un pannello di raccomandazioni con suggerimenti basati sui problemi rilevati, stilizzati come lista con bordo sinistro blu.
- **Status**: IMPLEMENTATO

### AM-16 Monitor Distribuzione Tipi
- **Pattern EARS**: Il sistema DEVE mostrare la distribuzione dei tipi di problema in un pannello dedicato.
- **Status**: IMPLEMENTATO

### AM-17 Monitor Tabella Tutti i Problemi
- **Pattern EARS**: Il sistema DEVE mostrare una tabella scrollabile (max 600px) con tutti i problemi, badge severita' e tipo, e card espandibili.
- **Status**: IMPLEMENTATO

### AM-18 Monitor Summary Section
- **Pattern EARS**: Il sistema DEVE mostrare una sezione riepilogo con sfondo gradiente blu/viola contenente statistiche aggregate.
- **Status**: IMPLEMENTATO

### AM-19 Admin RAG Dark-Only
- **Pattern EARS**: La pagina admin_rag DEVE utilizzare esclusivamente il tema dark con la stessa palette delle altre pagine admin (sfondo indaco/slate).
- **Status**: IMPLEMENTATO

### AM-20 Admin RAG CRUD Domande
- **Pattern EARS**: La pagina admin_rag DEVE permettere la gestione CRUD (creazione, lettura, cancellazione) delle domande RAG tramite form e tabella.
- **Status**: IMPLEMENTATO

### AM-21 Admin RAG Lista PDF
- **Pattern EARS**: La pagina admin_rag DEVE mostrare la lista dei documenti PDF indicizzati con possibilita' di download.
- **Status**: IMPLEMENTATO

### AM-22 Admin RAG Reindicizzazione
- **Pattern EARS**: La pagina admin_rag DEVE permettere il lancio della reindicizzazione RAG e mostrare lo stato di avanzamento.
- **Status**: IMPLEMENTATO

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
