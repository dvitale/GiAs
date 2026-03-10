# Theme System

**Componente**: Frontend (gchat)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: statics/css/style.css, statics/js/chat.js (initializeTheme, toggleTheme), statics/js/history.js (initTheme)

## Requisiti Funzionali

### TS-01 Due Temi Light e Dark
- **Pattern EARS**: Il sistema DEVE supportare due temi: light (default, palette warm/beige con accent `#d4a574`) e dark (palette `#1a1a1a` con accent viola `#8b5cf6`), attivato dalla classe CSS `dark-theme` su body.
- **Status**: IMPLEMENTATO

### TS-02 CSS Variables Toggle
- **Pattern EARS**: QUANDO il tema cambia, il sistema DEVE sovrascrivere le variabili CSS root (--bg-primary, --bg-secondary, --text-primary, --accent-color, --shadow-*, etc.) tramite il selettore `body.dark-theme`.
- **Status**: IMPLEMENTATO

### TS-03 LocalStorage Persistenza
- **Pattern EARS**: QUANDO l'utente cambia tema, il sistema DEVE salvare la preferenza in localStorage con chiave `theme` e valore `dark` o `light`.
- **Status**: IMPLEMENTATO

### TS-04 Ripristino Tema al Caricamento
- **Pattern EARS**: QUANDO la pagina si carica, il sistema DEVE leggere la preferenza da localStorage e, se il valore e' `dark`, aggiungere la classe `dark-theme` al body.
- **Status**: IMPLEMENTATO

### TS-05 Transizioni 0.3s
- **Pattern EARS**: Il sistema DEVE applicare transizioni di 0.3s ease su background-color, border-color e color per un cambio tema fluido.
- **Status**: IMPLEMENTATO

### TS-06 Icona Sole/Luna
- **Pattern EARS**: QUANDO il tema e' light, il sistema DEVE mostrare l'icona sole (sun-icon). QUANDO il tema e' dark, DEVE mostrare l'icona luna (moon-icon), alternando la visibilita' con `display: block/none`.
- **Status**: IMPLEMENTATO

### TS-07 Header Gradients
- **Pattern EARS**: QUANDO il tema e' light, l'header DEVE avere gradiente `#c49464 -> #a07850`. QUANDO il tema e' dark, l'header DEVE avere gradiente `#1e1e1e -> #2d2d2d`.
- **Status**: IMPLEMENTATO

### TS-08 Tema Consistente tra Pagine
- **Pattern EARS**: Il sistema DEVE inizializzare il tema da localStorage su tutte le pagine (index, history, debug, debug_langgraph) per mantenere la preferenza utente.
- **Status**: IMPLEMENTATO

### TS-09 Admin/Analytics/Monitor Dark-Only
- **Pattern EARS**: Le pagine analytics, monitor e admin_rag DEVONO utilizzare esclusivamente il tema dark con palette dedicata (--bg-primary: #0f172a, gradiente sfondo indaco/slate).
- **Status**: IMPLEMENTATO

### TS-10 Dark Theme ASL Badge
- **Pattern EARS**: QUANDO il tema e' dark, il badge ASL nell'header DEVE usare sfondo `rgba(139, 92, 246, 0.3)` (viola) al posto dello sfondo bianco trasparente del tema light.
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### TS-NF01 No Flash of Unstyled Content
- **Pattern EARS**: Il sistema DEVE applicare il tema salvato il prima possibile al caricamento per evitare flash visivi del tema sbagliato.
- **Status**: IMPLEMENTATO
- **Note**: L'inizializzazione avviene nel costruttore della classe ChatBot o in un blocco script inline immediatamente dopo il body.
