# Chat UI

**Componente**: Frontend (gchat)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: statics/js/chat.js, template/index.html, statics/css/style.css

## Requisiti Funzionali

### CU-01 Classe ChatBot
- **Pattern EARS**: Il sistema DEVE istanziare la classe `ChatBot` al caricamento del DOM e assegnarla a `window.chatBot` per renderla accessibile globalmente.
- **Status**: IMPLEMENTATO

### CU-02 Welcome e transizione chat
- **Pattern EARS**: QUANDO l'applicazione si carica, il sistema DEVE mostrare la welcome screen con greeting, input area e quick actions, nascondendo la chat screen. QUANDO l'utente invia il primo messaggio, il sistema DEVE nascondere la welcome screen, mostrare la chat screen, spostare i quick action buttons nella chat screen e fare focus sull'input della chat.
- **Status**: IMPLEMENTATO
- **Accorpa**: CU-02, CU-03

### CU-04 Sender ID Generazione
- **Pattern EARS**: Il sistema DEVE generare un sender ID unico per sessione nel formato `user_` + timestamp + `_` + 9 caratteri random alfanumerici (base36).
- **Status**: IMPLEMENTATO

### CU-05 Greeting Dinamico
- **Pattern EARS**: QUANDO l'applicazione si carica, il sistema DEVE mostrare un saluto basato sull'ora: `Buongiorno` (5-11), `Buon pomeriggio` (12-17), `Buonasera` (18-4), aggiungendo il nome utente se disponibile da `window.welcomeData.userName`.
- **Status**: IMPLEMENTATO

### CU-06 Quick actions da API
- **Pattern EARS**: QUANDO l'applicazione si carica, il sistema DEVE caricare le domande predefinite da GET `/api/predefined-questions` e renderizzarle come bottoni ordinati per campo `order`, con icona SVG diversa per categoria (help, piani, priorita, default). QUANDO l'utente clicca un quick action, il sistema DEVE inserire il testo della domanda nell'input e fare focus. QUANDO l'utente fa Ctrl+Click (o Cmd+Click), il sistema DEVE inviare direttamente la domanda senza inserirla nell'input.
- **Status**: IMPLEMENTATO
- **Accorpa**: CU-06, CU-07, CU-08, CU-41

### CU-09 Streaming SSE con fallback
- **Pattern EARS**: QUANDO lo streaming e' abilitato (window.streamingEnabled) e il browser supporta ReadableStream, il sistema DEVE inviare messaggi via SSE endpoint `/chat/stream`. QUANDO un evento SSE di tipo `status` o `reasoning` arriva, DEVE aggiornare il thinking message; QUANDO un evento `error` arriva, DEVE mostrare l'errore; QUANDO un evento `final` arriva, DEVE mostrare il messaggio completo con suggestions e fallback_intents. In caso di errore, DEVE fare fallback al modo sincrono `/chat`.
- **Status**: IMPLEMENTATO
- **Accorpa**: CU-09, CU-37

### CU-10 Thinking indicator
- **Pattern EARS**: MENTRE il sistema attende una risposta streaming, il sistema DEVE mostrare un messaggio "thinking" con tre pallini pulsanti e testo italico aggiornabile (es. "Analizzando...", nome nodo, etc.). QUANDO la risposta finale arriva, DEVE rimuovere il thinking message con animazione fade-out di 0.3 secondi.
- **Status**: IMPLEMENTATO
- **Accorpa**: CU-10, CU-11

### CU-12 Download Conversazione TXT
- **Pattern EARS**: QUANDO un messaggio bot non-fallback e' visualizzato, il sistema DEVE mostrare un bottone "Scarica" che genera un file `.txt` con timestamp, informazioni utente, domanda, risposta pulita (senza HTML) e dati completi JSON se presenti.
- **Status**: IMPLEMENTATO

### CU-13 Download Escluso per Fallback
- **Pattern EARS**: SE il messaggio contiene keyword di fallback (`non ho capito`, `mi dispiace`, `non riesco`, `si e' verificato un errore`, `riprova piu' tardi`, `controlla la tua connessione`), il sistema DEVE non mostrare il bottone download.
- **Status**: IMPLEMENTATO

### CU-14 Liste Collassabili
- **Pattern EARS**: QUANDO un messaggio contiene una lista con piu' di 10 elementi (COLLAPSE_THRESHOLD), il sistema DEVE nascondere gli elementi oltre il 10mo e mostrare un bottone "Mostra tutti i N risultati (+M)" per espanderli.
- **Status**: IMPLEMENTATO

### CU-15 Guided learning e question links
- **Pattern EARS**: QUANDO il backend restituisce `fallback_intents`, il sistema DEVE mostrare bottoni di guided learning con emoji, label e descrizione per ogni intent suggerito, con un link "Nessuna di queste" per dismissare. QUANDO l'utente seleziona un intent, il sistema DEVE inviare la scelta al backend via POST `/api/admin/guided-learn`, mostrare feedback e auto-dismissare il container dopo 4 secondi con fade-out.
- **Status**: IMPLEMENTATO
- **Accorpa**: CU-15, CU-16

### CU-17 Sessione e suggerimenti
- **Pattern EARS**: QUANDO il testo del messaggio contiene `[[testo]]`, il sistema DEVE convertirlo in un link cliccabile con classe `question-link` che, al click, inserisce il testo nell'input (o lo invia direttamente con Ctrl+Click). QUANDO il testo contiene `[testo](url)`, il sistema DEVE convertirlo in un link con classe `doc-download-link` che apre l'URL in una nuova tab.
- **Status**: IMPLEMENTATO
- **Accorpa**: CU-17, CU-18

### CU-19 Session Reset
- **Pattern EARS**: QUANDO l'utente clicca "+ Nuova Chat", il sistema DEVE: (1) inviare POST a `/session/reset`, (2) rigenerare il senderId, (3) svuotare i messaggi, (4) tornare alla welcome screen, (5) resettare gli input, (6) nascondere il typing indicator, (7) fare focus sull'input.
- **Status**: IMPLEMENTATO

### CU-20 Suggestions Chip
- **Pattern EARS**: QUANDO il backend restituisce `suggestions`, il sistema DEVE mostrare chip cliccabili sotto il messaggio con header "Cosa vuoi fare ora?" che inseriscono la query nell'input (click) o la inviano direttamente (Ctrl+click).
- **Status**: IMPLEMENTATO

### CU-21 Shortcut navigazione debug via logo
- **Pattern EARS**: QUANDO l'utente fa Ctrl+Click sul logo GIAS, il sistema DEVE navigare alla pagina debug mantenendo la query string corrente. QUANDO l'utente fa Shift+Click sul logo GIAS, il sistema DEVE navigare alla pagina LangGraph debugger mantenendo la query string corrente.
- **Status**: IMPLEMENTATO
- **Accorpa**: CU-21, CU-22

### CU-23 Accessibilita' role=log
- **Pattern EARS**: Il sistema DEVE configurare l'area messaggi con `role="log"` e `aria-live="polite"` per i lettori di schermo.
- **Status**: IMPLEMENTATO

### CU-24 Scroll-to-bottom button
- **Pattern EARS**: QUANDO l'utente scorre verso l'alto di piu' di 100px dal fondo, il sistema DEVE mostrare un bottone fluttuante "Vai in fondo" che, al click, scrolla alla fine dei messaggi. QUANDO l'utente e' vicino al fondo (entro 100px), il sistema DEVE nascondere il bottone.
- **Status**: IMPLEMENTATO
- **Accorpa**: CU-24, CU-25

### CU-26 Rendering markdown-to-HTML
- **Pattern EARS**: QUANDO si formatta un messaggio, il sistema DEVE: (1) eseguire l'escape dei caratteri HTML (`&`, `<`, `>`) per prevenire injection, (2) convertire `### Header` e `**Header:**` in div con classe `section-header`, (3) convertire `**testo**` in tag `<strong>`, (4) raggruppare righe numerate (`N. `) in un `list-container` con elementi `list-item-compact`, (5) raggruppare righe nel formato `Label: valore` o `**Label:** valore` in un `field-group` con label e value separati.
- **Status**: IMPLEMENTATO
- **Accorpa**: CU-26, CU-27, CU-28, CU-29, CU-30

### CU-31 Input comportamento (typing, resize, send, enter)
- **Pattern EARS**: MENTRE il sistema attende una risposta sincrona, DEVE mostrare un indicatore con tre pallini animati e testo "Sto elaborando..." aggiornabile durante i retry. QUANDO l'utente digita nel textarea, il sistema DEVE ridimensionare automaticamente l'altezza fino a un massimo di 200px. MENTRE l'input e' vuoto, DEVE disabilitare il bottone di invio. QUANDO l'utente preme Enter (senza Shift), DEVE inviare il messaggio; Shift+Enter DEVE inserire un a capo.
- **Status**: IMPLEMENTATO
- **Accorpa**: CU-31, CU-32, CU-33, CU-34

### CU-35 Window Variables Injection
- **Pattern EARS**: Il sistema DEVE iniettare nel template HTML le variabili globali: `window.basePath`, `window.transcriptionEnabled`, `window.streamingEnabled`, `window.welcomeData` e `window.queryParams`.
- **Status**: IMPLEMENTATO

### CU-36 History Link con Query Params
- **Pattern EARS**: Il sistema DEVE costruire dinamicamente l'href del link cronologia aggiungendo i queryParams correnti come query string.
- **Status**: IMPLEMENTATO

### CU-38 Download Nome File
- **Pattern EARS**: QUANDO si scarica una conversazione, il sistema DEVE generare un nome file nel formato `gias-{timestamp}.txt`.
- **Status**: IMPLEMENTATO

### CU-39 Payload ASL Priorita'
- **Pattern EARS**: QUANDO si costruisce il payload per il server, il sistema DEVE usare `asl_name` dal queryParams come campo `asl` con priorita' su `asl_id`.
- **Status**: IMPLEMENTATO

### CU-40 Guided Learning Disabilita Bottoni
- **Pattern EARS**: QUANDO l'utente seleziona un'opzione nel guided learning, il sistema DEVE disabilitare tutti gli altri bottoni e evidenziare quello selezionato.
- **Status**: IMPLEMENTATO

### CU-42 EscapeHtml Utility
- **Pattern EARS**: Il sistema DEVE fornire una funzione `escapeHtml` che converte `&`, `<`, `>`, `"`, `'` nelle entita' HTML corrispondenti.
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### CU-NF01 Smooth Scroll
- **Pattern EARS**: Il sistema DEVE utilizzare `scrollTo` con `behavior: 'smooth'` per lo scrolling automatico ai nuovi messaggi.
- **Status**: IMPLEMENTATO

### CU-NF02 Responsive Layout
- **Pattern EARS**: Il sistema DEVE adattare il layout per schermi sotto 768px (header piu' compatto, messaggi piu' larghi) e sotto 480px (greeting verticale, quick actions a 2 colonne, hierarchy nascosta).
- **Status**: IMPLEMENTATO
