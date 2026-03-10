# History Page

**Componente**: Frontend (gchat)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: statics/js/history.js, template/history.html, statics/css/style.css

## Requisiti Funzionali

### HP-01 Codice Fiscale Obbligatorio
- **Pattern EARS**: QUANDO la pagina si carica senza `codice_fiscale` nei queryParams, il sistema DEVE mostrare il messaggio di errore "Codice fiscale non disponibile. Accedi dalla pagina principale." e non caricare le conversazioni.
- **Status**: IMPLEMENTATO

### HP-02 Caricamento Conversazioni API
- **Pattern EARS**: QUANDO la pagina si carica con codice_fiscale valido, il sistema DEVE chiamare GET `/api/chat-log/user-conversations?codice_fiscale={cf}&limit=50&offset=0` per ottenere la lista delle conversazioni.
- **Status**: IMPLEMENTATO

### HP-03 Paginazione Limit 50
- **Pattern EARS**: Il sistema DEVE caricare le conversazioni a pagine di 50 elementi, mostrando il bottone "Carica altre" se ci sono piu' conversazioni disponibili.
- **Status**: IMPLEMENTATO

### HP-04 Load More Button
- **Pattern EARS**: QUANDO l'utente clicca "Carica altre", il sistema DEVE incrementare l'offset di 50, caricare le nuove conversazioni e concatenarle alla lista esistente, aggiornando il testo del bottone a "Caricamento..." durante il caricamento.
- **Status**: IMPLEMENTATO

### HP-05 Search Debounce 300ms
- **Pattern EARS**: QUANDO l'utente digita nel campo di ricerca, il sistema DEVE attendere 300ms dopo l'ultimo input prima di filtrare le conversazioni lato client per titolo e ASL.
- **Status**: IMPLEMENTATO

### HP-06 Filtro Client-Side
- **Pattern EARS**: QUANDO l'utente cerca, il sistema DEVE filtrare le conversazioni in memoria verificando se il titolo o l'ASL contengono il testo cercato (case-insensitive).
- **Status**: IMPLEMENTATO

### HP-07 Date Relative
- **Pattern EARS**: QUANDO si formattano le date nella lista conversazioni, il sistema DEVE usare formato relativo: "Oggi HH:MM" per oggi, "Ieri HH:MM" per ieri, giorno della settimana abbreviato per gli ultimi 7 giorni, "DD MMM YYYY" per date piu' vecchie.
- **Status**: IMPLEMENTATO

### HP-08 Caricamento Messaggi Conversazione
- **Pattern EARS**: QUANDO l'utente seleziona una conversazione, il sistema DEVE chiamare GET `/api/chat-log/conversation/{sessionId}?codice_fiscale={cf}` e renderizzare i messaggi con domanda (user-message) e risposta (bot-message).
- **Status**: IMPLEMENTATO

### HP-09 Formattazione Risposte
- **Pattern EARS**: QUANDO si renderizzano le risposte, il sistema DEVE eseguire l'escape HTML, convertire `**text**` in `<strong>` e `\n` in `<br>`.
- **Status**: IMPLEMENTATO

### HP-10 Sidebar 300px Desktop
- **Pattern EARS**: MENTRE lo schermo e' piu' largo di 768px, il sistema DEVE mostrare la sidebar a sinistra con larghezza fissa di 300px con lista conversazioni, campo ricerca e bottone "Carica altre".
- **Status**: IMPLEMENTATO

### HP-11 Sidebar Drawer Mobile
- **Pattern EARS**: MENTRE lo schermo e' piu' stretto di 768px, il sistema DEVE nascondere la sidebar come drawer con `translateX(-100%)`, mostrare un bottone toggle fisso in basso a sinistra e un overlay scuro quando aperta.
- **Status**: IMPLEMENTATO

### HP-12 Chiusura Sidebar Mobile
- **Pattern EARS**: QUANDO l'utente seleziona una conversazione su mobile, il sistema DEVE chiudere automaticamente la sidebar drawer.
- **Status**: IMPLEMENTATO

### HP-13 Query Params Propagazione
- **Pattern EARS**: Il sistema DEVE propagare i queryParams (user_id, asl_id, asl_name, codice_fiscale, username) nei link di navigazione (torna alla chat, link cronologia attivo) per mantenere il contesto utente.
- **Status**: IMPLEMENTATO

### HP-14 Escape HTML e JS
- **Pattern EARS**: Il sistema DEVE eseguire l'escape HTML nei titoli e session_id tramite `escapeHtml` (createElement textContent), e l'escape JavaScript nei callback onclick tramite `escapeJs` (escape backslash e singola apice).
- **Status**: IMPLEMENTATO

### HP-15 Conversazione Attiva Highlight
- **Pattern EARS**: QUANDO una conversazione e' selezionata, il sistema DEVE evidenziarla nella sidebar con classe `active` (sfondo accent-light e bordo sinistro accent-color).
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### HP-NF01 Tema Condiviso
- **Pattern EARS**: Il sistema DEVE inizializzare il tema light/dark da localStorage come la pagina principale, con toggle funzionante.
- **Status**: IMPLEMENTATO
